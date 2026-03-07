import re
from memory.memory_manager import recall_relevant, recall_patterns
from memory.pattern_engine import get_all_categories

def build_context(user_input: str) -> str:
    context_parts = []

    # Past conversations
    past_memories = recall_relevant(user_input, limit=3)
    if past_memories:
        context_parts.append("Relevant past conversations:")
        for mem in past_memories:
            context_parts.append(
                f"  [{mem['role']} at {mem['timestamp']}]: {mem['message']}"
            )

    # Collect all patterns
    categories = get_all_categories()
    all_patterns = []
    for category in categories:
        patterns = recall_patterns(category, limit=2)
        for p in patterns:
            all_patterns.append({"category": category, "pattern": p})

    # Local relevance scoring — no API call
    if all_patterns:
        relevant = _local_relevance_check(user_input, all_patterns)
        if relevant:
            context_parts.append("\nKnown facts about the user:")
            for item in relevant:
                context_parts.append(f"  [{item['category']}]: {item['pattern']}")

    if not context_parts:
        return ""

    return "\n".join(context_parts)

def _local_relevance_check(user_input: str, patterns: list) -> list:
    """Score pattern relevance locally using keyword overlap.
    No API call — fast, free, runs on any platform."""

    if not patterns:
        return []

    # Extract meaningful words from user input
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
        "gotta", "kinda", "dont", "im", "ive", "whats", "thats",
    }

    input_words = set(re.findall(r'\w+', user_input.lower()))
    input_words -= stop_words

    if not input_words:
        # No meaningful words — return top 3 most recent patterns as general context
        return patterns[:3]

    scored = []
    for pattern in patterns:
        pattern_text = f"{pattern['category']} {pattern['pattern']}".lower()
        pattern_words = set(re.findall(r'\w+', pattern_text))
        pattern_words -= stop_words

        # Score = number of overlapping meaningful words
        overlap = len(input_words & pattern_words)

        # Boost score for category match
        category_words = set(re.findall(r'\w+', pattern['category'].lower()))
        category_overlap = len(input_words & category_words)
        score = overlap + (category_overlap * 2)

        if score > 0:
            scored.append((score, pattern))

    if not scored:
        # No keyword matches — include personality/preference patterns as fallback
        fallback_categories = {"personality", "preferences", "habits", "food", "music"}
        fallback = [p for p in patterns if p["category"].lower() in fallback_categories]
        return fallback[:3]

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:5]]