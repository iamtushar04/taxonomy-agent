"""
semantic_agent.py — Truly Semantic, Tool-Calling Conversational Agent.

Replaces the rigid, keyword-scripted intent router with an autonomous ReAct
agent that maintains full multi-turn conversation memory and executes native
taxonomy and product tools on demand.
"""

import json
import logging
from typing import Any, List, Dict

from chatbot_agent.state import ChatAgentState, MappingRule, MappingRuleType
from chatbot_agent.tools.taxonomy_tools import inspect_tree, search_taxonomy, get_node_details, edit_taxonomy
from chatbot_agent.tools.product_tools import search_products
from pipeline.utils.llm_client import get_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Native Tools Schema (OpenAI Function Calling Format)
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "inspect_tree",
            "description": "Explore the taxonomy hierarchy structure, branch names, levels, and node counts. Use when the user asks broad or architectural questions about the graph layout, categories, or available branches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {
                        "type": "string",
                        "description": "Optional branch name or root category to focus on (e.g. 'Peptide Therapeutics', 'Chromatography'). Leave empty to see the top-level tree."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_taxonomy",
            "description": "Search across taxonomy nodes, patent claims, and attached product features. Use when searching for specific technologies, mechanisms, concepts, or terms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term or concept (e.g. 'auto-injector', 'purification', 'macrocyclization', 'permeability')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_node_details",
            "description": "Retrieve comprehensive details for a specific taxonomy node: exact definition, hierarchy path, all supporting patent IDs with claim evidence, and linked commercial products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_identifier": {
                        "type": "string",
                        "description": "The node name or node_id (e.g. 'Continuous Chromatography' or 'tech_14') or specific patent ID."
                    }
                },
                "required": ["node_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search and inspect commercial product specifications, capabilities, and features associated with this workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term for product features, brand, or specifications (e.g. 'pen', 'subcutaneous', 'dose')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_taxonomy",
            "description": "Move, rename, merge, exclude, or prioritize a node in the taxonomy hierarchy. Use whenever the user asks to restructure or correct the graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["reparent", "rename", "merge", "exclude", "prioritize"],
                        "description": "Type of edit action."
                    },
                    "source_node": {
                        "type": "string",
                        "description": "The node being moved, renamed, or modified."
                    },
                    "target_node": {
                        "type": "string",
                        "description": "The target parent node, new name, or merge target (if applicable)."
                    }
                },
                "required": ["action", "source_node"]
            }
        }
    }
]

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """You are the Taxonomy & Product Alignment Co-Pilot, an elite AI assistant specializing in patent intelligence, commercial product analysis, and technology taxonomy engineering.

WORKSPACE CAPABILITIES:
1. You have direct tools to inspect the live taxonomy hierarchy, search patent claims, view evidence, query commercial product specifications, and register live taxonomy restructuring rules.
2. The taxonomy is ACTIVE in the user's workspace right now. Never tell the user "once the taxonomy is built" or "please wait for taxonomy generation".

CONVERSATIONAL GUIDELINES:
- Multi-Turn Fluency: Maintain complete conversational continuity. Resolve pronouns ("them", "that one", "the second patent", "it") based on prior turns without asking the user to repeat themselves.
- Grounded Answers: Always call tools (`search_taxonomy`, `get_node_details`, `inspect_tree`, `search_products`) to ground your answers in actual patent claims and real product specs.
- Format Clearly:
  * Bold all Patent IDs: **US10683334B2**, **WO2023207107A1**.
  * Trace hierarchy paths with clean breadcrumbs: *Category -> Sub-category -> Node*.
  * Use bullet points and clear technical summaries.
- Editing & Restructuring: If the user says "move X under Y", "rename X to Z", or "exclude X", invoke the `edit_taxonomy` tool and confirm the change clearly.
"""

# ---------------------------------------------------------------------------
# Semantic Agent Node
# ---------------------------------------------------------------------------

