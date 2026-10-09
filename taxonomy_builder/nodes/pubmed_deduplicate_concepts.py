import json
import logging
from collections import Counter
from taxonomy_builder.pubmed_state import PubMedGenerationState, CanonicalConcept
from pipeline.utils.llm_client import chat_json

logger = logging.getLogger(__name__)

# ── Generic concept blocklist ────────────────────────────────────────────────
# These are common patent-language words that carry zero taxonomic value.
# Any concept whose full name is in this set is dropped before embedding.
GENERIC_BLOCKLIST = {
    "method", "methods", "system", "systems", "device", "devices",
    "apparatus", "process", "processes", "technique", "techniques",
    "application", "applications", "approach", "approaches",
    "material", "materials", "composition", "compositions",
    "structure", "structures", "component", "components",
    "mechanism", "mechanisms", "procedure", "procedures",
    "invention", "embodiment", "embodiments", "feature", "features",
    "property", "properties", "parameter", "parameters",
    "step", "steps", "operation", "operations", "element", "elements",
}

# ── Embedding model (singleton) ───────────────────────────────────────────────
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        print("Loading high-accuracy CPU-optimized embedding model (fastembed BAAI/bge-small-en-v1.5)...")
        # pyrefly: ignore [missing-import]
        from fastembed import TextEmbedding
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model


def _batch_name_clusters(clusters: list[list[str]]) -> dict[int, str]:
    """
    Name ALL clusters via batched LLM calls (max 50 clusters per call).
    Chunking prevents token overflow when handling 200+ patents.
    """
    BATCH_SIZE = 50
    name_map: dict[int, str] = {}

    for batch_start in range(0, len(clusters), BATCH_SIZE):
        batch = clusters[batch_start : batch_start + BATCH_SIZE]
        batch_payload = [{"id": batch_start + i, "terms": c} for i, c in enumerate(batch)]

        prompt = f"""You are a technical terminology expert. Below are groups of synonymous terms extracted from patents.
For each group, provide the single most professional, standard scientific name.

RULES:
- Use full technical terms (e.g., "Tensile Strength", not "TS")
- Be consistent in naming style across all groups
- Do NOT use abbreviations unless they are the universal standard (e.g., "pH", "UV")
- Output ONLY a JSON object: {{"group_id": "Canonical Name", ...}}

Groups to name:
{json.dumps(batch_payload, indent=2)}
"""
        try:
            resp = chat_json(
                messages=[{"role": "user", "content": prompt}],
                cheap=True,
                max_tokens=4000
            )
            for k, v in resp.items():
                if str(k).isdigit():
                    name_map[int(k)] = v
        except Exception as e:
            print(f"Batch naming failed for batch starting at {batch_start}: {e}. Using fallback names.")

    return name_map


def deduplicate_concepts(state: PubMedGenerationState) -> dict:
    """
    Improvements applied:
    1. Generic concept blocklist — drops zero-value patent boilerplate before embedding.
    2. Raised similarity threshold 0.85 → 0.88 — stricter deduplication, fewer near-duplicates.
    3. Chunked batch naming (50 per call) — prevents token overflow at 100-200 patents.
    4. Aggregates domain_paths from raw concepts into each CanonicalConcept.
    """
    print("--- DEDUPLICATING CONCEPTS (OPEN SOURCE EMBEDDINGS) ---")
    all_concepts = state.get("all_concepts", [])
    if not all_concepts:
        return {"canonical_concepts": []}

    model = get_embedding_model()
    from taxonomy_builder.utils.embedding_utils import community_detection

    # ── Step 1: Get unique names ──────────────────────────────────────────────
    unique_names = list(set([c.name.lower().strip() for c in all_concepts]))
    unique_names = [n for n in unique_names if n]

    # ── Step 2: Blocklist filter ──────────────────────────────────────────────
    before_blocklist = len(unique_names)
    unique_names = [n for n in unique_names if n not in GENERIC_BLOCKLIST]
    dropped = before_blocklist - len(unique_names)
    if dropped:
        print(f"Blocklist filter: removed {dropped} generic patent-language concepts.")

    if not unique_names:
        return {"canonical_concepts": []}

    # ── Step 3: Compute embeddings locally ───────────────────────────────────
    print(f"Computing local embeddings for {len(unique_names)} unique concepts...")
    embeddings_raw = list(model.embed(unique_names))

    # ── Step 4: Community detection at RAISED threshold (0.85 → 0.88) ────────
    THRESHOLD = 0.88   # stricter — fewer near-duplicates slip through
    communities = community_detection(embeddings_raw, min_community_size=1, threshold=THRESHOLD)

    clusters = []
    for community in communities:
        cluster = [unique_names[idx] for idx in community]
        clusters.append(cluster)

    print(f"Reduced {len(unique_names)} raw concepts to {len(clusters)} canonical concepts.")

    # ── Step 5: Chunked batch naming (50 per call) ───────────────────────────
    print(f"Naming {len(clusters)} clusters (batched, 50 per call)...")
    name_map = _batch_name_clusters(clusters)

    # ── Step 6: Build CanonicalConcepts with aggregated domain_paths ─────────
    canonical_concepts = []

    for i, cluster in enumerate(clusters):
        canonical_name = name_map.get(i, clusters[i][0].title())

        supporting_pmids: set[str] = set()
        supporting_contexts: list[str] = []
        contexts_by_pmid: dict[str, list[str]] = {}
        domain_paths: list[list[str]] = []

        for c in all_concepts:
            if c.name.lower().strip() in cluster:
                supporting_pmids.add(c.pmid)
                supporting_contexts.append(c.context)
                contexts_by_pmid.setdefault(c.pmid, []).append(c.context)
                if c.domain_path:
                    domain_paths.append(c.domain_path)

        canonical_concepts.append(
            CanonicalConcept(
                name=canonical_name,
                supporting_pmids=list(supporting_pmids),
                supporting_contexts=supporting_contexts,
                contexts_by_pmid=contexts_by_pmid,
                domain_paths=domain_paths
            )
        )

    with_paths = sum(1 for c in canonical_concepts if c.domain_paths)
    print(f"Domain path coverage: {with_paths}/{len(canonical_concepts)} canonical concepts have domain ancestry.")

    out_data = {"canonical_concepts": canonical_concepts}

    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "deduplicate_concepts", state, out_data)

    return out_data
