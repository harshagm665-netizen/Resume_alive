"""
functions/agents/resume_analyzer.py — Agent for analyzing and parsing resumes.
"""
from typing import Dict, Any, Optional
from loguru import logger
from agents.base_agent import BaseAgent
from llm.client import llm
from llm.prompts import RESUME_PARSE_SYSTEM, RESUME_PARSE_USER
from llm.temperature import TaskType
from tools.pdf_parser import parse_pdf_bytes
from tools.docx_parser import parse_docx_bytes

class ResumeAnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Resume Analyzer",
            role="Expert HR Assistant",
            goal="Extract structured data from raw resumes (PDF/DOCX) accurately.",
            task_type=TaskType.RESUME_PARSING
        )
        self.register_tool("parse_pdf", "Extract text from PDF", parse_pdf_bytes)
        self.register_tool("parse_docx", "Extract text from DOCX", parse_docx_bytes)

    def analyze(self, file_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
        """Parses a resume file and extracts structured data."""
        logger.info(f"[{self.name}] Analyzing {filename}...")
        
        # 1. Extract raw text
        ext = filename.split(".")[-1].lower()
        if ext == "pdf":
            text = parse_pdf_bytes(file_bytes)
        elif ext in ["doc", "docx"]:
            text = parse_docx_bytes(file_bytes)
        else:
            try:
                text = file_bytes.decode("utf-8")
            except:
                logger.error(f"Unsupported resume format: {ext}")
                return None
                
        if not text:
            logger.error("Failed to extract text from resume.")
            return None
            
        # 2. Extract structured data using LLM
        logger.info(f"[{self.name}] Extracting structured profile...")
        try:
            profile = llm.chat_json(RESUME_PARSE_SYSTEM, RESUME_PARSE_USER.format(resume_text=text[:15000]), self.task_type)
            return profile
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None
