"""
reauth_gmail.py — Re-authorize Gmail OAuth and update secrets.toml refresh token.

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
SECRETS = Path(".streamlit/secrets.toml")

flow = InstalledAppFlow.from_client_secrets_file("gmail_credentials.json", SCOPES)

# Print the URL first, then start listening
auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

print("\n" + "="*60)
print("STEP 1: Open this URL in your browser:")
print("="*60)
print(f"\n{auth_url}\n")
print("="*60)
print("STEP 2: Sign in as plznololing@gmail.com and click Allow.")
print("STEP 3: Your browser will redirect to localhost:8502.")
print("        The script will finish automatically.")
print("="*60 + "\n")
print("Waiting for browser authorization...")

creds = flow.run_local_server(port=8888, open_browser=False)

print(f"\nAuthorized. New refresh token: {creds.refresh_token[:20]}...")

# Update secrets.toml
content = SECRETS.read_text()
new_content = re.sub(
    r'(refresh_token\s*=\s*)"[^"]*"',
    f'refresh_token = "{creds.refresh_token}"',
    content,
)
SECRETS.write_text(new_content)
print("Updated secrets.toml.")

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
print("Updated gmail_token.json.")

# Quick test
from googleapiclient.discovery import build
service = build("gmail", "v1", credentials=creds)
profile = service.users().getProfile(userId="me").execute()
print(f"\nConnected as: {profile['emailAddress']}")
print("Done. Cron will resume on the next tick.")
