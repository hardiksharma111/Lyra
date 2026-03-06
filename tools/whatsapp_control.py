import json
import os

def _load_key(name: str) -> str:
    with open("Keys.txt", "r") as f:
        for line in f:
            if line.startswith(name):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"{name} key not found in Keys.txt")

def save_contact(name: str, number: str) -> str:
    contacts_file = "memory/contacts.json"
    contacts = {}
    if os.path.exists(contacts_file):
        with open(contacts_file) as f:
            contacts = json.load(f)
    if not number.startswith("+"):
        number = "+91" + number.lstrip("0")
    contacts[name.lower()] = number
    os.makedirs("memory", exist_ok=True)
    with open(contacts_file, "w") as f:
        json.dump(contacts, f, indent=2)
    return f"Saved {name} as {number}"

def list_contacts() -> str:
    try:
        from tools.google_control import get_contacts
        contacts = get_contacts()
        if contacts:
            lines = [f"{c['name']}: {c.get('phone', 'no number')}" for c in contacts[:10]]
            return "Contacts:\n" + "\n".join(lines)
    except:
        pass
    return "No contacts found"

def send_sms(to: str, message: str) -> str:
    return "SMS coming in Phase 3.5 via Android"

def send_whatsapp(to: str, message: str) -> str:
    return "WhatsApp coming in Phase 3.5 via Android"

def send_to_self(message: str) -> str:
    return "Messaging coming in Phase 3.5 via Android"