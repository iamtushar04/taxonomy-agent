"""
Node 7 — write_excel

Writes validated extractions back into the source Excel file.

Cell conventions:
  - FOUND, single value   → write value string
  - FOUND, multi-value    → values joined with " | "
  - UNCERTAIN             → "[?] " prefix on the value
  - NOT_FOUND             → cell left blank (None)
  - Evidence              → stored as a cell Comment (note)
  - Metadata fields       → written directly from state["metadata"]

Uses openpyxl.  The workbook is loaded, the target row is updated,
and the file is saved back.  A backup is made before writing to avoid
data loss.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.comments import Comment

from pipeline.state import ExtractionResult, PatentExtractionState
from pipeline.utils.excel_mapper import ExcelColumnMap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metadata column name → key in state["metadata"]
# Case-insensitive matching used at runtime.
# ---------------------------------------------------------------------------
_METADATA_COLUMN_ALIASES: dict[str, str] = {
    "patent number":      "patent_number",
    "patent no":          "patent_number",
    "patent title":       "title",
    "title":              "title",
    "assignee":           "assignees",
    "assignees":          "assignees",
    "inventors":          "inventors",
    "application date":   "application_date",
    "application year":   "application_year",
    "publication date":   "publication_date",
    "publication year":   "publication_year",
    "priority date":      "priority_date",
    "expiry date":        "expiry_date",
    "expiration date":    "expiry_date",
    "legal status":       "legal_status",
    "simple legal status":"legal_status",
    "legal status & events": "legal_events",
    "legal events":       "legal_events",
    "patent type":        "patent_type",
    "count of ipc":       "count_ipc",
    "count of cpc":       "count_cpc",
    "count ipc":          "count_ipc",
    "count cpc":          "count_cpc",
    "summary":            "abstract",
}


def _resolve_metadata_key(col_label: str) -> Optional[str]:
    return _METADATA_COLUMN_ALIASES.get(col_label.lower().strip())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_cell_value(result: ExtractionResult) -> Optional[str]:
    """
    Convert an ExtractionResult to the string that goes in the Excel cell.
    Returns None for NOT_FOUND (cell stays blank).
    """
    if result["status"] == "NOT_FOUND":
        return None

    values = result.get("values") or []
    if not values:
        return None

    value_strings = [v["value"] for v in values if v.get("value")]
    if not value_strings:
        return None

    joined = " | ".join(value_strings)
    if result["status"] == "UNCERTAIN":
        joined = f"[?] {joined}"

    return joined


def _format_comment(result: ExtractionResult) -> Optional[str]:
    """Build a comment string from evidence + source information."""
    values = result.get("values") or []
    if not values:
        return None

    lines = [f"Node: {result['node_path']}", f"Status: {result['status']}", ""]
    for i, v in enumerate(values, start=1):
        lines.append(f"Value {i}: {v.get('value', '')}")
        lines.append(f"  Source: {v.get('source', '')}")
        lines.append(f"  Evidence: {v.get('evidence', '')[:300]}")
        lines.append(f"  Confidence: {v.get('confidence', 0):.2f}")
        lines.append("")

    return "\n".join(lines)


def _backup_excel(excel_path: str) -> str:
    """Create a timestamped backup of the Excel file before writing."""
    src = Path(excel_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = src.with_name(f"{src.stem}_backup_{timestamp}{src.suffix}")
    shutil.copy2(src, dst)
    logger.info("[write_excel] Backup created: %s", dst)
    return str(dst)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def write_excel(
    state: PatentExtractionState,
    col_map: ExcelColumnMap,
    make_backup: bool = False,
) -> PatentExtractionState:
    """
    LangGraph node: write extractions and metadata to the Excel workbook.

    This function takes an extra argument (col_map) that is not part of
    the LangGraph state.  Use functools.partial when registering in the graph:

        graph.add_node("write_excel", partial(write_excel, col_map=col_map))

    Reads:   state["validated_extractions"]
             state["metadata"]
             state["excel_path"]
             state["excel_sheet"]
             state["excel_row"]
    Writes:  state["excel_written"]
    """
    excel_path  = state.get("excel_path", "")
    sheet_name  = state.get("excel_sheet", "")
    row_idx     = state.get("excel_row", 0)
    metadata    = state.get("metadata") or {}
    extractions = state.get("validated_extractions") or state.get("extractions") or []
    errors      = state.get("errors") or []
    patent_number = state.get("patent_number", "")

    if not excel_path or not sheet_name or not row_idx:
        logger.error("[write_excel] Missing excel_path / excel_sheet / excel_row in state")
        return {**state, "excel_written": False}

    logger.info("[write_excel] Writing row %d for %s", row_idx, patent_number)

    try:
        if make_backup:
            _backup_excel(excel_path)

        wb = openpyxl.load_workbook(excel_path)
        ws = wb[sheet_name]

        # ── Write metadata columns ─────────────────────────────────────────
        for col_label, col_idx in col_map.label_to_col.items():
            meta_key = _resolve_metadata_key(col_label)
            if meta_key and meta_key in metadata:
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.value = metadata[meta_key]

        # ── Write extraction results ───────────────────────────────────────
        node_id_to_result: dict[str, ExtractionResult] = {
            e["node_id"]: e for e in extractions
        }

        for node_id, col_idx in col_map.node_to_col.items():
            result = node_id_to_result.get(node_id)
            if result is None:
                continue   # Node wasn't in relevant set — leave cell as-is

            cell = ws.cell(row=row_idx, column=col_idx)
            cell_value = _format_cell_value(result)
            cell.value = cell_value

            # Add evidence as a cell comment
            comment_text = _format_comment(result)
            if comment_text:
                cell.comment = Comment(comment_text, "TaxonomyAgent")

        # ── Write error note if any ────────────────────────────────────────
        if errors and col_map.patent_number_col:
            pn_cell = ws.cell(row=row_idx, column=col_map.patent_number_col)
            error_note = "ERRORS:\n" + "\n".join(errors)
            pn_cell.comment = Comment(error_note, "TaxonomyAgent")

        wb.save(excel_path)
        logger.info("[write_excel] Saved: %s (row %d)", excel_path, row_idx)
        return {**state, "excel_written": True}

    except Exception as exc:
        msg = f"Excel write failed for {patent_number}: {exc}"
        logger.error("[write_excel] %s", msg)
        return {**state, "excel_written": False, "errors": errors + [msg]}
