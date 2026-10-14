# pyrefly: ignore [missing-import]
from fastapi import APIRouter

from .cache import _UPLOAD_CACHE
from .upload_products import router as upload_router
from .ingest_urls import router as urls_router
from .get_session_products import router as session_router

router = APIRouter(prefix="/api/products", tags=["Product Ingestion"])

router.include_router(upload_router)
router.include_router(urls_router)
router.include_router(session_router)

__all__ = ["router", "_UPLOAD_CACHE"]
