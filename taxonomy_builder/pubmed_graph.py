from langgraph.graph import StateGraph, END
from langgraph.types import Send

from taxonomy_builder.pubmed_state import PubMedGenerationState
from taxonomy_builder.nodes.pubmed_fetch_articles import pubmed_fetch_articles
from taxonomy_builder.nodes.pubmed_extract_concepts import pubmed_extract_concepts
from taxonomy_builder.nodes.pubmed_group_concepts import group_concepts as pubmed_group_concepts
from taxonomy_builder.nodes.pubmed_deduplicate_concepts import deduplicate_concepts as pubmed_deduplicate_concepts
from taxonomy_builder.nodes.pubmed_build_hierarchy import build_hierarchy as pubmed_build_hierarchy
from taxonomy_builder.nodes.pubmed_enrich_nodes import enrich_nodes as pubmed_enrich_nodes
from taxonomy_builder.nodes.pubmed_format_taxonomy import format_taxonomy as pubmed_format_taxonomy

def continue_to_extract_concepts(state: PubMedGenerationState):
    pubmed_data = state.get("pubmed_data", {})
    if not pubmed_data:
        return "format_taxonomy"

    sends = []
    for p_id, p_data in pubmed_data.items():
        sends.append(
            Send(
                "extract_concepts",
                {
                    "run_id": state.get("run_id", "default"),
                    "pmid": p_id,
                    "text": p_data.get("full_text", "")
                }
            )
        )
    return sends

def build_pubmed_graph():
    builder = StateGraph(PubMedGenerationState)

    builder.add_node("fetch_articles", pubmed_fetch_articles)
    builder.add_node("extract_concepts", pubmed_extract_concepts)
    builder.add_node("deduplicate_concepts", pubmed_deduplicate_concepts)
    builder.add_node("group_concepts", pubmed_group_concepts)
    builder.add_node("build_hierarchy", pubmed_build_hierarchy)
    builder.add_node("enrich_nodes", pubmed_enrich_nodes)
    builder.add_node("format_taxonomy", pubmed_format_taxonomy)

    builder.set_entry_point("fetch_articles")

    builder.add_conditional_edges(
        "fetch_articles",
        continue_to_extract_concepts,
        ["extract_concepts", "format_taxonomy"]
    )

    builder.add_edge("extract_concepts", "deduplicate_concepts")
    builder.add_edge("deduplicate_concepts", "group_concepts")
    builder.add_edge("group_concepts", "build_hierarchy")
    builder.add_edge("build_hierarchy", "enrich_nodes")
    builder.add_edge("enrich_nodes", "format_taxonomy")
    builder.add_edge("format_taxonomy", END)

    return builder.compile()
