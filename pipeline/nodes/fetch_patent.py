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
    logger.info("[fetch_patent] Fetching: %s", patent_number)

    api_key = os.environ.get("WISSEN_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    url = f"{_BASE_URL}/patent/{patent_number}"

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

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
