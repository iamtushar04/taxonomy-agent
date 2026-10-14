from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from services import db_service
from core.security import get_current_user

router = APIRouter()

@router.get("/api/analytics/{run_id}")
async def get_analytics(
    run_id: str,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """
    Returns patent-level metadata (assignee, filing_date, title) for analytics charts.
    Only works for patent runs (not PubMed). Returns 400 for PubMed sessions.
    """
    run_record = db_service.get_run_source_data(db, run_id, current_user_id)
    if not run_record:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run_record.status != "completed":
        raise HTTPException(status_code=400, detail="Run not completed yet.")
    if run_record.is_pubmed:
        raise HTTPException(status_code=400, detail="Analytics not available for PubMed runs.")

    source_data = run_record.source_data or {}
    products_dict = source_data.get("_products", {})

    # Serialize only the fields needed for charts — safe even if keys are missing
    analytics_patents = []
    for patent_id, meta in source_data.items():
        if patent_id == "_products":
            continue
        analytics_patents.append({
            "patent_id": patent_id,
            "title": meta.get("title", "N/A"),
            "assignee": meta.get("assignee") or "Unknown",
            "filing_date": meta.get("filing_date") or meta.get("date") or None,
            "summary": meta.get("summary") or "",
            "full_text": (meta.get("full_text") or ""),
        })

    # Serialize products list
    analytics_products = []
    for prod_id, pmeta in products_dict.items():
        analytics_products.append({
            "product_id": prod_id,
            "product_name": pmeta.get("product_name", "Unknown Product"),
            "brand_or_assignee": pmeta.get("brand_or_assignee", "Unknown"),
            "category": pmeta.get("category", "Uncategorized"),
            "features": pmeta.get("features", []),
            "source_filename": pmeta.get("source_filename", ""),
            "full_text_snippet": pmeta.get("full_text_snippet", "")
        })

    return {
        "run_id": run_id,
        "patents": analytics_patents,
        "products": analytics_products
    }
