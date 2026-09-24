"""
Node 4 — match_relevance

Determines which taxonomy nodes are relevant to a given patent.
Uses a two-pass strategy to minimise LLM calls:

  Pass 1 — Keyword scan (free)
    Check if the patent abstract + independent claims mention any term
    from the node name or description. Fast, zero cost.

  Pass 2 — LLM scoring (cheap model, batched)
    For nodes not clearly accepted or rejected by keywords, send a
    batch of node names + the patent context to GPT-4o-mini and get
    a 0/1 relevance score for each.

The output is a filtered list of relevant TaxonomyNode dicts that the
extraction node will process.
"""

from __future__ import annotations

import logging
import re

from pipeline.state import PatentExtractionState, TaxonomyNode
from pipeline.utils.llm_client import chat_json

logger = logging.getLogger(__name__)

# ── Tuning constants ──────────────────────────────────────────────────────
# Minimum keyword hits in the patent text to auto-accept a node (pass 1)
_KW_ACCEPT_THRESHOLD = 1

# Nodes per LLM batch in pass 2
_LLM_BATCH_SIZE = 30


# ---------------------------------------------------------------------------
# Pass 1 — keyword matching
# ---------------------------------------------------------------------------

def _build_keyword_set(node: TaxonomyNode) -> set[str]:
    """Extract searchable keywords from a node's name and path."""
    tokens: set[str] = set()
    for text in [node["name"], node["path"]]:
        # Split on spaces, slashes, parentheses, dashes
        words = re.split(r"[\s/\-\(\)>]+", text.lower())
        tokens.update(w for w in words if len(w) > 3)
    return tokens


def _keyword_score(node: TaxonomyNode, patent_text: str) -> int:
    """Count how many of the node's keywords appear in the patent text."""
    lower_text = patent_text.lower()
    keywords = _build_keyword_set(node)
    return sum(1 for kw in keywords if kw in lower_text)


# ---------------------------------------------------------------------------
# Pass 2 — LLM relevance scoring
# ---------------------------------------------------------------------------

def _llm_score_batch(
    nodes: list[TaxonomyNode],
    patent_context: str,
) -> dict[str, bool]:
    """
    Ask GPT-4o-mini whether each node is relevant to the patent.
    Returns {node_id: True/False}.
    """
    node_list = "\n".join(
        f'{i+1}. node_id="{n["node_id"]}" | name="{n["name"]}" | path="{n["path"]}"'
        for i, n in enumerate(nodes)
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a patent analyst. Given a patent's context and a list of "
                "taxonomy nodes, determine which nodes are relevant to this patent. "
                "A node is relevant if the patent likely contains information that "
                "could fill that category. Return a JSON object: "
                "{\"<node_id>\": true or false, ...}. "
                "Be inclusive — if in doubt, mark as true."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Patent context (abstract + first claims):\n{patent_context[:3000]}\n\n"
                f"Taxonomy nodes to evaluate:\n{node_list}\n\n"
                "Return JSON: {\"<node_id>\": true/false, ...}"
            ),
        },
    ]

    try:
        result = chat_json(messages, cheap=True, max_tokens=1024)
        # Normalise values to bool
        return {k: bool(v) for k, v in result.items()}
    except Exception as exc:
        logger.error("[match_relevance] LLM batch failed: %s", exc)
        # Default to relevant on error (better to over-extract than miss)
        return {n["node_id"]: True for n in nodes}


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def match_relevance(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: filter taxonomy nodes to those relevant for this patent.

    Reads:   state["taxonomy_nodes"]
             state["patent_chunks"]
             state["metadata"]  (abstract used for context)
    Writes:  state["relevant_nodes"]
    """
    nodes: list[TaxonomyNode]   = state.get("taxonomy_nodes") or []
    chunks                      = state.get("patent_chunks") or []
    metadata                    = state.get("metadata") or {}

    if not nodes:
        return {**state, "relevant_nodes": []}

    # Build patent text for keyword matching (abstract + all claims)
    claim_chunks = [c for c in chunks if c["section"] == "claims"]
    patent_text = (metadata.get("abstract", "") + " " +
                   " ".join(c["text"] for c in claim_chunks[:10]))  # first 10 claims

    # Patent context for LLM (shorter)
    patent_context = (
        f"Title: {metadata.get('title', '')}\n"
        f"Abstract: {metadata.get('abstract', '')[:1000]}\n"
        f"Key claims: {' '.join(c['text'] for c in claim_chunks[:3])[:1500]}"
    )

    definitely_relevant: list[TaxonomyNode] = []
    maybe_relevant: list[TaxonomyNode] = []
    rejected: list[TaxonomyNode] = []

    # ── Pass 1: keyword ────────────────────────────────────────────────────
    for node in nodes:
        score = _keyword_score(node, patent_text)
        if score >= _KW_ACCEPT_THRESHOLD:
            definitely_relevant.append(node)
        else:
            maybe_relevant.append(node)

    logger.info(
        "[match_relevance] Pass 1: %d auto-accepted, %d going to LLM",
        len(definitely_relevant), len(maybe_relevant),
    )

    # ── Pass 2: LLM scoring for uncertain nodes ────────────────────────────
    llm_relevant: list[TaxonomyNode] = []
    for i in range(0, len(maybe_relevant), _LLM_BATCH_SIZE):
        batch = maybe_relevant[i : i + _LLM_BATCH_SIZE]
        scores = _llm_score_batch(batch, patent_context)
        for node in batch:
            if scores.get(node["node_id"], True):   # default True if missing
                llm_relevant.append(node)
            else:
                rejected.append(node)

    relevant_nodes = definitely_relevant + llm_relevant

    logger.info(
        "[match_relevance] Final: %d relevant, %d rejected (of %d total nodes)",
        len(relevant_nodes), len(rejected), len(nodes),
    )
    return {**state, "relevant_nodes": relevant_nodes}
