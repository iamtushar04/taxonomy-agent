"""
respond_general.py — General Q&A node for the chatbot.

Handles the general_question intent — everything that isn't a specific command.
Uses conversation history + mental model + taxonomy context (if available).
"""

import logging
import os
from chatbot_agent.state import ChatAgentState

logger = logging.getLogger(__name__)

GENERAL_SYSTEM_PROMPT = """You are a helpful assistant for a patent taxonomy workspace.

STATUS CONTEXT:
If a taxonomy is available in the current session, it HAS ALREADY BEEN GENERATED and is active right now.
NEVER say "once the taxonomy is built", "I will analyze it when ready", or "please wait for taxonomy generation" — the taxonomy and patents are already finalized and visible.

You help users:
1. Understand patent classifications, hierarchy branches, and technological mechanisms.
2. Identify which patents or products cover specific capabilities.
3. Guide users in adding mapping rules or modifying branches.
4. Answer follow-up questions accurately based on conversation context.

Keep responses concise, clear, and evidence-grounded.
"""


def respond_general(state: ChatAgentState) -> dict:
    """
    Handle general questions and conversations.
    Updates: response_text, response_metadata
    """
    user_message = state.user_message
    mental_model = state.mental_model
    final_taxonomy = state.final_taxonomy
    source_data = state.source_data

    # Build system context based on current state
    extra_context = []
    if mental_model:
        extra_context.append(
            f"\nCurrent product context: {mental_model.product_name} — {mental_model.domain} ({mental_model.target_industry})"
        )

    if final_taxonomy:
        extra_context.append(f"\nThe taxonomy is ALREADY BUILT with {len(final_taxonomy)} nodes and active in the workspace.")
        # Retrieve relevant nodes to ground general questions
        try:
            from chatbot_agent.utils.rag_retriever import retrieve_relevant_nodes
            from chatbot_agent.nodes.explain_taxonomy import _format_nodes_as_context
            rel_nodes = retrieve_relevant_nodes(user_message, final_taxonomy, source_data, state.messages, top_k=5)
            tax_ctx = _format_nodes_as_context(rel_nodes, source_data, final_taxonomy)
            extra_context.append(f"\nRelevant Taxonomy Context:\n{tax_ctx}")
        except Exception as err:
            logger.warning(f"[respond_general] Context retrieval failed: {err}")

    if state.mapping_rules:
        extra_context.append(f"\nThe user has {len(state.mapping_rules)} pending mapping rules.")

    system_prompt = GENERAL_SYSTEM_PROMPT
    if extra_context:
        system_prompt += "\n\nCurrent session context:\n" + "\n".join(extra_context)

    try:
        from pipeline.utils.llm_client import chat_completion

        # Build messages with history
        messages = [{"role": "system", "content": system_prompt}]

        # Add last 8 conversation messages for context
        history = state.messages[-8:] if state.messages else []
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        response_text = chat_completion(messages, model="gpt-4o-mini", temperature=0.4).strip()

        logger.info(f"[respond_general] Generated response ({len(response_text)} chars)")

        return {
            "response_text": response_text,
            "response_metadata": {"type": "general_response"}
        }

    except Exception as e:
        logger.error(f"[respond_general] Error: {e}")
        return {
            "response_text": f"I encountered an error: {str(e)}. Please try again.",
            "errors": [str(e)]
        }
