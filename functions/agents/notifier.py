"""
functions/agents/notifier.py — Agent for formatting and delivering notifications.
"""
from loguru import logger
from agents.base_agent import BaseAgent
from llm.client import llm
from llm.temperature import TaskType
from db.models import Job

class NotifierAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Notifier",
            role="Communications Manager",
            goal="Format job alerts beautifully for Telegram delivery.",
            task_type=TaskType.JSON_OUTPUT
        )
        
    def format_job_alert(self, job: Job) -> str:
        """Formats a job for Telegram MarkdownV2."""
        # This is a deterministic string manipulation task, usually best done without LLM 
        # to save tokens and latency, but we wrap it in the agent for the architecture.
        # We'll use a direct formatting method instead of calling LLM for basic formatting.
        
        title = job.title.replace('*', '').replace('_', '\\_')
        company = job.company.replace('*', '').replace('_', '\\_')
        location = job.location.replace('_', '\\_')
        url = job.url
        score = job.ai_score
        match_level = job.metadata.get("match_level", "N/A")
        
        text = f"*{title}* at *{company}*\n"
        text += f"📍 {location}\n"
        text += f"💰 {job.salary} | ⏳ {job.experience}\n"
        if score > 0:
            text += f"🤖 Match: {score}% ({match_level})\n"
        text += f"\n[Apply Here]({url})"
        return text
