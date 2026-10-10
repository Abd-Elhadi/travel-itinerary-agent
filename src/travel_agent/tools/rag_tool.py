import json
from typing import Any, Dict
from agents import function_tool
from travel_agent.rag.manager import GlobalRAGManager

_rag_manager = GlobalRAGManager()

def search_destination_knowledge_raw(destination: str, query: str) -> Dict[str, Any]:
    """Retrieves rich qualitative travel insights using ChromaDB + DuckDuckGo RAG."""
    contexts = _rag_manager.query_destination_context(destination=destination, query=query, top_k=3)
    return {
        "destination": destination,
        "query": query,
        "contexts": contexts,
        "count": len(contexts),
    }

@function_tool
def search_destination_knowledge(destination: str, query: str) -> str:
    """Retrieves travel insights, hidden gems, and cultural tips for any global destination.

    Args:
        destination: Target city or country name.
        query: Specific traveler interest or context query.
    """
    return json.dumps(search_destination_knowledge_raw(destination, query))