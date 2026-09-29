"""
OpenAI client wrapper.

Centralises:
- API key loading
- Model selection (main vs. cheap)
- Structured JSON response parsing
- Retry logic with exponential backoff
- Token usage logging
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIError, APIConnectionError, RateLimitError
from langfuse.openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Always resolve .env from the project root (two levels up from this file)
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------
_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        # Re-load dotenv in case the singleton is being created after a late import
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                f"OPENAI_API_KEY not found. Checked .env at: {_ENV_PATH}. "
                "Please set the key in your .env file."
            )
        _client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialised (key prefix: %s...)", api_key[:8])
    return _client


# ---------------------------------------------------------------------------
# Models (read from env with sensible defaults)
# ---------------------------------------------------------------------------
def _main_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o")


def _cheap_model() -> str:
    return os.environ.get("OPENAI_RELEVANCE_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Core call — retried automatically on transient errors
# ---------------------------------------------------------------------------
@retry(
    # Only retry on transient OpenAI API errors — NOT on config/env errors
    retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def chat_completion(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    max_tokens: int = 4096,
) -> str:
    """
    Call the OpenAI Chat Completions API and return the assistant text.

    Args:
        messages:    Standard OpenAI messages list.
        model:       Override model; defaults to OPENAI_MODEL env var.
        temperature: Sampling temperature (0 = deterministic).
        json_mode:   If True, sets response_format to json_object.
        max_tokens:  Maximum tokens in the response.

    Returns:
        The assistant's text content as a plain string.
    """
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": model or _main_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    usage = response.usage
    logger.debug(
        "LLM call | model=%s | prompt_tokens=%s | completion_tokens=%s",
        kwargs["model"],
        usage.prompt_tokens if usage else "?",
        usage.completion_tokens if usage else "?",
    )
    return response.choices[0].message.content or ""


@retry(
    retry=retry_if_exception_type(ValueError),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
def chat_json(
    messages: list[dict],
    *,
    model: str | None = None,
    cheap: bool = False,
    max_tokens: int = 4096,
) -> dict:
    """
    Like chat_completion but always returns a parsed JSON dict.
    Uses the cheap model when cheap=True (good for relevance scoring).
    Automatically retries up to 3 times if the LLM hallucinates invalid JSON.
    """
    resolved_model = model or (_cheap_model() if cheap else _main_model())
    raw = chat_completion(
        messages,
        model=resolved_model,
        temperature=0.0,
        json_mode=True,
        max_tokens=max_tokens,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("JSON decode failed. Raw response:\n%s", raw)
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc
