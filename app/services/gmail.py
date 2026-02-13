import base64
import json
import os
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmailEvent, Mailbox

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

TOKEN_DIR = Path("/app/data/tokens")
TOKEN_DIR.mkdir(parents=True, exist_ok=True)


def _get_flow(redirect_uri: str) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def get_auth_url(redirect_uri: str) -> str:
    flow = _get_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return auth_url


def exchange_code(code: str, redirect_uri: str, mailbox_id: str) -> Credentials:
    flow = _get_flow(redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_path = TOKEN_DIR / f"{mailbox_id}.json"
    token_path.write_text(creds.to_json())
    return creds


def _get_credentials(mailbox_id: str) -> Credentials | None:
    token_path = TOKEN_DIR / f"{mailbox_id}.json"
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_info(
        json.loads(token_path.read_text()), SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


def _get_gmail_service(mailbox_id: str):
    creds = _get_credentials(mailbox_id)
    if not creds:
        raise ValueError(f"No credentials for mailbox {mailbox_id}. Run OAuth flow first.")
    return build("gmail", "v1", credentials=creds)


def fetch_new_emails(db: Session, mailbox: Mailbox, max_results: int = 10) -> list[EmailEvent]:
    service = _get_gmail_service(str(mailbox.id))
    query = "is:inbox is:unread"
    if mailbox.last_sync_at:
        epoch = int(mailbox.last_sync_at.timestamp())
        query += f" after:{epoch}"

    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    new_events = []

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        existing = db.query(EmailEvent).filter_by(gmail_message_id=msg_id).first()
        if existing:
            continue

        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        body_text = _extract_body(msg["payload"])

        event = EmailEvent(
            mailbox_id=mailbox.id,
            gmail_message_id=msg_id,
            thread_id=msg.get("threadId"),
            sender=headers.get("from", ""),
            recipient=headers.get("to", ""),
            subject=headers.get("subject", ""),
            body_text=body_text,
            received_at=datetime.fromtimestamp(int(msg["internalDate"]) / 1000),
            is_processed=False,
        )
        db.add(event)
        new_events.append(event)

    if new_events:
        mailbox.last_sync_at = datetime.utcnow()
        db.commit()

    return new_events


def _extract_body(payload: dict) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        if part["mimeType"] == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


def send_reply(mailbox_id: str, thread_id: str, to: str, subject: str, body: str) -> str:
    service = _get_gmail_service(mailbox_id)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()
    return sent["id"]
