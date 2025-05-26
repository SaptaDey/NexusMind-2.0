from fastapi import APIRouter, HTTPException

from src.asr_got_reimagined.domain.services.mcp_service import get_session_data
from src.asr_got_reimagined.api.schemas.graph_state import GraphStateSchema

router = APIRouter(prefix="/mcp", tags=["mcp"])

@router.get("/session/{session_id}", response_model=GraphStateSchema)
async def get_session_graph_state(session_id: str):
    """
    Retrieve the graph state for the specified session.
    """
    session_data_result = get_session_data(session_id)
    if session_data_result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    graph_state = session_data_result.graph_state

        return graph_state
    elif isinstance(graph_state, dict):
        return GraphStateSchema(**graph_state)
    else:
        raise HTTPException(status_code=500, detail="Unsupported graph state format")