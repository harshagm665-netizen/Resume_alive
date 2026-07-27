"""
scrapers/foundit.py — Foundit (formerly Monster India) scraper.
Uses public HTML search page with updated selectors.
"""
import re
import json
from bs4 import BeautifulSoup
from loguru import logger
from .base import BaseScraper, Job


class FounditScraper(BaseScraper):
    portal_name = "Foundit"
    BASE_URL = "https://www.foundit.in"

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        jobs: list[Job] = []
        logger.info(f"[Foundit] Searching: '{query}' in '{location}'")

        # Try the main search page
        params = {"query": query, "location": location}
        url = f"{self.BASE_URL}/srp/results"
        resp = self._get(url, params=params)
        if not resp:
            logger.debug("[Foundit] Could not reach search page.")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # Try embedded JSON (Next.js __NEXT_DATA__)
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data:
            try:
                data = json.loads(next_data.string or "")
                job_list = (
                    data.get("props", {})
                        .get("pageProps", {})
                        .get("jobSearchResult", {})
                        .get("jobDetails", [])
                    or
                    data.get("props", {})
                        .get("pageProps", {})
                        .get("data", {})
                        .get("jobs", [])
                )
                for item in job_list:
                    if len(jobs) >= max_results:
                        break
                    try:
                        title   = item.get("designation", "") or item.get("title", "Unknown")
                        company = item.get("company", {})
                        if isinstance(company, dict):
                            company = company.get("name", "Unknown")
                        loc     = item.get("locations", [location])[0] if item.get("locations") else location
                        job_id  = str(item.get("jobId", "") or item.get("id", ""))
                        url_j   = item.get("jobUrl", "") or f"https://www.foundit.in/job/{job_id}"
                        if not url_j.startswith("http"):
                            url_j = self.BASE_URL + url_j
                        salary  = item.get("salary", "Not disclosed") or "Not disclosed"
                        exp     = item.get("experienceRange", "") or "Not specified"
                        desc    = re.sub(r"<[^>]+>", " ", item.get("jobDescription", "") or "").strip()[:500]
                        jobs.append(Job(
                            title=title, company=str(company), location=str(loc),
                            url=url_j, portal=self.portal_name, salary=salary,
                            description=desc, experience=exp, job_id=job_id,
                        ))
                    except Exception as e:
                        logger.debug(f"[Foundit JSON] item error: {e}")
                if jobs:
                    logger.info(f"[Foundit] Found {len(jobs)} jobs (JSON).")
                    return jobs
            except Exception as e:
                logger.debug(f"[Foundit] __NEXT_DATA__ parse error: {e}")

        # Try JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") != "JobPosting" or len(jobs) >= max_results:
                        continue
                    title   = item.get("title", "Unknown")
                    url_j   = item.get("url", "") or item.get("sameAs", "")
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

        # HTML cards fallback
        cards = soup.select("div.card-apply-content, div.jobCard, div[class*='job-card'], article.job")
        for card in cards:
            if len(jobs) >= max_results:
                break
            try:
                t_el = card.select_one("h3 a, a.position-title, .job-title a")
                c_el = card.select_one(".company-name, .company a")
                l_el = card.select_one(".location, .job-location")
                if not t_el:
                    continue
                title   = t_el.get_text(strip=True)
                href    = t_el.get("href", "")
                url_j   = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                company = c_el.get_text(strip=True) if c_el else "Unknown"
                loc_j   = l_el.get_text(strip=True) if l_el else location
                job_id  = re.search(r"/(\d+)", url_j)
                job_id  = job_id.group(1) if job_id else url_j
                jobs.append(Job(
                    title=title, company=company, location=loc_j,
                    url=url_j, portal=self.portal_name, job_id=job_id,
                ))
            except Exception as e:
                logger.debug(f"[Foundit HTML] card error: {e}")

        logger.info(f"[Foundit] Found {len(jobs)} jobs.")
        return jobs
