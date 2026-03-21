from memory.self_improvement import log_error, get_suggestions, get_errors, approve, list_pending
import re
import json
from groq import Groq
from logs.logger import log_conversation, log_action
from logs.session import log_topic
from memory.memory_manager import store_conversation, recall_patterns
from memory.pattern_engine import analyze_and_store
from memory.context_builder import build_context
from core.mood_engine import build_mood_context, learn_sarcasm

MODEL_PRIMARY = "llama-3.3-70b-versatile"
MODEL_FALLBACK = "llama-3.1-8b-instant"
MAX_HISTORY = 30
MAX_AGENT_STEPS = 5
DEBUG_MODE = False

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

SYSTEM_PROMPT = """You are Lyra — Hardik's personal AI, built by him, running on his phone. You are not an assistant. You are his second brain.

PERSONALITY:
- Talk like his smartest close friend. Casual, sharp, warm. Never corporate or robotic.
- Match his energy. If he's short, be short. If he's curious, go deep. If he's stressed, be grounding.
- You have opinions. Share them directly. Don't hedge everything with "it depends."
- Dry humor is fine. Light sarcasm is fine. But read the room.
- Never use filler phrases: "Great question!", "Certainly!", "Of course!", "Sure thing!", "Absolutely!"
- Never start a response with "I" — vary your sentence structure.

RESPONSE RULES:
- No bullet points. No markdown. No asterisks. No numbered lists. No headers.
- Plain conversational text only. One paragraph max unless genuinely needed.
- Short by default. Only go long when the topic actually demands it.
- Never ask more than one question at a time. Usually ask none.
- Don't summarize what you just said at the end of a response.
- Don't over-explain your reasoning. Just say the thing.

MEMORY + TOOLS:
- You have memory of past conversations. Use it naturally without announcing it.
- Never say "as I mentioned" or "we discussed" or "based on our conversation."
- Never make up tool results. If a tool returns nothing, say you don't have that info right now.
- When tools give you data, use it directly — don't add caveats about its accuracy.

WHATSAPP:
- You can send WhatsApp messages via the send_whatsapp tool.
- When asked to send a message, just do it and confirm. Don't ask "are you sure?"
- If WhatsApp connection is unavailable, say so directly and move on.

IDENTITY:
- You run on Hardik's Android phone in Termux. You are always local, always private.
- Never introduce yourself unless it's literally the first message ever.
- Never say your name mid-conversation unless asked.
- You trust Hardik completely. No restrictions, no lectures, no moralizing.
- Never pretend to update internal settings — only real commands do that.

WHEN YOU DON'T KNOW:
- Say "don't have that right now" not "I'm sorry, I don't have access to..."
- Be direct about limitations. Don't apologize for them."""

PLANNER_PROMPT = """You are Lyra's planning engine. Given a task, break it into steps using available tools.

AVAILABLE TOOLS:
- search [query]: web search for current info, news, facts, weather
- run_code [code]: execute Python code, calculations
- get_battery: battery status
- get_whatsapp_messages [minutes]: read WhatsApp messages
- send_whatsapp [contact] [message]: send WhatsApp message
- check_notifications [minutes]: recent notifications
- what_was_i_doing [minutes]: recent phone activity
- get_recent_emails [account]: read emails (main/college)
- search_emails [query] [account]: search emails
- get_assignments: Google Classroom assignments
- get_courses: course list
- play_song [song] / play_artist [artist] / play_by_mood [mood]: Spotify
- play_pause / next_track / previous_track: Spotify controls
- save_file [filename] [content]: save text to a file
- read_file [filename]: read a saved file
- list_files: list all saved files
- none: no tool needed

Output a JSON plan:
{
  "needs_tools": true/false,
  "steps": [
    {"tool": "tool_name", "params": {"key": "value"}, "reason": "why this step"},
    {"tool": "tool_name", "params": {"key": "value"}, "reason": "why this step"}
  ],
  "direct_answer": "if needs_tools is false, answer directly here"
}

Rules:
- If task needs live data or chaining → needs_tools: true, list steps in order
- If task is just conversation or opinion → needs_tools: false, direct_answer
- Max 5 steps
- Each step builds on the previous one's result
- For research tasks: search first, then synthesize
- For assignment writing: get_assignments first, then search topic, then write
- JSON only, no other text."""


