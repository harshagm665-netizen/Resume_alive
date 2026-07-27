"""
functions/cache/redis_client.py — Upstash Redis client using REST API.
"""
import json
import requests
from typing import Optional, Any
from loguru import logger
from config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

class UpstashRedisClient:
    """Client for Upstash Redis using the REST API to avoid long-lived connections in serverless environments."""
    
    def __init__(self):
        self.url = UPSTASH_REDIS_REST_URL.rstrip("/")
        self.token = UPSTASH_REDIS_REST_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
    def _execute(self, command: str, *args) -> Any:
        if not self.url or not self.token:
            logger.warning("Upstash Redis not configured. Skipping cache operation.")
            return None
            
        payload = [command] + list(args)
        try:
            resp = requests.post(self.url, headers=self.headers, json=payload, timeout=5)
            resp.raise_for_status()
            result = resp.json()
            if "error" in result:
                logger.error(f"Upstash error: {result['error']}")
                return None
            return result.get("result")
        except Exception as e:
            logger.error(f"Upstash request failed: {e}")
            return None

    def get(self, key: str) -> Optional[str]:
        return self._execute("GET", key)

    def set(self, key: str, value: str, ex: int = None) -> bool:
        if ex:
            return self._execute("SET", key, value, "EX", str(ex)) == "OK"
        return self._execute("SET", key, value) == "OK"

    def delete(self, *keys) -> int:
        res = self._execute("DEL", *keys)
        return int(res) if res is not None else 0

    def incr(self, key: str) -> int:
        res = self._execute("INCR", key)
        return int(res) if res is not None else 0

    def expire(self, key: str, seconds: int) -> bool:
        res = self._execute("EXPIRE", key, str(seconds))
        return bool(res)

    def sadd(self, key: str, *members) -> int:
        res = self._execute("SADD", key, *members)
        return int(res) if res is not None else 0

    def sismember(self, key: str, member: str) -> bool:
        res = self._execute("SISMEMBER", key, member)
        return bool(res)
        
redis_client = UpstashRedisClient()
