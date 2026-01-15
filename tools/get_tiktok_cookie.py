#!/usr/bin/env python3
"""
TikTok Session Cookie Extractor Helper.

This script helps you extract the TikTok session cookie from your browser
and optionally save it to GCP Secret Manager.

Usage:
    1. Log in to TikTok in your browser
    2. Open Developer Tools (F12) → Application → Cookies → tiktok.com
    3. Copy the value of the 'sessionid' cookie
    4. Run this script:
       python tools/get_tiktok_cookie.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT

Alternatively, paste the cookie when prompted.
"""

import argparse
import sys


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
    """Extract TikTok session cookie and optionally save to Secret Manager."""
    parser = argparse.ArgumentParser(
        description="Save TikTok session cookie to GCP Secret Manager."
    )
    parser.add_argument(
        "--channel-id",
        type=str,
        required=True,
        help="Channel identifier (e.g., 'timeline_b').",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save cookie to GCP Secret Manager.",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="GCP Project ID. If not provided, uses default from environment.",
    )
    parser.add_argument(
        "--cookie",
        type=str,
        help="The sessionid cookie value. If not provided, will prompt for input.",
    )
    args = parser.parse_args()

    print("🎵 TikTok Session Cookie Helper")
    print("=" * 50)
    print()

    # Get cookie value
    if args.cookie:
        session_cookie = args.cookie
    else:
        print("How to get your TikTok session cookie:")
        print("1. Log in to TikTok in your browser")
        print("2. Open Developer Tools (F12)")
        print("3. Go to Application → Cookies → tiktok.com")
        print("4. Find 'sessionid' and copy its value")
        print()
        session_cookie = input("Paste your sessionid cookie value: ").strip()

    if not session_cookie:
        print("❌ Error: No cookie provided")
        sys.exit(1)

    # Validate cookie format (basic check)
    if len(session_cookie) < 20:
        print("⚠️  Warning: Cookie seems too short. Make sure you copied the full value.")

    print()
    print(f"Cookie length: {len(session_cookie)} characters")
    print(f"Cookie preview: {session_cookie[:20]}...{session_cookie[-10:]}")
    print()

    if args.save:
        import os

        print("=" * 50)
        print("📤 SAVING TO GCP SECRET MANAGER...")
        print("=" * 50)
        print()

        # Get project ID
        project_id = args.project
        if not project_id:
            project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")

        if not project_id:
            print("❌ Error: Could not determine GCP Project ID.")
            print("   Set --project flag or GCP_PROJECT environment variable.")
            sys.exit(1)

        channel_upper = args.channel_id.upper()
        print(f"   Project: {project_id}")
        print(f"   Channel: {args.channel_id}")
        print()

        create_or_update_secret(
            project_id,
            f"{channel_upper}_TIKTOK_SESSION_COOKIE",
            session_cookie,
        )

        print()
        print("🎉 Cookie saved successfully!")
        print()

    else:
        print("=" * 50)
        print("📋 SECRET TO CREATE IN GCP SECRET MANAGER:")
        print("=" * 50)
        print()
        print(f"Secret Name: {args.channel_id.upper()}_TIKTOK_SESSION_COOKIE")
        print(f"Secret Value: {session_cookie}")
        print()
        print("💡 TIP: Run with --save to auto-save to Secret Manager!")
        print(f"   Example: python tools/get_tiktok_cookie.py --save --channel-id {args.channel_id} --project YOUR_PROJECT")
        print()


if __name__ == "__main__":
    main()
