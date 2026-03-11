from memory.memory_manager import store_pattern, recall_patterns
from groq import Groq
import json
import os

MODEL = "llama-3.3-70b-versatile"

# Categories that should never be created
BLACKLISTED_CATEGORIES = ["none", "null", "na", "n/a", "other", "misc", "miscellaneous"]

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

client = Groq(api_key=_load_key("GROQ"))

DEFAULT_CATEGORIES = [
    "preferences", "habits", "schedule",
    "personality", "goals", "people",
]

CATEGORIES_FILE = "memory/categories.json"

def _load_categories() -> list:
    if not os.path.exists(CATEGORIES_FILE):
        _save_categories(DEFAULT_CATEGORIES)
        return DEFAULT_CATEGORIES.copy()
    with open(CATEGORIES_FILE, "r") as f:
        data = json.load(f)
        # Clean out any blacklisted categories that snuck in
        return [c for c in data if c not in BLACKLISTED_CATEGORIES]

def _save_categories(categories: list):
    os.makedirs("memory", exist_ok=True)
    clean = [c for c in categories if c not in BLACKLISTED_CATEGORIES]
    with open(CATEGORIES_FILE, "w") as f:
        json.dump(clean, f, indent=2)

def analyze_and_store(user_input: str) -> list:
    categories = _load_categories()
    response = _single_analysis_call(user_input, categories)
    if not response:
        return []

    learned = []

    if "NEWCAT:" in response:
        for line in response.split("\n"):
            if line.startswith("NEWCAT:"):
                new_cat = line.replace("NEWCAT:", "").strip().lower()
                if (new_cat and
                    " " not in new_cat and
                    new_cat.isalpha() and
                    new_cat not in categories and
                    new_cat not in BLACKLISTED_CATEGORIES):
                    categories.append(new_cat)
                    _save_categories(categories)

    for line in response.split("\n"):
        for category in categories:
            prefix = f"{category.upper()}:"
            if line.startswith(prefix):
                pattern = line.replace(prefix, "").strip()
                if pattern and pattern != "NONE" and pattern.startswith("User"):
                    store_pattern(pattern, category=category)
                    learned.append({"category": category, "pattern": pattern})

    return learned

def _single_analysis_call(user_input: str, categories: list) -> str:
    categories_str = ", ".join(categories)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": f"""Analyze this message and extract personal information about the user.

Message: '{user_input}'

Existing categories: {categories_str}

Instructions:
1. For each category, if the message reveals something write: CATEGORYNAME: User [fact]
2. If nothing relevant for a category write: CATEGORYNAME: NONE
3. If the message contains info that needs a NEW category write: NEWCAT: [single word]
4. Keep each fact to one sentence starting with 'User'

Respond in this exact format, one line per category:
{chr(10).join([f"{c.upper()}: " for c in categories])}
NEWCAT: NONE"""
            }],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return None

def get_profile_summary() -> dict:
    categories = _load_categories()
    profile = {}
    for category in categories:
        patterns = recall_patterns(category, limit=10)
        if patterns:
            profile[category] = patterns
    return profile

def print_profile():
    profile = get_profile_summary()
    if not profile:
        print("No patterns learned yet.")
        return
    print("\n--- Lyra's Profile of You ---")
    for category, patterns in profile.items():
        print(f"\n{category.upper()}:")
        for p in patterns:
            print(f"  - {p}")
    print("-----------------------------\n")

def get_all_categories() -> list:
    return _load_categories()