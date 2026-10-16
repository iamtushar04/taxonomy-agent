"""
Node 1 — fetch_patent

Calls the Wissen Patent API and stores the full JSON response in state.
Any network or API error is caught and written to state["errors"],
which the graph's conditional edge uses to skip to write_excel.
"""

from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

from pipeline.state import PatentExtractionState

load_dotenv()
logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("WISSEN_API_BASE", "https://api.patent.wissenresearch.com")
_TIMEOUT = 60  # seconds


def fetch_patent(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: fetch patent data from the Wissen API.

    Reads:   state["patent_number"]
    Writes:  state["raw_api_response"]
             state["errors"]  (on failure)
    """
    patent_number = state["patent_number"]
    if state.get("raw_api_response"):
        logger.info("[fetch_patent] Reusing existing raw_api_response for %s", patent_number)
        return state
    logger.info("[fetch_patent] Fetching: %s", patent_number)

    api_key = os.environ.get("WISSEN_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    is_cn = patent_number.upper().startswith("CN")
    extract_base = os.environ.get("WISSEN_API_EXTRACT_BASE", f"{_BASE_URL}/extract")
    primary_url = f"{extract_base}/{patent_number}?cache=false" if is_cn else f"{_BASE_URL}/patent/{patent_number}"
    fallback_url = f"{_BASE_URL}/patent/{patent_number}" if is_cn else f"{extract_base}/{patent_number}?cache=false"

    data = None
    last_exc = None

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            try:
                response = client.get(primary_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                else:
                    logger.warning("[fetch_patent] Primary endpoint %s returned HTTP %s for %s, trying fallback...", primary_url, response.status_code, patent_number)
                    res_fb = client.get(fallback_url, headers=headers)
                    if res_fb.status_code == 200:
                        data = res_fb.json()
                    else:
                        response.raise_for_status()
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning("[fetch_patent] Request error for %s on primary, trying fallback: %s", patent_number, e)
                res_fb = client.get(fallback_url, headers=headers)
                res_fb.raise_for_status()
                data = res_fb.json()

    except httpx.HTTPStatusError as exc:
        msg = f"HTTP {exc.response.status_code} fetching {patent_number}: {exc}"
        logger.error("[fetch_patent] %s", msg)
        return {**state, "errors": state.get("errors", []) + [msg]}

    except httpx.RequestError as exc:
        msg = f"Network error fetching {patent_number}: {exc}"
        logger.error("[fetch_patent] %s", msg)
        return {**state, "errors": state.get("errors", []) + [msg]}

    logger.info(
        "[fetch_patent] OK — title: %s", data.get("title", "(no title)")[:80]
    )
    return {**state, "raw_api_response": data}
