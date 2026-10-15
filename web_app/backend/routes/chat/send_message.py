import datetime
import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from core.security import get_current_user
# pyrefly: ignore [missing-import]
import models
from chatbot_agent.state import ChatAgentState, ChatMessage, ProductUnderstanding, MappingRule
from chatbot_agent.graph import get_chatbot_graph
from .helpers import get_or_create_chat_session, trigger_taxonomy_run

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/{run_id}/message")
def send_chat_message(
    run_id: str,
    body: dict,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message for a taxonomy run.
    The chatbot LangGraph automatically routes based on user intent:
    - Explanations & Q&A over the taxonomy (RAG on final_taxonomy & source_data)
    - Custom mapping rules ("Map X under Y")
    - Product understanding & domain focus
    - Triggering a new/updated taxonomy run
    """
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.user_id is not None and run.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this run")

    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session = get_or_create_chat_session(run_id, user_id, db)

    # Auto-extract product text from run.source_data if products were uploaded with the run
    if not session.product_doc_text and run.source_data and isinstance(run.source_data, dict):
        products_dict = run.source_data.get("_products", {})
        if products_dict:
            lines = []
            for p in products_dict.values():
                lines.append(f"Product: {p.get('product_name', 'Product')}")
                if p.get("features"):
                    lines.append("Features: " + ", ".join(p["features"]))
                if p.get("target_market"):
                    lines.append(f"Target Market: {p['target_market']}")
            if lines:
                session.product_doc_text = "\n".join(lines)

    # Parse mental model and mapping rules
    mental_model = None
    if session.mental_model:
        try:
            mental_model = ProductUnderstanding(**session.mental_model)
        except Exception:
            pass

    mapping_rules = []
    for r in (session.mapping_rules or []):
        try:
            mapping_rules.append(MappingRule(**r))
        except Exception:
            pass

    # Build agent state directly with this run's data
    state = ChatAgentState(
        session_id=session.id,
        run_id=run_id,
        user_message=user_message,
        messages=[ChatMessage(**m) for m in (session.messages or [])],
        product_doc_text=session.product_doc_text,
        mental_model=mental_model,
        mental_model_confirmed=session.mental_model_confirmed or False,
        mapping_rules=mapping_rules,
        final_taxonomy=run.final_taxonomy,
        source_data=run.source_data,
    )

    user_msg_record = {
        "role": "user",
        "content": user_message,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    # Execute chatbot graph
    try:
        graph = get_chatbot_graph(force_rebuild=True)
        result_state = graph.invoke(state)

        response_text = result_state.get("response_text", "")
        response_metadata = result_state.get("response_metadata", {})
        detected_intent = result_state.get("detected_intent")
        updated_rules = result_state.get("mapping_rules", mapping_rules)
        updated_mental_model = result_state.get("mental_model", mental_model)
    except Exception as e:
        logger.exception(f"Chatbot execution error for run {run_id}: {e}")
        response_text = f"I'm here to help, but encountered an error processing your query: {str(e)}. Please try rephrasing or asking about a specific node."
        response_metadata = {"error": str(e)}
        detected_intent = None
        updated_rules = mapping_rules
        updated_mental_model = mental_model

    assistant_msg_record = {
        "role": "assistant",
        "content": response_text,
        "intent": detected_intent.value if detected_intent else None,
        "metadata": response_metadata,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    # Update session in DB
    messages = list(session.messages or [])
    messages.append(user_msg_record)
    messages.append(assistant_msg_record)
    session.messages = messages

    if updated_rules:
        session.mapping_rules = [r.model_dump() if hasattr(r, "model_dump") else r for r in updated_rules]

    if updated_mental_model:
        session.mental_model = updated_mental_model.model_dump() if hasattr(updated_mental_model, "model_dump") else updated_mental_model

    if response_metadata.get("trigger_run"):
        session.mental_model_confirmed = True

    db.commit()

    # Trigger taxonomy run if agent determined "build_taxonomy" intent
    triggered_run_id = None
    if response_metadata.get("trigger_run"):
        triggered_run_id = trigger_taxonomy_run(
            patent_ids=run.input_ids or [],
            mental_model_context=response_metadata.get("mental_model_context", ""),
            user_id=user_id,
            db=db,
            source_session=session,
            run_id=run_id
        )

    return {
        "response": response_text,
        "intent": detected_intent.value if detected_intent else "general_question",
        "metadata": response_metadata,
        "mental_model": session.mental_model,
        "mental_model_confirmed": session.mental_model_confirmed,
        "mapping_rules": session.mapping_rules or [],
        "triggered_run_id": triggered_run_id,
    }
