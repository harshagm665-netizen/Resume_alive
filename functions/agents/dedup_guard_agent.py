"""
functions/agents/dedup_guard_agent.py — Agent wrapper for the DedupGuard.
"""
from typing import List, Tuple
from loguru import logger
from agents.base_agent import BaseAgent
from cache.dedup_guard import dedup_guard
from db.models import Job
from llm.temperature import TaskType

class DedupGuardAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Dedup Guard Agent",
            role="Quality control to prevent spam and duplicate jobs.",
            goal="Filter out jobs the user has already seen or jobs that look like repetitive spam posts.",
            task_type=TaskType.DEDUP_DECISION
        )
        # Register the deterministic python tool for the agent
        self.register_tool(
            name="filter_jobs",
            description="Filters a list of jobs based on global spam thresholds and user seen-history.",
            func=self._filter
        )

    def _filter(self, uid: str, jobs: List[Job]) -> Tuple[List[Job], int]:
        return dedup_guard.filter_jobs(uid, jobs)
        
    def filter(self, uid: str, jobs: List[Job]) -> Tuple[List[Job], int]:
        """
        Executes the dedup filtering. 
        While it's an 'agent', for performance we bypass the LLM and directly invoke the deterministic tool.
        """
        logger.info(f"[{self.name}] Filtering {len(jobs)} jobs for user {uid}")
        return self._filter(uid, jobs)
