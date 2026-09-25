"""
run.py — Entry point for the Patent Taxonomy Extraction pipeline.

Usage:
    # Process all patents in the Excel file
    uv run python run.py --excel "data/Wissen Research_Metallocene PE_Reasoning.xlsx" --sheet "Sheet1"

    # Process only specific rows (1-indexed, inclusive)
    uv run python run.py --excel data/Wissen.xlsx --sheet Sheet1 --rows 2 5 10

    # Process a single patent number directly (writes to first empty row)
    uv run python run.py --patent US7504937B2 --excel data/Wissen.xlsx --sheet Sheet1

    # Dry-run: fetch + parse only, no extraction or Excel writes
    uv run python run.py --excel data/Wissen.xlsx --sheet Sheet1 --dry-run

    # Use a plain-text taxonomy instead of Excel headers
    uv run python run.py --excel data/out.xlsx --sheet Sheet1 --taxonomy data/Wissen.txt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging setup — do this before importing pipeline modules
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("run")


# ---------------------------------------------------------------------------
# Pipeline imports
# ---------------------------------------------------------------------------
from pipeline.graph import build_graph
from pipeline.state import PatentExtractionState
from pipeline.utils.excel_mapper import build_column_map, read_patent_numbers
from pipeline.utils.taxonomy_loader import (
    get_leaf_nodes,
    parse_excel_taxonomy,
    parse_text_taxonomy,
)
from pipeline.utils import tracer
from langfuse import observe


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patent Taxonomy Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--excel", required=True,
        help="Path to the target Excel workbook (input & output).",
    )
    parser.add_argument(
        "--sheet", default="Sheet1",
        help="Sheet name in the Excel workbook (default: Sheet1).",
    )
    parser.add_argument(
        "--header-row", type=int, default=1,
        help="Row number (1-based) of the bottom-most header row (default: 1).",
    )
    parser.add_argument(
        "--taxonomy", default=None,
        help=(
            "Optional path to a plain-text taxonomy file (Wissen.txt format). "
            "If omitted, the taxonomy is inferred from the Excel column headers."
        ),
    )
    parser.add_argument(
        "--rows", nargs="+", type=int, default=None,
        help="Only process these specific data row numbers (1-based).",
    )
    parser.add_argument(
        "--patent", default=None,
        help="Process a single patent number directly (bypasses Excel row scan).",
    )
    parser.add_argument(
        "--start-row", type=int, default=2,
        help="First data row when scanning the sheet (default: 2, skips header).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch + parse only. No LLM calls, no Excel writes.",
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Create a timestamped backup of the Excel file before writing.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    excel_path = str(Path(args.excel).resolve())
    sheet_name = args.sheet

    logger.info("=" * 60)
    logger.info("Patent Taxonomy Extraction Pipeline")
    logger.info("Excel:  %s", excel_path)
    logger.info("Sheet:  %s", sheet_name)
    if args.dry_run:
        logger.info("MODE:   DRY RUN (no extraction, no writes)")
    logger.info("=" * 60)

    # ── 1. Load taxonomy ───────────────────────────────────────────────────
    if args.taxonomy:
        logger.info("Loading taxonomy from text file: %s", args.taxonomy)
        with open(args.taxonomy, encoding="utf-8") as f:
            taxonomy_text = f.read()
        all_nodes = parse_text_taxonomy(taxonomy_text)
    else:
        logger.info("Inferring taxonomy from Excel column headers")
        all_nodes = parse_excel_taxonomy(excel_path, sheet_name)

    leaf_nodes = get_leaf_nodes(all_nodes)
    logger.info(
        "Taxonomy: %d total nodes, %d leaf nodes",
        len(all_nodes), len(leaf_nodes),
    )

    # ── 2. Build column map ────────────────────────────────────────────────
    col_map = build_column_map(
        excel_path, sheet_name, all_nodes,
        header_row=args.header_row,
        scan_all_header_rows=True,
    )

    # ── 3. Determine patents to process ───────────────────────────────────
    if args.patent:
        # Single patent mode — find the right row or use first empty data row
        patents_to_process: list[tuple[int, str]] = [(args.start_row, args.patent)]
    else:
        all_patents = read_patent_numbers(
            excel_path, sheet_name, col_map, start_row=args.start_row
        )
        if args.rows:
            patents_to_process = [(r, p) for r, p in all_patents if r in args.rows]
        else:
            patents_to_process = all_patents

    logger.info("Patents to process: %d", len(patents_to_process))

    if not patents_to_process:
        logger.warning("No patents found to process. Exiting.")
        return

    # ── 4. Build LangGraph ─────────────────────────────────────────────────
    if not args.dry_run:
        app = build_graph(col_map)

    # ── 5. Run pipeline for each patent ───────────────────────────────────
    success = 0
    failed = 0
    for row_idx, patent_number in patents_to_process:
        logger.info("-" * 50)
        logger.info("Processing: %s (row %d)", patent_number, row_idx)

        initial_state: PatentExtractionState = {
            "patent_number":   patent_number,
            "taxonomy_nodes":  leaf_nodes,
            "excel_path":      excel_path,
            "excel_sheet":     sheet_name,
            "excel_row":       row_idx,
            "errors":          [],
        }

        if args.dry_run:
            from pipeline.nodes.fetch_patent import fetch_patent
            from pipeline.nodes.parse_content import parse_content
            state = fetch_patent(initial_state)
            if not state.get("errors"):
                state = parse_content(state)
                chunks = state.get("patent_chunks") or []
                meta   = state.get("metadata") or {}
                logger.info(
                    "  [DRY RUN] %s | chunks=%d | title=%s",
                    patent_number, len(chunks), meta.get("title", "?")[:60],
                )
            else:
                logger.error("  [DRY RUN] Fetch failed: %s", state["errors"])
            continue

        is_success = _process_single_patent(app, initial_state, patent_number, row_idx)
        if is_success:
            success += 1
        else:
            failed += 1

    # ── 6. Summary ────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("DONE — Success: %d | Failed: %d | Total: %d",
                success, failed, len(patents_to_process))
    logger.info("Output: %s", excel_path)

@observe(name="Extract_Patent_Data")
def _process_single_patent(app, initial_state, patent_number: str, row_idx: int) -> bool:
    try:
        from pipeline.utils import tracer
        tracer.init_trace(patent_number)
        
        final_state = None
        for event in app.stream(initial_state):
            for node_name, node_state in event.items():
                tracer.log_node_event(patent_number, node_name, node_state)
                final_state = node_state
        
        if final_state and final_state.get("errors"):
            logger.warning("Completed with errors: %s", final_state["errors"])
            return False
        else:
            logger.info("✓ %s — written to row %d", patent_number, row_idx)
            return True
    except Exception as exc:
        logger.error("FATAL for %s: %s", patent_number, exc, exc_info=True)
        return False
    logger.info("Log:    pipeline.log")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
