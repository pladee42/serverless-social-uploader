#!/usr/bin/env python3
"""
Meta (Facebook/Instagram) Token Helper.

This script helps you get long-lived Meta access tokens and save them to GCP Secret Manager.

Features:
- Automatically exchanges short-lived tokens (1 hour) for long-lived tokens (60 days)
- Saves tokens and IDs to Secret Manager

How to get tokens:
1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app
3. Generate User Token with permissions:
   - pages_manage_posts
   - pages_read_engagement
   - instagram_basic
   - instagram_content_publish
4. Run this script - it will exchange for a long-lived token automatically

Usage:
    python tools/get_meta_token.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT
"""

import argparse
import os
import sys

import httpx

GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def exchange_for_long_lived_token(short_token: str, app_id: str, app_secret: str) -> dict:
    """
    Exchange a short-lived token for a long-lived token (60 days).
    
    Args:
        short_token: Short-lived user access token from Graph API Explorer
        app_id: Facebook App ID
        app_secret: Facebook App Secret
    
    Returns:
        Dict with access_token and expires_in
    """
    url = f"{GRAPH_API_BASE}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    }
    
    response = httpx.get(url, params=params, timeout=30.0)
    
    if response.status_code != 200:
        error = response.json().get("error", {})
        raise Exception(f"Token exchange failed: {error.get('message', response.text)}")
    
    data = response.json()
    
    # Verify the token to get actual expiration
    debug_url = f"{GRAPH_API_BASE}/debug_token"
    debug_params = {
        "input_token": data["access_token"],
        "access_token": f"{app_id}|{app_secret}",
    }
    debug_response = httpx.get(debug_url, params=debug_params, timeout=30.0)
    if debug_response.status_code == 200:
        debug_data = debug_response.json().get("data", {})
        expires_at = debug_data.get("expires_at", 0)
        if expires_at == 0:
            # expires_at=0 means never expires
            data["never_expires"] = True
        elif expires_at > 0:
            import time
            data["expires_in"] = expires_at - int(time.time())
    
    return data


def get_page_access_token(user_token: str, page_id: str) -> str:
    """
    Get a page access token from user token.
    Page tokens don't expire if derived from long-lived user tokens.
    """
    url = f"{GRAPH_API_BASE}/{page_id}"
    params = {
        "fields": "access_token",
        "access_token": user_token,
    }
    
    response = httpx.get(url, params=params, timeout=30.0)
    
    if response.status_code != 200:
        error = response.json().get("error", {})
        raise Exception(f"Failed to get page token: {error.get('message', response.text)}")
    
    return response.json().get("access_token")


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
    print("=" * 60)
    print()

    # Get App credentials for token exchange
    print("Step 1: App Credentials")
    print("-" * 40)
    print("Find these at: https://developers.facebook.com/apps/ → Settings → Basic")
    print()
    app_id = input("App ID: ").strip()
    app_secret = input("App Secret: ").strip()

    if not app_id or not app_secret:
        print("❌ Error: App ID and App Secret are required")
        sys.exit(1)

    print()

    # Get short-lived token
    print("Step 2: User Access Token")
    print("-" * 40)
    print("Get it from: https://developers.facebook.com/tools/explorer/")
    print("Make sure to select the required permissions!")
    print()
    short_token = input("Short-lived Access Token: ").strip()

    if not short_token:
        print("❌ Error: Access token is required")
        sys.exit(1)

    print()

    # Exchange for long-lived token
    print("Step 3: Exchanging for Long-Lived Token...")
    print("-" * 40)
    try:
        result = exchange_for_long_lived_token(short_token, app_id, app_secret)
        long_lived_token = result["access_token"]
        never_expires = result.get("never_expires", False)
        expires_in = result.get("expires_in", 0)
        days = expires_in // 86400 if expires_in > 0 else 0
        if never_expires:
            print("✅ Success! Token never expires ✨")
        else:
            print(f"✅ Success! Token expires in {days} days")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print()
    tokens = {"access_token": long_lived_token}

    # Get platform-specific IDs
    print("Step 4: Platform IDs")
    print("-" * 40)

    if args.platform in ("facebook", "both"):
        print()
        print("Facebook Page ID:")
        print("Find it in your Page's About section or via:")
        print(f"  GET /me/accounts?access_token={long_lived_token[:20]}...")
        page_id = input("Page ID: ").strip()
        if page_id:
            tokens["facebook_page_id"] = page_id
            # Get page-specific token (doesn't expire!)
            try:
                print("   Getting page access token...")
                page_token = get_page_access_token(long_lived_token, page_id)
                tokens["facebook_access_token"] = page_token
                print("   ✅ Got non-expiring page token!")
            except Exception as e:
                print(f"   ⚠️  Using user token instead: {e}")
                tokens["facebook_access_token"] = long_lived_token

    if args.platform in ("instagram", "both"):
        print()
        print("Instagram Business Account ID:")
        print("Get it via: GET /{page-id}?fields=instagram_business_account")
        ig_user_id = input("Instagram User ID: ").strip()
        if ig_user_id:
            tokens["instagram_user_id"] = ig_user_id
            tokens["instagram_access_token"] = long_lived_token

    print()
    print("=" * 60)

    if args.save:
        print("📤 SAVING TO GCP SECRET MANAGER...")
        print("=" * 60)
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
                tokens["facebook_access_token"],
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
                tokens["instagram_access_token"],
            )
            create_or_update_secret(
                project_id,
                f"{channel_upper}_INSTAGRAM_USER_ID",
                tokens["instagram_user_id"],
            )

        print()
        print("🎉 Tokens saved successfully!")
        print()
        print("📌 Token Expiration:")
        if "facebook_page_id" in tokens:
            print("   Facebook Page Token: Never expires ✨")
        if "instagram_user_id" in tokens:
            if never_expires:
                print("   Instagram Token: Never expires ✨")
            else:
                print(f"   Instagram Token: ~{days} days")
                print("   ⚠️  Set a reminder to refresh before expiration!")

    else:
        print("📋 TOKENS GENERATED (not saved):")
        print("=" * 60)
        print()

        channel_upper = args.channel_id.upper()

        if "facebook_page_id" in tokens:
            print(f"{channel_upper}_FACEBOOK_ACCESS_TOKEN = {tokens['facebook_access_token'][:30]}...")
            print(f"{channel_upper}_FACEBOOK_PAGE_ID = {tokens['facebook_page_id']}")

        if "instagram_user_id" in tokens:
            print(f"{channel_upper}_INSTAGRAM_ACCESS_TOKEN = {tokens['instagram_access_token'][:30]}...")
            print(f"{channel_upper}_INSTAGRAM_USER_ID = {tokens['instagram_user_id']}")

        print()
        print("💡 TIP: Run with --save to auto-save to Secret Manager!")


if __name__ == "__main__":
    main()
