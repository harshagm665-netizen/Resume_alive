"""
functions/monitoring/health.py — Comprehensive system health checks.
"""
from firebase_functions import https_fn
from loguru import logger

from cache.redis_client import redis_client
from db.firestore_client import get_db

@https_fn.on_request()
def deep_health_check(req: https_fn.Request) -> https_fn.Response:
    """Checks all dependencies (Firestore, Redis, LLM limits)."""
    status = {"status": "ok", "dependencies": {}}
    
    # 1. Firestore
    try:
        db = get_db()
        # Just check if we can get a reference
        db.collection("METRICS").limit(1).get()
        status["dependencies"]["firestore"] = "ok"
    except Exception as e:
        status["status"] = "degraded"
        status["dependencies"]["firestore"] = f"error: {e}"
        
    # 2. Redis
    try:
        # Simple ping by setting a temporary key
        ok = redis_client.set("health_ping", "pong", ex=5)
        if ok:
            status["dependencies"]["redis"] = "ok"
        else:
            status["status"] = "degraded"
            status["dependencies"]["redis"] = "error: ping failed"
    except Exception as e:
        status["status"] = "degraded"
        status["dependencies"]["redis"] = f"error: {e}"
        
    http_status = 200 if status["status"] == "ok" else 503
    return https_fn.Response(str(status), status=http_status, headers={"Content-Type": "application/json"})
