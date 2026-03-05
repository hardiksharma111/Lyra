import json
import os
from datetime import datetime

CONVERSATION_LOG = "logs/conversation_log.json"
ACTION_LOG = "logs/action_log.json"

def _read_log(filepath: str) -> list:
    # Read existing log file, return empty list if file is empty
    try:
        with open(filepath, "r") as f:
            content = f.read().strip()
            # If file is empty return empty list
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def _write_log(filepath: str, data: list):
    # Write updated log back to file
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def log_conversation(role: str, message: str):
    # role is either "user" or "agent"
    logs = _read_log(CONVERSATION_LOG)

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "role": role,
        "message": message
    }

    logs.append(entry)
    _write_log(CONVERSATION_LOG, logs)

def log_action(action: str, reasoning: str, confidence: str = "N/A"):
    # Logs what the agent did and why
    logs = _read_log(ACTION_LOG)

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "reasoning": reasoning,
        # Confidence of how sure the agent was — part of our safety layer
        "confidence": confidence
    }

    logs.append(entry)
    _write_log(ACTION_LOG, logs)

def get_recent_conversations(limit: int = 10) -> list:
    # Fetches last N conversations — used later by memory system
    logs = _read_log(CONVERSATION_LOG)
    return logs[-limit:]

def get_session_summary() -> dict:
    # Returns a quick summary of current session stats
    logs = _read_log(CONVERSATION_LOG)

    if not logs:
        return {"total_messages": 0, "session_start": None}

    return {
        "total_messages": len(logs),
        "session_start": logs[0]["timestamp"],
        "last_active": logs[-1]["timestamp"]
    }