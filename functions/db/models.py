"""
functions/db/models.py — Pydantic models for Firestore documents.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class UserProfile(BaseModel):
    uid: str
    name: str = ""
    username: str = ""
    experience_level: str = ""
    current_role: str = ""
    preferred_locations: List[str] = Field(default_factory=list)
    salary_expectations: Dict[str, Any] = Field(default_factory=dict)
    skill_graph: Dict[str, Any] = Field(default_factory=dict)
    parsed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)

class Job(BaseModel):
    job_id: str = ""
    title: str
    company: str
    location: str
    portal: str
    url: str
    description: str = ""
    posted_date: str = "Unknown"
    salary: str = "Not disclosed"
    experience: str = "Not specified"
    ai_score: float = 0.0
    hybrid_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=now_utc)
    
    def dedup_key(self) -> str:
        return f"{self.portal}::{self.job_id or self.url}"

class SearchSession(BaseModel):
    search_id: str
    uid: str
    query: str
    location: str
    results_count: int = 0
    portals_used: List[str] = Field(default_factory=list)
    personalized: bool = False
    searched_at: datetime = Field(default_factory=now_utc)

class UserJob(BaseModel):
    id: str
    uid: str
    job_id: str
    match_score: float
    status: str = "new" # new, applied, rejected
    agent_notes: str = ""
    interview_questions: List[str] = Field(default_factory=list)
    cold_email_draft: str = ""
    matched_at: datetime = Field(default_factory=now_utc)
