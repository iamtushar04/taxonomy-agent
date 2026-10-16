import re
import uuid
from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json





def flatten_and_enrich_tree(tree: dict, parent_id: str | None, current_level: int, concept_groups: dict, descriptions: dict, concept_by_name: dict, parent_path: str = "") -> list[dict]:
    flat_nodes = []

    for node_name, children in tree.items():
        node_id = f"T_{str(uuid.uuid4())[:8]}"
        current_path = f"{parent_path} > {node_name}" if parent_path else node_name

        supporting_patents = set()
        supporting_products = set()
        patent_contexts = []
        contexts_by_patent = {}

        # Group node: attach products from canonical concepts in this group
        if node_name in concept_groups:
            for canonical_concept in concept_groups[node_name]:
                for pid in canonical_concept.supporting_patent_ids:
                    if str(pid).startswith("prod_"):
                        supporting_products.add(pid)

        # Granular leaf node: attach products from the canonical concept by name
        if node_name in concept_by_name:
            for pid in concept_by_name[node_name].supporting_patent_ids:
                if str(pid).startswith("prod_"):
                    supporting_products.add(pid)

        node_dict = {
            "node_id": node_id,
            "parent_node_id": parent_id,
            "name": node_name,
            "level": current_level,
            "path": current_path,
            "description": descriptions.get(node_name, f"Technical details related to {node_name}."),
            "supporting_patent_ids": list(supporting_patents),
            "supporting_product_ids": list(supporting_products),
            "patent_contexts": patent_contexts,
            "contexts_by_patent": contexts_by_patent,
            "rules": {}
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
                concept_by_name=concept_by_name,
                parent_path=current_path
            )
            flat_nodes.extend(child_nodes)

    return flat_nodes


def align_patents_to_nodes(flat_nodes: list[dict], patents_data: dict, run_id: str | None = None) -> list[dict]:
    """
    Direct pipeline extraction matching every fetched patent across all taxonomy leaf nodes.
    Passes patent_number, taxonomy nodes (with full hierarchical path and description),
    and solid reasoning to pipeline/graph.py:run_patent_extraction.
    Extracts exact values and verbatim evidence quotes with Claims Priority 1,
    with ZERO generic fallback duplicates.
    """
    if not flat_nodes or not patents_data:
        return flat_nodes

    from pipeline.graph import run_patent_extraction

    node_by_id = {n["node_id"]: n for n in flat_nodes}

    # Evaluate candidate leaf nodes (only true leaves should have direct claim snippets attached)
    candidate_nodes = [
        n for n in flat_nodes
        if not any(other.get("parent_node_id") == n["node_id"] for other in flat_nodes)
    ]

    print(f"--- RUNNING PIPELINE EXTRACTION FOR {len(patents_data)} PATENTS ACROSS {len(candidate_nodes)} LEAF NODES ---")

    # Format nodes for the pipeline with full path & description
    pipeline_nodes = [
        {
            "node_id": n["node_id"],
            "name": n["name"],
            "parent_id": n.get("parent_node_id"),
            "level": n.get("level", 0),
            "path": n.get("path", n["name"]),
            "description": n.get("description", f"Technical details related to {n['name']}."),
            "rules": n.get("rules", {}),
        }
        for n in candidate_nodes
    ]

    # Build solid reasoning for each node path
    reasoning_map = {
        n["path"]: (
            f"Taxonomy Path: {n['path']}\n"
            f"Target Node: {n['name']}\n"
            f"Extraction Guidance: Extract specific technical features, measurements, or explicit disclosures for '{n['name']}'. "
            f"PRIORITY WATERFALL: Check Claims first (Priority 1). If not in claims, check Description (Priority 2). "
            f"If not explicitly taught, return status NOT_FOUND with values=[]. Do not infer or invent."
        )
        for n in candidate_nodes
    }

    for p_id, p_info in patents_data.items():
        if not isinstance(p_info, dict):
            continue

        raw_api_resp = p_info.get("raw_api_response")
        print(f"-> Extracting for patent {p_id} via pipeline...")

        try:
            extractions = run_patent_extraction(
                patent_number=p_id,
                taxonomy_nodes=pipeline_nodes,
                extraction_reasoning=reasoning_map,
                raw_api_response=raw_api_resp,
                run_id=run_id,
            )
        except Exception as exc:
            print(f"Warning: Pipeline extraction failed for {p_id}: {exc}")
            extractions = []

        # Process pipeline extraction results
        found_count = 0
        for ext in extractions:
            if not isinstance(ext, dict):
                continue
            status = ext.get("status")
            nid = ext.get("node_id")
            if not nid or nid not in node_by_id:
                continue

            target_node = node_by_id[nid]
            target_node.setdefault("supporting_patent_ids", [])
            target_node.setdefault("contexts_by_patent", {})
            target_node.setdefault("patent_contexts", [])

            if status == "FOUND":
                values = ext.get("values") or []
                if values:
                    found_count += 1
                    if p_id not in target_node["supporting_patent_ids"]:
                        target_node["supporting_patent_ids"].append(p_id)

                    best = values[0]
                    val_str = str(best.get("value", "")).strip()
                    ev_str = str(best.get("evidence", "")).strip()
                    src_str = str(best.get("source", "")).strip()

                    # Strip any Phase 1 / Phase 2 debug markers so they NEVER appear in Excel
                    for tag in ["[RAW Phase 1]", "[FORMATTED Phase 2]", "Raw Phase 1", "Phase 1", "Phase 2"]:
                        val_str = val_str.replace(tag, "")
                        ev_str = ev_str.replace(tag, "")
                    val_str = val_str.strip()
                    ev_str = ev_str.strip()

                    # Format cell text cleanly: Raw value + exact verbatim quote + source citation
                    if val_str and ev_str and val_str.lower() not in ev_str.lower() and ev_str.lower() not in val_str.lower():
                        cell_text = f"{val_str} | \"{ev_str}\""
                    elif val_str:
                        cell_text = val_str
                    else:
                        cell_text = f"\"{ev_str}\""

                    if src_str:
                        cell_text = f"{cell_text} [{src_str}]"

                    target_node["contexts_by_patent"][p_id] = [cell_text]
                    target_node["patent_contexts"].append(cell_text)

        print(f"   [OK] Patent {p_id}: {found_count} nodes FOUND with exact evidence.")

    return flat_nodes


