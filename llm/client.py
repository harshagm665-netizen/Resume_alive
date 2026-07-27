"""
llm/client.py — Unified LLM client with automatic key rotation and caching.
Priority: Groq (primary) -> Groq (backups) -> Gemini (final fallback).
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
# google-genai is imported lazily inside _gemini_chat to avoid
# namespace conflicts with other google.* packages.

from config import KEY_ROTATOR


class LLMError(Exception):
    pass


class LLMCache:
    """Thread-safe in-memory LLM response cache keyed by prompt hash."""

    def __init__(self, max_size: int = 512):
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def _key(self, system: str, user: str) -> str:
        raw = f"{system}|||{user}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, system: str, user: str) -> Optional[str]:
        k = self._key(system, user)
        with self._lock:
            return self._cache.get(k)

    def set(self, system: str, user: str, value: str) -> None:
        k = self._key(system, user)
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest entry
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
    Usage:
        client = LLMClient()
        response = client.chat(system_prompt, user_prompt)
    """

    def __init__(self):
        self._groq_model = "llama-3.3-70b-versatile"
        self._gemini_model = "gemini-1.5-flash"

    # ── Public API ─────────────────────────────────────────────────────────────

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        """Send a chat message. Returns the assistant's text response."""
        # Check cache first (only for non-JSON mode or always for repeated prompts)
        cached = _cache.get(system, user)
        if cached:
            logger.debug("LLM cache hit.")
            return cached

        key = KEY_ROTATOR.current_groq()
        if key:
            try:
                result = self._groq_chat(key, system, user, json_mode)
                _cache.set(system, user, result)
                return result
            except groq_sdk.RateLimitError:
                logger.warning("Groq rate limit hit, rotating key.")
                KEY_ROTATOR.mark_failed(key)
                return self._groq_with_rotation(system, user, json_mode)
            except Exception as e:
                logger.warning(f"Groq chat failed: {e}")
                KEY_ROTATOR.mark_failed(key)
                return self._groq_with_rotation(system, user, json_mode)
        else:
            logger.warning("All Groq keys exhausted -> falling back to Gemini")
            result = self._gemini_chat(system, user, json_mode)
            _cache.set(system, user, result)
            return result

    def chat_json(self, system: str, user: str) -> dict:
        """Like chat() but parse and return JSON. Retries on parse error."""
        raw = self.chat(system, user, json_mode=True)
        return self._parse_json(raw)

    # ── JSON Parsing ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Parse JSON from LLM response, stripping markdown fences."""
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

    # ── Groq ───────────────────────────────────────────────────────────────────

    def _groq_chat(self, key: str, system: str, user: str, json_mode: bool) -> str:
        client = groq_sdk.Groq(api_key=key)
        kwargs: dict[str, Any] = {
            "model": self._groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def _groq_with_rotation(self, system: str, user: str, json_mode: bool) -> str:
        """Try all remaining Groq keys, then fall back to Gemini."""
        for _ in range(20):  # Safety limit to prevent infinite loop
            key = KEY_ROTATOR.current_groq()
            if not key:
                logger.warning("All Groq keys exhausted -> Gemini fallback")
                result = self._gemini_chat(system, user, json_mode)
                _cache.set(system, user, result)
                return result
            try:
                result = self._groq_chat(key, system, user, json_mode)
                _cache.set(system, user, result)
                return result
            except groq_sdk.RateLimitError:
                logger.warning(f"Groq key ...{key[-6:]} rate limited, rotating.")
                KEY_ROTATOR.mark_failed(key)
            except Exception as e:
                logger.warning(f"Groq key ...{key[-6:]} failed: {e}")
                KEY_ROTATOR.mark_failed(key)

        # All keys exhausted
        result = self._gemini_chat(system, user, json_mode)
        _cache.set(system, user, result)
        return result

    # ── Gemini ─────────────────────────────────────────────────────────────────

    def _gemini_chat(self, system: str, user: str, json_mode: bool) -> str:
        gemini_key = KEY_ROTATOR.get_gemini_key()
        if not gemini_key:
            raise LLMError("No LLM keys available (Groq exhausted, Gemini key missing).")
        try:
            from google import genai as _genai  # lazy import avoids namespace conflicts
        except ImportError:
            raise LLMError("google-genai package not installed. Run: pip install google-genai")

        client = _genai.Client(api_key=gemini_key)

        # Use system instruction + user content properly
        config = {}
        if json_mode:
            config["response_mime_type"] = "application/json"

        try:
            resp = client.models.generate_content(
                model=self._gemini_model,
                contents=user,
                config={"system_instruction": system, **config} if config else {"system_instruction": system},
            )
            return resp.text or ""
        except Exception as e:
            raise LLMError(f"Gemini API error: {e}")


# Singleton
llm = LLMClient()
