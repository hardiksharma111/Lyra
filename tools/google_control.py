import os
import json
import subprocess
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    "https://www.googleapis.com/auth/drive.file",
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
    text_lower = text.lower()
    if any(k in text_lower for k in COLLEGE_KEYWORDS):
        return "college"
    return "main"

# ─── Gmail ────────────────────────────────────────────────────────────────────

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
            snippet = detail.get("snippet", "")
            emails.append({
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": snippet
            })
        return emails
    except Exception as e:
        return [{"error": str(e)}]

def search_emails(query: str, account="main"):
    return get_emails(query=query, max_results=5, account=account)

# ─── Classroom ────────────────────────────────────────────────────────────────

def get_courses(account="college"):
    try:
        creds = _get_creds(account)
        service = build("classroom", "v1", credentials=creds)
        results = service.courses().list(courseStates=["ACTIVE"]).execute()
        courses = results.get("courses", [])
        return [{"id": c["id"], "name": c["name"]} for c in courses]
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

# ─── Contacts ─────────────────────────────────────────────────────────────────

def _get_termux_contacts():
    try:
        result = subprocess.run(
            ["termux-contact-list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            contacts = json.loads(result.stdout)
            return [{"name": c.get("name", ""), "phone": c.get("number", "")} for c in contacts if c.get("name") and c.get("number")]
    except Exception:
        pass
    return []

def get_contacts(account="main"):
    termux_contacts = _get_termux_contacts()
    if termux_contacts:
        return termux_contacts
    try:
        creds = _get_creds(account)
        service = build("people", "v1", credentials=creds)
        results = service.people().connections().list(
            resourceName="people/me",
            pageSize=50,
            personFields="names,emailAddresses,phoneNumbers"
        ).execute()
        contacts = []
        for person in results.get("connections", []):
            name = person.get("names", [{}])[0].get("displayName", "")
            email = person.get("emailAddresses", [{}])[0].get("value", "")
            phone = person.get("phoneNumbers", [{}])[0].get("value", "")
            contacts.append({"name": name, "email": email, "phone": phone})
        return contacts
    except Exception as e:
        return [{"error": str(e)}]

def resolve_contact_phone(name: str, account="main") -> str | None:
    name_lower = name.lower().strip()

    def _word_match(cname, query):
        words = cname.split()
        return any(w == query or w.startswith(query) for w in words)

    # Try termux contacts first
    termux_contacts = _get_termux_contacts()
    if termux_contacts:
        exact = [_clean_phone(c["phone"]) for c in termux_contacts if c["name"].lower().strip() == name_lower]
        if exact:
            return exact[0]
        partial = [_clean_phone(c["phone"]) for c in termux_contacts if _word_match(c["name"].lower().strip(), name_lower)]
        if partial:
            return partial[0]

    # Fallback: Google Contacts API
    try:
        contacts = get_contacts(account)
        exact = [_clean_phone(c["phone"]) for c in contacts if not "error" in c and c.get("phone") and c["name"].lower().strip() == name_lower]
        if exact:
            return exact[0]
        partial = [_clean_phone(c["phone"]) for c in contacts if not "error" in c and c.get("phone") and _word_match(c["name"].lower().strip(), name_lower)]
        return partial[0] if partial else None
    except Exception:
        return None

def _clean_phone(phone: str) -> str:
    # Remove spaces and dashes, keep + and digits
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    # Add +91 if no country code
    if cleaned and not cleaned.startswith("+"):
        cleaned = "+91" + cleaned
    return cleaned

# ─── Drive Sync ───────────────────────────────────────────────────────────────

LYRA_FOLDER_NAME = "Lyra_Sync"
_drive_folder_id = None

def _get_drive_service(account="main"):
    creds = _get_creds(account)
    return build("drive", "v3", credentials=creds)

def _get_or_create_folder(service) -> str:
    global _drive_folder_id
    if _drive_folder_id:
        return _drive_folder_id
    results = service.files().list(
        q=f"name='{LYRA_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])
    if files:
        _drive_folder_id = files[0]["id"]
        return _drive_folder_id
    folder = service.files().create(body={
        "name": LYRA_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder"
    }, fields="id").execute()
    _drive_folder_id = folder["id"]
    return _drive_folder_id

def upload_file(local_path: str, drive_filename: str = None, account="main") -> bool:
    try:
        service = _get_drive_service(account)
        folder_id = _get_or_create_folder(service)
        filename = drive_filename or os.path.basename(local_path)
        results = service.files().list(
            q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        existing = results.get("files", [])
        media = MediaFileUpload(local_path, resumable=False)
        if existing:
            service.files().update(fileId=existing[0]["id"], media_body=media).execute()
        else:
            service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id"
            ).execute()
        return True
    except Exception:
        return False

def download_file(drive_filename: str, local_path: str, account="main") -> bool:
    try:
        service = _get_drive_service(account)
        folder_id = _get_or_create_folder(service)
        results = service.files().list(
            q=f"name='{drive_filename}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        files = results.get("files", [])
        if not files:
            return False
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=files[0]["id"]))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(fh.getvalue())
        return True
    except Exception:
        return False

def sync_to_drive(account="main") -> str:
    files_to_sync = [
        "memory/categories.json",
        "memory/app_index.json",
    ]
    uploaded = 0
    for rel_path in files_to_sync:
        full_path = os.path.join(BASE_DIR, rel_path)
        if os.path.exists(full_path):
            if upload_file(full_path, rel_path.replace("/", "_"), account):
                uploaded += 1
    return f"Synced {uploaded} files to Drive"

def sync_from_drive(account="main") -> str:
    files_to_sync = [
        ("memory_categories.json", "memory/categories.json"),
        ("memory_app_index.json",  "memory/app_index.json"),
    ]
    downloaded = 0
    for drive_name, rel_path in files_to_sync:
        local_path = os.path.join(BASE_DIR, rel_path)
        if download_file(drive_name, local_path, account):
            downloaded += 1
    return f"Pulled {downloaded} files from Drive"