def bubble_up_patents(flat_nodes: list[dict]) -> list[dict]:
    """
    For every node, propagate all descendant patent & product IDs and evidence contexts upward to ancestors.
    Deduplicates contexts to avoid repeated strings inside cells.
    """
    if not flat_nodes:
        return flat_nodes

    node_map = {n["node_id"]: n for n in flat_nodes}
    children_map: dict[str, list[str]] = {}
    for n in flat_nodes:
        pid = n.get("parent_node_id")
        if pid:
            children_map.setdefault(pid, []).append(n["node_id"])

    def collect_descendants(node_id: str, visited: set) -> tuple[set, set, dict]:
        if node_id in visited:
            return set(), set(), {}
        visited.add(node_id)
        
        node = node_map[node_id]
        patents = set(node.get("supporting_patent_ids", []))
        products = set(node.get("supporting_product_ids", []))
        
        # Deduplicate node's own contexts
        contexts = {}
        for p, ctx_list in node.get("contexts_by_patent", {}).items():
            contexts[p] = list(dict.fromkeys(c.strip() for c in ctx_list if c and c.strip()))
        
        for child_id in children_map.get(node_id, []):
            child_patents, child_products, child_contexts = collect_descendants(child_id, visited)
            patents.update(child_patents)
            products.update(child_products)
            for p, ctx_list in child_contexts.items():
                existing = contexts.setdefault(p, [])
                for c in ctx_list:
                    if c and c not in existing:
                        existing.append(c)
            
        return patents, products, contexts

    for n in flat_nodes:
        all_patents, all_products, all_contexts = collect_descendants(n["node_id"], set())
        n["supporting_patent_ids"] = sorted(list(all_patents))
        n["supporting_product_ids"] = sorted(list(all_products))
        n["contexts_by_patent"] = all_contexts

    return flat_nodes


def enrich_nodes(state: TaxonomyGenerationState) -> dict:
    """
    Traverses the draft tree, generates descriptions via LLM,
    systematically aligns all patents to matching nodes with evidence,
    and bubbles up patents to all ancestors.
    """
    print("--- ENRICHING NODES ---")
    draft_tree = state.get("draft_tree", {})
    concept_groups = state.get("concept_groups", {})
    canonical_concepts = state.get("canonical_concepts", [])
    patents_data = state.get("patents_data", {})

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

    # Flatten the tree and attach initial patents to leaf/group nodes
    final_taxonomy = flatten_and_enrich_tree(
        tree=draft_tree,
        parent_id=None,
        current_level=0,
        concept_groups=concept_groups,
        descriptions=descriptions,
        concept_by_name=concept_by_name
    )

    # Systematic two-pass alignment: map every fetched patent across all taxonomy nodes
    if patents_data:
        final_taxonomy = align_patents_to_nodes(final_taxonomy, patents_data, run_id=state.get("run_id"))

    # Bubble up patents and evidence from children to all ancestor nodes
    final_taxonomy = bubble_up_patents(final_taxonomy)

    leaf_count = sum(1 for n in final_taxonomy if not any(
        other["parent_node_id"] == n["node_id"] for other in final_taxonomy
    ))
    print(f"Enriched {len(final_taxonomy)} nodes ({leaf_count} leaves). All patents aligned & bubbled up.")

    out_data = {"final_taxonomy": final_taxonomy}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "enrich_nodes", state, out_data)

    return out_data
