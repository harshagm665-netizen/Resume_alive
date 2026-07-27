"""
scrapers/naukri.py — Naukri.com scraper.
Uses the internal API with correct headers; falls back to HTML scraping.
"""

import re
import json
from bs4 import BeautifulSoup
from loguru import logger
from .base import BaseScraper, Job


class NaukriScraper(BaseScraper):
    portal_name = "Naukri"
    BASE_URL = "https://www.naukri.com"

    def search(self, query: str, location: str, max_results: int = 20) -> list[Job]:
        logger.info(f"[Naukri] Searching: '{query}' in '{location}'")
        jobs = self._try_api(query, location, max_results)
        if not jobs:
            jobs = self._try_html(query, location, max_results)
        logger.info(f"[Naukri] Found {len(jobs)} jobs.")
        return jobs

    # ── Method 1: JSON API ─────────────────────────────────────────────────────
    def _try_api(self, query: str, location: str, max_results: int) -> list[Job]:
        jobs: list[Job] = []
        slug_q = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        slug_l = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
        api_url = "https://www.naukri.com/jobapi/v3/search"
        headers = {
            **self._default_headers(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "appid": "109",
            "systemid": "109",
            "Referer": f"https://www.naukri.com/{slug_q}-jobs-in-{slug_l}",
        }
        self._session.headers.update(headers)
        params = {
            "noOfResults": min(max_results, 20),
            "urlType": "search_by_key_loc",
            "searchType": "adv",
            "keyword": query,
            "location": location,
            "pageNo": 1,
            "jobAge": 7,
            "seoKey": f"{slug_q}-jobs-in-{slug_l}",
            "src": "jobsearchDesk",
        }
        resp = self._get(api_url, params=params)
        if not resp:
            return []
        try:
            data = resp.json()
        except Exception:
            return []

        for item in data.get("jobDetails", []):
            if len(jobs) >= max_results:
                break
            try:
                title    = item.get("title", "Unknown")
                company  = item.get("companyName", "Unknown")
                placeholders = item.get("placeholders", [])
                loc      = placeholders[0].get("label", location) if placeholders else location
                job_id   = str(item.get("jobId", ""))
                url      = item.get("jdURL", "")
                if not url.startswith("http"):
                    url = f"https://www.naukri.com{url}"
                salary   = item.get("salary", "") or "Not disclosed"
                exp      = item.get("experience", {})
                exp_lbl  = exp.get("label", "Not specified") if isinstance(exp, dict) else str(exp)
                desc     = re.sub(r"<[^>]+>", " ", item.get("jobDescription", "") or "").strip()[:500]
                posted   = item.get("footerPlaceholderLabel", "")
                jobs.append(Job(
                    title=title, company=company, location=loc[:80],
                    url=url, portal=self.portal_name, salary=salary,
                    description=desc, posted_date=posted, experience=exp_lbl,
                    job_id=job_id,
                ))
            except Exception as e:
                logger.debug(f"[Naukri API] parse error: {e}")
        return jobs

    # ── Method 2: HTML scraping ────────────────────────────────────────────────
    def _try_html(self, query: str, location: str, max_results: int) -> list[Job]:
        jobs: list[Job] = []
        slug_q = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        slug_l = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
        url = f"https://www.naukri.com/{slug_q}-jobs-in-{slug_l}"
        resp = self._get(url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("article.jobTuple, div.jobTuple, div[class*='job-tuple']")
        if not cards:
            # Try extracting from embedded JSON
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, list):
                        items = data
                    elif data.get("@type") == "ItemList":
                        items = [e.get("item", {}) for e in data.get("itemListElement", [])]
                    else:
                        continue
                    for item in items:
                        if len(jobs) >= max_results:
                            break
                        title = item.get("title", "") or item.get("name", "")
                        url_j = item.get("url", "") or item.get("sameAs", "")
                        company = ""
                        if isinstance(item.get("hiringOrganization"), dict):
                            company = item["hiringOrganization"].get("name", "")
                        loc_data = item.get("jobLocation", {})
                        if isinstance(loc_data, dict):
                            addr = loc_data.get("address", {})
                            loc_j = addr.get("addressLocality", location) if isinstance(addr, dict) else location
                        else:
                            loc_j = location
                        if title and url_j:
                            jobs.append(Job(
                                title=title, company=company, location=loc_j,
                                url=url_j, portal=self.portal_name, job_id=url_j,
                            ))
                except Exception:
                    continue

        for card in cards:
            if len(jobs) >= max_results:
                break
            try:
                t_el = card.select_one("a.title, .jobTitle a, h3.title")
                c_el = card.select_one("a.subTitle, .companyInfo a, .company-name")
                l_el = card.select_one("li.location span, .location span")
                s_el = card.select_one("li.salary span, .salary")
                e_el = card.select_one("li.experience span, .experience")
                if not t_el:
                    continue
                title   = t_el.get_text(strip=True)
                href    = t_el.get("href", "")
                url_j   = href if href.startswith("http") else f"https://www.naukri.com{href}"
                company = c_el.get_text(strip=True) if c_el else "Unknown"
                loc_j   = l_el.get_text(strip=True) if l_el else location
                salary  = s_el.get_text(strip=True) if s_el else "Not disclosed"
                exp     = e_el.get_text(strip=True) if e_el else "Not specified"
                job_id  = re.search(r"-(\d+)\.htm", url_j)
                job_id  = job_id.group(1) if job_id else url_j
                jobs.append(Job(
                    title=title, company=company, location=loc_j,
                    url=url_j, portal=self.portal_name, salary=salary,
                    experience=exp, job_id=job_id,
                ))
            except Exception as e:
                logger.debug(f"[Naukri HTML] parse error: {e}")

        return jobs
