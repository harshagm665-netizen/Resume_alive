"""
functions/agents/market_intel.py — Agent for analyzing market trends.
"""
from typing import List
from loguru import logger
from agents.base_agent import BaseAgent
from llm.client import llm
from llm.temperature import TaskType
from db.models import Job

class MarketIntelAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Market Intel",
            role="Data Analyst",
            goal="Identify hiring trends, salary benchmarks, and demand for skills in a set of jobs.",
            task_type=TaskType.MARKET_ANALYSIS
        )
        
    def analyze_market(self, jobs: List[Job], query: str, location: str) -> str:
        """Analyzes a set of jobs to produce market insights."""
        logger.info(f"[{self.name}] Analyzing {len(jobs)} jobs for '{query}' in {location}...")
        if not jobs:
            return "No jobs available for market analysis."
            
        system = "You are an expert market analyst. Summarize the job market based on the provided job listings. Discuss salary ranges (if any), top required skills, and hiring patterns."
        
        job_data = ""
        for i, j in enumerate(jobs[:20]):
            job_data += f"\n{i+1}. {j.title} at {j.company} | Salary: {j.salary} | Exp: {j.experience}"
            
        user = f"Query: {query}\nLocation: {location}\n\nJobs:\n{job_data}\n\nProvide a concise 3-paragraph summary."
        
        try:
            return llm.chat(system, user, self.task_type)
        except Exception as e:
            logger.error(f"Market analysis failed: {e}")
            return "Failed to perform market analysis."
