import os
import json
import subprocess
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS_FILE = os.path.join(BASE_DIR, "google_credentials.json")
TOKEN_MAIN = os.path.join(BASE_DIR, "memory", "google_token_main.json")
TOKEN_COLLEGE = os.path.join(BASE_DIR, "memory", "google_token_college.json")

COLLEGE_KEYWORDS = ["college", "assignment", "classroom", "course", "homework", "submit", "professor", "lecture"]


def _get_token_path(account="main"):
    return TOKEN_COLLEGE if account == "college" else TOKEN_MAIN


def _get_creds(account="main"):
    token_path = _get_token_path(account)
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def detect_account(text: str) -> str:
    return "college" if any(k in text.lower() for k in COLLEGE_KEYWORDS) else "main"


# ── Gmail ─────────────────────────────────────────────────────────────────────

def get_emails(query="", max_results=5, account="main"):
    try:
        creds = _get_creds(account)
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        emails = []
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            emails.append({
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": detail.get("snippet", "")
            })
        return emails
    except Exception as e:
        return [{"error": str(e)}]


def search_emails(query: str, account="main"):
    return get_emails(query=query, max_results=5, account=account)


# ── Classroom ─────────────────────────────────────────────────────────────────

def get_courses(account="college"):
    try:
        creds = _get_creds(account)
        service = build("classroom", "v1", credentials=creds)
        results = service.courses().list(courseStates=["ACTIVE"]).execute()
        return [{"id": c["id"], "name": c["name"]} for c in results.get("courses", [])]
    except Exception as e:
        return [{"error": str(e)}]


def get_assignments(account="college"):
    try:
        creds = _get_creds(account)
        service = build("classroom", "v1", credentials=creds)
        courses = service.courses().list(courseStates=["ACTIVE"]).execute().get("courses", [])
        assignments = []
        for course in courses[:5]:
            works = service.courses().courseWork().list(
                courseId=course["id"], orderBy="dueDate desc"
            ).execute().get("courseWork", [])
            for w in works[:3]:
                due = w.get("dueDate", {})
                due_str = f"{due.get('year','?')}-{due.get('month','?')}-{due.get('day','?')}" if due else "No due date"
                assignments.append({
                    "course": course["name"],
                    "title": w.get("title", ""),
                    "due": due_str,
                    "state": w.get("state", "")
                })
        return assignments
    except Exception as e:
        return [{"error": str(e)}]


# ── Contacts ──────────────────────────────────────────────────────────────────

def _get_termux_contacts():
    try:
        result = subprocess.run(
            ["termux-contact-list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            contacts = json.loads(result.stdout)
            return [
                {"name": c.get("name", ""), "phone": c.get("number", "")}
                for c in contacts if c.get("name") and c.get("number")
            ]
    except Exception:
        pass
    return []


def _clean_phone(phone: str) -> str:
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    if cleaned and not cleaned.startswith("+"):
        cleaned = "+91" + cleaned
    return cleaned


def resolve_contact_phone(name: str) -> str | None:
    name_lower = name.lower().strip()

    def word_match(cname, query):
        return any(w == query or w.startswith(query) for w in cname.split())

    contacts = _get_termux_contacts()
    exact = [_clean_phone(c["phone"]) for c in contacts if c["name"].lower().strip() == name_lower]
    if exact:
        return exact[0]
    partial = [_clean_phone(c["phone"]) for c in contacts if word_match(c["name"].lower().strip(), name_lower)]
    return partial[0] if partial else None