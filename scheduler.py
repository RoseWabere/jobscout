"""
scheduler.py — JobScout KE
Background scheduler.  Run alongside the Streamlit app.

  streamlit run app.py &
  python scheduler.py

Also acts as a Telegram command listener:
  /start   — start auto-scraping
  /stop    — pause auto-scraping
  /scrape  — run one scrape cycle immediately
  /status  — get stats summary
  /export  — get Excel file
"""
import os, sys, time, schedule, json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    ATS_ALERT_THRESHOLD,
)
import database as db
from modules.scrapers import run_scrapers
from modules.notifier import (
    send_job_alert, poll_callbacks,
    is_tg_configured, _send, _BASE,
)
from modules.excel_export import export_to_excel

import requests as _req

_running   = True
_AUTO_SCRAPE = True

SOURCES  = os.environ.get(
    "SCRAPE_SOURCES", "BrighterMonday,Fuzu,MyJobMag,Remotive"
).split(",")
INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_HOURS","4"))

# ── Telegram command polling ──────────────────────────────────────────
_CMD_OFFSET_FILE = Path(__file__).parent / "data" / "cmd_offset.txt"

def _cmd_offset() -> int:
    try:
        return int(_CMD_OFFSET_FILE.read_text().strip())
    except Exception:
        return 0

def _save_cmd_offset(v: int):
    _CMD_OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CMD_OFFSET_FILE.write_text(str(v))


def poll_commands():
    global _AUTO_SCRAPE
    if not is_tg_configured():
        return
    offset = _cmd_offset()
    try:
        r = _req.get(
            f"{_BASE}/getUpdates",
            params={"offset": offset, "timeout": 4,
                    "allowed_updates": ["message"]},
            timeout=8,
        )
        data = r.json()
    except Exception as e:
        print(f"[scheduler] poll commands: {e}")
        return

    for upd in data.get("result", []):
        noff = upd["update_id"] + 1
        if noff > offset:
            offset = noff

        msg  = upd.get("message", {})
        text = msg.get("text","").strip().lower()
        cid  = str(msg.get("chat",{}).get("id",""))

        # Only respond to the configured chat
        if cid != TELEGRAM_CHAT_ID:
            continue

        if text in ("/start", "start"):
            _AUTO_SCRAPE = True
            _send("<b>JobScout KE started.</b>\nAuto-scraping is active. "
                  "I will notify you when relevant jobs are found.")
        elif text in ("/stop", "stop"):
            _AUTO_SCRAPE = False
            _send("<b>Auto-scraping paused.</b>\nSend /start to resume.")
        elif text in ("/scrape", "scrape"):
            _send("Running a scrape now...")
            scrape_cycle()
        elif text in ("/status", "status"):
            stats = db.get_stats()
            _send(
                f"<b>JobScout KE — Status</b>\n\n"
                f"Total tracked: {stats['total']}\n"
                f"New / unread:  {stats['new']}\n"
                f"Pending:       {stats['pending']}\n"
                f"Applied:       {stats['applied']}\n"
                f"Avg score:     {stats['avg_score']}%\n\n"
                f"Auto-scrape:   {'active' if _AUTO_SCRAPE else 'paused'}"
            )
        elif text in ("/export", "export"):
            try:
                path = export_to_excel(db.get_jobs())
                with open(path, "rb") as f:
                    _req.post(
                        f"{_BASE}/sendDocument",
                        data={"chat_id": TELEGRAM_CHAT_ID,
                              "caption": "JobScout KE — Applications export"},
                        files={"document": (path.name, f,
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                        timeout=30,
                    )
            except Exception as e:
                _send(f"Export error: {e}")
        elif text.startswith("/"):
            _send(
                "<b>Commands:</b>\n"
                "/start — resume auto-scraping\n"
                "/stop — pause auto-scraping\n"
                "/scrape — run now\n"
                "/status — get stats\n"
                "/export — get Excel file"
            )

    _save_cmd_offset(offset)


def scrape_cycle():
    if not _AUTO_SCRAPE:
        return
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Scrape cycle — {SOURCES}")

    s         = db.load_settings()
    kw_raw    = s.get("user_keywords","")
    kw_list   = [k.strip() for k in kw_raw.split(",") if k.strip()] or None
    max_days  = int(s.get("max_days","7"))
    threshold = int(s.get("min_match_score", str(ATS_ALERT_THRESHOLD)))

    result    = run_scrapers(sources=SOURCES, keywords=kw_list, max_days=max_days)
    new       = result["total_new"]
    print(f"[{ts}] Done — {new} new jobs.")

    if new == 0 or not is_tg_configured():
        return

    to_notify = [
        j for j in db.get_jobs(status="new", min_score=threshold)
        if not j.get("notification_sent")
    ][:8]

    sent = 0
    for j in to_notify:
        ok = send_job_alert(
            j["id"], j["title"], j.get("company",""),
            j.get("match_score",0), [], j.get("url",""),
        )
        if ok:
            db.update_job(j["id"], notification_sent=1, status="pending_approval")
            sent += 1
        time.sleep(0.5)

    print(f"[{ts}] Notified {sent} jobs.")


def callback_cycle():
    """Process Telegram inline button presses (Approve / Skip)."""
    from modules.notifier import poll_callbacks
    for cb in poll_callbacks():
        action = cb["action"]
        jid    = cb["job_id"]
        ts     = datetime.now().strftime("%H:%M:%S")
        if action == "approve":
            db.update_status(jid, "pending_approval")
            print(f"[{ts}] Job #{jid} approved via Telegram")
        elif action == "ignore":
            db.update_status(jid, "skipped")
            print(f"[{ts}] Job #{jid} skipped via Telegram")


if __name__ == "__main__":
    print(f"JobScout KE scheduler started — scraping every {INTERVAL}h.")
    print(f"Sources: {SOURCES}")
    print("Telegram commands: /start /stop /scrape /status /export")

    # Announce to Telegram
    if is_tg_configured():
        _send(
            "<b>JobScout KE scheduler is online.</b>\n"
            "Commands: /start /stop /scrape /status /export"
        )

    # Scheduled times
    schedule.every().day.at("07:30").do(scrape_cycle)
    schedule.every().day.at("12:00").do(scrape_cycle)
    schedule.every().day.at("17:00").do(scrape_cycle)
    schedule.every(INTERVAL).hours.do(scrape_cycle)

    # Frequent tasks
    schedule.every(2).minutes.do(callback_cycle)
    schedule.every(1).minutes.do(poll_commands)

    # Run immediately on start
    scrape_cycle()

    while _running:
        schedule.run_pending()
        time.sleep(30)
