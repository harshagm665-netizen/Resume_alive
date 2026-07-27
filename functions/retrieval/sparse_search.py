"""
functions/retrieval/sparse_search.py — Simple BM25 or keyword matching.
"""
from typing import List, Dict, Any
import math
from collections import Counter
import re

class SparseSearch:
    """In-memory BM25 index for sparse retrieval. Usually handled by Elastic/Typesense, 
    but we will implement a lightweight version for the cloud function."""
    
    def __init__(self):
        self.documents = {} # chunk_id -> dict
        self.doc_tokens = {} # chunk_id -> list of tokens
        self.df = Counter()
        self.doc_count = 0
        self.avgdl = 0
        self.k1 = 1.5
        self.b = 0.75
        
    def clear(self):
        self.documents = {}
        self.doc_tokens = {}
        self.df = Counter()
        self.doc_count = 0
        self.avgdl = 0
        
    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())
        
    def index_chunks(self, chunks: List[Dict[str, Any]]):
        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            if chunk_id in self.documents:
                continue
                
            self.documents[chunk_id] = chunk
            tokens = self._tokenize(chunk["text"])
            self.doc_tokens[chunk_id] = tokens
            
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.df[token] += 1
                
            self.doc_count += 1
            
        if self.doc_count > 0:
            total_len = sum(len(t) for t in self.doc_tokens.values())
            self.avgdl = total_len / self.doc_count
            
    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        if self.doc_count == 0:
            return []
            
        q_tokens = self._tokenize(query)
        scores = {}
        
        for chunk_id, d_tokens in self.doc_tokens.items():
            score = 0.0
            doc_len = len(d_tokens)
            term_freqs = Counter(d_tokens)
            
            for q_term in q_tokens:
                if q_term not in term_freqs:
                    continue
                    
                tf = term_freqs[q_term]
                idf = math.log(1 + (self.doc_count - self.df[q_term] + 0.5) / (self.df[q_term] + 0.5))
                num = tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * (num / den)
                
            if score > 0:
                scores[chunk_id] = score
                
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        results = []
        for chunk_id, score in sorted_scores:
            results.append({
                "chunk_id": chunk_id,
                "parent_id": self.documents[chunk_id]["parent_id"],
                "score": score,
                "text": self.documents[chunk_id]["text"],
                "job_data": self.documents[chunk_id].get("job_data", {})
            })
        return results

sparse_search = SparseSearch()
