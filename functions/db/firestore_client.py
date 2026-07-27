"""
functions/db/firestore_client.py — Firestore CRUD operations.
"""

from typing import Optional, List
from loguru import logger
from db.models import UserProfile, Job, SearchSession, UserJob

_db = None

def get_db():
    global _db
    if _db is None:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore as firestore_admin
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            _db = firestore_admin.client()
        except Exception as e:
            logger.warning(f"Failed to initialize Firestore (mocking for local test): {e}")
            _db = None
    return _db

class FirestoreClient:
    def __init__(self):
        self.db = get_db()
        
    def save_user_profile(self, profile: UserProfile) -> None:
        doc_ref = self.db.collection('USERS').document(profile.uid)
        doc_ref.set(profile.model_dump(mode="json"), merge=True)
        
    def get_user_profile(self, uid: str) -> Optional[UserProfile]:
        doc = self.db.collection('USERS').document(uid).get()
        if doc.exists:
            return UserProfile(**doc.to_dict())
        return None
        
    def save_job(self, job: Job) -> str:
        """Saves a job and returns its ID."""
        # Clean ID to be safe for firestore paths
        import hashlib
        job_id = hashlib.md5(job.dedup_key().encode()).hexdigest()
        job.job_id = job_id
        doc_ref = self.db.collection('JOBS').document(job_id)
        doc_ref.set(job.model_dump(mode="json"), merge=True)
        return job_id

    def log_search(self, session: SearchSession) -> None:
        doc_ref = self.db.collection('SEARCHES').document(session.search_id)
        doc_ref.set(session.model_dump(mode="json"))

    def save_user_job(self, user_job: UserJob) -> None:
        doc_ref = self.db.collection('USER_JOBS').document(user_job.id)
        doc_ref.set(user_job.model_dump(mode="json"), merge=True)

fs_client = FirestoreClient()
