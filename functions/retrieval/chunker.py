"""
functions/retrieval/chunker.py — Parent-Child chunking for jobs.
"""
from typing import List, Dict, Any
from db.models import Job

class JobChunker:
    """Chunks a job description into logical child chunks for hybrid retrieval."""
    
    def chunk_job(self, job: Job) -> List[Dict[str, Any]]:
        """
        Splits a job into logical chunks (skills, requirements, etc.).
        Returns a list of dicts representing child chunks.
        """
        # Very simple chunking for now, normally we'd use an LLM or regex to split by headers
        # For this prototype, we'll split the description by newlines and group into chunks of ~200 chars.
        
        chunks = []
        desc = job.description or ""
        
        if not desc.strip():
            desc = f"{job.title} at {job.company} in {job.location}. Salary: {job.salary}"
            
        paragraphs = [p.strip() for p in desc.split("\n") if p.strip()]
        
        current_chunk = ""
        for p in paragraphs:
            if len(current_chunk) + len(p) < 400:
                current_chunk += p + " "
            else:
                if current_chunk:
                    chunks.append(self._create_chunk(job, current_chunk.strip()))
                current_chunk = p + " "
                
        if current_chunk:
            chunks.append(self._create_chunk(job, current_chunk.strip()))
            
        return chunks
        
    def _create_chunk(self, job: Job, text: str) -> Dict[str, Any]:
        import uuid
        return {
            "chunk_id": str(uuid.uuid4()),
            "parent_id": job.job_id,
            "text": text,
            "portal": job.portal,
            "company": job.company,
            "title": job.title
        }

chunker = JobChunker()
