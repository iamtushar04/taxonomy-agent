"""
Shared state TypedDict that flows through every LangGraph node.
Each node reads from and writes to this dict — nothing is passed as
function arguments, keeping node signatures uniform and easy to extend.
"""

from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Sub-types
# ---------------------------------------------------------------------------

class TaxonomyNode(TypedDict):
    node_id: str          # stable hash of the full path
    name: str             # leaf label, e.g. "Tensile Strength"
    parent_id: Optional[str]
    level: int            # 0 = root, 1 = first child, …
    path: str             # "Polymer Properties > Mechanical > Tensile Strength"
    description: str      # LLM-generated extraction hint (Phase 3)
    rules: dict           # data-preference rules injected into prompts


class PatentChunk(TypedDict):
    chunk_id: str         # "{patent_number}::{section}::{index}"
    section: str          # "claims" | "description" | "abstract" | "table" | "figure"
    source_label: str     # human-readable, e.g. "Claim 1", "Example 4", "Table 2"
    priority: int         # 1 = highest (independent claims), 3 = lowest
    text: str


class ExtractionValue(TypedDict):
    value: str            # extracted value with unit, e.g. "35 MPa"
    evidence: str         # exact quote from patent text
    source: str           # e.g. "Claim 1", "Example 4"
    confidence: float     # 0.0 – 1.0


class ExtractionResult(TypedDict):
    node_id: str
    node_name: str
    node_path: str
    status: str           # "FOUND" | "NOT_FOUND" | "UNCERTAIN"
    values: list[ExtractionValue]


# ---------------------------------------------------------------------------
# Main pipeline state
# ---------------------------------------------------------------------------

class PatentExtractionState(TypedDict, total=False):
    # ── Inputs (set by run.py before graph invocation) ──────────────────────
    patent_number: str
    taxonomy_nodes: list[TaxonomyNode]   # all nodes from the taxonomy
    excel_path: str                       # absolute path to the workbook
    excel_sheet: str
    excel_row: int                        # 1-indexed row for this patent

    # ── Node 1: fetch_patent ─────────────────────────────────────────────────
    raw_api_response: dict[str, Any]

    # ── Node 2: parse_content ────────────────────────────────────────────────
    patent_chunks: list[PatentChunk]
    metadata: dict[str, Any]             # title, assignees, dates, legal_status …

    # ── Node 3: describe_nodes ───────────────────────────────────────────────
    # taxonomy_nodes is updated in-place with .description and .rules filled

    # ── Node 4: match_relevance ──────────────────────────────────────────────
    relevant_nodes: list[TaxonomyNode]

    # ── Node 5: extract_values ───────────────────────────────────────────────
    extractions: list[ExtractionResult]

    # ── Node 6: validate ─────────────────────────────────────────────────────
    validated_extractions: list[ExtractionResult]

    # ── Node 7: write_excel ──────────────────────────────────────────────────
    excel_written: bool

    # ── Errors (any node can append here) ────────────────────────────────────
    errors: list[str]
