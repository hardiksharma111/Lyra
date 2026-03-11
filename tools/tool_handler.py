from groq import Groq
import json
import re
import subprocess

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

MODEL = "llama-3.3-70b-versatile"


def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")


client = Groq(api_key=_load_key("GROQ"))


def detect_intent(user_input: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""You are an intent detector for a personal AI assistant on Android.

TOOLS:
- search [query]: web search — use for anything needing current/live info
- run_code [code]: execute Python — use for calculations, data processing
- get_battery: battery status
- what_was_i_doing [minutes]: recent phone activity
- last_app_opened: last app used
- check_notifications [app] [minutes]: recent notifications
- get_whatsapp_messages [minutes]: recent WhatsApp messages
- send_whatsapp [contact] [message]: send WhatsApp message
- list_contacts: phone contacts
- play_pause / next_track / previous_track / get_current_track: Spotify playback
- play_song [song] / play_artist [artist] / play_playlist [name]: Spotify play
- spotify_volume [0-100] / play_by_mood [mood] / get_user_playlists: Spotify extras
- get_recent_emails [account]: Gmail (account = main or college)
- search_emails [query] [account]: search Gmail
- get_assignments / get_courses: Google Classroom
- exit: quit Lyra
- none: just conversation, no tool needed

DECISION RULES (apply in order):
1. Needs current/live data (weather, news, prices, scores, facts, anything happening now) → search
2. Needs math, calculation, conversion, or code → run_code
3. Asks about phone activity, notifications, WhatsApp → matching phone tool
4. Asks about music/Spotify → matching Spotify tool
5. Asks about email, assignments → matching Google tool
6. Says goodbye/exit/bye/later → exit
7. Everything else → none

Respond with JSON only — no other text:
{{"tool": "tool_name", "params": {{}}, "confidence": "high/medium/low"}}

User message: '{user_input}'"""
            }],
            max_tokens=150
        )
        result = response.choices[0].message.content.strip()
        result = re.sub(r'```json|```', '', result).strip()
        return json.loads(result)
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
        return send_whatsapp(params.get("contact", ""), params.get("message", ""))

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

    return None


def handle_tool(user_input: str) -> tuple[str | None, bool]:
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