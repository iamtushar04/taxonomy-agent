# pyrefly: ignore [missing-import]
from fastapi import APIRouter
from .delete_session import router as delete_session_router

router = APIRouter(prefix="/api", tags=["delete"])

router.include_router(delete_session_router)
