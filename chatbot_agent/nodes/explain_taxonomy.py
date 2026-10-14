"""
explain_taxonomy.py — Post-run Q&A node.

Handles:
  - explain_node  : "Why is X here?", "Explain Thermal Management"
  - correct_node  : "This grouping is wrong", "X doesn't belong here"

Uses RAG over the stored final_taxonomy + source_data to give
evidence-grounded answers.
"""

import logging
import os
from chatbot_agent.state import ChatAgentState, MappingRule, MappingRuleType

logger = logging.getLogger(__name__)

EXPLAIN_SYSTEM_PROMPT = """You are an expert patent taxonomy reasoning assistant.

STATUS:
The taxonomy for this session HAS ALREADY BEEN GENERATED and is active in the workspace.
You have direct, full access to the taxonomy hierarchy, product capabilities, and patent evidence.

Your job is to:
1. Answer questions about WHICH patents cover specific mechanisms, technologies, or product features (e.g. cellular permeability, macrocyclization, drug delivery).
2. When asked "how many patents" or "which patents belong to feature X":
   - State the exact count and list the relevant Patent IDs in **bold** (e.g., **US20150011467A1**, **US20130089545A1**, **CN107496932A**).
   - Explain the specific mechanism or claim context for each patent.
   - Show which taxonomy node and branch (e.g., *Biopharmaceuticals -> Peptide Therapeutics -> Drug Delivery*) contains each patent.
3. Show how commercial product capabilities align with patents and taxonomy categories.
4. Answer follow-up questions accurately, maintaining full conversational context.

CRITICAL RULES:
- NEVER say "once the taxonomy is built", "please wait for taxonomy generation", "I need to analyze it when ready", or "please hold on for a moment" — the taxonomy is finalized and available right now in your context.
- Directly answer the user's question with specific patent numbers, counts, and technical details.
- Use clean markdown with bullet points and bold headers.
"""


def explain_taxonomy(state: ChatAgentState) -> dict:
    """
    Handle explain_node and correct_node intents using RAG over the taxonomy.
    Updates: response_text, response_metadata, (optionally) mapping_rules for corrections
    """
    from pipeline.utils.llm_client import chat_completion
    from chatbot_agent.utils.rag_retriever import retrieve_relevant_nodes

    intent = state.detected_intent
    user_message = state.user_message
    entities = state.intent_entities or {}
    final_taxonomy = state.final_taxonomy
    source_data = state.source_data

    if not final_taxonomy:
        return {
            "response_text": (
                "No taxonomy has been generated yet for this session. Please build a taxonomy first, "
                "then I can answer detailed questions about nodes and patents."
            ),
            "response_metadata": {"type": "no_taxonomy_warning"}
        }

    # Retrieve relevant taxonomy nodes using query and recent conversation history
    relevant_nodes = retrieve_relevant_nodes(
        query=user_message,
        taxonomy=final_taxonomy,
        source_data=source_data,
        history_messages=state.messages,
        top_k=6
    )

    # Build rich context for the LLM
    taxonomy_context = _format_nodes_as_context(relevant_nodes, source_data, final_taxonomy)

    try:
        messages = [
            {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Taxonomy context (relevant nodes & patent evidence):\n\n{taxonomy_context}\n\n"
                f"User question: {user_message}"
            )}
        ]

        # Add recent conversation history for context (last 6 messages)
        history = state.messages[-6:] if state.messages else []
        if history:
            messages = (
                [messages[0]]
                + [{"role": m.role, "content": m.content} for m in history]
                + [messages[-1]]
            )

        response_text = chat_completion(messages, model="gpt-4o-mini", temperature=0.3).strip()

        metadata = {
            "type": "taxonomy_explanation",
            "relevant_nodes": [n.get("name", "") for n in relevant_nodes]
        }

        # For correct_node intent — automatically suggest adding a correction rule
        result = {
            "response_text": response_text,
            "response_metadata": metadata
        }

        if intent and intent.value == "correct_node":
            source_node = entities.get("source_node", "")
            if source_node:
                correction_rule = MappingRule(
                    rule_type=MappingRuleType.REPARENT,
                    source_node=source_node,
                    target_node=None,
                    applied=False,
                    raw_instruction=user_message
                )
                existing_rules = list(state.mapping_rules or [])
                existing_rules.append(correction_rule)
                result["mapping_rules"] = existing_rules
                result["response_text"] += (
                    f"\n\nI've logged a correction note for **\"{source_node}\"**. "
                    f"You can tell me where it should go (e.g. \"Move it under Safety Systems\") "
                    f"and I'll save that as a mapping rule for the next rebuild."
                )

        return result

    except Exception as e:
        logger.error(f"[explain_taxonomy] Error: {e}")
        return {
            "response_text": f"I had trouble generating an explanation: {str(e)}",
            "errors": [str(e)]
        }


