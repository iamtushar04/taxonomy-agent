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


def _append(patent_number: str, text: str) -> None:
    """Append text to the trace file."""
    trace_file = _LOGS_DIR / f"{patent_number}_trace.md"
    with trace_file.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


def log_node_event(patent_number: str, node_name: str, state: PatentExtractionState) -> None:
    """
    Called after every LangGraph node completes. 
    Writes a customized summary based on which node just ran.
    """
    _append(patent_number, f"## Node: `{node_name}`\n")

    if state.get("errors"):
        _append(patent_number, "> [!WARNING]\n> Pipeline reported errors:\n")
        for err in state["errors"]:
            _append(patent_number, f"> - {err}")
        _append(patent_number, "")

    if node_name == "fetch_patent":
        raw = state.get("raw_api_response") or {}
        title = raw.get("title", "(No title)")
        _append(patent_number, f"**API Fetch Successful.**\n")
        _append(patent_number, f"- **Title:** {title}")
        _append(patent_number, f"- **Raw JSON Keys:** {', '.join(raw.keys())}\n")

    elif node_name == "parse_content":
        chunks = state.get("patent_chunks") or []
        metadata = state.get("metadata") or {}
        _append(patent_number, f"**Metadata Extracted:** {len(metadata)} fields.")
        _append(patent_number, f"**Chunks Generated:** {len(chunks)} chunks\n")
        
        # Group chunks by section
        section_counts: dict[str, int] = {}
        for c in chunks:
            section_counts[c["section"]] = section_counts.get(c["section"], 0) + 1
            
        _append(patent_number, "### Chunk Breakdown")
        for sec, count in section_counts.items():
            _append(patent_number, f"- **{sec}**: {count}")
        _append(patent_number, "")
        
        _append(patent_number, "<details>\n<summary><b>View Parsed Text Chunks (Preview)</b></summary>\n")
        for i, c in enumerate(chunks, 1):
            # Show the first 300 chars of each chunk so the file doesn't become too massive to open
            snippet = c['text'].replace('\n', ' ')[:300]
            _append(patent_number, f"- **Chunk {i} [{c['section']}]**: {snippet}...")
        _append(patent_number, "</details>\n")

    elif node_name == "describe_nodes":
        nodes = state.get("taxonomy_nodes") or []
        _append(patent_number, f"Processed {len(nodes)} total taxonomy nodes. Descriptions loaded/generated from LLM.\n")
        
        _append(patent_number, "<details>\n<summary><b>View Generated Node Descriptions</b></summary>\n")
        for n in nodes:
            desc = n.get("description", "(No description)")
            _append(patent_number, f"- **{n['name']}**: {desc}")
        _append(patent_number, "</details>\n")

    elif node_name == "match_relevance":
        relevant = state.get("relevant_nodes") or []
        all_nodes = state.get("taxonomy_nodes") or []
        relevant_ids = {n["node_id"] for n in relevant}
        
        _append(patent_number, f"Filtered taxonomy from **{len(all_nodes)}** nodes down to **{len(relevant)}** relevant nodes for this patent.\n")
        
        _append(patent_number, "<details>\n<summary><b>View Relevant Nodes</b></summary>\n")
        for n in relevant:
            _append(patent_number, f"- ✅ {n['path']}")
        _append(patent_number, "</details>\n")
        
        _append(patent_number, "<details>\n<summary><b>View Rejected Nodes</b></summary>\n")
        for n in all_nodes:
            if n["node_id"] not in relevant_ids:
                _append(patent_number, f"- ❌ {n['path']}")
        _append(patent_number, "</details>\n")

    elif node_name == "extract_values":
        extractions = state.get("extractions") or []
        found = sum(1 for e in extractions if e["status"] == "FOUND")
        not_found = sum(1 for e in extractions if e["status"] == "NOT_FOUND")
        uncertain = sum(1 for e in extractions if e["status"] == "UNCERTAIN")
        
        _append(patent_number, f"**Extraction Results:** {found} FOUND, {not_found} NOT_FOUND, {uncertain} UNCERTAIN.\n")
        
        for ext in extractions:
            if ext["status"] == "NOT_FOUND":
                continue
                
            _append(patent_number, f"### `{ext['node_name']}`")
            _append(patent_number, f"**Status:** {ext['status']}")
            for i, val in enumerate(ext.get("values") or [], 1):
                _append(patent_number, f"- **Value {i}:** {val['value']}")
                _append(patent_number, f"  - **Source:** {val['source']}")
                _append(patent_number, f"  - **Confidence:** {val['confidence']}")
                _append(patent_number, f"  - **Evidence:** > {val['evidence']}")
            _append(patent_number, "")

    elif node_name == "validate":
        extractions = state.get("validated_extractions") or []
        _append(patent_number, "Evidence strings fuzz-matched against original text. Low confidence/hallucinated evidence downgraded to UNCERTAIN.\n")
        
        uncertain = [e for e in extractions if e["status"] == "UNCERTAIN"]
        if uncertain:
            _append(patent_number, "#### Nodes downgraded to UNCERTAIN during validation:")
            for e in uncertain:
                _append(patent_number, f"- `{e['node_name']}`")
        else:
            _append(patent_number, "All FOUND extractions passed validation.")
        _append(patent_number, "")

    elif node_name == "write_excel":
        if state.get("excel_written"):
            _append(patent_number, f"✅ Data successfully written to **{state['excel_sheet']}** at row **{state['excel_row']}** in `{state['excel_path']}`.")
        else:
            _append(patent_number, "❌ Failed to write to Excel.")
        _append(patent_number, "")

    _append(patent_number, "---\n")
