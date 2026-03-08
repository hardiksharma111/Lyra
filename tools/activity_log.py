import time

# In-memory store — no files, no permissions needed
_activity_log = []
MAX_ENTRIES = 500

def log_event(event: dict):
    global _activity_log
    _activity_log.append(event)
    if len(_activity_log) > MAX_ENTRIES:
        _activity_log = _activity_log[-MAX_ENTRIES:]

def read_log(minutes=60):
    cutoff = time.time() * 1000 - (minutes * 60 * 1000)
    return [e for e in _activity_log if e.get("ts", 0) >= cutoff]

def last_app_opened():
    for entry in reversed(_activity_log):
        if entry.get("type") == "app_open":
            return entry.get("app", "unknown")
    return None

def what_was_i_doing(minutes=60):
    entries = read_log(minutes)
    if not entries:
        return f"No activity recorded in the past {minutes} minutes. Make sure Lyra has been running."

    app_opens = [e for e in entries if e.get("type") == "app_open"]
    notifs = [e for e in entries if e.get("type") == "notification"]

    summary = []
    if app_opens:
        apps = [f"{e.get('app','?')} at {e.get('time','')}" for e in app_opens[-10:]]
        summary.append("Apps opened: " + ", ".join(apps))
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
    phone = None
    try:
        from tools.google_control import resolve_contact_phone
        phone = resolve_contact_phone(contact)
    except Exception:
        pass
    if phone:
        phone_clean = "".join(c for c in phone if c.isdigit() or c == "+")
        if phone_clean.startswith("0"):
            phone_clean = "+91" + phone_clean[1:]
        elif not phone_clean.startswith("+"):
            phone_clean = "+91" + phone_clean
        flutter_push_fn("send_whatsapp", {"contact": phone_clean, "message": message, "method": "phone"})
        return f"Sending to {contact} ({phone_clean}): {message}"
    flutter_push_fn("send_whatsapp", {"contact": contact, "message": message, "method": "name"})
    return f"Sending to {contact} (name search): {message}"