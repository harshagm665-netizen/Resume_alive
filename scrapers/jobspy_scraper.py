"""
scrapers/jobspy_scraper.py — Uses python-jobspy to reliably scrape
LinkedIn and Indeed (handles anti-bot measures internally).
"""
import re
from loguru import logger
from .base import BaseScraper, Job

try:
    import jobspy as _jobspy
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False


class JobSpyScraper(BaseScraper):
    """
    Wraps python-jobspy which reliably scrapes LinkedIn + Indeed
    using session rotation and proper headers.
    """
    portal_name = "JobSpy"
    BASE_URL = ""

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        if not JOBSPY_AVAILABLE:
            logger.warning("[JobSpy] python-jobspy not installed — skipping.")
            return []

        jobs: list[Job] = []
        logger.info(f"[JobSpy] Searching: '{query}' in '{location}'")

        try:
            df = _jobspy.scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=query,
                location=location,
                results_wanted=max_results,
                country_indeed="India",
                hours_old=720,      # last 30 days
                linkedin_fetch_description=False,
            )
        except Exception as e:
            logger.error(f"[JobSpy] scrape_jobs failed: {e}")
            return []

        if df is None or df.empty:
            logger.warning("[JobSpy] No results returned.")
            return []

        for _, row in df.iterrows():
            try:
                title = str(row.get("title", "Unknown") or "Unknown")
                company = str(row.get("company", "Unknown") or "Unknown")
                loc = str(row.get("location", location) or location)
                url = str(row.get("job_url", "") or "")
                salary = _fmt_salary(row)
                description = str(row.get("description", "") or "")[:500]
                date_posted = str(row.get("date_posted", "") or "")
                portal = str(row.get("site", "JobSpy")).capitalize()
                job_id = str(row.get("id", "")) or url

                if not url or not title or title == "Unknown":
                    continue

                jobs.append(Job(
                    title=title,
                    company=company,
                    location=loc,
                    url=url,
                    portal=portal,
                    salary=salary,
                    description=description,
                    posted_date=str(date_posted)[:10],
                    job_id=job_id,
                ))
            except Exception as e:
                logger.debug(f"[JobSpy] Row parse error: {e}")
                continue

        logger.info(f"[JobSpy] Found {len(jobs)} jobs.")
        return jobs


def _fmt_salary(row) -> str:
    try:
        lo = row.get("min_amount")
        hi = row.get("max_amount")
        interval = str(row.get("salary_source", "") or "")
        if lo and hi:
            return f"₹{int(lo):,}–{int(hi):,} {interval}".strip()
        elif lo:
            return f"₹{int(lo):,}+"
    except Exception:
        pass
    return "Not disclosed"
