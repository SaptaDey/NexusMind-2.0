import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def new_mcp_id():
    """
    Create a sample MCP for testing and return its ID.
    """
    payload = {"title": "Test MCP", "description": "A test material change proposal"}
    resp = client.post("/api/v1/mcps", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]

def test_get_mcp_graph_without_include_graph_state(new_mcp_id):
    """
    When include_graph_state is not requested, the response should not contain
    the new 'graph_state' field.
    """
    response = client.get(f"/api/v1/mcps/{new_mcp_id}/graph")
    assert response.status_code == 200
    data = response.json()
    # Old behavior asserted graph_state_full; no longer valid
    # assert "graph_state_full" in data
    assert "graph_state" not in data

def test_get_mcp_graph_with_include_graph_state(new_mcp_id):
    """
    When include_graph_state=true, the response must include the updated
    'graph_state' field returned from Neo4j.
    """
    response = client.get(
        f"/api/v1/mcps/{new_mcp_id}/graph",
        params={"include_graph_state": "true"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "graph_state" in data, "Expected 'graph_state' in response when requested"
    graph_state = data["graph_state"]
    assert isinstance(graph_state, dict), "graph_state should be a JSON object"