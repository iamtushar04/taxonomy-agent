import json
from collections import Counter
from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json


def _compute_domain_backbone(canonical_concepts) -> tuple[str, dict]:
    """
    Fix 2: Aggregate domain_paths across ALL canonical concepts to find
    the most patent-evidence-supported Level 2, 3, 4 nodes.
    Returns a human-readable summary string and a raw counts dict.
    """
    all_paths = []
    for c in canonical_concepts:
        all_paths.extend(c.domain_paths)

    if not all_paths:
        return "", {}

    l2 = Counter(p[0] for p in all_paths if len(p) >= 1)
    l3 = Counter(p[1] for p in all_paths if len(p) >= 2)
    l4 = Counter(p[2] for p in all_paths if len(p) >= 3)

    total = len(all_paths)
    lines = [
        f"\nDOMAIN BACKBONE EVIDENCE (from {total} patent domain path signals):",
        "  Use these as the dominant structure for the nested skeleton.",
        "  Level 2 (Broad Domain): " + ", ".join(f"{n} ({c}x)" for n, c in l2.most_common(4)),
        "  Level 3 (Tech Area):    " + ", ".join(f"{n} ({c}x)" for n, c in l3.most_common(4)),
        "  Level 4 (Sub-system):   " + ", ".join(f"{n} ({c}x)" for n, c in l4.most_common(4)),
    ]
    return "\n".join(lines), {"l2": dict(l2), "l3": dict(l3), "l4": dict(l4)}


def group_concepts(state: TaxonomyGenerationState) -> dict:
    """
    Fix 2: Now uses domain_paths from CanonicalConcept to:
    1. Show the LLM the most frequent domain ancestry per concept (concept-level grounding).
    2. Compute an overall domain backbone from all domain paths and inject it
       into the prompt as hard evidence for the nested_skeleton structure.

    Previously: LLM had only concept name + 100-char context to make grouping decisions.
    Now: LLM also sees per-concept domain hints AND an overall backbone summary
         grounded in actual patent text.
    """
    print("--- GROUPING CONCEPTS (NESTED SKELETON) ---")
    canonical_concepts = state.get("canonical_concepts", [])

    if not canonical_concepts:
        return {"concept_groups": {}, "concept_tree_skeleton": {}}

    # FIX 2: Compute overall domain backbone from aggregated domain_paths
    backbone_summary, _ = _compute_domain_backbone(canonical_concepts)

    # FIX 2: Build richer concept lines — name + context + dominant domain hint
    concept_lines = []
    for c in canonical_concepts:
        ctx = c.supporting_contexts[0][:100] if c.supporting_contexts else "no context"

        # Derive the most commonly mentioned domain path for this concept
        domain_hint = ""
        if c.domain_paths:
            path_strs = [" > ".join(p[:3]) for p in c.domain_paths if len(p) >= 2]
            if path_strs:
                most_common_path = Counter(path_strs).most_common(1)[0][0]
                domain_hint = f" [patent domain: {most_common_path}]"

        concept_lines.append(f'"{c.name}"{domain_hint}: {ctx}')

    system_prompt = """You are an expert patent analyst and ontologist. I will give you a list of technical concepts extracted from real patents.
Each concept includes:
- A context snippet (what the concept does in the patent)
- A [patent domain] tag showing the technology ancestry path extracted directly from the patent text

Your task is TWO parts:

PART 1 — FLAT MAPPING (for internal use):
Assign each concept to a concise, technical group name (e.g., "Thermal Management", "Charging Control").
Output: { "concept_name": "Group Name", ... }

PART 2 — NESTED SKELETON (for hierarchy building):
Organize the groups from Part 1 into a nested structure reflecting real technology relationships.
- Keys are group/category names
- Values are nested dicts of sub-groups, or {} for leaf groups
- Should have 2-4 levels of nesting (group names only, NOT individual concepts)

RULES:
1. Group names must be concise and technically precise
2. Do NOT create generic categories ("Other", "Miscellaneous")
3. Respect the [patent domain] tags — they are extracted from real patent text and must guide placement
4. The nested skeleton should directly reflect the domain backbone evidence provided
5. No two groups should overlap significantly

OUTPUT FORMAT — return a single JSON object with exactly two keys:
{
  "flat_mapping": {
    "concept_name": "Group Name",
    ...
  },
  "nested_skeleton": {
    "Parent Group": {
      "Child Group": {},
      ...
    }
  }
}
"""

    user_prompt = (
        "Group the following concepts and produce both a flat mapping and a nested skeleton.\n"
        + backbone_summary  # FIX 2: inject backbone evidence
        + "\n\nCONCEPTS (with context and patent domain hints):\n"
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

        # Fallback: if LLM returned the old flat format (backwards compat)
        if not flat_mapping and not concept_tree_skeleton:
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
            print(f"Warning: {len(unmapped)} concepts not mapped to any group: {unmapped[:5]}...")

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
