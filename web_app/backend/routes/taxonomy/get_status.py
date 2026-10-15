from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from services import db_service
from services.run_stage_service import get_run_stage
from core.security import get_current_user

router = APIRouter()

@router.get("/api/status/{run_id}")
async def get_status(
    run_id: str,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """Fetches the processing status of a taxonomy run, including active pipeline verification stage."""
    run_record = db_service.get_run_status(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Not found.")
        
    resp = {"run_id": run_id, "status": run_record.status}
    if run_record.status == "failed":
        resp["error"] = run_record.error_message
    elif run_record.status == "running" or run_record.status == "pending":
        stage_info = get_run_stage(run_id)
        resp["stage"] = stage_info.get("stage")
        resp["stage_title"] = stage_info.get("title")
        resp["stage_description"] = stage_info.get("description")
        resp["step"] = stage_info.get("step", 1)
        resp["total_steps"] = stage_info.get("total_steps", 5)

    return resp
