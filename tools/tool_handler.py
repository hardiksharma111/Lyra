from core.platform import IS_ANDROID, IS_WINDOWS
from groq import Groq
import json
import re

# Windows-only tools
if IS_WINDOWS:
    from tools.system_controls import (
        get_system_status, get_battery, get_brightness,
        set_brightness, volume_up, volume_down, mute_volume,
        unmute_volume, lock_screen, shutdown, cancel_shutdown,
        open_app, set_volume
    )

# Android-only tools
if IS_ANDROID:
    from tools.vision_control import (
        analyze_screen, read_screen, describe_screen,
        analyze_screen_with_question
    )

# Cross-platform tools
from tools.spotify_control import (
    play_pause, next_track, previous_track, get_current_track,
    play_song, play_artist, play_playlist,
    set_volume as spotify_volume,
    play_by_mood, get_user_playlists
)
from tools.whatsapp_control import (
    save_contact, list_contacts
)
from tools.google_control import (
    get_recent_emails, read_email_content,
    search_emails, get_assignments, get_courses
)

MODEL = "llama-3.3-70b-versatile"

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

# Android-only system tools
ANDROID_TOOLS = """
- get_battery: Get battery percentage
- get_volume: Get current volume
- set_volume [level 0-15]: Set volume
- get_wifi: Get WiFi info
- describe_screen: Describe what app/screen is currently showing
- read_screen: Read all text visible on screen
- analyze_screen [question]: Answer a specific question about what's on screen
""" if IS_ANDROID else ""

WINDOWS_TOOLS = """
- get_system_status: Get CPU, RAM, battery, brightness info
- get_battery: Get battery percentage and charging status
- get_brightness: Get current screen brightness
- set_brightness [level 0-100]: Set screen brightness
- volume_up [steps]: Increase volume
- volume_down [steps]: Decrease volume
- set_volume [level 0-100]: Set exact volume level
- mute_volume: Mute audio
- unmute_volume: Unmute audio
- lock_screen: Lock the computer
- shutdown [seconds]: Shutdown computer after delay
- cancel_shutdown: Cancel a pending shutdown
- open_app [app_name]: Open an application
""" if IS_WINDOWS else ""

AVAILABLE_TOOLS = f"""
Available tools:
{WINDOWS_TOOLS}{ANDROID_TOOLS}
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
- list_contacts: List contacts from Google
- save_contact [name] [number]: Save a contact manually
- get_recent_emails [account]: Get recent emails (main/college)
- read_email_content [index] [account]: Read full email
- search_emails [query]: Search emails
- get_assignments: Get Google Classroom assignments
- get_courses: Get list of courses
- exit: Exit Lyra completely
- none: No tool needed, just have a conversation
"""

