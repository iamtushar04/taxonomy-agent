"""
product_tools.py — Native tools for commercial product inspection in Chatbot Agent.
"""

from typing import Any, Optional


def search_products(
    query: str,
    source_data: Optional[dict[str, Any]] = None,
    product_doc_text: Optional[str] = None
) -> dict[str, Any]:
    """
    Search and inspect commercial product specifications, capabilities, and features.
    """
    products_map = source_data.get("_products", {}) if isinstance(source_data, dict) else {}
    
    query_lower = query.lower().strip()
    words = query_lower.split()

    matched_products = []
    for pid, p_info in products_map.items():
        name = p_info.get("product_name", "").lower()
        features = p_info.get("features", [])
        features_text = " ".join(features).lower()
        brand = (p_info.get("brand_or_assignee") or "").lower()
        snippet = (p_info.get("full_text_snippet") or "").lower()

        score = 0
        if query_lower in name or query_lower in features_text:
            score += 10
        elif any(w in name or w in features_text or w in snippet for w in words):
            score += 5

        if score > 0 or not query_lower:
            matched_products.append({
                "product_id": pid,
                "product_name": p_info.get("product_name", pid),
                "brand_or_assignee": p_info.get("brand_or_assignee", "Unknown"),
                "features": features[:8],
                "summary": p_info.get("full_text_snippet", "")[:250],
                "score": score
            })

    matched_products.sort(key=lambda x: x["score"], reverse=True)

    if not matched_products and product_doc_text:
        return {
            "total_matches": 0,
            "raw_product_text": product_doc_text[:800],
            "note": "No structured product cards matched, but raw product documentation was found."
        }

    return {
        "total_matches": len(matched_products),
        "products": matched_products
    }
