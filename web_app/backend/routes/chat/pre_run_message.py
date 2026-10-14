import re
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from core.security import get_current_user
from pipeline.utils.llm_client import chat_completion

router = APIRouter()

@router.post("/pre-run/message")
def pre_run_chat_message(
    body: dict,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Conversational instruction endpoint before a taxonomy run is built.
    Allows user to give instructions, guide the mental model, and provide patent IDs.
    """
    user_message = body.get("message", "").strip()
    session_upload_id = body.get("session_upload_id")
    mental_model_data = body.get("mental_model")
    incoming_patents = body.get("patent_ids", []) or []
    history = body.get("history", [])

    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Detect patent or pubmed IDs from user message
    patent_matches = re.findall(r'\b(?:US|EP|WO|JP|CN|KR)?\d{6,12}[A-Z0-9]*\b', user_message, re.IGNORECASE)
    cleaned_patents = [p.upper() for p in patent_matches if any(c.isdigit() for c in p)]
    cleaned_patents = list(dict.fromkeys(cleaned_patents))

    all_patents = list(dict.fromkeys(cleaned_patents + incoming_patents))

    lower_msg = user_message.lower().strip()
    start_phrases = [
        "start", "then start", "go ahead", "proceed", "build", 
        "run", "generate", "create taxonomy", "do it", "let's do it", 
        "lets do it", "yes start", "okay start", "begin", "launch"
    ]
    wants_to_start = any(p in lower_msg for p in start_phrases)
    trigger_build = wants_to_start and len(all_patents) > 0

    system_prompt = (
        "You are an expert taxonomy AI assistant guiding the user before generating a patent taxonomy.\n"
        "The user is uploading product documents, giving guidelines on what to focus on or avoid, "
        "or providing patent/PubMed IDs.\n"
        "If the user confirms to start or proceed, affirm that you are launching the pipeline now.\n"
        "Respond conversationally, affirming how their guidelines will shape the taxonomy hierarchy, "
        "which technical concepts will be prioritized or avoided, and whether patent IDs were detected.\n"
        "Keep your tone professional, concise, and helpful."
    )

    if trigger_build:
        reply = f"🚀 Understood! Launching the taxonomy build now for {len(all_patents)} patent(s), prioritizing your specified guidelines and product focus."
    else:
        context_str = ""
        if mental_model_data:
            context_str += f"\nCurrent Product Mental Model: {mental_model_data.get('product_name')} | Focus: {mental_model_data.get('focus_areas')} | Avoid: {mental_model_data.get('avoid_areas')}"
        if all_patents:
            context_str += f"\nKnown Patent IDs ({len(all_patents)}): {', '.join(all_patents[:8])}"

        prompt = f"User instruction: {user_message}{context_str}"

        llm_messages = [{"role": "system", "content": system_prompt}]
        for h in history[-4:]:
            if h.get("role") in ("user", "assistant"):
                llm_messages.append({"role": h["role"], "content": h.get("content", "")})
        llm_messages.append({"role": "user", "content": prompt})

        try:
            reply = chat_completion(llm_messages, model="gpt-4o-mini", temperature=0.3).strip()
        except Exception:
            reply = f"Understood. I've noted your guidance: '{user_message}' and will apply it when structuring the taxonomy."

    updated_mental_model = dict(mental_model_data) if mental_model_data else {}
    if mental_model_data:
        if "focus on" in lower_msg or "prioritize" in lower_msg:
            cur_focus = list(updated_mental_model.get("focus_areas", []))
            cur_focus.append(user_message[:100])
            updated_mental_model["focus_areas"] = cur_focus
        if "avoid" in lower_msg or "ignore" in lower_msg or "exclude" in lower_msg:
            cur_avoid = list(updated_mental_model.get("avoid_areas", []))
            cur_avoid.append(user_message[:100])
            updated_mental_model["avoid_areas"] = cur_avoid

    ready_to_build = len(all_patents) > 0

    return {
        "response": reply,
        "mental_model": updated_mental_model if updated_mental_model else None,
        "detected_patent_ids": all_patents,
        "ready_to_build": ready_to_build,
        "trigger_build": trigger_build
    }