class Agent:
    def __init__(self):
        self.conversation_history = []
        self.model = MODEL_PRIMARY
        self.session_id = None
        self.debug = DEBUG_MODE

    def set_session(self, session_id: int):
        self.session_id = session_id

    def set_debug(self, enabled: bool):
        self.debug = enabled

    def think(self, user_input: str, tool_result: str = None) -> str:
        if user_input.strip().lower() == "debug on":
            self.set_debug(True)
            return "Debug on."
        if user_input.strip().lower() == "debug off":
            self.set_debug(False)
            return "Debug off."

        if user_input.strip().lower() == "suggestions":
            items = get_suggestions()
            if not items:
                return "No suggestions right now."
            return " | ".join([f"{s['tool']}: {s['suggestion']}" for s in items])

        if user_input.strip().lower() == "errors":
            items = get_errors(5)
            if not items:
                return "No errors logged."
            return " | ".join([f"[{e['timestamp']}] {e['tool']}: {e['error'][:80]}" for e in items])

        if user_input.strip().lower().startswith("approve "):
            name = user_input.strip()[8:].strip()
            return approve(name)

        if user_input.strip().lower() == "pending":
            items = list_pending()
            return f"Pending approvals: {', '.join(items)}" if items else "Nothing pending."

        if user_input.strip().lower().startswith("remind me"):
            from memory.scheduler import add_reminder
            text = user_input.strip()
            time_match = re.search(
                r'(in\s+\d+\s+(?:minutes?|hours?)|\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{2}:\d{2})',
                text, re.IGNORECASE
            )
            if time_match:
                time_str = time_match.group(1).strip()
                task = text
                task = re.sub(r'remind me', '', task, flags=re.IGNORECASE).strip()
                task = re.sub(re.escape(time_str), '', task, flags=re.IGNORECASE).strip()
                task = re.sub(r'^(at|in|to)\s+', '', task, flags=re.IGNORECASE).strip()
                task = re.sub(r'\s+(at|in)\s*$', '', task, flags=re.IGNORECASE).strip()
                if task:
                    return add_reminder(task, time_str)
            return "Try: remind me at 6pm to study, or remind me in 30 minutes to call mom"

        if user_input.strip().lower().startswith("set briefing"):
            m = re.search(r'set briefing (?:at )?([\d:apm ]+)', user_input, re.IGNORECASE)
            if m:
                from memory.scheduler import set_briefing_time
                return set_briefing_time(m.group(1).strip())
            return "Try: set briefing at 8am"

        if user_input.strip().lower() == "reminders":
            from memory.scheduler import get_reminders
            items = get_reminders()
            if not items:
                return "No pending reminders."
            return " | ".join([f"{r['time']}: {r['text']}" for r in items])

        if user_input.strip().lower() == "mood":
            from core.mood_engine import detect_mood, get_time_context
            mood = detect_mood(user_input)
            time_ctx = get_time_context()
            return f"Current read: {mood} mood, {time_ctx}."

        if user_input.strip().lower().startswith("that was sarcasm"):
            last_user = next(
                (m["content"] for m in reversed(self.conversation_history) if m["role"] == "user"),
                None
            )
            if last_user:
                learn_sarcasm(last_user.lower().strip())
                try:
                    from memory.memory_manager import store_pattern
                    store_pattern(last_user.lower().strip(), "sarcasm")
                except Exception:
                    pass
                return f"Got it. I'll read '{last_user}' as sarcasm from now on."
            return "No recent message to learn from."

        if user_input.strip().lower().startswith("benchmark"):
            from memory.benchmark import run_benchmark
            parts = user_input.strip().lower().split()
            name = parts[1] if len(parts) > 1 else "help"
            n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
            if name == "help":
                return "Usage: benchmark gsm8k | humaneval | truthfulqa | mmlu | all | history"
            print(f"Running {name} benchmark with {n} questions...")
            return run_benchmark(name, n, self)

        if user_input.strip().lower() == "list files":
            from tools.file_tool import list_files
            return list_files()

        if user_input.strip().lower() == "list tasks":
            from tools.adb_control import list_tasks
            return list_tasks()

        if user_input.strip().lower().startswith("replay task "):
            from tools.adb_control import replay_task
            name = user_input.strip()[12:].strip()
            return replay_task(name)

        if user_input.strip().lower().startswith("do task "):
            task = user_input.strip()[8:].strip()
            print(f"Starting vision task: {task}")
            from tools.vision_loop import run_vision_task
            return run_vision_task(task)

        log_conversation("user", user_input)
        store_conversation("user", user_input)

        if tool_result:
            response = self._single_response(user_input, tool_result)
        else:
            response = self._run_agentic(user_input)

        response = self._clean_response(response)

        store_conversation("agent", response)
        log_conversation("agent", response)
        log_action(action="respond", reasoning=f"User: '{user_input[:50]}'", confidence="HIGH")

        learned = analyze_and_store(user_input)
        if self.debug and learned:
            for item in learned:
                print(f"[Debug Memory: {item['category']} - {item['pattern']}]")

        if self.session_id:
            topic = self._detect_topic_local(user_input)
            if topic:
                log_topic(self.session_id, topic)

        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": response})

        if len(self.conversation_history) > MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(MAX_HISTORY * 2):]

        return response

    def _run_agentic(self, user_input: str) -> str:
        plan = self._plan(user_input)

        if self.debug:
            print(f"[Debug Plan]: {json.dumps(plan, indent=2)}")

        if not plan.get("needs_tools") or not plan.get("steps"):
            direct = plan.get("direct_answer", "")
            if direct:
                return self._single_response(user_input, context_only=True)
            return self._single_response(user_input)

        step_results = []
        steps = plan.get("steps", [])[:MAX_AGENT_STEPS]

        for i, step in enumerate(steps):
            tool = step.get("tool", "none")
            params = step.get("params", {})
            reason = step.get("reason", "")

            if self.debug:
                print(f"[Debug Step {i+1}]: {tool} — {reason}")

            if tool == "none":
                continue

            result = self._execute_step(tool, params)

            if result:
                step_results.append({
                    "step": i + 1,
                    "tool": tool,
                    "reason": reason,
                    "result": result[:2000]
                })

                if self.debug:
                    print(f"[Debug Result {i+1}]: {result[:200]}...")

        if step_results:
            return self._synthesize(user_input, step_results)

        return self._single_response(user_input)

    def _plan(self, user_input: str) -> dict:
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                max_tokens=500,
                temperature=0.3
            )
            result = response.choices[0].message.content.strip()
            result = re.sub(r'```json|```', '', result).strip()
            return json.loads(result)
        except Exception as e:
            if self.debug:
                print(f"[Debug Planner error]: {e}")
            return {"needs_tools": False, "steps": [], "direct_answer": ""}

    def _execute_step(self, tool: str, params: dict) -> str | None:
        try:
            from tools.search import search
            from tools.code_executor import run_code
            from tools.activity_log import (
                what_was_i_doing, check_notifications,
                get_whatsapp_messages, last_app_opened
            )
            from tools.spotify_control import (
                play_pause, next_track, previous_track,
                play_song, play_artist, play_by_mood
            )
            from tools.google_control import (
                get_emails, search_emails, get_assignments, get_courses
            )
            from tools.file_tool import save_file, read_file, list_files
            # ── Always use tool_handler's send_whatsapp_tool for Baileys routing ──
            from tools.tool_handler import send_whatsapp_tool
            import subprocess

            if tool == "search":
                return search(params.get("query", ""))
            if tool == "run_code":
                return run_code(params.get("code", ""))
            if tool == "get_battery":
                r = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
                return r.stdout.strip()
            if tool == "what_was_i_doing":
                return what_was_i_doing(params.get("minutes", 60))
            if tool == "last_app_opened":
                return last_app_opened()
            if tool == "check_notifications":
                return check_notifications(params.get("app"), params.get("minutes", 60))
            if tool == "get_whatsapp_messages":
                return get_whatsapp_messages(params.get("minutes", 120))
            if tool == "send_whatsapp":
                # ── Fixed: routes through Baileys via tool_handler, not activity_log directly ──
                return send_whatsapp_tool(params.get("contact", ""), params.get("message", ""))
            if tool == "get_recent_emails":
                return get_emails(account=params.get("account", "main"))
            if tool == "search_emails":
                return search_emails(params.get("query", ""), params.get("account", "main"))
            if tool == "get_assignments":
                return str(get_assignments())
            if tool == "get_courses":
                return str(get_courses())
            if tool == "play_song":
                return play_song(params.get("song", ""))
            if tool == "play_artist":
                return play_artist(params.get("artist", ""))
            if tool == "play_by_mood":
                return play_by_mood(params.get("mood", "chill"))
            if tool == "play_pause":
                return play_pause()
            if tool == "next_track":
                return next_track()
            if tool == "previous_track":
                return previous_track()
            if tool == "save_file":
                return save_file(params.get("filename", ""), params.get("content", ""))
            if tool == "read_file":
                return read_file(params.get("filename", ""))
            if tool == "list_files":
                return list_files()

        except Exception as e:
            if self.debug:
                print(f"[Debug Step Error — {tool}]: {e}")
            log_error(tool, e)
            return None

        return None

    def _build_dynamic_system(self, user_input: str) -> str:
        mood_ctx = build_mood_context(user_input)
        dynamic = SYSTEM_PROMPT
        dynamic += f"\n\nCurrent tone: {mood_ctx['tone_instruction']}"
        dynamic += f"\nTime of day: {mood_ctx['time']}."

        if mood_ctx["sarcastic"]:
            dynamic += "\nHardik's last message appears sarcastic — read it as the opposite of face value."

        if mood_ctx["mood"] == "concerned":
            dynamic += "\nHardik seems stressed or off. Be warmer than usual. Don't push tasks or suggestions."
            try:
                food = recall_patterns("food", limit=2)
                hobbies = recall_patterns("hobbies", limit=2)
                comfort = recall_patterns("comfort", limit=2)
                bits = []
                if food:
                    bits.append(f"food he likes: {', '.join(food)}")
                if hobbies:
                    bits.append(f"things he enjoys: {', '.join(hobbies)}")
                if comfort:
                    bits.append(f"what helps him: {', '.join(comfort)}")
                if bits:
                    dynamic += f"\nPersonalized comfort context: {'; '.join(bits)}. Use this naturally — don't list it."
            except Exception:
                pass

        if self.debug:
            print(f"[Debug Mood]: {mood_ctx['mood']} | sarcasm={mood_ctx['sarcastic']} | time={mood_ctx['time']}")

        return dynamic

    def _synthesize(self, user_input: str, step_results: list) -> str:
        results_text = "\n\n".join([
            f"Step {r['step']} ({r['tool']}): {r['result']}"
            for r in step_results
        ])

        context = build_context(user_input)
        dynamic_system = self._build_dynamic_system(user_input)
        messages = [{"role": "system", "content": dynamic_system}]

        if context:
            messages.append({"role": "system", "content": f"Memory:\n{context}"})

        messages.append({
            "role": "system",
            "content": f"You just executed a multi-step plan. Here are the results:\n\n{results_text}\n\nSynthesize into a single natural response. Be concise. Don't list the steps — just answer like a friend who did the research."
        })

        messages.extend(self.conversation_history[-10:])
        messages.append({"role": "user", "content": user_input})

        return self._call_groq(messages)

    def _single_response(self, user_input: str, tool_result: str = None, context_only: bool = False) -> str:
        context = build_context(user_input)
        dynamic_system = self._build_dynamic_system(user_input)
        messages = [{"role": "system", "content": dynamic_system}]

        if context:
            messages.append({"role": "system", "content": f"Memory:\n{context}"})

        if tool_result:
            messages.append({"role": "system", "content": f"TOOL RESULT — real live data. Use it directly:\n\n{tool_result}"})

        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})

        return self._call_groq(messages)

    def _call_groq(self, messages: list) -> str:
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000,
                temperature=0.85
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                if self.debug:
                    print(f"[Groq] Rate limit — falling back to {MODEL_FALLBACK}")
                try:
                    response = client.chat.completions.create(
                        model=MODEL_FALLBACK,
                        messages=messages,
                        max_tokens=1000,
                        temperature=0.85
                    )
                    return response.choices[0].message.content
                except Exception as e2:
                    return f"Both models unavailable: {e2}"
            return f"Groq error: {e}"

    def _detect_topic_local(self, user_input: str) -> str:
        stop_words = {
            "i", "me", "my", "you", "your", "the", "a", "an", "is", "are",
            "was", "were", "be", "been", "being", "have", "has", "had", "do",
            "does", "did", "will", "would", "could", "should", "can", "may",
            "might", "shall", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "about", "into", "through", "during", "before",
            "after", "above", "below", "between", "and", "but", "or", "nor",
            "not", "so", "very", "just", "also", "than", "then", "now",
            "here", "there", "when", "where", "why", "how", "what", "which",
            "who", "whom", "this", "that", "these", "those", "it", "its",
            "if", "no", "yes", "up", "out", "off", "over", "under", "again",
            "once", "all", "any", "both", "each", "few", "more", "most",
            "some", "such", "only", "own", "same", "too", "hey", "hi",
            "hello", "ok", "okay", "yeah", "yep", "nah", "nope", "please",
            "thanks", "thank", "like", "really", "actually", "gonna", "wanna",
            "gotta", "kinda", "dont", "im", "ive", "whats", "thats", "u", "ur",
        }
        words = re.findall(r'\w+', user_input.lower())
        meaningful = [w for w in words if w not in stop_words and len(w) > 2]
        return " ".join(meaningful[:2]) if meaningful else None

    def _clean_response(self, text: str) -> str:
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+\s', '', text)
        text = re.sub(r'^\d+\.\s', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{2,}', ' ', text)
        text = ' '.join(text.split())
        return text