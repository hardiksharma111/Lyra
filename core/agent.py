from memory.self_improvement import log_error, get_suggestions, get_errors, approve, list_pending
import re
import json
import os
import time
from datetime import datetime
from groq import Groq
from logs.logger import log_conversation, log_action
from logs.session import log_topic
from memory.memory_manager import store_conversation, recall_patterns
from memory.pattern_engine import analyze_and_store
from memory.context_builder import build_context
from core.mood_engine import build_mood_context, learn_sarcasm
from core.subagents import SubAgentOrchestrator

MODEL_PRIMARY = "llama-3.3-70b-versatile"
MODEL_FALLBACK = "llama-3.1-8b-instant"
MAX_HISTORY = 30
MAX_AGENT_STEPS = 5
MAX_REPLAN_ATTEMPTS = 2
DEBUG_MODE = False
FEEDBACK_LOG_FILE = os.path.join("memory", "feedback_log.json")
REPEAT_WINDOW_SECONDS = 60

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

PLANNER_PROMPT = """You are Lyra's planning engine. You have access to tools for getting information and completing tasks.

AVAILABLE TOOLS:
- search: web search for current info, news, facts, weather
- run_code: execute Python code for calculations
- send_whatsapp: send WhatsApp messages
- get_whatsapp_messages: read recent WhatsApp messages
- search_emails: search emails
- play_song / play_artist / play_by_mood: Spotify control
- do_task: execute a phone task via vision (e.g., "open chrome and search ai")
- record_task / replay_task: record and replay task sequences
- save_file / read_file: file operations
- And more...

RULES:
- For any task that needs CURRENT information (news, weather, real-time data) → use search
- For code or calculations → use run_code
- For phone/app control → use do_task with specific description
- For finding things in memory → use search_emails or search
- If you just need to answer directly → don't use tools

BE SPECIFIC: When calling do_task, give very specific instructions like:
- "open chrome and search for artificial intelligence"
- "open youtube and search for ai news"
- "open settings and enable developer mode"

RESPOND NATURALLY: Don't force tool use. If the answer is in conversation context, just answer."""

VALID_TOOLS = {
    "search": ["query"],
    "run_code": ["code"],
    "get_battery": [],
    "get_whatsapp_messages": ["minutes"],
    "send_whatsapp": ["contact", "message"],
    "check_notifications": ["minutes"],
    "what_was_i_doing": ["minutes"],
    "get_recent_emails": ["account"],
    "search_emails": ["query", "account"],
    "get_assignments": [],
    "get_courses": [],
    "play_song": ["song"],
    "play_artist": ["artist"],
    "play_by_mood": ["mood"],
    "play_pause": [],
    "next_track": [],
    "previous_track": [],
    "save_file": ["filename", "content"],
    "read_file": ["filename"],
    "list_files": [],
    "do_task": ["task"],
    "record_task": ["name", "steps"],
    "replay_task": ["name"],
    "none": [],
}

# OpenAI-compatible tool schemas for Groq native tool calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the web for current information, news, facts, or weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Execute Python code for calculations, data processing, or analysis",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Send a WhatsApp message to a contact",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "Contact name or number"},
                    "message": {"type": "string", "description": "Message text"}
                },
                "required": ["contact", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_whatsapp_messages",
            "description": "Get recent WhatsApp messages",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "description": "How many minutes back to retrieve"}
                },
                "required": ["minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search emails by query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Email search query"},
                    "account": {"type": "string", "description": "Account: 'main' or 'college'", "enum": ["main", "college"]}
                },
                "required": ["query", "account"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_song",
            "description": "Play a song on Spotify",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string", "description": "Song name"}
                },
                "required": ["song"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "do_task",
            "description": "Execute a task via vision loop (open apps, control the phone)",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description (e.g., 'open chrome and search ai')"}
                },
                "required": ["task"]
            }
        }
    }
]


