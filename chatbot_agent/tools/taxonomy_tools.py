"""
taxonomy_tools.py — Native tools for the Semantic Agentic Assistant.

Provides functions to:
- inspect_tree: Explore hierarchy paths, branches, levels, and structure.
- search_taxonomy: Semantic and keyword search across nodes, claims, and product links.
- get_node_details: Pull deep claim evidence, supporting patents, contexts, and products.
- edit_taxonomy: Register real-time hierarchy editing rules (move, rename, merge, exclude).
"""

import re
from typing import Any, Optional
from chatbot_agent.state import MappingRule, MappingRuleType


def inspect_tree(
    taxonomy: list[dict[str, Any]],
    branch: Optional[str] = None,
    max_depth: int = 3
) -> dict[str, Any]:
    """
    Explore the taxonomy hierarchy structure, branch names, levels, and node counts.
    """
    if not taxonomy:
        return {"error": "No taxonomy is currently available in the active workspace."}

    node_by_id = {n.get("node_id"): n for n in taxonomy if n.get("node_id")}
    
    # If a specific branch name was requested, find that root or parent node
    target_node = None
    if branch:
        branch_lower = branch.lower().strip()
        for n in taxonomy:
            if n.get("name", "").lower() == branch_lower or branch_lower in n.get("name", "").lower():
                target_node = n
                break

    lines = []
    total_nodes = len(taxonomy)
    root_nodes = [n for n in taxonomy if n.get("level", 0) <= 0 or not n.get("parent_node_id")]

    if target_node:
        target_id = target_node.get("node_id")
        sub_nodes = [n for n in taxonomy if n.get("parent_node_id") == target_id]
        lines.append(f"Branch: {target_node.get('name')} (Level {target_node.get('level', 1)})")
        lines.append(f"Description: {target_node.get('description', '')}")
        lines.append(f"Supporting Patents ({len(target_node.get('supporting_patent_ids', []))}): {', '.join(target_node.get('supporting_patent_ids', []))}")
        lines.append(f"Direct Child Nodes ({len(sub_nodes)}):")
        for sn in sub_nodes:
            p_count = len(sn.get("supporting_patent_ids", []))
            lines.append(f"  • {sn.get('name')} (ID: {sn.get('node_id')}, Patents: {p_count})")
        return {
            "branch_name": target_node.get("name"),
            "node_id": target_id,
            "child_count": len(sub_nodes),
            "summary": "\n".join(lines)
        }

    # Top-level tree overview
    lines.append(f"Taxonomy Hierarchy Overview (Total {total_nodes} nodes):")
    for r in root_nodes[:8]:
        r_id = r.get("node_id")
        children = [n for n in taxonomy if n.get("parent_node_id") == r_id]
        pat_count = len(r.get("supporting_patent_ids", []))
        lines.append(f"• Root: {r.get('name')} (Level {r.get('level', 0)}, Patents: {pat_count}, Direct Sub-branches: {len(children)})")
        for c in children[:5]:
            lines.append(f"    - {c.get('name')} (Patents: {len(c.get('supporting_patent_ids', []))})")
        if len(children) > 5:
            lines.append(f"    ... and {len(children) - 5} more sub-nodes")

    return {
        "total_nodes": total_nodes,
        "root_count": len(root_nodes),
        "structure": "\n".join(lines)
    }


def search_taxonomy(
    query: str,
    taxonomy: list[dict[str, Any]],
    source_data: Optional[dict[str, Any]] = None,
    top_k: int = 6
) -> list[dict[str, Any]]:
    """
    Search taxonomy nodes, patent claims, and attached product features for relevant concepts.
    """
    if not taxonomy:
        return []

    source_data = source_data or {}
    products_map = source_data.get("_products", {}) if isinstance(source_data, dict) else {}
    node_by_id = {n.get("node_id"): n for n in taxonomy if n.get("node_id")}

    query_lower = query.lower().strip()
    words = set(re.findall(r"\w+", query_lower))

    scored_nodes = []
    for node in taxonomy:
        score = 0.0
        name = node.get("name", "").lower()
        desc = node.get("description", "").lower()
        patents = [p.lower() for p in node.get("supporting_patent_ids", [])]
        prods = node.get("supporting_product_ids", [])

        # Direct exact match in name
        if query_lower in name:
            score += 15.0
        elif any(w in name for w in words):
            score += 8.0

        # Description matches
        if query_lower in desc:
            score += 6.0
        elif any(w in desc for w in words):
            score += 3.0

        # Direct patent match
        if any(query_lower == p or query_lower in p for p in patents):
            score += 20.0

        # Product matches
        for pid in prods:
            p_info = products_map.get(pid, {})
            p_name = p_info.get("product_name", "").lower()
            p_feats = " ".join(p_info.get("features", [])).lower()
            if query_lower in p_name or query_lower in p_feats:
                score += 10.0
            elif any(w in p_feats for w in words):
                score += 4.0

        if score > 0:
            scored_nodes.append((score, node))

    scored_nodes.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, node in scored_nodes[:top_k]:
        nid = node.get("node_id")
        
        # Build hierarchy breadcrumb path
        parent_names = []
        curr_p = node.get("parent_node_id")
        while curr_p and curr_p in node_by_id and len(parent_names) < 4:
            p_node = node_by_id[curr_p]
            parent_names.append(p_node.get("name", curr_p))
            curr_p = p_node.get("parent_node_id")
        branch_path = " -> ".join(reversed(parent_names + [node.get("name", "")])) if parent_names else node.get("name", "")

        results.append({
            "node_id": nid,
            "name": node.get("name"),
            "level": node.get("level"),
            "hierarchy_path": branch_path,
            "description": node.get("description"),
            "supporting_patent_ids": node.get("supporting_patent_ids", []),
            "supporting_product_ids": node.get("supporting_product_ids", []),
            "relevance_score": score
        })

    return results


