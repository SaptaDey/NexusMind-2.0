from fastapi import APIRouter, Depends, HTTPException, status
from src.asr_got_reimagined.services.session_service import SessionService
from src.asr_got_reimagined.api.schemas import SessionDataSchema, GraphStateSchema

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/session/{session_id}/data", response_model=SessionDataSchema)
async def get_session_data(session_id: str, service: SessionService = Depends()):
    """
    Retrieve session data including graph state.
    """
    session_data_result = service.get_session_data(session_id)
    if session_data_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )
    graph_state = session_data_result.graph_state

    if isinstance(graph_state, GraphStateSchema):
        response_graph_state = graph_state
    elif isinstance(graph_state, dict):
        response_graph_state = GraphStateSchema(**graph_state)
    else:
        # Attempt to extract a serializable dict from graph_state object
        if hasattr(graph_state, "dict") and callable(graph_state.dict):
            graph_state_dict = graph_state.dict()
            response_graph_state = GraphStateSchema(**graph_state_dict)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid graph_state format"
            )

    return SessionDataSchema(
        session_id=session_data_result.session_id,
        user_data=session_data_result.user_data,
        graph_state=response_graph_state
    )