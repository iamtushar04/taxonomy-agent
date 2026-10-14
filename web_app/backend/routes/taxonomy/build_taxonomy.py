import uuid
import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from schemas import PatentRequest
from services.taxonomy_service import run_taxonomy_pipeline
from services import db_service
from core.security import get_current_user

router = APIRouter()

@router.post("/api/build-taxonomy")
async def build_taxonomy(
    request: PatentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """Initiates a background pipeline run to generate a patent taxonomy."""
    if not request.patent_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one patent ID.")
    
    # Ensure the 8-character ID is perfectly unique in the database
    while True:
        run_id = str(uuid.uuid4())[:8]
        if db_service.is_run_id_unique(db, run_id):
            break
    
    db_service.create_new_run(db, run_id, request.patent_ids, current_user_id)
    
    # Persist chat session with initial messages & mental model immediately so history is preserved
    chat_messages = []
    if request.messages:
        for m in request.messages:
            chat_messages.append({
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
                "intent": m.get("intent"),
                "metadata": m.get("metadata", {}),
                "timestamp": m.get("timestamp") or datetime.datetime.utcnow().isoformat()
            })
    else:
        chat_messages = [{
            "role": "user",
            "content": f"Build taxonomy for {len(request.patent_ids)} items: {', '.join(request.patent_ids[:5])}",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }]

    chat_sess = models.ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user_id,
        run_id=run_id,
        messages=chat_messages,
        mental_model=request.mental_model,
        mental_model_confirmed=bool(request.mental_model),
        mapping_rules=[]
    )
    db.add(chat_sess)
    db.commit()

    instructions = request.mental_model_context or request.instructions
    session_upload_id = request.session_upload_id

    # Fallback auto-ingest: If links provided directly without prior extraction
    if not session_upload_id and request.product_urls:
        from services.product_service import ProductDocumentService
        from routes.products.cache import _UPLOAD_CACHE
        extracted_products, _ = ProductDocumentService.parse_from_urls(request.product_urls)
        if extracted_products:
            session_upload_id = f"upl_{uuid.uuid4().hex[:12]}"
            _UPLOAD_CACHE[session_upload_id] = extracted_products

    background_tasks.add_task(
        run_taxonomy_pipeline,
        run_id,
        request.patent_ids,
        session_upload_id,
        instructions
    )
    return {"run_id": run_id, "message": "Started", "status": "running"}

