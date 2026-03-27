"""
modules/scrapers/__init__.py
Orchestrates all scrapers. Single entry point: run_scrapers().
"""
from typing import List, Optional, Callable

from .brightermonday import scrape_brightermonday
from .fuzu           import scrape_fuzu
from .myjobmag       import scrape_myjobmag
from .careerpoint    import scrape_careerpointkenya
from .remotive       import scrape_remotive
from .arbeitnow      import scrape_arbeitnow
from .myjobs import scrape_myjobsinkenya


SOURCE_MAP = {
    "BrighterMonday": scrape_brightermonday,
    "Fuzu":           scrape_fuzu,
    "MyJobMag":       scrape_myjobmag,
    "MyJobsInKenya":  scrape_myjobsinkenya,
    "CareerPoint KE": scrape_careerpointkenya,
    "Remotive":       scrape_remotive,
    "Arbeitnow":      scrape_arbeitnow,
}


def run_scrapers(
    sources:     Optional[List[str]]          = None,
    keywords:    Optional[List[str]]          = None,
    max_days:    int                          = 7,
    progress_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    from database import insert_job, log_scrape

    if sources is None:
        sources = list(SOURCE_MAP.keys())

    summary   = {}
    total_new = 0

    for name in sources:
        fn = SOURCE_MAP.get(name)
        if not fn:
            continue
        if progress_fn:
            progress_fn(f"Scanning {name}...")
        try:
            jobs      = fn(keywords=keywords, max_days=max_days)
            new_count = sum(1 for j in jobs if insert_job(j))
            total_new += new_count
            summary[name] = {"found": len(jobs), "new": new_count, "status": "ok"}
            log_scrape(name, len(jobs), new_count, "ok")
        except Exception as e:
            msg = str(e)
            summary[name] = {"found": 0, "new": 0, "status": "error", "msg": msg}
            log_scrape(name, 0, 0, "error", msg)
            print(f"[{name}] ERROR: {e}")

    return {"sources": summary, "total_new": total_new}