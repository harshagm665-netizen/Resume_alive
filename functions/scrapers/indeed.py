"""
scrapers/indeed.py — Indeed.com job scraper.
"""

import re
import urllib.parse
from bs4 import BeautifulSoup
from loguru import logger
from .base import BaseScraper, Job


class IndeedScraper(BaseScraper):
    portal_name = "Indeed"
    BASE_URL = "https://in.indeed.com"
    SEARCH_URL = "https://in.indeed.com/jobs"

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        jobs: list[Job] = []
        start = 0
        page_size = 15
        max_pages = 5
        pages_fetched = 0

        logger.info(f"[Indeed] Searching: '{query}' in '{location}'")

        while len(jobs) < max_results and pages_fetched < max_pages:
            pages_fetched += 1
            params = {
                "q": query,
                "l": location,
                "start": start,
                "fromage": "7",
                "sort": "date",
            }
            resp = self._get(self.SEARCH_URL, params=params)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.job_seen_beacon") or soup.select("div.tapItem") or soup.select("div.resultContent")

            if not cards:
                logger.warning("[Indeed] No cards found — possible CAPTCHA or structure change.")
                break

            for card in cards:
                if len(jobs) >= max_results:
                    break
                try:
                    title_el = card.select_one("h2.jobTitle > a, h2.jobTitle span")
                    company_el = card.select_one("span.companyName, [data-testid='company-name']")
                    location_el = card.select_one("div.companyLocation, [data-testid='text-location']")
                    salary_el = card.select_one("div.salary-snippet-container, [data-testid='attribute_snippet_testid']")
                    date_el = card.select_one("span.date, [data-testid='myJobsStateDate']")

                    title = ""
                    link_url = ""
                    if title_el:
                        title = title_el.get_text(strip=True)
                        parent_a = card.select_one("h2.jobTitle > a")
                        if parent_a:
                            href = parent_a.get("href", "")
                            link_url = f"https://in.indeed.com{href}" if href.startswith("/") else href

                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    loc = location_el.get_text(strip=True) if location_el else location
                    salary = salary_el.get_text(strip=True) if salary_el else "Not disclosed"
                    posted = date_el.get_text(strip=True) if date_el else ""

                    # Extract job ID
                    job_id_match = re.search(r"jk=([a-f0-9]+)", link_url)
                    job_id = job_id_match.group(1) if job_id_match else link_url

                    if not title or not link_url:
                        continue

                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=loc,
                        url=link_url,
                        portal=self.portal_name,
                        salary=salary,
                        posted_date=posted,
                        job_id=job_id,
                    ))
                except Exception as e:
                    logger.debug(f"[Indeed] Card parse error: {e}")
                    continue

            if len(cards) < page_size:
                break
            start += page_size

        logger.info(f"[Indeed] Found {len(jobs)} jobs.")
        return jobs
