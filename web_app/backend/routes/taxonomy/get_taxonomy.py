from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from services import db_service
from core.security import get_current_user

router = APIRouter()

@router.get("/api/taxonomy/{run_id}")
async def get_taxonomy(
    run_id: str,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """Fetches the completed taxonomy graph, node metadata, and associated products/patents."""
    run_record = db_service.get_run_taxonomy(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Not found.")
        
    if run_record.status != "completed":
        raise HTTPException(status_code=400, detail="Not ready.")

    source_data = run_record.source_data or {}
    products_map = source_data.get("_products", {})
    
    # Lightweight patent metadata map (id -> title, assignee, filing_date)
    patents_meta = {}
    for pid, pdata in source_data.items():
        if pid != "_products":
            patents_meta[pid] = {
                "title": pdata.get("title", ""),
                "assignee": pdata.get("assignee", ""),
                "filing_date": pdata.get("filing_date", ""),
                "summary": pdata.get("summary", "")
            }

    return {
        "run_id": run_id, 
        "name": run_record.name, 
        "taxonomy": run_record.final_taxonomy or [],
        "products_map": products_map,
        "patents_meta": patents_meta
    }
