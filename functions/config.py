"""
functions/config.py — Configuration, environment variables, and constants.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TG_TOKEN: str = os.getenv("tg_token", "")
TG_CHAT_ID: str = os.getenv("tg_chat_id", "")
TG_API_ID: str = os.getenv("tg_api_id", "")
TG_API_HASH: str = os.getenv("tg_api_hash", "")
TG_ERR_TOPIC_ID: Optional[str] = os.getenv("tg_err_topic_id")
TG_REPORT_TOPIC_ID: Optional[str] = os.getenv("tg_report_topic_id")

# ── API Keys ──────────────────────────────────────────────────────────────────
# Primary Groq Key
PRIMARY_GROQ_KEY = os.getenv("llm_api_key", "")
# Backup Groq Keys (comma separated)
BACKUP_GROQ_KEYS_RAW = os.getenv("GROQ_BACKUP_KEYS", "")
BACKUP_GROQ_KEYS = [k.strip() for k in BACKUP_GROQ_KEYS_RAW.split(",") if k.strip()]

# Combine all Groq keys
ALL_GROQ_KEYS = []
if PRIMARY_GROQ_KEY:
    ALL_GROQ_KEYS.append(PRIMARY_GROQ_KEY)
ALL_GROQ_KEYS.extend(BACKUP_GROQ_KEYS)

GEMINI_API_KEY: str = os.getenv("GEMINI", "")

# ── LinkedIn ─────────────────────────────────────────────────────────────────
LINKEDIN_EMAIL: str = os.getenv("linkedin_email", "")
LINKEDIN_PASSWORD: str = os.getenv("linkedin_password", "")

# ── Upstash Redis ────────────────────────────────────────────────────────────
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

# ── Qdrant ───────────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# ── Misc ──────────────────────────────────────────────────────────────────────
ATS_QC_ENABLED: bool = os.getenv("ats_qc_enabled", "True").lower() == "true"
TG_LISTEN_ENABLED: bool = os.getenv("tg_listen_enabled", "True").lower() == "true"

# ── Shared constants ──────────────────────────────────────────────────────────
MAX_RESULTS_PER_PORTAL = 10
MAX_DISPLAY = 25
SCORE_THRESHOLD = 40

# ── Dedup Thresholds ──────────────────────────────────────────────────────────
DEDUP_CONFIG = {
    "spam_threshold": 3,
    "user_seen_ttl": 60 * 60 * 24 * 7, # 7 days
}

# ── Location normalization ─────────────────────────────────────────────────────
# Maps common misspellings/aliases → canonical Indian city name
_CITY_ALIASES: dict[str, str] = {
    "banglore": "Bangalore", "bangalor": "Bangalore", "bengaluru": "Bangalore",
    "bengalore": "Bangalore", "bangaluru": "Bangalore", "bangalore": "Bangalore",
    "bngalore": "Bangalore", "blr": "Bangalore",
    "bombay": "Mumbai", "mumbay": "Mumbai", "mumabi": "Mumbai",
    "new delhi": "Delhi", "ndelhi": "Delhi", "delhi ncr": "Delhi",
    "hyderabad": "Hyderabad", "hyd": "Hyderabad", "secunderabad": "Hyderabad",
    "chennai": "Chennai", "madras": "Chennai",
    "pune": "Pune",
    "kolkata": "Kolkata", "calcutta": "Kolkata", "kolcutta": "Kolkata",
    "gurgaon": "Gurugram", "gurugram": "Gurugram", "ggn": "Gurugram",
    "noida": "Noida",
    "ahmedabad": "Ahmedabad", "amdabad": "Ahmedabad", "ahemdabad": "Ahmedabad",
    "jaipur": "Jaipur",
    "chandigarh": "Chandigarh",
    "kochi": "Kochi", "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram", "trivendrum": "Thiruvananthapuram",
    "coimbatore": "Coimbatore", "covai": "Coimbatore",
    "mysore": "Mysuru", "mysuru": "Mysuru",
    "indore": "Indore",
    "bhopal": "Bhopal",
    "patna": "Patna",
    "lucknow": "Lucknow",
    "vizag": "Visakhapatnam", "vishakhapatnam": "Visakhapatnam",
    "nagpur": "Nagpur",
    "surat": "Surat",
}

_INDIA_CITIES = {
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune",
    "Kolkata", "Gurugram", "Noida", "Ahmedabad", "Jaipur", "Chandigarh",
    "Kochi", "Thiruvananthapuram", "Coimbatore", "Mysuru", "Indore",
    "Bhopal", "Patna", "Lucknow", "Visakhapatnam", "Nagpur", "Surat",
}

def normalize_location(raw: str) -> str:
    clean = raw.strip()
    lower = clean.lower()

    if lower in _CITY_ALIASES:
        canonical = _CITY_ALIASES[lower]
        if canonical in _INDIA_CITIES:
            return f"{canonical}, India"
        return canonical

    lower_full = lower
    if any(q in lower_full for q in [", india", "india", ", karnataka", ", tamil",
                                      ", maharashtra", ", telangana", ", west bengal"]):
        return clean

    for alias, canonical in _CITY_ALIASES.items():
        if alias in lower or lower in alias:
            if canonical in _INDIA_CITIES:
                return f"{canonical}, India"
            return canonical

    for city in _INDIA_CITIES:
        if city.lower() in lower or lower in city.lower():
            return f"{city}, India"

    return clean
