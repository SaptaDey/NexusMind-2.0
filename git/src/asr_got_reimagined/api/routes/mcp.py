from fastapi import APIRouter, HTTPException
from src.asr_got_reimagined.domain.models.graph_state import GraphState
from src.asr_got_reimagined.domain.schemas.graph_state import GraphStateSchema
from src.asr_got_reimagined.services.mcp_service import get_mcp_session_data

router = APIRouter(prefix="/mcp", tags=["mcp"])

@router.get("/session/{session_id}")
async def get_mcp_session(session_id: str):
    """
    Retrieve MCP session data including its graph state.
    """
    # Fetch the session data result from the service layer
    session_data_result = await get_mcp_session_data(session_id)
    graph_state = session_data_result.graph_state

    # Serialize based on the type of graph_state
    if isinstance(graph_state, GraphState):
        response_graph = GraphStateSchema.from_orm(graph_state)
    elif isinstance(graph_state, dict):
        # Construct schema directly from a dict
        response_graph = GraphStateSchema(**graph_state)
    else:
        # Unknown type: error out
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported graph state type: {type(graph_state).__name__}"
        )

    return {
        "session_id": session_id,
        "graph_state": response_graph.dict(),
    }