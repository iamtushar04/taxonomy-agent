"""
graph.py — LangGraph definition for the Chatbot Agent.

Mirrors the pattern of taxonomy_builder/graph.py.

Flow:
  detect_intent
    ↓ (conditional routing by intent)
  ├── build_taxonomy_cmd   (intent: build_taxonomy)
  ├── apply_mapping_cmd    (intent: custom_mapping)
  ├── explain_taxonomy     (intent: explain_node | correct_node | re_run)
  └── respond_general      (intent: general_question + fallback)
    ↓
  END
"""

import logging
from langgraph.graph import StateGraph, END

from chatbot_agent.state import ChatAgentState, ChatIntent
from chatbot_agent.nodes.detect_intent import detect_intent
from chatbot_agent.nodes.ingest_product import ingest_product
from chatbot_agent.nodes.build_taxonomy_cmd import build_taxonomy_cmd
from chatbot_agent.nodes.apply_mapping_cmd import apply_mapping_cmd
from chatbot_agent.nodes.explain_taxonomy import explain_taxonomy
from chatbot_agent.nodes.respond_general import respond_general

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing Logic
# ---------------------------------------------------------------------------

def route_by_intent(state: ChatAgentState) -> str:
    """
    After detect_intent runs, route to the correct handler node.
    """
    intent = state.detected_intent

    if intent == ChatIntent.BUILD_TAXONOMY:
        return "build_taxonomy_cmd"
    elif intent == ChatIntent.CUSTOM_MAPPING:
        return "apply_mapping_cmd"
    elif intent in (ChatIntent.EXPLAIN_NODE, ChatIntent.CORRECT_NODE, ChatIntent.RE_RUN):
        return "explain_taxonomy"
    else:
        # If taxonomy exists in the workspace, route any questions to explain_taxonomy for grounded answers
        if state.final_taxonomy:
            return "explain_taxonomy"
        return "respond_general"


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_chatbot_graph():
    """
    Build and compile the chatbot LangGraph.

    Returns:
        Compiled LangGraph runnable
    """
    builder = StateGraph(ChatAgentState)

    # ── Add Nodes ────────────────────────────────────────────────────────────
    # Note: ingest_product is NOT in the graph — it is called directly by the
    # API route when a file upload is received (separate endpoint).
    # The graph handles the conversational turn after upload is done.

    builder.add_node("detect_intent",      detect_intent)
    builder.add_node("build_taxonomy_cmd", build_taxonomy_cmd)
    builder.add_node("apply_mapping_cmd",  apply_mapping_cmd)
    builder.add_node("explain_taxonomy",   explain_taxonomy)
    builder.add_node("respond_general",    respond_general)

    # ── Edges ────────────────────────────────────────────────────────────────
    builder.set_entry_point("detect_intent")

    # After detect_intent, route to the correct handler
    builder.add_conditional_edges(
        "detect_intent",
        route_by_intent,
        {
            "build_taxonomy_cmd": "build_taxonomy_cmd",
            "apply_mapping_cmd":  "apply_mapping_cmd",
            "explain_taxonomy":   "explain_taxonomy",
            "respond_general":    "respond_general",
        }
    )

    # All handler nodes go to END
    builder.add_edge("build_taxonomy_cmd", END)
    builder.add_edge("apply_mapping_cmd",  END)
    builder.add_edge("explain_taxonomy",   END)
    builder.add_edge("respond_general",    END)

    graph = builder.compile()
    logger.info("[chatbot_agent] Graph compiled successfully")
    return graph


_chatbot_graph = None

def get_chatbot_graph(force_rebuild: bool = False):
    """Get or create the chatbot graph instance."""
    global _chatbot_graph
    if _chatbot_graph is None or force_rebuild:
        _chatbot_graph = build_chatbot_graph()
    return _chatbot_graph
