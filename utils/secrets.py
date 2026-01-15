"""
Dynamic Secret Manager Utility.

This module implements the "Open Source" Config-Driven Pattern for secret lookup.
Secrets are resolved dynamically based on the pattern:
    {CHANNEL_ID_UPPERCASE}_{PLATFORM}_{KEY_TYPE}

Example:
    For channel_id="timeline_b" and platform="youtube", key_type="refresh_token":
    -> Secret name: "TIMELINE_B_YOUTUBE_REFRESH_TOKEN"
"""

import os
from functools import lru_cache
from typing import Optional

from google.cloud import secretmanager


@lru_cache(maxsize=1)
def _get_client() -> secretmanager.SecretManagerServiceClient:
    """Get or create a cached Secret Manager client."""
    return secretmanager.SecretManagerServiceClient()


def _get_project_id() -> str:
    """Get the GCP project ID from environment or metadata server."""
    # First, check environment variable
    project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id:
        return project_id

    # Fallback: On Cloud Run, we can fetch from metadata server
    try:
        import httpx

        response = httpx.get(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
            timeout=2.0,
        )
        if response.status_code == 200:
            return response.text
    except Exception:
        pass

    raise ValueError(
        "Could not determine GCP project ID. "
        "Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable."
    )


def get_secret(secret_name: str, version: str = "latest") -> str:
    """
    Fetch a secret value from GCP Secret Manager.

    Args:
        secret_name: The name of the secret (e.g., "TIMELINE_B_YOUTUBE_REFRESH_TOKEN").
        version: The version of the secret (default: "latest").

    Returns:
        The secret value as a string.

    Raises:
        google.api_core.exceptions.NotFound: If the secret does not exist.
    """
    client = _get_client()
    project_id = _get_project_id()

    name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
    response = client.access_secret_version(request={"name": name})

    return response.payload.data.decode("UTF-8")


def build_secret_name(channel_id: str, platform: str, key_type: str) -> str:
    """
    Build a secret name following the Config-Driven Pattern.

    Pattern: {CHANNEL_ID_UPPERCASE}_{PLATFORM}_{KEY_TYPE}

    Args:
        channel_id: The channel identifier (e.g., "timeline_b").
        platform: The platform name (e.g., "youtube", "tiktok").
        key_type: The type of key (e.g., "refresh_token", "cookie").

    Returns:
        The formatted secret name (e.g., "TIMELINE_B_YOUTUBE_REFRESH_TOKEN").
    """
    return f"{channel_id.upper()}_{platform.upper()}_{key_type.upper()}"


def get_channel_secret(
    channel_id: str,
    platform: str,
    key_type: str,
    version: str = "latest",
) -> str:
    """
    Fetch a channel-specific secret using the Config-Driven Pattern.

    This is a convenience function that combines build_secret_name and get_secret.

    Args:
        channel_id: The channel identifier (e.g., "timeline_b").
        platform: The platform name (e.g., "youtube", "tiktok").
        key_type: The type of key (e.g., "refresh_token", "cookie").
        version: The version of the secret (default: "latest").

    Returns:
        The secret value as a string.

    Example:
        >>> token = get_channel_secret("gaming_hub", "youtube", "refresh_token")
        # Fetches secret named "GAMING_HUB_YOUTUBE_REFRESH_TOKEN"
    """
    secret_name = build_secret_name(channel_id, platform, key_type)
    return get_secret(secret_name, version)


def secret_exists(secret_name: str) -> bool:
    """
    Check if a secret exists in Secret Manager.

    Args:
        secret_name: The name of the secret.

    Returns:
        True if the secret exists, False otherwise.
    """
    try:
        get_secret(secret_name)
        return True
    except Exception:
        return False


def validate_channel_secrets(
    channel_id: str,
    platforms: list[str],
) -> dict[str, bool]:
    """
    Validate that all required secrets exist for a channel.

    Args:
        channel_id: The channel identifier.
        platforms: List of platform names to validate.

    Returns:
        A dict mapping platform names to whether their secrets exist.

    Example:
        >>> validate_channel_secrets("timeline_b", ["youtube", "tiktok"])
        {"youtube": True, "tiktok": False}
    """
    # Define required key types per platform
    required_keys = {
        "youtube": ["client_id", "client_secret", "refresh_token"],
        "tiktok": ["session_cookie"],
        "facebook": ["access_token", "page_id"],
        "instagram": ["access_token", "user_id"],
    }

    result = {}
    for platform in platforms:
        platform_lower = platform.lower()
        if platform_lower not in required_keys:
            result[platform] = False
            continue

        # Check all required keys for this platform
        all_exist = True
        for key_type in required_keys[platform_lower]:
            secret_name = build_secret_name(channel_id, platform_lower, key_type)
            if not secret_exists(secret_name):
                all_exist = False
                break

        result[platform] = all_exist

    return result
