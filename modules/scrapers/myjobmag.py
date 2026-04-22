# modules/scrapers/myjobmag.py
"""
Scraper for myjobmag.co.ke – based on the working example.
"""
import html
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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
BASE_URL = "https://myjobmag.co.ke"

def _clean_text(text: str) -> str:
    """Clean HTML‑encoded text."""
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace('\r', '').replace('\n', ' ').replace('\t', ' ')
    text = text.replace('\u00a0', ' ').replace('\u2019', ' ').replace('\u2023', ' ')
    text = text.replace('\u2013', ' ')
    text = ' '.join(text.split())
    return text.strip()


def scrape_myjobmag(
    keywords: Optional[List[str]] = None,
    max_days: int = SCRAPE_MAX_DAYS,
    max_pages: int = 3,
) -> List[dict]:
    """Scrape myjobmag.co.ke with keyword search."""
    cutoff = datetime.now() - timedelta(days=max_days)
    searches = keywords if keywords else [
        "data", "data analyst", "data engineer", "research", "software engineer",
        "python", "ict", "developer", "analytics"
    ]
    all_jobs = []
    seen_urls = set()

    for term in searches:
        query = term.replace(" ", "+")
        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/search/jobs?q={query}&currentpage={page}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.content, 'html.parser')
            except Exception as e:
                print(f"[MyJobMag] '{term}' p{page}: {e}")
                break

            listings = soup.find_all('li', class_='job-list-li')
            if not listings:
                break

            added = 0
            for listing in listings:
                # Title
                title_el = listing.find('h2')
                title = _clean_text(title_el.get_text()) if title_el else ""

                # Link
                a_tag = listing.find('a')
                link = a_tag['href'] if a_tag and a_tag.has_attr('href') else ""
                url = BASE_URL + link if link and link.startswith('/') else link

                if not title or not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                # Description
                desc_el = listing.find('li', class_='job-desc')
                description = _clean_text(desc_el.get_text()) if desc_el else ""

                # Date
                date_el = listing.find('li', id='job-date')
                posted_raw = _clean_text(date_el.get_text()) if date_el else ""

                # Company & location – not directly in the card, so use defaults
                company = ""
                location = "Kenya"

                # Optional: try to extract company from the anchor text
                if a_tag and not company:
                    # Sometimes the anchor text includes company after "at"
                    at_match = a_tag.text.strip().split(" at ")
                    if len(at_match) > 1:
                        company = at_match[-1].strip()

                posted = normalize_date(posted_raw)
                if posted and posted < cutoff:
                    continue

                job = make_job(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=url,
                    source="MyJobMag",
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