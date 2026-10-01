"""
State definitions for the Taxonomy Builder LangGraph pipeline.
"""

import operator
from typing import Annotated, Any, TypedDict
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Map Phase Schemas (Extracting Concepts per Patent)
# ---------------------------------------------------------------------------

class Concept(BaseModel):
    name: str = Field(description="The name of the technical concept")
    context: str = Field(description="A brief sentence explaining how it is used in the patent")
    patent_id: str = Field(description="The ID of the patent this concept came from")
    domain_path: list[str] = Field(
        default_factory=list,
        description="Technology ancestry path extracted from patent text (e.g. ['Automotive', 'Electric Vehicle', 'Battery Management']). Used to ground the hierarchy."
    )

class ConceptList(BaseModel):
    concepts: list[Concept]

class CanonicalConcept(BaseModel):
    name: str = Field(description="The canonical name of the technical concept")
    supporting_patent_ids: list[str] = Field(description="List of patent IDs that mention this concept")
    supporting_contexts: list[str] = Field(description="List of context snippets for this concept")

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
    supporting_patent_ids: list[str]

# ---------------------------------------------------------------------------
# Global Graph State
# ---------------------------------------------------------------------------

class TaxonomyGenerationState(TypedDict, total=False):
    # ── Inputs ───────────────────────────────────────────────────────────────
    run_id: str
    patent_ids: list[str]
    
    # ── Map Phase Data ───────────────────────────────────────────────────────
    # Dictionary mapping patent_id -> dict with Title, Abstract, Claims, etc.
    patents_data: dict[str, Any] 
    
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
