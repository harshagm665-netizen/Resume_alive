import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from scrapers import ALL_SCRAPERS, SCRAPER_INSTANCES

def search_jobs(query, location):
    all_jobs = []
    search_query = query
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {
            executor.submit(
                SCRAPER_INSTANCES[scraper_cls.portal_name].search,
                search_query, location, 15
            ): scraper_cls.portal_name
            for scraper_cls in ALL_SCRAPERS
            if scraper_cls.portal_name in SCRAPER_INSTANCES
        }
        for future in as_completed(future_map, timeout=60):
            portal = future_map[future]
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"[Error in {portal}] {e}")
                
    return all_jobs

def main():
    parser = argparse.ArgumentParser(description="Job Scraper CLI")
    parser.add_argument("query", help="Job role (e.g. 'Robotics Engineer')")
    parser.add_argument("location", help="Location (e.g. 'Bangalore')")
    args = parser.parse_args()
    
    print(f"\n--- Searching for '{args.query}' in '{args.location}' ---\n")
    
    jobs = search_jobs(args.query, args.location)
    
    def matches_location(job_loc, target_loc):
        jl = (job_loc or "").lower()
        tl = target_loc.lower()
        if tl in jl or "remote" in jl: return True
        if tl == "india" or tl == "skip": return True
        if "bangalore" in tl or "banglore" in tl or "bengaluru" in tl:
            if "bangalore" in jl or "bengaluru" in jl or "banglore" in jl: return True
        return False

    def is_older_than_a_week(posted: str) -> bool:
        p = (posted or "").lower()
        old_keywords = ["month", "30 days", "14 days", "15 days", "20 days", "weeks", "2 week", "3 week", "4 week", "year"]
        return any(k in p for k in old_keywords)

    def is_relevant(job_title: str, query: str) -> bool:
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        jt = job_title.lower()
        return any(qw in jt for qw in query_words)

    seen = set()
    unique_jobs = []
    for job in jobs:
        if is_older_than_a_week(job.posted_date): continue
        if not matches_location(job.location, args.location): continue
        if not is_relevant(job.title, args.query): continue
        k = job.dedup_key()
        if k not in seen:
            seen.add(k)
            unique_jobs.append(job)
            
    if not unique_jobs:
        print("No matching jobs found (or anti-bot blocked the request).")
        return
        
    print(f"Found {len(unique_jobs)} unique jobs:\n")
    for i, job in enumerate(unique_jobs[:15], 1):
        print(f"{i}. [{job.portal}] {job.title}")
        print(f"   Company: {job.company}")
        print(f"   Location: {job.location}")
        print(f"   Posted: {job.posted_date}")
        print(f"   URL: {job.url}\n")
        
    if len(unique_jobs) > 15:
        print(f"... and {len(unique_jobs) - 15} more.")

if __name__ == '__main__':
    main()
