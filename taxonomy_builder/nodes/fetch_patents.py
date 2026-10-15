import os
import httpx
from dotenv import load_dotenv
from taxonomy_builder.state import TaxonomyGenerationState

load_dotenv()

_BASE_URL = os.environ.get("WISSEN_API_BASE", "https://api.patent.wissenresearch.com")
_EXTRACT_BASE_URL = os.environ.get("WISSEN_EXTRACT_BASE", "https://api.patent.wissenresearch.com/extract")
_TIMEOUT = 60


def _clean_html_or_text(val: str) -> str:
    """Safely extracts clean plain text from HTML fragments or plain strings."""
    if not val or not isinstance(val, str):
        return ""
    if "<" in val and ">" in val:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(val, "html.parser").get_text(separator=" \n").strip()
        except Exception:
            return val.strip()
    return val.strip()


def _extract_claims(data: dict) -> str:
    """
    Cascading claims extraction across all patent API formats:
    1. Standard 'claims' string
    2. 'structured_claims' list of claim dicts or strings (common in EP, US)
    3. 'independent_claims' list or string (common in EP, US, JP)
    4. 'claims_html' HTML fragment (common in live /extract/ responses)
    5. Fallback fields: 'unstructured_claims', 'raw_claims', 'claims_text'
    """
    # 1. Plain text claims
    claims = data.get("claims")
    if claims and isinstance(claims, str) and claims.strip():
        return _clean_html_or_text(claims)

    # 2. structured_claims (list of claim dicts or strings)
    structured_claims = data.get("structured_claims")
    if structured_claims and isinstance(structured_claims, list):
        claim_parts = []
        for c in structured_claims:
            if isinstance(c, dict):
                num = c.get("claim_number") or c.get("number") or ""
                txt = c.get("claim_text") or c.get("text") or ""
                cleaned_txt = _clean_html_or_text(txt)
                if num and cleaned_txt:
                    claim_parts.append(f"{num}. {cleaned_txt}")
                elif cleaned_txt:
                    claim_parts.append(cleaned_txt)
            elif isinstance(c, str) and c.strip():
                claim_parts.append(_clean_html_or_text(c))
        if claim_parts:
            return "\n\n".join(claim_parts)

    # 3. independent_claims
    indep_claims = data.get("independent_claims")
    if indep_claims:
        if isinstance(indep_claims, list):
            parts = []
            for c in indep_claims:
                if isinstance(c, dict):
                    txt = c.get("claim_text") or c.get("text") or ""
                    if txt:
                        parts.append(_clean_html_or_text(txt))
                elif isinstance(c, str) and c.strip():
                    parts.append(_clean_html_or_text(c))
            if parts:
                return "\n\n".join(parts)
        elif isinstance(indep_claims, str) and indep_claims.strip():
            return _clean_html_or_text(indep_claims)

    # 4. claims_html (from /extract/ endpoint)
    claims_html = data.get("claims_html")
    if claims_html and isinstance(claims_html, str) and claims_html.strip():
        return _clean_html_or_text(claims_html)

    # 5. Generic unstructured fallback keys
    for k in ("unstructured_claims", "raw_claims", "claims_text"):
        val = data.get(k)
        if val:
            if isinstance(val, list):
                return "\n\n".join(_clean_html_or_text(str(x)) for x in val if str(x).strip())
            return _clean_html_or_text(str(val))

    return ""


def _extract_description(data: dict) -> str:
    """
    Cascading description extraction across all patent API formats:
    1. Standard 'description' string
    2. 'structured_description' list of paragraphs or HTML (common in EP, US)
    3. 'description_html' HTML fragment (common in live /extract/ responses)
    4. Fallback fields: 'unstructured_description', 'raw_description', 'description_text', 'detailed_description'
    """
    # 1. Plain text description
    desc = data.get("description")
    if desc and isinstance(desc, str) and desc.strip():
        return _clean_html_or_text(desc)

    # 2. structured_description
    struct_desc = data.get("structured_description")
    if struct_desc:
        if isinstance(struct_desc, list) and len(struct_desc) > 0:
            parts = []
            for p in struct_desc:
                if isinstance(p, dict):
                    txt = p.get("text") or p.get("paragraph") or ""
                    if txt:
                        parts.append(_clean_html_or_text(txt))
                elif isinstance(p, str) and p.strip():
                    parts.append(_clean_html_or_text(p))
            if parts:
                return "\n\n".join(parts)
        elif isinstance(struct_desc, str) and struct_desc.strip():
            return _clean_html_or_text(struct_desc)

    # 3. description_html (from /extract/ endpoint)
    desc_html = data.get("description_html")
    if desc_html and isinstance(desc_html, str) and desc_html.strip():
        return _clean_html_or_text(desc_html)

    # 4. Generic unstructured fallback keys
    for k in ("unstructured_description", "raw_description", "description_text", "detailed_description"):
        val = data.get(k)
        if val:
            if isinstance(val, list):
                return "\n\n".join(_clean_html_or_text(str(x)) for x in val if str(x).strip())
            return _clean_html_or_text(str(val))

    return ""


