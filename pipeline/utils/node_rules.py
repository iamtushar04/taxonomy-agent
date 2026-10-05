"""
Data-preference rules per taxonomy node.

Rules tell the LLM extraction prompt:
  - Which limit to pick when a range is given (upper / lower / most_specific)
  - Which unit to standardise to (MPa, g/cm³, °C …)
  - Source priority order

Rules are matched by case-insensitive substring of the node name.
The first matching rule wins; _default catches everything else.

To add a new node rule: just append an entry here — no other file changes.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule definitions
# Each entry: (substring_to_match, rule_dict)
# Matching is done in order — first match wins.
# ---------------------------------------------------------------------------
_RULES: list[tuple[str, dict]] = [
    # Mechanical
    ("tensile strength",        {"limit": "upper", "unit": "MPa",     "priority": ["claims", "description", "tables"]}),
    ("tensile elongation",      {"limit": "upper", "unit": "%",       "priority": ["claims", "description", "tables"]}),
    ("modulus",                 {"limit": "upper", "unit": "MPa",     "priority": ["claims", "description", "tables"]}),
    ("dart impact",             {"limit": "upper", "unit": "g",       "priority": ["claims", "description", "tables"]}),
    ("drop impact",             {"limit": "upper", "unit": "J/cm",    "priority": ["claims", "description", "tables"]}),
    ("impact strength",         {"limit": "upper", "unit": "J/cm",    "priority": ["claims", "description", "tables"]}),
    ("durability",              {"limit": "upper", "unit": None,      "priority": ["claims", "description", "tables"]}),
    # Optical
    ("haze",                    {"limit": "lower", "unit": "%",       "priority": ["claims", "description", "tables"]}),
    ("gloss",                   {"limit": "upper", "unit": "%",       "priority": ["claims", "description", "tables"]}),
    ("clarity",                 {"limit": "upper", "unit": "%",       "priority": ["claims", "description", "tables"]}),
    ("transparency",            {"limit": "upper", "unit": "%",       "priority": ["claims", "description", "tables"]}),
    # Thermal / barrier
    ("melt temperature",        {"limit": "upper", "unit": "°C",      "priority": ["claims", "description", "tables"]}),
    ("melting temperature",     {"limit": "upper", "unit": "°C",      "priority": ["claims", "description", "tables"]}),
    ("seal initiation",         {"limit": "lower", "unit": "°C",      "priority": ["claims", "description", "tables"]}),
    ("sealing temperature",     {"limit": "lower", "unit": "°C",      "priority": ["claims", "description", "tables"]}),
    ("vicat",                   {"limit": "lower", "unit": "°C",      "priority": ["claims", "description", "tables"]}),
    ("heat resistance",         {"limit": "upper", "unit": "°C",      "priority": ["claims", "description", "tables"]}),
    ("barrier",                 {"limit": "most_specific", "unit": None, "priority": ["claims", "description", "tables"]}),
    # Rheological
    ("melt flow index",         {"limit": "lower", "unit": "g/10min", "priority": ["claims", "description", "tables"]}),
    ("melt index ratio",        {"limit": "lower", "unit": None,      "priority": ["claims", "description", "tables"]}),
    ("melt index",              {"limit": "lower", "unit": "g/10min", "priority": ["claims", "description", "tables"]}),
    ("melt elastic modulus",    {"limit": "upper", "unit": "Pa",      "priority": ["claims", "description", "tables"]}),
    ("dow rheology index",      {"limit": "most_specific", "unit": None, "priority": ["claims", "description", "tables"]}),
    ("dri",                     {"limit": "most_specific", "unit": None, "priority": ["claims", "description", "tables"]}),
    # Physical
    ("density",                 {"limit": "upper", "unit": "g/cm³",   "priority": ["claims", "description", "tables"]}),
    # Polymerization
    ("polymerization temperature", {"limit": "lower", "unit": "°C",   "priority": ["claims", "description", "tables"]}),
    # Processing
    ("recyclability",           {"limit": "most_specific", "unit": None, "priority": ["claims", "description", "tables"]}),
    ("extrusion",               {"limit": "most_specific", "unit": None, "priority": ["claims", "description", "tables"]}),
]

# Default for anything not matched
_DEFAULT_RULE: dict = {
    "limit": "most_specific",
    "unit": None,
    "priority": ["claims", "description", "tables"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_rules_for_node(node_name: str) -> dict:
    """
    Return the data-preference rule dict for a given taxonomy node name.
    Matching is case-insensitive substring search; first match wins.
    Falls back to _DEFAULT_RULE.
    """
    lower = node_name.lower()
    for substring, rule in _RULES:
        if substring in lower:
            logger.debug("Rule matched '%s' → %s", node_name, rule)
            return rule
    logger.debug("No rule matched '%s' — using default", node_name)
    return _DEFAULT_RULE.copy()


def format_rules_for_prompt(rules: dict) -> str:
    """
    Render a rules dict as a short instruction string to embed in LLM prompts.
    """
    parts = []

    limit = rules.get("limit", "most_specific")
    if limit == "upper":
        parts.append("If a range is given, use the UPPER limit as the representative value.")
    elif limit == "lower":
        parts.append("If a range is given, use the LOWER limit as the representative value.")
    else:
        parts.append("If multiple values are given, choose the MOST SPECIFIC / niche value.")

    unit = rules.get("unit")
    if unit:
        parts.append(f"Standardise the value to {unit}. Convert if necessary.")

    priority = rules.get("priority", ["claims", "description", "tables"])
    parts.append(f"Source priority: {' -> '.join(p.upper() for p in priority)}.")

    parts.append("If multiple value ranges are mentioned, identify the most specific and niche value.")
    parts.append("For multilayer films, consider the property of the entire composition. If not specified, use the metallocene layer.")

    return " ".join(parts)
