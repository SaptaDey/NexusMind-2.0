"""
git/src/asr_got_reimagined/api/routes/mcp.py

Flask routes for MCP session‐data endpoints.
"""

from flask import Blueprint, request, jsonify, abort
from src.asr_got_reimagined.domain.models.graph_state import GraphStateSchema
from src.asr_got_reimagined.services.mcp_service import get_session_data

mcp_bp = Blueprint("mcp", __name__, url_prefix="/mcp")

@mcp_bp.route("/session/<string:session_id>/data", methods=["GET"])
def get_session_data_route(session_id):
    """
    Retrieve session data for the given session ID and return its graph state.
    """
    session_data_result = get_session_data(session_id)
    if not session_data_result:
        abort(404, description=f"Session data not found for ID {session_id}")

    graph_state = session_data_result.graph_state
    if isinstance(graph_state, GraphStateSchema):
        response_graph_state = graph_state
    elif isinstance(graph_state, dict):
        response_graph_state = GraphStateSchema(**graph_state)
    else:
        abort(500, description="Unsupported graph state type received")

    return jsonify({
        "sessionId": session_data_result.session_id,
        "graphState": response_graph_state.dict()
    })