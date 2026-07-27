"""
scrapers/base.py — Base scraper class and Job dataclass.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional
import requests
from fake_useragent import UserAgent
from loguru import logger


@dataclass
class Job:
    """Job listing data from a scraper.

    Scraped fields are set by scrapers; scoring fields are set by job_scorer.
    """
    # ── Scraped data (set by scrapers) ────────────────────────────────────────
    title: str
    company: str
    location: str
    url: str
    portal: str
    salary: str = "Not disclosed"
    description: str = ""
    posted_date: str = "Unknown"
    experience: str = "Not specified"
    job_id: str = ""  # portal-specific ID for dedup

    # ── Scoring data (set by job_scorer) ──────────────────────────────────────
    score: int = 0
    match_level: str = ""
    matching_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    score_reason: str = ""

    def dedup_key(self) -> str:
        return f"{self.portal}::{self.job_id or self.url}"


class BaseScraper(ABC):
    """Abstract base for all job portal scrapers."""

    portal_name: str = "unknown"
    BASE_URL: str = ""

    def __init__(self):
        self._ua = UserAgent()
        self._session = requests.Session()
        self._session.headers.update(self._default_headers())

    def _default_headers(self) -> dict:
        return {
            "User-Agent": self._ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": self.BASE_URL,
        }

    def _get(self, url: str, params: dict | None = None, timeout: int = 15) -> requests.Response | None:
        """Safe GET with error handling and header rotation."""
        self._session.headers["User-Agent"] = self._ua.random
        try:
            resp = self._session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[{self.portal_name}] HTTP {e.response.status_code} for {url}")
        except requests.exceptions.Timeout:
            logger.warning(f"[{self.portal_name}] Timeout for {url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"[{self.portal_name}] Request error: {e}")
        return None

    @abstractmethod
    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        """Search for jobs. Must be implemented by each scraper."""
        ...
