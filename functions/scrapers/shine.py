"""
scrapers/shine.py — Shine.com job scraper.
Uses __NEXT_DATA__ SSR extraction with confirmed field mapping.
"""

import re
import json
from bs4 import BeautifulSoup
from loguru import logger
from .base import BaseScraper, Job


class ShineScraper(BaseScraper):
    portal_name = "Shine"
    BASE_URL = "https://www.shine.com"
    SEARCH_URL = "https://www.shine.com/job-search/{query}-jobs-in-{location}"

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        jobs: list[Job] = []
        page = 1

        logger.info(f"[Shine] Searching: '{query}' in '{location}'")

        while len(jobs) < max_results:
            slug_query = query.lower().replace(" ", "-")
            slug_loc = location.lower().replace(" ", "-")
            url = f"{self.SEARCH_URL.format(query=slug_query, location=slug_loc)}?page={page}"

            resp = self._get(url)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # Extract jobs from __NEXT_DATA__ SSR data
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if next_data_script:
                try:
                    next_data = json.loads(next_data_script.string or "{}")
                    # Navigate to job results in initialState
                    initial_state = next_data.get("props", {}).get("pageProps", {}).get("initialState", {})
                    jsrp = initial_state.get("jsrp", {})
                    search_result = jsrp.get("searchresult", {})
                    data = search_result.get("data", {})
                    results = data.get("results", [])

                    if not results:
                        # Try alternative path
                        results = jsrp.get("jobList", [])

                    for item in results:
                        if len(jobs) >= max_results:
                            break

                        try:
                            # Confirmed field mapping from probe
                            title = item.get("jJT", "") or "Unknown"
                            company = item.get("jCName", "") or "Unknown"
                            location_list = item.get("jLoc", [])
                            if isinstance(location_list, list) and location_list:
                                loc = ", ".join(str(l) for l in location_list[:2])
                            else:
                                loc = str(location_list) if location_list else location
                            salary = item.get("jSal", "") or "Not disclosed"
                            experience = item.get("jExp", "") or "Not specified"
                            description_html = item.get("jJD", "") or ""
                            description = re.sub(r"<[^>]+>", " ", description_html).strip()[:500]
                            posted_date = item.get("jPDate", "") or ""
                            job_id = str(item.get("id", ""))

                            # Build URL from slug
                            slug = item.get("jSlug", "")
                            if slug:
                                url_j = f"{self.BASE_URL}/jobs/{slug}"
                            else:
                                url_j = item.get("jRUrl", "") or f"{self.BASE_URL}/jobs/{job_id}"

                            jobs.append(Job(
                                title=title,
                                company=company,
                                location=loc,
                                url=url_j,
                                portal=self.portal_name,
                                salary=salary,
                                description=description,
                                posted_date=posted_date[:10] if posted_date else "",
                                experience=experience,
                                job_id=job_id,
                            ))
                        except Exception as e:
                            logger.debug(f"[Shine] Item parse error: {e}")

                    # Check if we have more pages
                    total_jobs = search_result.get("totalJobCount", 0)
                    if len(results) < 20 or len(jobs) >= total_jobs:
                        break
                    page += 1
                    continue

                except Exception as e:
                    logger.debug(f"[Shine] __NEXT_DATA__ parse error: {e}")

            # Fallback: HTML scraping
            cards = soup.select("div.jobTuple") or soup.select("article.job-result-card") or soup.select("li.job-card")
            if not cards:
                break

            for card in cards:
                if len(jobs) >= max_results:
                    break
                try:
                    title_el = card.select_one("h3.job-title a, a.jobTitle, h2.job-title")
                    company_el = card.select_one("span.company-name, div.company, a.company")
                    location_el = card.select_one("span.loc, span.location, li.location")
                    salary_el = card.select_one("span.salary, li.salary")
                    exp_el = card.select_one("span.exp, li.experience")

                    title = title_el.get_text(strip=True) if title_el else "Unknown"
                    href = title_el.get("href", "") if title_el else ""
                    url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    loc = location_el.get_text(strip=True) if location_el else location
                    salary = salary_el.get_text(strip=True) if salary_el else "Not disclosed"
                    experience = exp_el.get_text(strip=True) if exp_el else "Not specified"
                    job_id = re.search(r"/(\d+)", url).group(1) if re.search(r"/(\d+)", url) else url

                    if not title or title == "Unknown":
                        continue

                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=loc,
                        url=url,
                        portal=self.portal_name,
                        salary=salary,
                        experience=experience,
                        job_id=job_id,
                    ))
                except Exception as e:
                    logger.debug(f"[Shine] Card parse error: {e}")

            # HTML scraper doesn't easily paginate, exit after first page
            break

        logger.info(f"[Shine] Found {len(jobs)} jobs.")
        return jobs
