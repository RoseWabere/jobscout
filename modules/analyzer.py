"""
modules/analyzer.py — JobScout KE
ATS analysis using Groq LLaMA-3.3-70b.

FIXES vs old version:
  1. Score is based ONLY on JD requirements vs candidate — CV skills not
     in the JD never boost the score.
  2. Missing keywords are taken from the JD, not CV.
  3. Cover letter is 3 full paragraphs, professional and specific.
  4. Tailored bullets are STAR-format, quantified where possible.
  5. company/title placeholders are never left unfilled.
  6. Falls back gracefully to keyword overlap when Groq is down.
"""
import json
import re
import requests
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import GROQ_API_KEY, GROQ_MODEL, GROQ_URL, YOUR_NAME, YOUR_EMAIL, YOUR_PHONE

import database as db

# Rose's master profile — used by the LLM as context
ROSE_PROFILE = """
CANDIDATE: Rose Wabere
Contact: rosewabere7@gmail.com | +254 708 486 104 | Nairobi, Kenya
LinkedIn: linkedin.com/in/rosewabere | GitHub: github.com/Rozieroz

TITLE: Data and Analytics Engineer

CORE SKILLS:
  Languages & Query: Python, SQL, PySpark, DAX, Power Query, Bash
  Pipelines & Orchestration: Apache Airflow, dbt, ETL/ELT, Docker
  Visualisation: Power BI (Desktop & Cloud), Streamlit, Grafana
  ML / AI: Scikit-learn, XGBoost, TensorFlow, LangChain, RAG, Weaviate, Groq LLM APIs
  Databases: PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Neon.tech
  Cloud & DevOps: GCP, AWS, Azure, Git, GitHub Actions, Vercel, Railway
  APIs & Integration: FastAPI, REST APIs, M-Pesa/Daraja, AfricasTalking, WhatsApp Business API
  Office: Power Apps, Power Automate, Excel (advanced), Jira

EXPERIENCE:
  Data Science & Data Engineering Associate — Data Science East Africa (Jan 2025–Present)
    • Designed and delivered production ETL pipelines serving 5+ client datasets monthly
    • Built Power BI dashboards cutting reporting time by 40% for DSEA clients
    • Engineered ML datasets improving model accuracy across client prediction tasks
    • Stack: Python, SQL, Power BI, Apache Airflow, PostgreSQL

  Freelance AI Trainer, Annotator & Analyst — Remote (2021–Present)
    • RLHF data annotation for LLM training at scale for international AI companies
    • Evaluated model outputs for factual accuracy, safety, and instruction-following
    • Delivered 1,000+ annotated samples per project with <2% error rate

  Case File Analyst Intern — Kamukunji Police Station (Oct 2024–Jan 2025)
    • Digitised 2,000+ criminal case records into structured database
    • Built Excel-based tracking system reducing case retrieval time by 60%

  Inventory & Customer Research Analyst — Jumia Kenya / Jamboshop / Jiji (2023–2025)
    • Pricing analytics across 10,000+ SKUs; identified 15% margin improvement opportunities
    • Market research reports influencing category strategy for e-commerce clients

  Emergency Response Data Intern — NDOC (Mar–Jun 2021)
    • Real-time emergency data tracking feeding national situational reports

  Credit Analyst Intern — Taifa SACCO (May–Jul 2019)
    • Loan portfolio analysis supporting KES 50M+ in credit decisions

PROJECTS (deployed and live):
  1. Kipaji Chetu — Adaptive AI Learning: FastAPI, PostgreSQL, Groq, Edge-TTS, Whisper
  2. Safari Scouts — Kenya Travel RAG: safari-scouts.vercel.app | LangChain, Weaviate, 500+ docs
  3. Nairobi House Price Predictor: nairobi-house-price-prediction.streamlit.app | XGBoost, MAE 15.2M KSh
  4. Kijani Care 360: kijanicare-360.vercel.app | Geospatial ETL, FastAPI, LangChain, Docker
  5. Africa Energy Data Pipeline: 54 countries, PySpark, 2 academic publications
  6. Earthquake Data Pipeline: Airflow + Grafana real-time PostgreSQL ingestion
  7. Kenya Food Price Tracker: PySpark time-series forecasting, inflation analysis
  8. Market Research AI Agent: LangChain, 1,000+ docs, 60% research time reduction

EDUCATION:
  B.A. Security Studies & Criminology — Mount Kenya University
  Diploma Criminology — University of Nairobi
  Diploma Microfinance — Co-operative University of Kenya

CERTIFICATIONS:
  Data Analytics / Data Science / AI — LuxDevHQ
  Software Development — Women Techsters
  Cybersecurity Fundamentals — Women Techsters
  Green Digital Skills — INCO Academy
"""

_SYSTEM = """You are a senior ATS specialist and Kenyan career coach with 15 years of experience
placing data and tech candidates at top Kenyan and international firms.

You MUST return ONLY valid JSON — no markdown fences, no preamble, no trailing text.
Every string field must be complete — never leave placeholders like [Company] or [Role].
Score based STRICTLY on how well the candidate matches the JD requirements.
Do not inflate the score because the candidate has skills the JD does not require."""

