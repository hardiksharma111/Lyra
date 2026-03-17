import os
import sys
import time
import threading
from threading import Lock

from core.platform import IS_ANDROID, IS_WINDOWS

os.system('cls' if os.name == 'nt' else 'clear')

from core.agent import Agent
from logs.session import start_session, end_session
from memory.pattern_engine import print_profile, get_all_categories
from tools.tool_handler import handle_tool

if IS_WINDOWS:
    from tools.system_controls import build_app_index
    from voice.wakeword import wait_for_wakeword

if IS_ANDROID:
    import requests

    FLUTTER_URL = "http://127.0.0.1:5001/command"

    def push_to_flutter(action: str, text: str = ""):
        """Send response to Flutter app to display + speak."""
        try:
            requests.post(FLUTTER_URL, json={"action": action, "text": text}, timeout=5)
        except Exception:
            pass  # Flutter not open — silently ignore

    def speak(text: str):
        push_to_flutter("speak", text)

    def listen():
        return input("You: ").strip()

    # Lightweight HTTP server so Flutter can POST activity events directly to Python
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json as _json

    class EventHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                # Read in chunks to handle large audio payloads
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
                if action == "log_event":
                    from tools.activity_log import log_event
                    log_event(body.get("event", {}))
                elif action == "transcribe":
                    from tools.voice_input import transcribe_base64
                    audio_b64 = body.get("audio", "")
                    ext = body.get("ext", "mp4")
                    transcript = transcribe_base64(audio_b64, ext)
                    import json as _j
                    response = _j.dumps({"status": "ok", "transcript": transcript}).encode()
                elif action == "record_and_transcribe":
                    import threading, json as _j
                    result_holder = ["Recording..."]
                    def do_record():
                        from tools.voice_input import record_and_transcribe
                        result_holder[0] = record_and_transcribe()
                    t = threading.Thread(target=do_record)
                    t.start()
                    t.join(timeout=20)
                    response = _j.dumps({"status": "ok", "transcript": result_holder[0]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(response)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(_json.dumps({"error": str(e)}).encode())
        def log_message(self, *args): pass  # silence access logs

    def start_event_server():
        server = HTTPServer(("127.0.0.1", 5002), EventHandler)
        server.serve_forever()

    event_thread = threading.Thread(target=start_event_server, daemon=True)
    event_thread.start()

    # Offline message queue — processed when Groq comes back online
    _offline_queue = []
    _is_online = True

    def check_online():
        global _is_online
        try:
            import requests as _r
            _r.get("https://api.groq.com", timeout=3)
            return True
        except Exception:
            return False

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
    agent = Agent()
    session_id = start_session()
    agent.set_session(session_id)
    should_exit = [False]

    # On Android: minimal startup output, Termux is background brain
    if IS_ANDROID:
        safe_print("[Session started]")
        safe_print("Platform: Android")
        safe_print("Lyra ready. Type below.")
        safe_print("-" * 40)
    else:
        safe_print("Lyra ready. Type below or say 'blueberry' for voice.")
        safe_print("Commands: 'profile' | 'categories' | 'goodbye'")
        safe_print(f"Platform: Windows")
        safe_print("-" * 50)

    if IS_WINDOWS and not os.path.exists("memory/app_index.json"):
        build_app_index()

    def handle_input(user_input: str) -> bool:
        if not user_input or user_input in ERROR_RESPONSES:
            return False

        if user_input.lower() == "profile":
            print_profile()
            return False

        if user_input.lower() == "categories":
            cats = get_all_categories()
            safe_print(f"Current categories: {', '.join(cats)}\n")
            return False

        tool_result, should_exit_now = handle_tool(user_input)

        if should_exit_now:
            if IS_ANDROID:
                push_to_flutter("speak", "Later.")
                end_session(session_id)
                should_exit[0] = True
                # On Android: restart instead of killing — keeps Termux alive
                import subprocess
                subprocess.Popen(["python", "main.py"])
            else:
                safe_print("Lyra: Goodbye.\n")
                speak("Goodbye.")
                end_session(session_id)
                should_exit[0] = True
            return True

        if tool_result:
            if IS_ANDROID:
                # Let agent wrap the tool result in a natural response
                response = agent.think(user_input, tool_result=tool_result)
                push_to_flutter("speak", response)
            else:
                response = agent.think(user_input, tool_result=tool_result)
                safe_print(f"Lyra: {response}\n")
                speak(response)
            return False

        response = agent.think(user_input)

        if IS_ANDROID:
            push_to_flutter("speak", response)
        else:
            safe_print(f"Lyra: {response}\n")
            speak(response)

        return False

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

    # On Android: also poll Flutter for messages typed in the app UI
    if IS_ANDROID:
        def flutter_poll_loop():
            """Pick up messages typed in Flutter app and process them."""
            while not should_exit[0]:
                try:
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

                except Exception:
                    pass
                time.sleep(1)  # Poll every second

        poll_thread = threading.Thread(target=flutter_poll_loop, daemon=True)
        poll_thread.start()

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