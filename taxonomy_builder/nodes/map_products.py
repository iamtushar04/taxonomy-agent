"""
map_products.py

Downstream additive node in Taxonomy Builder:
Executes ONLY if products_data is provided in state.
Matches commercial product features against finalized taxonomy nodes based on
strict claim & specification evidence.
"""

import json
from typing import Dict, Any, List
from taxonomy_builder.state import TaxonomyGenerationState
from taxonomy_builder.utils.tracer import log_node_event

def map_products(state: TaxonomyGenerationState) -> dict:
    products_data = state.get("products_data", {})
    final_taxonomy = state.get("final_taxonomy", [])

    # If no product docs were uploaded, pass through unmodified (zero risk)
    if not products_data or not final_taxonomy:
        return {"final_taxonomy": final_taxonomy}

    print(f"--- MAPPING {len(products_data)} PRODUCTS TO TAXONOMY NODES ---")

    try:
        from pipeline.utils.llm_client import chat_completion

        # Prepare compact summaries of taxonomy nodes (Level 1, 2, and leaf nodes)
        nodes_summary = []
        for n in final_taxonomy:
            nodes_summary.append({
                "node_id": n.get("node_id"),
                "name": n.get("name"),
                "level": n.get("level"),
                "description": n.get("description", "")
            })

        # Prepare compact product features summary
        products_summary = []
        for p_id, p_info in products_data.items():
            products_summary.append({
                "product_id": p_id,
                "product_name": p_info.get("product_name"),
                "features": p_info.get("features", [])[:8],
                "summary": p_info.get("full_text_snippet", "")[:300]
            })

        system_prompt = (
            "You are an expert Patent and Commercial Product Alignment Analyst.\n"
            "Your task is to identify which finalized taxonomy nodes each commercial product implements or relates to.\n"
            "MATCHING CRITERIA:\n"
            "1. Map a product to a node if the product's documented features, technical mechanism, or domain subject matter clearly relates to that taxonomy category.\n"
            "2. Map to both relevant high-level categories (e.g. Biotechnology, Peptide Therapeutics) and specific sub-technology nodes where appropriate.\n"
            "3. Return a clean JSON array of mappings: [{'node_id': '...', 'product_ids': ['...']}]\n"
            "Only return the JSON array, no extra conversational text."
        )

        user_content = f"TAXONOMY NODES:\n{json.dumps(nodes_summary, indent=1)}\n\nPRODUCTS:\n{json.dumps(products_summary, indent=1)}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        response_text = chat_completion(messages, model="gpt-4o-mini").strip()
        # Clean potential markdown fences
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("\n", 1)[0]

        mappings = json.loads(response_text)
        
        # Build node_id -> set of product_ids map
        node_product_map = {}
        for m in mappings:
            nid = m.get("node_id")
            pids = m.get("product_ids", [])
            if nid and pids:
                if nid not in node_product_map:
                    node_product_map[nid] = set()
                node_product_map[nid].update(pids)

        # Update final_taxonomy nodes with supporting_product_ids (unioning with existing)
        updated_taxonomy = []
        for node in final_taxonomy:
            node_copy = dict(node)
            existing_pids = set(node_copy.get("supporting_product_ids") or [])
            matched_products = set(node_product_map.get(node.get("node_id"), []))
            all_products = sorted(list(existing_pids | matched_products))
            node_copy["supporting_product_ids"] = all_products
            updated_taxonomy.append(node_copy)

        out_data = {"final_taxonomy": updated_taxonomy}
        log_node_event(state.get("run_id", "default"), "map_products", state, out_data)
        return out_data

    except Exception as e:
        print(f"Error mapping products to taxonomy: {e}")
        # Safe fallback: preserve original final_taxonomy untouched
        return {"final_taxonomy": final_taxonomy}
