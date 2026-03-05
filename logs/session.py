import json
import os
from datetime import datetime

SESSION_FILE = "logs/session_log.json"

def start_session():
    # Called every time the agent starts up
    sessions = _read_sessions()

    session = {
        "session_id": len(sessions) + 1,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": None,
        "duration_minutes": None,
        "topics": []
    }

    sessions.append(session)
    _write_sessions(sessions)
    print(f"[Session {session['session_id']} started]")
    return session["session_id"]

def end_session(session_id: int):
    # Called every time the agent shuts down
    sessions = _read_sessions()

    for session in sessions:
        if session["session_id"] == session_id:
            end_time = datetime.now()
            start_time = datetime.strptime(
                session["start_time"], "%Y-%m-%d %H:%M:%S"
            )
            duration = round((end_time - start_time).seconds / 60, 2)

            session["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
            session["duration_minutes"] = duration
            break

    _write_sessions(sessions)
    print(f"[Session {session_id} ended]")

def log_topic(session_id: int, topic: str):
    # Tracks what topics came up in each session
    # Phase 4 pattern engine uses this to learn your interests
    sessions = _read_sessions()

    for session in sessions:
        if session["session_id"] == session_id:
            if topic not in session["topics"]:
                session["topics"].append(topic)
            break

    _write_sessions(sessions)

def _read_sessions() -> list:
    try:
        with open(SESSION_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def _write_sessions(data: list):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=2)