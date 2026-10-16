"""
Deep Trace Logger for Patent Extraction Pipeline.

Writes a human-readable Markdown log for each patent processed,
detailing exactly what happens at every node in the graph.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pipeline.state import PatentExtractionState

logger = logging.getLogger(__name__)

# Resolve logs directory relative to project root
_LOGS_DIR = Path(__file__).resolve().parents[2] / "logs" / "traces"


def init_trace(patent_number: str) -> None:
    """Initialize a fresh markdown trace file for a patent."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    trace_file = _LOGS_DIR / f"{patent_number}_trace.md"
    
    with trace_file.open("w", encoding="utf-8") as f:
        f.write(f"# Pipeline Trace: {patent_number}\n\n")
        f.write("This file contains a deep trace of the LangGraph pipeline execution, node by node.\n\n")
        f.write("---\n\n")
    
    logger.debug("[tracer] Initialized trace file: %s", trace_file)


def _append(patent_number: str, text: str, run_id: str | None = None) -> None:
    """Append text to the trace file in logs/traces/ and optionally in logs/taxonomy_builder/<run_id>/."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    trace_file = _LOGS_DIR / f"{patent_number}_trace.md"
    try:
        with trace_file.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        logger.warning(f"Could not write trace to {trace_file}: {e}")

    if run_id:
        try:
            tb_dir = Path(__file__).resolve().parents[2] / "logs" / "taxonomy_builder" / str(run_id)
            if tb_dir.exists():
                safe_pid = str(patent_number).replace("/", "_").replace("\\", "_")
                tb_file = tb_dir / f"{safe_pid}_trace.md"
                with tb_file.open("a", encoding="utf-8") as f:
                    f.write(text + "\n")
        except Exception as e:
            logger.warning(f"Could not append trace to taxonomy_builder run {run_id}: {e}")


def log_node_event(patent_number: str, node_name: str, state: PatentExtractionState, run_id: str | None = None) -> None:
    """
    Called after every LangGraph node completes. 
    Writes a customized summary based on which node just ran.
    """
    def write_line(text: str):
        _append(patent_number, text, run_id=run_id)

    write_line(f"## Pipeline Node: `{node_name}`\n")

    if state.get("errors"):
        write_line("> [!WARNING]\n> Pipeline reported errors:\n")
        for err in state["errors"]:
            write_line(f"> - {err}")
        write_line("")

    if node_name == "fetch_patent":
        raw = state.get("raw_api_response") or {}
        title = raw.get("title", "(No title)")
        write_line(f"**API Fetch Successful.**\n")
        write_line(f"- **Title:** {title}")
        write_line(f"- **Raw JSON Keys:** {', '.join(raw.keys())}\n")

    elif node_name == "parse_content":
        chunks = state.get("patent_chunks") or []
        metadata = state.get("metadata") or {}
        write_line(f"**Metadata Extracted:** {len(metadata)} fields.")
        write_line(f"**Chunks Generated:** {len(chunks)} chunks\n")
        
        # Group chunks by section
        section_counts: dict[str, int] = {}
        for c in chunks:
            section_counts[c["section"]] = section_counts.get(c["section"], 0) + 1
            
        write_line("### Chunk Breakdown")
        for sec, count in section_counts.items():
            write_line(f"- **{sec}**: {count}")
        write_line("")
        
        write_line("<details>\n<summary><b>View Parsed Text Chunks (Preview)</b></summary>\n")
        for i, c in enumerate(chunks, 1):
            snippet = c['text'].replace('\n', ' ')[:300]
            write_line(f"- **Chunk {i} [{c['section']}]**: {snippet}...")
        write_line("</details>\n")

    elif node_name == "describe_nodes":
        nodes = state.get("taxonomy_nodes") or []
        write_line(f"Processed {len(nodes)} total taxonomy nodes. Descriptions loaded/generated from LLM.\n")
        
        write_line("<details>\n<summary><b>View Generated Node Descriptions</b></summary>\n")
        for n in nodes:
            desc = n.get("description", "(No description)")
            write_line(f"- **{n['name']}**: {desc}")
        write_line("</details>\n")

    elif node_name == "match_relevance":
        relevant = state.get("relevant_nodes") or []
        all_nodes = state.get("taxonomy_nodes") or []
        relevant_ids = {n["node_id"] for n in relevant}
        
        write_line(f"Filtered taxonomy from **{len(all_nodes)}** nodes down to **{len(relevant)}** relevant nodes for this patent.\n")
        
        write_line("<details>\n<summary><b>View Relevant Nodes</b></summary>\n")
        for n in relevant:
            write_line(f"- ✅ {n['path']}")
        write_line("</details>\n")
        
        write_line("<details>\n<summary><b>View Rejected Nodes</b></summary>\n")
        for n in all_nodes:
            if n["node_id"] not in relevant_ids:
                write_line(f"- ❌ {n['path']}")
        write_line("</details>\n")

    elif node_name == "extract_values":
        extractions = state.get("extractions") or []
        found = sum(1 for e in extractions if e["status"] == "FOUND")
        not_found = sum(1 for e in extractions if e["status"] == "NOT_FOUND")
        uncertain = sum(1 for e in extractions if e["status"] == "UNCERTAIN")
        
        write_line(f"**Extraction Results:** {found} FOUND, {not_found} NOT_FOUND, {uncertain} UNCERTAIN.\n")
        
        for ext in extractions:
            if ext["status"] == "NOT_FOUND":
                continue
                
            write_line(f"### `{ext['node_name']}`")
            write_line(f"**Status:** {ext['status']}")
            for i, val in enumerate(ext.get("values") or [], 1):
                write_line(f"- **Value {i}:** {val['value']}")
                write_line(f"  - **Source:** {val['source']}")
                write_line(f"  - **Confidence:** {val['confidence']}")
                write_line(f"  - **Evidence:** > {val['evidence']}")
            write_line("")

    elif node_name == "validate":
        extractions = state.get("validated_extractions") or []
        write_line("Evidence strings fuzz-matched against original text. Low confidence/hallucinated evidence downgraded to UNCERTAIN.\n")
        
        uncertain = [e for e in extractions if e["status"] == "UNCERTAIN"]
        if uncertain:
            write_line("#### Nodes downgraded to UNCERTAIN during validation:")
            for e in uncertain:
                write_line(f"- `{e['node_name']}`")
        else:
            write_line("All FOUND extractions passed validation.")
        write_line("")

    elif node_name == "write_excel":
        if state.get("excel_written"):
            write_line(f"✅ Data successfully written to **{state['excel_sheet']}** at row **{state['excel_row']}** in `{state['excel_path']}`.")
        else:
            write_line("❌ Failed to write to Excel.")
        write_line("")

    write_line("---\n")
