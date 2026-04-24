from fastapi import APIRouter

from backend.app.api import cases, postprocess, sessions


router = APIRouter()
router.include_router(cases.router, tags=["cases"])
router.include_router(sessions.router, tags=["sessions"])
router.include_router(postprocess.router, tags=["postprocess"])