_PROMPT = """=== JOB DESCRIPTION ===
Title:   {title}
Company: {company}
Source:  {source}
URL:     {url}

Full description:
{description}

=== CANDIDATE ===
{profile}

{cv_extra}

=== YOUR TASK ===
Analyse the match between this candidate and this specific job.

Rules for scoring:
- match_score is 0-100 and reflects ONLY skills/experience in the JD that the candidate has
- If the JD requires React and the candidate has no React: gap
- If the candidate has PySpark but the JD does not mention it: do NOT add to score
- Be honest. A 75% score means the candidate is a genuinely strong fit.

Rules for text output:
- Every field must be a complete, polished sentence/paragraph
- Never use placeholders. The company name is "{company}". Use it.
- The job title is "{title}". Use it.
- Cover letter must be 3 full paragraphs, warm and specific, ~280-320 words total
- Bullets must follow STAR format and include numbers where Rose's profile has them

Return this exact JSON (no other text):
{{
  "match_score": <int 0-100>,
  "rationale": "<2 honest sentences explaining the score>",
  "matched_keywords": ["keyword from JD that Rose has", ...],
  "missing_skills": ["skill the JD requires that Rose lacks", ...],
  "strengths": ["specific strength relevant to this JD", "...", "..."],
  "gaps": ["honest gap relevant to this JD", ...],
  "tailored_cv_summary": "<4-5 sentences. First sentence names the role at {company}. Uses exact language from the JD. Includes 2-3 numbers from Rose's experience.>",
  "tailored_bullets": [
    "<STAR bullet 1 — most relevant to this JD>",
    "<STAR bullet 2>",
    "<STAR bullet 3>",
    "<STAR bullet 4>"
  ],
  "cover_letter": "<PARAGRAPH 1 (80-100 words): Why this specific role at {company} excites Rose — mention something specific about the company or role from the JD.>\\n\\n<PARAGRAPH 2 (120-140 words): 2 specific achievements from Rose's background that directly address the JD requirements. Include numbers. Name the project or employer.>\\n\\n<PARAGRAPH 3 (60-80 words): Forward-looking close. What Rose will bring in the first 90 days. Specific CTA — request a conversation, state availability.>",
  "interview_tips": [
    "<concrete tip for this specific role>",
    "<concrete tip>",
    "<concrete tip>"
  ],
  "recruiter_email": "<email address found anywhere in the JD text, or empty string if none>"
}}"""

# GROQ api call from config, but with DB override if user has entered a custom key in the UI settings
def _get_groq_key() -> str:
    # Priority: 1. DB settings (user entered in UI), 2. config module, 3. empty
    settings = db.load_settings()
    db_key = settings.get("groq_key", "")
    if db_key:
        return db_key
    return GROQ_API_KEY  # from config (which now reads secrets or .env)


def _call_groq(prompt: str, max_tokens: int = 2000) -> str:
    GROQ_API_KEY = _get_groq_key()
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set – please add it in Settings tab or Streamlit secrets")
    
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                 "Content-Type": "application/json"},
        json={
            "model":       GROQ_MODEL,
            "messages":    [{"role":"system","content":_SYSTEM},
                            {"role":"user",  "content":prompt}],
            "temperature": 0.2,
            "max_tokens":  max_tokens,
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def analyse(
    job_title:       str,
    company:         str,
    job_description: str,
    url:             str = "",
    source:          str = "",
    cv_text:         str = "",
    cv_skills:       list[str] | None = None,
) -> dict:
    """
    Full ATS analysis of a job against Rose's profile.
    Returns a rich dict consumed by the UI and PDF generator.
    """
    cv_extra = ""
    if cv_text:
        cv_extra = f"\nUPLOADED CV (first 1500 chars):\n{cv_text[:1500]}"
    if cv_skills:
        cv_extra += f"\nDetected skills from uploaded CV: {', '.join(cv_skills[:25])}"

    prompt = _PROMPT.format(
        title=job_title,
        company=company or "the hiring company",
        source=source,
        url=url,
        description=job_description[:3500],
        profile=ROSE_PROFILE,
        cv_extra=cv_extra,
    )

    try:
        raw    = _call_groq(prompt)
        raw    = re.sub(r"^```(?:json)?", "", raw.strip()).rstrip("`").strip()
        result = json.loads(raw)

        defaults = {
            "match_score": 0, "rationale": "", "matched_keywords": [],
            "missing_skills": [], "strengths": [], "gaps": [],
            "tailored_cv_summary": "", "tailored_bullets": [],
            "cover_letter": "", "interview_tips": [], "recruiter_email": "",
        }
        for k, v in defaults.items():
            result.setdefault(k, v)

        result["match_score"] = max(0, min(100, int(result["match_score"])))

        # Never leave placeholder text
        for field in ["tailored_cv_summary", "cover_letter"]:
            if "[" in result.get(field,"") or "Company" in result.get(field,""):
                result[field] = result[field].replace("[Company]", company or "the company")
                result[field] = result[field].replace("[Role]", job_title)
                result[field] = result[field].replace("[company]", company or "the company")

        return result

    except json.JSONDecodeError as e:
        print(f"[analyzer] JSON parse error: {e}")
        return _fallback(job_title, company, job_description)
    except Exception as e:
        print(f"[analyzer] Groq error: {e}")
        return _fallback(job_title, company, job_description)


def _fallback(title: str, company: str, description: str) -> dict:
    """Honest keyword-overlap fallback when Groq is unavailable."""
    from modules.scrapers._utils import TARGET_ROLES
    combined = (title + " " + description).lower()
    hits = sum(1 for r in TARGET_ROLES if r in combined)
    score = min(60, hits * 12)
    jd_words = set(re.findall(r"\b[a-z]{4,}\b", description.lower()))
    profile_words = set(re.findall(r"\b[a-z]{4,}\b", ROSE_PROFILE.lower()))
    matched = sorted(jd_words & profile_words)[:12]
    return {
        "match_score": score,
        "rationale": "Groq is unavailable — rough keyword match only. Run analysis again when API is reachable.",
        "matched_keywords": matched,
        "missing_skills": [],
        "strengths": [],
        "gaps": [],
        "tailored_cv_summary": "",
        "tailored_bullets": [],
        "cover_letter": "",
        "interview_tips": [],
        "recruiter_email": "",
        "_fallback": True,
    }
