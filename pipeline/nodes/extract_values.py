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
5. Multiple distinct values for the same node are allowed. List each as a separate
   object in the values array.
6. Include the unit in the value string (e.g. "35 MPa", not just "35").

SOURCE PRIORITY WATERFALL -- follow this order strictly:
  Step 1. Check [Claim N] sections FIRST.
          If the value is explicitly stated in any claim -> use it. STOP here.
  Step 2. If NOT in claims -> check [Description] and [Example N] sections.
          If found -> use it. STOP here.
  Step 3. If NOT in description -> check [Table N] sections.
          Use ONLY inventive/working examples. Do NOT use comparative or
          reference examples. Record the table number and example number
          in the source field (e.g. "Table 3, Example 4").
  Step 4. If not found anywhere -> return status "NOT_FOUND".

Record which source you used in the source field of every extracted value.
If an EXPERT EXTRACTION REASONING block is provided in the user message,
it overrides this waterfall completely -- follow it exactly instead.
"""


def _extract_for_node(
    node: TaxonomyNode,
    context: str,
    extraction_reasoning: dict[str, str] | None = None,
) -> ExtractionResult:
    """Run one LLM call to extract values for a single taxonomy node.

    If extraction_reasoning contains an entry whose key ends with the node's
    leaf name (or matches the node path), that human-written reasoning is
    injected verbatim into the prompt so the LLM knows exactly:
      - which source to look at (Claims / Description / Table N)
      - which examples to use (inventive examples only, not comparatives)
      - how to pick the value (full range, MD/TD separate, etc.)
    """
    # Phase 1: extract raw data using reasoning only.
    # Node rules (upper/lower limit, unit conversion) are Phase 2 — applied
    # AFTER extraction on the already-extracted data. Do NOT inject them here.

    # ── Find matching reasoning for this node ────────────────────────────────
    reasoning_hint = ""
    if extraction_reasoning:
        node_path  = node["path"]   # e.g. "Polymer Properties > Mechanical > Tensile Strength"
        node_name  = node["name"]   # e.g. "Tensile Strength"

        # First try exact path match, then leaf-name match
        for col_path, reasoning_text in extraction_reasoning.items():
            if col_path == node_path or col_path.endswith(node_name):
                reasoning_hint = reasoning_text
                break
        # Fallback: partial match on the node name anywhere in the col_path
        if not reasoning_hint:
            for col_path, reasoning_text in extraction_reasoning.items():
                if node_name.lower() in col_path.lower():
                    reasoning_hint = reasoning_text
                    break

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Taxonomy node: \"{node['path']}\"\n"
                f"What to extract: {node.get('description', node['name'])}\n"
                + (
                    "\n--- EXPERT EXTRACTION REASONING (FOLLOW THIS EXACTLY) ---\n"
                    + reasoning_hint
                    + "\n--- END REASONING ---\n\n"
                    if reasoning_hint else ""
                )
                + f"Patent text:\n{context}\n\n"
                "Return JSON:\n"
                "{\n"
                "  \"status\": \"FOUND\" | \"NOT_FOUND\" | \"UNCERTAIN\",\n"
                "  \"values\": [\n"
                "    {\n"
                "      \"value\": \"...\",\n"
                "      \"evidence\": \"exact quote\",\n"
                "      \"source\": \"Claim 1 / Example 4 / Table 2 / Abstract\",\n"
                "      \"confidence\": 0.95 // Number between 0.0 and 1.0\n"
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
    extraction_reasoning: dict[str, str] = state.get("extraction_reasoning") or {}

    if extraction_reasoning:
        logger.info(
            "[extract_values] Reasoning loaded: %d column(s) for %s",
            len(extraction_reasoning), patent_number,
        )
    else:
        logger.info(
            "[extract_values] No reasoning provided for %s — using generic extraction",
            patent_number,
        )

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
        result = _extract_for_node(node, context, extraction_reasoning)
        extractions.append(result)
        logger.debug(
            "[extract_values] -> status=%s values=%d reasoning=%s",
            result["status"], len(result["values"]),
            "YES" if extraction_reasoning else "NO",
        )

    found = sum(1 for e in extractions if e["status"] == "FOUND")
    logger.info(
        "[extract_values] Done: %d FOUND, %d NOT_FOUND, %d UNCERTAIN",
        found,
        sum(1 for e in extractions if e["status"] == "NOT_FOUND"),
        sum(1 for e in extractions if e["status"] == "UNCERTAIN"),
    )

    return {**state, "extractions": extractions}
