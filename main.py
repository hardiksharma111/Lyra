from core.agent import Agent
from voice import speak, listen
from voice.wakeword import wait_for_wakeword
from logs.session import start_session, end_session
import threading
import os

os.system('cls' if os.name == 'nt' else 'clear')

ERROR_RESPONSES = [
    "I couldn't understand that",
    "Speech service unavailable",
    "No speech detected"
]

EXIT_COMMANDS = ["quit", "exit", "stop", "goodbye"]
SWITCH_TO_VOICE = ["switch to voice", "use voice", "voice mode"]
SWITCH_TO_TEXT = ["switch to text", "use text", "text mode"]
MAX_FAILED_ATTEMPTS = 5

def main():
    agent = Agent()
    session_id = start_session()
    agent.set_session(session_id)

    mode = ["text"]
    should_exit = [False]

    print("Agent ready. Type anytime | Say 'blueberry' for voice.")
    print("Commands: 'switch to voice' | 'switch to text' | 'goodbye'")
    print("-" * 50)

    def output(text: str):
        print(f"Agent: {text}\n")
        if mode[0] == "voice":
            speak(text)

    def handle_input(user_input: str) -> bool:
        if not user_input or user_input in ERROR_RESPONSES:
            return False

        if user_input.lower() in SWITCH_TO_VOICE:
            mode[0] = "voice"
            output("Switched to voice mode. Say blueberry to activate.")
            print("[Mode: Voice]")
            return False

        if user_input.lower() in SWITCH_TO_TEXT:
            mode[0] = "text"
            print("[Mode: Text]")
            print("Agent: Switched to text mode.\n")
            return False

        if user_input.lower() in EXIT_COMMANDS:
            print("Agent: Goodbye.\n")
            end_session(session_id)
            should_exit[0] = True
            return True

        print(f"You: {user_input}")
        response = agent.think(user_input)
        output(response)
        return False

    def voice_loop():
        while not should_exit[0]:
            try:
                if mode[0] != "voice":
                    threading.Event().wait(1)
                    continue

                wait_for_wakeword()

                if mode[0] != "voice":
                    continue

                speak("Listening.")
                print("\n[Voice activated]")

                failed_attempts = 0

                while not should_exit[0]:
                    voice_input = listen()

                    if not voice_input or voice_input in ERROR_RESPONSES:
                        failed_attempts += 1
                        print(f"({voice_input}) - attempt {failed_attempts}/{MAX_FAILED_ATTEMPTS}")
                        if failed_attempts >= MAX_FAILED_ATTEMPTS:
                            speak("Going back to standby.")
                            break
                        continue

                    failed_attempts = 0
                    exiting = handle_input(voice_input)
                    if exiting:
                        return

                    print("Say 'blueberry' to speak again.")
                    break

            except Exception as e:
                print(f"Voice error: {e} - restarting...")
                continue

    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()

    while not should_exit[0]:
        try:
            user_input = input("You (text): ").strip()
            exiting = handle_input(user_input)
            if exiting:
                break
        except Exception as e:
            print(f"Text error: {e}")
            continue

if __name__ == "__main__":
    main()