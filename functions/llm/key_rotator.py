"""
functions/llm/key_rotator.py — Thread-safe API key rotation.
"""

import threading
from typing import Optional
from loguru import logger

class KeyRotator:
    """Thread-safe Groq API key rotator with Gemini as final fallback."""

    def __init__(self, groq_keys: list[str], gemini_key: str):
        self._groq_keys = list(groq_keys)
        self._exhausted: set[str] = set()
        self._gemini_key = gemini_key
        self._idx = 0
        self._lock = threading.Lock()

    def current_groq(self) -> Optional[str]:
        """Return next available Groq key, or None if all exhausted."""
        with self._lock:
            available = [k for k in self._groq_keys if k not in self._exhausted]
            if not available:
                return None
            return available[self._idx % len(available)]

    def mark_failed(self, key: str) -> None:
        """Mark a Groq key as failed and rotate."""
        with self._lock:
            if key not in self._exhausted:
                logger.warning(f"Groq key ...{key[-6:]} marked as failed. Rotating.")
                if len(self._groq_keys) > 1:
                    self._exhausted.add(key)
                self._idx += 1

    def get_gemini_key(self) -> str:
        return self._gemini_key

    def all_groq_exhausted(self) -> bool:
        with self._lock:
            available = [k for k in self._groq_keys if k not in self._exhausted]
            return len(available) == 0

    def reset(self) -> None:
        """Reset exhausted keys (call after some cooldown)."""
        with self._lock:
            self._exhausted.clear()
            self._idx = 0
            logger.info("Key rotator reset — all Groq keys re-enabled.")

from config import ALL_GROQ_KEYS, GEMINI_API_KEY
KEY_ROTATOR = KeyRotator(ALL_GROQ_KEYS, GEMINI_API_KEY)
