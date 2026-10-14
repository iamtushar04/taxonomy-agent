from typing import List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, Depends

# pyrefly: ignore [missing-import]
from core.security import get_current_user
# pyrefly: ignore [missing-import]
from product_schemas import ParsedProduct
from .cache import _UPLOAD_CACHE

router = APIRouter()

@router.get("/session/{session_upload_id}", response_model=List[ParsedProduct])
async def get_session_products(
    session_upload_id: str,
    current_user_id: int = Depends(get_current_user)
):
    """Retrieve already parsed products for a session upload ID."""
    if session_upload_id not in _UPLOAD_CACHE:
        raise HTTPException(status_code=404, detail="Upload session expired or not found.")
    return _UPLOAD_CACHE[session_upload_id]
