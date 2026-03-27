"""
modules/scrapers.py — JobScout KE
Playwright-based scrapers for Kenyan job boards.

WHY PLAYWRIGHT: BrighterMonday, Fuzu, and similar boards use React/Next.js.
Requests + BeautifulSoup only see the raw JS bundle — no job data.
Playwright renders the full DOM in a real Chromium instance.

Strategy: JS evaluation inside the page context is more resilient than
Python-side CSS selectors, because React class names change on every build.
"""
import re
import time
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import MAX_JOBS_PER_SOURCE, SCRAPE_DELAY_SECONDS

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PW_AVAILABLE = True
except ImportError:
    PW_AVAILABLE = False
    print("[scrapers] playwright not installed — JS-heavy sites will be limited")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

KEYWORDS = [
    "data engineer", "analytics engineer", "data analyst", "data scientist",
    "python developer", "sql developer", "etl", "data pipeline", "power bi",
    "machine learning", "ai engineer", "backend developer", "software engineer",
    "business intelligence", "bi analyst", "llm", "automation engineer",
    "systems analyst", "database administrator", "cloud engineer", "devops",
    "django", "fastapi", "postgresql", "mongodb",
]


# ══════════════════════════════════════════════════════════════════════
#  SHARED UTILITIES
# ══════════════════════════════════════════════════════════════════════

def keyword_score(text: str) -> int:
    text_l = text.lower()
    hits = sum(1 for k in KEYWORDS if k in text_l)
    return min(100, hits * 8)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _make_job(title, company="", location="Kenya", description="",
              url="", source="", salary="Not stated", job_type="Full Time",
              posted_date="") -> dict:
    title = _clean(title)
    company = _clean(company)
    if not title or len(title) < 4:
        return {}
    skip_phrases = ["browse", "view all", "see more", "load more", "jobs near",
                    "find jobs", "search jobs", "post a job", "sign in", "login"]
    if any(p in title.lower() for p in skip_phrases):
        return {}
    score = keyword_score(f"{title} {description}")
    return {
        "title": title[:120],
        "company": company[:100],
        "location": location or "Kenya",
        "description": description[:3000],
        "url": url,
        "source": source,
        "salary": salary or "Not stated",
        "job_type": job_type or "Full Time",
        "posted_date": posted_date or datetime.now().strftime("%Y-%m-%d"),
        "match_score": score,
        "keywords": "",
    }


# ══════════════════════════════════════════════════════════════════════
#  PLAYWRIGHT ENGINE
# ══════════════════════════════════════════════════════════════════════

def _pw_scrape(url: str, js_extractor: str, wait_selector: str = "",
               extra_wait_ms: int = 2500) -> list[dict]:
    """
    Core Playwright runner. Launches headless Chromium, navigates to url,
    waits for content, runs js_extractor (a JS function body string),
    returns list of raw dicts.
    """
    if not PW_AVAILABLE:
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ],
        )
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        page = ctx.new_page()
        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        results = []
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            # Wait for specific element if given
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=8000)
                except PWTimeout:
                    pass
            # Always wait extra time for React to hydrate
            page.wait_for_timeout(extra_wait_ms)
            results = page.evaluate(js_extractor)
        except PWTimeout:
            print(f"[Playwright] Timeout: {url}")
        except Exception as e:
            print(f"[Playwright] Error on {url}: {e}")
        finally:
            browser.close()

    return results or []


# ══════════════════════════════════════════════════════════════════════
#  BRIGHTERMONEY KENYA
# ══════════════════════════════════════════════════════════════════════

_BM_JS = """
() => {
    const jobs = [];
    const seen = new Set();

    // Strategy 1: article cards (React components render into articles)
    document.querySelectorAll('article').forEach(article => {
        const titleEl = article.querySelector('h2, h3, h4, [class*="title" i], [class*="heading" i]');
        const companyEl = article.querySelector('[class*="company" i], [class*="employer" i], [class*="org" i]');
        const locationEl = article.querySelector('[class*="location" i], [class*="place" i]');
        const salaryEl = article.querySelector('[class*="salary" i], [class*="pay" i]');
        const linkEl = article.querySelector('a[href]') || (article.tagName === 'A' ? article : null);

        const title = titleEl?.textContent?.trim();
        const company = companyEl?.textContent?.trim() || '';
        const href = linkEl?.href || '';
        const key = (title||'') + href;

        if (title && title.length > 3 && !seen.has(key)) {
            seen.add(key);
            jobs.push({
                title,
                company,
                location: locationEl?.textContent?.trim() || 'Kenya',
                salary: salaryEl?.textContent?.trim() || '',
                url: href,
            });
        }
    });

    // Strategy 2: any anchor that looks like a job listing
    if (jobs.length < 3) {
        document.querySelectorAll('a[href*="/jobs/"]').forEach(a => {
            const title = (
                a.querySelector('h2, h3, h4, strong, b')?.textContent?.trim() ||
                a.getAttribute('title') ||
                a.textContent?.trim().split('\\n')[0]
            );
            const href = a.href;
            const key = (title||'') + href;
            if (title && title.length > 5 && !seen.has(key)) {
                seen.add(key);
                const parent = a.closest('[class*="card" i], [class*="item" i], [class*="listing" i], li, article');
                const company = parent?.querySelector('[class*="company" i], [class*="employer" i]')?.textContent?.trim() || '';
                jobs.push({ title, company, location: 'Kenya', salary: '', url: href });
            }
        });
    }

    return jobs.slice(0, 30);
}
"""


