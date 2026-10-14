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
    db: Session
) -> Optional[str]:
    """Triggers taxonomy generation pipeline in background thread with mental model guidance."""
    try:
        import threading
        # pyrefly: ignore [missing-import]
        from services.taxonomy_service import run_taxonomy_pipeline
        # pyrefly: ignore [missing-import]
        from services import db_service

        if not patent_ids:
            logger.warning("[chat_routes] No patent IDs found to trigger run")
            return None

        new_run_id = str(uuid.uuid4())[:8]
        db_service.create_new_run(db, new_run_id, patent_ids, user_id)

        t = threading.Thread(
            target=run_taxonomy_pipeline,
            args=(new_run_id, patent_ids, None),
            kwargs={"mental_model_context": mental_model_context},
            daemon=True
        )
        t.start()

        logger.info(f"[chat_routes] Successfully triggered run {new_run_id} from chatbot")
        return new_run_id

    except Exception as e:
        logger.error(f"[chat_routes] Failed to trigger run: {e}")
        return None
