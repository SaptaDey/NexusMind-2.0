from fastapi import APIRouter, HTTPException
from src.asr_got_reimagined.api.schemas.session_data import SessionDataRequest, SessionDataResponse
from src.asr_got_reimagined.domain.models.graph_state import GraphStateSchema
from src.asr_got_reimagined.domain.services.mcp_service import process_session_data

router = APIRouter(prefix="/mcp", tags=["mcp"])

@router.post("/session", response_model=SessionDataResponse)
async def create_session(request: SessionDataRequest):
    """
    Create a new MCP session and return its initial graph state.
    """
    session_data_result = await process_session_data(request)

    # If the graph state is already a GraphStateSchema, return it directly
    if isinstance(session_data_result.graph_state, GraphStateSchema):
        response_graph_state = session_data_result.graph_state
    # If the graph state arrived as a raw dict, hydrate it into the schema
        response_graph_state = GraphStateSchema(**session_data_result.graph_state)
    else:
        raise HTTPException(
            status_code=500,
            detail="Unsupported graph state type"
        )

    return SessionDataResponse(
        session_id=session_data_result.session_id,
        graph_state=response_graph_state
    )