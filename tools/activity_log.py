import time
import json
import os
import subprocess

# In-memory store — no files, no permissions needed
_activity_log = []
MAX_ENTRIES = 500

# Path to remember confirmed contacts
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTACT_MEMORY_FILE = os.path.join(BASE_DIR, "memory", "confirmed_contacts.json")

def _load_confirmed_contacts() -> dict:
    try:
        if os.path.exists(CONTACT_MEMORY_FILE):
            with open(CONTACT_MEMORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_confirmed_contact(name: str, phone: str):
    contacts = _load_confirmed_contacts()
    contacts[name.lower().strip()] = phone
    try:
        with open(CONTACT_MEMORY_FILE, "w") as f:
            json.dump(contacts, f, indent=2)
    except Exception:
        pass

def _get_all_termux_contacts() -> list:
    try:
        result = subprocess.run(
            ["termux-contact-list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = json.loads(result.stdout)
            return [{"name": c.get("name", ""), "phone": c.get("number", "")} for c in raw if c.get("name") and c.get("number")]
    except Exception:
        pass
    return []

def _clean_phone(phone: str) -> str:
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    if cleaned.startswith("0"):
        cleaned = "+91" + cleaned[1:]
    elif not cleaned.startswith("+"):
        cleaned = "+91" + cleaned
    return cleaned

def _find_contacts(name: str) -> list:
    name_lower = name.lower().strip()
    contacts = _get_all_termux_contacts()
    exact = []
    partial = []
    for c in contacts:
        cname = c["name"].lower().strip()
        phone = _clean_phone(c["phone"])
        words = cname.split()
        if name_lower == cname:
            exact.append({"name": c["name"], "phone": phone})
        elif any(w == name_lower or w.startswith(name_lower) for w in words):
            partial.append({"name": c["name"], "phone": phone})
    return exact if exact else partial

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

# Pending confirmation state — holds contact name + message while waiting for user to pick
_pending_whatsapp = None

def get_pending_whatsapp():
    return _pending_whatsapp

def clear_pending_whatsapp():
    global _pending_whatsapp
    _pending_whatsapp = None

def confirm_and_send(choice_input: str, flutter_push_fn) -> str:
    global _pending_whatsapp
    if not _pending_whatsapp:
        return None

    candidates = _pending_whatsapp["candidates"]
    message = _pending_whatsapp["message"]
    original_name = _pending_whatsapp["original_name"]

    # Try to parse choice as number
    try:
        idx = int(choice_input.strip()) - 1
        if 0 <= idx < len(candidates):
            chosen = candidates[idx]
            _save_confirmed_contact(original_name, chosen["phone"])
            clear_pending_whatsapp()
            flutter_push_fn("send_whatsapp", {"contact": chosen["phone"], "message": message, "method": "phone"})
            return f"Got it. Sending to {chosen['name']} ({chosen['phone']}): {message}\nI'll remember this for next time."
    except ValueError:
        pass

    # Try to match by name fragment
    choice_lower = choice_input.lower().strip()
    for c in candidates:
        if choice_lower in c["name"].lower():
            _save_confirmed_contact(original_name, c["phone"])
            clear_pending_whatsapp()
            flutter_push_fn("send_whatsapp", {"contact": c["phone"], "message": message, "method": "phone"})
            return f"Got it. Sending to {c['name']} ({c['phone']}): {message}\nI'll remember this for next time."

    options = "\n".join([f"{i+1}. {c['name']} ({c['phone']})" for i, c in enumerate(candidates)])
    return f"Didn't catch that. Reply with the number:\n{options}"

def send_whatsapp(contact: str, message: str, flutter_push_fn=None) -> str:
    global _pending_whatsapp

    if flutter_push_fn is None:
        return "Cannot send — no Flutter connection"

    name_lower = contact.lower().strip()

    # Check confirmed contacts memory first
    confirmed = _load_confirmed_contacts()
    if name_lower in confirmed:
        phone = confirmed[name_lower]
        flutter_push_fn("send_whatsapp", {"contact": phone, "message": message, "method": "phone"})
        return f"Sending to {contact} ({phone}): {message}"

    # Search phone contacts
    matches = _find_contacts(contact)

    if not matches:
        # No match — fall back to WhatsApp name search
        flutter_push_fn("send_whatsapp", {"contact": contact, "message": message, "method": "name"})
        return f"Couldn't find '{contact}' in contacts. Trying WhatsApp name search."

    if len(matches) == 1:
        # Single match — confirm once, then remember
        chosen = matches[0]
        _save_confirmed_contact(name_lower, chosen["phone"])
        flutter_push_fn("send_whatsapp", {"contact": chosen["phone"], "message": message, "method": "phone"})
        return f"Sending to {chosen['name']} ({chosen['phone']}): {message}"

    # Multiple matches — ask user to pick
    _pending_whatsapp = {
        "candidates": matches,
        "message": message,
        "original_name": name_lower
    }
    options = "\n".join([f"{i+1}. {c['name']} ({c['phone']})" for i, c in enumerate(matches)])
    return f"I found {len(matches)} contacts named '{contact}':\n{options}\nWhich one? Reply with the number."