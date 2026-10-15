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
from chatbot_agent.nodes.build_taxonomy_cmd import build_taxonomy_cmd
from chatbot_agent.nodes.semantic_agent import semantic_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing Logic
# ---------------------------------------------------------------------------

def route_by_intent(state: ChatAgentState) -> str:
    """
    After detect_intent runs, route to the correct handler node.
    Directs all conversational, analytical, product, and graph-editing turns to semantic_agent.
    """
    intent = state.detected_intent

    if intent == ChatIntent.BUILD_TAXONOMY:
        return "build_taxonomy_cmd"
    
    # All reasoning, Q&A, product matching, and tree editing go to semantic_agent
    return "semantic_agent"


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_chatbot_graph():
    """
    Build and compile the chatbot LangGraph with the Semantic Agent.
    """
    builder = StateGraph(ChatAgentState)

    builder.add_node("detect_intent",  detect_intent)
    builder.add_node("build_taxonomy_cmd", build_taxonomy_cmd)
    builder.add_node("semantic_agent", semantic_agent)

    # ── Edges ────────────────────────────────────────────────────────────────
    builder.set_entry_point("detect_intent")

    builder.add_conditional_edges(
        "detect_intent",
        route_by_intent,
        {
            "build_taxonomy_cmd": "build_taxonomy_cmd",
            "semantic_agent":     "semantic_agent",
        }
    )

    builder.add_edge("build_taxonomy_cmd", END)
    builder.add_edge("semantic_agent",     END)

    graph = builder.compile()
    logger.info("[chatbot_agent] Semantic Agent Graph compiled successfully")
    return graph


_chatbot_graph = None

def get_chatbot_graph(force_rebuild: bool = False):
    """Get or create the chatbot graph instance."""
    global _chatbot_graph
    if _chatbot_graph is None or force_rebuild:
        _chatbot_graph = build_chatbot_graph()
    return _chatbot_graph
