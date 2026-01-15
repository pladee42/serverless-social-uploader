"""
Meta (Facebook & Instagram) Video Uploader.

This module implements video uploads to Facebook Pages and Instagram
using the Graph API with long-lived User Access Tokens.

Authentication Flow:
    1. User generates a Long-Lived User Access Token (60-day expiry)
    2. Token is stored in GCP Secret Manager
    3. For Facebook: Upload to Page via /videos endpoint
    4. For Instagram: Upload via Container-based flow

Requirements:
    - Facebook Page with video upload permissions
    - Instagram Business/Creator account linked to Facebook Page
    - App in "Development" mode (no app review required for admin users)

Reference:
    - Facebook: https://developers.facebook.com/docs/video-api/guides/publishing
    - Instagram: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Meta Graph API
GRAPH_API_VERSION = "v24.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Timeouts
UPLOAD_TIMEOUT = 600.0  # 10 minutes for large video uploads
POLL_INTERVAL = 5  # seconds between status checks
MAX_POLL_ATTEMPTS = 120  # 10 minutes max wait


@dataclass
class MetaCredentials:
    """Container for Meta authentication credentials."""

    access_token: str
    page_id: Optional[str] = None  # For Facebook Page uploads
    instagram_user_id: Optional[str] = None  # For Instagram uploads


@dataclass
class MetaVideoMetadata:
    """Metadata for the video to upload."""

    title: str = ""
    description: str = ""
    caption: str = ""  # Used for Instagram
    share_to_facebook: bool = True  # Cross-post Instagram Reels to Facebook for combined views


async def _upload_video_to_facebook(
    video_url: str,
    credentials: MetaCredentials,
    metadata: MetaVideoMetadata,
) -> dict:
    """
    Upload a video to a Facebook Page using the resumable upload API.

    Args:
        video_url: Public URL of the video file.
        credentials: MetaCredentials with access_token and page_id.
        metadata: MetaVideoMetadata with title and description.

    Returns:
        A dict with upload result.
    """
    if not credentials.page_id:
        return {
            "platform": "facebook",
            "status": "error",
            "message": "page_id is required for Facebook uploads",
        }

    logger.info(f"Uploading video to Facebook Page: {credentials.page_id}")

    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as client:
        # Use the video URL directly (Facebook will fetch it)
        upload_url = f"{GRAPH_API_BASE}/{credentials.page_id}/videos"

        params = {
            "access_token": credentials.access_token,
            "file_url": video_url,
            "title": metadata.title,
            "description": metadata.description or metadata.caption,
            "published": "true",
        }

        try:
            response = await client.post(upload_url, data=params)
            response.raise_for_status()
            result = response.json()

            if "id" in result:
                video_id = result["id"]
                logger.info(f"✅ Facebook upload successful! Video ID: {video_id}")
                return {
                    "platform": "facebook",
                    "status": "success",
                    "video_id": video_id,
                    "video_url": f"https://www.facebook.com/{credentials.page_id}/videos/{video_id}",
                }
            else:
                logger.error(f"Facebook upload failed: {result}")
                return {
                    "platform": "facebook",
                    "status": "error",
                    "message": result.get("error", {}).get("message", "Unknown error"),
                }

        except httpx.HTTPStatusError as e:
            error_body = e.response.json() if e.response.content else {}
            error_msg = error_body.get("error", {}).get("message", str(e))
            logger.error(f"Facebook API error: {error_msg}")
            return {
                "platform": "facebook",
                "status": "error",
                "message": error_msg,
                "error_code": e.response.status_code,
            }

        except Exception as e:
            logger.error(f"Facebook upload error: {e}")
            return {
                "platform": "facebook",
                "status": "error",
                "message": str(e),
            }


async def _create_instagram_container(
    video_url: str,
    credentials: MetaCredentials,
    metadata: MetaVideoMetadata,
) -> Optional[str]:
    """
    Create an Instagram media container for video upload.

    Returns:
        The container ID if successful, None otherwise.
    """
    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as client:
        container_url = f"{GRAPH_API_BASE}/{credentials.instagram_user_id}/media"

        params = {
            "access_token": credentials.access_token,
            "media_type": "REELS",  # Use REELS for video content
            "video_url": video_url,
            "caption": metadata.caption or metadata.description or metadata.title,
            "share_to_feed": "true",  # Share to Instagram feed
        }
        
        # Add cross-posting to Facebook if enabled and page_id is available
        if metadata.share_to_facebook and credentials.page_id:
            params["collaborate_with_sharing_on_facebook"] = "true"
            logger.info("Cross-posting to Facebook enabled for combined view counts")

        response = await client.post(container_url, data=params)
        response.raise_for_status()
        result = response.json()

        return result.get("id")


async def _wait_for_container_ready(
    container_id: str,
    credentials: MetaCredentials,
) -> bool:
    """
    Poll the container status until it's ready for publishing.

    Returns:
        True if container is ready, False if it failed or timed out.
    """
    import asyncio

    async with httpx.AsyncClient(timeout=60.0) as client:
        status_url = f"{GRAPH_API_BASE}/{container_id}"
        params = {
            "access_token": credentials.access_token,
            "fields": "status_code,status",
        }

        for attempt in range(MAX_POLL_ATTEMPTS):
            response = await client.get(status_url, params=params)
            result = response.json()

            status_code = result.get("status_code")
            logger.info(f"Container status: {status_code} (attempt {attempt + 1})")

            if status_code == "FINISHED":
                return True
            elif status_code in ("ERROR", "EXPIRED"):
                logger.error(f"Container failed: {result.get('status')}")
                return False

            await asyncio.sleep(POLL_INTERVAL)

        logger.error("Container processing timed out")
        return False


async def _publish_instagram_container(
    container_id: str,
    credentials: MetaCredentials,
) -> dict:
    """
    Publish a ready Instagram media container.

    Returns:
        A dict with the publish result.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        publish_url = f"{GRAPH_API_BASE}/{credentials.instagram_user_id}/media_publish"

        params = {
            "access_token": credentials.access_token,
            "creation_id": container_id,
        }

        response = await client.post(publish_url, data=params)
        response.raise_for_status()
        result = response.json()

        return result


