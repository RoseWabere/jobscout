"""
database.py — JobScout KE
SQLite primary store + optional Aiven PostgreSQL cloud sync.

Design:
  - All reads/writes go to local SQLite (fast, offline-capable)
  - If DATABASE_URL is set, inserts are mirrored to Aiven PostgreSQL
  - Excel export is generated from the same SQLite data
"""
import sqlite3
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_PATH, DATABASE_URL

# ── PostgreSQL (optional) ─────────────────────────────────────────────
_pg_conn = None

def _pg():
    """Return a live psycopg2 connection, or None if not configured."""
    global _pg_conn
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        if _pg_conn is None or _pg_conn.closed:
            _pg_conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            _pg_conn.autocommit = True
            _ensure_pg_schema(_pg_conn)
        return _pg_conn
    except Exception as e:
        print(f"[db] Aiven connect error: {e}")
        return None


def _ensure_pg_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            hash TEXT UNIQUE,
            title TEXT, company TEXT, location TEXT,
            job_type TEXT, salary TEXT, source TEXT,
            url TEXT, description TEXT, posted_date TEXT,
            scraped_at TEXT, status TEXT DEFAULT 'new',
            match_score INT DEFAULT 0, keywords TEXT,
            missing_skills TEXT, tailored_cv TEXT,
            cover_letter TEXT, notification_sent INT DEFAULT 0,
            approved_at TEXT, applied_at TEXT,
            resume_pdf_path TEXT, cover_letter_pdf_path TEXT
        );
        """)


# ── SQLite DDL ────────────────────────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    hash                  TEXT    UNIQUE,
    title                 TEXT    NOT NULL,
    company               TEXT    DEFAULT '',
    location              TEXT    DEFAULT 'Kenya',
    job_type              TEXT    DEFAULT 'Full Time',
    salary                TEXT    DEFAULT 'Not stated',
    source                TEXT    NOT NULL,
    url                   TEXT    DEFAULT '',
    description           TEXT    DEFAULT '',
    posted_date           TEXT,
    scraped_at            TEXT    NOT NULL,
    status                TEXT    NOT NULL DEFAULT 'new',
    match_score           INTEGER DEFAULT 0,
    keywords              TEXT    DEFAULT '',
    missing_skills        TEXT    DEFAULT '',
    tailored_cv           TEXT    DEFAULT '',
    cover_letter          TEXT    DEFAULT '',
    resume_pdf_path       TEXT    DEFAULT '',
    cover_letter_pdf_path TEXT    DEFAULT '',
    notification_sent     INTEGER DEFAULT 0,
    approved_at           TEXT,
    applied_at            TEXT
);

CREATE TABLE IF NOT EXISTS cv_master (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT,
    raw_text    TEXT,
    skills      TEXT,
    contact     TEXT,
    sections    TEXT,
    uploaded_at TEXT
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT,
    source      TEXT,
    jobs_found  INTEGER,
    new_jobs    INTEGER,
    status      TEXT,
    message     TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def init_db():
    with _conn() as c:
        c.executescript(_DDL)


init_db()


# ── Helpers ───────────────────────────────────────────────────────────
def job_hash(title: str, company: str, source: str) -> str:
    raw = f"{title.lower().strip()}{company.lower().strip()}{source}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ── Jobs — write ──────────────────────────────────────────────────────
def insert_job(job: dict) -> bool:
    """Insert job into SQLite (and optionally Aiven). Returns True if new."""
    h = job_hash(job["title"], job.get("company", ""), job["source"])
    sql = """
        INSERT INTO jobs
            (hash,title,company,location,job_type,salary,source,url,
             description,posted_date,scraped_at,status,match_score,keywords)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    vals = (
        h, job["title"], job.get("company",""), job.get("location","Kenya"),
        job.get("job_type","Full Time"), job.get("salary","Not stated"),
        job["source"], job.get("url",""), job.get("description",""),
        job.get("posted_date", datetime.now().strftime("%Y-%m-%d")),
        datetime.now().isoformat(), "new",
        job.get("match_score", 0), job.get("keywords",""),
    )
    try:
        with _conn() as c:
            c.execute(sql, vals)
        # Mirror to Aiven
        pg = _pg()
        if pg:
            _pg_insert(pg, h, job)
        return True
    except sqlite3.IntegrityError:
        return False


