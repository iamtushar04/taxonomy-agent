"""
apply_mapping_cmd.py — Handle "Map X under Y" style commands from the user.

When the user says things like:
  - "Map Thermal Regulation under Safety Systems"
  - "Put Battery Charging under Power Electronics"
  - "Merge Thermal and Heat Management into one node"
  - "Rename Cooling Systems to Thermal Control"
  - "Exclude Consumer Electronics from taxonomy"

This node:
1. Parses the mapping instruction using LLM (entities already extracted by detect_intent)
2. Creates a MappingRule and appends it to the session's mapping_rules list
3. Confirms the rule back to the user and asks: apply now or save for next run?
"""

import logging
from chatbot_agent.state import ChatAgentState, MappingRule, MappingRuleType

logger = logging.getLogger(__name__)

# Human-readable descriptions for rule types
RULE_DESCRIPTIONS = {
    MappingRuleType.REPARENT:   "moved under",
    MappingRuleType.MERGE:      "merged with",
    MappingRuleType.SPLIT:      "split from",
    MappingRuleType.RENAME:     "renamed to",
    MappingRuleType.EXCLUDE:    "excluded from taxonomy",
    MappingRuleType.PRIORITIZE: "prioritized more heavily",
}


def apply_mapping_cmd(state: ChatAgentState) -> dict:
    """
    Parse and store a user-defined mapping rule.
    Updates: mapping_rules, response_text, response_metadata
    """
    entities = state.intent_entities or {}
    user_message = state.user_message

    rule_type_str = entities.get("rule_type", "reparent")
    source_node   = entities.get("source_node", "").strip()
    target_node   = entities.get("target_node", "").strip() or None

    # Validate we have at least a source node
    if not source_node:
        return {
            "response_text": (
                "I understood you want to define a mapping rule, but I couldn't identify which node to act on. "
                "Could you be more specific? For example:\n"
                "- **\"Map Thermal Regulation under Safety Systems\"**\n"
                "- **\"Merge Battery Charging with Power Management\"**\n"
                "- **\"Exclude Consumer Electronics\"**"
            ),
            "response_metadata": {"type": "mapping_parse_error"}
        }

    # Convert rule type string to enum safely
    try:
        rule_type = MappingRuleType(rule_type_str)
    except ValueError:
        rule_type = MappingRuleType.REPARENT

    # Create the rule
    new_rule = MappingRule(
        rule_type=rule_type,
        source_node=source_node,
        target_node=target_node,
        applied=False,
        raw_instruction=user_message
    )

    # Append to existing rules (immutably)
    existing_rules = list(state.mapping_rules or [])
    existing_rules.append(new_rule)

    # Build confirmation message
    description = RULE_DESCRIPTIONS.get(rule_type, "modified")
    if target_node:
        confirmation = f"**\"{source_node}\"** will be {description} **\"{target_node}\"**"
    else:
        confirmation = f"**\"{source_node}\"** will be {description}"

    total_rules = len(existing_rules)
    response_text = (
        f"Got it! I've saved this mapping rule:\n\n"
        f"📌 {confirmation}\n\n"
        f"You now have **{total_rules} mapping rule{'s' if total_rules > 1 else ''}** saved.\n\n"
        f"These rules will be applied when you build the taxonomy. "
        f"Say **\"build taxonomy\"** to start the run with these rules applied."
    )

    # If there's a linked run (post-run phase), offer to apply immediately
    if state.run_id:
        response_text += (
            f"\n\nSince a taxonomy already exists (Run #{state.run_id[:8]}...), "
            f"I can also apply this rule and rebuild. Say **\"apply now\"** or **\"rebuild with corrections\"** if you'd like that."
        )

    logger.info(f"[apply_mapping_cmd] Added rule: {new_rule.rule_type} '{source_node}' → '{target_node}'")

    return {
        "mapping_rules": existing_rules,
        "response_text": response_text,
        "response_metadata": {
            "type": "mapping_rule_added",
            "new_rule": new_rule.model_dump(),
            "all_rules": [r.model_dump() for r in existing_rules]
        }
    }
