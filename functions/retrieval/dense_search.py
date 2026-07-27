"""
functions/retrieval/dense_search.py — Qdrant Cloud Vector Search.
"""
from typing import List, Dict, Any
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from config import QDRANT_URL, QDRANT_API_KEY
from retrieval.embedder import embedder

class DenseSearch:
    def __init__(self, collection_name: str = "jobs"):
        self.collection_name = collection_name
        self.client = None
        if QDRANT_URL and QDRANT_API_KEY:
            try:
                self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
                self._ensure_collection()
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")

    def _ensure_collection(self):
        if not self.client:
            return
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE)
            )

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        if not self.client or not chunks:
            return
            
        texts = [c["text"] for c in chunks]
        embeddings = embedder.embed_texts(texts)
        
        points = []
        for i, chunk in enumerate(chunks):
            points.append(PointStruct(
                id=chunk["chunk_id"],
                vector=embeddings[i],
                payload=chunk
            ))
            
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Indexed {len(points)} chunks in Qdrant.")

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns dense search results mapping chunk_id to score and parent_id."""
        if not self.client:
            return []
            
        query_vector = embedder.embed_query(query)
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )
        
        results = []
        for hit in hits:
            results.append({
                "chunk_id": str(hit.id),
                "parent_id": hit.payload.get("parent_id"),
                "score": hit.score,
                "text": hit.payload.get("text", "")
            })
        return results

dense_search = DenseSearch()