def semantic_agent(state: ChatAgentState) -> dict:
    """
    Autonomous ReAct agent that inspects conversation memory, invokes tools,
    and returns rich multi-turn responses.
    """
    user_message = state.user_message.strip()
    if not user_message:
        return {"response_text": "How can I assist you with this taxonomy or patent portfolio today?"}

    client = get_client()
    taxonomy = state.final_taxonomy or []
    source_data = state.source_data or {}
    product_doc_text = state.product_doc_text or ""
    current_mapping_rules = list(state.mapping_rules or [])

    # Assemble conversation history (last 8 messages)
    history_messages: List[Dict[str, Any]] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    
    # Context note if taxonomy exists
    if taxonomy:
        history_messages.append({
            "role": "system",
            "content": f"Context: Active taxonomy contains {len(taxonomy)} nodes across technical domains. Supporting products: {len(source_data.get('_products', {}))} products mapped."
        })

    # Add prior dialogue turns
    if state.messages:
        for m in state.messages[-8:]:
            history_messages.append({
                "role": m.role if m.role in ("user", "assistant") else "user",
                "content": m.content or ""
            })

    # Add current user message
    history_messages.append({"role": "user", "content": user_message})

    # Track new mapping rules and executed tool names
    new_mapping_rules: List[MappingRule] = []
    executed_tools: List[str] = []
    response_metadata: Dict[str, Any] = {}

    try:
        # First LLM call: decide response or tool execution
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=history_messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            temperature=0.2
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # Step 2: Handle Tool Calls if the agent requested them
        if tool_calls:
            # Append assistant message with tool calls to history
            history_messages.append(response_message)

            for tool_call in tool_calls:
                func_name = tool_call.function.name
                executed_tools.append(func_name)
                
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except Exception:
                    args = {}

                tool_result: Any = {}

                # Execute matching tool
                if func_name == "inspect_tree":
                    tool_result = inspect_tree(
                        taxonomy=taxonomy,
                        branch=args.get("branch")
                    )

                elif func_name == "search_taxonomy":
                    tool_result = search_taxonomy(
                        query=args.get("query", user_message),
                        taxonomy=taxonomy,
                        source_data=source_data
                    )

                elif func_name == "get_node_details":
                    tool_result = get_node_details(
                        node_identifier=args.get("node_identifier", ""),
                        taxonomy=taxonomy,
                        source_data=source_data
                    )

                elif func_name == "search_products":
                    tool_result = search_products(
                        query=args.get("query", ""),
                        source_data=source_data,
                        product_doc_text=product_doc_text
                    )

                elif func_name == "edit_taxonomy":
                    edit_res = edit_taxonomy(
                        action=args.get("action", "reparent"),
                        source_node=args.get("source_node", ""),
                        target_node=args.get("target_node"),
                        mapping_rules=current_mapping_rules
                    )
                    tool_result = edit_res
                    if "rule" in edit_res:
                        new_rule = MappingRule(**edit_res["rule"])
                        new_mapping_rules.append(new_rule)
                        response_metadata["rule_added"] = edit_res["rule"]

                else:
                    tool_result = {"error": f"Unknown tool: {func_name}"}

                # Append tool result message
                history_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

            # Second LLM call: Synthesize final answer with tool outputs
            second_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=history_messages,
                temperature=0.1
            )
            final_text = second_response.choices[0].message.content or ""

        else:
            final_text = response_message.content or ""

        response_metadata["executed_tools"] = executed_tools
        combined_rules = current_mapping_rules + new_mapping_rules

        return {
            "response_text": final_text,
            "response_metadata": response_metadata,
            "mapping_rules": combined_rules,
            "tool_calls": [{"tool": t} for t in executed_tools]
        }

    except Exception as e:
        logger.exception(f"Semantic agent execution error: {e}")
        return {
            "response_text": f"I encountered an error processing your query: {str(e)}. Please feel free to ask about specific patents, branches, or product features.",
            "response_metadata": {"error": str(e)},
            "errors": [str(e)]
        }
