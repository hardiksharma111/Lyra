import re
from memory.memory_manager import recall_relevant, recall_patterns
from memory.pattern_engine import get_all_categories

# Minimum word overlap score to include a memory
MEMORY_THRESHOLD = 2
PATTERN_THRESHOLD = 2


def build_context(user_input: str) -> str:
    context_parts = []
    input_words = _meaningful_words(user_input)

    # Only pull past conversations if strong keyword match
    if input_words:
        past_memories = recall_relevant(user_input, limit=5)
        strong_memories = [
            m for m in past_memories
            if _score(input_words, m.get("message", "")) >= MEMORY_THRESHOLD
        ]
        if strong_memories:
            context_parts.append("Relevant past conversations:")
            for mem in strong_memories[:3]:
                context_parts.append(
                    f"  [{mem['role']} at {mem['timestamp']}]: {mem['message']}"
                )

    # Only inject patterns with strong relevance
    categories = get_all_categories()
    all_patterns = []
    for category in categories:
        patterns = recall_patterns(category, limit=2)
        for p in patterns:
            all_patterns.append({"category": category, "pattern": p})

    if all_patterns and input_words:
        relevant = _score_patterns(input_words, all_patterns)
        if relevant:
            context_parts.append("\nKnown facts about you:")
            for item in relevant:
                context_parts.append(f"  [{item['category']}]: {item['pattern']}")

    return "\n".join(context_parts) if context_parts else ""


def _meaningful_words(text: str) -> set:
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
        "tell", "give", "show", "find", "look", "get", "let", "know",
        "name", "list", "thing", "things", "something", "anything",
    }
    words = set(re.findall(r'\w+', text.lower()))
    return words - stop_words


def _score(input_words: set, text: str) -> int:
    text_words = set(re.findall(r'\w+', text.lower()))
    return len(input_words & text_words)


def _score_patterns(input_words: set, patterns: list) -> list:
    scored = []
    for pattern in patterns:
        pattern_text = f"{pattern['category']} {pattern['pattern']}".lower()
        pattern_words = set(re.findall(r'\w+', pattern_text))
        category_words = set(re.findall(r'\w+', pattern['category'].lower()))

        overlap = len(input_words & pattern_words)
        category_overlap = len(input_words & category_words)
        score = overlap + (category_overlap * 2)

        if score >= PATTERN_THRESHOLD:
            scored.append((score, pattern))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:4]]