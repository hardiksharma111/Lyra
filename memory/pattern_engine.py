from memory.memory_manager import store_pattern, recall_patterns
import ollama
import json
import os

MODEL = "llama3.2"

# Seed categories — Lyra starts with these but can create more
DEFAULT_CATEGORIES = [
    "preferences",
    "habits",
    "schedule",
    "personality",
    "goals",
    "people",
]

CATEGORIES_FILE = "memory/categories.json"

def _load_categories() -> list:
    # Load categories from file — includes any Lyra created herself
    if not os.path.exists(CATEGORIES_FILE):
        _save_categories(DEFAULT_CATEGORIES)
        return DEFAULT_CATEGORIES.copy()

    with open(CATEGORIES_FILE, "r") as f:
        return json.load(f)

def _save_categories(categories: list):
    os.makedirs("memory", exist_ok=True)
    with open(CATEGORIES_FILE, "w") as f:
        json.dump(categories, f, indent=2)

def _create_new_category(user_input: str, existing_categories: list) -> str:
    # Asks Lyra if a new category is needed for this input
    response = ollama.chat(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": f"""You are analyzing user input to categorize personal information.
Existing categories: {', '.join(existing_categories)}

User message: '{user_input}'

Does this message contain personal information that doesn't fit any existing category?
If yes, respond with: NEWCAT: [single word category name in lowercase]
If no, respond with: NONE
Only respond with NEWCAT or NONE, nothing else."""
        }]
    )

    result = response['message']['content'].strip()

    if result.startswith("NEWCAT:"):
        new_cat = result.replace("NEWCAT:", "").strip().lower()
        # Validate — single word, no special characters
        if new_cat and " " not in new_cat and new_cat.isalpha():
            return new_cat

    return None

def analyze_and_store(user_input: str) -> list:
    learned = []
    categories = _load_categories()

    # Check if a new category is needed
    new_category = _create_new_category(user_input, categories)
    if new_category and new_category not in categories:
        categories.append(new_category)
        _save_categories(categories)
        print(f"[Memory: created new category '{new_category}']")

    # Check all categories including any new one
    for category in categories:
        result = _check_category(user_input, category)
        if result:
            store_pattern(result, category=category)
            learned.append({"category": category, "pattern": result})

    return learned

def _check_category(user_input: str, category: str) -> str:
    response = ollama.chat(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": f"""Does this message reveal anything about the user's {category}?
Message: '{user_input}'
If yes, respond with one clear factual sentence starting with 'User'
If no, respond with NONE
Only respond with the sentence or NONE, nothing else."""
        }]
    )

    result = response['message']['content'].strip()

    if result == "NONE" or not result.startswith("User"):
        return None

    return result

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