async def _upload_video_to_instagram(
    video_url: str,
    credentials: MetaCredentials,
    metadata: MetaVideoMetadata,
) -> dict:
    """
    Upload a video to Instagram as a Reel.

    The Instagram API uses a container-based flow:
    1. Create a media container with the video URL
    2. Wait for processing to complete
    3. Publish the container

    Args:
        video_url: Public URL of the video file.
        credentials: MetaCredentials with access_token and instagram_user_id.
        metadata: MetaVideoMetadata with caption.

    Returns:
        A dict with upload result.
    """
    if not credentials.instagram_user_id:
        return {
            "platform": "instagram",
            "status": "error",
            "message": "instagram_user_id is required for Instagram uploads",
        }

    logger.info(f"Uploading video to Instagram: {credentials.instagram_user_id}")

    try:
        # Step 1: Create container
        logger.info("Creating Instagram media container...")
        container_id = await _create_instagram_container(video_url, credentials, metadata)

        if not container_id:
            return {
                "platform": "instagram",
                "status": "error",
                "message": "Failed to create media container",
            }

        logger.info(f"Container created: {container_id}")

        # Step 2: Wait for processing
        logger.info("Waiting for video processing...")
        if not await _wait_for_container_ready(container_id, credentials):
            return {
                "platform": "instagram",
                "status": "error",
                "message": "Video processing failed or timed out",
            }

        # Step 3: Publish
        logger.info("Publishing to Instagram...")
        result = await _publish_instagram_container(container_id, credentials)

        if "id" in result:
            media_id = result["id"]
            if metadata.share_to_facebook and credentials.page_id:
                logger.info(f"✅ Instagram upload successful with Facebook cross-post! Media ID: {media_id}")
            else:
                logger.info(f"✅ Instagram upload successful! Media ID: {media_id}")
            return {
                "platform": "instagram",
                "status": "success",
                "media_id": media_id,
                "cross_posted_to_facebook": metadata.share_to_facebook and credentials.page_id is not None,
            }
        else:
            return {
                "platform": "instagram",
                "status": "error",
                "message": "Publish failed - no media ID returned",
            }

    except httpx.HTTPStatusError as e:
        error_body = e.response.json() if e.response.content else {}
        error_msg = error_body.get("error", {}).get("message", str(e))
        logger.error(f"Instagram API error: {error_msg}")
        return {
            "platform": "instagram",
            "status": "error",
            "message": error_msg,
            "error_code": e.response.status_code,
        }

    except Exception as e:
        logger.error(f"Instagram upload error: {e}")
        return {
            "platform": "instagram",
            "status": "error",
            "message": str(e),
        }


async def upload_to_facebook(
    video_url: str,
    credentials: MetaCredentials,
    metadata: MetaVideoMetadata,
) -> dict:
    """
    Upload a video to Facebook.

    Args:
        video_url: Public URL of the video file (must be accessible by Facebook).
        credentials: MetaCredentials with access_token and page_id.
        metadata: MetaVideoMetadata with title and description.

    Returns:
        A dict with upload result.
    """
    return await _upload_video_to_facebook(video_url, credentials, metadata)


async def upload_to_instagram(
    video_url: str,
    credentials: MetaCredentials,
    metadata: MetaVideoMetadata,
) -> dict:
    """
    Upload a video to Instagram as a Reel.
    
    Supports cross-posting to Facebook for combined view counts.
    Set metadata.share_to_facebook=True and provide credentials.page_id.

    Args:
        video_url: Public URL of the video file (must be accessible by Instagram).
        credentials: MetaCredentials with access_token, instagram_user_id, and optionally page_id.
        metadata: MetaVideoMetadata with caption and share_to_facebook flag.

    Returns:
        A dict with upload result including cross_posted_to_facebook flag.
    """
    return await _upload_video_to_instagram(video_url, credentials, metadata)
