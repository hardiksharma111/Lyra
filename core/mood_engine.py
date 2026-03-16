import re
from datetime import datetime

MOODS = {
    "focused":   "Concise, minimal, no small talk. Direct answers only.",
    "casual":    "Relaxed, conversational, light. Can joke around.",
    "concerned": "Gentle, supportive, careful. Something seems off.",
    "alert":     "Sharp, clear, prioritized. Something important is happening.",
    "curious":   "Exploratory, enthusiastic. Engage with ideas naturally.",
    "playful":   "Light, witty, a bit teasing. Late night energy.",
}

SARCASM_PATTERNS = [
    "cool cool cool", "yeah sure", "totally", "oh great", "wow amazing",
    "thanks a lot", "fantastic", "oh perfect", "great job", "very helpful",
    "love that", "awesome", "sure sure", "definitely", "oh wonderful",
]

_message_history = []
_learned_sarcasm = []


def record_message(text: str):
    global _message_history
    _message_history.append({
        "text": text,
        "time": datetime.now(),
        "length": len(text.split()),
    })
    _message_history = _message_history[-10:]


def detect_mood(user_input: str) -> str:
    now = datetime.now()
    hour = now.hour
    text_lower = user_input.lower().strip()
    words = text_lower.split()
    word_count = len(words)

    is_late_night = hour >= 23 or hour <= 4
    is_work_hours = 9 <= hour <= 18

    is_very_short = word_count <= 2
    is_long = word_count >= 20

    rapid_messages = False
    if len(_message_history) >= 3:
        recent = _message_history[-3:]
        diffs = [(recent[i]["time"] - recent[i-1]["time"]).total_seconds() for i in range(1, len(recent))]
        if all(d < 15 for d in diffs):
            rapid_messages = True

    distress_words = [
        "sad", "depressed", "anxious", "stressed", "overwhelmed", "tired",
        "exhausted", "lonely", "lost", "failing", "hopeless", "cant", "can't",
        "don't know", "idk", "help me", "what do i do", "not okay", "feel bad",
    ]
    has_distress = any(w in text_lower for w in distress_words)

    focus_words = [
        "study", "assignment", "deadline", "exam", "code", "debug",
        "project", "submit", "lecture", "class", "work", "task", "fix",
    ]
    has_focus = any(w in text_lower for w in focus_words)

    alert_words = [
        "urgent", "asap", "emergency", "important", "critical",
        "now", "quick", "fast", "hurry", "immediately",
    ]
    has_alert = any(w in text_lower for w in alert_words)

    curious_words = [
        "how does", "why does", "explain", "what is", "tell me about",
        "curious", "wondering", "interesting", "what if", "hypothetically",
    ]
    has_curiosity = any(w in text_lower for w in curious_words)

    # Priority order
    if has_distress:
        return "concerned"
    if has_curiosity and is_long:
        return "curious"
    if has_alert and not has_curiosity:
        return "alert"
    if has_focus and is_work_hours:
        return "focused"
    if is_late_night and (is_very_short or rapid_messages):
        return "playful"
    if rapid_messages and is_very_short:
        return "casual"
    if has_focus:
        return "focused"
    if is_late_night:
        return "playful"
    return "casual"


def detect_sarcasm(user_input: str) -> bool:
    text_lower = user_input.lower().strip()
    for pattern in SARCASM_PATTERNS + _learned_sarcasm:
        if pattern in text_lower:
            return True
    return False


def learn_sarcasm(phrase: str):
    phrase = phrase.lower().strip()
    if phrase and phrase not in _learned_sarcasm and phrase not in SARCASM_PATTERNS:
        _learned_sarcasm.append(phrase)


def get_time_context() -> str:
    hour = datetime.now().hour
    if 5 <= hour <= 8:
        return "early morning"
    if 9 <= hour <= 12:
        return "morning"
    if 13 <= hour <= 17:
        return "afternoon"
    if 18 <= hour <= 22:
        return "evening"
    return "late night"


def get_mood_instruction(mood: str) -> str:
    return MOODS.get(mood, MOODS["casual"])


def build_mood_context(user_input: str) -> dict:
    record_message(user_input)
    mood = detect_mood(user_input)
    is_sarcastic = detect_sarcasm(user_input)
    time_ctx = get_time_context()
    tone = get_mood_instruction(mood)
    return {
        "mood": mood,
        "sarcastic": is_sarcastic,
        "time": time_ctx,
        "tone_instruction": tone,
    }   