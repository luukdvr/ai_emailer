from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Optional, List

try:
    import backoff  # type: ignore
except Exception:  # pragma: no cover
    # Fallback no-op decorator if backoff isn't installed yet (e.g., dry-run before deps install)
    def _noop_decorator(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap
    backoff = type("backoff", (), {"on_exception": staticmethod(_noop_decorator), "expo": None})()  # type: ignore

import os
import json

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "token.json")
CRED_PATH = os.path.join(os.path.dirname(__file__), "..", "credentials.json")


def _load_creds():
    # Lazy imports to avoid hard dependency during dry-runs
    from google.oauth2.credentials import Credentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    from google.auth.transport.requests import Request  # type: ignore

    creds: Optional[Credentials] = None
    token_path = os.path.abspath(TOKEN_PATH)
    cred_path = os.path.abspath(CRED_PATH)

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(cred_path):
                raise FileNotFoundError(
                    f"credentials.json not found at {cred_path}. Download from Google Cloud Console (OAuth Desktop App)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds


def get_service():
    from googleapiclient.discovery import build  # type: ignore
    creds = _load_creds()
    service = build("gmail", "v1", credentials=creds)
    return service


def ensure_label(service, label_name: str) -> str:
    try:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
    except Exception as e:
        msg = str(e)
        if "accessNotConfigured" in msg or "has not been used in project" in msg:
            raise RuntimeError(
                "Gmail API is disabled for this project. Please enable it and retry: "
                "https://console.developers.google.com/apis/api/gmail.googleapis.com/overview"
            ) from e
        if "insufficientPermissions" in msg or "Insufficient Permission" in msg:
            raise RuntimeError(
                "Insufficient OAuth scopes. Delete token.json and re-authorize to grant both gmail.send and gmail.labels."
            ) from e
        raise
    for lbl in labels:
        if lbl.get("name") == label_name:
            return lbl.get("id")
    body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show"
    }
    created = service.users().labels().create(userId="me", body=body).execute()
    return created.get("id")


def _build_message(sender_header: str, to: str, subject: str, body_text: str) -> dict:
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = sender_header
    msg["Subject"] = subject
    msg.set_content(body_text)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


@backoff.on_exception(getattr(backoff, "expo", None), Exception, max_tries=5)
def send_message(service, to_email: str, subject: str, body: str, label_id: Optional[str], sender_header: Optional[str] = None) -> dict:
    message = _build_message(sender_header or "me", to_email, subject, body)
    sent = service.users().messages().send(userId="me", body=message).execute()
    
    # Get thread ID for tracking
    thread_id = sent.get("threadId")
    
    if label_id:
        try:
            service.users().messages().modify(
                userId="me",
                id=sent["id"],
                body={"addLabelIds": [label_id]},
            ).execute()
        except Exception as e:
            msg = str(e)
            if "insufficientPermissions" in msg or "Insufficient Permission" in msg:
                raise RuntimeError(
                    "Email sent but label could not be applied due to insufficient OAuth scopes. "
                    "Delete token.json and re-run to re-authorize with scopes: gmail.send, gmail.labels."
                ) from e
            raise
    
    # Add thread_id to response for database tracking
    sent["threadId"] = thread_id
    return sent


def get_thread_messages(service, thread_id: str) -> List[dict]:
    """Get all messages in a Gmail thread."""
    try:
        thread = service.users().threads().get(userId="me", id=thread_id).execute()
        return thread.get("messages", [])
    except Exception as e:
        print(f"Error getting thread {thread_id}: {e}")
        return []


def get_message_content(service, message_id: str) -> dict:
    """Get full content of a Gmail message."""
    try:
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        return message
    except Exception as e:
        print(f"Error getting message {message_id}: {e}")
        return {}
