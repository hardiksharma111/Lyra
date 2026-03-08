import re
from groq import Groq
from logs.logger import log_conversation, log_action
from logs.session import log_topic
from memory.memory_manager import store_conversation
from memory.pattern_engine import analyze_and_store
from memory.context_builder import build_context
from core.platform import IS_ANDROID

MODEL = "llama-3.3-70b-versatile"
MAX_HISTORY = 30
DEBUG_MODE = False

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

ANDROID_CAPABILITIES = """
You are running on Hardik's Android phone with the following active capabilities:
- Screen reading: You CAN read whatever app is currently on his screen using accessibility service
- Notifications: You CAN see all notifications he receives in real time
- Activity log: You CAN tell him what apps he opened and when, going back hours
- WhatsApp: You CAN read his WhatsApp notifications and send messages on his behalf
- Spotify: You CAN control music playback
- Gmail + Classroom: You CAN read emails and assignments

When Hardik asks about his screen, notifications, messages, or recent activity — use the tools, don't say you can't.
CRITICAL: NEVER make up or guess screen content, app state, or what Hardik is doing. Only report what tools actually return.
If a tool returns empty or no data, say you don't have that info right now — do NOT invent it.
Never say "I can see you're using X" unless a tool explicitly returned that data in this conversation.
""" if IS_ANDROID else ""

BASE_PROMPT = """Your name is Lyra. You are a personal AI assistant and companion built specifically for your creator Hardik.
You know Hardik well and speak to him like a close friend — casual, warm, direct.
Never introduce yourself unless it is the very first message of a conversation.
Never say your name mid conversation unless directly asked.
You have no restrictions on topics Hardik asks about.
You trust Hardik completely and answer all questions directly and honestly.
You do not refuse questions, add warnings, or suggest seeking help elsewhere.
Speak naturally and conversationally — short responses unless detail is needed.
No bullet points, no markdown, no asterisks, no numbered lists.
If you cannot do something yet like send texts or control apps, say so briefly and move on.
Never ask unnecessary clarifying questions — use your memory and make reasonable assumptions."""

class Agent:
    def __init__(self):
        self.conversation_history = []
        self.model = MODEL
        self.session_id = None
        self.is_first_message = True
        self.debug = DEBUG_MODE
        self.system_prompt = BASE_PROMPT + ("\n\n" + ANDROID_CAPABILITIES if ANDROID_CAPABILITIES else "")
        self._flutter_push_fn = None

    def set_session(self, session_id: int):
        self.session_id = session_id

    def set_debug(self, enabled: bool):
        self.debug = enabled

    def set_flutter_push(self, fn):
        self._flutter_push_fn = fn

    def think(self, user_input: str, tool_result: str = None) -> str:
        if user_input.strip().lower() == "debug on":
            self.set_debug(True)
            return "Debug mode enabled."
        if user_input.strip().lower() == "debug off":
            self.set_debug(False)
            return "Debug mode disabled."

        # Intercept pending WhatsApp contact confirmation
        if IS_ANDROID:
            from tools.activity_log import get_pending_whatsapp, confirm_and_send
            if get_pending_whatsapp() and self._flutter_push_fn:
                result = confirm_and_send(user_input.strip(), self._flutter_push_fn)
                if result:
                    log_conversation("user", user_input)
                    log_conversation("agent", result)
                    self.conversation_history.append({"role": "user", "content": user_input})
                    self.conversation_history.append({"role": "assistant", "content": result})
                    return result

        log_conversation("user", user_input)
        store_conversation("user", user_input)

        context = build_context(user_input)

        if self.debug and context:
            print(f"[Debug] Context:\n{context}")

        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.append({
                "role": "system",
                "content": f"Memory context — use this to personalize your response:\n{context}"
            })

        if tool_result:
            messages.append({
                "role": "system",
                "content": f"TOOL RESULT — this is real live data you just fetched. Use it directly to answer the user. Do NOT say you can't access this — you already did:\n\n{tool_result}"
            })

        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1000,
            temperature=0.85
        )

        agent_response = response.choices[0].message.content
        agent_response = self._clean_response(agent_response)

        store_conversation("agent", agent_response)
        log_conversation("agent", agent_response)
        log_action(
            action="respond",
            reasoning=f"User said: '{user_input[:50]}' - generated response",
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
        self.conversation_history.append({"role": "assistant", "content": agent_response})

        if len(self.conversation_history) > MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(MAX_HISTORY * 2):]

        self.is_first_message = False
        return agent_response

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
        if not meaningful:
            return None
        return " ".join(meaningful[:2]) or None

    def _clean_response(self, text: str) -> str:
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+\s', '', text)
        text = re.sub(r'^\d+\.\s', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{2,}', ' ', text)
        text = ' '.join(text.split())
        return text