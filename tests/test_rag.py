from unittest.mock import patch

from travel_agent.rag.manager import GlobalRAGManager


@patch("travel_agent.rag.manager.DDGS")
def test_global_rag_flow(mock_ddgs_class, tmp_path):
    # Mock DDGS text search response
    mock_instance = mock_ddgs_class.return_value
    mock_instance.text.return_value = [
        {"title": "Gullfoss Waterfall", "body": "Iconic waterfall along the Golden Circle in Iceland.", "href": "https://example.com/gullfoss"},
        {"title": "Blue Lagoon", "body": "Famous geothermal spa located near Reykjavik.", "href": "https://example.com/bluelagoon"}
    ]

    test_db = str(tmp_path / "test_vectorstore")
    rag = GlobalRAGManager(db_path=test_db)

    # First call: Cache miss -> triggers mock DDGS search -> populates ChromaDB
    contexts = rag.query_destination_context(destination="Reykjavik", query="best food spots and geothermal baths")
    assert isinstance(contexts, list)
    assert len(contexts) > 0

    # Order-agnostic check across returned contexts
    combined_context = " ".join(contexts)
    assert "Blue Lagoon" in combined_context
    assert "Gullfoss" in combined_context
