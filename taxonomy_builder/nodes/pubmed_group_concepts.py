import json
from collections import Counter
from taxonomy_builder.pubmed_state import PubMedGenerationState
from pipeline.utils.llm_client import chat_json


def _compute_domain_backbone(canonical_concepts) -> str:
    """
    Aggregate domain_paths across ALL canonical concepts to find
    the most patent-evidence-supported Level 2, 3, 4 nodes.
    Returns a human-readable summary string.
    """
    all_paths = []
    for c in canonical_concepts:
        all_paths.extend(c.domain_paths)

    if not all_paths:
        return ""

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
    return "\n".join(lines)


def _deduplicate_group_names(concept_groups: dict) -> dict:
    """
    Level 2 semantic deduplication: run a second embedding pass on the
    GROUP NAMES themselves (after grouping) to merge near-synonymous groups.

    Example: "Polymerization Process" + "Polymerization Techniques" + "Polymerization Methods"
             → merged into one group, concepts from all three combined.

    Uses a HIGHER threshold (0.90) than concept deduplication (0.88) because
    group names are already canonical and should only merge on very high similarity.
    """
    if len(concept_groups) < 2:
        return concept_groups

    try:
        from sentence_transformers import SentenceTransformer, util
        # Re-use already loaded model if available (avoids re-loading ~400MB model)
        from taxonomy_builder.nodes.deduplicate_concepts import get_embedding_model
        model = get_embedding_model()
    except Exception as e:
        print(f"Group dedup: embedding model not available ({e}). Skipping.")
        return concept_groups

    group_names = list(concept_groups.keys())
    embeddings = model.encode(group_names, convert_to_tensor=True)

    GROUP_DEDUP_THRESHOLD = 0.90  # Stricter than concept-level (0.88)
    communities = util.community_detection(embeddings, min_community_size=1, threshold=GROUP_DEDUP_THRESHOLD)

    merged_groups: dict = {}
    for community in communities:
        names_in_cluster = [group_names[idx] for idx in community]

        # Pick canonical name = the longest name (most descriptive)
        canonical_name = max(names_in_cluster, key=len)

        # Merge all canonical concepts from all groups in this cluster
        merged_concepts = []
        seen_concept_names: set[str] = set()
        for name in names_in_cluster:
            for c in concept_groups.get(name, []):
                if c.name not in seen_concept_names:
                    merged_concepts.append(c)
                    seen_concept_names.add(c.name)

        merged_groups[canonical_name] = merged_concepts

    n_merged = len(group_names) - len(merged_groups)
    if n_merged > 0:
        print(f"Group-level deduplication: merged {n_merged} near-duplicate groups "
              f"({len(group_names)} -> {len(merged_groups)} groups).")
    else:
        print(f"Group-level deduplication: no near-duplicate groups found ({len(group_names)} groups are all unique).")

    return merged_groups


def group_concepts(state: PubMedGenerationState) -> dict:
    """
    Improvements applied:
    1. Per-concept domain hints (patent domain: X > Y) in the grouping prompt.
    2. Overall domain backbone evidence injected from aggregated domain_paths.
    3. NEW: Level 2 group-name semantic deduplication after grouping — merges
       near-synonymous groups like "Polymerization Process" / "Polymerization Techniques".
    """
    print("--- GROUPING CONCEPTS (NESTED SKELETON) ---")
    canonical_concepts = state.get("canonical_concepts", [])

    if not canonical_concepts:
        return {"concept_groups": {}, "concept_tree_skeleton": {}}

    # Compute overall domain backbone from aggregated domain_paths
    backbone_summary = _compute_domain_backbone(canonical_concepts)

    # Build richer concept lines — name + context + dominant domain hint
    concept_lines = []
    for c in canonical_concepts:
        ctx = c.supporting_contexts[0][:100] if c.supporting_contexts else "no context"

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
5. No two groups should overlap significantly — if two groups mean the same thing, use ONE name

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
        + backbone_summary
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

        # Fallback: backwards compat with old flat format
        if not flat_mapping and not concept_tree_skeleton:
            flat_mapping = response_json
            concept_tree_skeleton = {}

        # Build concept_groups: group_name → list[CanonicalConcept]
        concept_groups: dict = {}
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

        # ── Level 2 Group Deduplication ──────────────────────────────────────
        concept_groups = _deduplicate_group_names(concept_groups)

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
