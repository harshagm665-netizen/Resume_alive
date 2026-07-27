"""
functions/llm/client.py — Unified LLM client with automatic key rotation, caching, and temperature configs.
"""

import json
import hashlib
import threading
from typing import Optional, Any
from loguru import logger
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

import groq as groq_sdk

from llm.key_rotator import KeyRotator, KEY_ROTATOR
from llm.temperature import get_temperature, TaskType

class LLMError(Exception):
    pass

class LLMCache:
    """Thread-safe in-memory LLM response cache keyed by prompt hash."""

    def __init__(self, max_size: int = 512):
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def _key(self, system: str, user: str, temp: float) -> str:
        raw = f"{system}|||{user}|||{temp}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, system: str, user: str, temp: float) -> Optional[str]:
        k = self._key(system, user, temp)
        with self._lock:
            return self._cache.get(k)

    def set(self, system: str, user: str, temp: float, value: str) -> None:
        k = self._key(system, user, temp)
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[k] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

_cache = LLMCache()

class LLMClient:
    """
    Wraps Groq + Gemini with transparent fallback, key rotation, and caching.
    """

    def __init__(self):
        self._groq_model = "llama-3.3-70b-versatile"
        self._gemini_model = "gemini-1.5-flash"

    def chat(self, system: str, user: str, task_type: TaskType, json_mode: bool = False) -> str:
        """Send a chat message with temperature based on TaskType."""
        temp, top_p = get_temperature(task_type)
        
        cached = _cache.get(system, user, temp)
        if cached:
            logger.debug("LLM cache hit.")
            return cached

        key = KEY_ROTATOR.current_groq()
        if key:
            try:
                result = self._groq_chat(key, system, user, temp, top_p, json_mode)
                _cache.set(system, user, temp, result)
                return result
            except groq_sdk.RateLimitError:
                logger.warning("Groq rate limit hit, rotating key.")
                KEY_ROTATOR.mark_failed(key)
                return self._groq_with_rotation(system, user, temp, top_p, json_mode)
            except Exception as e:
                logger.warning(f"Groq chat failed: {e}")
                KEY_ROTATOR.mark_failed(key)
                return self._groq_with_rotation(system, user, temp, top_p, json_mode)
        else:
            logger.warning("All Groq keys exhausted -> falling back to Gemini")
            result = self._gemini_chat(system, user, temp, top_p, json_mode)
            _cache.set(system, user, temp, result)
            return result

    def chat_json(self, system: str, user: str, task_type: TaskType) -> dict:
        """Like chat() but parse and return JSON."""
        raw = self.chat(system, user, task_type, json_mode=True)
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nRaw:\n{raw[:500]}")
            raise LLMError(f"LLM returned non-JSON: {raw[:200]}")

    def _groq_chat(self, key: str, system: str, user: str, temp: float, top_p: float, json_mode: bool) -> str:
        client = groq_sdk.Groq(api_key=key)
        kwargs: dict[str, Any] = {
            "model": self._groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temp,
            "top_p": top_p,
            "max_tokens": 4096,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def _groq_with_rotation(self, system: str, user: str, temp: float, top_p: float, json_mode: bool) -> str:
        for _ in range(20):
            key = KEY_ROTATOR.current_groq()
            if not key:
                logger.warning("All Groq keys exhausted -> Gemini fallback")
                result = self._gemini_chat(system, user, temp, top_p, json_mode)
                _cache.set(system, user, temp, result)
                return result
            try:
                result = self._groq_chat(key, system, user, temp, top_p, json_mode)
                _cache.set(system, user, temp, result)
                return result
            except groq_sdk.RateLimitError:
                logger.warning(f"Groq key ...{key[-6:]} rate limited, rotating.")
                KEY_ROTATOR.mark_failed(key)
            except Exception as e:
                logger.warning(f"Groq key ...{key[-6:]} failed: {e}")
                KEY_ROTATOR.mark_failed(key)

        result = self._gemini_chat(system, user, temp, top_p, json_mode)
        _cache.set(system, user, temp, result)
        return result

    def _gemini_chat(self, system: str, user: str, temp: float, top_p: float, json_mode: bool) -> str:
        gemini_key = KEY_ROTATOR.get_gemini_key()
        if not gemini_key:
            raise LLMError("No LLM keys available (Groq exhausted, Gemini key missing).")
        try:
            from google import genai as _genai
            from google.genai import types
        except ImportError:
            raise LLMError("google-genai package not installed.")

        client = _genai.Client(api_key=gemini_key)
        
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temp,
            top_p=top_p
        )
        if json_mode:
            config.response_mime_type = "application/json"

        try:
            resp = client.models.generate_content(
                model=self._gemini_model,
                contents=user,
                config=config,
            )
            return resp.text or ""
        except Exception as e:
            raise LLMError(f"Gemini API error: {e}")

llm = LLMClient()
