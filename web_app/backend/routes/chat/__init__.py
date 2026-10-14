# pyrefly: ignore [missing-import]
from fastapi import APIRouter

from .analyze_product import router as analyze_product_router
from .pre_run_message import router as pre_run_message_router
from .get_history import router as get_history_router
from .send_message import router as send_message_router

router = APIRouter(prefix="/api/chat", tags=["chatbot"])

router.include_router(analyze_product_router)
router.include_router(pre_run_message_router)
router.include_router(get_history_router)
router.include_router(send_message_router)
