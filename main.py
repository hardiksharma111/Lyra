import os
import sys
import time
import threading
from threading import Lock

# Platform detection first — before any other imports
from core.platform import IS_ANDROID, IS_WINDOWS

os.system('cls' if os.name == 'nt' else 'clear')

from core.agent import Agent
from logs.session import start_session, end_session
from memory.pattern_engine import print_profile, get_all_categories
from tools.tool_handler import handle_tool

# Windows-only imports
if IS_WINDOWS:
    from tools.system_controls import build_app_index
    from voice.wakeword import wait_for_wakeword

# Voice — different on Android vs PC
if IS_ANDROID:
    def speak(text):
        os.system(f'termux-tts-speak "{text}"')

    def listen():
        # Placeholder — Whisper voice input comes in Session 2
        return input("You (voice): ").strip()

    def wait_for_wakeword():
        input("Press Enter to activate voice...")
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

    safe_print("Lyra ready. Type below or say 'blueberry' for voice.")
    safe_print("Commands: 'profile' | 'categories' | 'goodbye'")
    safe_print(f"Platform: {'Android' if IS_ANDROID else 'Windows'}")
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

        safe_print(f"You: {user_input}")

        tool_result, should_exit_now = handle_tool(user_input)

        if should_exit_now:
            safe_print("Lyra: Goodbye.\n")
            speak("Goodbye.")
            end_session(session_id)
            should_exit[0] = True
            return True

        if tool_result:
            safe_print(f"Lyra: {tool_result}\n")
            speak(tool_result)
            return False

        response = agent.think(user_input)
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

    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()

    while not should_exit[0]:
        try:
            user_input = input("You: ").strip()
            if user_input:
                exiting = handle_input(user_input)
                if exiting:
                    break
        except Exception as e:
            safe_print(f"Error: {e}")
            continue


if __name__ == "__main__":
    main()