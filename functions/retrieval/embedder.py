"""
functions/retrieval/embedder.py — Gemini Embeddings.
"""
from typing import List
from loguru import logger
from config import GEMINI_API_KEY

class Embedder:
    """Generates embeddings using Gemini text-embedding-004."""
    
    def __init__(self):
        self.model = "text-embedding-004"
        
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY missing, skipping embeddings.")
            return [[0.0] * 768 for _ in texts]
            
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=GEMINI_API_KEY)
            result = client.models.embed_content(
                model=self.model,
                contents=texts
            )
            return [e.values for e in result.embeddings]
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return [[0.0] * 768 for _ in texts]
            
    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]

embedder = Embedder()
