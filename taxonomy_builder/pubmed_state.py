"""
State definitions for the Taxonomy Builder LangGraph pipeline.
"""

import operator
import json
from typing import Annotated, Any, TypedDict
from pydantic import BaseModel, Field, field_validator

def format_any_to_string(v: Any) -> str:
    """
    Losslessly and dynamically converts any datatype (dict, list, int, float, bool, set, tuple, etc.)
    into a clean, human-readable string without losing any key or parameter values.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, set):
        v = list(v)
    if isinstance(v, dict):
        if all(not isinstance(val, (dict, list, set, tuple)) for val in v.values()):
            return ", ".join(f"{k}: {val}" for k, val in v.items())
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    if isinstance(v, (list, tuple)):
        if all(not isinstance(val, (dict, list, set, tuple)) for val in v):
            return ", ".join(str(item) for item in v)
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v)

# ---------------------------------------------------------------------------
# Map Phase Schemas (Extracting Concepts per Patent)
# ---------------------------------------------------------------------------

class Concept(BaseModel):
    name: str = Field(description="The name of the technical concept")
    context: str = Field(description="A brief sentence explaining how it is used in the patent")
    pmid: str = Field(description="The ID of the patent this concept came from")
    domain_path: list[str] = Field(
        default_factory=list,
        description="Technology ancestry path extracted from patent text (e.g. ['Automotive', 'Electric Vehicle', 'Battery Management']). Used to ground the hierarchy."
    )

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: Any) -> str:
        if v is None:
            return "Unnamed Concept"
        if isinstance(v, str):
            clean = v.strip()
            return clean if clean else "Unnamed Concept"
        if isinstance(v, dict):
            for k in ["name", "concept", "title", "feature", "parameter"]:
                if k in v and v[k]:
                    return str(v[k]).strip()
            return ", ".join(f"{k}: {val}" for k, val in v.items() if not isinstance(val, (dict, list)))
        if isinstance(v, (list, tuple, set)):
            return " / ".join(str(x) for x in v if x)
        return str(v).strip()

    @field_validator("context", mode="before")
    @classmethod
    def normalize_context(cls, v: Any) -> str:
        return format_any_to_string(v)

    @field_validator("pmid", mode="before")
    @classmethod
    def normalize_pmid(cls, v: Any) -> str:
        return str(v).strip() if v is not None else ""

    @field_validator("domain_path", mode="before")
    @classmethod
    def normalize_domain_path(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            paths = []
            for item in v:
                if isinstance(item, list):
                    paths.extend([str(x).strip() for x in item if x])
                elif item:
                    paths.append(str(item).strip())
            return paths
        if isinstance(v, str):
            return [p.strip() for p in v.replace("->", "/").split("/") if p.strip()]
        return []

class ConceptList(BaseModel):
    concepts: list[Concept]

class CanonicalConcept(BaseModel):
    name: str = Field(description="The canonical name of the technical concept")
    supporting_pmids: list[str] = Field(description="List of patent IDs that mention this concept")
    supporting_contexts: list[str] = Field(description="List of context snippets for this concept")
    contexts_by_pmid: dict[str, list[str]] = Field(default_factory=dict, description="Maps a specific patent ID to its context strings")
    domain_paths: list[list[str]] = Field(
        default_factory=list,
        description="Aggregated domain ancestry paths from all raw concepts in this cluster (e.g. [['Materials Science', 'Polymers', 'Mechanical Properties'], ...]). Used to ground the hierarchy backbone."
    )

    @field_validator("supporting_contexts", mode="before")
    @classmethod
    def normalize_supporting_contexts(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return [format_any_to_string(v)] if v else []
        return [format_any_to_string(item) for item in v if item is not None]

    @field_validator("contexts_by_pmid", mode="before")
    @classmethod
    def normalize_contexts_by_pmid(cls, v: Any) -> dict[str, list[str]]:
        if not isinstance(v, dict):
            return {}
        result = {}
        for pid, ctxs in v.items():
            if isinstance(ctxs, list):
                result[str(pid)] = [format_any_to_string(c) for c in ctxs if c is not None]
            else:
                result[str(pid)] = [format_any_to_string(ctxs)]
        return result

# ---------------------------------------------------------------------------
# Reduce Phase Schemas (Grouping & Hierarchy)
# ---------------------------------------------------------------------------

class GroupedConcepts(BaseModel):
    group_name: str = Field(description="A concise, technical name for this group of concepts")
    original_concepts: list[str] = Field(description="The list of concept names that belong to this group")

class AllGroups(BaseModel):
    groups: list[GroupedConcepts]

class TaxonomyNodeDraft(BaseModel):
    name: str = Field(description="Name of the taxonomy node")
    children: list["TaxonomyNodeDraft"] = Field(default_factory=list, description="Child nodes in the hierarchy")

class HierarchyTree(BaseModel):
    root_nodes: list[TaxonomyNodeDraft]

# ---------------------------------------------------------------------------
# Final Output Schema (Matches existing pipeline's expected input)
# ---------------------------------------------------------------------------

class TaxonomyNodeFinal(TypedDict):
    node_id: str
    parent_node_id: str | None
    name: str
    level: int
    description: str
    supporting_pmids: list[str]

# ---------------------------------------------------------------------------
# Global Graph State
# ---------------------------------------------------------------------------

class PubMedGenerationState(TypedDict, total=False):
    # ── Inputs ───────────────────────────────────────────────────────────────
    run_id: str
    pmids: list[str]
    
    # ── Map Phase Data ───────────────────────────────────────────────────────
    # Dictionary mapping pmid -> dict with Title, Abstract, Claims, etc.
    pubmed_data: dict[str, Any] 
    
    # ── Reduce Phase Data (using operator.add for parallel mapping) ──────────
    all_concepts: Annotated[list[Concept], operator.add]
    
    # ── Processing State ─────────────────────────────────────────────────────
    canonical_concepts: list[CanonicalConcept]
    concept_groups: dict[str, list[CanonicalConcept]] # Group Name -> List of CanonicalConcepts
    concept_tree_skeleton: dict[str, Any]    # Nested group skeleton from group_concepts (Phase 2)
    draft_tree: dict[str, Any]               # The raw dict tree structure
    
    # ── Final Output ─────────────────────────────────────────────────────────
    final_taxonomy: list[TaxonomyNodeFinal]
    
    # ── Errors ───────────────────────────────────────────────────────────────
    errors: Annotated[list[str], operator.add]
