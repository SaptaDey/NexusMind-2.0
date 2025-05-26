from fastapi import APIRouter, HTTPException
from src.asr_got_reimagined.domain.models.graph_state import GraphStateSchema
from src.asr_got_reimagined.services.mcp_service import get_session_data

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/session-data/{session_id}")
async def fetch_session_data(session_id: str):
    """
    Retrieve session data and associated graph state for the given session ID.
    """
    session_data_result = await get_session_data(session_id)
    graph_state = session_data_result.graph_state

    if isinstance(graph_state, GraphStateSchema):
        response_graph_state = graph_state
    elif isinstance(graph_state, dict):
        response_graph_state = GraphStateSchema(**graph_state)
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported graph state type: {type(graph_state).__name__}"
        )

    return {
        "session_data": session_data_result.session_data,
        "graph_state": response_graph_state
    }