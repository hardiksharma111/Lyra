import os
import json
import time
import threading
from datetime import datetime

MEMORY_DIR = "memory"
REMINDERS_FILE = os.path.join(MEMORY_DIR, "reminders.json")
BRIEFING_CONFIG = os.path.join(MEMORY_DIR, "briefing_config.json")

os.makedirs(MEMORY_DIR, exist_ok=True)


def _load(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def add_reminder(text: str, time_str: str) -> str:
    """Parse time string like '6pm', '18:00', 'in 30 minutes' and schedule."""
    target = _parse_time(time_str)
    if not target:
        return f"Couldn't parse time: {time_str}"
    reminders = _load(REMINDERS_FILE)
    reminders.append({
        "text": text,
        "time": target,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fired": False
    })
    _save(REMINDERS_FILE, reminders)
    return f"Reminder set for {target}: {text}"


def _parse_time(time_str: str) -> str | None:
    import re
    now = datetime.now()
    time_str = time_str.strip().lower()

    # "in X minutes/hours"
    m = re.match(r'in (\d+) (minute|minutes|hour|hours)', time_str)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        from datetime import timedelta
        delta = timedelta(minutes=amount) if "minute" in unit else timedelta(hours=amount)
        return (now + delta).strftime("%Y-%m-%d %H:%M")

    # "6pm", "6:30pm", "18:00"
    m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now:
            from datetime import timedelta
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%d %H:%M")

    return None


def set_briefing_time(time_str: str) -> str:
    target = _parse_time(time_str)
    if not target:
        return f"Couldn't parse time: {time_str}"
    time_only = target.split(" ")[1]
    config = {"time": time_only, "enabled": True}
    _save(BRIEFING_CONFIG, config)
    return f"Morning briefing set for {time_only} daily."


def get_reminders() -> list:
    return [r for r in _load(REMINDERS_FILE) if not r.get("fired")]


def _run_briefing(speak_fn, agent):
    """Run morning briefing — chain weather + assignments + emails."""
    try:
        from tools.search import search
        from tools.google_control import get_assignments, get_emails
        parts = []

        weather = search("weather today")
        if weather:
            parts.append(weather[:300])

        assignments = get_assignments()
        if assignments:
            parts.append(f"Assignments: {str(assignments)[:300]}")

        emails = get_emails(account="main")
        if emails:
            parts.append(f"Emails: {str(emails)[:300]}")

        if parts:
            summary = agent.think("Give me a quick morning briefing based on this: " + " | ".join(parts))
            speak_fn(summary)
    except Exception as e:
        pass


def start_scheduler(speak_fn, agent):
    """Start background scheduler thread."""
    def _loop():
        while True:
            try:
                now = datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M")

                # Check reminders
                reminders = _load(REMINDERS_FILE)
                changed = False
                for r in reminders:
                    if not r.get("fired") and r.get("time", "") <= now_str:
                        speak_fn(f"Reminder: {r['text']}")
                        r["fired"] = True
                        changed = True
                if changed:
                    _save(REMINDERS_FILE, reminders)

                # Check morning briefing
                config = _load(BRIEFING_CONFIG) if os.path.exists(BRIEFING_CONFIG) else {}
                if config.get("enabled") and config.get("time"):
                    briefing_time = config["time"]
                    if now.strftime("%H:%M") == briefing_time:
                        _run_briefing(speak_fn, agent)
                        time.sleep(61)  # prevent double-fire

            except Exception:
                pass

            time.sleep(30)  # check every 30 seconds

    t = threading.Thread(target=_loop, daemon=True)
    t.start()