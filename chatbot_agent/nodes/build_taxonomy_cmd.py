"""
build_taxonomy_cmd.py — Handle the "build taxonomy" command from the user.

When the user says "build taxonomy" or "go ahead", this node:
1. Confirms the mental model is present (product was uploaded)
2. Assembles the taxonomy run trigger payload including the mental model
3. Returns a response with the run trigger signal so the backend API can start the run

NOTE: This node does NOT call the taxonomy pipeline directly.
      It returns response_metadata["trigger_run"] = True with parameters.
      The API route (/api/chat/session/{id}/message) reads this and starts the run.
"""

import logging
from chatbot_agent.state import ChatAgentState

logger = logging.getLogger(__name__)


def build_taxonomy_cmd(state: ChatAgentState) -> dict:
    """
    Handle "build taxonomy" intent.
    Confirms mental model, signals the API to trigger a taxonomy run.

    Updates: mental_model_confirmed, response_text, response_metadata
    """
    mental_model = state.mental_model
    mapping_rules = state.mapping_rules or []

    # Case 1: No product uploaded yet
    if not mental_model:
        return {
            "response_text": (
                "I don't have any product information yet. Please upload a product document first, "
                "or describe your product in the chat and I'll extract the key details.\n\n"
                "Once I understand the product, I can build a taxonomy focused on the right technology areas."
            ),
            "response_metadata": {"type": "no_product_warning"}
        }

    # Case 2: Product uploaded — confirm and trigger
    focus_list = "\n".join(f"  • {area}" for area in mental_model.focus_areas)
    rules_summary = ""
    if mapping_rules:
        rules_summary = f"\n\n**Custom mapping rules ({len(mapping_rules)}) will be applied:**\n"
        rules_summary += "\n".join(f"  • {r.rule_type.value}: {r.source_node}" + (f" → {r.target_node}" if r.target_node else "") for r in mapping_rules)

    response_text = (
        f"Starting taxonomy build with the following focus:\n\n"
        f"**Product:** {mental_model.product_name}\n"
        f"**Domain:** {mental_model.domain} ({mental_model.target_industry})\n\n"
        f"**Priority areas:**\n{focus_list}"
        f"{rules_summary}\n\n"
        f"⏳ Taxonomy generation is starting now. I'll notify you when it's complete."
    )

    # Build the mental model context string to inject into the taxonomy pipeline
    mental_model_context = _build_context_string(mental_model, mapping_rules)

    return {
        "mental_model_confirmed": True,
        "response_text": response_text,
        "response_metadata": {
            "type": "taxonomy_run_trigger",
            "trigger_run": True,
            "mental_model_context": mental_model_context,
            "mental_model": mental_model.model_dump(),
            "mapping_rules": [r.model_dump() for r in mapping_rules]
        }
    }


def _build_context_string(mental_model, mapping_rules: list) -> str:
    """
    Build a plain-text context string that gets injected into the taxonomy
    pipeline's LLM prompts as soft guidance. This is the ONLY point of
    contact with the taxonomy pipeline — a simple string, nothing more.
    """
    lines = [
        "=== PRODUCT CONTEXT (Use as guidance for taxonomy focus) ===",
        f"Product: {mental_model.product_name}",
        f"Domain: {mental_model.domain}",
        f"Target Industry: {mental_model.target_industry}",
        "",
        "Key Technical Features:",
    ]
    for feature in mental_model.key_features:
        lines.append(f"  - {feature}")

    if mental_model.focus_areas:
        lines.append("")
        lines.append("Priority Technology Areas (give these more weight in the taxonomy):")
        for area in mental_model.focus_areas:
            lines.append(f"  - {area}")

    if mental_model.avoid_areas:
        lines.append("")
        lines.append("Areas to de-prioritize (less relevant to this product):")
        for area in mental_model.avoid_areas:
            lines.append(f"  - {area}")

    if mapping_rules:
        lines.append("")
        lines.append("User-defined structural rules:")
        for rule in mapping_rules:
            target = f" → {rule.target_node}" if rule.target_node else ""
            lines.append(f"  - {rule.rule_type.value}: '{rule.source_node}'{target}")

    lines.append("=== END PRODUCT CONTEXT ===")
    return "\n".join(lines)
