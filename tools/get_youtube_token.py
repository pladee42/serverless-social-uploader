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


def create_or_update_secret(project_id: str, secret_id: str, secret_value: str) -> None:
    """Create a new secret or update an existing one in Secret Manager."""
    from google.cloud import secretmanager
    from google.api_core import exceptions

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    secret_path = f"{parent}/secrets/{secret_id}"

    # Try to create the secret first
    try:
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"   Created secret: {secret_id}")
    except exceptions.AlreadyExists:
        print(f"   Secret exists: {secret_id}")

    # Add a new version with the secret value
    client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": secret_value.encode("UTF-8")},
        }
    )
    print(f"   ✅ Updated: {secret_id}")


def main():
    """Run the OAuth2 console flow and optionally save to Secret Manager."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate YouTube OAuth2 tokens and optionally save to GCP Secret Manager."
    )
    parser.add_argument(
        "--channel-id",
        type=str,
        help="Channel identifier (e.g., 'timeline_b'). Required if using --save.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Automatically save credentials to GCP Secret Manager.",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="GCP Project ID. If not provided, uses default from environment.",
    )
    args = parser.parse_args()

    # Validate args
    if args.save and not args.channel_id:
        print("❌ Error: --channel-id is required when using --save")
        sys.exit(1)

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

    client_id = client_info.get("client_id", "")
    client_secret = client_info.get("client_secret", "")
    refresh_token = credentials.refresh_token

    # If --save flag is set, save to Secret Manager
    if args.save:
        print("=" * 50)
        print("📤 SAVING TO GCP SECRET MANAGER...")
        print("=" * 50)
        print()

        # Get project ID
        project_id = args.project
        if not project_id:
            import os
            project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")

        if not project_id:
            print("❌ Error: Could not determine GCP Project ID.")
            print("   Set --project flag or GCP_PROJECT environment variable.")
            sys.exit(1)

        channel_upper = args.channel_id.upper()
        print(f"   Project: {project_id}")
        print(f"   Channel: {args.channel_id}")
        print()

        create_or_update_secret(project_id, f"{channel_upper}_YOUTUBE_CLIENT_ID", client_id)
        create_or_update_secret(project_id, f"{channel_upper}_YOUTUBE_CLIENT_SECRET", client_secret)
        create_or_update_secret(project_id, f"{channel_upper}_YOUTUBE_REFRESH_TOKEN", refresh_token)

        print()
        print("🎉 All secrets saved successfully!")
        print()

    else:
        # Print values for manual copy
        print("=" * 50)
        print("📋 SAVE THESE VALUES TO GCP SECRET MANAGER:")
        print("=" * 50)
        print()
        print(f"CLIENT_ID:\n{client_id}")
        print()
        print(f"CLIENT_SECRET:\n{client_secret}")
        print()
        print(f"REFRESH_TOKEN:\n{refresh_token}")
        print()
        print("=" * 50)
        print()
        print("💡 TIP: Run with --save --channel-id YOUR_CHANNEL to auto-save!")
        print("   Example: python tools/get_youtube_token.py --save --channel-id timeline_b")
        print()


if __name__ == "__main__":
    main()
