import uuid
import logging
from typing import Optional
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
import models

logger = logging.getLogger(__name__)

def get_or_create_chat_session(run_id: str, user_id: int, db: Session) -> models.ChatSession:
    """Finds existing ChatSession for this run_id, or creates a new one."""
    session = db.query(models.ChatSession).filter(
        models.ChatSession.run_id == run_id
    ).first()

    if not session:
        session = models.ChatSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            run_id=run_id,
            messages=[],
            mapping_rules=[],
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    return session

def trigger_taxonomy_run(
    patent_ids: list,
    mental_model_context: str,
    user_id: int,
    db: Session,
    source_session: Optional[models.ChatSession] = None,
    run_id: Optional[str] = None
) -> Optional[str]:
    """Triggers taxonomy generation pipeline in background thread with mental model guidance.
    If run_id is provided, updates the existing run in-place without creating a new session or run."""
    try:
        import threading
        # pyrefly: ignore [missing-import]
        from services.taxonomy_service import run_taxonomy_pipeline
        # pyrefly: ignore [missing-import]
        from services import db_service

        if not patent_ids:
            logger.warning("[chat_routes] No patent IDs found to trigger run")
            return None

        if run_id:
            # IN-PLACE UPDATE: reuse existing run and existing chat session!
            active_run_id = run_id
            existing_run = db.query(models.Run).filter(models.Run.id == active_run_id).first()
            if existing_run:
                existing_run.status = "running"
                existing_run.error_message = None
                db.commit()
            logger.info(f"[chat_routes] Updating run {active_run_id} in-place from chatbot")
        else:
            # Fallback for new runs when no run_id is active
            active_run_id = str(uuid.uuid4())[:8]
            db_service.create_new_run(db, active_run_id, patent_ids, user_id)
            if source_session:
                new_chat_session = models.ChatSession(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    run_id=active_run_id,
                    product_doc_text=source_session.product_doc_text,
                    mental_model=source_session.mental_model,
                    mental_model_confirmed=True,
                    mapping_rules=list(source_session.mapping_rules or []),
                    messages=list(source_session.messages or [])
                )
                db.add(new_chat_session)
                db.commit()
            logger.info(f"[chat_routes] Created new run {active_run_id} from chatbot")

        t = threading.Thread(
            target=run_taxonomy_pipeline,
            args=(active_run_id, patent_ids, None),
            kwargs={"mental_model_context": mental_model_context},
            daemon=True
        )
        t.start()

        return active_run_id

    except Exception as e:
        logger.error(f"[chat_routes] Failed to trigger run: {e}")
        return None

