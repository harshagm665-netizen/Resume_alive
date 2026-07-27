"""
functions/monitoring/metrics.py — Metrics collection decorator.
"""
import time
import functools
from loguru import logger
from db.firestore_client import get_db

def track_metrics(module_name: str, func_name: str):
    """Decorator to track execution time, success rate, and errors."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_msg = ""
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                logger.error(f"[Metrics] {module_name}.{func_name} failed: {e}")
                raise
            finally:
                duration = time.time() - start_time
                try:
                    db = get_db()
                    doc_ref = db.collection('METRICS').document()
                    doc_ref.set({
                        "module": module_name,
                        "function": func_name,
                        "duration_sec": duration,
                        "success": success,
                        "error": error_msg,
                        "timestamp": firestore.SERVER_TIMESTAMP if db else None
                    })
                except Exception as db_e:
                    logger.warning(f"Failed to write metrics: {db_e}")
                    
        return wrapper
    return decorator
