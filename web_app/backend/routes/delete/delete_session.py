from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
from core.security import get_current_user
from schemas import DeleteSessionResponse
from services.delete import validate_session_deletion, perform_async_delete

router = APIRouter()


@router.delete(
    "/delete/sessions/{session_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeleteSessionResponse,
    summary="Delete a taxonomy/chat session asynchronously (HTTP 202)"
)
@router.delete(
    "/delete/runs/{session_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeleteSessionResponse,
    summary="Delete a taxonomy run session asynchronously (HTTP 202)"
)
@router.delete(
    "/runs/{session_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeleteSessionResponse,
    summary="Delete a run by ID asynchronously (HTTP 202)"
)
@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeleteSessionResponse,
    summary="Delete a session by ID asynchronously (HTTP 202)"
)
async def delete_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user)
):
    """
    Asynchronous 202 Accepted session deletion endpoint.
    
    1. Validates session existence and user authorization.
    2. Registers asynchronous cleanup in BackgroundTasks.
    3. Immediately returns HTTP 202 Accepted to the client.
    """
    # Validate existence & permissions immediately before accepting
    validate_session_deletion(db, session_id, current_user_id)

    # Dispatch deletion asynchronously via 202 technique
    background_tasks.add_task(perform_async_delete, session_id, current_user_id)

    return DeleteSessionResponse(
        status="accepted",
        message="Session deletion request accepted and processing in background.",
        session_id=session_id
    )
