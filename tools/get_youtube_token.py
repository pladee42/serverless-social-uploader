#!/usr/bin/env python3
"""
YouTube Refresh Token Generator.

This is a LOCAL-ONLY script that runs an OAuth2 "Console" flow to generate
a Refresh Token for YouTube API access.

Usage:
    1. Download your OAuth2 credentials from Google Cloud Console
       (Desktop App type) and save as 'client_secret.json'.
    2. Run this script: python tools/get_youtube_token.py
    3. Follow the URL, authorize, and paste the code back.
    4. Copy the printed Refresh Token to GCP Secret Manager.

The secret name pattern should be:
    {CHANNEL_ID}_YOUTUBE_REFRESH_TOKEN
    {CHANNEL_ID}_YOUTUBE_CLIENT_ID
    {CHANNEL_ID}_YOUTUBE_CLIENT_SECRET
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# YouTube upload requires these scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def main():
    """Run the OAuth2 console flow and print the refresh token."""
    # Look for client_secret.json in the current directory
    client_secrets_file = Path("client_secret.json")

    if not client_secrets_file.exists():
        print("❌ Error: client_secret.json not found!")
        print()
        print("To get this file:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Desktop App type)")
        print("3. Download the JSON and save as 'client_secret.json'")
        sys.exit(1)

    print("🔐 YouTube OAuth2 Token Generator")
    print("=" * 50)
    print()

    # Create the OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_file),
        scopes=SCOPES,
    )

    # Run the console-based flow (no browser redirect needed)
    print("Opening browser for authorization...")
    print("If the browser doesn't open, copy the URL below manually.")
    print()

    # Use run_local_server for easier flow (falls back to console if needed)
    try:
        credentials = flow.run_local_server(
            port=8888,
            prompt="consent",
            access_type="offline",
        )
    except Exception:
        # Fallback to console flow if local server fails
        print("Local server failed, using console flow...")
        credentials = flow.run_console()

    print()
    print("✅ Authorization successful!")
    print()
    print("=" * 50)
    print("📋 SAVE THESE VALUES TO GCP SECRET MANAGER:")
    print("=" * 50)
    print()

    # Load client_id and client_secret from the file
    with open(client_secrets_file) as f:
        client_config = json.load(f)

    # Handle both "installed" and "web" app types
    if "installed" in client_config:
        client_info = client_config["installed"]
    elif "web" in client_config:
        client_info = client_config["web"]
    else:
        client_info = client_config

    print(f"CLIENT_ID:\n{client_info.get('client_id', 'N/A')}")
    print()
    print(f"CLIENT_SECRET:\n{client_info.get('client_secret', 'N/A')}")
    print()
    print(f"REFRESH_TOKEN:\n{credentials.refresh_token}")
    print()
    print("=" * 50)
    print()
    print("💡 Next steps:")
    print("   1. Create secrets in GCP Secret Manager:")
    print("      - {CHANNEL_ID}_YOUTUBE_CLIENT_ID")
    print("      - {CHANNEL_ID}_YOUTUBE_CLIENT_SECRET")
    print("      - {CHANNEL_ID}_YOUTUBE_REFRESH_TOKEN")
    print()
    print("   2. Replace {CHANNEL_ID} with your channel identifier")
    print("      (e.g., TIMELINE_B_YOUTUBE_REFRESH_TOKEN)")
    print()


if __name__ == "__main__":
    main()
