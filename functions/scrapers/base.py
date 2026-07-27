"""
scrapers/base.py — Base scraper class and Job dataclass.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from curl_cffi import requests
from curl_cffi.requests.errors import RequestsError
from fake_useragent import UserAgent
from loguru import logger

from db.models import Job

class BaseScraper(ABC):
    """Abstract base for all job portal scrapers."""

    portal_name: str = "unknown"
    BASE_URL: str = ""

    def __init__(self):
        self._ua = UserAgent()
        self._session = requests.Session(impersonate="chrome")
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
            if resp.status_code >= 400:
                logger.debug(f"[{self.portal_name}] HTTP {resp.status_code} for {url}")
                return None
            return resp
        except RequestsError as e:
            logger.debug(f"[{self.portal_name}] Request error: {e}")
        return None

    @abstractmethod
    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        """Search for jobs. Must be implemented by each scraper."""
        ...
