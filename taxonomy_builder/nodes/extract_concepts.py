from typing import Any
from taxonomy_builder.state import Concept
from pipeline.utils.llm_client import chat_json

def extract_concepts(payload: dict[str, Any]) -> dict:
    """
    Extract technical concepts from a SINGLE patent using an LLM.
    Runs dynamically for any domain.
    """
    patent_id = payload["patent_id"]
    text = payload["text"]
    
    print(f"--- EXTRACTING CONCEPTS: {patent_id} ---")
    
    # Reasoning-based prompt
    system_prompt = """You are an expert patent analyst. Your task is to extract highly granular technical concepts and parameters from the provided patent text.

    First, provide your reasoning by identifying the domain and the types of specific parameters discussed. Then, output the JSON.

    RULES:
    1. Extract granular parameters with units if applicable (e.g., "Pulse Width (µs)", "Thermal conductivity (W/m·K)").
    2. Extract specific materials, components, and application areas.
    3. Focus on substantive technical information, NOT generic patent language (e.g. system, method, device).
    4. Output a JSON object containing a "reasoning" string and a "concepts" list. Each concept must have a "name" and a "context" string.

    --- EXAMPLES ---

    EXAMPLE 1 (Domain: Mechanical/Electrical Devices - Flexible PCBs):
    Reasoning: "The text discusses flexible printed circuits and ablation catheters. Therefore, I need to extract electrical parameters, base materials, and structural configurations."
    Concepts JSON: 
    {
      "reasoning": "The text discusses flexible printed circuits and ablation catheters. Therefore, I need to extract electrical parameters, base materials, and structural configurations.",
      "concepts": [
        {"name": "Pulse Width (µs)", "context": "Used for setting the electrical pulse duration."},
        {"name": "Thermoset Base", "context": "Base material for the flexible PCB."},
        {"name": "Electrode Array Configuration", "context": "Structural layout of the electrodes on the PCB."}
      ]
    }

    EXAMPLE 2 (Domain: Chemical/Materials - Metallocene PE):
    Reasoning: "The text discusses metallocene polyethylene compositions. I need to extract overarching material properties and specific application areas."
    Concepts JSON:
    {
      "reasoning": "The text discusses metallocene polyethylene compositions. I need to extract overarching material properties and specific application areas.",
      "concepts": [
        {"name": "Optical Properties", "context": "Crucial for film transparency and haze."},
        {"name": "Rheological Properties", "context": "Defines the flow behavior during processing."},
        {"name": "Medical Applications", "context": "End-use for the specialized polymer."}
      ]
    }
    """
    
    # Do not truncate arbitrarily; let the LLM handle the context window.
    # We can truncate to a large number just to be safe from absolute massive blobs.
    user_prompt = f"Extract the key technical concepts from the following patent text:\n\n{text[:60000]}"
    
    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # using the cheap model (e.g. gpt-4o-mini) because this runs for every patent
            cheap=True 
        )
        
        extracted = response_json.get("concepts", [])
        
        # Convert to our Pydantic Concept model for the state
        concepts = [
            Concept(
                name=c["name"],
                context=c.get("context", ""),
                patent_id=patent_id
            )
            for c in extracted
        ]
        
    except Exception as e:
        print(f"Failed to extract concepts for {patent_id}: {e}")
        concepts = []

    out_data = {"all_concepts": concepts}
    
    # We can't easily get run_id from Send payload unless we pass it, 
    # but we can fallback or skip tracing for map tasks if it's too noisy, 
    # but let's pass run_id in the payload in graph.py. 
    # For now, just return out_data (we will update graph.py to send run_id)
    run_id = payload.get("run_id", "default")
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(run_id, "extract_concepts", {}, out_data)
    
    return out_data
