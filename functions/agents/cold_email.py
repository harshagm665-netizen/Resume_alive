"""
functions/agents/cold_email.py — Drafts personalized LinkedIn / cold email messages.
"""
from loguru import logger
from agents.base_agent import BaseAgent
from db.models import UserProfile, Job
from llm.client import llm
from llm.temperature import TaskType
from monitoring.metrics import track_metrics

class ColdEmailAgent(BaseAgent):
    """
    Drafts a personalized outreach message directed at the hiring manager or recruiter.
    """

    def __init__(self):
        super().__init__(
            name="Cold Email Agent",
            role="Career strategist and executive assistant",
            goal="Write a highly personalized LinkedIn outreach message.",
            task_type=TaskType.COVER_LETTER
        )

    @track_metrics("cold_email_agent", "draft_email")
    def draft_email(self, user_profile: UserProfile, job: Job) -> str:
        logger.info(f"Drafting cold email for user {user_profile.uid} on job {job.job_id}")
        
        system_prompt = (
            "You are an expert career strategist and executive assistant. "
            "Your task is to write a short, punchy, and highly personalized LinkedIn outreach "
            "message (or cold email) for a candidate applying to a specific role. "
            "The tone should be confident, professional, yet conversational. Avoid corporate jargon. "
            "Keep it under 150 words. Focus on the candidate's strongest matching skills and the value "
            "they bring to the company. Do not use placeholders like '[Your Name]', format it ready to send "
            "using the candidate's actual name."
        )
        
        user_prompt = (
            f"Candidate Name: {user_profile.name or 'A candidate'}\n"
            f"Role: {user_profile.current_role}\n"
            f"Experience: {user_profile.experience_level}\n"
            f"Skills: {user_profile.skill_graph}\n\n"
            f"Target Job:\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Description: {job.description}\n"
        )
        
        try:
            # We use TaskType.COVER_LETTER here because we want an engaging email draft
            response = llm.chat(system_prompt, user_prompt, TaskType.COVER_LETTER)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate cold email draft: {e}")
            return "Error: Could not generate cold email draft at this time."
