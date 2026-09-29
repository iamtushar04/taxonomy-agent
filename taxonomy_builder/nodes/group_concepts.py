from taxonomy_builder.state import TaxonomyGenerationState
from pipeline.utils.llm_client import chat_json

def group_concepts(state: TaxonomyGenerationState) -> dict:
    """
    Groups the clustered canonical concepts into semantic categories using the LLM.
    """
    print("--- GROUPING CONCEPTS ---")
    canonical_concepts = state.get("canonical_concepts", [])
    
    if not canonical_concepts:
        return {"concept_groups": {}}
        
    # Extract just the canonical names to save tokens
    unique_concept_names = [c.name for c in canonical_concepts]
    
    system_prompt = """You are an expert patent analyst. I will give you a list of technical concepts extracted from a collection of patents.
    
    Your task is to group semantically similar concepts into overarching technical categories.
    
    RULES:
    1. Group concepts that mean the same thing or belong to the exact same technical category.
    2. Generate a concise, technically meaningful name for each group (e.g., 'Mechanical Properties').
    3. Do NOT create generic categories (e.g., 'Other', 'Miscellaneous').
    4. Ensure no two groups overlap significantly.
    5. Output MUST be a single flat JSON object mapping EACH original concept string EXACTLY to its assigned Group Name.
    
    Example output format:
    {
      "Tensile Strength": "Mechanical Properties",
      "Modulus": "Mechanical Properties",
      "Tensile elongation": "Mechanical Properties",
      "Zirconocene": "Catalyst Composition"
    }
    """
    
    user_prompt = "Group the following concepts:\n\n" + "\n".join(unique_concept_names)
    
    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Use the main, smarter model (e.g. gpt-4o) for clustering logic
            cheap=False,
            max_tokens=16000
        )
        
        concept_to_group = response_json
        
        # We need to group our actual CanonicalConcept objects based on this mapping
        concept_groups = {}
        for c in canonical_concepts:
            # Check if this concept was mapped by the LLM
            g_name = concept_to_group.get(c.name)
            if g_name:
                if g_name not in concept_groups:
                    concept_groups[g_name] = []
                concept_groups[g_name].append(c)
                
    except Exception as e:
        print(f"Failed to group concepts: {e}")
        concept_groups = {}
            
    out_data = {"concept_groups": concept_groups}
    
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "group_concepts", state, out_data)
            
    return out_data
