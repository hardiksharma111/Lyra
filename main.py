from core.agent import Agent
from voice import speak, listen
from voice.wakeword import wait_for_wakeword
from logs.session import start_session, end_session
import threading
import os
import sys
from threading import Lock

os.system('cls' if os.name == 'nt' else 'clear')

ERROR_RESPONSES = [
    "I couldn't understand that",
    "Speech service unavailable",
    "No speech detected"
]

EXIT_COMMANDS = ["quit", "exit", "stop", "goodbye"]
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
    safe_print("-" * 50)

    def handle_input(user_input: str) -> bool:
        if not user_input or user_input in ERROR_RESPONSES:
            return False

        if user_input.lower() in EXIT_COMMANDS:
            safe_print("Lyra: Goodbye.\n")
            speak("Goodbye.")
            end_session(session_id)
            should_exit[0] = True
            return True

        safe_print(f"You: {user_input}")
        response = agent.think(user_input)
        safe_print(f"Lyra: {response}\n")
        speak(response)
        return False

    def voice_loop():
        while not should_exit[0]:
            try:
                wait_for_wakeword()
                speak("Listening.")
                safe_print("\n[Voice activated]")

                failed_attempts = 0

                while not should_exit[0]:
                    voice_input = listen()

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

                    safe_print("Say 'blueberry' to speak again.")
                    break

            except Exception as e:
                safe_print(f"Voice error: {e} - restarting...")
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