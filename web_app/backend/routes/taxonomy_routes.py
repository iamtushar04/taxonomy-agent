import uuid
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
# pyrefly: ignore [missing-import]
from fastapi.responses import FileResponse
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

# pyrefly: ignore [missing-import]
import models
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from schemas import PatentRequest, GraphPayload, RenameRunRequest
# pyrefly: ignore [missing-import]
from services.taxonomy_service import run_taxonomy_pipeline, process_excel_generation
# pyrefly: ignore [missing-import]
from services import db_service
# pyrefly: ignore [missing-import]
from core.security import get_current_user

router = APIRouter(tags=["Taxonomy API"])

@router.post("/api/build-taxonomy")
async def build_taxonomy(request: PatentRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user)):
    if not request.patent_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one patent ID.")
    # Ensure the 8-character ID is perfectly unique in the database
    while True:
        run_id = str(uuid.uuid4())[:8]
        if db_service.is_run_id_unique(db, run_id):
            break
    
    db_service.create_new_run(db, run_id, request.patent_ids, current_user_id)
    
    background_tasks.add_task(run_taxonomy_pipeline, run_id, request.patent_ids)
    return {"run_id": run_id, "message": "Started"}

@router.get("/api/status/{run_id}")
async def get_status(run_id: str, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user)):
    # Optimized: Only fetch exactly the columns we need to save bandwidth
    run_record = db_service.get_run_status(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Not found.")
        
    resp = {"run_id": run_id, "status": run_record.status}
    if run_record.status == "failed":
        resp["error"] = run_record.error_message
    return resp

@router.get("/api/taxonomy/{run_id}")
async def get_taxonomy(run_id: str, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user)):
    # Optimized: Only fetch exactly what we need to avoid pulling massive unused data
    run_record = db_service.get_run_taxonomy(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Not found.")
        
    if run_record.status != "completed":
        raise HTTPException(status_code=400, detail="Not ready.")
    return {"run_id": run_id, "name": run_record.name, "taxonomy": run_record.final_taxonomy or []}

@router.post("/api/download-excel/{run_id}")
async def download_excel(run_id: str, payload: GraphPayload, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user)):
    # Optimized: Only fetch exactly what is needed (avoids pulling the massive final_taxonomy column)
    run_record = db_service.get_run_for_excel(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Run ID not found.")
        
    matrix_path = process_excel_generation(run_id, payload, run_record)
        
    return FileResponse(
        path=matrix_path, 
        filename=f"{run_record.name.replace(' ', '_')}.xlsx" if run_record.name else f"Taxonomy_Matrix_{run_id}.xlsx",
        headers={"Access-Control-Expose-Headers": "Content-Disposition"}, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.put("/api/runs/{run_id}/name")
async def rename_run(run_id: str, req: RenameRunRequest, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user)):
    """Allows a user to rename their taxonomy session."""
    run = db.query(models.Run).filter(models.Run.id == run_id, models.Run.user_id == current_user_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.name = req.name
    db.commit()
    return {"status": "success", "name": run.name}

@router.get("/api/runs")
async def get_user_runs(db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user)):
    """Fetch lightweight history of all runs for the current user."""
    runs = db_service.get_runs_by_user(db, current_user_id)
    return {"runs": runs}
