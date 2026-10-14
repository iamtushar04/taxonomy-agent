# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from core.security import get_current_user
from chatbot_agent.state import ProductUnderstanding
# pyrefly: ignore [missing-import]
from routes.products.cache import _UPLOAD_CACHE

router = APIRouter()

@router.post("/pre-run/analyze-product")
def analyze_product_pre_run(
    body: dict,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyzes uploaded product documents for conversational guidance on the main UI.
    Extracts structured ProductUnderstanding and returns a friendly AI summary card.
    """
    session_upload_id = body.get("session_upload_id")
    custom_instruction = body.get("instructions", "").strip()

    products = _UPLOAD_CACHE.get(session_upload_id, [])
    if not products:
        raise HTTPException(status_code=404, detail="No uploaded products found for this session.")

    text_parts = []
    for p in products:
        p_dict = p.dict() if hasattr(p, 'dict') else dict(p)
        text_parts.append(f"Product Name: {p_dict.get('product_name', 'Unknown')}")
        if p_dict.get('features'):
            text_parts.append("Features:\n" + "\n".join(f"- {f}" for f in p_dict['features']))
        if p_dict.get('full_text_snippet'):
            text_parts.append(f"Excerpt:\n{p_dict['full_text_snippet'][:1500]}")

    combined_text = "\n\n".join(text_parts)
    if custom_instruction:
        combined_text += f"\n\nUser Guidance/Instruction:\n{custom_instruction}"

    from chatbot_agent.nodes.ingest_product import PRODUCT_INGESTION_SYSTEM_PROMPT
    from pipeline.utils.llm_client import chat_json

    try:
        parsed = chat_json(
            messages=[
                {"role": "system", "content": PRODUCT_INGESTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract technical capabilities from this specification:\n\n{combined_text[:5000]}"}
            ],
            model="gpt-4o-mini"
        )
        mental_model = ProductUnderstanding(**parsed)
    except Exception as e:
        first_prod = products[0].dict() if hasattr(products[0], 'dict') else dict(products[0])
        mental_model = ProductUnderstanding(
            product_name=first_prod.get("product_name", "Uploaded Product"),
            domain=first_prod.get("category", "General Technical Domain"),
            key_features=first_prod.get("features", [])[:6],
            target_industry=first_prod.get("category", "Materials & Engineering"),
            focus_areas=["Core product functionality", "Key performance differentiators"],
            avoid_areas=["Generic packaging", "Unrelated auxiliary hardware"],
            summary=f"Automated understanding of {first_prod.get('product_name', 'product')} based on specification document."
        )

    features_list = getattr(mental_model, "key_features", None) or getattr(mental_model, "key_capabilities", []) or []

    products_list = []
    for p in products:
        p_dict = p.dict() if hasattr(p, 'dict') else dict(p)
        products_list.append(p_dict)

    mental_model_dict = mental_model.model_dump()
    mental_model_dict["products"] = products_list
    mental_model_dict["total_products"] = len(products_list)

    return {
        "status": "success",
        "session_upload_id": session_upload_id,
        "mental_model": mental_model_dict,
        "product_name": mental_model.product_name,
        "domain": mental_model.domain,
        "key_features": features_list,
        "key_capabilities": features_list,
        "focus_areas": mental_model.focus_areas,
        "avoid_areas": mental_model.avoid_areas,
        "summary": mental_model.summary,
        "products": products_list,
        "total_products": len(products_list)
    }
