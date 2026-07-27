"""
functions/agents/interview_prep.py — Generates custom mock interview questions.
"""
from typing import List
from loguru import logger
from agents.base_agent import BaseAgent
from db.models import UserProfile, Job
from llm.client import llm
from llm.temperature import TaskType
from monitoring.metrics import track_metrics

class InterviewPrepAgent(BaseAgent):
    """
    Analyzes the user's resume and the job description to identify skill gaps
    and generates 5 targeted mock interview questions.
    """

    @track_metrics("interview_prep_agent")
    def generate_questions(self, user_profile: UserProfile, job: Job) -> List[str]:
        logger.info(f"Generating interview questions for user {user_profile.uid} on job {job.job_id}")
        
        system_prompt = (
            "You are an expert technical interviewer and career coach. "
            "Your task is to analyze a candidate's profile against a target job description, "
            "identify the most likely areas they will be questioned on (especially any skill gaps or "
            "weaknesses), and generate exactly 5 tough, highly targeted mock interview questions.\n"
            "Return the output as a JSON object with a single key 'questions' containing a list of 5 strings."
        )
        
        user_prompt = (
            f"Candidate Profile:\n"
            f"Role: {user_profile.current_role}\n"
            f"Experience: {user_profile.experience_level}\n"
            f"Skills: {user_profile.skill_graph}\n\n"
            f"Target Job:\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Description: {job.description}\n"
        )
        
        try:
            response = llm.chat_json(system_prompt, user_prompt, TaskType.ANALYSIS)
            questions = response.get("questions", [])
            if not isinstance(questions, list) or len(questions) == 0:
                return ["Could not generate specific questions at this time."]
            return [str(q) for q in questions[:5]]
        except Exception as e:
            logger.error(f"Failed to generate interview questions: {e}")
            return [f"Error generating questions: {e}"]
