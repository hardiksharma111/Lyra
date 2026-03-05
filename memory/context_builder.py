from memory.memory_manager import recall_relevant, recall_patterns
from memory.pattern_engine import get_all_categories
from groq import Groq

MODEL = "llama-3.3-70b-versatile"

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

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

    # Collect all patterns first
    categories = get_all_categories()
    all_patterns = []
    for category in categories:
        patterns = recall_patterns(category, limit=2)
        for p in patterns:
            all_patterns.append({"category": category, "pattern": p})

    # ONE call to filter relevant patterns instead of one call per pattern
    if all_patterns:
        relevant = _batch_relevance_check(user_input, all_patterns)
        if relevant:
            context_parts.append("\nKnown facts about the user:")
            for item in relevant:
                context_parts.append(f"  [{item['category']}]: {item['pattern']}")

    if not context_parts:
        return ""

    return "\n".join(context_parts)

def _batch_relevance_check(user_input: str, patterns: list) -> list:
    # ONE call checks all patterns at once instead of one call per pattern
    if not patterns:
        return []

    patterns_text = "\n".join([
        f"{i+1}. [{p['category']}]: {p['pattern']}"
        for i, p in enumerate(patterns)
    ])

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""User's current message: '{user_input}'

Known facts about the user:
{patterns_text}

Which facts are relevant to answering the current message?
Reply with only the numbers of relevant facts, comma separated.
Example: 1, 3, 5
If none are relevant reply: NONE"""
            }],
            max_tokens=50
        )

        result = response.choices[0].message.content.strip()

        if result == "NONE":
            return []

        # Parse the numbers
        relevant = []
        for num in result.split(","):
            num = num.strip()
            if num.isdigit():
                idx = int(num) - 1
                if 0 <= idx < len(patterns):
                    relevant.append(patterns[idx])

        return relevant

    except Exception as e:
        print(f"[Context check skipped: {e}]")
        return []