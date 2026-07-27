"""
llm/prompts.py — All prompt templates for the job scraper.
"""

RESUME_PARSE_SYSTEM = """You are an expert HR assistant and resume parser.
Extract structured information from the resume text provided.
Always return valid JSON only — no extra text."""

RESUME_PARSE_USER = """Parse this resume and extract the following as JSON:
{{
  "name": "candidate name",
  "email": "email if present",
  "phone": "phone if present",
  "total_experience_years": <number or 0>,
  "current_role": "current or most recent job title",
  "skills": ["skill1", "skill2", ...],
  "technologies": ["tech1", "tech2", ...],
  "domains": ["domain1", ...],
  "education": ["degree - institution", ...],
  "languages": ["Python", "Java", ...],
  "summary": "2-3 sentence professional summary"
}}

Resume text:
---
{resume_text}
---"""


JOB_SCORE_SYSTEM = """You are an expert technical recruiter. 
Given a candidate's resume profile and a job listing, evaluate how well the candidate matches the job.
Return a JSON object only."""

JOB_SCORE_USER = """Rate how well this candidate matches the job on a scale of 0-100.

CANDIDATE PROFILE:
- Current Role: {current_role}
- Total Experience: {total_experience_years} years
- Skills: {skills}
- Technologies: {technologies}
- Domains: {domains}
- Education: {education}

JOB POSTING:
- Title: {job_title}
- Company: {company}
- Location: {location}
- Experience Required: {experience}
- Description: {description}

Return JSON:
{{
  "score": <integer 0-100>,
  "match_level": "<Excellent|Good|Fair|Low>",
  "matching_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],
  "reason": "One concise sentence explaining the score"
}}"""


GENERIC_SEARCH_SCORE_SYSTEM = """You are a job relevance scorer. 
Evaluate how relevant a job posting is to the given search query."""

GENERIC_SEARCH_SCORE_USER = """Given the search query '{query}' for location '{location}', 
rate this job listing's relevance (0-100):

Job Title: {job_title}
Company: {company}
Description: {description}

Return JSON:
{{
  "score": <integer 0-100>,
  "match_level": "<Excellent|Good|Fair|Low>",
  "reason": "One concise sentence"
}}"""
