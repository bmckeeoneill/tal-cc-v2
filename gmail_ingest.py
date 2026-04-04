"""
Gmail ingest for TAL Command Center.

Polls the inbox every 5 minutes for unread emails.
For each new email: extracts subject, body, sender, date, and attachments (base64),
writes a row to signals_raw in Supabase, then marks the email as read.

Run:
    python3 gmail_ingest.py

First run will open a browser to authorize Gmail access.
Token is saved to gmail_token.json for subsequent runs.
"""

import base64
import json
import os
import time
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from supabase import create_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
CREDENTIALS_FILE = "gmail_credentials.json"  # fallback for local interactive auth
TOKEN_FILE = "gmail_token.json"              # fallback for local token cache
POLL_INTERVAL_SECONDS = 300  # 5 minutes

ALLOWED_SENDERS = {
    "brian.br.oneill@oracle.com",
    "bmckeeoneill@gmail.com",
    "unknown-email@nlcorp.com",  # CRM notifications
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
STORAGE_BUCKET = "signal-attachments"

def _load_secrets():
    """Read SUPABASE_URL and SUPABASE_KEY from .streamlit/secrets.toml if not in env."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        import re
        with open(secrets_path) as f:
            content = f.read()
        url_match = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', content)
        key_match = re.search(r'SUPABASE_KEY\s*=\s*"([^"]+)"', content)
        if url_match:
            url = url_match.group(1)
        if key_match:
            key = key_match.group(1)
    return url, key

SUPABASE_URL, SUPABASE_KEY = _load_secrets()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _load_gmail_secrets():
    """Try to load Gmail OAuth creds from secrets.toml [gmail] section."""
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        return None
    import re
    content = open(secrets_path).read()
    # Only look in [gmail] section
    gmail_section = re.search(r'\[gmail\](.*?)(?=\n\[|\Z)', content, re.DOTALL)
    if not gmail_section:
        return None
    sec = gmail_section.group(1)
    def _get(key):
        m = re.search(rf'{key}\s*=\s*"([^"]+)"', sec)
        return m.group(1) if m else None
    return _get("client_id"), _get("client_secret"), _get("refresh_token")


def get_gmail_service():
    creds = None

    # Try secrets.toml first (works on Streamlit Cloud and cron)
    gmail_secrets = _load_gmail_secrets()
    if gmail_secrets and all(gmail_secrets):
        client_id, client_secret, refresh_token = gmail_secrets
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        creds.refresh(Request())
        return build("gmail", "v1", credentials=creds)

    # Fallback: local token file (first-run interactive auth)
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Email parsing
# ---------------------------------------------------------------------------

def get_body(payload):
    """Recursively extract plain text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = get_body(part)
        if result:
            return result

    return ""


def get_attachments(payload):
    """Return list of {filename, mime_type, data_base64} for all attachments."""
    attachments = []

    def recurse(part):
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            attachments.append({
                "filename": filename,
                "mime_type": part.get("mimeType", ""),
                "attachment_id": body["attachmentId"],
            })
        for subpart in part.get("parts", []):
            recurse(subpart)

    recurse(payload)
    return attachments


def fetch_attachment_data(service, message_id, attachment_id):
    """Fetch attachment bytes and return as base64 string."""
    result = service.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    return result.get("data", "")


def parse_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def process_message(service, msg_id):
    """Fetch a full message and return a dict ready for signals_raw."""
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    payload = msg["payload"]
    headers = payload.get("headers", [])

    subject = parse_header(headers, "Subject")
    sender = parse_header(headers, "From")
    date_str = parse_header(headers, "Date")

    body_text = get_body(payload)

    # Resolve attachments
    raw_attachments = get_attachments(payload)
    resolved = []
    for att in raw_attachments:
        data = fetch_attachment_data(service, msg_id, att["attachment_id"])
        resolved.append({
            "filename": att["filename"],
            "mime_type": att["mime_type"],
            "data_base64": data,
        })

    # Parse date — fall back to now if header is unparseable
    try:
        from email.utils import parsedate_to_datetime
        received_at = parsedate_to_datetime(date_str).isoformat()
    except Exception:
        received_at = datetime.now(timezone.utc).isoformat()

    return {
        "rep_id": "brianoneill",
        "received_at": received_at,
        "from_email": sender,
        "subject": subject,
        "body_text": body_text,
        "attachments": resolved if resolved else None,
        "processed": False,
        "postmark_message_id": f"gmail:{msg_id}",
    }


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set as environment variables.\n"
            "Export them before running:\n"
            "  export SUPABASE_URL=your_url\n"
            "  export SUPABASE_KEY=your_key"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


_INLINE_LOGO_RE = re.compile(r'^outlook-[a-z0-9]+\.(png|jpg|jpeg|gif|webp)$', re.IGNORECASE)


def _is_logo_image(filename: str) -> bool:
    """Return True if this looks like an Outlook inline signature/logo image, not a real attachment."""
    return bool(_INLINE_LOGO_RE.match(filename))


def upload_attachments_to_storage(supabase, signal_id: str, attachments: list) -> str | None:
    """Upload image attachments to Supabase Storage. Returns file_url of first image, or None."""
    first_url = None
    for att in attachments:
        filename = (att.get("filename") or "attachment").replace(" ", "_")
        if _is_logo_image(filename):
            continue  # Skip Outlook inline signature/logo images
        ext = os.path.splitext(filename.lower())[1]
        if ext not in IMAGE_EXTENSIONS:
            continue
        try:
            import base64 as b64
            raw = att.get("data_base64") or ""
            # Gmail uses URL-safe base64; fix padding
            padded = raw.replace("-", "+").replace("_", "/")
            padded += "=" * (-len(padded) % 4)
            file_bytes = b64.b64decode(padded)
            path = f"brianoneill/{signal_id}/{filename}"
            mime = att.get("mime_type") or "image/png"
            supabase.storage.from_(STORAGE_BUCKET).upload(
                path=path,
                file=file_bytes,
                file_options={"content-type": mime, "upsert": "true"},
            )
            signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(path, expires_in=315360000)
            url = signed.get("signedURL") or signed.get("data", {}).get("signedUrl", "")
            if url and not first_url:
                first_url = url
        except Exception as e:
            print(f"    ⚠ Could not upload {filename}: {e}")
    return first_url


def insert_signal(supabase, row):
    resp = supabase.table("signals_raw").upsert(row, on_conflict="postmark_message_id").execute()
    return (resp.data or [{}])[0].get("id")


# ---------------------------------------------------------------------------
# Main poll loop
# ---------------------------------------------------------------------------

def poll_once(service, supabase):
    """Fetch unread messages, insert into Supabase, mark as read."""
    allowed_from = " OR ".join(f"from:{addr}" for addr in ALLOWED_SENDERS)
    result = service.users().messages().list(
        userId="me", q=f"is:unread newer_than:7d ({allowed_from})", maxResults=50
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No new messages.")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(messages)} unread message(s).")

    for m in messages:
        msg_id = m["id"]
        try:
            row = process_message(service, msg_id)
            # Extract bare email address for sender check
            sender_raw = row["from_email"]
            sender_addr = sender_raw.split("<")[-1].strip(">").strip().lower()
            if sender_addr not in ALLOWED_SENDERS:
                print(f"  — Skipped (not from allowed sender): {sender_raw!r}")
                continue
            signal_id = insert_signal(supabase, row)

            # Upload image attachments to Storage and store file_url
            attachments = row.get("attachments") or []
            if signal_id and attachments:
                file_url = upload_attachments_to_storage(supabase, signal_id, attachments)
                if file_url:
                    supabase.table("signals_raw").update({"file_url": file_url}).eq("id", signal_id).execute()
                    print(f"    ↑ Uploaded attachment → Storage")

            print(f"  ✓ Ingested: {row['subject']!r} from {row['from_email']!r}")
        except Exception as e:
            print(f"  ✗ Error processing message {msg_id}: {e}")


def main():
    import sys
    once = "--once" in sys.argv

    if not once:
        print("Starting Gmail ingest for TAL Command Center.")
        print(f"Polling every {POLL_INTERVAL_SECONDS // 60} minutes.\n")

    service = get_gmail_service()
    supabase = get_supabase()

    if once:
        poll_once(service, supabase)
        return

    while True:
        try:
            poll_once(service, supabase)
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
