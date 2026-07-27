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
        
        target_portals = portals if portals else self.available_portals
        all_jobs: List[Job] = []
        
        for portal in target_portals:
            if portal not in self.scrapers:
                logger.warning(f"Portal {portal} not found.")
                continue
                
            scraper = self.scrapers[portal]
            try:
                # Scrapers return dicts or dataclasses, convert them to our new Job model if needed
                # We updated db.models.Job to have the exact same fields, but let's be careful
                raw_jobs = scraper.search(query, norm_location, max_results)
                for rj in raw_jobs:
                    # In python, if rj is the original dataclass, we can convert it:
                    if hasattr(rj, "__dict__"):
                        try:
                            # if rj is already a db.models.Job, this is fine too.
                            # The fields match because we updated models.py.
                            job_data = {k: v for k, v in rj.__dict__.items() if not k.startswith("_")}
                            # Avoid passing non-pydantic fields
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

                            all_jobs.append(Job(**job_data))
                        except Exception as parse_e:
                            logger.error(f"Error converting job: {parse_e}")
                            
            except Exception as e:
                logger.error(f"[DiscoveryAgent] Scraper {portal} failed: {e}")
                
        logger.info(f"[DiscoveryAgent] Total jobs discovered: {len(all_jobs)}")
        return all_jobs