class Agent:
    def __init__(self):
        self.conversation_history = []
        self.model = MODEL_PRIMARY
        self.session_id = None
        self.debug = DEBUG_MODE
        self._recent_user_inputs = []
        self.subagents = SubAgentOrchestrator(self._call_groq_custom, debug=self.debug)

    def set_session(self, session_id: int):
        self.session_id = session_id

    def set_debug(self, enabled: bool):
        self.debug = enabled
        self.subagents.set_debug(enabled)

    def _append_feedback_event(self, event: dict):
        os.makedirs(os.path.dirname(FEEDBACK_LOG_FILE), exist_ok=True)
        events = []

        if os.path.exists(FEEDBACK_LOG_FILE):
            try:
                with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        events = loaded
            except Exception:
                events = []

        events.append(event)
        with open(FEEDBACK_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)

    def _track_implicit_feedback(self, user_input: str):
        normalized = re.sub(r"\s+", " ", user_input.strip().lower())
        if len(normalized) < 8:
            return

        now = time.time()
        self._recent_user_inputs = [
            (text, ts)
            for (text, ts) in self._recent_user_inputs
            if now - ts <= REPEAT_WINDOW_SECONDS
        ]

        repeated = any(
            text == normalized and (now - ts) <= REPEAT_WINDOW_SECONDS
            for (text, ts) in self._recent_user_inputs
        )

        if repeated:
            self._append_feedback_event({
                "type": "negative_repeat_within_60s",
                "text": user_input,
                "normalized": normalized,
                "timestamp": datetime.now().isoformat(),
                "window_seconds": REPEAT_WINDOW_SECONDS
            })

        self._recent_user_inputs.append((normalized, now))

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
                return "Usage: benchmark gsm8k | humaneval | truthfulqa | mmlu | phase8 | all | history"
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

        self._track_implicit_feedback(user_input)

        log_conversation("user", user_input)
        store_conversation("user", user_input)

        if tool_result:
            response = self._single_response(user_input, tool_result)
        else:
            phase9_response = self._run_phase9(user_input)
            response = phase9_response if phase9_response else self._run_agentic(user_input)

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

    def _run_phase9(self, user_input: str) -> str | None:
        """Phase 9: role-based sub-agent orchestration (research/writer/verifier)."""
        try:
            memory_context = build_context(user_input)
            result = self.subagents.run(user_input, memory_context, self.conversation_history)
            if result and result.strip():
                if self.debug:
                    print("[Debug Phase9] Sub-agent orchestration used")
                return result
        except Exception as e:
            if self.debug:
                print(f"[Debug Phase9 error]: {e}")
        return None

    def _run_agentic(self, user_input: str) -> str:
        """
        Agentic loop with replan support.
        If steps produce no results, replans with context of what failed.
        Never exits on empty steps — retries up to MAX_REPLAN_ATTEMPTS times.
        """
        accumulated_results = []
        failed_tools = []
        current_input = user_input

        for attempt in range(MAX_REPLAN_ATTEMPTS + 1):
            # Build replan context if this is a retry
            replan_context = ""
            if attempt > 0 and failed_tools:
                replan_context = f"\n\nNote: Previously tried these tools with no results: {', '.join(failed_tools)}. Try a different approach."
                current_input = user_input + replan_context

            plan = self._plan(current_input)

            if self.debug:
                print(f"[Debug Plan attempt {attempt+1}]: {json.dumps(plan, indent=2)}")

            if not plan.get("needs_tools") or not plan.get("steps"):
                direct = plan.get("direct_answer", "")
                if direct or attempt == 0:
                    return self._single_response(user_input, context_only=True) if direct else self._single_response(user_input)
                # On retry with no tools needed — use accumulated results if any
                break

            steps = plan.get("steps", [])[:MAX_AGENT_STEPS]
            step_results_this_attempt = []

            for i, step in enumerate(steps):
                tool = step.get("tool", "none")
                params = step.get("params", {})
                reason = step.get("reason", "")

                if tool == "none":
                    continue

                # Validate tool exists
                if tool not in VALID_TOOLS:
                    if self.debug:
                        print(f"[Debug] Unknown tool: {tool} — skipping")
                    failed_tools.append(tool)
                    continue

                # Inject previous step result into params if tool needs context
                # e.g. save_file content can come from previous search result
                if accumulated_results and tool == "save_file" and not params.get("content"):
                    params["content"] = accumulated_results[-1]["result"][:3000]

                if self.debug:
                    print(f"[Debug Step {i+1}]: {tool} — {reason}")

                result = self._execute_step(tool, params)

                if result and result.strip():
                    step_data = {
                        "step": len(accumulated_results) + len(step_results_this_attempt) + 1,
                        "tool": tool,
                        "reason": reason,
                        "result": result[:2000]
                    }
                    step_results_this_attempt.append(step_data)

                    if self.debug:
                        print(f"[Debug Result {i+1}]: {result[:200]}...")
                else:
                    failed_tools.append(tool)
                    if self.debug:
                        print(f"[Debug Step {i+1}]: {tool} returned empty")

            accumulated_results.extend(step_results_this_attempt)

            # If we got results this attempt, synthesize
            if step_results_this_attempt:
                break

            # No results this attempt — will replan if attempts remain
            if self.debug and attempt < MAX_REPLAN_ATTEMPTS:
                print(f"[Debug] No results on attempt {attempt+1}, replanning...")

        # Synthesize whatever we have
        if accumulated_results:
            return self._synthesize(user_input, accumulated_results)

        # Nothing worked after all attempts — fall back to direct response
        if self.debug:
            print("[Debug] All attempts exhausted, falling back to direct response")
        return self._single_response(user_input)

    def _plan(self, user_input: str) -> dict:
        """
        Use Groq native function calling (tool_choice='auto') for guaranteed structured output.
        Returns dict with tool_calls instead of parsing text JSON.
        """
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                max_tokens=600,
                temperature=0.1
            )
            
            # Extract tool calls from response
            tool_calls = []
            direct_answer = ""
            
            message = response.choices[0].message
            
            # If model provided tool calls, use them
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.type == "function":
                        tool_name = tool_call.function.name
                        # Parse function arguments (usually JSON string)
                        try:
                            args = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                        
                        # Validate tool
                        if tool_name in VALID_TOOLS:
                            tool_calls.append({
                                "tool": tool_name,
                                "params": args,
                                "reason": f"Tool call from model"
                            })
                        elif self.debug:
                            print(f"[Debug Planner] Unknown tool: {tool_name}")
            else:
                # Fallback: model returned text (no tool calls)
                # This means the task doesn't need tools
                direct_answer = message.content.strip() if message.content else ""
            
            return {
                "needs_tools": len(tool_calls) > 0,
                "steps": tool_calls,
                "direct_answer": direct_answer
            }
            
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
                return what_was_i_doing(int(params.get("minutes", 60)))
            if tool == "last_app_opened":
                return last_app_opened()
            if tool == "check_notifications":
                return check_notifications(params.get("app"), int(params.get("minutes", 60)))
            if tool == "get_whatsapp_messages":
                return get_whatsapp_messages(int(params.get("minutes", 120)))
            if tool == "send_whatsapp":
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
            if tool == "do_task":
                # Route to vision loop for phone automation
                from tools.vision_loop import run_vision_task
                task_desc = params.get("task", "")
                return run_vision_task(task_desc)
            if tool == "record_task":
                # Record task sequence for replay
                from tools.adb_control import record_task
                name = params.get("name", "")
                steps = params.get("steps", [])
                return record_task(name, steps)
            if tool == "replay_task":
                # Replay a recorded task
                from tools.adb_control import replay_task
                name = params.get("name", "")
                return replay_task(name)

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
        return self._call_groq_custom(messages, max_tokens=1000, temperature=0.85)

    def _call_groq_custom(self, messages: list, max_tokens: int = 1000, temperature: float = 0.85) -> str:
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
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
                        max_tokens=max_tokens,
                        temperature=temperature
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