def _format_nodes_as_context(nodes: list[dict], source_data: dict | None, taxonomy: list[dict] | None = None) -> str:
    """Format retrieved taxonomy nodes and patent evidence as readable context for the LLM."""
    if not nodes:
        return "No specific nodes found matching the query."

    lines = []
    source_data = source_data or {}
    products_map = source_data.get("_products", {}) if isinstance(source_data, dict) else {}
    node_by_id = {n.get("node_id"): n for n in (taxonomy or []) if n.get("node_id")}

    # 1. Commercial Product Capabilities Section
    if products_map:
        lines.append("### Active Commercial Product Profile:")
        for pid, p_info in products_map.items():
            lines.append(f"Product: {p_info.get('product_name', 'Product')}")
            feats = p_info.get("features", [])
            if feats:
                lines.append("Extracted Technical Capabilities:")
                for f in feats:
                    lines.append(f"  • {f}")
        lines.append("")

    # 2. Retrieved Taxonomy Nodes & Evidence
    for node in nodes:
        name = node.get("name", "Unknown")
        level = node.get("level", "?")
        description = node.get("description", "No description available")
        patent_ids = list(node.get("supporting_patent_ids", []))
        parent_id = node.get("parent_node_id")

        # Trace hierarchy branch up to root
        parent_names = []
        curr_p = parent_id
        while curr_p and curr_p in node_by_id and len(parent_names) < 4:
            p_node = node_by_id[curr_p]
            p_name = p_node.get("name", curr_p)
            parent_names.append(p_name)
            if not patent_ids and p_node.get("supporting_patent_ids"):
                patent_ids.extend(p_node.get("supporting_patent_ids"))
            curr_p = p_node.get("parent_node_id")

        branch_path = " -> ".join(reversed(parent_names + [name])) if parent_names else name

        lines.append(f"### Node: {name} (Level {level})")
        lines.append(f"Hierarchy Path: {branch_path}")
        lines.append(f"Definition: {description}")

        # Linked commercial product capabilities
        prod_ids = node.get("supporting_product_ids", [])
        if prod_ids:
            for pid in prod_ids:
                p_info = products_map.get(pid, {})
                p_name = p_info.get("product_name", pid)
                p_feats = p_info.get("features", [])
                lines.append(f"Aligned Product: {p_name}")
                if p_feats:
                    lines.append(f"  Matched Product Capabilities: {'; '.join(p_feats)}")

        # Supporting patents and evidence contexts
        patent_ids = list(dict.fromkeys(patent_ids))
        if patent_ids:
            lines.append(f"Supported by {len(patent_ids)} Patent(s): {', '.join(patent_ids)}")
            ctx_map = node.get("contexts_by_patent", {})
            for pid in patent_ids[:5]:
                p_meta = source_data.get(pid, {})
                title = p_meta.get("title", "")
                abstract = p_meta.get("abstract", "") or p_meta.get("summary", "")
                lines.append(f"  * Patent **{pid}**: {title}")
                if ctx_map.get(pid):
                    lines.append(f"    Evidence Context: \"{ctx_map[pid][0][:250]}\"")
                elif abstract:
                    lines.append(f"    Summary: {abstract[:250]}...")

        lines.append("")

    return "\n".join(lines)
