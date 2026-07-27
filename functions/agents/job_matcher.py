"""
functions/agents/job_matcher.py — Agent for scoring and re-ranking jobs against a profile.
"""
from typing import Dict, Any, List
from loguru import logger
from agents.base_agent import BaseAgent
from db.models import Job, UserProfile
from llm.client import llm
from llm.prompts import JOB_SCORE_SYSTEM, JOB_SCORE_USER, GENERIC_SEARCH_SCORE_SYSTEM, GENERIC_SEARCH_SCORE_USER
from llm.temperature import TaskType

class JobMatcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Job Matcher",
            role="Technical Recruiter",
            goal="Score and re-rank job listings based on relevance to the user's profile.",
            task_type=TaskType.JOB_SCORING
        )
        
    def score_job(self, job: Job, profile: UserProfile) -> Dict[str, Any]:
        """Scores a job against a user profile."""
        logger.info(f"[{self.name}] Scoring '{job.title}' at {job.company} for {profile.uid}...")
        
        user_prompt = JOB_SCORE_USER.format(
            current_role=profile.current_role,
            total_experience_years=profile.experience_level,
            skills=", ".join(profile.skill_graph.get("skills", [])),
            technologies=", ".join(profile.skill_graph.get("technologies", [])),
            domains=", ".join(profile.skill_graph.get("domains", [])),
            education=", ".join(profile.skill_graph.get("education", [])),
            job_title=job.title,
            company=job.company,
            location=job.location,
            experience=job.experience,
            description=job.description[:10000] # truncate
        )
        
        try:
            result = llm.chat_json(JOB_SCORE_SYSTEM, user_prompt, self.task_type)
            score_val = result.get("score", 0)
            job.ai_score = float(score_val) if score_val is not None else 0.0
            job.metadata["match_level"] = result.get("match_level", "Unknown")
            job.metadata["matching_skills"] = result.get("matching_skills", [])
            job.metadata["missing_skills"] = result.get("missing_skills", [])
            job.metadata["score_reason"] = result.get("reason", "")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Scoring failed: {e}")
            job.ai_score = 0
            return {}

    def score_generic(self, job: Job, query: str, location: str) -> Dict[str, Any]:
        """Scores a job generically without a profile."""
        user_prompt = GENERIC_SEARCH_SCORE_USER.format(
            query=query,
            location=location,
            job_title=job.title,
            company=job.company,
            description=job.description[:5000]
        )
        try:
            result = llm.chat_json(GENERIC_SEARCH_SCORE_SYSTEM, user_prompt, self.task_type)
            score_val = result.get("score", 0)
            job.ai_score = float(score_val) if score_val is not None else 0.0
            job.metadata["match_level"] = result.get("match_level", "Unknown")
            job.metadata["score_reason"] = result.get("reason", "")
            return result
        except Exception:
            job.ai_score = 0
            return {}
