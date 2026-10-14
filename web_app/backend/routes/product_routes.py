import uuid
from typing import List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
# pyrefly: ignore [missing-import]
from core.security import get_current_user
# pyrefly: ignore [missing-import]
from product_schemas import ProductUploadResponse, ParsedProduct
# pyrefly: ignore [missing-import]
from services.product_service import ProductDocumentService

router = APIRouter(prefix="/api/products", tags=["Product Ingestion"])

# Temporary in-memory cache for uploaded products keyed by session_upload_id
# (Keeps files lightweight and avoids dirtying the DB until a run is created)
_UPLOAD_CACHE = {}

@router.post("/upload", response_model=ProductUploadResponse)
async def upload_product_documents(
    files: List[UploadFile] = File(...),
    current_user_id: int = Depends(get_current_user)
):
    """
    Accepts one or multiple product documents (.pdf, .docx, .xlsx, .csv, .txt),
    parses them modularly via ProductDocumentService, and returns extracted products.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    session_upload_id = f"upl_{uuid.uuid4().hex[:12]}"
    extracted_products = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            if len(content) == 0:
                errors.append(f"Skipping empty file: {file.filename}")
                continue

            products, err = ProductDocumentService.parse_document(file.filename, content)
            if err:
                errors.append(err)
            if products:
                extracted_products.extend(products)
        except Exception as e:
            errors.append(f"Failed to process {file.filename}: {str(e)}")

    if not extracted_products and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Cache products for subsequent pipeline assignment
    _UPLOAD_CACHE[session_upload_id] = extracted_products

    return ProductUploadResponse(
        session_upload_id=session_upload_id,
        total_files_parsed=len(files),
        total_products_extracted=len(extracted_products),
        products=extracted_products,
        errors=errors
    )

@router.get("/session/{session_upload_id}", response_model=List[ParsedProduct])
async def get_session_products(
    session_upload_id: str,
    current_user_id: int = Depends(get_current_user)
):
    """Retrieve already parsed products for a session upload ID."""
    if session_upload_id not in _UPLOAD_CACHE:
        raise HTTPException(status_code=404, detail="Upload session expired or not found.")
    return _UPLOAD_CACHE[session_upload_id]