def detect_intent(user_input: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""You are an intent detector for a personal AI assistant.

{AVAILABLE_TOOLS}

User message: '{user_input}'

Analyze the user's intent and respond with JSON only:
{{
    "tool": "tool_name_or_none",
    "params": {{}},
    "confidence": "high/medium/low"
}}

Examples:
- "goodbye" → {{"tool": "exit", "params": {{}}, "confidence": "high"}}
- "play something chill" → {{"tool": "play_by_mood", "params": {{"mood": "chill"}}, "confidence": "high"}}
- "next song" → {{"tool": "next_track", "params": {{}}, "confidence": "high"}}
- "check my emails" → {{"tool": "get_recent_emails", "params": {{"account": "main"}}, "confidence": "high"}}
- "check my college emails" → {{"tool": "get_recent_emails", "params": {{"account": "college"}}, "confidence": "high"}}
- "what assignments do i have" → {{"tool": "get_assignments", "params": {{}}, "confidence": "high"}}
- "what courses am i taking" → {{"tool": "get_courses", "params": {{}}, "confidence": "high"}}
- "search emails about fees" → {{"tool": "search_emails", "params": {{"query": "fees"}}, "confidence": "high"}}
- "read first email" → {{"tool": "read_email_content", "params": {{"index": 0}}, "confidence": "high"}}
- "list my contacts" → {{"tool": "list_contacts", "params": {{}}, "confidence": "high"}}
- "what's on my screen" → {{"tool": "describe_screen", "params": {{}}, "confidence": "high"}}
- "read my screen" → {{"tool": "read_screen", "params": {{}}, "confidence": "high"}}
- "what app is open" → {{"tool": "describe_screen", "params": {{}}, "confidence": "high"}}
- "read that notification" → {{"tool": "read_screen", "params": {{}}, "confidence": "high"}}
- "what does my screen say" → {{"tool": "read_screen", "params": {{}}, "confidence": "high"}}
- "is there a deadline on screen" → {{"tool": "analyze_screen", "params": {{"question": "is there a deadline or due date visible"}}, "confidence": "high"}}
- "how are you" → {{"tool": "none", "params": {{}}, "confidence": "high"}}

Respond with JSON only, no other text."""
            }],
            max_tokens=150
        )
        result = response.choices[0].message.content.strip()
        result = re.sub(r'```json|```', '', result).strip()
        return json.loads(result)
    except Exception as e:
        return {"tool": "none", "params": {}, "confidence": "low"}

def execute_tool(tool: str, params: dict) -> str | None:
    if tool == "none" or not tool:
        return None

    # Windows-only tools
    if IS_WINDOWS:
        if tool == "get_system_status":
            return get_system_status()
        if tool == "get_battery":
            return get_battery()
        if tool == "get_brightness":
            return str(get_brightness()) + "% brightness"
        if tool == "set_brightness":
            return set_brightness(params.get("level", 50))
        if tool == "volume_up":
            return volume_up(params.get("steps", 5))
        if tool == "volume_down":
            return volume_down(params.get("steps", 5))
        if tool == "set_volume":
            return set_volume(params.get("level", 50))
        if tool == "mute_volume":
            return mute_volume()
        if tool == "unmute_volume":
            return unmute_volume()
        if tool == "lock_screen":
            return lock_screen()
        if tool == "shutdown":
            return shutdown(params.get("seconds", 30))
        if tool == "cancel_shutdown":
            return cancel_shutdown()
        if tool == "open_app":
            return open_app(params.get("app_name", ""))

    # Android system tools
    if IS_ANDROID:
        if tool == "get_battery":
            import subprocess
            result = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
            return result.stdout.strip()
        if tool == "set_volume":
            import subprocess
            level = params.get("level", 50)
            subprocess.run(["termux-volume", "music", str(level)])
            return f"Volume set to {level}"
        if tool == "describe_screen":
            return describe_screen()
        if tool == "read_screen":
            return read_screen()
        if tool == "analyze_screen":
            question = params.get("question", "What is on this screen?")
            return analyze_screen_with_question(question)

    # Cross-platform tools
    if tool == "play_pause":
        return play_pause()
    if tool == "next_track":
        return next_track()
    if tool == "previous_track":
        return previous_track()
    if tool == "get_current_track":
        return get_current_track()
    if tool == "play_song":
        return play_song(params.get("song", params.get("query", "")))
    if tool == "play_artist":
        return play_artist(params.get("artist", ""))
    if tool == "play_playlist":
        return play_playlist(params.get("playlist", ""))
    if tool == "spotify_volume":
        return spotify_volume(params.get("level", 50))
    if tool == "play_by_mood":
        return play_by_mood(params.get("mood", "chill"))
    if tool == "get_user_playlists":
        return get_user_playlists()
    if tool == "list_contacts":
        return list_contacts()
    if tool == "save_contact":
        return save_contact(params.get("name", ""), params.get("number", ""))
    if tool == "get_recent_emails":
        return get_recent_emails(
            account=params.get("account", "main"),
            context=params.get("context", "")
        )
    if tool == "read_email_content":
        return read_email_content(
            index=params.get("index", 0),
            account=params.get("account", None)
        )
    if tool == "search_emails":
        return search_emails(
            query=params.get("query", ""),
            account=params.get("account", None)
        )
    if tool == "get_assignments":
        return get_assignments()
    if tool == "get_courses":
        return get_courses()

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