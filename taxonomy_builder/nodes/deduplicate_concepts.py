import os
import math
import logging
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

def deduplicate_concepts(state: TaxonomyGenerationState) -> dict:
    """
    Uses open-source SentenceTransformers to cluster semantic duplicates.
    Collapses hundreds of variations into CanonicalConcepts using LLM for naming.
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
    
    # 2. Fetch Embeddings locally (Convert to PyTorch tensor for advanced clustering)
    print(f"Computing local embeddings for {len(unique_names)} unique concepts...")
    embeddings_raw = model.encode(unique_names, convert_to_tensor=True)
            
    # 3. Advanced Community Detection Clustering
    THRESHOLD = 0.85 # 85% similarity threshold for dense clusters
    
    communities = util.community_detection(embeddings_raw, min_community_size=1, threshold=THRESHOLD)
    
    clusters = [] 
    for community in communities:
        cluster = [unique_names[idx] for idx in community]
        clusters.append(cluster)
            
    print(f"Reduced {len(unique_names)} raw concepts to {len(clusters)} canonical concepts.")
    
    # 4. Map back to original concepts and build CanonicalConcepts
    canonical_concepts = []
    
    for cluster in clusters:
        # Use LLM to generate a professional canonical name
        prompt = f"Given these synonymous technical terms: {cluster}, output a single JSON object with a 'name' key containing the most professional, standard scientific term for this group. Do not use abbreviations unless standard."
        try:
            resp = chat_json([{"role": "user", "content": prompt}], cheap=True)
            canonical_name = resp.get("name", cluster[0].title())
        except Exception:
            canonical_name = cluster[0].title()

        
        supporting_patent_ids = set()
        supporting_contexts = []
        
        for c in all_concepts:
            if c.name.lower().strip() in cluster:
                supporting_patent_ids.add(c.patent_id)
                supporting_contexts.append(c.context)
                
        canonical_concepts.append(
            CanonicalConcept(
                name=canonical_name,
                supporting_patent_ids=list(supporting_patent_ids),
                supporting_contexts=supporting_contexts
            )
        )
        
    out_data = {"canonical_concepts": canonical_concepts}
    
    from taxonomy_builder.utils.tracer import log_node_event
    log_node_event(state.get("run_id", "default"), "deduplicate_concepts", state, out_data)
    
    return out_data
