from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json


def build_hierarchy(state: TaxonomyGenerationState) -> dict:
    """
    Phase 1 Fix:
    - Receives the nested concept_tree_skeleton (from group_concepts) instead of flat group names
    - Passes full concept contexts as grounding evidence to the LLM
    - Forces a 'Technology' root and 5-7 levels of depth
    - Uses the EV battery example as a reference in the prompt
    """
    print("--- BUILDING HIERARCHY ---")
    
    # NEW: prefer the nested skeleton produced by group_concepts (Phase 2).
    # Fall back to flat group names for backwards compatibility.
    concept_tree_skeleton = state.get("concept_tree_skeleton", {})
    concept_groups = state.get("concept_groups", {})

    # Build a rich context block: group name → list of supporting concept names + contexts
    context_lines = []
    for group_name, concepts in concept_groups.items():
        concept_summary = "; ".join(
            f"{c.name} ({c.supporting_contexts[0][:80] if c.supporting_contexts else 'no context'})"
            for c in concepts[:5]  # cap at 5 per group to save tokens
        )
        context_lines.append(f"- {group_name}: {concept_summary}")

    if not concept_groups and not concept_tree_skeleton:
        return {"draft_tree": {}}

    system_prompt = """You are a world-class patent ontologist. Your job is to organize technical concept groups extracted from real patents into a deep, logically nested technology taxonomy tree.

STRICT RULES:
1. The tree MUST start with a single root node called "Technology". Every branch must descend from it.
2. The tree MUST have a minimum depth of 5 levels and a maximum depth of 8 levels.
   Level 1: "Technology" (always the root)
   Level 2: Broad domain (e.g., "Automotive", "Medical Devices", "Energy Systems")
   Level 3: Technology area (e.g., "Electric Vehicles", "Implantable Devices")
   Level 4: Sub-system (e.g., "Battery Systems", "Power Electronics")
   Level 5: Functional group (e.g., "Thermal Management", "Charging Control")
   Level 6: Mechanism / method (e.g., "Temperature Monitoring", "Overheat Detection")
   Level 7+: Granular leaf nodes (e.g., "Battery Temperature", "Temperature Sensor")
3. Do NOT invent nodes that have no connection to the evidence provided. Every Level 4+ node must relate to at least one concept from the input.
4. The input concept groups MUST all appear somewhere in the tree as nodes. Do not drop any.
5. Output MUST be a nested JSON object. Keys are node names. Values are dictionaries of child nodes. Leaf nodes get empty dicts {}.
6. Do NOT create generic catch-all nodes like "Other", "Miscellaneous", or "Various Technologies".
7. If you are unsure where a concept belongs, place it under the most logically appropriate parent — do not hallucinate a new domain branch.

REFERENCE EXAMPLE (EV Battery Domain):
Input groups: ["Thermal Management", "Charging Control", "Temperature Sensing"]
Expected output structure:
{
  "Technology": {
    "Automotive": {
      "Electric Vehicles": {
        "Battery Systems": {
          "Battery Management": {
            "Thermal Management": {
              "Temperature Monitoring": {},
              "Overheat Detection": {}
            },
            "Charging Control": {
              "Current Regulation": {},
              "Threshold Logic": {}
            }
          }
        }
      }
    }
  }
}

IMPORTANT: The example above is for illustration only. Use the actual input concept groups and their evidence to determine the correct domain and nesting — do not blindly copy the example structure.
"""

    # If we have a nested skeleton from Phase 2, use it as a structural hint
    skeleton_hint = ""
    if concept_tree_skeleton:
        import json
        skeleton_hint = f"\n\nSTRUCTURAL HINT (nested grouping from prior step — use as a guide, not a constraint):\n{json.dumps(concept_tree_skeleton, indent=2)}"

    group_names = list(concept_groups.keys())
    user_prompt = (
        f"Build a deep hierarchical taxonomy tree for the following concept groups.\n\n"
        f"CONCEPT GROUPS WITH EVIDENCE:\n" + "\n".join(context_lines) +
        f"\n\nALL GROUP NAMES (must all appear in the tree):\n" + "\n".join(group_names) +
        skeleton_hint
    )

    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            cheap=False,
            max_tokens=16000
        )

        # Unwrap if the LLM wrapped everything under a "Technology" key at the top level
        # We want draft_tree to BE the full tree including the "Technology" root
        draft_tree = response_json

        # Validation: ensure all input groups appear in the tree
        def get_all_nodes(tree_dict):
            nodes = set()
            for k, v in tree_dict.items():
                nodes.add(k)
                if isinstance(v, dict):
                    nodes.update(get_all_nodes(v))
            return nodes

        tree_nodes = get_all_nodes(draft_tree)
        missing_groups = [g for g in group_names if g not in tree_nodes]

        if missing_groups:
            print(f"Warning: LLM dropped {len(missing_groups)} groups: {missing_groups}. Patching into 'Uncategorized'.")
            # Find the deepest reasonable place to put uncategorized nodes
            # Try to place under Technology > Uncategorized
            if "Technology" in draft_tree:
                draft_tree["Technology"].setdefault("Uncategorized", {})
                for g in missing_groups:
                    draft_tree["Technology"]["Uncategorized"][g] = {}
            else:
                draft_tree.setdefault("Uncategorized", {})
                for g in missing_groups:
                    draft_tree["Uncategorized"][g] = {}

        # Validate minimum depth
        def get_max_depth(tree_dict, current=0):
            if not tree_dict:
                return current
            return max(get_max_depth(v, current + 1) for v in tree_dict.values() if isinstance(v, dict))

        max_depth = get_max_depth(draft_tree)
        print(f"Tree depth: {max_depth} levels")
        if max_depth < 4:
            print("Warning: Tree is shallower than expected (< 4 levels). Consider reviewing the prompt or input data.")

    except Exception as e:
        print(f"Failed to build hierarchy: {e}")
        draft_tree = {}

    out_data = {"draft_tree": draft_tree}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "build_hierarchy", state, out_data)

    return out_data
