import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_mcp_default_response_excludes_graph_state():
    """
    By default, the response must not include graph state.
    """
    response = client.get("/mcp")
    assert response.status_code == 200
    data = response.json()
    # Ensure old field is removed
    assert "graph_state_full" not in data
    # No graph_state unless explicitly requested
    assert "graph_state" not in data


def test_mcp_explicit_exclude_graph_state():
    """
    When include_graph_state=false, the response still must not include graph state.
    """
    response = client.get("/mcp?include_graph_state=false")
    assert response.status_code == 200
    data = response.json()
    assert "graph_state_full" not in data
    assert "graph_state" not in data


def test_mcp_includes_graph_state_when_requested():
    """
    When include_graph_state=true, the response must include the Neo4j-sourced graph_state.
    """
    response = client.get("/mcp?include_graph_state=true")
    assert response.status_code == 200
    data = response.json()

    # Legacy field should no longer appear
    assert "graph_state_full" not in data

    # New graph_state field must be present
    assert "graph_state" in data
    graph_state = data["graph_state"]
    assert isinstance(graph_state, dict)

    # Verify basic structure of the Neo4j graph state
    assert "nodes" in graph_state and isinstance(graph_state["nodes"], list)
    assert "relationships" in graph_state and isinstance(graph_state["relationships"], list)