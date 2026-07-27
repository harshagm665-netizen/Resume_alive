"""
functions/retrieval/retrieval_agent.py — Agent orchestrating the hybrid retrieval.
"""
from typing import List, Dict, Any
from loguru import logger
from agents.base_agent import BaseAgent
from db.models import Job
from retrieval.chunker import chunker
from retrieval.dense_search import dense_search
from retrieval.sparse_search import sparse_search
from retrieval.fusion import reciprocal_rank_fusion
from llm.temperature import TaskType

class RetrievalAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Retrieval Agent",
            role="Hybrid semantic search engine.",
            goal="Index discovered jobs and retrieve the most relevant ones for a user query.",
            task_type=TaskType.JSON_OUTPUT
        )
        self.register_tool("index_jobs", "Indexes a batch of jobs", self.index_jobs)
        self.register_tool("search", "Searches indexed jobs", self.search)

    def index_jobs(self, jobs: List[Job]) -> None:
        """Chunks and indexes jobs into dense and sparse stores."""
        if not jobs:
            return
            
        logger.info(f"[{self.name}] Chunking {len(jobs)} jobs...")
        all_chunks = []
        for job in jobs:
            all_chunks.extend(chunker.chunk_job(job))
            
        logger.info(f"[{self.name}] Indexing {len(all_chunks)} chunks...")
        dense_search.index_chunks(all_chunks)
        sparse_search.index_chunks(all_chunks)
        logger.info(f"[{self.name}] Indexing complete.")

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Runs hybrid search and returns fused results."""
        logger.info(f"[{self.name}] Searching for '{query}'...")
        
        dense_res = dense_search.search(query, limit=limit*2)
        sparse_res = sparse_search.search(query, limit=limit*2)
        
        fused = reciprocal_rank_fusion(dense_res, sparse_res)
        
        # Return top N parent jobs
        return fused[:limit]
