"""
YouTube Video Uploader.

This module implements the "Refresh Token" strategy for YouTube uploads.
It reconstructs credentials from a refresh token (stored in Secret Manager)
and uses the YouTube Data API v3 for uploads.

Authentication Flow:
    1. Fetch client_id, client_secret, refresh_token from Secret Manager
    2. Rebuild google.oauth2.credentials.Credentials object
    3. Use googleapiclient to upload video with resumable upload

Reference:
    https://developers.google.com/youtube/v3/guides/uploading_a_video
"""

import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Optional

import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# YouTube API constants
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"

# Retry settings for resumable upload
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)


@dataclass
class YouTubeCredentials:
    """Container for YouTube OAuth2 credentials."""

    client_id: str
    client_secret: str
    refresh_token: str
    access_token: Optional[str] = None

    def to_google_credentials(self) -> Credentials:
        """Convert to google.oauth2.credentials.Credentials object."""
        return Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=[YOUTUBE_UPLOAD_SCOPE],
            # Allow using refresh token to automatically refresh access token
            expiry=None,
        )


@dataclass
class VideoMetadata:
    """Metadata for the video to upload."""

    title: str
    description: str = ""
    tags: list[str] | None = None
    category_id: str = "27"  # "Entertainment" category
    privacy_status: str = "private"  # "public", "private", or "unlisted"
    made_for_kids: bool = False
    ai_generated: bool = False


def build_youtube_service(credentials: YouTubeCredentials):
    """
    Build an authenticated YouTube API service.

    Args:
        credentials: YouTubeCredentials containing OAuth2 tokens.

    Returns:
        A googleapiclient Resource for the YouTube API.
    """
    google_creds = credentials.to_google_credentials()

    return build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=google_creds,
    )


def _resumable_upload(insert_request) -> dict:
    """
    Execute a resumable upload with exponential backoff retry.

    Args:
        insert_request: The YouTube API insert request.

    Returns:
        The API response dict containing video details.

    Raises:
        HttpError: If the upload fails after all retries.
    """
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            logger.info("Uploading chunk...")
            status, response = insert_request.next_chunk()

            if status:
                progress = int(status.progress() * 100)
                logger.info(f"Upload progress: {progress}%")

        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred: {e.content}"
            else:
                raise

        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            logger.warning(error)
            retry += 1

            if retry > MAX_RETRIES:
                raise Exception(f"Upload failed after {MAX_RETRIES} retries")

            # Exponential backoff with jitter
            sleep_seconds = random.random() * (2**retry)
            logger.info(f"Retrying in {sleep_seconds:.1f} seconds...")
            time.sleep(sleep_seconds)
            error = None

    return response


async def upload_video(
    video_path: str,
    credentials: YouTubeCredentials,
    metadata: VideoMetadata,
) -> dict:
    """
    Upload a video to YouTube using the resumable upload protocol.

    Args:
        video_path: Local path to the video file.
        credentials: YouTubeCredentials for authentication.
        metadata: VideoMetadata with title, description, etc.

    Returns:
        A dict with upload result including video_id.

    Raises:
        FileNotFoundError: If the video file doesn't exist.
        HttpError: If the YouTube API returns an error.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    file_size = os.path.getsize(video_path)
    logger.info(f"Uploading video: {video_path} ({file_size / 1024 / 1024:.1f} MB)")

    # Build the YouTube service
    youtube = build_youtube_service(credentials)

    # Prepare the video resource body
    body = {
        "snippet": {
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags or [],
            "categoryId": metadata.category_id,
        },
        "status": {
            "privacyStatus": metadata.privacy_status,
            "selfDeclaredMadeForKids": metadata.made_for_kids,
            "containsSyntheticMedia": metadata.ai_generated,
        },
    }

    # Create the media upload object (resumable)
    media = MediaFileUpload(
        video_path,
        chunksize=256 * 1024,  # 256 KB chunks
        resumable=True,
        mimetype="video/*",
    )

    # Create the insert request
    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    # Execute with retry logic
    try:
        response = _resumable_upload(insert_request)

        video_id = response.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        logger.info(f"✅ Upload successful! Video ID: {video_id}")
        logger.info(f"   URL: {video_url}")

        return {
            "platform": "youtube",
            "status": "success",
            "video_id": video_id,
            "video_url": video_url,
            "title": metadata.title,
            "privacy_status": metadata.privacy_status,
        }

    except HttpError as e:
        logger.error(f"❌ YouTube API error: {e}")
        return {
            "platform": "youtube",
            "status": "error",
            "message": str(e),
            "error_code": e.resp.status if hasattr(e, "resp") else None,
        }
