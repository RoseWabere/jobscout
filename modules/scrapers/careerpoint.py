"""
modules/scrapers/careerpoint.py
CareerPoint Kenya — requests + BeautifulSoup.
"""
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import SCRAPE_DELAY_SECONDS, MAX_JOBS_PER_SOURCE, SCRAPE_MAX_DAYS
from ._utils import make_job, normalize_date

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.1 Safari/537.36"
    ),
}

_CP_SEARCHES = ["data", "analyst", "python", "software", "technology", "ict", "engineer"]


def scrape_careerpointkenya(
    keywords:  Optional[List[str]] = None,
    max_days:  int = SCRAPE_MAX_DAYS,
    max_pages: int = 2,
) -> List[dict]:
    cutoff   = datetime.now() - timedelta(days=max_days)
    searches = keywords if keywords else _CP_SEARCHES
    all_jobs: List[dict] = []
    seen_urls: set = set()

    for term in searches:
        for page in range(1, max_pages + 1):
            q   = term.replace(" ", "+")
            url = f"https://careerpointkenya.co.ke/jobs/?s={q}&pg={page}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                print(f"[CareerPoint] {e}")
                break

            cards = soup.select(
                "div.job-listing, article.job, li[class*='job'], "
                "div[class*='job'], article"
            )
            if not cards:
                break

            added = 0
            for card in cards:
                title_el   = card.select_one("h2 a, h3 a, a[href*='/job/'], [class*='title'] a")
                company_el = card.select_one("[class*='company'], [class*='employer']")
                date_el    = card.select_one("span.date, time, [class*='posted'], [class*='date']")

                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href  = title_el.get("href","")
                if href.startswith("/"):
                    href = "https://careerpointkenya.co.ke" + href
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                posted = normalize_date(date_el.get_text(strip=True) if date_el else "")
                if posted and posted < cutoff:
                    continue

                job = make_job(
                    title=title,
                    company=company_el.get_text(strip=True) if company_el else "",
                    location="Kenya",
                    url=href,
                    source="CareerPoint KE",
                    posted_date=posted.strftime("%Y-%m-%d") if posted else "",
                )
                if job:
                    all_jobs.append(job)
                    added += 1

            time.sleep(SCRAPE_DELAY_SECONDS)
            if not added:
                break

        if len(all_jobs) >= MAX_JOBS_PER_SOURCE:
            break

    return all_jobs[:MAX_JOBS_PER_SOURCE]