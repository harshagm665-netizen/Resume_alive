"""
core/resume_parser.py — Extract structured skills/profile from a resume PDF or text.
"""

import io
import re
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from llm.client import llm
from llm.prompts import RESUME_PARSE_SYSTEM, RESUME_PARSE_USER


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from a PDF file given as bytes."""
    if not PYPDF_AVAILABLE:
        raise ImportError("pypdf not installed. Run: pip install pypdf")
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract raw text from a DOCX file given as bytes."""
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed.")
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs)


def extract_resume_text(file_bytes: bytes, filename: str = "") -> str:
    """Auto-detect format and extract text."""
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif fname.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    else:
        # Try PDF first, then docx, then treat as plain text
        try:
            return extract_text_from_pdf(file_bytes)
        except Exception:
            pass
        try:
            return extract_text_from_docx(file_bytes)
        except Exception:
            pass
        return file_bytes.decode("utf-8", errors="ignore")


def parse_resume(file_bytes: bytes, filename: str = "") -> dict:
    """
    Parse a resume file and return a structured profile dict.
    Returns keys: name, email, phone, total_experience_years,
                  current_role, skills, technologies, domains,
                  education, languages, summary
    """
    logger.info(f"Parsing resume: {filename or 'unknown'}")
    text = extract_resume_text(file_bytes, filename)

    if not text.strip():
        logger.warning("Resume text extraction returned empty string.")
        return _empty_profile()

    # Truncate if very long (LLM context limit)
    text = text[:8000]

    user_prompt = RESUME_PARSE_USER.format(resume_text=text)
    try:
        profile = llm.chat_json(RESUME_PARSE_SYSTEM, user_prompt)
        # Normalize types
        profile.setdefault("name", "Candidate")
        profile.setdefault("skills", [])
        profile.setdefault("technologies", [])
        profile.setdefault("domains", [])
        profile.setdefault("education", [])
        profile.setdefault("languages", [])
        profile.setdefault("total_experience_years", 0)
        profile.setdefault("current_role", "Professional")
        profile.setdefault("summary", "")
        return profile
    except Exception as e:
        logger.error(f"Resume parse LLM error: {e}")
        return _empty_profile()


def _empty_profile() -> dict:
    return {
        "name": "Candidate",
        "email": "",
        "phone": "",
        "total_experience_years": 0,
        "current_role": "",
        "skills": [],
        "technologies": [],
        "domains": [],
        "education": [],
        "languages": [],
        "summary": "",
    }
