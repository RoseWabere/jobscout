"""
modules/scrapers/remotive.py — Remotive free API.
"""
import re, html, requests
from datetime import datetime, timedelta
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import MAX_JOBS_PER_SOURCE, SCRAPE_MAX_DAYS
from ._utils import make_job, normalize_date

_SEARCHES = ["data engineer", "data analyst", "python", "machine learning",
             "analytics", "business intelligence", "backend", "software engineer"]


def scrape_remotive(
    keywords: Optional[List[str]] = None,
    max_days: int = SCRAPE_MAX_DAYS,
) -> List[dict]:
    cutoff   = datetime.now() - timedelta(days=max_days)
    searches = keywords if keywords else _SEARCHES
    all_jobs: List[dict] = []
    seen: set = set()

    for term in searches:
        try:
            r = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": term, "limit": 20},
                headers=HEADERS, timeout=15,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[Remotive] {term}: {e}")
            continue

        for item in data.get("jobs", []):
            url = item.get("url","")
            if url in seen:
                continue
            seen.add(url)

            pub = item.get("publication_date","")
            posted = None
            if pub:
                try:
                    posted = datetime.fromisoformat(pub.replace("Z","+00:00")).replace(tzinfo=None)
                    if posted < cutoff:
                        continue
                except Exception:
                    pass

            desc = re.sub(r"<[^>]+>", " ", item.get("description",""))
            desc = html.unescape(desc).strip()

            j = make_job(
                title=item.get("title",""),
                company=item.get("company_name",""),
                location=item.get("candidate_required_location","Remote"),
                url=url,
                description=desc[:3000],
                source="Remotive",
                posted_date=posted.strftime("%Y-%m-%d") if posted else "",
            )
            if j:
                all_jobs.append(j)

        if len(all_jobs) >= MAX_JOBS_PER_SOURCE:
            break

    print(f"[Remotive] Total: {len(all_jobs)} relevant jobs")
    return all_jobs[:MAX_JOBS_PER_SOURCE]