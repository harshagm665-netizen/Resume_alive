"""
functions/tools/skill_mapper.py — Tool to standardize skills and extract them using LLM.
"""
from typing import List
from llm.client import llm
from llm.temperature import TaskType

def extract_skills_from_text(text: str) -> List[str]:
    """Uses LLM to extract a standardized list of skills from text."""
    system = "You are an expert skill extractor. Extract all technical and soft skills from the text. Return a JSON object with a single key 'skills' containing a list of strings."
    try:
        result = llm.chat_json(system, text, task_type=TaskType.SKILL_EXTRACTION)
        return result.get("skills", [])
    except Exception:
        return []
