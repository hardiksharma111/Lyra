import os
import json
import re
from datetime import datetime

MEMORY_DIR = "memory"
ERROR_LOG = os.path.join(MEMORY_DIR, "error_log.json")
SUGGESTIONS_FILE = os.path.join(MEMORY_DIR, "suggestions.json")
APPROVAL_DIR = os.path.join(MEMORY_DIR, "approval_queue")

os.makedirs(APPROVAL_DIR, exist_ok=True)


def _load(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def log_error(tool: str, error: str, user_input: str = ""):
    errors = _load(ERROR_LOG)
    errors.append({
        "tool": tool,
        "error": str(error)[:300],
        "user_input": user_input[:200],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    errors = errors[-100:]  # keep last 100
    _save(ERROR_LOG, errors)
    _maybe_generate_suggestion(tool, str(error))


def _maybe_generate_suggestion(tool: str, error: str):
    errors = _load(ERROR_LOG)
    recent = [e for e in errors[-20:] if e["tool"] == tool]
    if len(recent) >= 3:
        suggestions = _load(SUGGESTIONS_FILE)
        existing = [s["tool"] for s in suggestions if s["status"] == "pending"]
        if tool not in existing:
            suggestions.append({
                "tool": tool,
                "issue": error[:200],
                "suggestion": f"Tool '{tool}' has failed {len(recent)} times recently. Review and fix.",
                "status": "pending",
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            _save(SUGGESTIONS_FILE, suggestions)


def get_suggestions() -> list:
    return [s for s in _load(SUGGESTIONS_FILE) if s["status"] == "pending"]


def get_errors(limit: int = 10) -> list:
    return _load(ERROR_LOG)[-limit:]


def add_to_approval_queue(name: str, description: str, code: str):
    path = os.path.join(APPROVAL_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump({
            "name": name,
            "description": description,
            "code": code,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=2)


def approve(name: str) -> str:
    path = os.path.join(APPROVAL_DIR, f"{name}.json")
    if not os.path.exists(path):
        pending = list_pending()
        if not pending:
            return "No pending approvals."
        return f"Not found. Pending: {', '.join(pending)}"
    with open(path, "r") as f:
        item = json.load(f)
    try:
        exec(item["code"], {})
        os.remove(path)
        suggestions = _load(SUGGESTIONS_FILE)
        for s in suggestions:
            if s["tool"] == name:
                s["status"] = "approved"
        _save(SUGGESTIONS_FILE, suggestions)
        return f"Approved and deployed: {name}"
    except Exception as e:
        return f"Deploy failed: {e}"


def list_pending() -> list:
    if not os.path.exists(APPROVAL_DIR):
        return []
    return [f.replace(".json", "") for f in os.listdir(APPROVAL_DIR) if f.endswith(".json")]