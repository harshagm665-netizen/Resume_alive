"""
functions/monitoring/self_healing.py — Error memory and auto-fix logic using Redis.
"""
import hashlib
from loguru import logger
from cache.redis_client import redis_client

class SelfHealingEngine:
    """Fingerprints errors and manages known fixes."""
    
    def fingerprint(self, error_msg: str) -> str:
        """Creates a stable hash for an error message."""
        # Strip variable numbers/IDs if possible to make fingerprint more generic
        clean_msg = "".join([c for c in error_msg if not c.isdigit()])
        return hashlib.md5(clean_msg.encode()).hexdigest()

    def get_known_fix(self, fingerprint: str) -> str:
        """Retrieves a known fix from Redis if it exists."""
        fix = redis_client.get(f"fix:{fingerprint}")
        if fix:
            logger.info(f"[SelfHealing] Found known fix for {fingerprint}")
        return fix

    def store_fix(self, fingerprint: str, fix_action: str) -> None:
        """Stores a successful fix in Redis."""
        logger.info(f"[SelfHealing] Storing fix for {fingerprint}")
        redis_client.set(f"fix:{fingerprint}", fix_action, ex=60*60*24*30) # 30 days

self_healing_engine = SelfHealingEngine()
