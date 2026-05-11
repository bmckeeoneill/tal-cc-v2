"""
reauth_gmail.py — Re-authorize Gmail OAuth with send permissions.

Usage:
    cd /Users/brianoneill/Desktop/TAL_CC_clean
    source venv/bin/activate
    python3 reauth_gmail.py
"""

import json
import re
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

print("Opening browser for Gmail authorization...")
flow = InstalledAppFlow.from_client_secrets_file("gmail_credentials.json", SCOPES)
creds = flow.run_local_server(port=8888, open_browser=True)

# Update token file
token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": list(creds.scopes),
}
Path("gmail_token.json").write_text(json.dumps(token_data))

# Update secrets.toml refresh token
secrets_path = Path(".streamlit/secrets.toml")
content = secrets_path.read_text()
new_content = re.sub(
    r'(refresh_token\s*=\s*)"[^"]*"',
    f'refresh_token = "{creds.refresh_token}"',
    content,
)
secrets_path.write_text(new_content)

# Verify
from googleapiclient.discovery import build
service = build("gmail", "v1", credentials=creds)
profile = service.users().getProfile(userId="me").execute()
print(f"Done. Connected as: {profile['emailAddress']}")
print(f"New token written to gmail_token.json")
print(f"\nUpdate [gmail_token] in SLC secrets with:")
print(f'token = "{creds.token}"')
print(f'refresh_token = "{creds.refresh_token}"')
