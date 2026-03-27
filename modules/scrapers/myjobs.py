# modules/scrapers/myjobs.py
"""
Scraper for myjobsinkenya.com
"""
import re
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
    "Accept-Language": "en-US,en;q=0.9",
}
BASE_URL = "https://www.myjobsinkenya.com"

# Date class patterns – avoid matching 'time' substring in job-type classes
_DATE_CLASSES = re.compile(r"\bdate\b|\bposted\b|\bago\b", re.I)

def _parse_card(card) -> dict:
    """Extract fields from a job card."""
    # Title
    title_el = card.find("h4")
    link = title_el.find("a", href=True) if title_el else card.find("a", href=True)
    title = link.get_text(strip=True) if link else ""
    if not title:
        return None
    url = link["href"] if link["href"].startswith("http") else BASE_URL + link["href"]

    # Company
    company_el = card.find("span", class_="company")
    company = ""
    if company_el:
        co_link = company_el.find("a")
        company = (co_link or company_el).get_text(strip=True)

    # Location
    loc_el = card.find("span", class_="office-location")
    location = "Kenya"
    if loc_el:
        loc_link = loc_el.find("a")
        location = (loc_link or loc_el).get_text(strip=True) or "Kenya"

    # Job type
    jt_el = card.find("span", class_=re.compile(r"job-type"))
    job_type = ""
    if jt_el:
        jt_link = jt_el.find("a")
        job_type = (jt_link or jt_el).get_text(strip=True)

    # Posted date – use exact class 'date' first
    date_el = (
        card.find("span", class_="date")
        or card.find("span", class_="posted")
        or card.find("span", class_=_DATE_CLASSES)
        or card.find("time")
        or card.find("small")
    )
    posted_raw = ""
    if date_el:
        text = date_el.get_text(strip=True)
        # Avoid picking up job type text (e.g., "Full Time")
        if not re.match(r"^(full|part|contract|intern|temp|remote)", text, re.I):
            posted_raw = text

    return {
        "title": title,
        "company": company,
        "location": location,
        "job_type": job_type,
        "url": url,
        "posted_raw": posted_raw,
    }


def scrape_myjobsinkenya(
    keywords: Optional[List[str]] = None,
    max_days: int = SCRAPE_MAX_DAYS,
    max_pages: int = 3,
) -> List[dict]:
    """Scrape myjobsinkenya.com with keyword search."""
    cutoff = datetime.now() - timedelta(days=max_days)
    searches = keywords if keywords else [
        "data analyst", "data engineer", "software engineer",
        "python developer", "business intelligence", "machine learning",
        "ICT", "systems analyst", "database administrator",
        "software developer", "analytics", "developer"
    ]
    all_jobs = []
    seen_urls = set()

    for term in searches:
        for page in range(1, max_pages + 1):
            params = {"q": term}
            if page > 1:
                params["page"] = page
            try:
                resp = requests.get(
                    f"{BASE_URL}/search",
                    params=params,
                    headers=HEADERS,
                    timeout=15,
                )
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                print(f"[MyJobsInKenya] '{term}' p{page}: {e}")
                break

            cards = soup.find_all("div", class_="job-list")
            if not cards:
                break

            added = 0
            for card in cards:
                raw = _parse_card(card)
                if not raw or raw["url"] in seen_urls:
                    continue
                seen_urls.add(raw["url"])

                posted = normalize_date(raw["posted_raw"])
                if posted and posted < cutoff:
                    continue

                job = make_job(
                    title=raw["title"],
                    company=raw["company"],
                    location=raw["location"],
                    url=raw["url"],
                    job_type=raw.get("job_type", ""),
                    source="MyJobsInKenya",
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