"""
pipeline/nodes/apply_rules.py

Phase 2: Post-processing node to enforce specific formatting and rules
on the raw data extracted during Phase 1.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

from pipeline.state import PatentExtractionState, ExtractionResult
from pipeline.utils.llm_client import chat_json
from pipeline.utils.node_rules import get_rules_for_node, format_rules_for_prompt

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert material science patent reviewer.
Your job is to take a RAW extracted value from a patent and apply strict formatting rules to it.
You MUST output valid JSON with exactly this structure:
{
  "formatted_value": "..."
}

CRITICAL RULES:
- Do NOT invent or hallucinate numbers. Use only the raw data provided.
- Apply the specific conversion/formatting rule perfectly.
- If the raw data contains a range (e.g. "10 - 20") or multiple dimensions (e.g. "MD: 10, TD: 20"), preserve the range and the dimensions in your output while applying the rule to all numbers.
- Do NOT write explanations. Only output the final formatted value string.
- If the raw data says something like "not mentioned", just return the original text or a blank string.
"""

def _apply_rule_via_llm(raw_result: ExtractionResult, node_path: str, reasoning: str) -> ExtractionResult:
    # If not found, skip LLM
    if raw_result["status"] != "FOUND":
        return raw_result

    # 1. Look up rule for this node name
    node_name = raw_result["node_name"]
    rule_dict = get_rules_for_node(node_name)
    rule_text = format_rules_for_prompt(rule_dict)

    new_values = []
    for val_dict in raw_result["values"]:
        raw_val = val_dict["value"]
        if not raw_val:
            new_values.append(val_dict)
            continue

        prompt = (
            f"Taxonomy Node: {node_path}\n"
            f"Original Extracted Value: {raw_val}\n"
            f"Rule to apply: {rule_text}\n"
        )
        if reasoning:
            prompt += f"Context/Reasoning from Phase 1: {reasoning}\n"
            
        prompt += "\nOutput the final formatted_value in JSON."

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            res = chat_json(messages, max_tokens=1000)
            formatted = res.get("formatted_value", raw_val)
            val_dict["value"] = f"[RAW Phase 1]\n{raw_val}\n\n[FORMATTED Phase 2]\n{str(formatted).strip()}"
        except Exception as exc:
            logger.error("[apply_rules] LLM format failed for '%s': %s", node_name, exc)
            # fallback to raw
            
        new_values.append(val_dict)

    raw_result["values"] = new_values
    return raw_result

def apply_rules(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: Enforce node rules (Phase 2).
    """
    extractions: list[ExtractionResult] = state.get("extractions", [])
    extraction_reasoning: dict[str, str] = state.get("extraction_reasoning") or {}
    patent_number = state.get("patent_number", "")

    if not extractions:
        return state

    logger.info("[apply_rules] Applying Phase 2 formatting rules for %s...", patent_number)

    processed_extractions = []
    for i, ext in enumerate(extractions, start=1):
        logger.info("[apply_rules] [%d/%d] %s", i, len(extractions), ext["node_path"])
        
        # Get reasoning to provide context to the LLM (so it knows e.g. which is MD vs TD if needed)
        reasoning_hint = ""
        node_path = ext["node_path"]
        node_name = ext["node_name"]
        
        for col_path, reasoning_text in extraction_reasoning.items():
            if col_path == node_path or col_path.endswith(node_name):
                reasoning_hint = reasoning_text
                break
        
        if not reasoning_hint:
            for col_path, reasoning_text in extraction_reasoning.items():
                if node_name.lower() in col_path.lower():
                    reasoning_hint = reasoning_text
                    break

        # Process via LLM if there are rules
        updated_ext = _apply_rule_via_llm(ext, node_path, reasoning_hint)
        processed_extractions.append(updated_ext)

    return {**state, "extractions": processed_extractions}
