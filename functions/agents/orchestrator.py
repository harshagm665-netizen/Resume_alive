"""
functions/agents/orchestrator.py — Main controller that coordinates agents.
"""

import uuid
from typing import List, Dict, Any
from loguru import logger
from agents.job_discovery import JobDiscoveryAgent
from agents.dedup_guard_agent import DedupGuardAgent
from retrieval.retrieval_agent import RetrievalAgent
from agents.job_matcher import JobMatcherAgent
from agents.interview_prep import InterviewPrepAgent
from agents.cold_email import ColdEmailAgent
from db.models import SearchSession, UserJob, UserProfile
from db.firestore_client import fs_client

class Orchestrator:
    """The central brain orchestrating the multi-agent workflow."""
    
    def __init__(self):
        self.discovery = JobDiscoveryAgent()
        self.dedup_guard = DedupGuardAgent()
        self.retrieval = RetrievalAgent()
        self.job_matcher = JobMatcherAgent()
        self.interview_prep = InterviewPrepAgent()
        self.cold_email = ColdEmailAgent()
        
    def process_search_request(self, uid: str, query: str, location: str, portals: List[str] = None, progress_callback=None) -> List[Dict[str, Any]]:
        """Phase 2 Orchestrator: Discovers jobs and saves to DB."""
        session_id = str(uuid.uuid4())
        logger.info(f"Starting session {session_id} for user {uid}")
        
        def notify(msg):
            if progress_callback:
                progress_callback(msg)
                
        # 1. Discovery
        notify(f"Discovering jobs for '{query}'...")
        raw_jobs = self.discovery.discover_jobs(query, location, max_results=10, portals=portals)
        
        
        # 1.5 Deduplication and Spam Filter
        notify(f"Filtering {len(raw_jobs)} discovered jobs...")
        jobs, dropped = self.dedup_guard.filter(uid, raw_jobs)
        
        # 1.8 Index for Hybrid Retrieval
        notify("Indexing jobs for semantic search...")
        self.retrieval.index_jobs(jobs)
        
        # 1.9 Search
        notify("Re-ranking best matches...")
        top_matches = self.retrieval.search(query, limit=5)
        logger.info(f"Top {len(top_matches)} matches retrieved.")
        
        # 2. Save Session
        session = SearchSession(
            search_id=session_id,
            uid=uid,
            query=query,
            location=location,
            results_count=len(jobs),
            portals_used=portals or self.discovery.available_portals
        )
        fs_client.log_search(session)
        
        # 3. Process, Score and Save Jobs
        profile = fs_client.get_user_profile(uid)
        
        notify("Scoring and saving jobs...")
        saved_jobs = []
        for job in top_matches:
            # Score job
            if profile:
                self.job_matcher.score_job(job, profile)
            else:
                self.job_matcher.score_generic(job, query, location)
                
            job_id = fs_client.save_job(job)
            job.job_id = job_id
            saved_jobs.append(job.model_dump())
            
            # Generate personalized insights for top matches (score > 70)
            if profile and job.ai_score > 70:
                logger.info(f"Generating interview prep and cold email for high-match job: {job_id}")
                notify(f"Generating personalized insights for {job.company}...")
                interview_qs = self.interview_prep.generate_questions(profile, job)
                email_draft = self.cold_email.draft_email(profile, job)
                
                user_job = UserJob(
                    id=f"{uid}_{job_id}",
                    uid=uid,
                    job_id=job_id,
                    match_score=job.ai_score,
                    interview_questions=interview_qs,
                    cold_email_draft=email_draft
                )
                fs_client.save_user_job(user_job)
            
        return saved_jobs
