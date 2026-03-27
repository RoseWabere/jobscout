"""
config.py — JobScout KE
Central configuration. All secrets come from .env.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── Identity ───────────────────────────────────────────────────────────
YOUR_NAME  = os.getenv("YOUR_NAME",  "Rose Wabere")
YOUR_EMAIL = os.getenv("YOUR_EMAIL", "rosewabere7@gmail.com")
YOUR_PHONE = os.getenv("YOUR_PHONE", "+254708486104")

# ── Groq ───────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

# ── Telegram ───────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── WhatsApp hook (plug in your custom bot here) ───────────────────────
# Set WHATSAPP_WEBHOOK_URL to your custom WhatsApp bot's endpoint.
# The notifier will POST a JSON payload there.
WHATSAPP_WEBHOOK_URL = os.getenv("WHATSAPP_WEBHOOK_URL", "")

# ── SMTP (for sending application emails) ─────────────────────────────
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_EMAIL    = os.getenv("YOUR_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")

# ── App ────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

DB_PATH              = BASE_DIR / "jobscout.db"
UPLOADS_DIR          = BASE_DIR / "data" / "uploads"
OUTPUT_DIR           = BASE_DIR / "data" / "output"
ATS_ALERT_THRESHOLD  = int(os.getenv("ATS_ALERT_THRESHOLD", "55"))
MAX_JOBS_PER_SOURCE  = int(os.getenv("MAX_JOBS_PER_SOURCE", "25"))
SCRAPE_DELAY_SECONDS = float(os.getenv("SCRAPE_DELAY_SECONDS", "2.0"))

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXPORTS_DIR = BASE_DIR / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def health() -> dict[str, bool]:
    return {
        "groq":     bool(GROQ_API_KEY),
        "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "whatsapp": bool(WHATSAPP_WEBHOOK_URL),
        "smtp":     bool(SMTP_PASSWORD),
    }

# target job keywords (comma-separated in .env)
TARGET_KEYWORDS = os.getenv("TARGET_KEYWORDS", "data engineer,analytics engineer,data analyst,data scientist,ml engineer,ai engineer,bi analyst,python developer,sql developer")
TARGET_KEYWORDS_LIST = [kw.strip() for kw in TARGET_KEYWORDS.split(",") if kw.strip()]

# to avoid old postings
DEFAULT_MAX_DAYS = int(os.getenv("DEFAULT_MAX_DAYS", "5"))
SCRAPE_MAX_DAYS = 5
