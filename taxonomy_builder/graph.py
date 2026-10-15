"""
Graph definition for Taxonomy Builder using Map-Reduce pattern.

Pipeline flow (updated):
  fetch_patents
    ↓ (fan-out per patent)
  extract_concepts       ← parallel, with domain_path extraction (Phase 3)
    ↓ (fan-in)
  deduplicate_concepts
    ↓
  group_concepts         ← produces nested skeleton + flat mapping (Phase 2)
    ↓
  build_hierarchy        ← 5-7 level deep tree, Technology root, context-grounded (Phase 1)
    ↓
  validate_hierarchy     ← structural validation + auto-patch (Phase 4)
    ↓
  enrich_nodes
    ↓
  format_taxonomy
"""
from langgraph.graph import StateGraph, END
from langgraph.types import Send

from taxonomy_builder.state import TaxonomyGenerationState
from taxonomy_builder.nodes.fetch_patents import fetch_patents
from taxonomy_builder.nodes.extract_concepts import extract_concepts
from taxonomy_builder.nodes.group_concepts import group_concepts
from taxonomy_builder.nodes.deduplicate_concepts import deduplicate_concepts
from taxonomy_builder.nodes.build_hierarchy import build_hierarchy
from taxonomy_builder.nodes.validate_hierarchy import validate_hierarchy
from taxonomy_builder.nodes.enrich_nodes import enrich_nodes
from taxonomy_builder.nodes.format_taxonomy import format_taxonomy
from taxonomy_builder.nodes.map_products import map_products


def continue_to_extract_concepts(state: TaxonomyGenerationState):
    """
    Map-Reduce routing logic.
    Dispatches parallel 'extract_concepts' nodes for:
    1. Every fetched patent
    2. Every uploaded commercial product specification (if any)
    """
    patents_data = state.get("patents_data", {})
    products_data = state.get("products_data", {})
    
    if not patents_data and not products_data:
        return "format_taxonomy"

    sends = []
    
    domain_anchor = state.get("domain_anchor")

    # 1. Dispatch parallel extraction for patents
    for p_id, p_data in patents_data.items():
        sends.append(
            Send(
                "extract_concepts",
                {
                    "run_id": state.get("run_id", "default"),
                    "patent_id": p_id,
                    "text": p_data.get("full_text", ""),
                    "is_product": False,
                    "mental_model_context": state.get("mental_model_context"),
                    "domain_anchor": domain_anchor
                }
            )
        )

    # 2. Dispatch parallel extraction for commercial products
    for prod_id, prod_info in products_data.items():
        prod_name = prod_info.get("product_name", prod_id)
        prod_features = prod_info.get("features", [])
        features_str = "\n".join(f"- {f}" for f in prod_features)
        raw_text = prod_info.get("full_text_snippet", "")
        
        product_doc_text = (
            f"Commercial Product Specification\n"
            f"Product Name: {prod_name}\n"
            f"Key Technical Features & Components:\n{features_str}\n\n"
            f"Documentation Details:\n{raw_text}"
        )
        
        sends.append(
            Send(
                "extract_concepts",
                {
                    "run_id": state.get("run_id", "default"),
                    "patent_id": prod_id,  # will be prod_xxx
                    "text": product_doc_text,
                    "is_product": True,
                    "product_name": prod_name,
                    "domain_anchor": domain_anchor
                }
            )
        )

    return sends


def build_taxonomy_graph():
    builder = StateGraph(TaxonomyGenerationState)

    # ── Add Nodes ────────────────────────────────────────────────────────────
    builder.add_node("fetch_patents", fetch_patents)
    builder.add_node("extract_concepts", extract_concepts)
    builder.add_node("deduplicate_concepts", deduplicate_concepts)
    builder.add_node("group_concepts", group_concepts)
    builder.add_node("build_hierarchy", build_hierarchy)
    builder.add_node("validate_hierarchy", validate_hierarchy)   # NEW Phase 4
    builder.add_node("enrich_nodes", enrich_nodes)
    builder.add_node("format_taxonomy", format_taxonomy)
    builder.add_node("map_products", map_products)

    # ── Edges ────────────────────────────────────────────────────────────────
    builder.set_entry_point("fetch_patents")

    # fetch_patents fans out to multiple extract_concepts running in parallel
    builder.add_conditional_edges(
        "fetch_patents",
        continue_to_extract_concepts,
        ["extract_concepts", "format_taxonomy"]
    )

    # After all parallel extract_concepts finish, reduce into deduplicate
    builder.add_edge("extract_concepts", "deduplicate_concepts")
    builder.add_edge("deduplicate_concepts", "group_concepts")
    builder.add_edge("group_concepts", "build_hierarchy")
    builder.add_edge("build_hierarchy", "validate_hierarchy")    # NEW Phase 4
    builder.add_edge("validate_hierarchy", "enrich_nodes")       # was build_hierarchy → enrich_nodes
    builder.add_edge("enrich_nodes", "format_taxonomy")
    builder.add_edge("format_taxonomy", "map_products")
    builder.add_edge("map_products", END)

    return builder.compile()
