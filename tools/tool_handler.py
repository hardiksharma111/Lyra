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

AVAILABLE_TOOLS = """
Available tools:
- search [query]: Search the web for any information, news, facts
- run_code [code]: Execute Python code and return the result
- get_battery: Get battery percentage
- what_was_i_doing [minutes]: What apps/activity in last X minutes (default 60)
- last_app_opened: What was the last app opened
- check_notifications [app] [minutes]: Recent notifications, optional app filter
- get_whatsapp_messages [minutes]: Read recent WhatsApp messages from notifications
- send_whatsapp [contact] [message]: Send a WhatsApp message
- list_contacts: List phone contacts
- play_pause: Play or pause Spotify
- next_track: Skip to next track
- previous_track: Go to previous track
- get_current_track: What song is playing right now
- play_song [song name]: Play a specific song
- play_artist [artist name]: Play top tracks by artist
- play_playlist [playlist name]: Play a playlist
- spotify_volume [0-100]: Set Spotify volume
- play_by_mood [mood]: Play music matching a mood
- get_user_playlists: List Spotify playlists
- get_recent_emails [account]: Get recent emails (main/college)
- search_emails [query] [account]: Search emails
- get_assignments: Get Google Classroom assignments
- get_courses: Get list of courses
- exit: Exit Lyra
- none: No tool needed, just conversation
"""

def detect_intent(user_input: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""You are an intent detector for a personal AI assistant running on Android.

{AVAILABLE_TOOLS}

User message: '{user_input}'

Respond with JSON only:
{{
    "tool": "tool_name_or_none",
    "params": {{}},
    "confidence": "high/medium/low"
}}

Examples:
- "goodbye" → {{"tool": "exit", "params": {{}}, "confidence": "high"}}
- "search who is elon musk" → {{"tool": "search", "params": {{"query": "who is elon musk"}}, "confidence": "high"}}
- "what's the latest news on ai" → {{"tool": "search", "params": {{"query": "latest AI news 2025"}}, "confidence": "high"}}
- "what's the weather in mumbai" → {{"tool": "search", "params": {{"query": "weather in mumbai today"}}, "confidence": "high"}}
- "calculate compound interest for 10000 at 8 percent for 5 years" → {{"tool": "run_code", "params": {{"code": "p=10000;r=8/100;t=5;print(p*(1+r)**t)"}}, "confidence": "high"}}
- "run this code: print(2+2)" → {{"tool": "run_code", "params": {{"code": "print(2+2)"}}, "confidence": "high"}}
- "play something chill" → {{"tool": "play_by_mood", "params": {{"mood": "chill"}}, "confidence": "high"}}
- "next song" → {{"tool": "next_track", "params": {{}}, "confidence": "high"}}
- "check my emails" → {{"tool": "get_recent_emails", "params": {{"account": "main"}}, "confidence": "high"}}
- "college emails" → {{"tool": "get_recent_emails", "params": {{"account": "college"}}, "confidence": "high"}}
- "what assignments do i have" → {{"tool": "get_assignments", "params": {{}}, "confidence": "high"}}
- "what was i doing" → {{"tool": "what_was_i_doing", "params": {{"minutes": 60}}, "confidence": "high"}}
- "last app i opened" → {{"tool": "last_app_opened", "params": {{}}, "confidence": "high"}}
- "any notifications" → {{"tool": "check_notifications", "params": {{"minutes": 60}}, "confidence": "high"}}
- "check my whatsapp" → {{"tool": "get_whatsapp_messages", "params": {{"minutes": 120}}, "confidence": "high"}}
- "send rahul hey on whatsapp" → {{"tool": "send_whatsapp", "params": {{"contact": "rahul", "message": "hey"}}, "confidence": "high"}}
- "tell priya i'm coming" → {{"tool": "send_whatsapp", "params": {{"contact": "priya", "message": "I'm coming"}}, "confidence": "high"}}
- "battery" → {{"tool": "get_battery", "params": {{}}, "confidence": "high"}}
- "how are you" → {{"tool": "none", "params": {{}}, "confidence": "high"}}

RULES:
- Use search for anything needing current info, facts, news, weather, prices
- Use run_code when user asks to calculate, compute, or run something
- WhatsApp message queries → get_whatsapp_messages or send_whatsapp
- Low confidence if genuinely ambiguous → tool: none

JSON only, no other text."""
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