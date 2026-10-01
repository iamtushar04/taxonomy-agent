"""
Excel ↔ Taxonomy mapper.

Responsibilities:
  1. Read the header row(s) of the target Excel sheet and map each column
     to a taxonomy node ID (by matching the column label to node names).
  2. Expose helpers to look up which column corresponds to a given node.
  3. Identify the "Patent Number" column so run.py can iterate rows.

The mapping is computed once at startup and shared across all patents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl

from pipeline.state import TaxonomyNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ExcelColumnMap:
    """
    Holds the bidirectional mapping between Excel columns and taxonomy nodes.
    """
    # column_index (1-based) → node_id
    col_to_node: dict[int, str] = field(default_factory=dict)

    # node_id → column_index (1-based)
    node_to_col: dict[str, int] = field(default_factory=dict)

    # column label (header text) → column_index
    label_to_col: dict[str, int] = field(default_factory=dict)

    # The 1-based column index that holds the patent number
    patent_number_col: Optional[int] = None

    # Last data row detected (exclusive upper bound)
    header_rows: list[int] = field(default_factory=list)

    def get_col_for_node(self, node_id: str) -> Optional[int]:
        return self.node_to_col.get(node_id)

    def get_node_for_col(self, col: int) -> Optional[str]:
        return self.col_to_node.get(col)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

# Known aliases for the Patent Number column
_PATENT_NUM_ALIASES = {
    "patent number", "patent no", "patent no.", "patent_number",
    "pub number", "publication number", "patent id",
}

# Known aliases for columns that should be skipped (not taxonomy leaf nodes)
_SKIP_ALIASES = {
    "s.no", "s. no", "sno", "serial", "serial no", "sr no",
}


def build_column_map(
    excel_path: str,
    sheet_name: str,
    taxonomy_nodes: list[TaxonomyNode],
    header_row: int = 1,
    scan_all_header_rows: bool = False,
) -> ExcelColumnMap:
    """
    Scan the header row(s) of the Excel sheet and map each column to a
    taxonomy node by matching the column label (case-insensitive) to
    node names and path segments.

    Args:
        excel_path:           Path to the workbook.
        sheet_name:           Sheet name.
        taxonomy_nodes:       Full flat list of taxonomy nodes.
        header_row:           The last header row number (1-based).
        scan_all_header_rows: If True, scan rows 1..header_row (handles
                              merged multi-row headers). Labels from all
                              rows are collected and used for matching.

    Returns:
        ExcelColumnMap with all mappings populated.
    """
    import sys
    from pathlib import Path as _Path
    _root = str(_Path(__file__).resolve().parents[2])
    if _root not in sys.path:
        sys.path.insert(0, _root)
    import get_graph as _gg

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]

    # Build a lookup: normalised node path -> node
    # and normalised leaf name -> node
    path_to_node: dict[str, TaxonomyNode] = {}
    name_to_node: dict[str, TaxonomyNode] = {}
    for node in taxonomy_nodes:
        name_to_node[node["name"].lower().strip()] = node
        last_segment = node["path"].split(">")[-1].strip().lower()
        name_to_node[last_segment] = node
        
        # Build normalized full path string
        norm_path = " > ".join(s.strip() for s in node["path"].split(">")).lower()
        path_to_node[norm_path] = node

    col_map = ExcelColumnMap()
    max_col = ws.max_column or 0

    # Determine which rows to scan
    rows_to_scan = list(range(1, header_row + 1)) if scan_all_header_rows else [header_row]
    col_map.header_rows = rows_to_scan

    # Build a per-column label by scanning all header rows.
    # We build the full path by joining all non-empty labels in the column.
    col_paths: dict[int, list[str]] = {}
    col_labels: dict[int, str] = {}
    for row_num in rows_to_scan:
        try:
            row_map = _gg.row_value_map(ws, row_num, max_col)
        except Exception:
            # Fallback: read raw cells
            row_map = {}
            for c in range(1, max_col + 1):
                v = ws.cell(row=row_num, column=c).value
                if v is not None:
                    row_map[c] = v

        for col_idx, val in row_map.items():
            label = str(val).strip()
            if label:
                if col_idx not in col_paths:
                    col_paths[col_idx] = []
                col_paths[col_idx].append(label)
                col_labels[col_idx] = label  # last non-empty wins

    for col_idx in range(1, max_col + 1):
        label = col_labels.get(col_idx, "")
        if not label:
            continue

        col_map.label_to_col[label] = col_idx
        lower_label = label.lower()
        full_col_path = " > ".join(col_paths.get(col_idx, [])).lower()

        # Check patent number column
        if lower_label in _PATENT_NUM_ALIASES:
            col_map.patent_number_col = col_idx
            logger.debug("Patent number column: %d ('%s')", col_idx, label)
            continue

        # Skip non-data columns
        if lower_label in _SKIP_ALIASES:
            continue

        # Match to taxonomy node (try full path first, then leaf)
        node = path_to_node.get(full_col_path) or name_to_node.get(lower_label)
        if node:
            col_map.col_to_node[col_idx] = node["node_id"]
            col_map.node_to_col[node["node_id"]] = col_idx
            logger.debug(
                "Mapped col %d ('%s') -> node '%s'", col_idx, label, node["path"]
            )
        else:
            logger.debug("Col %d ('%s') has no matching taxonomy node", col_idx, label)

    if col_map.patent_number_col is None:
        logger.warning(
            "Could not find a 'Patent Number' column in sheet '%s'. "
            "Checked aliases: %s",
            sheet_name,
            _PATENT_NUM_ALIASES,
        )

    logger.info(
        "Column map: %d taxonomy columns mapped, patent_number_col=%s",
        len(col_map.col_to_node),
        col_map.patent_number_col,
    )
    wb.close()
    return col_map


# ---------------------------------------------------------------------------
# Row reader
# ---------------------------------------------------------------------------

def read_patent_numbers(
    excel_path: str,
    sheet_name: str,
    col_map: ExcelColumnMap,
    start_row: int = 2,
) -> list[tuple[int, str]]:
    """
    Return a list of (row_index, patent_number) tuples for every non-empty
    row in the patent number column.

    Args:
        excel_path:  Path to workbook.
        sheet_name:  Sheet name.
        col_map:     ExcelColumnMap produced by build_column_map().
        start_row:   First data row (1-based). Default 2 skips header.

    Returns:
        List of (row, patent_number) tuples, in sheet order.
    """
    if col_map.patent_number_col is None:
        raise ValueError(
            "Patent number column not found. Check column header aliases."
        )

    wb = openpyxl.load_workbook(excel_path, data_only=True, read_only=True)
    ws = wb[sheet_name]
    results: list[tuple[int, str]] = []

    for row_idx in range(start_row, (ws.max_row or 0) + 1):
        cell = ws.cell(row=row_idx, column=col_map.patent_number_col)
        value = cell.value
        if value is not None and str(value).strip():
            results.append((row_idx, str(value).strip()))

    wb.close()
    logger.info("Found %d patent numbers in '%s'", len(results), sheet_name)
    return results