def _parse_patent_response(data: dict) -> tuple[str, str, str, str, str, str]:
    """
    Universally extracts patent fields from either standard /patent/ or live /extract/ responses.
    Employs robust cascading fallback for claims and descriptions across jurisdictions (CN, EP, US, JP, WO).
    """
    title = data.get("title", "") or ""
    abstract = data.get("abstract", "") or ""

    claims = _extract_claims(data)
    desc = _extract_description(data)

    # Assignees: list or string
    assignees = data.get("assignee") or data.get("assignees", [])
    if isinstance(assignees, list):
        assignee_str = ", ".join(str(a).strip() for a in assignees if str(a).strip())
    else:
        assignee_str = str(assignees).strip()
    if not assignee_str or assignee_str.lower() in ("none", "null"):
        assignee_str = "N/A"

    # Filing / Priority / Publication date
    filing_date = (
        data.get("application_date")
        or data.get("filing_date")
        or data.get("priority_date")
        or data.get("publication_date")
        or ""
    )

    return str(title), str(abstract), str(claims), str(desc), str(assignee_str), str(filing_date)


def fetch_patents(state: TaxonomyGenerationState) -> dict:
    """
    Fetches real patent text from the Wissen Patent API.
    Supports both standard /patent/ endpoint and live /extract/ endpoint with HTML parsing.
    For CN patents, prioritizes live /extract/?cache=false to avoid stale or empty cached records.
    Combines abstract, claims, and description into full_text.
    """
    print("--- FETCHING PATENTS ---")
    run_id = state.get("run_id", "default")
    try:
        # pyrefly: ignore [missing-import]
        from services.run_stage_service import set_run_stage
        set_run_stage(run_id, "fetching")
    except Exception:
        pass
    patent_ids = state.get("patent_ids", [])
    
    api_key = os.environ.get("WISSEN_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    
    patents_data = {}
    errors = []
    
    with httpx.Client(timeout=_TIMEOUT) as client:
        for p_id in patent_ids:
            is_cn = p_id.upper().startswith("CN")
            primary_url = f"{_EXTRACT_BASE_URL}/{p_id}?cache=false" if is_cn else f"{_BASE_URL}/patent/{p_id}"
            fallback_url = f"{_BASE_URL}/patent/{p_id}" if is_cn else f"{_EXTRACT_BASE_URL}/{p_id}?cache=false"

            data = None
            try:
                print(f"Fetching {p_id} from {primary_url}...")
                response = client.get(primary_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                else:
                    print(f"Primary endpoint returned HTTP {response.status_code} for {p_id}, trying fallback: {fallback_url}")
                    res_fb = client.get(fallback_url, headers=headers)
                    if res_fb.status_code == 200:
                        data = res_fb.json()
                    else:
                        print(f"Fallback endpoint also returned HTTP {res_fb.status_code} for {p_id}")
            except Exception as req_e:
                print(f"Primary request error for {p_id}: {req_e}, trying fallback...")
                try:
                    res_fb = client.get(fallback_url, headers=headers)
                    if res_fb.status_code == 200:
                        data = res_fb.json()
                except Exception as fb_err:
                    print(f"Fallback request also failed for {p_id}: {fb_err}")

            if not data or not isinstance(data, dict):
                print(f"Skipping {p_id}: Could not retrieve patent data from any endpoint.")
                errors.append(f"Patent {p_id} could not be retrieved from API.")
                continue

            title, abstract, claims, desc, assignee_str, filing_date = _parse_patent_response(data)

            # If primary endpoint returned missing claims AND missing description, attempt fallback to alternate endpoint
            if not claims and not desc:
                try:
                    print(f"Primary text incomplete for {p_id} (claims/desc missing), attempting fallback to {fallback_url}...")
                    res_fb = client.get(fallback_url, headers=headers)
                    if res_fb.status_code == 200:
                        fb_data = res_fb.json()
                        fb_title, fb_abstract, fb_claims, fb_desc, fb_assignee, fb_filing = _parse_patent_response(fb_data)
                        if not title and fb_title:
                            title = fb_title
                        if not abstract and fb_abstract:
                            abstract = fb_abstract
                        if not claims and fb_claims:
                            claims = fb_claims
                        if not desc and fb_desc:
                            desc = fb_desc
                        if assignee_str == "N/A" and fb_assignee != "N/A":
                            assignee_str = fb_assignee
                        if not filing_date and fb_filing:
                            filing_date = fb_filing
                except Exception as fb_e:
                    print(f"Fallback extraction failed for {p_id}: {fb_e}")

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
                    print(f"Failed to summarize abstract for {p_id}: {llm_e}")
                    summary_text = "N/A"

            full_text = f"Title: {title}\n\nAbstract: {abstract}\n\nClaims: {claims}\n\nDescription: {desc}"

            patents_data[p_id] = {
                "title": str(title),
                "full_text": full_text,
                "assignee": assignee_str,
                "filing_date": str(filing_date) if filing_date else None,
                "summary": summary_text
            }
            print(f"Successfully loaded {p_id} (title: '{title[:45]}...', claims: {len(claims)} chars, desc: {len(desc)} chars)")
                
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
