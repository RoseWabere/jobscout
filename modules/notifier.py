"""
modules/notifier.py — JobScout KE
Telegram alerts with Approve / Ignore inline buttons.
Callback polling is offset-tracked so each button press fires once.

WhatsApp hook: set WHATSAPP_WEBHOOK_URL in .env to forward to your custom bot.
"""
import json
import sys
from pathlib import Path

import requests as _req

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    WHATSAPP_WEBHOOK_URL, ATS_ALERT_THRESHOLD,
)

_BASE    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_OFFSET  = Path(__file__).resolve().parent.parent / "data" / "tg_offset.txt"


# ── Public API ─────────────────────────────────────────────────────────

def send_job_alert(
    job_id: int, title: str, company: str,
    score: int, missing: list[str], url: str = "",
) -> bool:
    if not is_tg_configured():
        return False

    bar      = _bar(score)
    kw_line  = ", ".join(missing[:6]) if missing else "none — great match"
    score_lbl = "Strong match" if score >= 70 else ("Decent match" if score >= 50 else "Partial match")

    msg = (
        f"<b>New job found</b>  {bar}\n\n"
        f"<b>{_esc(title)}</b>\n"
        f"{_esc(company or 'Unknown company')}\n\n"
        f"<b>Match score:</b>  {score}/100  ({score_lbl})\n"
        f"<b>Gaps to note:</b>  {_esc(kw_line)}\n"
    )
    if url:
        msg += f"\n<a href=\"{url}\">View job posting</a>"

    keyboard = {"inline_keyboard": [[
        {"text": "Approve and apply",  "callback_data": f"approve:{job_id}"},
        {"text": "Skip this one",      "callback_data": f"ignore:{job_id}"},
    ]]}

    ok = _send(msg, keyboard)

    # Forward to custom WhatsApp bot if configured
    if WHATSAPP_WEBHOOK_URL:
        _whatsapp_forward({
            "job_id": job_id, "title": title, "company": company,
            "score": score, "url": url,
        })

    return ok


def send_dispatch_confirmation(title: str, to_email: str) -> None:
    if not is_tg_configured():
        return
    _send(f"Application sent\n\n<b>{_esc(title)}</b>\nDelivered to: <code>{_esc(to_email)}</code>")


def send_test(msg: str = "JobScout KE is connected.") -> bool:
    return _send(f"<b>Test notification</b>\n{msg}")


def poll_callbacks() -> list[dict]:
    """
    Poll Telegram getUpdates for pending button presses.
    Returns list of {job_id: int, action: str}.
    Uses a file-backed offset so each callback fires once only.
    """
    if not is_tg_configured():
        return []

    offset = _read_offset()
    try:
        r = _req.get(
            f"{_BASE}/getUpdates",
            params={"offset": offset, "timeout": 4,
                    "allowed_updates": ["callback_query"]},
            timeout=8,
        )
        data = r.json()
    except Exception as e:
        print(f"[notifier] poll error: {e}")
        return []

    results = []
    for update in data.get("result", []):
        new_offset = update["update_id"] + 1
        if new_offset > offset:
            offset = new_offset

        cb = update.get("callback_query")
        if not cb:
            continue

        raw = cb.get("data", "")
        if ":" not in raw:
            continue

        action, jid_str = raw.split(":", 1)
        try:
            job_id = int(jid_str)
        except ValueError:
            continue

        _answer_callback(cb["id"])
        results.append({"job_id": job_id, "action": action})

    _write_offset(offset)
    return results


def is_tg_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


# ── Internals ──────────────────────────────────────────────────────────

def _send(text: str, reply_markup: dict | None = None) -> bool:
    payload: dict = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = _req.post(f"{_BASE}/sendMessage", json=payload, timeout=10)
        ok = r.json().get("ok", False)
        if not ok:
            print(f"[notifier] Telegram: {r.json().get('description')}")
        return ok
    except Exception as e:
        print(f"[notifier] send error: {e}")
        return False


def _answer_callback(cb_id: str, text: str = "Got it") -> None:
    try:
        _req.post(f"{_BASE}/answerCallbackQuery",
                  json={"callback_query_id": cb_id, "text": text}, timeout=5)
    except Exception:
        pass


def _whatsapp_forward(payload: dict) -> None:
    """POST to your custom WhatsApp bot webhook."""
    try:
        _req.post(WHATSAPP_WEBHOOK_URL, json=payload, timeout=8)
    except Exception as e:
        print(f"[notifier] WhatsApp webhook error: {e}")


def _bar(score: int) -> str:
    filled = round(score / 10)
    return "\u2588" * filled + "\u2591" * (10 - filled)


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _read_offset() -> int:
    _OFFSET.parent.mkdir(parents=True, exist_ok=True)
    try:
        return int(_OFFSET.read_text().strip())
    except Exception:
        return 0


def _write_offset(val: int) -> None:
    _OFFSET.parent.mkdir(parents=True, exist_ok=True)
    _OFFSET.write_text(str(val))
