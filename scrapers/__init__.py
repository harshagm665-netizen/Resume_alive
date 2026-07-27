"""scrapers/__init__.py"""
from .base import Job, BaseScraper
from .linkedin import LinkedInScraper
from .shine import ShineScraper
from .naukri import NaukriScraper
from .indeed import IndeedScraper
from .instahyre import InstaHyreScraper
from .foundit import FounditScraper
from .jobspy_scraper import JobSpyScraper

# Singleton scraper instances — reused across searches to share sessions
SCRAPER_INSTANCES = {
    "LinkedIn": LinkedInScraper(),
    "Shine": ShineScraper(),
    "Naukri": NaukriScraper(),
    "Indeed": IndeedScraper(),
    "InstaHyre": InstaHyreScraper(),
    "Foundit": FounditScraper(),
    "JobSpy": JobSpyScraper(),
}

ALL_SCRAPERS = [
    LinkedInScraper,    # LinkedIn (global)
    ShineScraper,       # Shine.com (India, SSR extraction)
    NaukriScraper,      # Naukri.com (India, API + HTML fallback)
    IndeedScraper,      # Indeed.com (India)
    InstaHyreScraper,   # InstaHyre (India)
]

__all__ = [
    "Job", "BaseScraper",
    "LinkedInScraper", "ShineScraper", "NaukriScraper",
    "IndeedScraper", "InstaHyreScraper", "FounditScraper", "JobSpyScraper",
    "ALL_SCRAPERS", "SCRAPER_INSTANCES",
]
