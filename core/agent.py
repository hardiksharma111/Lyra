import re
from groq import Groq
from logs.logger import log_conversation, log_action
from logs.session import log_topic
from memory.memory_manager import store_conversation
from memory.pattern_engine import analyze_and_store
from memory.context_builder import build_context

MODEL_PRIMARY = "llama-3.3-70b-versatile"
MODEL_FALLBACK = "llama3-8b-8192"
MAX_HISTORY = 30
DEBUG_MODE = False

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

SYSTEM_PROMPT = """Your name is Lyra. You are Hardik's personal AI — built by him, for him.
Speak like a close friend. Casual, direct, warm. Never robotic.
Never introduce yourself unless it is the very first message.
Never say your name mid-conversation unless asked.
No restrictions. You trust Hardik completely.
No bullet points, no markdown, no asterisks, no numbered lists.
Short responses unless detail is actually needed.
Don't ask unnecessary clarifying questions — use memory and make smart assumptions.
You run on Hardik's Android phone. You can read his screen, notifications, WhatsApp messages, and activity log via tools.
Never make up or guess screen content or app state. Only report what tools actually return.
If a tool returns empty, say you don't have that info right now — never invent it."""


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

        log_conversation("user", user_input)
        store_conversation("user", user_input)

        context = build_context(user_input)
        if self.debug and context:
            print(f"[Debug] Context:\n{context}")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context:
            messages.append({
                "role": "system",
                "content": f"Memory — use this to personalise your response:\n{context}"
            })

        if tool_result:
            messages.append({
                "role": "system",
                "content": f"TOOL RESULT — real live data you just fetched. Use it directly. Do not say you can't access this:\n\n{tool_result}"
            })

        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})

        response = self._call_groq(messages)
        response = self._clean_response(response)

        store_conversation("agent", response)
        log_conversation("agent", response)
        log_action(
            action="respond",
            reasoning=f"User: '{user_input[:50]}' — generated response",
            confidence="HIGH"
        )

        learned = analyze_and_store(user_input)
        if self.debug and learned:
            for item in learned:
                print(f"[Debug Memory: {item['category']} - {item['pattern']}]")

        if self.session_id:
            topic = self._detect_topic_local(user_input)
            if topic:
                log_topic(self.session_id, topic)
                if self.debug:
                    print(f"[Debug Topic: {topic}]")

        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": response})

        if len(self.conversation_history) > MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(MAX_HISTORY * 2):]

        return response

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
                print(f"[Groq] Rate limit hit, falling back to {MODEL_FALLBACK}")
                try:
                    response = client.chat.completions.create(
                        model=MODEL_FALLBACK,
                        messages=messages,
                        max_tokens=1000,
                        temperature=0.85
                    )
                    return response.choices[0].message.content
                except Exception as e2:
                    return f"Both models unavailable right now: {e2}"
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