import uuid
from fastapi import APIRouter, HTTPException, Depends

from core.security import get_current_user
from product_schemas import ProductUploadResponse, ProductUrlRequest
from services.product_service import ProductDocumentService
from .cache import _UPLOAD_CACHE

router = APIRouter()

@router.post("/urls", response_model=ProductUploadResponse)
async def ingest_product_urls(
    payload: ProductUrlRequest,
    current_user_id: int = Depends(get_current_user)
):
    """
    Accepts one or multiple product URLs (direct PDF links or web specifications),
    downloads and parses them modularly via ProductDocumentService, and returns extracted products.
    """
    if not payload.urls:
        raise HTTPException(status_code=400, detail="No URLs provided.")

    session_upload_id = f"upl_{uuid.uuid4().hex[:12]}"
    extracted_products, errors = ProductDocumentService.parse_from_urls(payload.urls)

    if not extracted_products and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    _UPLOAD_CACHE[session_upload_id] = extracted_products

    return ProductUploadResponse(
        session_upload_id=session_upload_id,
        total_files_parsed=len(payload.urls),
        total_products_extracted=len(extracted_products),
        products=extracted_products,
        errors=errors
    )
