"""
modules/scrapers/_utils.py
Shared utilities. Relevance filter, make_job, normalize_date, pw_scrape.

FILTER DESIGN (learned from testing):
  The previous version was too strict — it dropped "ICT Manager", "Systems
  Administrator", "Cloud Architect", "Tableau Developer", etc.

  New approach: two-pass.
  Pass 1 — hard exclude titles that are unmistakably wrong (nursing, driving,
    construction, accountant, sales rep...).
  Pass 2 — require at least one TECH keyword in the title OR description.
    "tech keyword" is broadly defined: data, analyst, engineer, developer,
    ict, systems, cloud, database, bi, ml, ai, software, digital, gis, mis...

  Result: almost every real tech/data job passes; irrelevant jobs don't.
  The LLM scores quality — the filter only removes obvious garbage.
"""
import re
from datetime import datetime, timedelta
from typing import Optional

HARD_EXCLUDE = [
    "construction", "civil engineer", "structural engineer", "quantity surveyor",
    "site engineer", "site manager", "building engineer",
    "interior architect", "landscape architect",
    "interior design", "nurse", "nursing", "clinical officer", "midwife",
    "pharmacist", "doctor", "physician", "surgeon", "radiographer",
    "lab technician", "medical officer", "health worker",
    "teacher", "lecturer", "tutor", "school principal",
    "driver", "chauffeur", "dispatch rider",
    "chef", "cook", "waiter", "waitress", "housekeeper", "cleaner",
    "janitor", "security guard",
    "accountant", "auditor", "teller", "cashier", "bookkeeper", "tax ",
    "lawyer", "advocate", "legal officer", "paralegal",
    "plumber", "electrician", "mechanic",
    "community health", "community development",
    "hr manager", "human resource manager",
    "sales executive", "sales representative", "sales manager",
    "business development manager", "account manager", "field sales",
    "agronomist", "farm manager", "veterinarian",
]

# Any of these in the title → job is included
TECH_TITLE_KW = [
    "data", "analyst", "analytics", "engineer", "developer", "programmer",
    "ict", "information technology", "information system", "mis ",
    "systems", "network", "infrastructure", "devops", "cloud",
    "database", "dba", "sql", " bi ", "bi ", "power bi", "tableau", "looker",
    "machine learning", "artificial intelligence", " ai ", "ml ",
    "nlp", "deep learning", "software", "backend", "frontend",
    "full stack", "fullstack", "mobile app", "web developer",
    "python", "java ", "react", "angular", "node",
    "product manager", "product owner", "scrum", "agile",
    "digital", "gis", "statistician", "quantitative", "research analyst",
    "reporting analyst", "technical", "technology",
    "cybersecurity", "cyber security", "information security",
    "automation", "robotic", "architect", "solutions",
    "it officer", "ict officer", "officer it",
]

# If title has no tech kw, check description for these
TECH_DESC_KW = [
    "python", "sql", "power bi", "tableau", "excel analysis",
    "data analysis", "data engineering", "etl", "machine learning",
    "software development", "api", "database", "cloud", "aws", "gcp",
    "azure", "git", "programming", "analytics", "reporting",
    "data visualization", "statistical analysis", "modelling",
    "pipeline", "r programming", "javascript", "react",
]

NOISE = [
    "browse", "view all", "see more", "load more", "jobs near",
    "find jobs", "search jobs", "post a job", "sign in", "login",
    "register", "create account", "subscribe", "newsletter",
]

TARGET_ROLES = [
    "data engineer", "analytics engineer", "data analyst",
    "data scientist", "python developer", "machine learning",
    "ml engineer", "ai engineer", "business intelligence",
    "bi analyst", "bi developer", "etl developer", "etl engineer",
    "data pipeline", "power bi", "backend developer",
    "backend engineer", "software engineer", "software developer",
    "devops engineer", "cloud engineer", "database administrator",
    "dba", "automation engineer", "systems analyst", "data architect",
    "analytics", "reporting analyst", "full stack", "fullstack",
    "information systems", "it analyst", "ict", "systems administrator",
    "solutions architect", "cloud architect", "data platform",
    "gis analyst", "mis officer", "statistician",
]


def is_relevant(title: str, description: str = "") -> bool:
    tl = title.lower().strip()
    dl = description.lower()[:600]

    if any(p in tl for p in NOISE):
        return False
    if len(tl) < 4:
        return False

    for ex in HARD_EXCLUDE:
        if ex in tl:
            return False

    # "analyst" alone passes, but not in a purely financial/legal context
    _FINANCE_ANALYST = [
        "credit analyst", "financial analyst", "tax analyst",
        "loans analyst", "budget analyst", "compliance analyst",
        "actuarial analyst", "investment analyst", "equity analyst",
        "legal analyst", "grants analyst", "procurement analyst",
        "supply chain analyst", "logistics analyst",
    ]
    if "analyst" in tl and not any(
        kw in tl for kw in ["data", "ict", "business intelligence", "bi ",
                            "system", "research", "digital", "reporting",
                            "product", "marketing analyst", "insight"]
    ):
        if any(ex in tl for ex in _FINANCE_ANALYST):
            return False

    # check tech keywords in title
    for kw in TECH_TITLE_KW:
        if kw in tl:
            return True

    # fallback: check description
    for kw in TECH_DESC_KW:
        if kw in dl:
            return True

    return False


def relevance_score(title: str, description: str = "") -> int:
    combined = (title + " " + description).lower()
    hits = sum(1 for r in TARGET_ROLES if r in combined)
    return min(75, hits * 15)


def make_job(
    title:       str,
    company:     str = "",
    location:    str = "Kenya",
    description: str = "",
    url:         str = "",
    source:      str = "",
    salary:      str = "Not stated",
    job_type:    str = "Full Time",
    posted_date: str = "",
) -> Optional[dict]:
    title = re.sub(r"\s+", " ", title or "").strip()
    if not title or len(title) < 4:
        return None
    if not is_relevant(title, description):
        return None
    return {
        "title":       title[:120],
        "company":     (company or "").strip()[:100],
        "location":    location or "Kenya",
        "description": (description or "").strip()[:4000],
        "url":         url or "",
        "source":      source,
        "salary":      salary or "Not stated",
        "job_type":    job_type or "Full Time",
        "posted_date": posted_date or datetime.now().strftime("%Y-%m-%d"),
        "match_score": relevance_score(title, description),
        "keywords":    "",
    }


def normalize_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    s = date_str.lower().strip()
    for p in ["posted:", "published:", "date:", "posted on", "added:"]:
        s = s.removeprefix(p).strip()
    now = datetime.now()
    m = re.search(r"(\d+)\s+days?\s+ago", s)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.search(r"(\d+)\s+hours?\s+ago", s)
    if m:
        return now
    m = re.search(r"(\d+)\s+weeks?\s+ago", s)
    if m:
        return now - timedelta(weeks=int(m.group(1)))
    if "yesterday" in s:
        return now - timedelta(days=1)
    if "today" in s or "just now" in s or "moments" in s:
        return now
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except Exception:
            pass
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
                "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    return None


def pw_scrape(
    url:           str,
    js_extractor:  str,
    wait_selector: str = "",
    extra_wait_ms: int = 3000,
) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[scrapers] playwright not installed — run: playwright install chromium")
        return []

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()
        page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}",
            lambda r: r.abort(),
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    pass
            page.wait_for_timeout(extra_wait_ms)
            results = page.evaluate(js_extractor)
            if results is None:
                results = []
        except Exception as e:
            print(f"[playwright] {url[:70]}: {e}")
        finally:
            browser.close()

    return results or []