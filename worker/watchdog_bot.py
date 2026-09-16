#!/usr/bin/env python3
"""WatchDog Telegram companion bot.

Purpose: phone-friendly defensive notifications and quick passive triage.
Active penetration-test jobs are intentionally not launched from chat commands;
those remain behind the WatchDog dashboard authorization controls.
"""

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
WATCHDOG_BASE_URL = os.environ.get("WATCHDOG_BASE_URL", "").strip().rstrip("/")
POLL_SECONDS = max(2, int(os.environ.get("BOT_POLL_SECONDS", "3")))

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")


def api(method: str, payload=None):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    data = urllib.parse.urlencode(payload or {}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def send(chat_id: str, text: str):
    api("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"})


def allowed(chat_id) -> bool:
    return bool(ALLOWED_CHAT_ID) and str(chat_id) == ALLOWED_CHAT_ID


def triage(text: str) -> str:
    urls = sorted(set(URL_RE.findall(text)))
    emails = sorted(set(EMAIL_RE.findall(text)))
    ips = sorted(set(IP_RE.findall(text)))
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    score = 0
    reasons = []
    lowered = text.lower()
    if "xn--" in lowered:
        score += 20; reasons.append("punycode / IDN string")
    if re.search(r"login|verify|password|wallet|seed|urgent|suspended|invoice", lowered):
        score += 12; reasons.append("social-engineering language")
    if any(u.lower().startswith("http://") for u in urls):
        score += 8; reasons.append("unencrypted HTTP URL")
    if ips:
        score += 5; reasons.append("raw IP indicator")
    score = min(score, 100)

    label = "HIGHER" if score >= 35 else "ELEVATED" if score >= 15 else "LOW"
    return (
        f"WatchDog passive triage\n"
        f"Risk: {label} ({score}/100)\n"
        f"URLs: {len(urls)} | Emails: {len(emails)} | IPs: {len(ips)}\n"
        f"Reasons: {', '.join(reasons) if reasons else 'no basic heuristic triggers'}\n"
        f"SHA-256: {sha}\n\n"
        "This is a triage aid, not a malware verdict."
    )


def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not allowed(chat_id):
        return

    if text == "/start" or text == "/help":
        send(str(chat_id),
             "WatchDog bot\n\n"
             "/status — worker/bot status\n"
             "/triage <text> — local passive indicator triage + SHA-256\n"
             "/search <username/name/email/domain> — open WatchDog public-OSINT search\n\n"
             "Active scans are not launched from chat; use the dashboard authorization controls.")
        return

    if text == "/status":
        send(str(chat_id), "WatchDog bot: ONLINE\nMode: passive/defensive companion\nActive scan launch: DISABLED IN CHAT")
        return

    if text.startswith("/triage "):
        send(str(chat_id), triage(text[8:].strip()))
        return

    if text.startswith("/search "):
        q = text[8:].strip()
        if not q:
            send(str(chat_id), "Usage: /search username-or-public-identifier")
            return
        if WATCHDOG_BASE_URL:
            url = f"{WATCHDOG_BASE_URL}/index.html?search={urllib.parse.quote(q)}"
            send(str(chat_id), f"Open WatchDog search:\n{url}")
        else:
            send(str(chat_id), f"Search queued for dashboard entry: {q}\nSet WATCHDOG_BASE_URL to make this command open your console directly.")
        return

    send(str(chat_id), "Unknown command. Use /help.")


def main():
    if not TOKEN or not ALLOWED_CHAT_ID:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_ID before starting the bot.")

    offset = 0
    print("WatchDog Telegram bot started")
    while True:
        try:
            result = api("getUpdates", {"timeout": 25, "offset": offset})
            for update in result.get("result", []):
                offset = max(offset, int(update.get("update_id", 0)) + 1)
                if "message" in update:
                    handle_message(update["message"])
        except Exception as exc:
            print(f"bot error: {exc}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
