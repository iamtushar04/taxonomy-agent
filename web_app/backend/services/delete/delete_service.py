import os
import glob
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import SessionLocal
from services.db.delete.delete_session_db import get_session_for_deletion, delete_session_records

def validate_session_deletion(db: Session, session_id: str, user_id: int) -> dict:
    """
    Validates that a session exists and that the current user has permission to delete it.
    Raises HTTPException (404/403) on violation.
    """
    meta = get_session_for_deletion(db, session_id, user_id)
    if not meta["exists"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    if not meta["is_authorized"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to delete session '{session_id}'."
        )

    return meta


def perform_async_delete(session_id: str, user_id: int) -> None:
    """
    Background worker task triggered for HTTP 202 Accepted deletion workflow.
    Executes database deletions and purges any file artifacts associated with this session.
    """
    print(f"[delete_service] Starting background deletion for session {session_id} (user_id={user_id})...")
    
    # 1. Database record cleanup
    db: Session = SessionLocal()
    try:
        delete_session_records(db, session_id, user_id)
    except Exception as e:
        print(f"[delete_service] Background DB deletion failed for {session_id}: {e}")
    finally:
        db.close()

    # 2. File system artifact cleanup
    try:
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        project_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))
        
        # Search patterns for temporary excel files or traces
        patterns_to_check = [
            os.path.join(project_root, "data", f"taxonomy_matrix_{session_id}.xlsx"),
            os.path.join(backend_dir, "data", f"taxonomy_matrix_{session_id}.xlsx"),
            os.path.join(project_root, "traces", f"trace_{session_id}.json"),
        ]

        for file_path in patterns_to_check:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"[delete_service] Removed disk artifact: {file_path}")
                except Exception as file_err:
                    print(f"[delete_service] Warning: failed to delete file {file_path}: {file_err}")
    except Exception as fs_err:
        print(f"[delete_service] File cleanup warning for {session_id}: {fs_err}")

    print(f"[delete_service] Background deletion completed for session {session_id}.")