def scrape_brightermoney(max_pages: int = 3) -> list[dict]:
    all_jobs = []
    for page in range(1, max_pages + 1):
        url = f"https://www.brightermonday.co.ke/jobs?page={page}"
        raw = _pw_scrape(url, _BM_JS, wait_selector="article, main, [class*='job' i]")
        if not raw:
            break
        for r in raw:
            j = _make_job(
                title=r.get("title", ""),
                company=r.get("company", ""),
                location=r.get("location", "Kenya"),
                url=r.get("url", ""),
                salary=r.get("salary", ""),
                source="BrighterMonday",
            )
            if j:
                all_jobs.append(j)
        time.sleep(SCRAPE_DELAY_SECONDS)
    return all_jobs[:MAX_JOBS_PER_SOURCE]


# ══════════════════════════════════════════════════════════════════════
#  FUZU KENYA
# ══════════════════════════════════════════════════════════════════════

_FUZU_JS = """
() => {
    const jobs = [];
    const seen = new Set();

    // Fuzu uses React, job cards appear inside main content
    const selectors = [
        '[class*="JobCard"]', '[class*="job-card"]', '[class*="vacancy"]',
        'article', 'li[class*="job"]',
    ];

    for (const sel of selectors) {
        document.querySelectorAll(sel).forEach(card => {
            const titleEl = card.querySelector('h2, h3, h4, [class*="title" i], a[href*="/job/"]');
            const companyEl = card.querySelector('[class*="company" i], [class*="org" i], [class*="employer" i]');
            const linkEl = card.querySelector('a[href*="/kenya/job/"], a[href*="/job/"]') || card.closest('a');
            const title = titleEl?.textContent?.trim();
            const href = linkEl?.href || '';
            const key = (title||'') + href;
            if (title && title.length > 3 && !seen.has(key)) {
                seen.add(key);
                jobs.push({
                    title,
                    company: companyEl?.textContent?.trim() || '',
                    url: href,
                    location: 'Kenya',
                });
            }
        });
        if (jobs.length >= 5) break;
    }

    // Fallback: any job links
    if (jobs.length < 3) {
        document.querySelectorAll('a[href*="/kenya/job/"], a[href*="/job/"]').forEach(a => {
            const title = a.querySelector('h2,h3,h4,strong')?.textContent?.trim()
                          || a.textContent?.trim().slice(0,80);
            const key = title + a.href;
            if (title && title.length > 5 && !seen.has(key)) {
                seen.add(key);
                jobs.push({ title, company: '', url: a.href, location: 'Kenya' });
            }
        });
    }

    return jobs.slice(0, 30);
}
"""


def scrape_fuzu(max_pages: int = 3) -> list[dict]:
    all_jobs = []
    for page in range(1, max_pages + 1):
        url = f"https://fuzu.com/kenya/jobs?page={page}"
        raw = _pw_scrape(url, _FUZU_JS, wait_selector="a[href*='/job/'], main")
        if not raw:
            break
        for r in raw:
            j = _make_job(
                title=r.get("title", ""),
                company=r.get("company", ""),
                location="Kenya",
                url=r.get("url", ""),
                source="Fuzu",
            )
            if j:
                all_jobs.append(j)
        time.sleep(SCRAPE_DELAY_SECONDS)
    return all_jobs[:MAX_JOBS_PER_SOURCE]


# ══════════════════════════════════════════════════════════════════════
#  MYJOBMAG KENYA — Traditional HTML, requests works
# ══════════════════════════════════════════════════════════════════════

