"""
functions/cache/dedup_guard.py — Job deduplication logic and spam filtering using Redis.
"""
from typing import List, Tuple
from loguru import logger
from db.models import Job
from cache.redis_client import redis_client
from config import DEDUP_CONFIG

class DedupGuard:
    """Handles global deduplication, user seen-sets, and spam filtering."""
    
    def __init__(self):
        self.spam_threshold = DEDUP_CONFIG["spam_threshold"]
        self.user_ttl = DEDUP_CONFIG["user_seen_ttl"]

    def _company_role_key(self, job: Job) -> str:
        # e.g. "spam:google:software_engineer"
        c = "".join(x for x in job.company.lower() if x.isalnum())
        t = "".join(x for x in job.title.lower() if x.isalnum())
        return f"spam:{c}:{t}"

    def _user_seen_key(self, uid: str) -> str:
        return f"user:seen:{uid}"

    def filter_jobs(self, uid: str, jobs: List[Job]) -> Tuple[List[Job], int]:
        """
        Filters a list of jobs through the dedup guard.
        Returns: (passed_jobs, number_of_jobs_filtered_out)
        """
        passed: List[Job] = []
        filtered_count = 0
        
        seen_key = self._user_seen_key(uid)
        
        for job in jobs:
            dedup = job.dedup_key()
            cr_key = self._company_role_key(job)
            
            # 1. Global Spam Check
            count_str = redis_client.get(cr_key)
            count = int(count_str) if count_str else 0
            
            if count >= self.spam_threshold:
                logger.debug(f"[Dedup] Dropped as spam (>={self.spam_threshold}): {job.title} at {job.company}")
                filtered_count += 1
                continue
                
            # 2. User Seen Check
            has_seen = redis_client.sismember(seen_key, dedup)
            if has_seen:
                logger.debug(f"[Dedup] User {uid} already saw {dedup}")
                filtered_count += 1
                continue
                
            # Job passed all checks!
            passed.append(job)
            
            # Mark as seen by user (fire and forget)
            redis_client.sadd(seen_key, dedup)
            
            # Increment spam counter (fire and forget)
            redis_client.incr(cr_key)
            if count == 0:
                # Expire spam counters after 24 hours to reset
                redis_client.expire(cr_key, 60 * 60 * 24)
                
        # Update TTL on user's seen set
        redis_client.expire(seen_key, self.user_ttl)
        
        logger.info(f"[DedupGuard] {len(jobs)} jobs in, {len(passed)} out ({filtered_count} dropped).")
        return passed, filtered_count

dedup_guard = DedupGuard()
