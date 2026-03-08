import os
import json
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/contacts.readonly',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly'
    "https://www.googleapis.com/auth/drive.file",
]

ACCOUNTS = {
    "main":    "memory/google_token_main.json",
    "college": "memory/google_token_college.json",
}

def _get_creds(account: str = "main") -> Credentials:
    token_file = ACCOUNTS.get(account, ACCOUNTS["main"])
    if not os.path.exists(token_file):
        raise FileNotFoundError(f"Token not found for account '{account}'. Run setup_google.py first.")
    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, 'w') as f:
            f.write(creds.to_json())
    return creds

def _detect_account(context: str) -> str:
    context_lower = context.lower()
    college_keywords = ["college", "classroom", "assignment", "university", "school", "edu"]
    for keyword in college_keywords:
        if keyword in context_lower:
            return "college"
    return "main"

# ─── CONTACTS ───────────────────────────────────────────

def get_contacts(query: str = "", account: str = "main") -> list:
    try:
        creds = _get_creds(account)
        service = build('people', 'v1', credentials=creds)
        results = service.people().connections().list(
            resourceName='people/me',
            pageSize=100,
            personFields='names,phoneNumbers,emailAddresses'
        ).execute()

        connections = results.get('connections', [])
        contacts = []
        for person in connections:
            names = person.get('names', [])
            phones = person.get('phoneNumbers', [])
            emails = person.get('emailAddresses', [])

            name = names[0]['displayName'] if names else 'Unknown'
            phone = phones[0]['value'] if phones else None
            email = emails[0]['value'] if emails else None

            if query.lower() in name.lower() or not query:
                contacts.append({
                    "name": name,
                    "phone": phone,
                    "email": email
                })

        return contacts
    except Exception as e:
        return []

def find_contact(name: str) -> dict | None:
    # Search main first then college
    for account in ["main", "college"]:
        contacts = get_contacts(query=name, account=account)
        if contacts:
            return contacts[0]
    return None

def get_contact_number(name: str) -> str | None:
    contact = find_contact(name)
    if contact and contact.get("phone"):
        phone = contact["phone"].replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = "+91" + phone.lstrip("0")
        return phone
    return None

# ─── GMAIL ───────────────────────────────────────────────

def get_recent_emails(count: int = 5, account: str = None, context: str = "") -> str:
    try:
        if account is None:
            account = _detect_account(context)

        creds = _get_creds(account)
        service = build('gmail', 'v1', credentials=creds)

        results = service.users().messages().list(
            userId='me',
            maxResults=count,
            labelIds=['INBOX']
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            return f"No emails found in {account} inbox"

        email_list = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
            sender = headers.get('From', 'Unknown')
            subject = headers.get('Subject', 'No subject')
            date = headers.get('Date', '')

            # Clean up sender
            if '<' in sender:
                sender = sender.split('<')[0].strip()

            email_list.append(f"From: {sender}\nSubject: {subject}\nDate: {date}")

        return f"Recent emails ({account}):\n\n" + "\n\n".join(email_list)

    except Exception as e:
        return f"Could not read emails: {e}"

def read_email_content(index: int = 0, account: str = None, context: str = "") -> str:
    try:
        if account is None:
            account = _detect_account(context)

        creds = _get_creds(account)
        service = build('gmail', 'v1', credentials=creds)

        results = service.users().messages().list(
            userId='me',
            maxResults=10,
            labelIds=['INBOX']
        ).execute()

        messages = results.get('messages', [])
        if not messages or index >= len(messages):
            return "Email not found"

        msg_data = service.users().messages().get(
            userId='me',
            id=messages[index]['id'],
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
        sender = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No subject')

        # Extract body
        body = ""
        payload = msg_data['payload']

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        elif payload['body'].get('data'):
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8')

        # Trim long emails
        if len(body) > 1000:
            body = body[:1000] + "...[truncated]"

        return f"From: {sender}\nSubject: {subject}\n\n{body}"

    except Exception as e:
        return f"Could not read email: {e}"

def search_emails(query: str, account: str = None) -> str:
    try:
        if account is None:
            account = _detect_account(query)

        creds = _get_creds(account)
        service = build('gmail', 'v1', credentials=creds)

        results = service.users().messages().list(
            userId='me',
            maxResults=5,
            q=query
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            return f"No emails found for '{query}'"

        email_list = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
            sender = headers.get('From', 'Unknown')
            if '<' in sender:
                sender = sender.split('<')[0].strip()
            subject = headers.get('Subject', 'No subject')
            email_list.append(f"From: {sender} — {subject}")

        return f"Found {len(email_list)} emails:\n" + "\n".join(email_list)

    except Exception as e:
        return f"Could not search emails: {e}"

# ─── GOOGLE CLASSROOM ────────────────────────────────────

def get_assignments(account: str = "college") -> str:
    try:
        creds = _get_creds(account)
        service = build('classroom', 'v1', credentials=creds)

        courses = service.courses().list(
            studentId='me',
            courseStates=['ACTIVE']
        ).execute().get('courses', [])

        if not courses:
            return "No active courses found"

        all_assignments = []

        for course in courses:
            course_name = course['name']
            course_id = course['id']

            try:
                work = service.courses().courseWork().list(
                    courseId=course_id
                ).execute().get('courseWork', [])

                for item in work:
                    title = item.get('title', 'No title')
                    due = item.get('dueDate', None)

                    due_str = "No due date"
                    if due:
                        due_str = f"{due.get('day', '?')}/{due.get('month', '?')}/{due.get('year', '?')}"

                    all_assignments.append(
                        f"[{course_name}] {title} — Due: {due_str}"
                    )
            except:
                continue

        if not all_assignments:
            return "No assignments found"

        return "Assignments:\n" + "\n".join(all_assignments[:15])

    except Exception as e:
        return f"Could not get assignments: {e}"

def get_courses(account: str = "college") -> str:
    try:
        creds = _get_creds(account)
        service = build('classroom', 'v1', credentials=creds)

        courses = service.courses().list(
            studentId='me',
            courseStates=['ACTIVE']
        ).execute().get('courses', [])

        if not courses:
            return "No active courses found"

        names = [c['name'] for c in courses]
        return "Your courses: " + ", ".join(names)

    except Exception as e:
        return f"Could not get courses: {e}"