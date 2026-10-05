"""
pipeline/utils/reasoning_loader.py

Parses the Human Reasoning Excel sheet and builds a per-patent,
per-leaf-column reasoning map.

Uses openpyxl only (already a project dependency — no pandas needed).

The Excel sheet structure (Human reasoning sheet):
    Row 1: empty / ignored
    Row 2: top-level group headers  (merged cells -> forward-filled)
            e.g. "Polymer Properties and Material Innovations"
    Row 3: mid-level group headers  (merged cells -> forward-filled)
            e.g. "Mechanical Properties", "Optical Properties"
    Row 4: leaf column names        (one per column, NOT forward-filled)
            e.g. "Tensile Strength", "Durability/Dart impact", "Density"
    Row 5+: patent data rows (S.No = 1, 2, 3 ...)
             followed immediately by a comment row (S.No = "Comment")

Note: openpyxl rows/cols are 1-indexed.
      Merged cells in openpyxl expose the value only on the top-left cell;
      all other cells in the merge return None. We forward-fill to simulate
      what pandas would do.

Output:
    {
      "EP3350236B1": {
        "Polymer Properties > Mechanical Properties > Tensile Strength":
            "The Tensile Strength value was mapped from Table 3 ...",
        "Physical Property > Density":
            "The Density value was mapped from the Claims itself ...",
      },
      "US10611867B2": { ... },
    }

Usage:
    from pipeline.utils.reasoning_loader import load_reasoning_map
    reasoning_map = load_reasoning_map("path/to/reasoning.xlsx",
                                       sheet="Human reasoning")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import openpyxl

logger = logging.getLogger(__name__)

# Type alias
ReasoningMap = Dict[str, Dict[str, str]]


def _clean(val) -> str | None:
    """Return stripped string or None for None/empty."""
    if val is None:
        return None
    v = str(val).strip()
    return None if v == "" else v


def _forward_fill(row_values: list) -> list:
    """
    Forward-fill None values — simulates pandas ffill for merged cells.
    openpyxl returns None for all cells in a merge except the top-left one.
    """
    filled, last = [], None
    for v in row_values:
        c = _clean(v)
        if c is not None:
            last = c
        filled.append(last)
    return filled


def _sheet_to_rows(ws) -> list[list]:
    """
    Read all cells from an openpyxl worksheet into a list-of-lists.
    Merged cell values are already resolved by openpyxl when
    read_only=False (default) — merged cells return the top-left value
    for the entire range when you access .value.

    We read .value for every cell so merged cells are correctly handled.
    """
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(list(row))
    return rows


def _find_header_start(rows: list[list]) -> int:
    """Find the row index (0-based) where the leaf headers exist. Hardcoded for Fresh_Test_Copy where leaf is row 3 (index 2)."""
    return 2

def _build_col_to_path(rows: list[list]) -> dict[int, str]:
    """
    Build column-index -> full hierarchical path string dynamically.
    """
    leaf_idx = _find_header_start(rows)
    if leaf_idx < 0 or len(rows) <= leaf_idx:
        return {}

    h1 = _forward_fill(rows[leaf_idx - 2]) if leaf_idx >= 2 else []
    h2 = _forward_fill(rows[leaf_idx - 1]) if leaf_idx >= 1 else []
    h3 = rows[leaf_idx]                      # leaf names

    col_to_path: dict[int, str] = {}
    for col_idx, leaf_raw in enumerate(h3):
        leaf = _clean(leaf_raw)
        if leaf is None:
            continue

        parts: list[str] = []
        top = h1[col_idx] if col_idx < len(h1) else None
        mid = h2[col_idx] if col_idx < len(h2) else None

        if top and top != leaf:
            parts.append(top)
        if mid and mid != top and mid != leaf:
            parts.append(mid)
        parts.append(leaf)

        col_to_path[col_idx] = " > ".join(parts)

    return col_to_path


def _find_patent_comment_pairs(rows: list[list]) -> list[tuple[str, int]]:
    """
    Scan rows starting after the leaf headers to find comment rows.
    col index 1 = S.No, col index 2 = Patent Number.
    """
    pairs: list[tuple[str, int]] = []
    last_patent: str | None = None
    
    leaf_idx = _find_header_start(rows)

    for row_idx, row in enumerate(rows[leaf_idx + 1:], start=leaf_idx + 1):
        # col 1 = S.No
        sno  = _clean(row[1]) if len(row) > 1 else None
        pnum = _clean(row[2]) if len(row) > 2 else None

        if sno and sno.lower() == "comment":
            if last_patent:
                pairs.append((last_patent, row_idx))
        elif sno and pnum:
            last_patent = pnum

    return pairs


def load_reasoning_map(
    excel_path: str | Path,
    sheet: str = "Human reasoning",
) -> ReasoningMap:
    """
    Parse the Human Reasoning Excel sheet and return:
        { patent_id: { column_path: reasoning_text } }

    Uses openpyxl (already a project dependency).

    Args:
        excel_path: Path to the Excel file.
        sheet:      Sheet name containing human reasoning rows.

    Returns:
        ReasoningMap -- empty dict if file/sheet not found or unreadable.
    """
    excel_path = Path(excel_path)

    if not excel_path.exists():
        logger.warning("[reasoning_loader] File not found: %s", excel_path)
        return {}

    try:
        wb = openpyxl.load_workbook(excel_path, read_only=False, data_only=True)
    except Exception as exc:
        logger.error("[reasoning_loader] Cannot open workbook: %s", exc)
        return {}

    if sheet not in wb.sheetnames:
        logger.warning(
            "[reasoning_loader] Sheet '%s' not in %s. Available: %s",
            sheet, excel_path.name, wb.sheetnames,
        )
        wb.close()
        return {}

    ws = wb[sheet]
    rows = _sheet_to_rows(ws)
    wb.close()

    if len(rows) < 6:
        logger.warning("[reasoning_loader] Sheet too small (%d rows)", len(rows))
        return {}

    # Build column -> path mapping
    col_to_path = _build_col_to_path(rows)
    logger.info(
        "[reasoning_loader] Column map built: %d leaf columns", len(col_to_path)
    )

    # Find (patent_id, comment_row_idx) pairs
    pairs = _find_patent_comment_pairs(rows)
    logger.info("[reasoning_loader] %d patents with comment rows found", len(pairs))

    # Build final reasoning map
    reasoning_map: ReasoningMap = {}
    for patent_id, comment_row_idx in pairs:
        reasoning_map[patent_id] = {}
        row = rows[comment_row_idx]

        for col_idx, col_path in col_to_path.items():
            val = _clean(row[col_idx]) if col_idx < len(row) else None
            if val and val.lower() not in ("comment", "nan"):
                reasoning_map[patent_id][col_path] = val

        logger.info(
            "[reasoning_loader]   %s -> %d column(s) with reasoning",
            patent_id, len(reasoning_map[patent_id]),
        )

    return reasoning_map
