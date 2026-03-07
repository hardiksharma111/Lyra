import os
import json
import time
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYNC_FILES = [
    "memory/categories.json",
    "memory/app_index.json",
]

SYNC_FOLDER_NAME = "Lyra_Sync"
_sync_folder_id = None
_last_sync_time = 0
SYNC_INTERVAL = 300  # sync every 5 minutes


def _get_drive_service(account="main"):
    try:
        from tools.google_control import get_credentials
        creds = get_credentials(account)
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        return None


def _get_or_create_folder(service):
    global _sync_folder_id
    if _sync_folder_id:
        return _sync_folder_id
    try:
        res = service.files().list(
            q=f"name='{SYNC_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)"
        ).execute()
        files = res.get("files", [])
        if files:
            _sync_folder_id = files[0]["id"]
            return _sync_folder_id
        # Create folder
        meta = {"name": SYNC_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=meta, fields="id").execute()
        _sync_folder_id = folder["id"]
        return _sync_folder_id
    except Exception:
        return None


def _upload_file(service, folder_id, local_path, remote_name):
    try:
        from googleapiclient.http import MediaFileUpload
        # Check if file already exists
        res = service.files().list(
            q=f"name='{remote_name}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        files = res.get("files", [])
        media = MediaFileUpload(local_path, resumable=False)
        if files:
            service.files().update(fileId=files[0]["id"], media_body=media).execute()
        else:
            meta = {"name": remote_name, "parents": [folder_id]}
            service.files().create(body=meta, media_body=media, fields="id").execute()
        return True
    except Exception:
        return False


def _download_file(service, folder_id, remote_name, local_path):
    try:
        res = service.files().list(
            q=f"name='{remote_name}' and '{folder_id}' in parents and trashed=false",
            fields="files(id, modifiedTime)"
        ).execute()
        files = res.get("files", [])
        if not files:
            return False
        file_id = files[0]["id"]
        content = service.files()._http.request(
            f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        )
        # Use proper download
        import io
        from googleapiclient.http import MediaIoBaseDownload
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(fh.getvalue())
        return True
    except Exception:
        return False


def push_to_drive(account="main"):
    service = _get_drive_service(account)
    if not service:
        return False, "Drive service unavailable — check auth"
    folder_id = _get_or_create_folder(service)
    if not folder_id:
        return False, "Could not create sync folder"

    uploaded = []
    failed = []
    for rel_path in SYNC_FILES:
        local_path = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(local_path):
            continue
        remote_name = rel_path.replace("/", "_")
        ok = _upload_file(service, folder_id, local_path, remote_name)
        if ok:
            uploaded.append(rel_path)
        else:
            failed.append(rel_path)

    # Also upload session log if exists
    session_log = os.path.join(BASE_DIR, "logs", "session_log.json")
    if os.path.exists(session_log):
        _upload_file(service, folder_id, session_log, "logs_session_log.json")
        uploaded.append("logs/session_log.json")

    global _last_sync_time
    _last_sync_time = time.time()
    msg = f"Synced {len(uploaded)} files to Drive"
    if failed:
        msg += f" ({len(failed)} failed)"
    return True, msg


def pull_from_drive(account="main"):
    service = _get_drive_service(account)
    if not service:
        return False, "Drive service unavailable"
    folder_id = _get_or_create_folder(service)
    if not folder_id:
        return False, "Sync folder not found on Drive"

    downloaded = []
    for rel_path in SYNC_FILES:
        local_path = os.path.join(BASE_DIR, rel_path)
        remote_name = rel_path.replace("/", "_")
        ok = _download_file(service, folder_id, remote_name, local_path)
        if ok:
            downloaded.append(rel_path)

    return True, f"Pulled {len(downloaded)} files from Drive"


def sync_status():
    if _last_sync_time == 0:
        return "Never synced"
    elapsed = int(time.time() - _last_sync_time)
    if elapsed < 60:
        return f"Synced {elapsed}s ago"
    return f"Synced {elapsed // 60}m ago"


def auto_sync_loop(account="main"):
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            push_to_drive(account)
        except Exception:
            pass


def start_auto_sync(account="main"):
    t = threading.Thread(target=auto_sync_loop, args=(account,), daemon=True)
    t.start()