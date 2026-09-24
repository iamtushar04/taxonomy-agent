"""
Node 2 — parse_content

Converts the raw API response into:
  - state["patent_chunks"]  — list of PatentChunk dicts (ordered by priority)
  - state["metadata"]       — bibliographic fields written directly to Excel
                              (no LLM needed for these)
"""

from __future__ import annotations

import logging

from pipeline.state import PatentChunk, PatentExtractionState
from pipeline.utils.html_parser import (
    parse_claims_text,
    parse_structured_description,
    PRIORITY_ABSTRACT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metadata fields mapped directly from API — no LLM
# ---------------------------------------------------------------------------

def _extract_metadata(data: dict) -> dict:
    """Pull all structured/bibliographic fields from the API response."""
    assignees = data.get("assignees") or []
    inventors  = data.get("inventors") or []

    legal_events = data.get("legal_events") or []
    legal_events_summary = "; ".join(
        f"{e.get('date', '')} {e.get('title', '')}"
        for e in legal_events[:5]          # cap at 5 events for readability
    )

    classifications = data.get("classifications") or []
    ipc_codes = [c for c in classifications if c.get("code", "").startswith(("A", "B", "C", "D", "E", "F", "G", "H"))]
    cpc_codes = [c for c in classifications if not c.get("code", "").startswith(("A", "B", "C", "D", "E", "F", "G", "H"))]

    patent_family = data.get("patent_family") or []
    patent_types = list({p.get("country", "") for p in patent_family})

    app_date  = data.get("application_date", "") or ""
    grant_date = data.get("grant_date", "") or ""

    return {
        "patent_number":      data.get("patent_number", ""),
        "title":              data.get("title", ""),
        "assignees":          ", ".join(assignees),
        "inventors":          ", ".join(inventors),
        "application_date":   app_date,
        "application_year":   app_date[:4] if app_date else "",
        "publication_date":   grant_date,
        "publication_year":   grant_date[:4] if grant_date else "",
        "priority_date":      data.get("priority_date", ""),
        "expiry_date":        data.get("expiration_date", ""),
        "legal_status":       data.get("legal_status", ""),
        "legal_events":       legal_events_summary,
        "patent_type":        ", ".join(patent_types),
        "count_ipc":          len(ipc_codes),
        "count_cpc":          len(cpc_codes),
        "abstract":           data.get("abstract", ""),
    }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def parse_content(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: parse raw API response into chunks + metadata.

    Reads:   state["raw_api_response"]
             state["patent_number"]
    Writes:  state["patent_chunks"]
             state["metadata"]
    """
    data           = state.get("raw_api_response") or {}
    patent_number  = state["patent_number"]

    if not data:
        msg = f"No API data for {patent_number} — skipping parse"
        logger.warning("[parse_content] %s", msg)
        return {**state, "patent_chunks": [], "metadata": {}, "errors": state.get("errors", []) + [msg]}

    logger.info("[parse_content] Parsing content for %s", patent_number)

    chunks: list[PatentChunk] = []

    # ── 1. Abstract ──────────────────────────────────────────────────────────
    abstract = (data.get("abstract") or "").strip()
    if abstract:
        chunks.append(PatentChunk(
            chunk_id=f"{patent_number}::abstract::0",
            section="abstract",
            source_label="Abstract",
            priority=PRIORITY_ABSTRACT,
            text=abstract,
        ))

    # ── 2. Claims (highest priority) ────────────────────────────────────────
    claims_text       = data.get("claims") or ""
    structured_claims = data.get("structured_claims") or []
    claim_chunks = parse_claims_text(claims_text, structured_claims, patent_number)
    chunks.extend(claim_chunks)
    logger.debug("[parse_content] %d claim chunks", len(claim_chunks))

    # ── 3. Structured description (HTML → tables + paragraphs + figures) ────
    structured_desc = data.get("structured_description") or ""
    desc_chunks = parse_structured_description(structured_desc, patent_number)
    chunks.extend(desc_chunks)
    logger.debug("[parse_content] %d description/table/figure chunks", len(desc_chunks))

    # ── 4. Sort by priority (ascending = highest first) ─────────────────────
    chunks.sort(key=lambda c: c["priority"])

    # ── 5. Extract metadata (no LLM needed) ─────────────────────────────────
    metadata = _extract_metadata(data)

    logger.info(
        "[parse_content] Total %d chunks | metadata fields: %d",
        len(chunks), len(metadata),
    )
    return {**state, "patent_chunks": chunks, "metadata": metadata}
