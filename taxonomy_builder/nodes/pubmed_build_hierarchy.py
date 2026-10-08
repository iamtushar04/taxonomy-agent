import json
from collections import Counter
from taxonomy_builder.pubmed_state import PubMedGenerationState
from pipeline.utils.llm_client import chat_json


# ── Stage A: Build the backbone ───────────────────────────────────────────────

def _build_backbone(all_domain_paths: list[list[str]]) -> dict:
    """
    Stage A of two-stage hierarchy building.

    Uses ONLY the aggregated domain_path evidence (extracted from actual patent text)
    to build a lightweight Level 1-4 backbone tree.

    The output is a small nested dict (10-20 nodes max), so the LLM response is
    tiny and there is ZERO risk of token overflow here.
    """
    if not all_domain_paths:
        return {"Technology": {}}

    l2 = Counter(p[0] for p in all_domain_paths if len(p) >= 1)
    l3 = Counter(p[1] for p in all_domain_paths if len(p) >= 2)
    l4 = Counter(p[2] for p in all_domain_paths if len(p) >= 3)
    total = len(all_domain_paths)

    evidence_block = (
        f"Evidence from {total} patent domain path signals:\n"
        f"  Level 2 (Broad Domain): " + ", ".join(f"{n} ({c}x)" for n, c in l2.most_common(6)) + "\n"
        f"  Level 3 (Tech Area):    " + ", ".join(f"{n} ({c}x)" for n, c in l3.most_common(6)) + "\n"
        f"  Level 4 (Sub-system):   " + ", ".join(f"{n} ({c}x)" for n, c in l4.most_common(6))
    )

    system = """You are a taxonomy architect. Your job is to build the STRUCTURAL BACKBONE of a patent taxonomy.

IMPORTANT: Output ONLY the backbone skeleton (Level 1-4). Do NOT include specific concept groups yet.
The concept groups will be inserted in a separate step.

RULES:
1. Root node MUST be "Technology" (Level 1)
2. Build exactly 3-4 levels deep using the domain evidence provided
3. Include ONLY nodes that are directly supported by the evidence counts
4. Output a nested JSON object where all leaf values are {}
5. Keep it concise — maximum 5 nodes per level

EXAMPLE OUTPUT (for a polymer chemistry domain):
{
  "Technology": {
    "Chemistry": {
      "Polymer Chemistry": {
        "Polymerization Processes": {},
        "Catalyst Systems": {},
        "Polymer Properties": {}
      }
    }
  }
}
"""

    user = (
        "Build the backbone skeleton for a patent taxonomy using the following domain evidence.\n\n"
        + evidence_block
        + "\n\nOutput the backbone as a nested JSON object (Level 1-4 only)."
    )

    try:
        backbone = chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            cheap=False,
            max_tokens=2000   # Backbone is small — 2000 tokens is plenty
        )
        # Ensure Technology root
        if "Technology" not in backbone:
            backbone = {"Technology": backbone}
        return backbone
    except Exception as e:
        print(f"Backbone build failed: {e}. Using minimal fallback backbone.")
        return {"Technology": {}}


# ── Stage B: Place groups into backbone ───────────────────────────────────────

def _navigate_to_path(tree: dict, path: list[str]) -> dict:
    """Navigate the tree following `path`, creating missing nodes as needed."""
    node = tree
    for step in path:
        if step not in node:
            node[step] = {}
        val = node[step]
        if not isinstance(val, dict):
            node[step] = {}
        node = node[step]
    return node


