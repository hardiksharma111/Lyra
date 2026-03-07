import json
import os
import time
from datetime import datetime

LOG_FILE = os.path.expanduser("~/lyra_activity.json")
NOTIF_FILE = os.path.expanduser("~/lyra_notifications.json")
MAX_ENTRIES = 500

def append_events(events: list):
    if not events:
        return
    try:
        existing = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                existing = json.load(f)
    except:
        existing = []

    for event in events:
        existing.append(event)

    # Keep trimmed
    if len(existing) > MAX_ENTRIES:
        existing = existing[-MAX_ENTRIES:]

    with open(LOG_FILE, "w") as f:
        json.dump(existing, f)

def read_log(minutes=60):
    try:
        if not os.path.exists(LOG_FILE):
            return []
        with open(LOG_FILE, "r") as f:
            entries = json.load(f)
        cutoff = time.time() * 1000 - (minutes * 60 * 1000)
        return [e for e in entries if e.get("ts", 0) >= cutoff]
    except:
        return []

def last_app_opened():
    try:
        entries = read_log(minutes=1440)
        for entry in reversed(entries):
            if entry.get("type") == "app_open":
                return entry.get("app", "unknown")
        return None
    except:
        return None

def what_was_i_doing(minutes=60):
    entries = read_log(minutes)
    if not entries:
        return f"No activity recorded in the past {minutes} minutes."

    app_opens = [e for e in entries if e.get("type") == "app_open"]
    notifs = [e for e in entries if e.get("type") == "notification"]

    summary = []
    if app_opens:
        apps = []
        for e in app_opens:
            app = e.get("app", "unknown")
            t = e.get("time", "")
            apps.append(f"{app} at {t}" if t else app)
        summary.append("Apps opened: " + ", ".join(apps[-10:]))
    if notifs:
        summary.append(f"Received {len(notifs)} notifications")

    return "\n".join(summary) if summary else "No significant activity."

def check_notifications(app=None, minutes=60):
    entries = read_log(minutes)
    notifs = [e for e in entries if e.get("type") == "notification"]
    if app:
        notifs = [e for e in notifs if app.lower() in e.get("app", "").lower()]
    if not notifs:
        return f"No notifications{' from ' + app if app else ''} in the past {minutes} minutes."
    lines = [f"[{e.get('time','')}] {e.get('app','')}: {e.get('text','')}" for e in notifs[-20:]]
    return "\n".join(lines)

def get_whatsapp_messages(minutes=60):
    return check_notifications(app="WhatsApp", minutes=minutes)

def send_whatsapp(contact: str, message: str, flutter_push_fn=None):
    if flutter_push_fn is None:
        return "Cannot send — no Flutter connection"
    flutter_push_fn("send_whatsapp", {"contact": contact, "message": message})
    return f"Sent to {contact}: {message}"