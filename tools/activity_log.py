import json
import os
import requests
from groq import Groq

FLUTTER_URL = "http://127.0.0.1:5001/command"
ACTIVITY_LOG = "/sdcard/lyra_activity.json"
NOTIF_LOG = "/sdcard/lyra_notifications.json"
REQUEST_TIMEOUT = 10

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} not found")

client = Groq(api_key=_load_key("GROQ"))

def _send_command(command: dict) -> dict:
    try:
        r = requests.post(FLUTTER_URL, json=command, timeout=REQUEST_TIMEOUT)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── Activity Log ─────────────────────────────────────────────────────────────

def get_activity_log(limit_minutes: int = 60) -> list:
    """Read activity log directly from file (faster than going through Flutter)."""
    try:
        if not os.path.exists(ACTIVITY_LOG):
            return []
        with open(ACTIVITY_LOG, "r") as f:
            entries = json.load(f)
        import time
        cutoff = (time.time() * 1000) - (limit_minutes * 60 * 1000)
        return [e for e in entries if e.get("ts", 0) >= cutoff]
    except Exception:
        return []

def get_notifications(limit_minutes: int = 60, app_filter: str = None) -> list:
    """Read notification log directly from file."""
    try:
        if not os.path.exists(NOTIF_LOG):
            return []
        with open(NOTIF_LOG, "r") as f:
            entries = json.load(f)
        import time
        cutoff = (time.time() * 1000) - (limit_minutes * 60 * 1000)
        filtered = [e for e in entries if e.get("ts", 0) >= cutoff]
        if app_filter:
            filtered = [e for e in filtered if app_filter.lower() in e.get("app", "").lower()]
        return filtered
    except Exception:
        return []

def what_was_i_doing(minutes_ago: int = 60) -> str:
    """Answer 'what was I doing X minutes ago / in the past hour'."""
    entries = get_activity_log(minutes_ago)
    if not entries:
        return f"No activity recorded in the past {minutes_ago} minutes. Make sure Lyra's accessibility service is enabled."

    # Build a readable summary
    summary_lines = []
    seen = set()
    for e in entries:
        key = f"{e.get('time')} {e.get('app')}"
        if key not in seen:
            seen.add(key)
            t = e.get("time", "")
            app = e.get("app", "Unknown")
            etype = e.get("type", "")
            if etype == "app_open":
                summary_lines.append(f"{t} — opened {app}")
            elif etype == "notification":
                text = e.get("text", "")[:100]
                summary_lines.append(f"{t} — {app} notification: {text}")

    if not summary_lines:
        return "No significant activity recorded."

    log_text = "\n".join(summary_lines[-30:])  # Last 30 events max

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"Here's what the user did on their phone in the past {minutes_ago} minutes:\n\n{log_text}\n\nGive a brief, natural summary of their activity. Be concise, 2-3 sentences max. Speak directly to them."
            }],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"In the past {minutes_ago} minutes: " + ", ".join(
            set(e.get("app", "") for e in entries if e.get("app"))
        )

def check_notifications(app: str = None, minutes: int = 60) -> str:
    """Get recent notifications, optionally filtered by app."""
    notifs = get_notifications(minutes, app)
    if not notifs:
        filter_str = f"from {app} " if app else ""
        return f"No notifications {filter_str}in the past {minutes} minutes."

    lines = []
    for n in notifs[-20:]:  # Last 20
        t = n.get("time", "")
        app_name = n.get("app", "")
        title = n.get("title", "")
        text = n.get("text", "")
        if title and text:
            lines.append(f"{t} [{app_name}] {title}: {text}")
        elif title:
            lines.append(f"{t} [{app_name}] {title}")
        elif text:
            lines.append(f"{t} [{app_name}] {text}")

    if len(lines) == 1:
        return lines[0]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"These are recent notifications:\n\n" + "\n".join(lines) + "\n\nSummarize briefly what the user missed. Be direct, 2-3 sentences max."
            }],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "\n".join(lines)

def get_whatsapp_messages(minutes: int = 120) -> str:
    """Get WhatsApp notifications (messages) from the log."""
    return check_notifications(app="WhatsApp", minutes=minutes)

def send_whatsapp(contact: str, message: str) -> str:
    """Send a WhatsApp message via accessibility service."""
    result = _send_command({
        "action": "send_whatsapp",
        "contact": contact,
        "message": message
    })
    if result.get("status") == "ok":
        return f"Sent to {contact}: '{message}'"
    return result.get("message", "Failed to send WhatsApp message.")

def last_app_opened() -> str:
    """What was the last app opened."""
    entries = get_activity_log(60 * 24)  # Last 24 hours
    app_opens = [e for e in entries if e.get("type") == "app_open"]
    if not app_opens:
        return "No app activity recorded yet."
    last = app_opens[-1]
    return f"Last app opened: {last.get('app')} at {last.get('time')}"