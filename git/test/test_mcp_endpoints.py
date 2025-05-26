import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

class TestMcpEndpoints:

    def test_get_mcp_default_graph_state(self, client):
        response = client.get('/mcp')
        assert response.status_code == 200
        data = response.get_json()
        # Deprecated field should no longer appear
        assert 'graph_state_full' not in data
        # No graph state by default
        assert 'graph_state' not in data
        # Ensure other expected fields remain
        assert 'clusters' in data

    def test_get_mcp_without_graph_state(self, client):
        response = client.get('/mcp?include_graph_state=false')
        assert response.status_code == 200
        data = response.get_json()
        # Explicit exclusion yields no graph_state
        assert 'graph_state' not in data

    def test_get_mcp_with_graph_state(self, client):
        response = client.get('/mcp?include_graph_state=true')
        assert response.status_code == 200
        data = response.get_json()
        # Ensure deprecated field removed
        assert 'graph_state_full' not in data
        # New graph_state field is present
        assert 'graph_state' in data
        graph_state = data['graph_state']
        assert isinstance(graph_state, dict)
        # Validate structure from Neo4j
        assert 'nodes' in graph_state
        assert 'relationships' in graph_state

    def test_get_mcp_by_id_include_graph_state(self, client):
        # Assumes an MCP with ID 1 exists in test DB or fixture setup
        response = client.get('/mcp/1?include_graph_state=true')
        assert response.status_code == 200
        data = response.get_json()
        assert 'graph_state_full' not in data
        assert 'graph_state' in data