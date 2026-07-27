"""
core/job_scorer.py — AI-powered job-to-resume confidence scoring.
Uses concurrent LLM calls for faster batch processing.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from scrapers.base import Job
from llm.client import llm
from llm.prompts import (
    JOB_SCORE_SYSTEM, JOB_SCORE_USER,
    GENERIC_SEARCH_SCORE_SYSTEM, GENERIC_SEARCH_SCORE_USER,
)
from config import SCORE_THRESHOLD


def score_job_against_resume(job: Job, resume_profile: dict) -> Job:
    """
    Score a single job against the resume profile using LLM.
    Modifies job in-place with: score, match_level, matching_skills,
    missing_skills, score_reason.
    Returns the updated job.
    """
    try:
        user_prompt = JOB_SCORE_USER.format(
            current_role=resume_profile.get("current_role", ""),
            total_experience_years=resume_profile.get("total_experience_years", 0),
            skills=", ".join(resume_profile.get("skills", [])[:20]),
            technologies=", ".join(resume_profile.get("technologies", [])[:20]),
            domains=", ".join(resume_profile.get("domains", [])[:10]),
            education="; ".join(resume_profile.get("education", [])[:3]),
            job_title=job.title,
            company=job.company,
            location=job.location,
            experience=job.experience,
            description=job.description[:600] if job.description else "Not available",
        )
        result = llm.chat_json(JOB_SCORE_SYSTEM, user_prompt)
        job.score = int(result.get("score", 0))
        job.match_level = result.get("match_level", "Low")
        job.matching_skills = result.get("matching_skills", [])
        job.missing_skills = result.get("missing_skills", [])
        job.score_reason = result.get("reason", "")
    except Exception as e:
        logger.warning(f"Scoring error for '{job.title}': {e}")
        job.score = 0
        job.match_level = "Low"
        job.score_reason = "Could not score."
    return job


def score_job_generic(job: Job, query: str, location: str) -> Job:
    """Score a job by relevance to a plain-text query (no resume)."""
    try:
        user_prompt = GENERIC_SEARCH_SCORE_USER.format(
            query=query,
            location=location,
            job_title=job.title,
            company=job.company,
            description=job.description[:400] if job.description else "",
        )
        result = llm.chat_json(GENERIC_SEARCH_SCORE_SYSTEM, user_prompt)
        job.score = int(result.get("score", 0))
        job.match_level = result.get("match_level", "Low")
        job.score_reason = result.get("reason", "")
    except Exception as e:
        logger.warning(f"Generic scoring error for '{job.title}': {e}")
        job.score = 50  # Neutral default
    return job


def _score_single(job: Job, resume_profile: dict | None, query: str, location: str) -> Job:
    """Wrapper for concurrent scoring."""
    if resume_profile:
        return score_job_against_resume(job, resume_profile)
    return score_job_generic(job, query, location)


def batch_score(
    jobs: list[Job],
    resume_profile: dict | None = None,
    query: str = "",
    location: str = "",
    threshold: int = SCORE_THRESHOLD,
    max_workers: int = 5,
) -> list[Job]:
    """
    Score all jobs concurrently and return sorted, filtered results above threshold.
    Uses resume scoring if profile provided, generic otherwise.
    """
    scored: list[Job] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_score_single, job, resume_profile, query, location): job
            for job in jobs
        }
        for future in as_completed(future_map):
            try:
                result = future.result()
                scored.append(result)
            except Exception as e:
                job = future_map[future]
                logger.warning(f"Batch scoring failed for '{job.title}': {e}")
                job.score = 0
                job.match_level = "Low"
                scored.append(job)

    # Filter and sort
    filtered = [j for j in scored if j.score >= threshold]
    filtered.sort(key=lambda j: j.score, reverse=True)
    return filtered
