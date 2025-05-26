from fastapi import APIRouter, HTTPException, Depends

from src.asr_got_reimagined.api.schemas.mcp import (
    SessionDataResultSchema,
    GraphStateSchema,
    UpdateSessionRequestSchema,
)
from src.asr_got_reimagined.services.mcp_service import MCPService
from src.asr_got_reimagined.domain.models.session_data_result import SessionDataResult

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDataResultSchema,
    summary="Retrieve session data by ID",
)
    session_data_result: SessionDataResult = await MCPService.get_session_data(session_id)
    graph_state_data = session_data_result.graph_state

    # Always deserialize graph state from a dict
    if not isinstance(graph_state_data, dict):
        raise HTTPException(status_code=500, detail="Invalid graph state format")

    response_graph_state = GraphStateSchema(**graph_state_data)
    return SessionDataResultSchema(
        session_id=session_data_result.session_id,
        graph_state=response_graph_state,
        created_at=session_data_result.created_at,
        updated_at=session_data_result.updated_at,
    )


@router.post(
    "/sessions/{session_id}",
    response_model=SessionDataResultSchema,
    summary="Update session data",
)
async def update_session(
    session_id: str,
    update_request: UpdateSessionRequestSchema,
) -> SessionDataResultSchema:
    session_data_result: SessionDataResult = await MCPService.update_session_data(
        session_id, update_request
    )
    graph_state_data = session_data_result.graph_state

    # Always deserialize graph state from a dict
    if not isinstance(graph_state_data, dict):
        raise HTTPException(status_code=500, detail="Invalid graph state format")

    response_graph_state = GraphStateSchema(**graph_state_data)
    return SessionDataResultSchema(
        session_id=session_data_result.session_id,
        graph_state=response_graph_state,
        created_at=session_data_result.created_at,
        updated_at=session_data_result.updated_at,
    )