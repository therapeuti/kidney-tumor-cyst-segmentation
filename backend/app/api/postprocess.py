from fastapi import APIRouter, HTTPException

from backend.app.schemas.postprocess import (
    PostprocessApplyResponse,
    PostprocessFunctionDefinition,
    PostprocessPreviewResponse,
    PostprocessRequest,
)
from backend.app.services.postprocess_service import postprocess_service
from backend.app.services.session_service import session_service


router = APIRouter()


@router.get("/postprocess/functions", response_model=list[PostprocessFunctionDefinition])
def get_postprocess_functions() -> list[PostprocessFunctionDefinition]:
    return postprocess_service.list_functions()


@router.post("/sessions/{session_id}/postprocess/preview", response_model=PostprocessPreviewResponse)
def preview_postprocess(session_id: str, payload: PostprocessRequest) -> PostprocessPreviewResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return postprocess_service.preview(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/postprocess/apply", response_model=PostprocessApplyResponse)
def apply_postprocess(session_id: str, payload: PostprocessRequest) -> PostprocessApplyResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return postprocess_service.apply(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
