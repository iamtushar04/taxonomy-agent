from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from schemas import RenameRunRequest
from core.security import get_current_user

router = APIRouter()

@router.put("/api/runs/{run_id}/name")
async def rename_run(
    run_id: str,
    req: RenameRunRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """Allows a user to rename their taxonomy session."""
    run = db.query(models.Run).filter(models.Run.id == run_id, models.Run.user_id == current_user_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.name = req.name
    db.commit()
    return {"status": "success", "name": run.name}
