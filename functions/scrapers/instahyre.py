"""
scrapers/instahyre.py — InstaHyre scraper with updated API + HTML fallback.
"""
import re
import json
from bs4 import BeautifulSoup
from loguru import logger
from .base import BaseScraper, Job


class InstaHyreScraper(BaseScraper):
    portal_name = "InstaHyre"
    BASE_URL = "https://www.instahyre.com"

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        logger.info(f"[InstaHyre] Searching: '{query}' in '{location}'")

        jobs = self._try_api_v2(query, location, max_results)
        if not jobs:
            jobs = self._try_html(query, location, max_results)

        logger.info(f"[InstaHyre] Found {len(jobs)} jobs.")
        return jobs

    def _try_api_v2(self, query: str, location: str, max_results: int) -> list[Job]:
        """Try multiple known API endpoints."""
        endpoints = [
            "/api/v2/opportunity/",
            "/api/v1/opportunity/",
            "/api/v3/jobs/",
        ]
        for ep in endpoints:
            params = {"designation": query, "location": location, "limit": max_results}
            resp = self._get(f"{self.BASE_URL}{ep}", params=params)
            if not resp:
                continue
            try:
                data = resp.json()
                results = data.get("results", []) or data.get("data", []) or []
                if not results:
                    continue
                jobs = []
                for item in results[:max_results]:
                    try:
                        title   = item.get("designation", "") or item.get("title", "Unknown")
                        company = item.get("company", {})
                        company = company.get("name", "Unknown") if isinstance(company, dict) else str(company)
                        loc     = item.get("location", location)
                        if isinstance(loc, list):
                            loc = ", ".join(str(l) for l in loc[:2])
                        job_id  = str(item.get("id", "") or item.get("opportunity_id", ""))
                        url_j   = f"https://www.instahyre.com/candidate/opportunity/{job_id}" if job_id else self.BASE_URL
                        sal_min = item.get("salary_min", "") or ""
                        sal_max = item.get("salary_max", "") or ""
                        salary  = f"₹{sal_min}–{sal_max} LPA" if sal_min and sal_max else "Not disclosed"
                        exp     = str(item.get("experience", "Not specified") or "Not specified")
                        desc    = re.sub(r"<[^>]+>", " ", item.get("description", "") or "").strip()[:500]
                        posted  = str(item.get("created_at", "") or "")[:10]
                        jobs.append(Job(
                            title=title, company=company, location=str(loc),
                            url=url_j, portal=self.portal_name, salary=salary,
                            description=desc, posted_date=posted, experience=exp,
                            job_id=job_id,
                        ))
                    except Exception as e:
                        logger.debug(f"[InstaHyre API] item error: {e}")
                return jobs
            except Exception:
                continue
        return []

    def _try_html(self, query: str, location: str, max_results: int) -> list[Job]:
        """Scrape InstaHyre search page HTML."""
        params = {"designation": query, "location": location}
        resp = self._get(f"{self.BASE_URL}/candidate/jobs/", params=params)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        jobs: list[Job] = []

        # Try JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if len(jobs) >= max_results:
                        break
                    if item.get("@type") != "JobPosting":
                        continue
                    title   = item.get("title", "Unknown")
                    url_j   = item.get("url", "")
                    org     = item.get("hiringOrganization", {})
                    company = org.get("name", "Unknown") if isinstance(org, dict) else "Unknown"
                    loc_obj = item.get("jobLocation", {})
                    if isinstance(loc_obj, dict):
                        addr = loc_obj.get("address", {})
                        loc  = addr.get("addressLocality", location) if isinstance(addr, dict) else location
                    else:
                        loc = location
                    if title and url_j:
                        jobs.append(Job(
                            title=title, company=company, location=loc,
                            url=url_j, portal=self.portal_name, job_id=url_j,
                        ))
            except Exception:
                continue

        return jobs
