from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json
import uuid


def flatten_and_enrich_tree(tree: dict, parent_id: str | None, current_level: int, concept_groups: dict, descriptions: dict, concept_by_name: dict) -> list[dict]:
    flat_nodes = []

    for node_name, children in tree.items():
        node_id = f"T_{str(uuid.uuid4())[:8]}"

        supporting_patents = set()

        # Group node: attach patents from all canonical concepts in this group
        if node_name in concept_groups:
            for canonical_concept in concept_groups[node_name]:
                for pid in canonical_concept.supporting_patent_ids:
                    supporting_patents.add(pid)

        # Granular leaf node: attach patents from the canonical concept by name
        if node_name in concept_by_name:
            for pid in concept_by_name[node_name].supporting_patent_ids:
                supporting_patents.add(pid)

        node_dict = {
            "node_id": node_id,
            "parent_node_id": parent_id,
            "name": node_name,
            "level": current_level,
            "description": descriptions.get(node_name, f"Patent information related to {node_name}."),
            "supporting_patent_ids": list(supporting_patents)
        }

        flat_nodes.append(node_dict)

        # Recursively process children
        if isinstance(children, dict) and children:
            child_nodes = flatten_and_enrich_tree(
                tree=children,
                parent_id=node_id,
                current_level=current_level + 1,
                concept_groups=concept_groups,
                descriptions=descriptions,
                concept_by_name=concept_by_name
            )
            flat_nodes.extend(child_nodes)

    return flat_nodes


def bubble_up_patents(flat_nodes: list[dict]) -> list[dict]:
    """
    Fix 4: For every node, propagate all descendant patent IDs upward to ancestors.

    Previously: Only leaf nodes and matched group nodes had supporting_patent_ids.
                Parent nodes at Level 2/3/4 always had supporting_patent_ids = [].
    Now: Every parent node accumulates the union of all patents from its subtree.
         This makes every node in the taxonomy meaningful for patent search/navigation.
    """
    if not flat_nodes:
        return flat_nodes

    # Build lookup maps
    node_map = {n["node_id"]: n for n in flat_nodes}

    # Build parent → children map
    children_map: dict[str, list[str]] = {}
    for n in flat_nodes:
        pid = n.get("parent_node_id")
        if pid:
            children_map.setdefault(pid, []).append(n["node_id"])

    # Recursively collect all descendant patents for a given node
    def collect_descendant_patents(node_id: str, visited: set) -> set:
        if node_id in visited:
            return set()
        visited.add(node_id)
        result = set(node_map[node_id]["supporting_patent_ids"])
        for child_id in children_map.get(node_id, []):
            result.update(collect_descendant_patents(child_id, visited))
        return result

    # Apply bubble-up to every node
    for n in flat_nodes:
        all_patents = collect_descendant_patents(n["node_id"], set())
        n["supporting_patent_ids"] = sorted(list(all_patents))

    return flat_nodes


def enrich_nodes(state: TaxonomyGenerationState) -> dict:
    """
    Traverses the draft tree, attaches supporting patents, and generates descriptions via LLM.
    Fix 4: After building the flat list, patent IDs are bubbled up from children to all ancestors.
    """
    print("--- ENRICHING NODES ---")
    draft_tree = state.get("draft_tree", {})
    concept_groups = state.get("concept_groups", {})
    canonical_concepts = state.get("canonical_concepts", [])

    if not draft_tree:
        return {"final_taxonomy": []}

    # Inject granular concepts as leaf nodes into the tree
    def inject_granular_concepts(tree_dict):
        for k, v in list(tree_dict.items()):
            if k in concept_groups:
                if not isinstance(v, dict):
                    tree_dict[k] = {}
                for c in concept_groups[k]:
                    tree_dict[k][c.name] = {}
            elif isinstance(v, dict):
                inject_granular_concepts(v)

    inject_granular_concepts(draft_tree)

    # Gather all node paths to get context-aware descriptions in one batch
    all_node_paths = []
    def get_paths(d, current_path=""):
        for k, v in d.items():
            path = f"{current_path} > {k}" if current_path else k
            all_node_paths.append(path)
            if isinstance(v, dict):
                get_paths(v, path)

    get_paths(draft_tree)

    system_prompt = """You are an expert patent analyst. I will give you a list of taxonomy nodes along with their hierarchical path (e.g., Parent > Child > Node).
    Write a short, 1-sentence technical description for the leaf/target node to guide what information should be extracted for it.
    Output MUST be a JSON object mapping the EXACT node name (just the node name, not the full path) to its description.
    
    Example Input:
    Mechanical > Tensile Strength
    Wind Turbines > Blades > Pitch
    
    Example Output:
    {
      "Tensile Strength": "Measurement of the force required to pull something such as rope, wire, or a structural beam to the point where it breaks.",
      "Pitch": "The angle of the wind turbine blade relative to the wind plane."
    }"""

    user_prompt = "Node Paths:\n" + "\n".join(all_node_paths)

    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            cheap=True  # Descriptions don't need intense reasoning
        )
        descriptions = response_json
    except Exception as e:
        print(f"Failed to generate descriptions: {e}")
        descriptions = {}

    # Prepare concept lookup for attaching patents
    concept_by_name = {c.name: c for c in canonical_concepts}

    # Flatten the tree and attach patents to leaf/group nodes
    final_taxonomy = flatten_and_enrich_tree(
        tree=draft_tree,
        parent_id=None,
        current_level=0,
        concept_groups=concept_groups,
        descriptions=descriptions,
        concept_by_name=concept_by_name
    )

    # FIX 4: Bubble up patents from children to all ancestor nodes
    final_taxonomy = bubble_up_patents(final_taxonomy)

    leaf_count = sum(1 for n in final_taxonomy if not any(
        other["parent_node_id"] == n["node_id"] for other in final_taxonomy
    ))
    print(f"Enriched {len(final_taxonomy)} nodes ({leaf_count} leaves). Patent IDs bubbled up to all ancestors.")

    out_data = {"final_taxonomy": final_taxonomy}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "enrich_nodes", state, out_data)

    return out_data
