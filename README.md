# JobScout KE

Automated job hunting for Rose Wabere — data and analytics engineer based in Nairobi.

Scrapes Kenyan job boards daily, filters out irrelevant jobs, scores matches with Groq LLaMA, generates tailored resume and cover letter PDFs, sends Telegram alerts with one-tap approve/skip buttons, and tracks everything in SQLite with optional Aiven PostgreSQL cloud sync and Excel export.

---

## The problem it solves

Manually checking five job boards every morning, copy-pasting descriptions, rewriting your CV summary for each application, and keeping track of what you applied to — that is two hours of daily work that should not exist. JobScout automates the entire pipeline from discovery to document generation. You wake up, check your Telegram, tap Approve on the matches that interest you, download the tailored PDFs, and open the job URL. That is it.

---

## What is working right now

| Feature | Status |
|---------|--------|
| BrighterMonday scraper (Software & Data category) | Working — Playwright |
| Fuzu scraper (keyword search) | Working — Playwright |
| MyJobMag scraper (keyword search) | Working — requests/BS4 |
| CareerPoint Kenya scraper | Working — requests/BS4 |
| Remotive API (free, no key) | Working |
| Arbeitnow API (free, no key) | Working |
| Hard relevance filter (no construction, nursing, etc.) | Working |
| ATS scoring with Groq LLaMA-3.3-70b | Working |
| Tailored CV summary generation | Working |
| Full 3-paragraph cover letter | Working |
| Resume PDF (2 pages, all sections) | Working |
| Cover letter PDF (1 page, proper spacing) | Working |
| Telegram alerts with Approve/Skip buttons | Working |
| Telegram command bot (/scrape /status /export) | Working |
| WhatsApp custom bot webhook forward | Working |
| Aiven PostgreSQL mirror | Working (optional) |
| Excel export (3 sheets, colour-coded) | Working |
| SQLite local database | Working |
| Streamlit dashboard | Working |
| Background scheduler | Working |

---

## Quick start

```bash
# 1. Clone / copy the project
cd jobscout

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Chromium (once)
playwright install chromium

# 4. Configure
cp .env.example .env
# Edit .env with your keys

# 5. Run
streamlit run app.py

# In a second terminal — background scraper + Telegram bot
python scheduler.py
```

---

## Deploying so it never sleeps

- **Railway** — free tier, always-on, deploy in 5 minutes with a GitHub push
- **Render** — free tier with wake-on-request, or paid always-on
- **VPS** (Hetzner/DigitalOcean) — cheapest always-on option at ~$4/month
- **GitHub Actions** — free cron scraping every 6 hours (no server needed)

---

<!-- ## Project files

```
jobscout/
├── app.py                    Main Streamlit UI
├── scheduler.py              Background scraper + Telegram command bot
├── config.py                 All configuration, loaded from .env
├── database.py               SQLite + optional Aiven PostgreSQL
├── requirements.txt
├── .env.example
│
├── modules/
│   ├── scrapers/
│   │   ├── __init__.py       Orchestrator — run_scrapers()
│   │   ├── _utils.py         Shared helpers, relevance filter, Playwright runner
│   │   ├── brightermonday.py Software & Data category search
│   │   ├── fuzu.py           Keyword-driven Playwright scraper
│   │   ├── myjobmag.py       Keyword-driven requests/BS4 scraper
│   │   ├── careerpoint.py    Keyword-driven requests/BS4 scraper
│   │   ├── remotive.py       Free API scraper
│   │   └── arbeitnow.py      Free API scraper
│   │
│   ├── analyzer.py           Groq LLaMA ATS scoring + document generation prompts
│   ├── cv_parser.py          PDF text extraction (PyPDF2 + pdfminer fallback)
│   ├── generator.py          FPDF2 resume + cover letter PDF builder
│   ├── notifier.py           Telegram alerts + callback polling + WA webhook
│   └── excel_export.py       openpyxl Excel export with 3 formatted sheets
│
└── data/
    ├── jobscout.db           SQLite database (auto-created)
    ├── uploads/              Uploaded CV PDFs
    ├── output/               Generated resume and cover letter PDFs
    └── exports/              Excel exports
``` -->

# Workflow

## Analysing a job (3 minutes per job)

1. Open the **Tailor + Analyse** tab in the dashboard.
2. The jobs you approved are listed here with their full JD visible.
3. Click **Analyse with Groq LLaMA** on any job.
4. In about 10-15 seconds you get:
   - An honest ATS match score
   - Keywords from the JD that match your profile (green chips)
   - Skills the JD requires that you lack (red chips) — these are real gaps, not hallucinated ones
   - A tailored 4-sentence professional summary using the JD's own language
   - A full 3-paragraph cover letter addressed to the actual company
   - Three specific interview tips for this role
5. Read and edit the summary and cover letter if you want.
6. Click **Generate resume PDF** and **Generate cover letter PDF**.
7. Download both files.
8. Click **Mark as applied** once you have submitted.



## Score lifecycle

A job's `match_score` goes through two phases:

**Phase 1 — pre-filter score (0–80)**
Assigned by `_utils.relevance_score()` at scrape time. Based purely on how many of user's target role keywords appear in the job title and description. This is only a triage signal: it prevents clearly irrelevant jobs from cluttering the feed. It never exceeds 80 so the LLM always has room to adjust upward or downward.

**Phase 2 — ATS score (0–100)**
Assigned by `analyzer.analyse()` when the user clicks "Analyse with Groq." The LLM reads the full job description and compares it strictly against the user profile. Scoring rules are explicit in the prompt: skills in the CV that the JD does not mention do not increase the score. A 75% score means genuine fit. The LLM also returns matched keywords (from the JD), missing skills (JD requirements a user lacks), a tailored 4-sentence summary using exact JD language, STAR-format achievement bullets, a full 3-paragraph cover letter, and interview tips specific to the role.

# Database design

A single `jobs` table with a state machine status column. Hash column provides deduplication across scrape runs, the same job posted twice on BrighterMonday will not appear twice in the database. The  PostgreSQL mirror happens on every `insert_job()` and `update_job()` call using `ON CONFLICT DO NOTHING` for inserts, thus safe to run alongside the local SQLite without conflicts.

## Telegram as a control plane

The scheduler doubles as a Telegram bot. It polls `/getUpdates` with message type filtering every minute. Any message in the configured chat is treated as a command. Making it possible tp start or stop scraping, request a status report, or receive an Excel file, all from Telegram without touching the computer. Makes it possible to start the entire system from phone.

<!-- See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.
See [WORKFLOW.md](WORKFLOW.md) for step-by-step daily usage. -->
