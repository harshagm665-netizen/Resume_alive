"""
scrapers/linkedin.py — LinkedIn public job search scraper (no login required).
Uses LinkedIn's public jobs search endpoint.
"""

import re
import urllib.parse
from bs4 import BeautifulSoup
from loguru import logger
from fake_useragent import UserAgent
from .base import BaseScraper, Job


class LinkedInScraper(BaseScraper):
    portal_name = "LinkedIn"
    BASE_URL = "https://www.linkedin.com"
    SEARCH_URL = "https://www.linkedin.com/jobs/search"

    def __init__(self):
        super().__init__()
        self._ua = UserAgent()
        if "Referer" in self._session.headers:
            del self._session.headers["Referer"]

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        jobs: list[Job] = []
        start = 0
        page_size = 25

        logger.info(f"[LinkedIn] Searching: '{query}' in '{location}'")

        while len(jobs) < max_results:
            params = {
                "keywords": query,
                "location": location,
                "start": start,
                "pageSize": page_size,
                "f_TPR": "r604800",  # past 7 days
                "sortBy": "R",         # relevance
            }
            resp = self._get(self.SEARCH_URL, params=params)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.job-search-card")

            if not cards:
                # Try alternate selectors
                cards = soup.select("div.base-card") or soup.select("li.result-card")

            if not cards:
                logger.warning("[LinkedIn] No job cards found — page structure may have changed.")
                break

            for card in cards:
                if len(jobs) >= max_results:
                    break
                try:
                    title_el = card.select_one("h3.base-search-card__title, h3.result-card__title")
                    company_el = card.select_one("h4.base-search-card__subtitle, h4.result-card__subtitle")
                    location_el = card.select_one("span.job-search-card__location, span.result-card__location")
                    link_el = card.select_one("a.base-card__full-link, a.result-card__full-card-link")
                    date_el = card.select_one("time")
                    salary_el = card.select_one("span.job-search-card__salary-info")

                    title = title_el.get_text(strip=True) if title_el else "Unknown"
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    loc = location_el.get_text(strip=True) if location_el else location
                    url = link_el.get("href", "").split("?")[0] if link_el else ""
                    posted = date_el.get("datetime", date_el.get_text(strip=True) if date_el else "")
                    salary = salary_el.get_text(strip=True) if salary_el else "Not disclosed"

                    if not url or not title or title == "Unknown":
                        continue

                    # Extract job ID from URL
                    job_id_match = re.search(r"/jobs/view/(\d+)", url)
                    job_id = job_id_match.group(1) if job_id_match else url

                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=loc,
                        url=url,
                        portal=self.portal_name,
                        salary=salary,
                        posted_date=posted,
                        job_id=job_id,
                    ))
                except Exception as e:
                    logger.debug(f"[LinkedIn] Card parse error: {e}")
                    continue

            if len(cards) < page_size:
                break
            start += page_size

        logger.info(f"[LinkedIn] Found {len(jobs)} jobs.")
        return jobs
