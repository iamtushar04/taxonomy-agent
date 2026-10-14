from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from core.security import get_current_user
import models

router = APIRouter()

@router.get("/{run_id}/history")
def get_chat_history(
    run_id: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Load chat history, mental model, and mapping rules tied to a specific run.
    """
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.user_id is not None and run.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this run")

    session = db.query(models.ChatSession).filter(
        models.ChatSession.run_id == run_id
    ).first()

    greeting = (
        "👋 Hi! I'm your Taxonomy Assistant for this run.\n\n"
        "Here's what you can ask me:\n"
        "- **\"Why is patent X in this category?\"** → I'll explain based on patent claims and context\n"
        "- **\"Map X under Y\"** → Define custom taxonomy hierarchy placement rules\n"
        "- **\"What are the key technical concepts?\"** → Discuss findings and product alignment\n"
        "- **\"Re-build taxonomy\"** → Trigger a new build with your preferred focus"
    )

    if not session:
        return {
            "run_id": run_id,
            "messages": [],
            "mental_model": None,
            "mental_model_confirmed": False,
            "mapping_rules": [],
            "greeting": greeting,
            "has_taxonomy": run.final_taxonomy is not None,
        }

    return {
        "run_id": run_id,
        "messages": session.messages or [],
        "mental_model": session.mental_model,
        "mental_model_confirmed": session.mental_model_confirmed,
        "mapping_rules": session.mapping_rules or [],
        "greeting": greeting,
        "has_taxonomy": run.final_taxonomy is not None,
        "created_at": session.created_at,
    }
