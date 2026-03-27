from groq import Groq
import json
import subprocess
import requests as _requests

from tools.activity_log import (
    what_was_i_doing, check_notifications,
    get_whatsapp_messages, send_whatsapp, last_app_opened
)
from tools.spotify_control import (
    play_pause, next_track, previous_track, get_current_track,
    play_song, play_artist, play_playlist,
    set_volume as spotify_volume,
    play_by_mood, get_user_playlists
)
from tools.google_control import (
    get_emails, search_emails, get_assignments, get_courses
)
from tools.search import search
from tools.code_executor import run_code
from tools.file_tool import save_file, read_file, list_files

MODEL = "llama-3.3-70b-versatile"

RESERVED_COMMANDS = {
    "mood", "debug on", "debug off", "suggestions", "errors", "pending",
    "reminders", "profile", "categories", "benchmark", "list tasks", "list files",
}

BAILEYS_URL = "http://127.0.0.1:5003"

EXIT_WORDS = {"exit", "bye", "goodbye", "later", "quit"}
SIMPLE_NONE_WORDS = {"mood", "ok", "so", "yeah", "yup", "cool", "nice"}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Web search for current/live information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Run Python code for calculations/data processing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_battery",
            "description": "Get phone battery status.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "what_was_i_doing",
            "description": "Get recent app activity timeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "minimum": 1}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "last_app_opened",
            "description": "Get last opened app.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_notifications",
            "description": "Get recent notifications, optionally filtered by app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string"},
                    "minutes": {"type": "integer", "minimum": 1}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_whatsapp_messages",
            "description": "Get recent WhatsApp messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "minimum": 1}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Send WhatsApp message to a contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["contact", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_contacts",
            "description": "List phone contacts.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_pause",
            "description": "Toggle Spotify play/pause.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "next_track",
            "description": "Skip to next Spotify track.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "previous_track",
            "description": "Go to previous Spotify track.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_track",
            "description": "Get currently playing Spotify track.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_song",
            "description": "Play song on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string"}
                },
                "required": ["song"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_artist",
            "description": "Play artist on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "artist": {"type": "string"}
                },
                "required": ["artist"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_playlist",
            "description": "Play playlist on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist": {"type": "string"}
                },
                "required": ["playlist"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_volume",
            "description": "Set Spotify volume 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_by_mood",
            "description": "Play Spotify music by mood.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {"type": "string"}
                },
                "required": ["mood"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_playlists",
            "description": "List user Spotify playlists.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_emails",
            "description": "Get recent Gmail messages for account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account": {"type": "string", "enum": ["main", "college"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search Gmail messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "account": {"type": "string", "enum": ["main", "college"]}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_assignments",
            "description": "Get Google Classroom assignments.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_courses",
            "description": "Get Google Classroom courses.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_file",
            "description": "Save text content to a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a saved local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all saved local files.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")


client = Groq(api_key=_load_key("GROQ"))


def _send_via_baileys(phone: str, message: str) -> str:
    """Send a WhatsApp message directly via Baileys on port 5003."""
    try:
        r = _requests.post(
            BAILEYS_URL,
            json={"action": "send", "jid": phone, "message": message},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "sent":
            return f"Sent to {phone}: {message}"
        return f"Baileys error: {data.get('error', 'unknown')}"
    except Exception as e:
        return f"Could not reach Baileys: {e}"


def _baileys_flutter_bridge(action: str, payload: dict) -> None:
    """
    Bridge function passed to send_whatsapp() in activity_log.py.
    When activity_log resolves the contact and calls flutter_push_fn('send_whatsapp', {...}),
    we intercept it and send via Baileys instead of Flutter accessibility.
    """
    if action == "send_whatsapp":
        contact = payload.get("contact", "")
        message = payload.get("message", "")
        _send_via_baileys(contact, message)


def send_whatsapp_tool(contact: str, message: str) -> str:
    """
    Resolves contact via activity_log (uses phone contacts + confirmed memory),
    then sends via Baileys directly. No Flutter accessibility needed.
    """
    # Check if Baileys is connected first
    try:
        r = _requests.post(BAILEYS_URL, json={"action": "status"}, timeout=2)
        if not r.json().get("connected"):
            return "WhatsApp not connected right now — Baileys is running but not paired."
    except Exception:
        return "Baileys server not reachable on port 5003."

    return send_whatsapp(contact, message, flutter_push_fn=_baileys_flutter_bridge)


def _parse_tool_args(raw_args: str) -> dict:
    if not raw_args:
        return {}
    try:
        parsed = json.loads(raw_args)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def detect_intent(user_input: str) -> dict:
    lowered = user_input.strip().lower()

    if lowered in SIMPLE_NONE_WORDS:
        return {"tool": "none", "params": {}, "confidence": "high"}

    if lowered in EXIT_WORDS:
        return {"tool": "exit", "params": {}, "confidence": "high"}

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an intent router. Call exactly one function when a tool is needed. If no tool is needed, do not call a function."
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0,
            max_tokens=80,
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            return {"tool": "none", "params": {}, "confidence": "low"}

        call = tool_calls[0]
        return {
            "tool": call.function.name,
            "params": _parse_tool_args(call.function.arguments),
            "confidence": "high"
        }
    except Exception:
        return {"tool": "none", "params": {}, "confidence": "low"}


def execute_tool(tool: str, params: dict) -> str | None:
    if not tool or tool == "none":
        return None

    if tool == "search":
        return search(params.get("query", ""))
    if tool == "run_code":
        return run_code(params.get("code", ""))
    if tool == "get_battery":
        result = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
        return result.stdout.strip()
    if tool == "what_was_i_doing":
        return what_was_i_doing(params.get("minutes", 60))
    if tool == "last_app_opened":
        return last_app_opened()
    if tool == "check_notifications":
        return check_notifications(params.get("app"), params.get("minutes", 60))
    if tool == "get_whatsapp_messages":
        return get_whatsapp_messages(params.get("minutes", 120))
    if tool == "send_whatsapp":
        # ── Now routes through Baileys directly ──
        return send_whatsapp_tool(params.get("contact", ""), params.get("message", ""))
    if tool == "list_contacts":
        result = subprocess.run(["termux-contact-list"], capture_output=True, text=True)
        return result.stdout.strip()
    if tool == "play_pause": return play_pause()
    if tool == "next_track": return next_track()
    if tool == "previous_track": return previous_track()
    if tool == "get_current_track": return get_current_track()
    if tool == "play_song": return play_song(params.get("song", params.get("query", "")))
    if tool == "play_artist": return play_artist(params.get("artist", ""))
    if tool == "play_playlist": return play_playlist(params.get("playlist", ""))
    if tool == "spotify_volume": return spotify_volume(params.get("level", 50))
    if tool == "play_by_mood": return play_by_mood(params.get("mood", "chill"))
    if tool == "get_user_playlists": return get_user_playlists()
    if tool == "get_recent_emails":
        return get_emails(account=params.get("account", "main"))
    if tool == "search_emails":
        return search_emails(query=params.get("query", ""), account=params.get("account", "main"))
    if tool == "get_assignments": return get_assignments()
    if tool == "get_courses": return get_courses()
    if tool == "save_file":
        return save_file(params.get("filename", ""), params.get("content", ""))
    if tool == "read_file":
        return read_file(params.get("filename", ""))
    if tool == "list_files":
        return list_files()

    return None


def handle_tool(user_input: str) -> tuple[str | None, bool]:
    lower = user_input.strip().lower()

    if lower in RESERVED_COMMANDS:
        return None, False
    if any(lower.startswith(cmd) for cmd in [
        "that was sarcasm", "benchmark", "remind me", "set briefing",
        "approve ", "replay task ", "do task ",
    ]):
        return None, False

    intent = detect_intent(user_input)
    tool = intent.get("tool", "none")
    params = intent.get("params", {})
    confidence = intent.get("confidence", "low")

    if tool == "exit":
        return None, True
    if confidence == "low":
        return None, False

    result = execute_tool(tool, params)
    return result, False