"""
Node 5 — extract_values

For each relevant taxonomy node, asks GPT-4o to extract values from the
patent text.  Runs one LLM call per node (or batch of nodes when possible).

Output contract per node:
  {
    "status": "FOUND" | "NOT_FOUND" | "UNCERTAIN",
    "values": [
      {
        "value":      "35 MPa",
        "evidence":   "exact quote from patent text",
        "source":     "Claim 1",
        "confidence": 0.92
      }
    ]
  }

Key rules enforced in every prompt:
  - evidence MUST be an exact quote (not paraphrased)
  - Multiple values are allowed in the values list
  - If not found → status=NOT_FOUND, values=[]
  - Source priority follows node's data-preference rules
"""

from __future__ import annotations

import logging

from pipeline.state import (
    ExtractionResult,
    ExtractionValue,
    PatentChunk,
    PatentExtractionState,
    TaxonomyNode,
)
from pipeline.utils.llm_client import chat_json
from pipeline.utils.node_rules import format_rules_for_prompt

logger = logging.getLogger(__name__)

# Maximum characters of patent text to send per extraction call
_MAX_CONTEXT_CHARS = 12_000

# Sections in priority order for context assembly
_SECTION_PRIORITY = ["claims", "description", "table", "abstract", "figure"]


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(chunks: list[PatentChunk], max_chars: int = _MAX_CONTEXT_CHARS) -> str:
    """
    Assemble patent text from chunks in section-priority order.
    Caps total length at max_chars to stay within context window.
    """
    # Group chunks by section priority
    ordered: list[PatentChunk] = sorted(chunks, key=lambda c: c["priority"])

    parts: list[str] = []
    total = 0

    for chunk in ordered:
        label = chunk["source_label"]
        text  = chunk["text"]
        block = f"[{label}]\n{text}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Single-node extraction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a meticulous patent analyst. Your job is to extract specific technical
information from a patent document for a given taxonomy node.

Rules you MUST follow:
1. Extract information ONLY from the provided patent text. NEVER invent or infer
   information not explicitly stated.
2. The "evidence" field MUST be an exact verbatim quote from the text (max 300 chars).
3. If the information is not present, return status "NOT_FOUND" with values=[].
4. If the information is present but ambiguous or unclear, return status "UNCERTAIN".
5. Multiple distinct values for the same node are allowed — list each as a separate
   object in the values array.
6. Always follow the data preference rules provided.
7. Include the unit in the value string (e.g. "35 MPa", not just "35").
"""


def _extract_for_node(
    node: TaxonomyNode,
    context: str,
) -> ExtractionResult:
    """Run one LLM call to extract values for a single taxonomy node."""
    rules_text = format_rules_for_prompt(node.get("rules") or {})

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Taxonomy node: \"{node['path']}\"\n"
                f"What to extract: {node.get('description', node['name'])}\n"
                f"Data preference rules: {rules_text}\n\n"
                f"Patent text:\n{context}\n\n"
                "Return JSON:\n"
                "{\n"
                "  \"status\": \"FOUND\" | \"NOT_FOUND\" | \"UNCERTAIN\",\n"
                "  \"values\": [\n"
                "    {\n"
                "      \"value\": \"...\",\n"
                "      \"evidence\": \"exact quote\",\n"
                "      \"source\": \"Claim 1 / Example 4 / Table 2 / Abstract\",\n"
                "      \"confidence\": 0.0\n"
                "    }\n"
                "  ]\n"
                "}"
            ),
        },
    ]

    try:
        raw = chat_json(messages, max_tokens=2048)
    except Exception as exc:
        logger.error(
            "[extract_values] LLM error for node '%s': %s", node["name"], exc
        )
        return ExtractionResult(
            node_id=node["node_id"],
            node_name=node["name"],
            node_path=node["path"],
            status="UNCERTAIN",
            values=[],
        )

    status = raw.get("status", "NOT_FOUND")
    if status not in ("FOUND", "NOT_FOUND", "UNCERTAIN"):
        status = "UNCERTAIN"

    raw_values = raw.get("values") or []
    values: list[ExtractionValue] = []
    for v in raw_values:
        if not isinstance(v, dict):
            continue
        values.append(ExtractionValue(
            value=str(v.get("value", "")).strip(),
            evidence=str(v.get("evidence", "")).strip(),
            source=str(v.get("source", "")).strip(),
            confidence=float(v.get("confidence", 0.5)),
        ))

    return ExtractionResult(
        node_id=node["node_id"],
        node_name=node["name"],
        node_path=node["path"],
        status=status,
        values=values,
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def extract_values(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: extract values for all relevant taxonomy nodes.

    Reads:   state["relevant_nodes"]
             state["patent_chunks"]
    Writes:  state["extractions"]
    """
    relevant_nodes: list[TaxonomyNode] = state.get("relevant_nodes") or []
    chunks: list[PatentChunk]          = state.get("patent_chunks") or []
    patent_number                      = state.get("patent_number", "")

    if not relevant_nodes:
        logger.info("[extract_values] No relevant nodes for %s", patent_number)
        return {**state, "extractions": []}

    # Build the full context once and reuse for all nodes
    context = _build_context(chunks)

    logger.info(
        "[extract_values] Extracting %d nodes for %s (context=%d chars)",
        len(relevant_nodes), patent_number, len(context),
    )

    extractions: list[ExtractionResult] = []
    for i, node in enumerate(relevant_nodes, start=1):
        logger.info(
            "[extract_values] [%d/%d] %s", i, len(relevant_nodes), node["path"]
        )
        result = _extract_for_node(node, context)
        extractions.append(result)
        logger.debug(
            "[extract_values] → status=%s values=%d",
            result["status"], len(result["values"]),
        )

    found = sum(1 for e in extractions if e["status"] == "FOUND")
    logger.info(
        "[extract_values] Done: %d FOUND, %d NOT_FOUND, %d UNCERTAIN",
        found,
        sum(1 for e in extractions if e["status"] == "NOT_FOUND"),
        sum(1 for e in extractions if e["status"] == "UNCERTAIN"),
    )

    return {**state, "extractions": extractions}
