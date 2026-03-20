import os
import sys
import time
import threading
from threading import Lock
from collections import deque

from core.platform import IS_ANDROID, IS_WINDOWS

os.system('cls' if os.name == 'nt' else 'clear')

from core.agent import Agent
from logs.session import start_session, end_session
from memory.pattern_engine import print_profile, get_all_categories
from tools.tool_handler import handle_tool

if IS_WINDOWS:
    from voice.wakeword import wait_for_wakeword

if IS_ANDROID:
    import requests
    import json as _json
    import subprocess
    from http.server import HTTPServer, BaseHTTPRequestHandler

    FLUTTER_URL = "http://127.0.0.1:5001/command"

    _flutter_queue = deque()
    _flutter_queue_lock = Lock()

    def _enqueue_flutter(action: str, text: str = ""):
        with _flutter_queue_lock:
            _flutter_queue.append({"action": action, "text": text})

    def _flush_flutter_queue(max_items: int = 10):
        sent = 0
        while sent < max_items:
            with _flutter_queue_lock:
                if not _flutter_queue:
                    return
                msg = _flutter_queue[0]
            try:
                requests.post(FLUTTER_URL, json=msg, timeout=5)
                with _flutter_queue_lock:
                    if _flutter_queue and _flutter_queue[0] == msg:
                        _flutter_queue.popleft()
                sent += 1
            except Exception:
                return

    def push_to_flutter(action: str, text: str = ""):
        try:
            requests.post(FLUTTER_URL, json={"action": action, "text": text}, timeout=5)
        except Exception:
            _enqueue_flutter(action, text)

    def speak(text: str):
        push_to_flutter("speak", text)

    def listen():
        return input("You: ").strip()

    _handle_flutter_message = lambda text: None

    class EventHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                chunks = []
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                raw = b"".join(chunks)
                body = _json.loads(raw)
                action = body.get("action")
                response = b'{"status":"ok"}'

                if action == "ping":
                    response = b'{"status":"ok","message":"pong"}'

                elif action == "log_event":
                    from tools.activity_log import log_event
                    log_event(body.get("event", {}))

                elif action == "whatsapp_message":
                    from tools.activity_log import log_event
                    log_event({
                        "type": "whatsapp_message",
                        "app": "WhatsApp",
                        "pkg": "com.whatsapp",
                        "text": f"{body.get('from','?')}: {body.get('text','')}",
                        "ts": body.get("ts", 0),
                        "time": "",
                    })

                elif action == "record_and_transcribe":
                    def do_record_and_push():
                        try:
                            from tools.voice_input import start_vad_recording, record_and_transcribe
                            push_to_flutter("show_message", "PY: starting voice capture...")
                            try:
                                transcript = start_vad_recording()
                            except Exception:
                                push_to_flutter("show_message", "PY: VAD unavailable, falling back...")
                                transcript = record_and_transcribe()
                            push_to_flutter("show_message", f"PY: transcription done: {transcript[:80]}...")
                            if transcript and not transcript.startswith("Transcription error") and not transcript.startswith("Recording failed"):
                                push_to_flutter("transcript_result", transcript)
                            else:
                                push_to_flutter("transcript_error", transcript)
                        except Exception as e:
                            push_to_flutter("transcript_error", str(e))
                    threading.Thread(target=do_record_and_push, daemon=True).start()
                    response = _json.dumps({"status": "ok", "message": "recording started"}).encode()

                elif action == "transcribe":
                    from tools.voice_input import transcribe_base64
                    transcript = transcribe_base64(body.get("audio", ""), body.get("ext", "mp4"))
                    response = _json.dumps({"status": "ok", "transcript": transcript}).encode()

                self.send_response(200)
                self.end_headers()
                self.wfile.write(response)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(_json.dumps({"error": str(e)}).encode())

        def log_message(self, *args): pass

    threading.Thread(target=lambda: HTTPServer(("127.0.0.1", 5002), EventHandler).serve_forever(), daemon=True).start()

    # ── Push Groq key to Flutter once on startup ──
    def _load_key(name: str) -> str:
        with open("Keys.txt") as f:
            for line in f:
                if line.startswith(name):
                    return line.split("=", 1)[1].strip()
        raise ValueError(f"{name} not found in Keys.txt")

    def _push_config():
        time.sleep(3)
        try:
            groq_key = _load_key("GROQ")
            requests.post(FLUTTER_URL, json={"action": "set_config", "groq_key": groq_key}, timeout=5)
            print("[config] Groq key pushed to Flutter.")
        except Exception as e:
            print(f"[config] Failed to push key: {e}")

    threading.Thread(target=_push_config, daemon=True).start()

    # ── Auto-start Baileys WhatsApp server ──
    def _start_baileys():
        try:
            check = requests.post(
                'http://127.0.0.1:5003',
                json={'action': 'status'},
                timeout=2
            )
            if check.json().get('connected') is not None:
                print("[baileys] Already running.")
                return
        except Exception:
            pass
        try:
            subprocess.Popen(
                ['node', '/data/data/com.termux/files/home/baileys-server/server.js'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("[baileys] Server started.")
        except Exception as e:
            print(f"[baileys] Failed to start: {e}")

    threading.Thread(target=_start_baileys, daemon=True).start()
    # ── end Baileys auto-start ──

    def start_sync():
        try:
            from tools.cloud_sync import start_auto_sync, push_to_drive
            push_to_drive()
            start_auto_sync()
        except Exception:
            pass

    sync_thread = threading.Thread(target=start_sync, daemon=True)
    sync_thread.start()

else:
    from voice import speak, listen
    from voice.wakeword import wait_for_wakeword

ERROR_RESPONSES = [
    "I couldn't understand that",
    "Speech service unavailable",
    "No speech detected"
]

MAX_FAILED_ATTEMPTS = 5
print_lock = Lock()


def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)


def main():
    global _handle_flutter_message

    # ── --once mode ──
    once_mode = "--once" in sys.argv
    once_text = None
    if once_mode:
        idx = sys.argv.index("--once")
        if idx + 1 < len(sys.argv):
            once_text = sys.argv[idx + 1].strip()

    agent = Agent()
    session_id = start_session()
    agent.set_session(session_id)

    if not once_mode:
        from memory.scheduler import start_scheduler
        start_scheduler(speak, agent)

    should_exit = [False]

    platform_label = "Android" if IS_ANDROID else "Windows"
    if not once_mode:
        safe_print(f"Lyra ready. [{platform_label}]")
        safe_print("Commands: 'profile' | 'categories' | 'debug on/off' | 'goodbye'")
        safe_print("-" * 40)

    def handle_input(user_input: str) -> bool:
        if not user_input or user_input in ERROR_RESPONSES:
            return False

        if user_input.lower() == "profile":
            print_profile()
            return False

        if user_input.lower() == "categories":
            cats = get_all_categories()
            safe_print(f"Categories: {', '.join(cats)}\n")
            return False

        tool_result, should_exit_now = handle_tool(user_input)

        if should_exit_now:
            if IS_ANDROID:
                push_to_flutter("speak", "Later.")
                end_session(session_id)
                should_exit[0] = True
                if not once_mode:
                    subprocess.Popen(["python", "main.py"])
            else:
                safe_print("Lyra: Goodbye.\n")
                speak("Goodbye.")
                end_session(session_id)
                should_exit[0] = True
            return True

        response = agent.think(user_input, tool_result=tool_result if tool_result else None)

        if IS_ANDROID:
            push_to_flutter("speak", response)
        else:
            safe_print(f"Lyra: {response}\n")
            speak(response)

        return False

    # ── Once mode: process single input and exit ──
    if once_mode and IS_ANDROID:
        if once_text:
            safe_print(f"[once] {once_text}")
            handle_input(once_text)
            time.sleep(2)
        end_session(session_id)
        safe_print("[once] Done. Exiting.")
        return

    if IS_ANDROID:
        _handle_flutter_message = handle_input

        def flutter_poll_loop():
            while not should_exit[0]:
                try:
                    _flush_flutter_queue(max_items=20)
                    resp = requests.post(
                        FLUTTER_URL,
                        json={"action": "get_outbox"},
                        timeout=5
                    )
                    data = resp.json()
                    messages = data.get("messages", [])
                    for msg in messages:
                        if msg.get("type") == "user_message":
                            text = msg.get("text", "").strip()
                            if text:
                                safe_print(f"[Flutter] {text}")
                                handle_input(text)
                    activity = data.get("activity_events", [])
                    if activity:
                        from tools.activity_log import log_event
                        for ev in activity:
                            log_event(ev)
                except Exception:
                    pass
                time.sleep(1)

        poll_thread = threading.Thread(target=flutter_poll_loop, daemon=True)
        poll_thread.start()

    def voice_loop():
        while not should_exit[0]:
            try:
                wait_for_wakeword()
                time.sleep(0.5)
                speak("Listening.")
                safe_print("\n[Voice activated]")
                failed_attempts = 0

                while not should_exit[0]:
                    try:
                        voice_input = listen()
                    except Exception as e:
                        safe_print(f"Listen error: {e}")
                        break

                    if not voice_input or voice_input in ERROR_RESPONSES:
                        failed_attempts += 1
                        safe_print(f"({voice_input}) - attempt {failed_attempts}/{MAX_FAILED_ATTEMPTS}")
                        if failed_attempts >= MAX_FAILED_ATTEMPTS:
                            speak("Going back to standby.")
                            safe_print("[Voice standby]")
                            break
                        continue

                    failed_attempts = 0
                    exiting = handle_input(voice_input)
                    if exiting:
                        return

                    if not IS_ANDROID:
                        safe_print("Say 'blueberry' to speak again.")
                    break

            except Exception as e:
                safe_print(f"Voice error: {e} - restarting...")
                time.sleep(1)
                continue

    if IS_WINDOWS:
        voice_thread = threading.Thread(target=voice_loop, daemon=True)
        voice_thread.start()

    while not should_exit[0]:
        try:
            user_input = input("You: ").strip()
            if user_input:
                exiting = handle_input(user_input)
                if exiting:
                    break
        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            safe_print(f"Error: {e}")
            continue


if __name__ == "__main__":
    main()