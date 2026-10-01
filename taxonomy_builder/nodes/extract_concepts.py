from typing import Any
from taxonomy_builder.state import Concept
from pipeline.utils.llm_client import chat_json


def extract_concepts(payload: dict[str, Any]) -> dict:
    """
    Phase 3 Fix:
    - Previously extracted concept name + context only.
    - Now also extracts a domain_path: the technology ancestry path
      (e.g., ["Automotive", "Electric Vehicle", "Battery"]) for each concept.
    - domain_path grounds the hierarchy in actual patent evidence, reducing hallucination.
    """
    patent_id = payload["patent_id"]
    text = payload["text"]

    print(f"--- EXTRACTING CONCEPTS: {patent_id} ---")

    system_prompt = """You are an expert patent analyst. Your task is to extract highly granular technical concepts and parameters from the provided patent text.

First, identify the technology domain this patent belongs to. Then extract specific technical concepts.

RULES:
1. Extract granular parameters with units if applicable (e.g., "Pulse Width (µs)", "Thermal conductivity (W/m·K)").
2. Extract specific materials, components, methods, and application areas.
3. Focus on substantive technical information. Do NOT extract generic patent language (e.g., "system", "method", "device", "apparatus").
4. For each concept, provide a "domain_path": a list of 2-4 technology ancestry levels that places this concept in the technology hierarchy.
   - This must come from the actual patent text — do NOT invent domain paths.
   - Example: a concept about battery temperature from an EV patent → domain_path: ["Automotive", "Electric Vehicle", "Battery Management"]
   - Example: a concept about tensile strength from a polymer patent → domain_path: ["Materials Science", "Polymers", "Mechanical Properties"]
5. Output a JSON object with:
   - "reasoning": a 1-2 sentence explanation of the domain and what types of concepts you found
   - "concepts": a list of objects, each with "name", "context", and "domain_path"

--- EXAMPLE OUTPUT ---
{
  "reasoning": "This patent is in the Electric Vehicle domain, specifically about battery thermal management. I will extract temperature-related parameters, sensors, and control mechanisms.",
  "concepts": [
    {
      "name": "Battery Temperature",
      "context": "The system continuously monitors the temperature of lithium-ion battery cells.",
      "domain_path": ["Automotive", "Electric Vehicle", "Battery Management"]
    },
    {
      "name": "Temperature Sensor",
      "context": "A thermistor array measures cell-level temperature.",
      "domain_path": ["Automotive", "Electric Vehicle", "Battery Management", "Thermal Sensing"]
    },
    {
      "name": "Charging Current Reduction",
      "context": "Charging current is reduced when temperature exceeds the predefined threshold.",
      "domain_path": ["Automotive", "Electric Vehicle", "Battery Management", "Charging Control"]
    }
  ]
}
"""

    user_prompt = f"Extract the key technical concepts from the following patent text:\n\n{text[:60000]}"

    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # cheap model because this runs for every patent in parallel
            cheap=True
        )

        extracted = response_json.get("concepts", [])

        # Convert to our Pydantic Concept model
        concepts = [
            Concept(
                name=c["name"],
                context=c.get("context", ""),
                patent_id=patent_id,
                domain_path=c.get("domain_path", [])
            )
            for c in extracted
            if c.get("name")
        ]

    except Exception as e:
        print(f"Failed to extract concepts for {patent_id}: {e}")
        concepts = []

    out_data = {"all_concepts": concepts}

    run_id = payload.get("run_id", "default")
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(run_id, "extract_concepts", {}, out_data)

    return out_data
