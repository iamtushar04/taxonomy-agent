"""
rag_retriever.py — Retrieve relevant taxonomy nodes for Q&A.

Simple keyword-based retrieval over the final_taxonomy + source_data.
Designed to be upgraded to embedding-based retrieval later without changing the interface.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def retrieve_relevant_nodes(
    query: str,
    taxonomy: list[dict[str, Any]],
    source_data: dict[str, Any] | None = None,
    history_messages: list | None = None,
    top_k: int = 6
) -> list[dict[str, Any]]:
    """
    Retrieve the most relevant taxonomy nodes for a user query.

    Strategy:
    1. Tokenize query. If follow-up question (few tokens), expand using recent history.
    2. Score nodes by matching across:
       - Node Name (3x weight + exact phrase bonus)
       - Node Description (1.5x weight)
       - Linked Product Features (3.5x weight)
       - Patent Claims Context (2.0x weight)
       - Direct Patent ID match (10x boost)
    3. Return top_k nodes sorted by score, including parent hierarchy.
    """
    if not taxonomy:
        return []

    source_data = source_data or {}
    products_map = source_data.get("_products", {}) if isinstance(source_data, dict) else {}

    query_tokens = _tokenize(query)

    # Context expansion for follow-up questions like "are you telling me?" or "which ones?"
    if len(query_tokens) < 3 and history_messages:
        for m in reversed(history_messages[-4:]):
            content = m.content if hasattr(m, "content") else (m.get("content", "") if isinstance(m, dict) else "")
            role = m.role if hasattr(m, "role") else (m.get("role", "") if isinstance(m, dict) else "")
            if role == "user" and content:
                hist_tokens = _tokenize(content)
                if len(hist_tokens) >= 2:
                    query_tokens.update(hist_tokens)
                    break

    # Build node_id -> node map for fast lookup
    node_map = {n.get("node_id"): n for n in taxonomy if n.get("node_id")}

    scored_nodes = []
    for node in taxonomy:
        score = _score_node_comprehensive(node, query_tokens, products_map, source_data, query.lower())
        if score > 0:
            scored_nodes.append((score, node))

    # Sort by score descending
    scored_nodes.sort(key=lambda x: x[0], reverse=True)

    top_nodes = [node for _, node in scored_nodes[:top_k]]

    # If no matches, return top-level nodes as fallback
    if not top_nodes:
        top_nodes = [n for n in taxonomy if n.get("level", 1) <= 2][:top_k]

    logger.info(f"[rag_retriever] Retrieved {len(top_nodes)} nodes for query: '{query[:60]}'")
    return top_nodes


def _stem(word: str) -> str:
    """Normalize word endings for robust matching against typos and inflectional forms."""
    w = word.lower()
    for suffix in ("ing", "ments", "ment", "tions", "tion", "ities", "ity", "ies", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            return w[:-len(suffix)]
    return w


def _tokenize(text: str) -> set[str]:
    """Convert text to a set of lowercase stems, removing stopwords and query boilerplate."""
    STOPWORDS = {
        "the", "a", "an", "is", "it", "in", "on", "at", "for",
        "to", "of", "and", "or", "but", "why", "how", "what",
        "where", "when", "does", "this", "that", "here", "there",
        "i", "you", "we", "they", "he", "she", "be", "are", "was",
        "were", "can", "will", "would", "should", "could", "with",
        "under", "about", "which", "by", "from", "as", "my", "its",
        "me", "tell", "show", "has", "have", "had", "just", "then",
        "please", "give", "get", "got", "also", "part", "only",
        "many", "belong", "belongs", "patent", "patents", "product",
        "products", "feature", "features", "fetaures", "item", "items",
        "how", "count", "number", "much", "relate", "related", "list"
    }
    raw_tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {_stem(t) for t in raw_tokens if t not in STOPWORDS}


def _score_node_comprehensive(
    node: dict[str, Any],
    query_tokens: set[str],
    products_map: dict[str, Any],
    source_data: dict[str, Any],
    raw_query_lower: str
) -> float:
    """
    Comprehensive multi-field score for a taxonomy node.
    """
    score = 0.0

    name = node.get("name", "")
    description = node.get("description", "")
    name_lower = name.lower()
    desc_lower = description.lower()

    # 1. Node Name match (6.0x per stem token + 4.0 for prefix match)
    name_tokens = _tokenize(name)
    name_overlap = len(query_tokens & name_tokens)
    score += name_overlap * 6.0

    for qt in query_tokens:
        prefix = qt[:5] if len(qt) >= 5 else qt
        if prefix in name_lower:
            score += 4.0

    # 2. Node Description match (3.0x per stem token + 3.0 for prefix match)
    desc_tokens = _tokenize(description)
    desc_overlap = len(query_tokens & desc_tokens)
    score += desc_overlap * 3.0

    for qt in query_tokens:
        prefix = qt[:5] if len(qt) >= 5 else qt
        if prefix in desc_lower:
            score += 3.0

    # 3. Product capability alignment (4.0x weight)
    # Check linked product features
    prod_ids = node.get("supporting_product_ids", [])
    for pid in prod_ids:
        p_info = products_map.get(pid, {})
        for feat in p_info.get("features", []):
            feat_lower = feat.lower()
            feat_tokens = _tokenize(feat)
            feat_overlap = len(query_tokens & feat_tokens)
            if feat_overlap > 0:
                score += feat_overlap * 4.0
            for qt in query_tokens:
                prefix = qt[:5] if len(qt) >= 5 else qt
                if prefix in feat_lower:
                    score += 3.0

    # 4. Patent Evidence & Claim Context (2.5x weight)
    ctx_map = node.get("contexts_by_patent", {})
    for pid, contexts in ctx_map.items():
        if pid.lower() in raw_query_lower:
            score += 15.0
        for ctx in contexts:
            ctx_tokens = _tokenize(ctx)
            c_overlap = len(query_tokens & ctx_tokens)
            if c_overlap > 0:
                score += min(c_overlap, 3) * 2.5
            for qt in query_tokens:
                prefix = qt[:5] if len(qt) >= 5 else qt
                if prefix in ctx.lower():
                    score += 2.0

    # 5. Direct patent ID mention in query
    supporting_pids = [p.lower() for p in node.get("supporting_patent_ids", [])]
    for pid in supporting_pids:
        if pid in raw_query_lower:
            score += 20.0

    # 6. Specificity adjustments: boost leaf nodes (Level 3 & 4), penalize generic root (Level 0)
    lvl = node.get("level", 1)
    if lvl in (3, 4):
        score += 2.0
    elif lvl == 0:
        score -= 10.0

    return score


# ---------------------------------------------------------------------------
# Future: Embedding-based retrieval (upgrade path)
# ---------------------------------------------------------------------------
# To upgrade to semantic retrieval:
# 1. At taxonomy build time, generate embeddings for each node name+description
#    and store them in source_data or a separate vector store.
# 2. Replace retrieve_relevant_nodes with an embedding similarity search.
# 3. The calling interface (query, taxonomy, source_data, top_k) stays the same.
