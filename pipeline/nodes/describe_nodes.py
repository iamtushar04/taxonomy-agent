"""
Node 3 — describe_nodes

For every taxonomy node, generate a short LLM description of what
information should be extracted from a patent for that node.

This runs ONCE per taxonomy (not per patent) and caches results to disk.
On subsequent runs the cache is loaded immediately — no API calls.

Cache file: {CACHE_DIR}/node_descriptions_{taxonomy_hash}.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from pipeline.state import PatentExtractionState, TaxonomyNode
from pipeline.utils.llm_client import chat_json
from pipeline.utils.node_rules import format_rules_for_prompt

load_dotenv()
logger = logging.getLogger(__name__)

_CACHE_DIR = Path(os.environ.get("CACHE_DIR", ".cache"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _taxonomy_hash(nodes: list[TaxonomyNode]) -> str:
    """Stable hash of the taxonomy so the cache invalidates on taxonomy change."""
    combined = "|".join(n["path"] for n in sorted(nodes, key=lambda x: x["path"]))
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def _load_cache(cache_file: Path) -> dict[str, str]:
    if cache_file.exists():
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not load cache %s: %s", cache_file, exc)
    return {}


def _save_cache(cache_file: Path, data: dict[str, str]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _describe_batch(nodes: list[TaxonomyNode]) -> dict[str, str]:
    """
    Ask GPT-4o to generate descriptions for a batch of nodes in ONE call.
    Returns {node_id: description}.
    """
    node_list_text = "\n".join(
        f'{i+1}. node_id="{n["node_id"]}" | path="{n["path"]}"'
        for i, n in enumerate(nodes)
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a patent analysis expert. "
                "For each taxonomy node provided, write a concise 2-sentence description "
                "explaining exactly what information should be extracted from a patent for that node. "
                "Be specific about what types of values, units, or qualitative information to look for. "
                "Return a JSON object where each key is the node_id and each value is the description string."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate extraction descriptions for these {len(nodes)} taxonomy nodes:\n\n"
                f"{node_list_text}\n\n"
                "Return JSON: {\"<node_id>\": \"<description>\", ...}"
            ),
        },
    ]

    return chat_json(messages, max_tokens=4096)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

_BATCH_SIZE = 20   # nodes per LLM call


def describe_nodes(state: PatentExtractionState) -> PatentExtractionState:
    """
    LangGraph node: generate and cache descriptions for all taxonomy nodes.

    Reads:   state["taxonomy_nodes"]
    Writes:  state["taxonomy_nodes"]  (mutated in-place — description field filled)
    """
    nodes: list[TaxonomyNode] = state.get("taxonomy_nodes") or []
    if not nodes:
        logger.warning("[describe_nodes] No taxonomy nodes in state")
        return state

    # Check cache
    t_hash = _taxonomy_hash(nodes)
    cache_file = _CACHE_DIR / f"node_descriptions_{t_hash}.json"
    cache = _load_cache(cache_file)

    needs_description = [n for n in nodes if not n.get("description") and n["node_id"] not in cache]

    if needs_description:
        logger.info(
            "[describe_nodes] Generating descriptions for %d nodes (batch_size=%d)",
            len(needs_description), _BATCH_SIZE,
        )
        for i in range(0, len(needs_description), _BATCH_SIZE):
            batch = needs_description[i : i + _BATCH_SIZE]
            logger.info(
                "[describe_nodes] Batch %d/%d",
                i // _BATCH_SIZE + 1,
                (len(needs_description) + _BATCH_SIZE - 1) // _BATCH_SIZE,
            )
            try:
                result = _describe_batch(batch)
                cache.update(result)
            except Exception as exc:
                logger.error("[describe_nodes] Batch failed: %s", exc)
                # Use fallback description so pipeline can continue
                for n in batch:
                    cache[n["node_id"]] = (
                        f"Extract information related to '{n['name']}' from the patent. "
                        f"Include any relevant values, measurements, or qualitative descriptions."
                    )

        _save_cache(cache_file, cache)
        logger.info("[describe_nodes] Descriptions cached → %s", cache_file)
    else:
        logger.info("[describe_nodes] All descriptions loaded from cache")

    # Apply descriptions and rules back to nodes
    updated_nodes: list[TaxonomyNode] = []
    for node in nodes:
        description = cache.get(node["node_id"], node.get("description", ""))
        updated_nodes.append({
            **node,
            "description": description,
        })

    return {**state, "taxonomy_nodes": updated_nodes}