def scrape_myjobmag(max_pages: int = 3) -> list[dict]:
    all_jobs = []
    for page in range(1, max_pages + 1):
        try:
            url = f"https://www.myjobmag.co.ke/jobs?page={page}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "lxml")

            # MyJobMag uses standard HTML lists
            for card in soup.select(
                "div.job-list-item, li.job-item, article.job, "
                "div[class*='job-list'], div[class*='job-item'], "
                "li[class*='job']"
            ):
                title_el   = (card.select_one("h2 a, h3 a, a.job-title, [class*='title'] a, h2, h3")
                               or card.select_one("a"))
                company_el = card.select_one("[class*='company'], [class*='employer'], .org-name, b")
                if not title_el:
                    continue
                title   = _clean(title_el.get_text())
                company = _clean(company_el.get_text()) if company_el else ""
                href    = title_el.get("href", "") or title_el.find("a", href=True)
                if isinstance(href, str) and href.startswith("/"):
                    href = "https://www.myjobmag.co.ke" + href

                j = _make_job(title=title, company=company, url=str(href) if href else "",
                               source="MyJobMag")
                if j:
                    all_jobs.append(j)

        except Exception as e:
            print(f"[MyJobMag] page {page}: {e}")
        time.sleep(SCRAPE_DELAY_SECONDS)

    return all_jobs[:MAX_JOBS_PER_SOURCE]


# ══════════════════════════════════════════════════════════════════════
#  CAREER POINT KENYA
# ══════════════════════════════════════════════════════════════════════

def scrape_careerpointkenya(max_pages: int = 2) -> list[dict]:
    all_jobs = []
    for page in range(1, max_pages + 1):
        try:
            url = f"https://careerpointkenya.co.ke/jobs/?pg={page}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "lxml")

            for card in soup.select("div.job-listing, article.job, li.job-item, div[class*='job']"):
                title_el   = card.select_one("h2 a, h3 a, a[href*='/job/'], [class*='title'] a")
                company_el = card.select_one("[class*='company'], [class*='employer']")
                if not title_el:
                    continue
                title   = _clean(title_el.get_text())
                company = _clean(company_el.get_text()) if company_el else ""
                href    = title_el.get("href", "")
                if href.startswith("/"):
                    href = "https://careerpointkenya.co.ke" + href

                j = _make_job(title=title, company=company, url=href, source="CareerPoint KE")
                if j:
                    all_jobs.append(j)

        except Exception as e:
            print(f"[CareerPoint] page {page}: {e}")
        time.sleep(SCRAPE_DELAY_SECONDS)

    return all_jobs[:MAX_JOBS_PER_SOURCE]


# ══════════════════════════════════════════════════════════════════════
#  REMOTIVE — Free API, no key, remote tech jobs
# ══════════════════════════════════════════════════════════════════════

def scrape_remotive(keywords: str = "data engineer") -> list[dict]:
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": keywords, "limit": MAX_JOBS_PER_SOURCE},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[Remotive] {e}")
        return []

    jobs = []
    import html as _html
    for item in data.get("jobs", []):
        desc = re.sub(r"<[^>]+>", " ", item.get("description", ""))
        desc = _html.unescape(desc).strip()
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", desc)
        j = _make_job(
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            location=item.get("candidate_required_location", "Remote"),
            description=desc[:2000],
            url=item.get("url", ""),
            source="Remotive",
        )
        if j:
            jobs.append(j)

    return jobs[:MAX_JOBS_PER_SOURCE]


# ══════════════════════════════════════════════════════════════════════
#  ARBEITNOW — Free API, no key
# ══════════════════════════════════════════════════════════════════════

def scrape_arbeitnow(keywords: str = "") -> list[dict]:
    try:
        params = {}
        if keywords:
            params["search"] = keywords
        r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                         params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[Arbeitnow] {e}")
        return []

    import html as _html
    jobs = []
    for item in data.get("data", [])[:MAX_JOBS_PER_SOURCE]:
        desc = re.sub(r"<[^>]+>", " ", item.get("description", ""))
        desc = _html.unescape(desc).strip()
        j = _make_job(
            title=item.get("title", ""),
            company=item.get("company_name", ""),
            location=item.get("location", "Remote"),
            description=desc[:2000],
            url=item.get("url", ""),
            source="Arbeitnow",
        )
        if j:
            jobs.append(j)

    return jobs


# ══════════════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════

SOURCE_MAP = {
    "BrighterMonday": scrape_brightermoney,
    "Fuzu":           scrape_fuzu,
    "MyJobMag":       scrape_myjobmag,
    "CareerPoint KE": scrape_careerpointkenya,
    "Remotive":       scrape_remotive,
    "Arbeitnow":      scrape_arbeitnow,
}


def run_scrapers(
    sources: list[str] | None = None,
    progress_fn=None,
) -> dict:
    """
    Run selected scrapers, insert new jobs into DB, return summary dict.
    progress_fn(msg: str) is called with status updates.
    """
    from database import insert_job, log_scrape

    if sources is None:
        sources = list(SOURCE_MAP.keys())

    summary = {}
    total_new = 0

    for name in sources:
        fn = SOURCE_MAP.get(name)
        if not fn:
            continue
        if progress_fn:
            progress_fn(f"Scanning {name}...")
        try:
            jobs = fn()
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
