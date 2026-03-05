from core.agent import Agent
from voice import speak, listen
from voice.wakeword import wait_for_wakeword
from logs.session import start_session, end_session
import os

os.system('cls' if os.name == 'nt' else 'clear')

ERROR_RESPONSES = [
    "I couldn't understand that",
    "Speech service unavailable",
    "No speech detected"
]

EXIT_COMMANDS = ["quit", "exit", "stop", "goodbye"]
MAX_FAILED_ATTEMPTS = 5

def get_input() -> str:
    print("\n[V] Voice  |  [T] Type")
    choice = input("Choose input method: ").strip().lower()
    if choice == "t":
        return input("You (text): ").strip()
    else:
        return listen()

def main():
    agent = Agent()
    session_id = start_session()
    agent.set_session(session_id)

    print("Lyra standing by. Say 'blueberry' to activate.")

    while True:
        try:
            wait_for_wakeword()
            speak("Yes, I'm listening. Lyra at your service.")
            print("Lyra activated.")

            failed_attempts = 0

            while True:
                user_input = get_input()

                if not user_input or user_input in ERROR_RESPONSES:
                    failed_attempts += 1
                    print(f"({user_input}) - attempt {failed_attempts}/{MAX_FAILED_ATTEMPTS}")
                    if failed_attempts >= MAX_FAILED_ATTEMPTS:
                        speak("Going back to standby.")
                        break
                    continue

                failed_attempts = 0

                if user_input.lower() in EXIT_COMMANDS:
                    speak("Goodbye.")
                    end_session(session_id)
                    return

                print(f"You: {user_input}")
                response = agent.think(user_input)
                print(f"Lyra: {response}\n")
                speak(response)

        except Exception as e:
            print(f"Error: {e} - restarting...")
            continue

if __name__ == "__main__":
    main()