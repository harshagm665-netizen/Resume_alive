"""
functions/agents/job_discovery.py — Agent responsible for executing multi-portal searches.
"""

from typing import List, Dict, Any
from loguru import logger
from db.models import Job
from scrapers import ALL_SCRAPERS, SCRAPER_INSTANCES
from tools.location_resolver import resolve_location

class JobDiscoveryAgent:
    """Agent that orchestrates the scraping process."""
    
    def __init__(self):
        self.scrapers = SCRAPER_INSTANCES
        self.available_portals = list(self.scrapers.keys())
        
    def discover_jobs(self, query: str, location: str, max_results: int = 10, portals: List[str] = None) -> List[Job]:
        """Runs the scrapers and returns raw scraped jobs."""
        logger.info(f"[DiscoveryAgent] Finding jobs for '{query}' in '{location}'")
        
        # Resolve location
        norm_location = resolve_location(location)
        logger.debug(f"Normalized location: {norm_location}")
        
        import concurrent.futures
        
        target_portals = portals if portals else self.available_portals
        all_jobs: List[Job] = []
        
        def run_scraper(portal: str) -> List[Job]:
            if portal not in self.scrapers:
                logger.warning(f"Portal {portal} not found.")
                return []
                
            scraper = self.scrapers[portal]
            local_jobs = []
            try:
                raw_jobs = scraper.search(query, norm_location, max_results)
                for rj in raw_jobs:
                    if hasattr(rj, "__dict__"):
                        try:
                            job_data = {k: v for k, v in rj.__dict__.items() if not k.startswith("_")}
                            if 'score' in job_data:
                                job_data['ai_score'] = float(job_data.pop('score'))
                            if 'match_level' in job_data:
                                del job_data['match_level']
                            if 'matching_skills' in job_data:
                                del job_data['matching_skills']
                            if 'missing_skills' in job_data:
                                del job_data['missing_skills']
                            if 'score_reason' in job_data:
                                del job_data['score_reason']

                            local_jobs.append(Job(**job_data))
                        except Exception as parse_e:
                            logger.error(f"Error converting job: {parse_e}")
            except Exception as e:
                logger.error(f"[DiscoveryAgent] Scraper {portal} failed: {e}")
            return local_jobs

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(target_portals) or 1) as executor:
            future_to_portal = {executor.submit(run_scraper, p): p for p in target_portals}
            for future in concurrent.futures.as_completed(future_to_portal):
                portal_jobs = future.result()
                all_jobs.extend(portal_jobs)
                
        logger.info(f"[DiscoveryAgent] Total jobs discovered: {len(all_jobs)}")
        return all_jobs
