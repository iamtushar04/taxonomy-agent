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
                
                patents_data[p_id] = {
                    "title": str(title),
                    "full_text": full_text
                }
            except Exception as e:
                print(f"Failed to fetch {p_id}: {e}")
                errors.append(f"Fetch failed for {p_id}: {e}")
                
    out_data = {"patents_data": patents_data}
    if errors:
        out_data["errors"] = errors
        
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "fetch_patents", state, out_data)
        
    return out_data