def get_node_details(
    node_identifier: str,
    taxonomy: list[dict[str, Any]],
    source_data: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Retrieve deep evidence, patents, claims contexts, and product associations for a single node.
    """
    if not taxonomy:
        return {"error": "No taxonomy available."}

    source_data = source_data or {}
    products_map = source_data.get("_products", {}) if isinstance(source_data, dict) else {}
    node_by_id = {n.get("node_id"): n for n in taxonomy if n.get("node_id")}

    target = None
    ident_lower = node_identifier.lower().strip()
    
    # 1. Match by exact node_id
    if node_identifier in node_by_id:
        target = node_by_id[node_identifier]
    # 2. Match by exact name
    if not target:
        for n in taxonomy:
            if n.get("name", "").lower() == ident_lower:
                target = n
                break
    # 3. Match by partial name or contained patent ID
    if not target:
        for n in taxonomy:
            if ident_lower in n.get("name", "").lower():
                target = n
                break
            if any(ident_lower in pid.lower() for pid in n.get("supporting_patent_ids", [])):
                target = n
                break

    if not target:
        return {"error": f"Node or patent matching '{node_identifier}' was not found in the taxonomy."}

    # Trace branch breadcrumb
    parent_names = []
    curr_p = target.get("parent_node_id")
    while curr_p and curr_p in node_by_id and len(parent_names) < 5:
        p_node = node_by_id[curr_p]
        parent_names.append(p_node.get("name", curr_p))
        curr_p = p_node.get("parent_node_id")
    branch_path = " -> ".join(reversed(parent_names + [target.get("name", "")])) if parent_names else target.get("name", "")

    # Supporting patent metadata & claim contexts
    patents_detail = []
    ctx_map = target.get("contexts_by_patent", {})
    for pid in target.get("supporting_patent_ids", []):
        p_meta = source_data.get(pid, {}) if isinstance(source_data, dict) else {}
        patents_detail.append({
            "patent_id": pid,
            "title": p_meta.get("title", ""),
            "assignee": p_meta.get("assignee") or p_meta.get("applicant", "Unknown"),
            "claims_context": ctx_map.get(pid, [])
        })

    # Supporting commercial products
    products_detail = []
    for pid in target.get("supporting_product_ids", []):
        p_info = products_map.get(pid, {})
        products_detail.append({
            "product_id": pid,
            "product_name": p_info.get("product_name", pid),
            "features": p_info.get("features", [])
        })

    return {
        "node_id": target.get("node_id"),
        "name": target.get("name"),
        "level": target.get("level"),
        "hierarchy_path": branch_path,
        "description": target.get("description"),
        "total_patents": len(patents_detail),
        "patents": patents_detail,
        "aligned_products": products_detail
    }


def edit_taxonomy(
    action: str,
    source_node: str,
    target_node: Optional[str] = None,
    mapping_rules: Optional[list] = None
) -> dict[str, Any]:
    """
    Register a dynamic modification rule to move, rename, merge, or exclude a node.
    """
    valid_actions = {
        "reparent": MappingRuleType.REPARENT,
        "move": MappingRuleType.REPARENT,
        "merge": MappingRuleType.MERGE,
        "split": MappingRuleType.SPLIT,
        "rename": MappingRuleType.RENAME,
        "exclude": MappingRuleType.EXCLUDE,
        "remove": MappingRuleType.EXCLUDE,
        "prioritize": MappingRuleType.PRIORITIZE
    }

    action_clean = action.lower().strip()
    rule_type = valid_actions.get(action_clean)
    if not rule_type:
        return {"error": f"Invalid edit action '{action}'. Valid actions are: reparent, rename, merge, exclude, prioritize."}

    new_rule = MappingRule(
        rule_type=rule_type,
        source_node=source_node,
        target_node=target_node,
        applied=False,
        raw_instruction=f"{action} '{source_node}'" + (f" -> '{target_node}'" if target_node else "")
    )

    return {
        "status": "success",
        "action": rule_type.value,
        "source_node": source_node,
        "target_node": target_node,
        "message": f"Successfully registered taxonomy rule: {new_rule.raw_instruction}.",
        "rule": new_rule.model_dump()
    }
