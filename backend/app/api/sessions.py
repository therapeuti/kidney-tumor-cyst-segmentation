from fastapi import APIRouter, HTTPException, Query, Response

from backend.app.schemas.session import (
    SaveSessionResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionStatusResponse,
)
from backend.app.schemas.edit import (
    BrushEditRequest,
    EditResponse,
    FloodFillRequest,
    MagicWandApplyRequest,
    MagicWandPreviewRequest,
    MagicWandPreviewResponse,
    PolygonEditRequest,
    RelabelRequest,
    SliceInterpolateRequest,
)
from backend.app.schemas.viewer import SessionMetaResponse, SliceResponse
from backend.app.services.edit_service import edit_service
from backend.app.services.session_service import session_service
from backend.app.services.viewer_service import viewer_service


router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: SessionCreateRequest) -> SessionResponse:
    try:
        return session_service.create_session(payload.caseId, payload.phase)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
def get_session(session_id: str) -> SessionStatusResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session_service.session_status(session)


@router.post("/sessions/{session_id}/save", response_model=SaveSessionResponse)
def save_session(session_id: str) -> SaveSessionResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session_service.save_session(session)


@router.post("/sessions/{session_id}/undo", response_model=SessionStatusResponse)
def undo_session(session_id: str) -> SessionStatusResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return session_service.undo(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/redo", response_model=SessionStatusResponse)
def redo_session(session_id: str) -> SessionStatusResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return session_service.redo(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/meta", response_model=SessionMetaResponse)
def get_session_meta(session_id: str) -> SessionMetaResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return viewer_service.session_meta(session)


@router.get("/sessions/{session_id}/slice", response_model=SliceResponse)
def get_session_slice(
    session_id: str,
    axis: str = Query(...),
    index: int = Query(..., ge=0),
    window: float = Query(350.0, gt=0),
    level: float = Query(40.0),
) -> SliceResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return viewer_service.session_slice(session, axis=axis, index=index, window=window, level=level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/slice-image")
def get_session_slice_image(
    session_id: str,
    axis: str = Query(...),
    index: int = Query(..., ge=0),
    window: float = Query(350.0, gt=0),
    level: float = Query(40.0),
) -> Response:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        image_bytes = viewer_service.slice_image(session, axis=axis, index=index, window=window, level=level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@router.post("/sessions/{session_id}/edit/brush", response_model=EditResponse)
def edit_brush(session_id: str, payload: BrushEditRequest) -> EditResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.apply_brush(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/edit/polygon", response_model=EditResponse)
def edit_polygon(session_id: str, payload: PolygonEditRequest) -> EditResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.apply_polygon(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/edit/flood-fill", response_model=EditResponse)
def edit_flood_fill(session_id: str, payload: FloodFillRequest) -> EditResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.apply_flood_fill(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/voxel")
def get_voxel_info(
    session_id: str,
    axis: str = Query(...),
    sliceIndex: int = Query(..., ge=0),
    x: int = Query(..., ge=0),
    y: int = Query(..., ge=0),
):
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    from backend.app.core.coordinate import normalize_axis
    from backend.app.core.editing import display_to_volume, extract_slice_view
    axis_n = normalize_axis(axis)
    slice_view = extract_slice_view(session.seg_data, axis_n, sliceIndex)
    display_height = slice_view.shape[0]
    vox = display_to_volume(axis_n, x, y, sliceIndex, display_height)
    shape = session.seg_data.shape
    if not (0 <= vox[0] < shape[0] and 0 <= vox[1] < shape[1] and 0 <= vox[2] < shape[2]):
        return {"label": 0, "hu": None}
    label = int(session.seg_data[vox])
    hu = None
    if session.ct_data is not None:
        hu = round(float(session.ct_data[vox]), 1)
    else:
        from backend.app.services.viewer_service import viewer_service
        viewer_service.ensure_ct_loaded(session)
        if session.ct_data is not None:
            hu = round(float(session.ct_data[vox]), 1)
    return {"label": label, "hu": hu}


@router.post("/sessions/{session_id}/edit/magic-wand/preview", response_model=MagicWandPreviewResponse)
def edit_magic_wand_preview(session_id: str, payload: MagicWandPreviewRequest) -> MagicWandPreviewResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.preview_magic_wand(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/edit/magic-wand/mask")
def edit_magic_wand_mask(
    session_id: str,
    axis: str = Query(...),
    index: int = Query(..., ge=0),
) -> Response:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    from backend.app.core.coordinate import normalize_axis
    png = edit_service.get_preview_mask_slice(session, normalize_axis(axis), index)
    if png is None:
        return Response(status_code=204)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/sessions/{session_id}/edit/magic-wand/clear")
def edit_magic_wand_clear(session_id: str):
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    edit_service.clear_preview_mask(session)
    return {"ok": True}


@router.post("/sessions/{session_id}/edit/magic-wand/apply", response_model=EditResponse)
def edit_magic_wand_apply(session_id: str, payload: MagicWandApplyRequest) -> EditResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.apply_magic_wand(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/edit/relabel", response_model=EditResponse)
def edit_relabel(session_id: str, payload: RelabelRequest) -> EditResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.apply_relabel(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/edit/interpolate", response_model=EditResponse)
def edit_interpolate(session_id: str, payload: SliceInterpolateRequest) -> EditResponse:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    try:
        return edit_service.apply_interpolate(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
