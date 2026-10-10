import os
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from duckduckgo_search import DDGS

DB_PATH = "./data/vectorstore"

class GlobalRAGManager:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        self.embed_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="global_travel_cache",
            embedding_function=self.embed_fn
        )

    def search_and_cache(self, destination: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Performs live web search for a targeted query, caches chunks in ChromaDB, and returns them."""
        search_query = f"{destination} {query} activities travel guide"
        results = []
        dest_key = destination.lower()
        
        try:
            ddgs = DDGS()
            raw_results = list(ddgs.text(search_query, max_results=max_results))
            for res in raw_results:
                body = res.get("body") or res.get("snippet", "")
                title = res.get("title", "")
                if body:
                    content = f"{title}: {body}"
                    # Use unique ID per content snippet to avoid collision
                    chunk_id = f"{dest_key}_{abs(hash(content))}"
                    results.append({
                        "id": chunk_id,
                        "text": content,
                        "url": res.get("href", ""),
                        "destination": dest_key,
                        "query_topic": query.lower(),
                    })
        except Exception as e:
            print(f"[RAG Warning] Live search failed for {destination} ('{query}'): {e}")
            return []

        if results:
            self.collection.upsert(
                documents=[r["text"] for r in results],
                metadatas=[
                    {
                        "destination": r["destination"],
                        "url": r["url"],
                        "query_topic": r["query_topic"],
                    }
                    for r in results
                ],
                ids=[r["id"] for r in results]
            )

        return results

    def query_destination_context(
        self,
        destination: str,
        query: str,
        top_k: int = 3,
        distance_threshold: float = 0.75,
    ) -> List[str]:
        """Queries local vector DB first; if empty or semantic relevance is low, backfills with live search."""
        dest_key = destination.lower()
        search_prompt = f"{destination} {query}"

        # 1. Query ChromaDB filtered by destination tag
        cache_results = self.collection.query(
            query_texts=[search_prompt],
            n_results=top_k,
            where={"destination": dest_key},
        )

        docs = cache_results.get("documents", [[]])[0]
        distances = cache_results.get("distances", [[]])[0]

        # 2. Check for cache miss or poor semantic match (high distance score)
        has_poor_relevance = False
        if distances and len(distances) > 0:
            # Distance near 0 means high similarity, > 0.75-0.80 means poor match
            best_distance = distances[0]
            if best_distance > distance_threshold:
                has_poor_relevance = True

        if not docs or has_poor_relevance:
            reason = "Empty cache" if not docs else f"Low relevance match (distance: {distances[0]:.2f})"
            print(f"[RAG Backfill] {reason} for '{destination}' -> '{query}'. Fetching targeted live data...")
            
            fetched = self.search_and_cache(destination, query, max_results=5)
            
            # Re-query ChromaDB now that fresh specific snippets are indexed
            if fetched:
                re_query = self.collection.query(
                    query_texts=[search_prompt],
                    n_results=top_k,
                    where={"destination": dest_key},
                )
                docs = re_query.get("documents", [[]])[0]

        return docs