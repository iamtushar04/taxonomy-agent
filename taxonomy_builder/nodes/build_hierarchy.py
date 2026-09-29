from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json

def build_hierarchy(state: TaxonomyGenerationState) -> dict:
    """
    Takes the concept groups and asks the LLM to organize them into a hierarchical tree.
    """
    print("--- BUILDING HIERARCHY ---")
    groups = state.get("concept_groups", {})
    
    if not groups:
        return {"draft_tree": {}}
        
    group_names = list(groups.keys())
    
    system_prompt = """You are an expert ontologist and patent analyst. I will give you a list of technical categories.
    
    Your task is to organize these categories into a clean, logical hierarchical tree.
    
    RULES:
    1. Structure the tree with a rich, 3-level depth: Level 1 (Main tech area, e.g., "Polymer Properties and Material Innovations"), Level 2 (Major category, e.g., "Mechanical Properties"), and Level 3 (Specific parameters/leaf nodes, e.g., "Tensile Strength", "Modulus", "Dart Impact").
    2. Ensure micro-properties and granular specific parameters are placed as Level 3 leaf nodes under their respective Level 2 categories.
    3. The categories I provide must be placed as nodes within this tree. You can create broader parent nodes if necessary to group them logically.
    4. Output MUST be a nested JSON object representing the tree. The keys should be node names, and values should be dictionaries of child nodes. Leaf nodes should be empty dictionaries.
    
    Example output format:
    {
      "Polymer Properties": {
        "Mechanical Properties": {},
        "Thermal Properties": {}
      },
      "Applications": {
        "Packaging": {}
      }
    }
    """
    
    user_prompt = "Build a hierarchical tree using these categories:\n" + "\n".join(group_names)
    
    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            cheap=False,
            max_tokens=16000
        )
        draft_tree = response_json
        
        # Validation Check: Ensure all input groups are present in the tree
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
            print(f"Warning: LLM dropped {len(missing_groups)} groups. Adding them to 'Uncategorized'.")
            if "Uncategorized" not in draft_tree:
                draft_tree["Uncategorized"] = {}
            for g in missing_groups:
                draft_tree["Uncategorized"][g] = {}
                
    except Exception as e:
        print(f"Failed to build hierarchy: {e}")
        draft_tree = {}
    
    out_data = {"draft_tree": draft_tree}
    
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "build_hierarchy", state, out_data)
    
    return out_data
