"""
config.py — Loads all environment variables and manages LLM API key rotation.
Groq keys: primary -> backup pool -> Gemini fallback.
"""

import os
import threading
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TG_TOKEN: str = os.getenv("tg_token", "")
TG_CHAT_ID: str = os.getenv("tg_chat_id", "")
TG_API_ID: str = os.getenv("tg_api_id", "")
TG_API_HASH: str = os.getenv("tg_api_hash", "")
TG_ERR_TOPIC_ID: Optional[str] = os.getenv("tg_err_topic_id") or None
TG_REPORT_TOPIC_ID: Optional[str] = os.getenv("tg_report_topic_id") or None

# ── LLM Keys ──────────────────────────────────────────────────────────────────
_primary_groq = os.getenv("llm_api_key", "")
_backup_groq_raw = os.getenv("GROQ_BACKUP_KEYS", "")
_backup_groq_keys = [k.strip() for k in _backup_groq_raw.split(",") if k.strip()]

GEMINI_API_KEY: str = os.getenv("GEMINI", "")

# Build ordered key list: primary first, then backups, then Gemini sentinel
ALL_GROQ_KEYS: list[str] = []
if _primary_groq:
    ALL_GROQ_KEYS.append(_primary_groq)
ALL_GROQ_KEYS.extend(_backup_groq_keys)

logger.info(f"Loaded {len(ALL_GROQ_KEYS)} Groq key(s) + Gemini fallback.")

# ── LinkedIn (public scraping only — no login by default) ────────────────────
LINKEDIN_EMAIL: str = os.getenv("linkedin_email", "")
LINKEDIN_PASSWORD: str = os.getenv("linkedin_password", "")

# ── SQLite ────────────────────────────────────────────────────────────────────
SQLITE_DB_PATH: str = os.path.join(os.path.dirname(__file__), "jobs.db")

# ── Misc ──────────────────────────────────────────────────────────────────────
ATS_QC_ENABLED: bool = os.getenv("ats_qc_enabled", "True").lower() == "true"
TG_LISTEN_ENABLED: bool = os.getenv("tg_listen_enabled", "True").lower() == "true"

# ── Shared constants (single source of truth) ─────────────────────────────────
MAX_RESULTS_PER_PORTAL = 10
MAX_DISPLAY = 25
SCORE_THRESHOLD = 40

# ── Location normalization ─────────────────────────────────────────────────────
# Maps common misspellings/aliases → canonical Indian city name
_CITY_ALIASES: dict[str, str] = {
    # Bangalore
    "banglore": "Bangalore", "bangalor": "Bangalore", "bengaluru": "Bangalore",
    "bengalore": "Bangalore", "bangaluru": "Bangalore", "bangalore": "Bangalore",
    "bngalore": "Bangalore", "blr": "Bangalore",
    # Mumbai
    "bombay": "Mumbai", "mumbay": "Mumbai", "mumabi": "Mumbai",
    # Delhi
    "new delhi": "Delhi", "ndelhi": "Delhi", "delhi ncr": "Delhi",
    # Hyderabad
    "hyderabad": "Hyderabad", "hyd": "Hyderabad", "secunderabad": "Hyderabad",
    # Chennai
    "chennai": "Chennai", "madras": "Chennai",
    # Pune
    "pune": "Pune",
    # Kolkata
    "kolkata": "Kolkata", "calcutta": "Kolkata", "kolcutta": "Kolkata",
    # Gurgaon
    "gurgaon": "Gurugram", "gurugram": "Gurugram", "ggn": "Gurugram",
    # Noida
    "noida": "Noida",
    # Ahmedabad
    "ahmedabad": "Ahmedabad", "amdabad": "Ahmedabad", "ahemdabad": "Ahmedabad",
    # Jaipur
    "jaipur": "Jaipur",
    # Chandigarh
    "chandigarh": "Chandigarh",
    # Kochi
    "kochi": "Kochi", "cochin": "Kochi",
    # Thiruvananthapuram
    "trivandrum": "Thiruvananthapuram", "trivendrum": "Thiruvananthapuram",
    # Coimbatore
    "coimbatore": "Coimbatore", "covai": "Coimbatore",
    # Mysore
    "mysore": "Mysuru", "mysuru": "Mysuru",
    # Indore
    "indore": "Indore",
    # Bhopal
    "bhopal": "Bhopal",
    # Patna
    "patna": "Patna",
    # Lucknow
    "lucknow": "Lucknow",
    # Visakhapatnam
    "vizag": "Visakhapatnam", "vishakhapatnam": "Visakhapatnam",
    # Nagpur
    "nagpur": "Nagpur",
    # Surat
    "surat": "Surat",
}

# Cities in India — if user provides just a city name, append ", India"
_INDIA_CITIES = {
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune",
    "Kolkata", "Gurugram", "Noida", "Ahmedabad", "Jaipur", "Chandigarh",
    "Kochi", "Thiruvananthapuram", "Coimbatore", "Mysuru", "Indore",
    "Bhopal", "Patna", "Lucknow", "Visakhapatnam", "Nagpur", "Surat",
}


def normalize_location(raw: str) -> str:
    """Normalize user-typed location for Indian job search.

    - Fixes common misspellings (Banglore → Bangalore)
    - Appends ', India' if the location is a known Indian city
    - Returns the original if no match
    """
    clean = raw.strip()
    lower = clean.lower()

    # Exact alias match
    if lower in _CITY_ALIASES:
        canonical = _CITY_ALIASES[lower]
        if canonical in _INDIA_CITIES:
            return f"{canonical}, India"
        return canonical

    # Check if it already contains a country/state qualifier
    lower_full = lower
    if any(q in lower_full for q in [", india", "india", ", karnataka", ", tamil",
                                      ", maharashtra", ", telangana", ", west bengal"]):
        return clean

    # Fuzzy match: check if any known city is a substring
    for alias, canonical in _CITY_ALIASES.items():
        if alias in lower or lower in alias:
            if canonical in _INDIA_CITIES:
                return f"{canonical}, India"
            return canonical

    # Check exact city names
    for city in _INDIA_CITIES:
        if city.lower() in lower or lower in city.lower():
            return f"{city}, India"

    # Default: return as-is (could be non-India location)
    return clean


# ── Key rotation state (thread-safe) ─────────────────────────────────────────
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
            logger.warning(f"Groq key ...{key[-6:]} marked as failed. Rotating.")
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


KEY_ROTATOR = KeyRotator(ALL_GROQ_KEYS, GEMINI_API_KEY)
