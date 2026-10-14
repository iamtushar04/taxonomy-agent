from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from services import db_service
from core.security import get_current_user

router = APIRouter()

@router.get("/api/runs")
async def get_user_runs(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """Fetch lightweight history of all runs for the current user."""
    runs = db_service.get_runs_by_user(db, current_user_id)
    return {"runs": runs}
