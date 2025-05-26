"""API routes for the MCP service."""
import logging

from fastapi import APIRouter, HTTPException
from src.asr_got_reimagined.domain.schemas.session import SessionDataResult, GraphStateSchema
from src.asr_got_reimagined.service.mcp_service import MCPService

router = APIRouter(prefix="/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)


@router.get("/session/{session_id}", response_model=SessionDataResult)
async def get_session_data(session_id: str):
    """
    Retrieve session data by session_id, normalizing the graph_state to GraphStateSchema.
    """
    service = MCPService()
    session_data_result = await service.get_session_data(session_id)

    if isinstance(graph_state, GraphStateSchema):
        response_graph_state = graph_state
    elif isinstance(graph_state, dict):
        response_graph_state = GraphStateSchema(**graph_state)
    else:
        logger.error(f"Unsupported graph_state type: {type(graph_state)}")
        raise HTTPException(status_code=500, detail="Unsupported graph_state type")

    return SessionDataResult(
        session_id=session_data_result.session_id,
        data=session_data_result.data,
        graph_state=response_graph_state
    )