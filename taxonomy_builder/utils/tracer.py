"""
Deep Trace Logger for Taxonomy Builder Pipeline.
Writes human-readable Markdown logs detailing what happens at every node.
Creates a specific folder for each run and saves a log per patent.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from taxonomy_builder.state import TaxonomyGenerationState

logger = logging.getLogger(__name__)

# Resolve logs directory relative to project root
_BASE_LOGS_DIR = Path(__file__).resolve().parents[2] / "logs" / "taxonomy_builder"


def init_trace(run_id: str, patent_ids: list[str]) -> None:
    """Initialize fresh markdown trace files for a taxonomy run."""
    run_dir = _BASE_LOGS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Init global trace for the overall batch steps (Grouping, Hierarchy, etc.)
    global_file = run_dir / "global_trace.md"
    with global_file.open("w", encoding="utf-8") as f:
        f.write(f"# Taxonomy Builder Global Trace: {run_id}\n\n")
        f.write("This file contains the batch-level operations (Grouping, Hierarchy building, etc.)\n\n")
        f.write("---\n\n")
        
    # Init individual traces for each patent (Fetching, Concept Extraction)
    for pid in patent_ids:
        safe_pid = pid.replace("/", "_").replace("\\", "_")
        p_file = run_dir / f"{safe_pid}_trace.md"
        with p_file.open("w", encoding="utf-8") as f:
            f.write(f"# Taxonomy Builder Trace for Patent: {pid}\n\n")
            f.write("This file contains operations specific to this patent (Fetching, Concept Extraction).\n\n")
            f.write("---\n\n")
    
    logger.debug("[tracer] Initialized trace directory: %s", run_dir)


def _append(run_id: str, filename: str, text: str) -> None:
    """Append text to a specific trace file in the run directory."""
    filepath = _BASE_LOGS_DIR / run_id / filename
    if filepath.exists():
        with filepath.open("a", encoding="utf-8") as f:
            f.write(text + "\n")


def log_node_event(run_id: str, node_name: str, state: TaxonomyGenerationState, output_data: dict = None) -> None:
    """
    Called after a node completes. 
    Routes the log to either the global trace or the specific patent trace.
    """
    if state.get("errors"):
        _append(run_id, "global_trace.md", "> [!WARNING]\n> Pipeline reported errors:\n")
        for err in state["errors"]:
            _append(run_id, "global_trace.md", f"> - {err}")
        _append(run_id, "global_trace.md", "")

    # ── Map Nodes (Run per patent or handle specific patents) ──
    
    if node_name == "fetch_patents":
        patents = output_data.get("patents_data", {})
        _append(run_id, "global_trace.md", f"## Node: `{node_name}`\n**Fetched {len(patents)} patents.**\n---\n")
        
        for pid, data in patents.items():
            safe_pid = pid.replace("/", "_").replace("\\", "_")
            _append(run_id, f"{safe_pid}_trace.md", f"## Node: `fetch_patents`\n")
            _append(run_id, f"{safe_pid}_trace.md", f"**Title:** {data.get('title', 'No Title')}")
            _append(run_id, f"{safe_pid}_trace.md", f"**Extracted Text Length:** {len(data.get('full_text', ''))} characters\n---\n")

    elif node_name == "extract_concepts":
        concepts = output_data.get("all_concepts", [])
        if not concepts:
            return
            
        pid = concepts[0].patent_id
        safe_pid = pid.replace("/", "_").replace("\\", "_")
        _append(run_id, f"{safe_pid}_trace.md", f"## Node: `extract_concepts`\n")
        _append(run_id, f"{safe_pid}_trace.md", f"**Concepts Extracted:** {len(concepts)} hyper-granular concepts returned from LLM.\n")
        _append(run_id, f"{safe_pid}_trace.md", "<details>\n<summary><b>View Extracted Concepts (Input -> Output)</b></summary>\n")
        for c in concepts:
            _append(run_id, f"{safe_pid}_trace.md", f"- **{c.name}**: {c.context}")
        _append(run_id, f"{safe_pid}_trace.md", "</details>\n---\n")

    # ── Reduce Nodes (Run globally across all patents) ──
    
    elif node_name == "deduplicate_concepts":
        _append(run_id, "global_trace.md", f"## Node: `{node_name}`\n")
        canonical_concepts = output_data.get("canonical_concepts", [])
        _append(run_id, "global_trace.md", f"**Deduplication (Embeddings):** Reduced raw concepts to **{len(canonical_concepts)}** Canonical Concepts.\n")
        _append(run_id, "global_trace.md", "<details>\n<summary><b>View Canonical Concepts</b></summary>\n")
        for cc in canonical_concepts:
            _append(run_id, "global_trace.md", f"- **{cc.name}** (from {len(cc.supporting_patent_ids)} patents)")
        _append(run_id, "global_trace.md", "</details>\n---\n")

    elif node_name == "group_concepts":
        _append(run_id, "global_trace.md", f"## Node: `{node_name}`\n")
        groups = output_data.get("concept_groups", {})
        _append(run_id, "global_trace.md", f"**Semantic Clustering:** LLM grouped raw concepts into **{len(groups)}** unified categories.\n")
        _append(run_id, "global_trace.md", "<details>\n<summary><b>View Clustered Groups & Reasoning</b></summary>\n")
        for g_name, items in groups.items():
            _append(run_id, "global_trace.md", f"- **Group: {g_name}**")
            # De-duplicate concept names for cleaner logging
            unique_names = set(item.name for item in items)
            for name in unique_names:
                _append(run_id, "global_trace.md", f"  - Included concept: {name}")
        _append(run_id, "global_trace.md", "</details>\n---\n")

    elif node_name == "build_hierarchy":
        _append(run_id, "global_trace.md", f"## Node: `{node_name}`\n")
        draft_tree = output_data.get("draft_tree", {})
        _append(run_id, "global_trace.md", "**Hierarchy Generation:** LLM constructed the following 3-level tree structure from the groups.\n")
        _append(run_id, "global_trace.md", "```json\n" + json.dumps(draft_tree, indent=2) + "\n```\n---\n")

    elif node_name == "enrich_nodes":
        _append(run_id, "global_trace.md", f"## Node: `{node_name}`\n")
        final_taxonomy = output_data.get("final_taxonomy", [])
        _append(run_id, "global_trace.md", f"**Tree Flattening & Enrichment:** Generated **{len(final_taxonomy)}** final nodes.\n")
        _append(run_id, "global_trace.md", "Attached source patent IDs to leaf nodes and generated descriptions.\n")
        _append(run_id, "global_trace.md", "<details>\n<summary><b>View Node Descriptions</b></summary>\n")
        for node in final_taxonomy:
            _append(run_id, "global_trace.md", f"- **{node['name']}** (Level {node['level']}): {node['description']}")
            _append(run_id, "global_trace.md", f"  - *Supported by {len(node['supporting_patent_ids'])} patents*")
        _append(run_id, "global_trace.md", "</details>\n---\n")

    elif node_name == "format_taxonomy":
        _append(run_id, "global_trace.md", f"## Node: `{node_name}`\n")
        _append(run_id, "global_trace.md", "✅ Exported `draft_taxonomy.json` and generated multi-level template `taxonomy_template.xlsx`.\n---\n")
