"""Test suite for MCP endpoints verifying compatibility with Neo4j-native graph_state implementation."""

import pytest
from fastapi.testclient import TestClient
from mcp.api import app

client = TestClient(app)

@pytest.fixture
def sample_mcp_id():
    # Create a new MCP instance for testing
    response = client.post("/mcp", json={})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    return data["id"]

def test_get_mcp_without_graph_state(sample_mcp_id):
    response = client.get(f"/mcp/{sample_mcp_id}")
    assert response.status_code == 200
    data = response.json()
    # Legacy field should be removed and new field not present by default
    assert "graph_state_full" not in data
    assert "graph_state" not in data

def test_get_mcp_with_graph_state(sample_mcp_id):
    response = client.get(f"/mcp/{sample_mcp_id}?include_graph_state=true")
    assert response.status_code == 200
    data = response.json()
    # Ensure legacy field is gone and new field is present
    assert "graph_state_full" not in data
    assert "graph_state" in data
    graph_state = data["graph_state"]
    assert isinstance(graph_state, (list, dict))
    if isinstance(graph_state, list) and graph_state:
        entry = graph_state[0]
        assert "id" in entry
        assert "properties" in entry

def test_list_mcps_without_graph_state():
    response = client.get("/mcp")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    for item in items:
        assert "graph_state_full" not in item
        assert "graph_state" not in item

def test_list_mcps_with_graph_state():
    response = client.get("/mcp?include_graph_state=true")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    for item in items:
        assert "graph_state_full" not in item
        assert "graph_state" in item