def _pg_insert(conn, h: str, job: dict):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs
                    (hash,title,company,location,job_type,salary,source,url,
                     description,posted_date,scraped_at,status,match_score,keywords)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (hash) DO NOTHING
            """, (
                h, job["title"], job.get("company",""), job.get("location","Kenya"),
                job.get("job_type","Full Time"), job.get("salary","Not stated"),
                job["source"], job.get("url",""), job.get("description",""),
                job.get("posted_date",""), datetime.now().isoformat(), "new",
                job.get("match_score",0), job.get("keywords",""),
            ))
    except Exception as e:
        print(f"[db] Aiven insert error: {e}")


def update_job(job_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*kwargs.values(), job_id))
    # Mirror status changes to Aiven
    pg = _pg()
    if pg and ("status" in kwargs or "match_score" in kwargs):
        try:
            set_pg = ", ".join(f"{k}=%s" for k in kwargs)
            with pg.cursor() as cur:
                cur.execute(
                    f"UPDATE jobs SET {set_pg} WHERE hash=(SELECT hash FROM jobs WHERE id=%s LIMIT 1)",
                    (*kwargs.values(), job_id),
                )
        except Exception as e:
            print(f"[db] Aiven update error: {e}")


def update_status(job_id: int, status: str):
    ts = datetime.now().isoformat()
    extra = {}
    if status == "applied":
        extra["applied_at"] = ts
    elif status == "pending_approval":
        extra["approved_at"] = ts
    update_job(job_id, status=status, **extra)


# ── Jobs — read ───────────────────────────────────────────────────────
def get_jobs(status: Optional[str] = None, search: Optional[str] = None,
             min_score: int = 0, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM jobs"
    params: list = []
    where: list[str] = []
    if status and status != "all":
        where.append("status=?"); params.append(status)
    if search:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        params += [f"%{search}%"] * 3
    if min_score > 0:
        where.append("match_score >= ?"); params.append(min_score)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY scraped_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_job(job_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def get_stats() -> dict:
    with _conn() as c:
        total   = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        new_    = c.execute("SELECT COUNT(*) FROM jobs WHERE status='new'").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM jobs WHERE status='pending_approval'").fetchone()[0]
        applied = c.execute("SELECT COUNT(*) FROM jobs WHERE status='applied'").fetchone()[0]
        skipped = c.execute("SELECT COUNT(*) FROM jobs WHERE status='skipped'").fetchone()[0]
        today   = c.execute("SELECT COUNT(*) FROM jobs WHERE DATE(scraped_at)=DATE('now')").fetchone()[0]
        avg     = c.execute("SELECT AVG(match_score) FROM jobs WHERE match_score>0").fetchone()[0]
    return dict(total=total, new=new_, pending=pending, applied=applied,
                skipped=skipped, today=today, avg_score=round(avg or 0, 1))


# ── CV Master ─────────────────────────────────────────────────────────
def save_cv(filename: str, raw_text: str, skills: list, contact: dict, sections: dict) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO cv_master (filename,raw_text,skills,contact,sections,uploaded_at) VALUES (?,?,?,?,?,?)",
            (filename, raw_text, json.dumps(skills), json.dumps(contact),
             json.dumps(sections), datetime.now().isoformat()),
        )
        return cur.lastrowid


def get_latest_cv() -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM cv_master ORDER BY uploaded_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    d["skills"]   = json.loads(d.get("skills")   or "[]")
    d["contact"]  = json.loads(d.get("contact")  or "{}")
    d["sections"] = json.loads(d.get("sections") or "{}")
    return d


# ── Settings ──────────────────────────────────────────────────────────
def save_settings(d: dict):
    with _conn() as c:
        for k, v in d.items():
            c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, str(v)))


def load_settings() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT key,value FROM settings").fetchall()
    return {r[0]: r[1] for r in rows}


# ── Scrape Log ────────────────────────────────────────────────────────
def log_scrape(source: str, found: int, new: int, status: str, msg: str = ""):
    with _conn() as c:
        c.execute(
            "INSERT INTO scrape_log VALUES (NULL,?,?,?,?,?,?)",
            (datetime.now().isoformat(), source, found, new, status, msg),
        )


def get_scrape_log(limit: int = 60) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM scrape_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
