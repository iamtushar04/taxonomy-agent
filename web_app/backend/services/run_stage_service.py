"""
Service to track and provide real-time pipeline execution stages
(e.g., Fetching, Extracting, Building, AI Auditor Verifying, Finalizing)
for frontend UI status polling.
"""

from typing import Dict, Any

_RUN_STAGES: Dict[str, Dict[str, Any]] = {}

STAGE_DEFINITIONS = {
    "fetching": {
        "stage": "fetching",
        "title": "Fetching Patents & Products",
        "description": "Gathering claim texts, abstracts, and commercial technical specifications...",
        "step": 1,
        "total_steps": 5
    },
    "extracting": {
        "stage": "extracting",
        "title": "Extracting Technical Parameters",
        "description": "Extracting granular engineering parameters and technical domain pathways...",
        "step": 2,
        "total_steps": 5
    },
    "building_hierarchy": {
        "stage": "building_hierarchy",
        "title": "Constructing Taxonomy Hierarchy",
        "description": "Synthesizing canonical technology pillars and clustering concept branches...",
        "step": 3,
        "total_steps": 5
    },
    "auditing_hierarchy": {
        "stage": "auditing_hierarchy",
        "title": "AI Auditor Verifying Graph",
        "description": "AI Auditor is analyzing root, parent, and leaf nodes to fix misplacements and prune duplicates...",
        "step": 4,
        "total_steps": 5
    },
    "finalizing": {
        "stage": "finalizing",
        "title": "Finalizing Taxonomy Graph & Matrix",
        "description": "Computing ReactFlow layout and mapping commercial product claims...",
        "step": 5,
        "total_steps": 5
    }
}


def set_run_stage(run_id: str, stage_key: str, custom_desc: str = None) -> None:
    """Updates the active stage for a running pipeline."""
    base = STAGE_DEFINITIONS.get(stage_key, {
        "stage": stage_key,
        "title": stage_key.replace("_", " ").title(),
        "description": "Processing taxonomy pipeline...",
        "step": 3,
        "total_steps": 5
    })
    
    stage_data = dict(base)
    if custom_desc:
        stage_data["description"] = custom_desc

    _RUN_STAGES[run_id] = stage_data


def get_run_stage(run_id: str) -> Dict[str, Any]:
    """Retrieves the current execution stage for a run ID."""
    return _RUN_STAGES.get(run_id, STAGE_DEFINITIONS["fetching"])


def clear_run_stage(run_id: str) -> None:
    """Cleans up in-memory stage tracking when a run completes or fails."""
    _RUN_STAGES.pop(run_id, None)
