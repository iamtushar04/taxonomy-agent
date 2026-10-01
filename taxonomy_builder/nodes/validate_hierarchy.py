from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json


def _get_all_nodes(tree_dict: dict) -> set:
    """Recursively collect all node names from the tree."""
    nodes = set()
    for k, v in tree_dict.items():
        nodes.add(k)
        if isinstance(v, dict):
            nodes.update(_get_all_nodes(v))
    return nodes


def _get_max_depth(tree_dict: dict, current: int = 0) -> int:
    """Get the maximum depth of a nested dict tree."""
    if not tree_dict:
        return current
    return max(
        _get_max_depth(v, current + 1)
        for v in tree_dict.values()
        if isinstance(v, dict)
    )


def _get_root_keys(tree_dict: dict) -> list[str]:
    return list(tree_dict.keys())


def validate_hierarchy(state: TaxonomyGenerationState) -> dict:
    """
    Phase 4 — Validation Gate between build_hierarchy and enrich_nodes.

    Checks:
    1. Tree is rooted at 'Technology' (or a single sensible root)
    2. Minimum depth of 4 levels
    3. All concept groups appear somewhere in the tree
    4. No orphaned groups — auto-patches missing ones

    If the tree is critically broken (depth < 3 or no Technology root),
    triggers a single repair LLM call to fix it.
    """
    print("--- VALIDATING HIERARCHY ---")
    draft_tree = state.get("draft_tree", {})
    concept_groups = state.get("concept_groups", {})
    group_names = list(concept_groups.keys())

    issues = []
    patched = False

    # ── Check 1: Single root named "Technology" ──────────────────────────────
    root_keys = _get_root_keys(draft_tree)
    has_technology_root = "Technology" in root_keys

    if not has_technology_root:
        issues.append(f"Missing 'Technology' root. Found roots: {root_keys}")
        # Auto-wrap under Technology if there's a reasonable single root
        if len(root_keys) == 1:
            draft_tree = {"Technology": draft_tree}
            patched = True
            print(f"Auto-patched: wrapped '{root_keys[0]}' under 'Technology'.")
        elif len(root_keys) > 1:
            draft_tree = {"Technology": draft_tree}
            patched = True
            print(f"Auto-patched: wrapped {len(root_keys)} roots under 'Technology'.")

    # ── Check 2: Minimum depth ───────────────────────────────────────────────
    max_depth = _get_max_depth(draft_tree)
    print(f"Tree depth: {max_depth} levels")

    if max_depth < 3:
        issues.append(f"Tree too shallow: {max_depth} levels (minimum 4 required).")

    # ── Check 3: All groups present ──────────────────────────────────────────
    tree_nodes = _get_all_nodes(draft_tree)
    missing_groups = [g for g in group_names if g not in tree_nodes]

    if missing_groups:
        issues.append(f"{len(missing_groups)} concept groups missing from tree: {missing_groups[:5]}")
        # Auto-patch: place missing groups under Technology > Uncategorized
        if "Technology" in draft_tree:
            draft_tree["Technology"].setdefault("Uncategorized", {})
            for g in missing_groups:
                draft_tree["Technology"]["Uncategorized"][g] = {}
        else:
            draft_tree.setdefault("Uncategorized", {})
            for g in missing_groups:
                draft_tree["Uncategorized"][g] = {}
        patched = True
        print(f"Auto-patched: added {len(missing_groups)} missing groups to Uncategorized.")

    # ── Repair Call: if tree is critically broken, ask LLM to fix it ─────────
    needs_repair = max_depth < 3 and not patched

    if needs_repair:
        print("Tree critically shallow — triggering LLM repair call...")
        import json

        repair_prompt_system = """You are an expert patent ontologist. The taxonomy tree below is too shallow (less than 4 levels).
Your task is to deepen it while preserving ALL existing nodes.

RULES:
1. The tree MUST start with "Technology" as the single root node.
2. Minimum 5 levels of depth required.
3. Do NOT remove any existing nodes — only add intermediate parent nodes to create depth.
4. Output the corrected tree as a nested JSON object.
"""
        repair_prompt_user = (
            f"Current shallow tree:\n{json.dumps(draft_tree, indent=2)}\n\n"
            f"All concept groups that MUST appear in the final tree:\n" + "\n".join(group_names)
        )

        try:
            repaired = chat_json(
                messages=[
                    {"role": "system", "content": repair_prompt_system},
                    {"role": "user", "content": repair_prompt_user}
                ],
                cheap=False,
                max_tokens=8000
            )
            draft_tree = repaired
            new_depth = _get_max_depth(draft_tree)
            print(f"Repaired tree depth: {new_depth} levels")
            patched = True
        except Exception as e:
            print(f"Repair call failed: {e}. Keeping current tree.")

    # ── Summary ──────────────────────────────────────────────────────────────
    if issues:
        print(f"Validation found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        if patched:
            print("  All issues auto-patched.")
    else:
        print("Hierarchy validation passed.")

    out_data = {"draft_tree": draft_tree}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "validate_hierarchy", state, out_data)

    return out_data
