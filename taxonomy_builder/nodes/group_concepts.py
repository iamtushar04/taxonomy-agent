from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json


def group_concepts(state: TaxonomyGenerationState) -> dict:
    """
    Phase 2 Fix:
    - Previously produced a flat concept → group_name mapping.
    - Now produces TWO outputs:
      1. concept_groups: dict[group_name, list[CanonicalConcept]]  (unchanged format, used by enrich_nodes)
      2. concept_tree_skeleton: nested dict of group → subgroup → concepts
         (new, used by build_hierarchy as a structural hint)
    
    The nested skeleton gives build_hierarchy the parent-child group relationships
    it needs to build a 5-7 level deep tree instead of guessing from flat names.
    """
    print("--- GROUPING CONCEPTS (NESTED SKELETON) ---")
    canonical_concepts = state.get("canonical_concepts", [])

    if not canonical_concepts:
        return {"concept_groups": {}, "concept_tree_skeleton": {}}

    # Build a richer input: name + first supporting context snippet
    concept_lines = []
    for c in canonical_concepts:
        ctx = c.supporting_contexts[0][:100] if c.supporting_contexts else "no context"
        concept_lines.append(f'"{c.name}": {ctx}')

    system_prompt = """You are an expert patent analyst and ontologist. I will give you a list of technical concepts extracted from real patents, each with a short context snippet.

Your task is TWO parts:

PART 1 — FLAT MAPPING (for internal use):
Assign each concept to a concise, technical group name (e.g., "Thermal Management", "Charging Control").
Output this as a flat JSON object: { "concept_name": "Group Name", ... }

PART 2 — NESTED SKELETON (for hierarchy building):
Organize the groups you created in Part 1 into a nested structure that reflects real technology relationships.
Show which groups belong UNDER which parent groups. This is the backbone of the final taxonomy.
Output this as a nested JSON object where:
  - Keys are group/category names
  - Values are either:
    - A nested dict of sub-groups (if this group has children)
    - An empty dict {} (if this is a leaf group)

RULES FOR BOTH PARTS:
1. Group names must be concise and technically meaningful (e.g., "Mechanical Properties", not "Properties of Mechanical Things")
2. Do NOT create generic categories ("Other", "Miscellaneous")
3. Ensure no two groups overlap significantly
4. The nested skeleton should have 2-4 levels of nesting (groups within groups) — NOT individual concepts, just group names
5. Concepts should NOT appear in the skeleton — only group names

OUTPUT FORMAT — return a single JSON object with exactly two keys:
{
  "flat_mapping": {
    "Tensile Strength": "Mechanical Properties",
    "Modulus": "Mechanical Properties",
    "Battery Temperature": "Thermal Management",
    "Temperature Sensor": "Thermal Sensing"
  },
  "nested_skeleton": {
    "Battery Systems": {
      "Battery Management": {
        "Thermal Management": {},
        "Charging Control": {}
      },
      "Battery Sensing": {
        "Thermal Sensing": {}
      }
    }
  }
}
"""

    user_prompt = (
        "Group the following concepts and produce both a flat mapping and a nested skeleton:\n\n"
        + "\n".join(concept_lines)
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

        flat_mapping = response_json.get("flat_mapping", {})
        concept_tree_skeleton = response_json.get("nested_skeleton", {})

        # Fallback: if LLM returned the old flat format (just concept→group at top level)
        if not flat_mapping and not concept_tree_skeleton:
            # Try treating the whole response as a flat mapping (backwards compat)
            flat_mapping = response_json
            concept_tree_skeleton = {}

        # Build concept_groups: group_name → list[CanonicalConcept]
        concept_groups = {}
        for c in canonical_concepts:
            g_name = flat_mapping.get(c.name)
            if g_name:
                if g_name not in concept_groups:
                    concept_groups[g_name] = []
                concept_groups[g_name].append(c)

        # Log coverage
        unmapped = [c.name for c in canonical_concepts if c.name not in flat_mapping]
        if unmapped:
            print(f"Warning: {len(unmapped)} concepts were not mapped to any group: {unmapped[:5]}...")

        print(f"Produced {len(concept_groups)} concept groups and a skeleton with {len(concept_tree_skeleton)} top-level branches.")

    except Exception as e:
        print(f"Failed to group concepts: {e}")
        concept_groups = {}
        concept_tree_skeleton = {}

    out_data = {
        "concept_groups": concept_groups,
        "concept_tree_skeleton": concept_tree_skeleton,
    }

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "group_concepts", state, out_data)

    return out_data
