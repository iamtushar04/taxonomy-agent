"""
detect_intent.py — Classify the user's message into a ChatIntent.

This is the FIRST node that runs for every user message.
It routes the chatbot graph to the correct handler node.
"""

import json
import logging
import os

from chatbot_agent.state import ChatAgentState, ChatIntent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent Detection Prompt
# ---------------------------------------------------------------------------

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a patent taxonomy assistant chatbot.

Classify the user message into EXACTLY ONE of these intents:

- build_taxonomy   : User wants to start or re-trigger building a taxonomy (e.g. "build taxonomy", "go ahead", "start the run", "build it now", "yes build it", "then start")
- custom_mapping   : User wants to move/merge/rename/exclude/prioritize a taxonomy node (e.g. "put X under Y", "map X to Y", "merge X and Y", "rename X to Z", "exclude X")
- explain_node     : User wants to query the taxonomy, find patents, explain categories, or ask follow-ups about the taxonomy and patents.
  Includes:
  * Finding patents: "Which patent has X?", "Tell me patent which has X", "What patents cover X?", "Show patents under category Y", "Which patents discuss permeability?"
  * Explaining nodes: "Why is X here?", "Explain X", "How does X relate to Y?", "What is in category X?"
  * Follow-up questions: "Are you telling me?", "Which ones?", "Why?", "Explain further", "What about the other patent?"
- correct_node     : User says a taxonomy grouping is wrong (e.g. "X is wrong", "this is incorrect", "X doesn't belong here")
- re_run           : User wants to regenerate/rebuild the taxonomy (e.g. "regenerate", "rebuild", "redo with corrections")
- general_question : Anything else — greetings, general chit-chat, high-level non-taxonomy queries.

For custom_mapping, extract entities:
- rule_type: one of [reparent, merge, split, rename, exclude, prioritize]
- source_node: the node being acted upon
- target_node: the target (parent node, new name, or merge target) — null if not applicable

Return ONLY valid JSON in this format:
{
  "intent": "<intent_name>",
  "entities": {
    "rule_type": "<optional>",
    "source_node": "<optional>",
    "target_node": "<optional>"
  },
  "confidence": 0.0 to 1.0
}
"""

# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def detect_intent(state: ChatAgentState) -> dict:
    """
    Classify the user's latest message into a ChatIntent.
    Updates: detected_intent, intent_entities
    """
    user_message = state.user_message.strip()
    if not user_message:
        return {
            "detected_intent": ChatIntent.GENERAL_QUESTION,
            "intent_entities": {}
        }

    lower_msg = user_message.lower()

    # Fast-path for patent discovery or taxonomy queries if a taxonomy exists
    if state.final_taxonomy:
        patent_query_keywords = [
            "patent", "which patent", "tell me patent", "what patent", "show patent",
            "which one", "are you telling", "where is", "how is", "how many", "belong",
            "permeab", "peptide", "mechanism", "formulation", "claims", "evidence",
            "node", "branch", "category", "feature", "fetaures", "product", "delivery",
            "uptake", "synthesis", "design", "macrocycliz", "chemical", "count"
        ]
        if any(kw in lower_msg for kw in patent_query_keywords):
            logger.info(f"[detect_intent] Fast-path routing to explain_node for: '{user_message[:50]}'")
            return {
                "detected_intent": ChatIntent.EXPLAIN_NODE,
                "intent_entities": {}
            }

    try:
        from pipeline.utils.llm_client import chat_json

        prompt_content = f"User message: {user_message}"
        if state.final_taxonomy:
            prompt_content += f"\nNote: A finalized taxonomy exists with {len(state.final_taxonomy)} nodes."
        
        # Include recent message history for context on follow-up questions
        if state.messages:
            recent_msgs = state.messages[-3:]
            history_lines = [f"- {m.role}: {m.content[:100]}" for m in recent_msgs]
            prompt_content = "Recent conversation context:\n" + "\n".join(history_lines) + f"\n\nCurrent user message: {user_message}"

        parsed = chat_json([
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_content}
        ], cheap=True)

        intent_str = parsed.get("intent", "general_question")
        entities = parsed.get("entities", {})

        # Map string to enum safely
        try:
            intent = ChatIntent(intent_str)
        except ValueError:
            intent = ChatIntent.GENERAL_QUESTION

        logger.info(f"[detect_intent] intent={intent} entities={entities}")
        return {
            "detected_intent": intent,
            "intent_entities": entities
        }

    except Exception as e:
        logger.warning(f"[detect_intent] Failed to classify intent: {e}")
        # If taxonomy exists and failed, default to explain_node rather than general_question
        fallback_intent = ChatIntent.EXPLAIN_NODE if state.final_taxonomy else ChatIntent.GENERAL_QUESTION
        return {
            "detected_intent": fallback_intent,
            "intent_entities": {},
            "errors": [f"Intent detection failed: {str(e)}"]
        }
