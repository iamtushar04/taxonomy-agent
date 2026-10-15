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
    is_product = payload.get("is_product", False)
    domain_anchor = payload.get("domain_anchor") or {}

    anchor_guidance = ""
    if domain_anchor and isinstance(domain_anchor, dict):
        p_dom = domain_anchor.get("primary_domain")
        s_doms = domain_anchor.get("canonical_subdomains") or []
        if p_dom:
            anchor_guidance = (
                f"\nCANONICAL DATASET DOMAIN ANCHOR:\n"
                f"Primary Domain: '{p_dom}'\n"
                f"Core Subdomains: {', '.join(s_doms)}\n"
                f"MANDATORY: For each concept's 'domain_path', the first level MUST be '{p_dom}' or one of the Core Subdomains above. "
                f"Do NOT invent unrelated high-level root branches so that concepts cluster cleanly across all documents.\n"
            )

    if is_product:
        print(f"--- EXTRACTING PRODUCT CONCEPTS: {patent_id} ---")
        system_prompt = (
            "You are an expert technical product analyst and ontologist. Your task is to extract highly granular technical features, architecture components, engineering mechanisms, and parameters from the provided commercial product specification.\n"
            + anchor_guidance +
            """
RULES:
1. Extract granular engineering parameters, components, modules, protocols, materials, and algorithms.
2. Focus strictly on substantive technical and functional capabilities. Do NOT extract marketing fluff (e.g., "seamless", "best-in-class", "innovative solution").
3. For each concept, provide a "domain_path": a list of 2-4 technology ancestry levels that places this concept in the engineering/scientific taxonomy (e.g. ["Biotechnology", "Peptide Therapeutics", "Formulation"]).
4. Output a JSON object with:
   - "reasoning": a 1-2 sentence explanation of the technical domain of this commercial product
   - "concepts": a list of objects, each with "name" (string), "context" (plain text string describing the feature or parameter values; do NOT output a nested dictionary), and "domain_path" (list of strings)
"""
        )
        user_prompt = f"Extract the key technical features and architectural concepts from this product document:\n\n{text[:60000]}"
    else:
        print(f"--- EXTRACTING CONCEPTS: {patent_id} ---")
        system_prompt = (
            "You are an expert patent analyst. Your task is to extract highly granular technical concepts and parameters from the provided patent text.\n"
            + anchor_guidance +
            """
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
        )
        user_prompt = f"Extract the key technical concepts from the following patent text:\n\n{text[:60000]}"

    mental_model_context = payload.get("mental_model_context")
    if mental_model_context:
        system_prompt += f"\n\nPRODUCT FOCUS GUIDANCE:\nPrioritize technical concepts and hierarchy pathways that relate to this product focus:\n{mental_model_context}\n"

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

        # Convert to our Pydantic Concept model losslessly
        concepts = []
        for c in extracted:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            if not name:
                continue
            try:
                concepts.append(
                    Concept(
                        name=name,
                        context=c.get("context", ""),
                        patent_id=patent_id,
                        domain_path=c.get("domain_path", [])
                    )
                )
            except Exception as item_err:
                print(f"Warning: could not parse concept in {patent_id}: {item_err}")
                continue

    except Exception as e:
        print(f"Failed to extract concepts for {patent_id}: {e}")
        concepts = []

    out_data = {"all_concepts": concepts}

    run_id = payload.get("run_id", "default")
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(run_id, "extract_concepts", {}, out_data)

    return out_data
