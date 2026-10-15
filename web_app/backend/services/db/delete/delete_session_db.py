# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
import models

def get_session_for_deletion(db: Session, session_id: str, user_id: int):
    """
    Checks if a Run or ChatSession exists with the given ID and belongs to the user.
    Returns a dict with existence and authorization metadata.
    """
    # 1. Check in Run table
    run = db.query(models.Run).filter(models.Run.id == session_id).first()
    if run:
        is_owner = (run.user_id is None) or (run.user_id == user_id)
        return {
            "exists": True,
            "type": "run",
            "is_authorized": is_owner,
            "run": run
        }

    # 2. Check in ChatSession table (if standalone chat session)
    chat_session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if chat_session:
        is_owner = (chat_session.user_id is None) or (chat_session.user_id == user_id)
        return {
            "exists": True,
            "type": "chat_session",
            "is_authorized": is_owner,
            "chat_session": chat_session
        }

    return {
        "exists": False,
        "type": None,
        "is_authorized": False
    }


def delete_session_records(db: Session, session_id: str, user_id: int) -> dict:
    """
    Executes database-level deletion for a session.
    Removes associated ChatSession records and the Run record.
    Returns summary statistics of deleted records.
    """
    deleted_chat_sessions = 0
    deleted_runs = 0

    try:
        # Delete associated ChatSessions (matched by run_id or session id)
        deleted_chat_sessions = db.query(models.ChatSession).filter(
            (models.ChatSession.run_id == session_id) | (models.ChatSession.id == session_id)
        ).delete(synchronize_session=False)

        # Delete from Run table
        deleted_runs = db.query(models.Run).filter(
            models.Run.id == session_id
        ).delete(synchronize_session=False)

        db.commit()
        print(f"[delete_session_db] Successfully deleted session {session_id}: {deleted_runs} run(s), {deleted_chat_sessions} chat session(s).")
    except Exception as e:
        db.rollback()
        print(f"[delete_session_db] Error during DB delete for session {session_id}: {e}")
        raise e

    return {
        "session_id": session_id,
        "deleted_runs": deleted_runs,
        "deleted_chat_sessions": deleted_chat_sessions
    }
