from typing import Any
from taxonomy_builder.pubmed_state import Concept
from pipeline.utils.llm_client import chat_json

def pubmed_extract_concepts(payload: dict[str, Any]) -> dict:
    pmid = payload["pmid"]
    text = payload["text"]

    print(f"--- EXTRACTING MEDICAL CONCEPTS: {pmid} ---")

    system_prompt = """You are an expert biomedical researcher and clinical data analyst. Your task is to extract highly granular scientific and medical concepts from the provided PubMed abstract.

First, identify the broad medical/scientific domain this paper belongs to. Then extract specific clinical or biological concepts.

RULES:
1. Extract granular concepts like diseases, biological pathways, cellular mechanisms, drug mechanisms of action, patient demographics, and clinical outcomes.
2. Focus on substantive medical information. Do NOT extract generic language (e.g., "study", "analysis", "patients", "results").
3. For each concept, provide a "domain_path": a list of 2-4 ancestry levels that places this concept in a medical taxonomy.
   - Example: a concept about T-cell activation → domain_path: ["Immunology", "Cellular Immunity", "T-Cell Responses"]
   - Example: a concept about Myocardial Infarction → domain_path: ["Cardiology", "Ischemic Heart Disease", "Acute Coronary Syndrome"]
4. Output a JSON object with:
   - "reasoning": a 1-2 sentence explanation of the medical domain and what types of concepts you found
   - "concepts": a list of objects, each with "name", "context", and "domain_path"

--- EXAMPLE OUTPUT ---
{
  "reasoning": "This paper is in the Oncology domain, specifically focusing on immunotherapy. I will extract biomarkers, immune mechanisms, and clinical efficacy metrics.",
  "concepts": [
    {
      "name": "PD-L1 Expression",
      "context": "High PD-L1 expression was correlated with improved progression-free survival.",
      "domain_path": ["Oncology", "Immunotherapy", "Biomarkers"]
    },
    {
      "name": "Progression-Free Survival (PFS)",
      "context": "The median PFS in the treatment group was 12.4 months.",
      "domain_path": ["Clinical Trials", "Oncology Outcomes", "Survival Metrics"]
    }
  ]
}
"""

    user_prompt = f"Extract the key medical concepts from the following PubMed article:\n\n{text[:60000]}"

    try:
        response_json = chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            cheap=True
        )

        extracted = response_json.get("concepts", [])

        concepts = [
            Concept(
                name=c["name"],
                context=c.get("context", ""),
                pmid=pmid,
                domain_path=c.get("domain_path", [])
            )
            for c in extracted
            if c.get("name")
        ]

    except Exception as e:
        print(f"Failed to extract concepts for {pmid}: {e}")
        concepts = []

    out_data = {"all_concepts": concepts}
    
    run_id = payload.get("run_id", "default")
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(run_id, "pubmed_extract_concepts", {}, out_data)

    return out_data
