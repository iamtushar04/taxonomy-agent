from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import GraphPayload
from services.taxonomy_service import process_excel_generation, build_excel_preview_data
from services import db_service
from core.security import get_current_user

router = APIRouter()

@router.post("/api/preview-excel/{run_id}")
async def preview_excel(
    run_id: str,
    payload: GraphPayload,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """Generates preview data for the Excel matrix to display inline in the web application."""
    run_record = db_service.get_run_for_excel(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Run ID not found.")
        
    matrix_path = process_excel_generation(run_id, payload, run_record)
    preview_data = build_excel_preview_data(matrix_path)
    preview_data["filename"] = f"{run_record.name.replace(' ', '_')}.xlsx" if run_record.name else f"Taxonomy_Matrix_{run_id}.xlsx"
    return preview_data
