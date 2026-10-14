"""
ingest_product.py — Parse uploaded product document and extract understanding via LLM.

Flow:
  1. Receive raw product_doc_text (already extracted by doc_parser utility)
  2. Call LLM to extract structured ProductUnderstanding
  3. Return mental_model + a human-readable summary for the user
"""

import json
import logging
import os

from chatbot_agent.state import ChatAgentState, ProductUnderstanding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Product Understanding Extraction Prompt
# ---------------------------------------------------------------------------

PRODUCT_INGESTION_SYSTEM_PROMPT = """You are a product intelligence analyst reviewing a product specification document.

Read the following product document and extract the following information:

1. product_name: The full name and version of the product (e.g. "SolidBMS v2.0")
2. domain: Primary technology domain in 3-5 words (e.g. "Battery Management Systems")
3. key_features: 3-7 specific technical features or claims (as a list)
4. target_industry: The industry or application area this product targets (e.g. "Electric Vehicles", "Aerospace")
5. relevant_patent_classes: IPC/CPC patent classification codes most relevant to this product (e.g. ["H01M", "B60L"])
6. focus_areas: Technology sub-areas to prioritize when building a patent taxonomy for this product (3-6 items)
7. avoid_areas: Technology areas that are NOT relevant to this product (can be empty list)
8. summary: 2-3 sentence human-readable summary for the user explaining what you understood about this product

Be honest and concise. If information is missing or unclear, make a reasonable inference and note it.

Return ONLY valid JSON with exactly these fields:
{
  "product_name": "...",
  "domain": "...",
  "key_features": ["...", "..."],
  "target_industry": "...",
  "relevant_patent_classes": ["...", "..."],
  "focus_areas": ["...", "..."],
  "avoid_areas": ["...", "..."],
  "summary": "..."
}
"""

# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def ingest_product(state: ChatAgentState) -> dict:
    """
    Read uploaded product document text and extract a structured ProductUnderstanding.
    Updates: mental_model, response_text, response_metadata
    """
    product_doc_text = state.product_doc_text
    if not product_doc_text or not product_doc_text.strip():
        return {
            "errors": ["No product document text found. Please upload a product document first."],
            "response_text": "I didn't receive any product document content. Please upload a PDF, DOCX, or paste the product description."
        }

    # Truncate very long documents
    doc_excerpt = product_doc_text
    # if len(product_doc_text) > 8000:
    #     doc_excerpt += "\n\n[Document truncated for analysis — first 8000 characters shown]"

    try:
        from pipeline.utils.llm_client import chat_json

        parsed = chat_json([
            {"role": "system", "content": PRODUCT_INGESTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Product Document:\n\n{doc_excerpt}"}
        ], model="gpt-4o-mini")

        mental_model = ProductUnderstanding(**parsed)

        logger.info(f"[ingest_product] Extracted understanding for: {mental_model.product_name}")

        # Build user-facing response
        features_bullet = "\n".join(f"  • {f}" for f in mental_model.key_features)
        patent_classes = ", ".join(mental_model.relevant_patent_classes) if mental_model.relevant_patent_classes else "Not specified"

        response_text = (
            f"I've read the product document. Here's what I understood:\n\n"
            f"**{mental_model.product_name}**\n"
            f"Domain: {mental_model.domain}\n"
            f"Industry: {mental_model.target_industry}\n\n"
            f"Key Features:\n{features_bullet}\n\n"
            f"Relevant Patent Classes: {patent_classes}\n\n"
            f"{mental_model.summary}\n\n"
            f"Does this look correct? You can say:\n"
            f"- **\"Looks good, build taxonomy\"** — to start building with this understanding\n"
            f"- **\"Correct: [your correction]\"** — to fix anything I got wrong\n"
            f"- **\"Focus more on [area]\"** — to adjust the focus"
        )

        return {
            "mental_model": mental_model,
            "mental_model_confirmed": False,
            "response_text": response_text,
            "response_metadata": {
                "type": "product_understanding_card",
                "mental_model": mental_model.model_dump()
            }
        }

    except json.JSONDecodeError as e:
        logger.error(f"[ingest_product] Failed to parse LLM JSON response: {e}")
        return {
            "errors": [f"Failed to parse product understanding: {str(e)}"],
            "response_text": "I had trouble parsing the product document. Could you paste the key product features directly in the chat?"
        }
    except Exception as e:
        logger.error(f"[ingest_product] Unexpected error: {e}")
        return {
            "errors": [f"Product ingestion failed: {str(e)}"],
            "response_text": f"Something went wrong while analyzing the product document: {str(e)}"
        }
