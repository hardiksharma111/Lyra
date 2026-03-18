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
    from voice.wakeword import wait_for_wakeword

if IS_ANDROID:
    import requests
    import json as _json
    import subprocess
    from http.server import HTTPServer, BaseHTTPRequestHandler

    FLUTTER_URL = "http://127.0.0.1:5001/command"

    def push_to_flutter(data: dict):
        try:
            requests.post(FLUTTER_URL, json=data, timeout=5)
        except Exception:
            pass

    def speak(text: str):
        push_to_flutter({"action": "speak", "text": text})
        subprocess.Popen(
            ["termux-tts-speak", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

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

                if action == "log_event":
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
                    result_holder = ["Recording..."]
                    def do_record():
                        from tools.voice_input import record_and_transcribe
                        result_holder[0] = record_and_transcribe()
                    t = threading.Thread(target=do_record)
                    t.start()
                    t.join(timeout=25)
                    response = _json.dumps({"status": "ok", "transcript": result_holder[0]}).encode()

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

    def _start_event_server():
        HTTPServer(("127.0.0.1", 5002), EventHandler).serve_forever()

    threading.Thread(target=_start_event_server, daemon=True).start()

    def _start_sync():
        try:
            from tools.cloud_sync import start_auto_sync, push_to_drive
            push_to_drive()
            start_auto_sync()
        except Exception:
            pass

    threading.Thread(target=_start_sync, daemon=True).start()

else:
    from voice import speak, listen
    from voice.wakeword import wait_for_wakeword
    def push_to_flutter(data: dict): pass

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

    agent = Agent()
    session_id = start_session()
    agent.set_session(session_id)
    should_exit = [False]

    from memory.scheduler import start_scheduler
    start_scheduler(speak, agent)

    if IS_ANDROID:
        safe_print("[Session started]")
        safe_print("Platform: Android")
        safe_print("Lyra ready. Type below.")
        safe_print("-" * 40)
    else:
        safe_print("Lyra ready. Type below or say 'blueberry' for voice.")
        safe_print("Commands: 'profile' | 'categories' | 'goodbye'")
        safe_print("Platform: Windows")
        safe_print("-" * 50)

    if IS_WINDOWS and not os.path.exists("memory/app_index.json"):
        from tools.system_controls import build_app_index
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
                speak("Later.")
                end_session(session_id)
                should_exit[0] = True
                import subprocess
                subprocess.Popen(["python", "main.py"])
            else:
                safe_print("Lyra: Goodbye.\n")
                speak("Goodbye.")
                end_session(session_id)
                should_exit[0] = True
            return True

        response = agent.think(user_input, tool_result=tool_result if tool_result else None)

        if IS_ANDROID:
            speak(response)
        else:
            safe_print(f"Lyra: {response}\n")
            speak(response)

        return False

    if IS_ANDROID:
        _handle_flutter_message = handle_input

        def flutter_poll_loop():
            while not should_exit[0]:
                try:
                    resp = requests.post(FLUTTER_URL, json={"action": "get_outbox"}, timeout=5)
                    data = resp.json()
                    for msg in data.get("messages", []):
                        if msg.get("type") == "user_message":
                            text = msg.get("text", "").strip()
                            if text:
                                safe_print(f"[Flutter] {text}")
                                threading.Thread(target=handle_input, args=(text,), daemon=True).start()
                    activity = data.get("activity_events", [])
                    if activity:
                        from tools.activity_log import log_event
                        for ev in activity:
                            log_event(ev)
                except Exception:
                    pass
                time.sleep(1)

        threading.Thread(target=flutter_poll_loop, daemon=True).start()

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
                        if failed_attempts >= MAX_FAILED_ATTEMPTS:
                            speak("Going back to standby.")
                            break
                        continue

                    failed_attempts = 0
                    exiting = handle_input(voice_input)
                    if exiting:
                        return
                    break

            except Exception as e:
                safe_print(f"Voice error: {e}")
                time.sleep(1)

    if IS_WINDOWS:
        threading.Thread(target=voice_loop, daemon=True).start()

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