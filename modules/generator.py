"""
modules/generator.py — JobScout KE
Generates a proper 2-page ATS-safe resume PDF and 1-page cover letter PDF.

FIXES vs previous version:
  - Resume now includes Experience, Projects, Education, Certifications
  - Cover letter is full-length (3 paragraphs, proper spacing)
  - Job title comes from the analysis, not the JD (prevents "Construction" as title)
  - All sections populated from Rose's master profile if CV sections are empty
  - Clean typography with proper line heights
"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OUTPUT_DIR, YOUR_NAME, YOUR_EMAIL, YOUR_PHONE

try:
    from fpdf import FPDF
    _FPDF = True
except ImportError:
    _FPDF = False
    print("[generator] fpdf2 not installed — run: pip install fpdf2")

# ── Layout constants ────────────────────────────────────────────────────
F       = "Helvetica"
PW      = 210          # A4 width mm
ML, MR  = 18, 18
MT, MB  = 16, 16
UW      = PW - ML - MR

C_BK  = (15,  15,  15)
C_DK  = (45,  45,  45)
C_GY  = (85,  85,  85)
C_LT  = (145, 145, 145)
C_LN  = (205, 205, 205)

# ── Rose's master content (fallback if parsed CV sections are empty) ───
_EXPERIENCE = """Data Science and Data Engineering Associate — Data Science East Africa  |  Jan 2025–Present
• Designed and delivered production ETL pipelines processing 50GB+ monthly across 5+ client datasets
• Built Power BI dashboards (Desktop + Cloud) reducing reporting time by 40% for DSEA clients
• Engineered analytics-ready ML datasets improving predictive model performance across verticals
• Stack: Python, SQL, Apache Airflow, dbt, PostgreSQL, Power BI

Freelance AI Trainer, Annotator & Analyst  |  Remote  |  2021–Present
• RLHF annotation for LLM training; 1,000+ samples per project at <2% error rate
• Evaluated model outputs for factual accuracy, safety, and instruction-following quality

Case File Analyst Intern — Kamukunji Police Station  |  Oct 2024–Jan 2025
• Digitised 2,000+ criminal case records into structured database; built tracking system cutting retrieval time 60%

Inventory & Customer Research Analyst — Jumia Kenya / Jamboshop / Jiji  |  2023–2025
• Pricing analytics across 10,000+ SKUs; identified 15% margin improvement opportunities

Emergency Response Data Intern — NDOC  |  Mar–Jun 2021
• Real-time emergency data tracking feeding national situational awareness reports

Credit Analyst Intern — Taifa SACCO  |  May–Jul 2019
• Loan portfolio data analysis supporting KES 50M+ in credit decisions"""

_PROJECTS = """Safari Scouts — AI Kenya Travel RAG  |  safari-scouts.vercel.app
  LangChain, Weaviate vector DB, FastAPI, 500+ curated documents; live production deployment

Nairobi House Price Predictor  |  nairobi-house-price-prediction.streamlit.app
  XGBoost regression model; MAE 15.2M KSh on 8,000+ property records

Kipaji Chetu — Adaptive AI Learning Platform
  FastAPI, PostgreSQL, Groq LLM, Edge-TTS, Whisper STT; multi-modal learning system

Kijani Care 360  |  kijanicare-360.vercel.app
  Geospatial ETL pipeline, FastAPI, LangChain, PostgreSQL, Docker; environmental data platform

Africa Energy Data Pipeline  |  54 countries, 2000–2024
  PySpark processing; findings published in 2 academic papers

