"""
Fuzu Kenya — keyword-driven search.
"""
import time
from datetime import datetime, timedelta
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import SCRAPE_DELAY_SECONDS, MAX_JOBS_PER_SOURCE, SCRAPE_MAX_DAYS
from ._utils import make_job, normalize_date, pw_scrape

_FUZU_SEARCHES = [
    "data", "analyst", "python", "software", "engineer",
    "machine learning", "business intelligence", "developer",
]

_FUZU_JS = """
() => {
    const jobs = [];
    const seen = new Set();

    function add(title, company, location, url, dateRaw) {
        title = (title || '').trim().replace(/\\s+/g, ' ');
        url   = (url   || '').trim();
        if (!title || title.length < 4) return;
        const key = title.toLowerCase() + '|' + url;
        if (seen.has(key)) return;
        seen.add(key);
        jobs.push({ title, company:(company||'').trim(),
                    location:(location||'Kenya').trim(),
                    url, posted_raw:(dateRaw||'').trim() });
    }

    // Strategy 1: job cards
    const sels = [
        '[class*="JobCard"]','[class*="job-card"]','[class*="VacancyCard"]',
        '[class*="vacancy"]','article','li[class*="job"]','[class*="opportunity"]',
    ];
    for (const sel of sels) {
        document.querySelectorAll(sel).forEach(card => {
            const tEl = card.querySelector('h2,h3,h4,[class*="title" i]');
            const cEl = card.querySelector('[class*="company" i],[class*="org" i],[class*="employer" i]');
            const lEl = card.querySelector('[class*="location" i]');
            const dEl = card.querySelector('[class*="date" i],[class*="posted" i],time');
            const aEl = card.querySelector('a[href*="/job/"],a[href*="/vacancy/"]')
                        || card.querySelector('a[href]')
                        || (card.tagName==='A'?card:null);
            if (tEl && aEl) {
                add(tEl.textContent, cEl?.textContent, lEl?.textContent,
                    aEl.href, dEl?.textContent);
            }
        });
        if (jobs.length >= 5) break;
    }

    // Strategy 2: all job-links
    if (jobs.length < 3) {
        document.querySelectorAll('a[href*="/job/"],a[href*="/kenya/job/"],a[href*="/vacancy/"]').forEach(a => {
            const t = a.querySelector('h2,h3,h4,strong')?.textContent || a.textContent?.trim().slice(0,90);
            if (!t || t.length < 4) return;
            const par = a.closest('li,article,[class*="card" i]');
            const d   = par?.querySelector('[class*="date" i],time')?.textContent;
            add(t, par?.querySelector('[class*="company" i]')?.textContent, 'Kenya', a.href, d);
        });
    }

    return jobs.slice(0, 40);
}
"""


def scrape_fuzu(
    keywords:  Optional[List[str]] = None,
    max_days:  int = SCRAPE_MAX_DAYS,
    max_pages: int = 2,
) -> List[dict]:
    cutoff   = datetime.now() - timedelta(days=max_days)
    searches = keywords if keywords else _FUZU_SEARCHES
    all_jobs: List[dict] = []
    seen_urls: set = set()

    for term in searches:
        for page in range(1, max_pages + 1):
            q   = term.replace(" ", "+")
            url = f"https://fuzu.com/kenya/jobs?q={q}&page={page}"
            raw = pw_scrape(url, _FUZU_JS, wait_selector="a[href*='/job/'],main")
            if not raw:
                break

            added = 0
            for r in raw:
                job_url = r.get("url","")
                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                posted = normalize_date(r.get("posted_raw",""))
                if posted and posted < cutoff:
                    continue

                job = make_job(
                    title=r.get("title",""),
                    company=r.get("company",""),
                    location=r.get("location","Kenya"),
                    url=job_url,
                    source="Fuzu",
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