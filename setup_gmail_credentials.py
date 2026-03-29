"""
Run this once to create gmail_credentials.json from your Google OAuth client ID and secret.
Values are entered interactively in the terminal — never saved to chat history.

Usage:
    python setup_gmail_credentials.py
"""

import json
import getpass

print("\n=== Gmail Credentials Setup ===\n")
print("Find these values in Google Cloud Console →")
print("APIs & Services → Credentials → click your OAuth 2.0 Client ID\n")

client_id = input("Paste your Client ID: ").strip()
client_secret = input("Paste your Client Secret: ").strip()

creds = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost"]
    }
}

with open("gmail_credentials.json", "w") as f:
    json.dump(creds, f, indent=2)

print("\ngmail_credentials.json created successfully.")
print("Do NOT commit this file to git.\n")