Kenya Food Price Tracker
  PySpark time-series forecasting; inflation trend analysis across 47 counties"""

_EDUCATION = """B.A. Security Studies & Criminology — Mount Kenya University
Diploma in Criminology — University of Nairobi
Diploma in Microfinance — Co-operative University of Kenya"""

_CERTS = """Data Analytics / Data Science / AI — LuxDevHQ
Software Development — Women Techsters
Cybersecurity Fundamentals — Women Techsters
Green Digital Skills — INCO Academy"""

_SKILLS_DEFAULT = [
    "Python", "SQL", "PySpark", "dbt", "Apache Airflow", "ETL/ELT", "Docker",
    "Power BI", "DAX", "Streamlit", "Grafana", "FastAPI", "PostgreSQL", "MySQL",
    "MongoDB", "Redis", "AWS", "GCP", "Azure", "Git", "Scikit-learn", "XGBoost",
    "LangChain", "RAG", "Groq", "LLM APIs", "Weaviate", "Power Automate", "Excel",
]


# ── PDF base class ──────────────────────────────────────────────────────
class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(ML, MT, MR)
        self.set_auto_page_break(True, margin=MB)

    def _tc(self, rgb):
        self.set_text_color(*rgb)

    def _rule(self, y=None):
        y = y or self.get_y()
        self.set_draw_color(*C_LN)
        self.set_line_width(0.25)
        self.line(ML, y, PW - MR, y)
        self.ln(2)

    def _section(self, title: str):
        self.ln(4)
        self.set_font(F, "B", 8.5)
        self._tc(C_BK)
        self.cell(0, 5, title.upper(), ln=True)
        self._rule()

    def _body(self, txt: str, size: float = 9.0, leading: float = 4.8):
        self.set_font(F, "", size)
        self._tc(C_GY)
        self.multi_cell(UW, leading, txt.strip())

    def _bold_line(self, txt: str, size: float = 9.0):
        self.set_font(F, "B", size)
        self._tc(C_DK)
        self.cell(0, 5, txt.strip(), ln=True)

    def _bullet(self, txt: str, indent: float = 5):
        self.set_font(F, "", 9)
        self._tc(C_GY)
        self.set_x(ML + indent)
        self.cell(3.5, 4.8, "\u2022")
        self.multi_cell(UW - indent - 3.5, 4.8, txt.strip())

    def _kv(self, label: str, value: str):
        self.set_font(F, "B", 8.5)
        self._tc(C_DK)
        self.cell(28, 4.8, label + ":")
        self.set_font(F, "", 8.5)
        self._tc(C_GY)
        self.multi_cell(UW - 28, 4.8, value)


# ── Resume ──────────────────────────────────────────────────────────────

def generate_resume(
    contact:          dict,
    cv_sections:      dict,
    cv_skills:        list[str],
    tailored_summary: str,
    tailored_bullets: list[str],
    job_title:        str = "",
    job_id:           int = 0,
) -> Path:
    if not _FPDF:
        raise RuntimeError("fpdf2 not installed")

    name     = contact.get("name",     YOUR_NAME)
    email    = contact.get("email",    YOUR_EMAIL)
    phone    = contact.get("phone",    YOUR_PHONE)
    linkedin = contact.get("linkedin", "linkedin.com/in/rosewabere")
    github   = contact.get("github",   "github.com/Rozieroz")

    skills = cv_skills or _SKILLS_DEFAULT
    exp    = cv_sections.get("experience","").strip()    or _EXPERIENCE
    edu    = cv_sections.get("education","").strip()     or _EDUCATION
    certs  = cv_sections.get("certifications","").strip() or _CERTS
    proj   = cv_sections.get("projects","").strip()      or _PROJECTS

    pdf = _PDF()
    pdf.add_page()

    # ── Header ──────────────────────────────────────────────────────────
    pdf.set_font(F, "B", 18)
    pdf._tc(C_BK)
    pdf.cell(0, 9, name, ln=True, align="C")

    # Targeted role line — use job_title from analysis, NOT from JD raw text
    if job_title:
        pdf.set_font(F, "", 10)
        pdf._tc(C_GY)
        pdf.cell(0, 5, job_title, ln=True, align="C")

    # Contact row
    pdf.set_font(F, "", 7.5)
    pdf._tc(C_LT)
    contact_parts = [p for p in [email, phone, linkedin, github] if p]
    pdf.cell(0, 5, "   |   ".join(contact_parts), ln=True, align="C")
    pdf.ln(2)
    pdf._rule()

    # ── Summary ─────────────────────────────────────────────────────────
    if tailored_summary and tailored_summary.strip():
        pdf._section("Professional Summary")
        pdf._body(tailored_summary)
        pdf.ln(1)

    # ── Key Achievements (LLM bullets) ──────────────────────────────────
    if tailored_bullets:
        pdf._section("Key Achievements")
        for b in tailored_bullets:
            if b.strip():
                pdf._bullet(b)
        pdf.ln(1)

    # ── Skills ──────────────────────────────────────────────────────────
    pdf._section("Technical Skills")
    # Group into chunks of ~8 for readability
    chunks = [skills[i:i+9] for i in range(0, len(skills), 9)]
    for chunk in chunks:
        pdf._body("  ·  ".join(chunk), size=8.5)
    pdf.ln(1)

    # ── Experience ──────────────────────────────────────────────────────
    pdf._section("Professional Experience")
    _render_freetext(pdf, exp)
    pdf.ln(1)

    # ── Projects ────────────────────────────────────────────────────────
    if proj:
        pdf._section("Selected Projects")
        _render_freetext(pdf, proj)
        pdf.ln(1)

    # ── Education ───────────────────────────────────────────────────────
    pdf._section("Education")
    for line in edu.strip().split("\n"):
        s = line.strip()
        if s:
            pdf._body(s, size=8.5)
    pdf.ln(1)

    # ── Certifications ──────────────────────────────────────────────────
    if certs:
        pdf._section("Certifications")
        for line in certs.strip().split("\n"):
            s = line.strip()
            if s:
                pdf._body(s, size=8.5)

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]", "_", name)
    out  = OUTPUT_DIR / f"resume_{safe}_{job_id}_{ts}.pdf"
    pdf.output(str(out))
    return out


def _render_freetext(pdf: _PDF, text: str):
    """
    Render a block of free text intelligently:
      - Lines that look like job/section headings → bold
      - Lines starting with • or - → bullet
      - Everything else → body text
    """
    for line in text.strip().split("\n"):
        s = line.rstrip()
        if not s.strip():
            pdf.ln(2)
            continue

        # Heading: short, starts with capital, no leading whitespace, ends with date pattern or |
        stripped = s.strip()
        is_heading = (
            len(stripped) < 100
            and re.match(r"^[A-Z]", stripped)
            and ("|" in stripped or re.search(r"\d{4}", stripped))
            and not stripped.startswith("•")
        )
        if is_heading:
            pdf.ln(2)
            pdf._bold_line(stripped, size=9)
        elif stripped.startswith(("•", "-", "*")):
            pdf._bullet(stripped.lstrip("•-* "))
        else:
            pdf._body(stripped)


# ── Cover Letter ────────────────────────────────────────────────────────

def generate_cover_letter(
    contact:           dict,
    job_title:         str,
    company:           str,
    cover_letter_text: str,
    job_id:            int = 0,
) -> Path:
    if not _FPDF:
        raise RuntimeError("fpdf2 not installed")

    name  = contact.get("name",  YOUR_NAME)
    email = contact.get("email", YOUR_EMAIL)
    phone = contact.get("phone", YOUR_PHONE)
    linkedin = contact.get("linkedin","linkedin.com/in/rosewabere")

    pdf = _PDF()
    pdf.add_page()

    # ── Letterhead ──────────────────────────────────────────────────────
    pdf.set_font(F, "B", 14)
    pdf._tc(C_BK)
    pdf.cell(0, 8, name, ln=True)

    pdf.set_font(F, "", 8)
    pdf._tc(C_LT)
    hdr_parts = [p for p in [email, phone, linkedin] if p]
    pdf.cell(0, 5, "   |   ".join(hdr_parts), ln=True)
    pdf.ln(1)
    pdf._rule()

    # ── Date + recipient block ───────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font(F, "", 9)
    pdf._tc(C_GY)
    pdf.cell(0, 5, datetime.now().strftime("%B %d, %Y"), ln=True)
    pdf.ln(4)

    pdf.set_font(F, "B", 9)
    pdf._tc(C_DK)
    pdf.cell(0, 5, "Hiring Manager", ln=True)

    pdf.set_font(F, "", 9)
    pdf._tc(C_GY)
    if company:
        pdf.cell(0, 5, company, ln=True)
    pdf.ln(4)

    pdf.set_font(F, "", 9)
    pdf._tc(C_BK)
    pdf.cell(0, 5, f"Re: Application for {job_title}", ln=True)
    pdf.ln(6)

    # ── Body — render each paragraph with proper spacing ─────────────────
    # Split on double newline (paragraph break)
    paras = [p.strip() for p in cover_letter_text.split("\n\n") if p.strip()]
    for i, para in enumerate(paras):
        pdf.set_font(F, "", 10)
        pdf._tc(C_GY)
        pdf.multi_cell(UW, 5.8, para)
        pdf.ln(5)  # space between paragraphs

    # ── Closing ──────────────────────────────────────────────────────────
    pdf.ln(3)
    pdf.set_font(F, "", 10)
    pdf._tc(C_GY)
    pdf.cell(0, 5, "Warm regards,", ln=True)
    pdf.ln(8)   # signature space
    pdf.set_font(F, "B", 10)
    pdf._tc(C_BK)
    pdf.cell(0, 5, name, ln=True)
    pdf.set_font(F, "", 8.5)
    pdf._tc(C_LT)
    pdf.cell(0, 5, "   |   ".join([p for p in [email, phone] if p]), ln=True)

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]", "_", name)
    out  = OUTPUT_DIR / f"cover_letter_{safe}_{job_id}_{ts}.pdf"
    pdf.output(str(out))
    return out
