import json
import logging
from collections import Counter
from taxonomy_builder.state import TaxonomyGenerationState, CanonicalConcept
from pipeline.utils.llm_client import chat_json

logger = logging.getLogger(__name__)

# Load model once globally to avoid reloading on every run
_model = None
def get_embedding_model():
    global _model
    if _model is None:
        print("Loading high-accuracy open-source embedding model (all-mpnet-base-v2)...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-mpnet-base-v2')
    return _model


def _batch_name_clusters(clusters: list[list[str]]) -> dict[int, str]:
    """
    Fix 1: Name ALL clusters in a SINGLE LLM call instead of one call per cluster.
    Previously: 117 LLM calls (slow, expensive, inconsistent naming style).
    Now: 1 LLM call (fast, cheap, consistent naming across all clusters).
    """
    clusters_payload = [{"id": i, "terms": c} for i, c in enumerate(clusters)]

    prompt = f"""You are a technical terminology expert. Below are groups of synonymous terms extracted from patents.
For each group, provide the single most professional, standard scientific name.

RULES:
- Use full technical terms (e.g., "Tensile Strength", not "TS")
- Be consistent in naming style across all groups
- Do NOT use abbreviations unless they are the universal standard (e.g., "pH", "UV")
- Output ONLY a JSON object: {{"group_id": "Canonical Name", ...}}

Groups to name:
{json.dumps(clusters_payload, indent=2)}
"""

    try:
        resp = chat_json(
            messages=[{"role": "user", "content": prompt}],
            cheap=True,
            max_tokens=4000
        )
        # Keys may come back as strings; normalize to int
        return {int(k): v for k, v in resp.items() if str(k).isdigit()}
    except Exception as e:
        print(f"Batch naming failed: {e}. Falling back to cluster[0].title().")
        return {}


def deduplicate_concepts(state: TaxonomyGenerationState) -> dict:
    """
    Fix 1 + domain_path aggregation:
    - Uses open-source SentenceTransformers to cluster semantic duplicates.
    - Names ALL clusters in ONE batched LLM call (was: one call per cluster).
    - Aggregates domain_paths from raw concepts into each CanonicalConcept
      so downstream nodes (group_concepts, build_hierarchy) can use patent-grounded
      evidence for the tree backbone.
    """
    print("--- DEDUPLICATING CONCEPTS (OPEN SOURCE EMBEDDINGS) ---")
    all_concepts = state.get("all_concepts", [])
    if not all_concepts:
        return {"canonical_concepts": []}

    model = get_embedding_model()
    from sentence_transformers import util

    # 1. Get unique names to save embedding costs
    unique_names = list(set([c.name.lower().strip() for c in all_concepts]))
    unique_names = [n for n in unique_names if n]

    if not unique_names:
        return {"canonical_concepts": []}

    # 2. Fetch embeddings locally
    print(f"Computing local embeddings for {len(unique_names)} unique concepts...")
    embeddings_raw = model.encode(unique_names, convert_to_tensor=True)

    # 3. Community detection clustering at 85% similarity
    THRESHOLD = 0.85
    communities = util.community_detection(embeddings_raw, min_community_size=1, threshold=THRESHOLD)

    clusters = []
    for community in communities:
        cluster = [unique_names[idx] for idx in community]
        clusters.append(cluster)

    print(f"Reduced {len(unique_names)} raw concepts to {len(clusters)} canonical concepts.")

    # 4. FIX 1: Batch ALL cluster naming in ONE LLM call
    print(f"Naming {len(clusters)} clusters in a single batched LLM call...")
    name_map = _batch_name_clusters(clusters)

    # 5. Build CanonicalConcepts with domain_path aggregation
    canonical_concepts = []

    for i, cluster in enumerate(clusters):
        canonical_name = name_map.get(i, clusters[i][0].title())

        supporting_patent_ids = set()
        supporting_contexts = []
        domain_paths = []          # FIX: aggregate domain_paths from all raw concepts in cluster

        for c in all_concepts:
            if c.name.lower().strip() in cluster:
                supporting_patent_ids.add(c.patent_id)
                supporting_contexts.append(c.context)
                if c.domain_path:                      # domain_path from extract_concepts.py
                    domain_paths.append(c.domain_path)

        canonical_concepts.append(
            CanonicalConcept(
                name=canonical_name,
                supporting_patent_ids=list(supporting_patent_ids),
                supporting_contexts=supporting_contexts,
                domain_paths=domain_paths              # FIX: populate new field
            )
        )

    # Log domain_path coverage
    with_paths = sum(1 for c in canonical_concepts if c.domain_paths)
    print(f"Domain path coverage: {with_paths}/{len(canonical_concepts)} canonical concepts have domain ancestry.")

    out_data = {"canonical_concepts": canonical_concepts}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "deduplicate_concepts", state, out_data)

    return out_data
