import pytest
from flask import Flask

from app import create_app

@pytest.fixture
def client():
    """
    Create and configure a new app instance for each test.
    """
    app = create_app('testing')
    with app.test_client() as client:
        yield client

def test_get_mcp_without_graph_state(client):
    """
    When no include_graph_state flag is provided, the response
    should not contain either the legacy 'graph_state_full' field
    or the new 'graph_state' field.
    """
    response = client.get('/mcp/1')
    assert response.status_code == 200
    data = response.get_json()

    # Ensure legacy full-graph field is removed
    assert 'graph_state_full' not in data
    # Ensure new graph_state is not returned by default
    assert 'graph_state' not in data

def test_get_mcp_with_graph_state(client):
    """
    When include_graph_state=True is provided, the response
    must include the new 'graph_state' field from Neo4j,
    and it must have the expected structure.
    """
    response = client.get('/mcp/1?include_graph_state=True')
    assert response.status_code == 200
    data = response.get_json()

    # Verify presence of the new graph_state field
    assert 'graph_state' in data
    graph_state = data['graph_state']
    assert isinstance(graph_state, dict)

    # Basic structure sanity checks
    assert 'nodes' in graph_state
    assert 'relationships' in graph_state

def test_get_mcp_not_found(client):
    """
    Requesting a non-existent MCP should return 404,
    even if include_graph_state=True is set.
    """
    response = client.get('/mcp/9999?include_graph_state=True')
    assert response.status_code == 404