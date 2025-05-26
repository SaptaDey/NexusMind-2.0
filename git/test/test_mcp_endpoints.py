"""
Test suite for MCP endpoints updated to use Neo4j-native graph_state.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_neo4j_get_graph_state(monkeypatch):
    """
    Monkeypatch the Neo4j graph state retrieval to return a predictable result.
    """
    def _mock(run_id):
        return {
            "nodes": [{"id": "node1", "labels": ["TestNode"]}],
            "edges": [{"source": "node1", "target": "node2", "type": "TEST_EDGE"}]
        }
    monkeypatch.setattr("app.services.neo4j.get_graph_state", _mock)
    return _mock


def test_get_run_without_graph_state():
    """
    Test that graph_state_full and graph_state are omitted by default.
    """
    run_id = "test-run-123"
    response = client.get(f"/mcp/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert "graph_state_full" not in data
    assert "graph_state" not in data


def test_get_run_with_graph_state():
    """
    Test that graph_state is returned when include_graph_state=true
    and graph_state_full is not present.
    """
    run_id = "test-run-123"
    response = client.get(f"/mcp/runs/{run_id}?include_graph_state=true")
    assert response.status_code == 200
    data = response.json()
    assert "graph_state_full" not in data
    assert "graph_state" in data
    assert isinstance(data["graph_state"], dict)
    expected = {
        "nodes": [{"id": "node1", "labels": ["TestNode"]}],
        "edges": [{"source": "node1", "target": "node2", "type": "TEST_EDGE"}]
    }
    assert data["graph_state"] == expected