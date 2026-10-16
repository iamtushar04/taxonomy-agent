"""
chunk_partitioner.py

Converts a raw patent full_text string (as stored in patents_data) into a
prioritized list of PatentChunk dicts — the same format the pipeline's
extract_values.py expects.

Section priority mapping:
  Priority 1 → Claims      (highest — exact inventive scope)
  Priority 2 → Description (narrative + examples)
  Priority 3 → Abstract    (overview / fallback)

This is intentionally lightweight: it does plain string splitting, not HTML
parsing. The pipeline's html_parser is for structured API responses; here we
already have the pre-assembled full_text from the DB.
"""

from __future__ import annotations

from pipeline.state import PatentChunk

# Max chars per section sent to the LLM
_MAX_CLAIMS_CHARS = 15_000
_MAX_DESC_CHARS   = 15_000
_MAX_ABS_CHARS    = 1_500


def partition_patent_chunks(patent_id: str, full_text: str, abstract: str = "") -> list[PatentChunk]:
    """
    Split raw patent full_text into a prioritized list of PatentChunk dicts.

    Args:
        patent_id:  Patent number / ID string (used for chunk_id generation).
        full_text:  Raw combined patent text (may contain "Claims:" and "Description:" headers).
        abstract:   Optional pre-extracted abstract / summary string.

    Returns:
        List of PatentChunk dicts sorted ascending by priority (1 = highest first).
    """
    chunks: list[PatentChunk] = []
    lower = full_text.lower()

    # ── Locate section boundaries ────────────────────────────────────────────
    claims_idx = lower.find("claims:")
    desc_idx   = lower.find("description:")

    # ── 1. Claims (Priority 1 — highest) ────────────────────────────────────
    if claims_idx != -1:
        if desc_idx != -1 and desc_idx > claims_idx:
            claims_text = full_text[claims_idx:desc_idx].strip()
        else:
            claims_text = full_text[claims_idx:].strip()

        if claims_text:
            chunks.append(PatentChunk(
                chunk_id=f"{patent_id}::claims::0",
                section="claims",
                source_label="Claims",
                priority=1,
                text=claims_text[:_MAX_CLAIMS_CHARS],
            ))

    # ── 2. Description (Priority 2) ──────────────────────────────────────────
    if desc_idx != -1:
        desc_text = full_text[desc_idx:].strip()
        if desc_text:
            chunks.append(PatentChunk(
                chunk_id=f"{patent_id}::description::0",
                section="description",
                source_label="Description",
                priority=2,
                text=desc_text[:_MAX_DESC_CHARS],
            ))

    # ── 3. Abstract / fallback (Priority 3) ─────────────────────────────────
    #    Use pre-extracted abstract if provided; otherwise first 1500 chars of full_text
    abs_text = (abstract or "").strip()
    if not abs_text and not chunks:
        # last resort — no sections found at all
        abs_text = full_text[:_MAX_ABS_CHARS]

    if abs_text:
        chunks.append(PatentChunk(
            chunk_id=f"{patent_id}::abstract::0",
            section="abstract",
            source_label="Abstract",
            priority=3,
            text=abs_text[:_MAX_ABS_CHARS],
        ))

    # Sort ascending so priority-1 comes first (matches _build_context sort order)
    chunks.sort(key=lambda c: c["priority"])
    return chunks
