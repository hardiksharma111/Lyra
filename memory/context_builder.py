from memory.memory_manager import recall_relevant, recall_patterns
from memory.pattern_engine import get_all_categories
import ollama

MODEL = "llama3.2"

def build_context(user_input: str) -> str:
    # Builds a rich context string from memory and patterns
    # This gets injected into Lyra's prompt before every response
    context_parts = []

    # Step 1 — Recall relevant past conversations
    past_memories = recall_relevant(user_input, limit=5)
    if past_memories:
        context_parts.append("Relevant past conversations:")
        for mem in past_memories:
            context_parts.append(
                f"  [{mem['role']} at {mem['timestamp']}]: {mem['message']}"
            )

    # Step 2 — Recall relevant patterns across all categories
    categories = get_all_categories()
    relevant_patterns = []

    for category in categories:
        patterns = recall_patterns(category, limit=2)
        for p in patterns:
            # Only include patterns relevant to current input
            if _is_relevant(p, user_input):
                relevant_patterns.append(f"  [{category}]: {p}")

    if relevant_patterns:
        context_parts.append("\nKnown facts about the user:")
        context_parts.extend(relevant_patterns)

    # Step 3 — Build final context string
    if not context_parts:
        return ""

    return "\n".join(context_parts)

def _is_relevant(pattern: str, user_input: str) -> bool:
    # Quick check if a pattern is relevant to current input
    # Uses the model to judge relevance
    response = ollama.chat(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": f"""Is this known fact relevant to answering the user's current message?
Known fact: '{pattern}'
User message: '{user_input}'
Reply with YES or NO only."""
        }]
    )
    return "YES" in response['message']['content'].upper()