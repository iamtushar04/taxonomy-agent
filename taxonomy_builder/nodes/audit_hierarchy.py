import copy
import json
import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json
from taxonomy_builder.utils.tracer import log_node_event

# Ensure backend/.env is accessible for dynamic configuration of AUDITOR_MODEL
_BACKEND_ENV = Path(__file__).resolve().parents[2] / "web_app" / "backend" / ".env"
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


def _get_auditor_model() -> str:
    """
    Reads the chosen model for the taxonomy auditor dynamically from backend/.env.
    Allows instant runtime model switching without restarting the backend server.
    """
    from dotenv import dotenv_values

    backend_model = None
    if _BACKEND_ENV.exists():
        env_map = dotenv_values(_BACKEND_ENV)
        backend_model = env_map.get("AUDITOR_MODEL") or env_map.get("TAXONOMY_AUDITOR_MODEL")

    root_model = None
    if not backend_model and _ROOT_ENV.exists():
        env_map = dotenv_values(_ROOT_ENV)
        root_model = env_map.get("AUDITOR_MODEL") or env_map.get("TAXONOMY_AUDITOR_MODEL")

    return (
        backend_model
        or root_model
        or os.environ.get("AUDITOR_MODEL")
        or os.environ.get("TAXONOMY_AUDITOR_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o-mini"
    )


def _collect_tree_structure(tree: dict) -> tuple[dict[str, list[str]], set[str], set[str]]:
    """
    Traverses tree and returns:
    1. parent_to_children: mapping of parent_name -> list of child_names
    2. leaf_concepts: set of all leaf node names
    3. parent_nodes: set of all intermediate/parent node names
    """
    parent_to_children: dict[str, list[str]] = {}
    leaf_concepts: set[str] = set()
    parent_nodes: set[str] = set()

    def _traverse(current_dict: dict, parent_name: str = "Technology"):
        if not isinstance(current_dict, dict):
            return
        
        children = []
        for k, v in current_dict.items():
            children.append(k)
            if isinstance(v, dict) and v:
                parent_nodes.add(k)
                _traverse(v, k)
            else:
                leaf_concepts.add(k)
        if parent_name:
            parent_to_children[parent_name] = children

    tech_root = tree.get("Technology", tree)
    parent_nodes.add("Technology")
    _traverse(tech_root, "Technology")

    return parent_to_children, leaf_concepts, parent_nodes


def _prune_cross_branch_duplicates(tree: dict) -> tuple[dict, int]:
    """
    Deterministic pass: finds any leaf node that appears in multiple branches.
    Keeps the deepest / first occurrence and prunes the duplicates.
    """
    seen_leaves: dict[str, tuple[list[str], dict]] = {}
    duplicates_removed = 0

    def _traverse(subtree: dict, current_path: list[str]):
        nonlocal duplicates_removed
        for k in list(subtree.keys()):
            v = subtree[k]
            new_path = current_path + [k]
            if not isinstance(v, dict) or not v:
                # Leaf node
                k_norm = k.lower().strip()
                if k_norm in seen_leaves:
                    prev_path, prev_sub = seen_leaves[k_norm]
                    # Keep the deeper path, prune shallower
                    if len(new_path) >= len(prev_path):
                        if k in prev_sub:
                            del prev_sub[k]
                            duplicates_removed += 1
                        seen_leaves[k_norm] = (new_path, subtree)
                    else:
                        del subtree[k]
                        duplicates_removed += 1
                else:
                    seen_leaves[k_norm] = (new_path, subtree)
            else:
                _traverse(v, new_path)

    _traverse(tree, [])
    return tree, duplicates_removed


def _prune_empty_parents(tree: dict, valid_concepts: set[str]) -> dict:
    """
    Recursively removes parent container categories that were left with zero children
    after duplicate pruning or node relocations, while strictly preserving leaf concepts and root.
    """
    if not isinstance(tree, dict):
        return tree

    for k in list(tree.keys()):
        v = tree[k]
        if isinstance(v, dict) and k not in valid_concepts:
            _prune_empty_parents(v, valid_concepts)
            if not v and k != "Technology":
                del tree[k]
    return tree


def _detach_node(tree: dict, node_name: str, parent_name: str | None = None) -> Any:
    """
    Searches for and removes node_name under parent_name (or anywhere if parent_name is None).
    Returns the detached node value (or None if not found).
    """
    if not isinstance(tree, dict):
        return None

    for k, v in list(tree.items()):
        if parent_name and k == parent_name and isinstance(v, dict):
            if node_name in v:
                detached = v[node_name]
                del v[node_name]
                return detached
        elif not parent_name and k == node_name:
            detached = v
            del tree[k]
            return detached
        elif isinstance(v, dict):
            detached = _detach_node(v, node_name, parent_name)
            if detached is not None:
                return detached
    return None


def _attach_node(tree: dict, target_parent: str, node_name: str, node_value: Any) -> bool:
    """
    Searches for target_parent in tree and attaches node_name: node_value into it.
    Returns True if successfully attached.
    """
    if not isinstance(tree, dict):
        return False

    for k, v in tree.items():
        if k == target_parent and isinstance(v, dict):
            v[node_name] = node_value
            return True
        elif isinstance(v, dict):
            if _attach_node(v, target_parent, node_name, node_value):
                return True
    return False


def audit_hierarchy(state: TaxonomyGenerationState) -> dict:
    """
    Self-Refining Ontology Auditor Agent Node.
    
    Triggered after build_hierarchy:
    1. Runs a deterministic cross-branch leaf deduplication pass.
    2. Gathers whitelists of valid concepts and parents (prevents hallucination).
    3. Audits the parent-child relationships per technological pillar.
    4. Outputs an Action-Diff of MOVE operations.
    5. Deterministically executes only valid moves without renaming or dropping nodes.
    """
    run_id = state.get("run_id", "default")
    try:
        # pyrefly: ignore [missing-import]
        from services.run_stage_service import set_run_stage
        set_run_stage(run_id, "auditing_hierarchy")
    except Exception:
        pass

    auditor_model = _get_auditor_model()
    print(f"--- AUDITING TAXONOMY HIERARCHY (Model: {auditor_model}) ---")
    draft_tree = state.get("draft_tree", {})
    if not draft_tree or not isinstance(draft_tree, dict):
        print("[audit_hierarchy] Warning: Empty draft tree. Skipping audit.")
        return {"draft_tree": draft_tree}

    tree_copy = copy.deepcopy(draft_tree)

    # ── Stage 1: Deterministic Cross-Branch Leaf Deduplication ────────────────
    tree_copy, dupes_pruned = _prune_cross_branch_duplicates(tree_copy)
    if dupes_pruned > 0:
        print(f"[audit_hierarchy] Pruned {dupes_pruned} duplicate leaf node(s) across branches.")

    # ── Stage 2: Whitelist Extraction ─────────────────────────────────────────
    parent_map, tree_leaves, valid_parents = _collect_tree_structure(tree_copy)
    
    # 1. Concept groups placed in draft_tree
    concept_groups = state.get("concept_groups", {})
    group_names = set(concept_groups.keys()) if isinstance(concept_groups, dict) else set()

    # 2. Canonical concepts
    canonical_list = state.get("canonical_concepts", [])
    canonical_names = set()
    if canonical_list:
        for c in canonical_list:
            if hasattr(c, "name"):
                canonical_names.add(c.name)
            elif isinstance(c, dict) and "name" in c:
                canonical_names.add(c["name"])
    
    # Crucial: valid_concepts MUST include all concept groups, tree leaves, and canonical names
    # This guarantees concept groups placed by build_hierarchy are never mistaken for empty containers
    valid_concepts = set(tree_leaves) | group_names | canonical_names

    if len(valid_concepts) < 4:
        print("[audit_hierarchy] Very small tree (<4 concepts). Skipping LLM re-parenting.")
        out_data = {"draft_tree": tree_copy}
        log_node_event(state.get("run_id", "default"), "audit_hierarchy", state, out_data)
        return out_data

    # ── Stage 3: Pillar-by-Pillar Action-Diff LLM Audit ────────────────────────
    tech_root = tree_copy.get("Technology", tree_copy)
    pillars = [k for k, v in tech_root.items() if isinstance(v, dict)]

    total_moves_applied = 0
    total_moves_rejected = 0

    for pillar_name in pillars:
        pillar_subtree = tech_root[pillar_name]
        p_map, p_concepts, p_parents = _collect_tree_structure({pillar_name: pillar_subtree})
        if len(p_concepts) < 3:
            continue

        # Format a clear, readable representation of this pillar's hierarchy
        branch_lines = []
        for p, children in p_map.items():
            if children:
                branch_lines.append(f"Parent Category [{p}]:")
                for c in children:
                    branch_lines.append(f"  - {c}")

        branch_text = "\n".join(branch_lines)
        eligible_parents = sorted(list(valid_parents - {"Technology"}))

        prompt = (
            "You are a strict taxonomy auditor and patent ontologist.\n"
            f"Review the technological hierarchy for the pillar: '{pillar_name}'.\n\n"
            f"CURRENT BRANCH HIERARCHY:\n{branch_text}\n\n"
            f"AVAILABLE TARGET PARENTS (Whitelist):\n" + "\n".join(f"- {p}" for p in eligible_parents) + "\n\n"
            "TASK:\n"
            "Identify if any child concept is placed under the logically WRONG parent and should be moved to a more appropriate parent from the whitelist.\n\n"
            "STRICT RULES (Violations will cause pipeline failure):\n"
            "1. DO NOT invent new node names. DO NOT rename existing concepts.\n"
            "2. 'concept' MUST be an exact verbatim string from the concepts above.\n"
            "3. 'to_parent' MUST be an exact verbatim string from the Available Target Parents list.\n"
            "4. Only suggest a move if there is a CLEAR technological/scientific mismatch (e.g. a sterilization parameter placed under resin polymerization).\n"
            "5. If the current hierarchy is logically sound, return an empty list.\n\n"
            "OUTPUT FORMAT (JSON ONLY):\n"
            "{\n"
            '  "moves": [\n'
            '    {\n'
            '      "concept": "Exact Concept Name",\n'
            '      "from_parent": "Exact Current Parent",\n'
            '      "to_parent": "Exact Target Parent",\n'
            '      "reason": "1-sentence justification"\n'
            '    }\n'
            '  ]\n'
            "}\n"
        )

        try:
            audit_result = chat_json(
                messages=[{"role": "user", "content": prompt}],
                model=auditor_model,
                max_tokens=2000
            )
            moves = audit_result.get("moves", []) if isinstance(audit_result, dict) else []

            # ── Stage 4: Deterministic Python Execution Gate ───────────────────
            for m in moves:
                if not isinstance(m, dict):
                    continue
                c_name = m.get("concept")
                from_p = m.get("from_parent")
                to_p = m.get("to_parent")
                reason = m.get("reason", "")

                # Strict Whitelist Validations
                if not c_name or c_name not in valid_concepts:
                    total_moves_rejected += 1
                    continue
                if not to_p or to_p not in valid_parents:
                    total_moves_rejected += 1
                    continue
                if from_p and from_p == to_p:
                    continue

                # Safely detach and re-attach
                detached_val = _detach_node(tree_copy, c_name, from_p)
                if detached_val is not None:
                    attached = _attach_node(tree_copy, to_p, c_name, detached_val)
                    if attached:
                        total_moves_applied += 1
                        print(f"[audit_hierarchy] Relocated '{c_name}' from '{from_p}' -> '{to_p}' ({reason})")
                    else:
                        # Revert back to original parent if attach failed
                        _attach_node(tree_copy, from_p, c_name, detached_val)
                        total_moves_rejected += 1
                else:
                    total_moves_rejected += 1

        except Exception as pillar_err:
            print(f"[audit_hierarchy] Note: Pillar '{pillar_name}' audit skipped due to error: {pillar_err}")

    # ── Stage 5: Clean empty parent containers ────────────────────────────────
    tree_copy = _prune_empty_parents(tree_copy, valid_concepts)

    print(f"[audit_hierarchy] Audit finished: {total_moves_applied} concept(s) relocated, {total_moves_rejected} rejected, {dupes_pruned} duplicates pruned.")

    out_data = {"draft_tree": tree_copy}
    log_node_event(state.get("run_id", "default"), "audit_hierarchy", state, out_data)

    return out_data
