"""
functions/agents/app_strategy.py — Agent for generating application strategies and cover letters.
"""
from loguru import logger
from agents.base_agent import BaseAgent
from llm.client import llm
from llm.temperature import TaskType
from db.models import Job, UserProfile

class AppStrategyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="App Strategy",
            role="Career Coach",
            goal="Provide personalized application advice and generate tailored cover letters.",
            task_type=TaskType.COVER_LETTER
        )
        
    def generate_cover_letter(self, job: Job, profile: UserProfile) -> str:
        """Generates a personalized cover letter."""
        logger.info(f"[{self.name}] Generating cover letter for {job.company}...")
        
        system = "You are an expert career coach helping a candidate write a highly personalized, compelling cover letter."
        user = f"""
        Candidate Name: {profile.name}
        Current Role: {profile.current_role}
        Skills: {', '.join(profile.skill_graph.get('skills', []))}
        
        Target Job: {job.title} at {job.company}
        Job Description: {job.description[:2000]}
        
        Write a professional, modern cover letter (3-4 paragraphs) that highlights the candidate's skills that match the job.
        Do not use placeholders like [Your Address]. Just provide the body of the letter.
        """
        
        try:
            return llm.chat(system, user, self.task_type)
        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            return "Failed to generate cover letter."
