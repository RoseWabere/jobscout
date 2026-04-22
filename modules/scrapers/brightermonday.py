"""
BrighterMonday Kenya — Playwright scraper.

Strategy: navigate to ICT/Technology category pages AND keyword search URLs.
The JS extractor uses multiple selector strategies and falls back to
walking ALL anchor tags that look like job links.
"""
import time
from datetime import datetime, timedelta
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import SCRAPE_DELAY_SECONDS, MAX_JOBS_PER_SOURCE, SCRAPE_MAX_DAYS
from ._utils import make_job, normalize_date, pw_scrape

# BrighterMonday category + search URLs for Software/Data
_BM_URLS = [
    "https://www.brightermonday.co.ke/listings/it-software",
    "https://www.brightermonday.co.ke/jobs/software-data",
    "https://www.brightermonday.co.ke/listings/ict-telecommunications",
    "https://www.brightermonday.co.ke/jobs?q=data+engineer",
    "https://www.brightermonday.co.ke/jobs?q=data+analyst",
    "https://www.brightermonday.co.ke/jobs?q=software+engineer",
    "https://www.brightermonday.co.ke/jobs?q=python+developer",
    "https://www.brightermonday.co.ke/jobs?q=business+intelligence",
]

# Robust JS — tries multiple strategies, returns whatever it finds
_BM_JS = """
() => {
    const jobs = [];
    const seen = new Set();

    function addJob(title, company, location, salary, url, dateRaw) {
        title = (title || '').trim().replace(/\\s+/g, ' ');
        url   = (url   || '').trim();
        if (!title || title.length < 4) return;
        const key = title.toLowerCase() + '|' + url;
        if (seen.has(key)) return;
        seen.add(key);
        jobs.push({ title, company: (company||'').trim(),
                    location: (location||'Kenya').trim(),
                    salary: (salary||'').trim(),
                    url, posted_raw: (dateRaw||'').trim() });
    }

    // ── Strategy 1: article / li / div cards ──────────────────────
    const cardSels = [
        'article[class*="job"]', 'article[class*="listing"]',
        'article[class*="card"]', 'article',
        'li[class*="job"]', 'li[class*="listing"]',
        'div[class*="job-card"]', 'div[class*="job-item"]',
        'div[class*="listing-card"]', 'div[class*="vacancy"]',
    ];
    for (const sel of cardSels) {
        document.querySelectorAll(sel).forEach(card => {
            const titleEl  = card.querySelector('h2,h3,h4,[class*="title" i]');
            const compEl   = card.querySelector('[class*="company" i],[class*="employer" i],[class*="org" i]');
            const locEl    = card.querySelector('[class*="location" i],[class*="place" i]');
            const salEl    = card.querySelector('[class*="salary" i],[class*="pay" i]');
            const dateEl   = card.querySelector('[class*="date" i],[class*="posted" i],[class*="ago" i],time');
            const linkEl   = card.querySelector('a[href]') || (card.tagName==='A'?card:null);
            if (titleEl && linkEl) {
                addJob(titleEl.textContent, compEl?.textContent,
                       locEl?.textContent, salEl?.textContent,
                       linkEl.href, dateEl?.textContent);
            }
        });
        if (jobs.length >= 5) break;
    }

    // ── Strategy 2: walk ALL job-looking anchor tags ───────────────
    if (jobs.length < 3) {
        const linkPatterns = ['/jobs/', '/listings/', '/job/', '/vacancy/', '/career/'];
        document.querySelectorAll('a[href]').forEach(a => {
            const href = a.href || '';
            if (!linkPatterns.some(p => href.includes(p))) return;
            if (href.includes('?') && !href.includes('/jobs/')) return;

            // Get title from: aria-label, title attr, first heading, first strong, or link text
            const title = a.getAttribute('aria-label') ||
                          a.getAttribute('title') ||
                          a.querySelector('h2,h3,h4,strong,b')?.textContent ||
                          a.textContent?.split('\\n')[0];
            if (!title || title.trim().length < 4) return;

            const parent = a.closest('li,article,div[class],[class*="card" i],[class*="item" i]');
            const comp   = parent?.querySelector('[class*="company" i],[class*="employer" i]')?.textContent;
            const date   = parent?.querySelector('[class*="date" i],[class*="ago" i],time')?.textContent;
            addJob(title, comp, 'Kenya', '', href, date);
        });
    }

    return jobs.slice(0, 40);
}
"""


def scrape_brightermonday(
    keywords:  Optional[List[str]] = None,
    max_days:  int = SCRAPE_MAX_DAYS,
    max_pages: int = 2,
) -> List[dict]:
    cutoff    = datetime.now() - timedelta(days=max_days)
    all_jobs: List[dict] = []
    seen_urls: set = set()

    for base_url in _BM_URLS:
        for page in range(1, max_pages + 1):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 1 else f"{base_url}{sep}page={page}"
            raw = pw_scrape(url, _BM_JS, wait_selector="article,main,ul")
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
                    salary=r.get("salary",""),
                    source="BrighterMonday",
                    posted_date=posted.strftime("%Y-%m-%d") if posted else "",
                )
                if job:
                    all_jobs.append(job)
                    added += 1

            time.sleep(SCRAPE_DELAY_SECONDS)
            if not added:  # no new results on this page
                break

        if len(all_jobs) >= MAX_JOBS_PER_SOURCE:
            break

    return all_jobs[:MAX_JOBS_PER_SOURCE]