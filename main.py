import os
import sys
from threading import Lock

os.system('clear')

from core.agent import Agent
from logs.session import start_session, end_session
from memory.pattern_engine import print_profile, get_all_categories
from tools.tool_handler import handle_tool

print_lock = Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def speak(text: str):
    os.system(f'termux-tts-speak "{text}"')

def main():
    agent = Agent()
    session_id = start_session()
    agent.set_session(session_id)
    should_exit = [False]

    safe_print("Lyra ready.")
    safe_print("Commands: 'profile' | 'categories' | 'debug on/off' | 'goodbye'")
    safe_print("-" * 40)

    def handle_input(user_input: str) -> bool:
        if not user_input:
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
            speak("Later.")
            end_session(session_id)
            should_exit[0] = True
            return True

        response = agent.think(user_input, tool_result=tool_result)
        safe_print(f"Lyra: {response}\n")
        speak(response)
        return False

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