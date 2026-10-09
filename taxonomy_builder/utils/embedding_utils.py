import numpy as np

def community_detection(embeddings, threshold=0.75, min_community_size=1):
    """
    Finds communities in a set of embeddings using purely NumPy.
    This exactly mimics the sentence_transformers.util.community_detection behavior
    without requiring the massive PyTorch dependency.
    """
    if not embeddings:
        return []
        
    if isinstance(embeddings, list):
        embeddings = np.array(embeddings)
    
    # Compute cosine similarity matrix
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings_normalized = embeddings / np.maximum(norms, 1e-9)
    cos_sim_matrix = np.dot(embeddings_normalized, embeddings_normalized.T)
    
    n = len(embeddings)
    extracted_communities = []
    remaining_nodes = set(range(n))
    
    while remaining_nodes:
        best_cluster = []
        
        # For each remaining node, find its neighbors above threshold
        for node in remaining_nodes:
            neighbors = [i for i in remaining_nodes if cos_sim_matrix[node][i] >= threshold]
            if len(neighbors) > len(best_cluster):
                best_cluster = neighbors
                
        if len(best_cluster) < min_community_size:
            # If no clusters meet the minimum size, break
            if min_community_size == 1:
                for node in remaining_nodes:
                    extracted_communities.append([node])
            break
            
        extracted_communities.append(best_cluster)
        for node in best_cluster:
            remaining_nodes.remove(node)
            
    return extracted_communities
