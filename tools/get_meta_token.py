#!/usr/bin/env python3
"""
Meta (Facebook/Instagram) Token Helper.

This script helps you save Meta access tokens to GCP Secret Manager.

For Facebook/Instagram, you need:
1. A Long-Lived User Access Token (valid for 60 days)
2. Page ID (for Facebook Page uploads)
3. Instagram Business Account ID (for Instagram uploads)

How to get tokens:
1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app
3. Generate User Token with permissions:
   - pages_manage_posts
   - pages_read_engagement
   - instagram_basic
   - instagram_content_publish
4. Exchange for Long-Lived Token (60 days):
   GET /oauth/access_token?grant_type=fb_exchange_token&
       client_id={app-id}&client_secret={app-secret}&fb_exchange_token={short-lived-token}

Usage:
    python tools/get_meta_token.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT
"""

import argparse
import os
import sys


def create_or_update_secret(project_id: str, secret_id: str, secret_value: str) -> None:
    """Create a new secret or update an existing one in Secret Manager."""
    from google.cloud import secretmanager
    from google.api_core import exceptions

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    secret_path = f"{parent}/secrets/{secret_id}"

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

    client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": secret_value.encode("UTF-8")},
        }
    )
    print(f"   ✅ Updated: {secret_id}")


def main():
    """Save Meta tokens to Secret Manager."""
    parser = argparse.ArgumentParser(
        description="Save Meta (Facebook/Instagram) tokens to GCP Secret Manager."
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
        help="Save tokens to GCP Secret Manager.",
    )
    parser.add_argument(
        "--project",
        type=str,
        help="GCP Project ID.",
    )
    parser.add_argument(
        "--platform",
        type=str,
        choices=["facebook", "instagram", "both"],
        default="both",
        help="Which platform to configure.",
    )
    args = parser.parse_args()

    print("📘 Meta Token Helper")
    print("=" * 50)
    print()

    tokens = {}

    # Get access token
    print("Enter your Long-Lived User Access Token:")
    print("(Get it from https://developers.facebook.com/tools/explorer/)")
    print()
    access_token = input("Access Token: ").strip()

    if not access_token:
        print("❌ Error: Access token is required")
        sys.exit(1)

    tokens["access_token"] = access_token

    # Get platform-specific IDs
    if args.platform in ("facebook", "both"):
        print()
        print("Enter your Facebook Page ID:")
        print("(Find it in your Page's About section or via Graph API Explorer)")
        page_id = input("Page ID: ").strip()
        if page_id:
            tokens["facebook_page_id"] = page_id

    if args.platform in ("instagram", "both"):
        print()
        print("Enter your Instagram Business Account ID:")
        print("(Get it via: GET /{page-id}?fields=instagram_business_account)")
        ig_user_id = input("Instagram User ID: ").strip()
        if ig_user_id:
            tokens["instagram_user_id"] = ig_user_id

    print()
    print("=" * 50)

    if args.save:
        print("📤 SAVING TO GCP SECRET MANAGER...")
        print("=" * 50)
        print()

        project_id = args.project
        if not project_id:
            project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")

        if not project_id:
            print("❌ Error: Could not determine GCP Project ID.")
            sys.exit(1)

        channel_upper = args.channel_id.upper()
        print(f"   Project: {project_id}")
        print(f"   Channel: {args.channel_id}")
        print()

        # Save Facebook secrets
        if "facebook_page_id" in tokens:
            create_or_update_secret(
                project_id,
                f"{channel_upper}_FACEBOOK_ACCESS_TOKEN",
                tokens["access_token"],
            )
            create_or_update_secret(
                project_id,
                f"{channel_upper}_FACEBOOK_PAGE_ID",
                tokens["facebook_page_id"],
            )

        # Save Instagram secrets
        if "instagram_user_id" in tokens:
            create_or_update_secret(
                project_id,
                f"{channel_upper}_INSTAGRAM_ACCESS_TOKEN",
                tokens["access_token"],
            )
            create_or_update_secret(
                project_id,
                f"{channel_upper}_INSTAGRAM_USER_ID",
                tokens["instagram_user_id"],
            )

        print()
        print("🎉 Tokens saved successfully!")
        print()
        print("⚠️  Remember: Long-lived tokens expire in 60 days.")
        print("   Set a reminder to refresh them before expiration.")

    else:
        print("📋 SECRETS TO CREATE:")
        print("=" * 50)
        print()

        channel_upper = args.channel_id.upper()

        if "facebook_page_id" in tokens:
            print(f"{channel_upper}_FACEBOOK_ACCESS_TOKEN = {tokens['access_token'][:20]}...")
            print(f"{channel_upper}_FACEBOOK_PAGE_ID = {tokens['facebook_page_id']}")

        if "instagram_user_id" in tokens:
            print(f"{channel_upper}_INSTAGRAM_ACCESS_TOKEN = {tokens['access_token'][:20]}...")
            print(f"{channel_upper}_INSTAGRAM_USER_ID = {tokens['instagram_user_id']}")

        print()
        print("💡 TIP: Run with --save to auto-save to Secret Manager!")


if __name__ == "__main__":
    main()
