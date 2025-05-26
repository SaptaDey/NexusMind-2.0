"""Test suite for MCP API endpoints, ensuring compatibility with the Neo4j-native graph state implementation."""
import pytest

def test_mcp_items_endpoint_without_graph_state(client):
    """
    When include_graph_state is not specified,
    the response should not include the graph_state field.
    """
    response = client.get("/mcp/items/123")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "graph_state" not in data
    # The deprecated graph_state_full field is no longer present

def test_mcp_items_endpoint_with_graph_state(client, monkeypatch):
    """
    When include_graph_state=true, the response should include the updated graph_state
    field as returned directly from Neo4j.
    """
    # Stub the Neo4j graph state retrieval to return a predictable structure.
    sample_graph = {
        "nodes": [{"id": "node_1", "labels": ["Example"]}],
        "relationships": [
            {"id": "rel_1", "start": "node_1", "end": "node_2", "type": "CONNECTS"}
        ],
    }
    monkeypatch.setattr("app.services.neo4j.get_graph_state", lambda item_id: sample_graph)

    response = client.get("/mcp/items/123?include_graph_state=true")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "graph_state" in data
    assert data["graph_state"] == sample_graph