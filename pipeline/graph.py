"""
LangGraph pipeline graph.

Assembles all nodes into a directed state graph.
Each patent runs through this graph independently.

Graph topology:
    fetch_patent
        ↓ (on error → write_excel)
    parse_content
        ↓
    describe_nodes
        ↓
    match_relevance
        ↓
    extract_values
        ↓
    apply_rules
        ↓
    validate
        ↓
    write_excel

The write_excel node is registered with col_map already bound via
functools.partial, keeping node signatures uniform (state → state).
"""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from pipeline.nodes.describe_nodes import describe_nodes
from pipeline.nodes.extract_values import extract_values
from pipeline.nodes.apply_rules import apply_rules
from pipeline.nodes.fetch_patent import fetch_patent
from pipeline.nodes.match_relevance import match_relevance
from pipeline.nodes.parse_content import parse_content
from pipeline.nodes.validate import validate
from pipeline.nodes.write_excel import write_excel
from pipeline.state import PatentExtractionState
from pipeline.utils.excel_mapper import ExcelColumnMap


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def _route_after_fetch(state: PatentExtractionState) -> str:
    """If fetch failed, jump straight to write_excel to record the error."""
    if state.get("errors"):
        return "write_excel"
    return "parse_content"


def _route_after_parse(state: PatentExtractionState) -> str:
    """If parse yielded no chunks, skip to write_excel (write metadata only)."""
    if not state.get("patent_chunks"):
        return "write_excel"
    return "describe_nodes"


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_graph(col_map: ExcelColumnMap) -> any:
    """
    Build and compile the LangGraph extraction pipeline.

    Args:
        col_map:  ExcelColumnMap — pre-built mapping of columns to node IDs.
                  Passed to write_excel via partial so the graph signature
                  stays uniform.

    Returns:
        Compiled LangGraph app (call .invoke(state) to run a patent).
    """
    # Bind col_map into write_excel without changing its signature
    write_excel_bound = partial(write_excel, col_map=col_map)

    graph = StateGraph(PatentExtractionState)

    # ── Register nodes ─────────────────────────────────────────────────────
    graph.add_node("fetch_patent",    fetch_patent)
    graph.add_node("parse_content",   parse_content)
    graph.add_node("describe_nodes",  describe_nodes)
    graph.add_node("match_relevance", match_relevance)
    graph.add_node("extract_values",  extract_values)
    graph.add_node("apply_rules",     apply_rules)
    graph.add_node("validate",        validate)
    graph.add_node("write_excel",     write_excel_bound)

    # ── Entry point ────────────────────────────────────────────────────────
    graph.set_entry_point("fetch_patent")

    # ── Edges ──────────────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "fetch_patent",
        _route_after_fetch,
        {"parse_content": "parse_content", "write_excel": "write_excel"},
    )
    graph.add_conditional_edges(
        "parse_content",
        _route_after_parse,
        {"describe_nodes": "describe_nodes", "write_excel": "write_excel"},
    )
    graph.add_edge("describe_nodes",  "match_relevance")
    graph.add_edge("match_relevance", "extract_values")
    graph.add_edge("extract_values",  "apply_rules")
    graph.add_edge("apply_rules",     "validate")
    graph.add_edge("validate",        "write_excel")
    graph.add_edge("write_excel",     END)

    return graph.compile()
