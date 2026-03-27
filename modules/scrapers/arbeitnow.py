"""
modules/scrapers/arbeitnow.py — Arbeitnow free API.
"""
import re, html, requests
from datetime import datetime, timedelta
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import MAX_JOBS_PER_SOURCE, SCRAPE_MAX_DAYS
from ._utils import make_job


def scrape_arbeitnow(
    keywords: Optional[List[str]] = None,
    max_days: int = SCRAPE_MAX_DAYS,
) -> List[dict]:
    cutoff = datetime.now() - timedelta(days=max_days)
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                         headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[Arbeitnow] {e}")
        return []

    all_jobs: List[dict] = []
    for item in data.get("data", []):
        created = item.get("created_at","")
        posted = None
        if created:
            try:
                posted = datetime.fromisoformat(created.replace("Z","+00:00")).replace(tzinfo=None)
                if posted < cutoff:
                    continue
            except Exception:
                pass

        desc = re.sub(r"<[^>]+>", " ", item.get("description",""))
        desc = html.unescape(desc).strip()

        if keywords:
            combined = (item.get("title","") + " " + desc).lower()
            if not any(kw.lower() in combined for kw in keywords):
                continue

        j = make_job(
            title=item.get("title",""),
            company=item.get("company_name",""),
            location=item.get("location","Remote"),
            url=item.get("url",""),
            description=desc[:3000],
            source="Arbeitnow",
            posted_date=posted.strftime("%Y-%m-%d") if posted else "",
        )
        if j:
            all_jobs.append(j)

        if len(all_jobs) >= MAX_JOBS_PER_SOURCE:
            break

    print(f"[Arbeitnow] Total: {len(all_jobs)} relevant jobs")
    return all_jobs[:MAX_JOBS_PER_SOURCE]