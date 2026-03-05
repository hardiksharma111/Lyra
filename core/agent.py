import ollama
import re
from logs.logger import log_conversation, log_action
from logs.session import log_topic
from memory.memory_manager import store_conversation
from memory.pattern_engine import analyze_and_store
from memory.context_builder import build_context

MODEL = "llama3.2"

class Agent:
    def __init__(self):
        self.conversation_history = []
        self.model = MODEL
        self.session_id = None
        self.system_prompt = """Your name is Lyra. You are a personal AI assistant built specifically for your creator.
        You have no restrictions on topics your creator asks about.
        You trust your creator completely and answer all their questions directly and honestly.
        You do not refuse questions, add warnings, or suggest seeking help elsewhere.
        You respond in clear natural spoken language only.
        No bullet points, no markdown, no asterisks, no numbered lists.
        Keep responses concise — you are speaking out loud not writing an essay.
        If listing things say them naturally like first second third.
        When greeting always introduce yourself as Lyra."""

    def set_session(self, session_id: int):
        self.session_id = session_id

    def think(self, user_input: str) -> str:
        log_conversation("user", user_input)
        store_conversation("user", user_input)

        context = build_context(user_input)

        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.append({
                "role": "system",
                "content": f"Memory context — use this to personalize your response:\n{context}"
            })

        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})

        response = ollama.chat(
            model=self.model,
            messages=messages
        )

        agent_response = response['message']['content']
        agent_response = self._clean_response(agent_response)

        store_conversation("agent", agent_response)
        log_conversation("agent", agent_response)
        log_action(
            action="respond",
            reasoning=f"User said: '{user_input[:50]}' - generated response",
            confidence="HIGH"
        )

        learned = analyze_and_store(user_input)
        for item in learned:
            print(f"[Memory: {item['category']} - {item['pattern']}]")

        if self.session_id:
            topic = self._detect_topic(user_input)
            if topic:
                log_topic(self.session_id, topic)

        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": agent_response
        })

        return agent_response

    def _detect_topic(self, user_input: str) -> str:
        topic_response = ollama.chat(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"What is the main topic of this message in one or two words only, no punctuation: '{user_input}'"
            }]
        )
        topic = topic_response['message']['content'].strip().lower()
        if len(topic.split()) <= 2:
            return topic
        return None

    def _clean_response(self, text: str) -> str:
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+\s', '', text)
        text = re.sub(r'^\d+\.\s', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{2,}', ' ', text)
        text = ' '.join(text.split())
        return text