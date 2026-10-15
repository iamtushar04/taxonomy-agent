import os
import httpx
from dotenv import load_dotenv
from taxonomy_builder.state import TaxonomyGenerationState

load_dotenv()

_BASE_URL = os.environ.get("WISSEN_API_BASE", "https://api.patent.wissenresearch.com")
_TIMEOUT = 60

def fetch_patents(state: TaxonomyGenerationState) -> dict:
    """
    Fetches real patent text from the Wissen Patent API.
    Combines abstract, claims, and description into full_text.
    """
    print("--- FETCHING PATENTS ---")
    patent_ids = state.get("patent_ids", [])
    
    api_key = os.environ.get("WISSEN_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    
    patents_data = {}
    errors = []
    
    with httpx.Client(timeout=_TIMEOUT) as client:
        for p_id in patent_ids:
            url = f"{_BASE_URL}/patent/{p_id}"
            try:
                print(f"Fetching {p_id}...")
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                title = data.get("title", "")
                abstract = data.get("abstract", "")
                claims = data.get("claims", "")
                desc = data.get("structured_description") or data.get("description", "")
                
                full_text = f"Title: {title}\n\nAbstract: {abstract}\n\nClaims: {claims}\n\nDescription: {desc}"
                
                assignees = data.get("assignee") or data.get("assignees", [])
                assignee_str = ", ".join(str(a) for a in assignees) if isinstance(assignees, list) and assignees else str(assignees)
                if not assignee_str or assignee_str.lower() == "none":
                    assignee_str = "N/A"
                    
                summary_text = "N/A"
                if abstract:
                    try:
                        from pipeline.utils.llm_client import chat_completion
                        messages = [
                            {"role": "system", "content": "You are a concise summarizer. Summarize the following abstract in 10 words or less."},
                            {"role": "user", "content": str(abstract)}
                        ]
                        summary_text = chat_completion(messages, model="gpt-4o-mini").strip()
                    except Exception as llm_e:
                        print(f"Failed to summarize abstract: {llm_e}")
                        summary_text = "N/A"

                filing_date = (
                    data.get("application_date")
                    or data.get("filing_date")
                    or data.get("priority_date")
                    or data.get("publication_date")
                    or ""
                )

                patents_data[p_id] = {
                    "title": str(title),
                    "full_text": full_text,
                    "assignee": assignee_str,
                    "filing_date": str(filing_date) if filing_date else None,
                    "summary": summary_text
                }
            except Exception as e:
                print(f"Failed to fetch {p_id}: {e}")
                errors.append(f"Fetch failed for {p_id}: {e}")
                
    # Derive unified canonical domain anchor across patents and products
    domain_anchor = {}
    if patents_data:
        sample_titles = [p.get("title", "") for p in list(patents_data.values())[:15] if p.get("title")]
        products_data = state.get("products_data", {})
        mental_model_context = state.get("mental_model_context", "")

        product_hints = []
        if products_data and isinstance(products_data, dict):
            for p in list(products_data.values())[:6]:
                if isinstance(p, dict):
                    p_name = p.get("product_name", "")
                    p_cat = p.get("category", "")
                    product_hints.append(f"{p_name} ({p_cat})")

        prompt = (
            "You are a chief patent ontologist.\n"
            "Analyze the following patent titles, summaries, and commercial product context.\n"
            "Define the single CANONICAL technology domain anchor that unifies all of them into a coherent taxonomy.\n\n"
            f"Patent Titles:\n" + "\n".join(f"- {t}" for t in sample_titles[:12]) + "\n\n"
            f"Product Context:\n{mental_model_context or ', '.join(product_hints) or 'None'}\n\n"
            "RULES:\n"
            "1. Identify the single unified 'primary_domain' (e.g. 'Materials Science & Polymer Chemistry' or 'Pharmaceuticals & Biotechnology').\n"
            "2. Identify exactly 3 to 5 'canonical_subdomains' that represent the core technical pillars (e.g. ['Catalysts & Formulation', 'Polymerization & Reactor Processes', 'Resin Properties & Morphologies', 'End-Use Applications & Molding']).\n"
            "3. Output ONLY a clean JSON object:\n"
            "{\n"
            '  "primary_domain": "...",\n'
            '  "canonical_subdomains": ["...", "...", "..."]\n'
            "}\n"
        )
        try:
            from pipeline.utils.llm_client import chat_json
            domain_anchor = chat_json(
                messages=[{"role": "user", "content": prompt}],
                cheap=True,
                max_tokens=600
            )
            print(f"-> Established Canonical Domain Anchor: {domain_anchor.get('primary_domain')} | Subdomains: {domain_anchor.get('canonical_subdomains')}")
        except Exception as e:
            print(f"Note: Could not generate domain anchor: {e}")

    out_data = {"patents_data": patents_data}
    if domain_anchor:
        out_data["domain_anchor"] = domain_anchor
    if errors:
        out_data["errors"] = errors
        
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "fetch_patents", state, out_data)
        
    return out_data