def _place_groups_in_backbone(
    backbone: dict,
    concept_groups: dict,
    context_lines: list[str],
) -> dict:
    import copy
    import difflib
    
    BATCH_SIZE = 10
    group_names = list(concept_groups.keys())
    context_lookup = {}
    for line in context_lines:
        if line.startswith("- "):
            parts = line[2:].split(":", 1)
            if len(parts) == 2:
                context_lookup[parts[0].strip()] = parts[1].strip()

    result_tree = copy.deepcopy(backbone)
    total_batches = (len(group_names) + BATCH_SIZE - 1) // BATCH_SIZE
    placed = 0

    for batch_idx in range(0, len(group_names), BATCH_SIZE):
        batch = group_names[batch_idx : batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1

        batch_context = []
        for g in batch:
            ctx = context_lookup.get(g, "no context")
            batch_context.append(f"- {g}: {ctx}")

        system = f"""You are a taxonomy expert. You have a backbone taxonomy tree and a list of concept groups that must be inserted into it.

For each group, output the EXACT path (list of node names from root) where the group should be inserted as a child.

CRITICAL RULES:
1. The path MUST start with "Technology"
2. The path MUST only use node names that EXIST in the backbone provided
3. You MUST output a JSON object containing EXACTLY these {len(batch)} keys:
{json.dumps(batch, indent=2)}
4. Choose the most logically appropriate parent for each group. If unsure, place under the closest relevant parent.

OUTPUT FORMAT:
Return a single JSON object mapping each group name to its path:
{{
  "{batch[0]}": ["Technology", "Level2", "Level3"],
  ...
}}
"""

        user = (
            f"BACKBONE TREE:\n{json.dumps(result_tree, indent=2)}\n\n"
            f"CONCEPT GROUPS TO PLACE:\n"
            + "\n".join(batch_context)
            + "\n\nOutput the placement path for each group."
        )

        try:
            placements = chat_json(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                cheap=False,
                max_tokens=1500
            )

            # Map the LLM's returned keys in case of slight hallucination
            llm_keys = list(placements.keys())
            
            for group_name in batch:
                # 1. Try exact match
                path = placements.get(group_name)
                
                # 2. Try fuzzy match if exact fails
                if not path:
                    matches = difflib.get_close_matches(group_name, llm_keys, n=1, cutoff=0.6)
                    if matches:
                        path = placements.get(matches[0])
                        print(f"  Fuzzy matched LLM key '{matches[0]}' to expected group '{group_name}'")

                if path:
                    # Fix LLM hallucinating a string instead of a list (e.g. "Technology > Heating")
                    if isinstance(path, str):
                        if " > " in path:
                            path = path.split(" > ")
                        elif "/" in path:
                            path = path.split("/")
                        else:
                            path = [path]
                            
                if path and isinstance(path, list) and len(path) >= 1:
                    parent_node = _navigate_to_path(result_tree, path)
                    parent_node[group_name] = {}
                    placed += 1
                else:
                    result_tree.setdefault("Technology", {})[group_name] = {}
                    placed += 1
                    print(f"  No valid path for '{group_name}' — attached to Technology root.")

        except Exception as e:
            print(f"  Placement batch {batch_num} failed: {e}. Attaching {len(batch)} groups to Technology root.")
            for group_name in batch:
                result_tree.setdefault("Technology", {})[group_name] = {}
                placed += 1

    print(f"Placed {placed}/{len(group_names)} groups into backbone.")
    return result_tree


def _prune_empty_branches(tree: dict, valid_leaf_names: set[str]) -> bool:
    """
    Recursively remove branches that do not contain any valid leaf nodes.
    Returns True if the tree has any contents left, False if it is empty.
    """
    keys_to_delete = []
    
    for k, v in tree.items():
        if not v:  # It's an empty dict (leaf)
            if k not in valid_leaf_names:
                keys_to_delete.append(k)
        else:
            # It's a branch, prune its children recursively
            has_children_left = _prune_empty_branches(v, valid_leaf_names)
            if not has_children_left:
                keys_to_delete.append(k)
                
    for k in keys_to_delete:
        del tree[k]
        
    return len(tree) > 0


# ── Main node ─────────────────────────────────────────────────────────────────

def build_hierarchy(state: PubMedGenerationState) -> dict:
    """
    Two-stage hierarchy building — eliminates the 'LLM dropped N groups' problem.

    Stage A: Build a small, evidence-grounded backbone (Level 1-4) from domain_paths.
             Output is tiny (~2000 tokens) — zero overflow risk.

    Stage B: Place EVERY concept group into the backbone in batches of 10.
             Each batch is a small, focused call — zero overflow risk.
             Since we explicitly iterate over every group, none can be dropped.

    Previously: One massive call trying to output a 10,000+ token JSON with all
                groups already nested. Groups at the bottom were silently dropped.
    """
    print("--- BUILDING HIERARCHY ---")

    concept_tree_skeleton = state.get("concept_tree_skeleton", {})
    concept_groups = state.get("concept_groups", {})

    if not concept_groups and not concept_tree_skeleton:
        return {"draft_tree": {}}

    # Build context lines for Stage B placement calls
    context_lines = []
    for group_name, concepts in concept_groups.items():
        concept_summary = "; ".join(
            f"{c.name} ({c.supporting_contexts[0][:80] if c.supporting_contexts else 'no context'})"
            for c in concepts[:5]
        )
        context_lines.append(f"- {group_name}: {concept_summary}")

    # Aggregate domain_paths for backbone evidence
    all_domain_paths = []
    for concepts in concept_groups.values():
        for c in concepts:
            if hasattr(c, "domain_paths") and c.domain_paths:
                all_domain_paths.extend(c.domain_paths)

    # ── Stage A: Build backbone ───────────────────────────────────────────────
    print("  Stage A: Building evidence-grounded backbone...")
    backbone = _build_backbone(all_domain_paths)

    # ── Stage B: Place all groups into backbone ───────────────────────────────
    print(f"  Stage B: Placing {len(concept_groups)} groups into backbone (batches of 10)...")
    draft_tree = _place_groups_in_backbone(backbone, concept_groups, context_lines)

    # ── Post-Processing: Prune Empty Backbone Folders ─────────────────────────
    valid_group_names = set(concept_groups.keys())
    _prune_empty_branches(draft_tree, valid_group_names)
    # Ensure Technology root wasn't accidentally deleted if somehow totally empty
    if "Technology" not in draft_tree:
        draft_tree["Technology"] = {}

    # ── Validation ────────────────────────────────────────────────────────────
    def get_all_nodes(tree_dict):
        nodes = set()
        for k, v in tree_dict.items():
            nodes.add(k)
            if isinstance(v, dict):
                nodes.update(get_all_nodes(v))
        return nodes

    def get_max_depth(tree_dict, current=0):
        if not tree_dict:
            return current
        return max(get_max_depth(v, current + 1) for v in tree_dict.values() if isinstance(v, dict))

    tree_nodes = get_all_nodes(draft_tree)
    missing_groups = [g for g in concept_groups if g not in tree_nodes]

    if missing_groups:
        # This should never happen with Stage B, but handle defensively
        print(f"Warning: {len(missing_groups)} groups still missing after placement — patching to Technology root.")
        draft_tree.setdefault("Technology", {})
        for g in missing_groups:
            draft_tree["Technology"][g] = {}

    max_depth = get_max_depth(draft_tree)
    print(f"Tree depth: {max_depth} levels")
    if max_depth < 4:
        print("Warning: Tree is shallower than expected (< 4 levels). Backbone may need richer domain evidence.")

    out_data = {"draft_tree": draft_tree}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "build_hierarchy", state, out_data)

    return out_data
