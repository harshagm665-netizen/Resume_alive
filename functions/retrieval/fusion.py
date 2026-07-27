"""
functions/retrieval/fusion.py — Reciprocal Rank Fusion (RRF).
"""
from typing import List, Dict, Any

def reciprocal_rank_fusion(dense_results: List[Dict[str, Any]], sparse_results: List[Dict[str, Any]], k: int = 60) -> List[Dict[str, Any]]:
    """
    Fuses sparse and dense results using RRF.
    Groups results by parent_id (job) and scores them.
    """
    # Group by parent_id, accumulating RRF scores
    scores = {}
    job_metadata = {}
    
    # Process dense results
    for rank, res in enumerate(dense_results):
        parent_id = res["parent_id"]
        if parent_id not in scores:
            scores[parent_id] = 0.0
            job_metadata[parent_id] = {"parent_id": parent_id, "chunks": []}
            
        scores[parent_id] += 1.0 / (k + rank + 1)
        job_metadata[parent_id]["chunks"].append(res)
        
    # Process sparse results
    for rank, res in enumerate(sparse_results):
        parent_id = res["parent_id"]
        if parent_id not in scores:
            scores[parent_id] = 0.0
            job_metadata[parent_id] = {"parent_id": parent_id, "chunks": []}
            
        scores[parent_id] += 1.0 / (k + rank + 1)
        # Avoid duplicate chunks if they were in both dense and sparse
        existing_chunks = {c["chunk_id"] for c in job_metadata[parent_id]["chunks"]}
        if res["chunk_id"] not in existing_chunks:
            job_metadata[parent_id]["chunks"].append(res)
            
    # Sort by RRF score
    sorted_parents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    final_results = []
    for parent_id, score in sorted_parents:
        data = job_metadata[parent_id]
        data["hybrid_score"] = score
        final_results.append(data)
        
    return final_results
