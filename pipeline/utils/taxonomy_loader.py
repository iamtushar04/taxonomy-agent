"""
Taxonomy loader.

Wraps get_graph.py (which understands multi-level merged Excel headers)
and converts the nested tree into a flat list of TaxonomyNode dicts
that the pipeline can work with directly.

Supports two taxonomy sources:
  1. Excel file  → parse_excel_taxonomy()
  2. Plain text  → parse_text_taxonomy()  (indented, e.g. Wissen.txt format)

Both return the same flat list of TaxonomyNode TypedDicts.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional

# Make sure get_graph.py (project root) is importable
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import get_graph  # noqa: E402  (project-level module)

from pipeline.state import TaxonomyNode
from pipeline.utils.node_rules import get_rules_for_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_id(path: str) -> str:
    """Stable, short node ID derived from the full hierarchy path."""
    return hashlib.md5(path.encode()).hexdigest()[:12]


def _flatten_tree(
    tree: dict,
    parent_path: str = "",
    parent_id: Optional[str] = None,
    level: int = 0,
    result: Optional[list] = None,
) -> list[TaxonomyNode]:
    """
    Recursively walk the nested dict produced by get_graph.to_nested_tree()
    and emit one TaxonomyNode per leaf (and per intermediate node that has
    leaf siblings — i.e. nodes that are themselves extraction targets).
    """
    if result is None:
        result = []

    for key, value in tree.items():
        if key == "__leaves__":
            # Each leaf becomes its own TaxonomyNode
            for leaf in value:
                path = f"{parent_path} > {leaf}" if parent_path else leaf
                node: TaxonomyNode = {
                    "node_id": _node_id(path),
                    "name": str(leaf),
                    "parent_id": parent_id,
                    "level": level,
                    "path": path,
                    "description": "",        # filled by describe_nodes node
                    "rules": get_rules_for_node(str(leaf)),
                }
                result.append(node)
        else:
            # Intermediate node
            path = f"{parent_path} > {key}" if parent_path else key
            node_id = _node_id(path)
            intermediate: TaxonomyNode = {
                "node_id": node_id,
                "name": str(key),
                "parent_id": parent_id,
                "level": level,
                "path": path,
                "description": "",
                "rules": get_rules_for_node(str(key)),
            }
            result.append(intermediate)
            _flatten_tree(value, path, node_id, level + 1, result)

    return result


# ---------------------------------------------------------------------------
# Public API — Excel source
# ---------------------------------------------------------------------------

def parse_excel_taxonomy(
    file_path: str,
    sheet_name: str,
    header_rows: Optional[list[int]] = None,
    start_col: Optional[int] = None,
    scan_rows: int = 30,
) -> list[TaxonomyNode]:
    """
    Extract the taxonomy from an Excel file using get_graph.py logic.

    Args:
        file_path:   Path to the .xlsx workbook.
        sheet_name:  Sheet that contains the multi-level header.
        header_rows: Override auto-detected header row numbers (1-indexed).
        start_col:   Override auto-detected first data column (1-indexed).
        scan_rows:   How many rows to scan when auto-detecting (default 30).

    Returns:
        Flat list of TaxonomyNode dicts, leaves + intermediates.
    """
    import openpyxl

    wb = openpyxl.load_workbook(file_path, data_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(
            f"Sheet '{sheet_name}' not found. Available: {wb.sheetnames}"
        )
    ws = wb[sheet_name]

    if header_rows and start_col:
        h_rows, s_col = header_rows, start_col
    else:
        detected = get_graph.detect_header_block(ws, scan_rows)
        if detected is None:
            raise RuntimeError(
                f"Could not auto-detect header block in sheet '{sheet_name}'. "
                "Pass header_rows and start_col explicitly."
            )
        h_rows = header_rows or detected["rows"]
        s_col = start_col or detected["start_col"]
        logger.info("Auto-detected header rows=%s start_col=%s", h_rows, s_col)

    columns = get_graph.build_taxonomy(ws, h_rows, s_col)
    tree = get_graph.to_nested_tree(columns)
    nodes = _flatten_tree(tree)
    logger.info("Loaded %d taxonomy nodes from Excel '%s'", len(nodes), file_path)
    return nodes


# ---------------------------------------------------------------------------
# Public API — Plain text source (Wissen.txt style)
# ---------------------------------------------------------------------------

def parse_text_taxonomy(text: str) -> list[TaxonomyNode]:
    """
    Parse an indented plain-text taxonomy.

    Supported format (from Wissen.txt / user paste):
        Level0 header
          Level1 header
            - Leaf node
            - Another leaf

    Lines starting with '-' after stripping are leaf nodes.
    Indentation depth (spaces or tabs) determines the level.

    Returns:
        Flat list of TaxonomyNode dicts.
    """
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    stack: list[tuple[int, str, str]] = []   # (indent, name, node_id)
    result: list[TaxonomyNode] = []

    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    for raw_line in lines:
        indent = _indent(raw_line)
        name = raw_line.strip().lstrip("- ").strip()
        if not name:
            continue

        # Trim stack to current depth
        while stack and stack[-1][0] >= indent:
            stack.pop()

        parent_id = stack[-1][2] if stack else None
        parent_path = stack[-1][1] if stack else ""
        path = f"{parent_path} > {name}" if parent_path else name
        node_id = _node_id(path)

        node: TaxonomyNode = {
            "node_id": node_id,
            "name": name,
            "parent_id": parent_id,
            "level": len(stack),
            "path": path,
            "description": "",
            "rules": get_rules_for_node(name),
        }
        result.append(node)
        stack.append((indent, path, node_id))

    logger.info("Parsed %d taxonomy nodes from text", len(result))
    return result


# ---------------------------------------------------------------------------
# Utility — get only leaf nodes (nodes with no children)
# ---------------------------------------------------------------------------

def get_leaf_nodes(nodes: list[TaxonomyNode]) -> list[TaxonomyNode]:
    """Return only the leaf nodes — those with no children."""
    parent_ids = {n["parent_id"] for n in nodes if n["parent_id"]}
    return [n for n in nodes if n["node_id"] not in parent_ids]
