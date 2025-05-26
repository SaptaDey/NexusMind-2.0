"""
Integration tests for MCP endpoints.

Ensures the deprecated 'graph_state_full' field is removed,
and the new 'graph_state' field is returned when requested.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client


@pytest.fixture
def test_mcp_id(client):
    # Create an MCP for testing
    payload = {"name": "TestMCP", "config": {}}
    response = client.post("/mcp", json=payload)
    assert response.status_code == 201
    data = response.json()
    return data["id"]


def test_get_mcp_without_graph_state(client, test_mcp_id):
    response = client.get(f"/mcp/{test_mcp_id}")
    assert response.status_code == 200
    json_data = response.json()
    # The deprecated field must not appear, and no graph_state by default
    assert "graph_state_full" not in json_data
    assert "graph_state" not in json_data


def test_get_mcp_with_graph_state(client, test_mcp_id):
    response = client.get(f"/mcp/{test_mcp_id}?include_graph_state=true")
    assert response.status_code == 200
    json_data = response.json()
    # Confirm deprecated field is gone and new graph_state is present
    assert "graph_state_full" not in json_data
    assert "graph_state" in json_data

    graph_state = json_data["graph_state"]
    assert isinstance(graph_state, dict)

    # Validate core graph_state structure
    assert "nodes" in graph_state and isinstance(graph_state["nodes"], list)
    assert "relationships" in graph_state and isinstance(graph_state["relationships"], list)