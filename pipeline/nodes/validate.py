"""
Node 6 — validate

Validates each extraction before it reaches the Excel writer.

Two checks:
  1. Evidence grounding — does the evidence string actually appear in
     the patent chunks? If not, the LLM hallucinated. → UNCERTAIN
  2. Confidence floor — if the LLM's own confidence is below the
     configured threshold, downgrade to UNCERTAIN.

Does NOT make additional LLM calls — purely string-based checks.
This keeps the validation step fast and deterministic.
"""

from __future__ import annotations

import logging
import os
import re
from difflib import SequenceMatcher

from pipeline.state import ExtractionResult, ExtractionValue, PatentExtractionState

logger = logging.getLogger(__name__)

# Minimum fuzzy similarity for evidence to be considered "found" in text
_EVIDENCE_SIMILARITY_THRESHOLD = 0.75

# Minimum confidence value below which we mark UNCERTAIN
_CONFIDENCE_FLOOR = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.5"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Normalize text by stripping quotes, collapsing whitespace, and normalizing dashes/unicode."""
    if not text:
        return ""
    t = text.replace("\ufffd", "-").replace("–", "-").replace("—", "-").replace("\xa0", " ")
    t = t.replace('“', '"').replace('”', '"').replace("‘", "'").replace("’", "'")
    # Normalize European decimal commas (e.g., 972,0 -> 972.0)
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    t = re.sub(r"[\s\n\r\t]+", " ", t)
    return t.lower().strip()


def _all_chunk_text(state: PatentExtractionState) -> str:
    """Concatenate all patent chunk text for evidence search."""
    chunks = state.get("patent_chunks") or []
    return _normalize_text(" ".join(c["text"] for c in chunks))


def _evidence_found(evidence: str, full_text: str) -> tuple[bool, float]:
    """
    Check if the evidence quote appears in the full patent text.
    Returns (found: bool, similarity: float).
    Uses substring search first (exact), then anchor matching, table segment matching, and fuzzy sliding window.
    """
    if not evidence:
        return False, 0.0

    ev_norm = _normalize_text(evidence)
    if not ev_norm:
        return False, 0.0

    # 1. Exact substring check on normalized text
    if ev_norm in full_text:
        return True, 1.0

    # 2. Strip surrounding quotation marks or citations often wrapped by LLMs
    ev_clean = ev_norm.strip('"\'`')
    if ev_clean in full_text:
        return True, 1.0

    # 3. Table segment matching: LLMs often quote multiple table cells separated by '|'
    if "|" in evidence:
        # Check pipe-collapsed version
        ev_no_pipes = re.sub(r"[\s\|]+", " ", ev_norm).strip()
        ft_no_pipes = re.sub(r"[\s\|]+", " ", full_text).strip()
        if ev_no_pipes and ev_no_pipes in ft_no_pipes:
            return True, 1.0

        # Check individual cell segments
        segments = [s.strip() for s in evidence.split("|") if len(s.strip()) >= 2]
        if segments:
            matched_segs = sum(1 for seg in segments if _normalize_text(seg) in full_text)
            seg_ratio = matched_segs / len(segments)
            if seg_ratio >= 0.70:
                return True, max(seg_ratio, 0.85)

    window = len(ev_clean)
    if window < 20:
        return True, 0.8

    # 3. Direct anchor lookup (check if prefix or suffix matches anywhere in text)
    anchor_len = min(35, window // 2)
    prefix_anchor = ev_clean[:anchor_len]
    pos = full_text.find(prefix_anchor)
    if pos != -1:
        local_snippet = full_text[pos : pos + window + 30]
        ratio = SequenceMatcher(None, ev_clean, local_snippet).ratio()
        if ratio >= _EVIDENCE_SIMILARITY_THRESHOLD:
            return True, ratio

    suffix_anchor = ev_clean[-anchor_len:]
    pos_s = full_text.find(suffix_anchor)
    if pos_s != -1:
        start_idx = max(0, pos_s - window + anchor_len - 15)
        local_snippet = full_text[start_idx : pos_s + anchor_len + 15]
        ratio = SequenceMatcher(None, ev_clean, local_snippet).ratio()
        if ratio >= _EVIDENCE_SIMILARITY_THRESHOLD:
            return True, ratio

    # 4. Sliding window fuzzy matching
    best = 0.0
    step = max(window // 6, 5)
    for i in range(0, max(1, len(full_text) - window + 1), step):
        snippet = full_text[i : i + window]
        ratio = SequenceMatcher(None, ev_clean, snippet).ratio()
        if ratio > best:
            best = ratio
        if best >= _EVIDENCE_SIMILARITY_THRESHOLD:
            return True, best

    return best >= _EVIDENCE_SIMILARITY_THRESHOLD, best


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def validate(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: validate extractions against the patent source text.

    Reads:   state["extractions"]
             state["patent_chunks"]
    Writes:  state["validated_extractions"]
    """
    extractions: list[ExtractionResult] = state.get("extractions") or []
    patent_number = state.get("patent_number", "")

    if not extractions:
        return {**state, "validated_extractions": []}

    full_text = _all_chunk_text(state)
    validated: list[ExtractionResult] = []

    for result in extractions:
        if result["status"] == "NOT_FOUND":
            validated.append(result)
            continue

        validated_values: list[ExtractionValue] = []
        for val in result["values"]:
            evidence  = val.get("evidence", "")
            confidence = val.get("confidence", 0.5)

            # Check 1: evidence grounding
            found, similarity = _evidence_found(evidence, full_text)
            if not found:
                logger.warning(
                    "[validate] Evidence NOT found in patent text for node '%s' "
                    "(similarity=%.2f). Downgrading to UNCERTAIN.\n  Evidence: %s",
                    result["node_name"], similarity, evidence[:120],
                )
                # Keep the value but reduce confidence
                validated_values.append({
                    **val,
                    "confidence": min(confidence, 0.4),
                })
                continue

            # Check 2: confidence floor
            adjusted_confidence = confidence * similarity if similarity < 1.0 else confidence
            if adjusted_confidence < _CONFIDENCE_FLOOR:
                logger.debug(
                    "[validate] Confidence too low for node '%s' (%.2f). Marking UNCERTAIN.",
                    result["node_name"], adjusted_confidence,
                )
                validated_values.append({
                    **val,
                    "confidence": adjusted_confidence,
                })
            else:
                validated_values.append({
                    **val,
                    "confidence": round(adjusted_confidence, 3),
                })

        # Determine final status
        if not validated_values:
            final_status = "NOT_FOUND"
        elif all(v["confidence"] < _CONFIDENCE_FLOOR for v in validated_values):
            final_status = "UNCERTAIN"
        else:
            final_status = result["status"]

        validated.append({
            **result,
            "status": final_status,
            "values": validated_values,
        })

    found_count = sum(1 for e in validated if e["status"] == "FOUND")
    uncertain_count = sum(1 for e in validated if e["status"] == "UNCERTAIN")
    logger.info(
        "[validate] %s — FOUND: %d, UNCERTAIN: %d, NOT_FOUND: %d",
        patent_number, found_count, uncertain_count,
        len(validated) - found_count - uncertain_count,
    )

    return {**state, "validated_extractions": validated}
