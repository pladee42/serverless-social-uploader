"""
Universal Social Media Uploader - FastAPI Application.

This is the main entry point for the serverless video uploader.
It implements the "Open Source" Config-Driven Pattern where all
configuration is resolved dynamically based on the channel_id.
"""

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from utils.secrets import get_channel_secret, validate_channel_secrets
from platforms.youtube import (
    upload_video as youtube_upload_video,
    YouTubeCredentials,
    VideoMetadata as YouTubeVideoMetadata,
)
from platforms.tiktok import (
    upload_video as tiktok_upload_video,
    TikTokCredentials,
    TikTokVideoMetadata,
)
from platforms.meta import (
    upload_to_facebook,
    upload_to_instagram,
    MetaCredentials,
    MetaVideoMetadata,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# --- Pydantic Models ---


class Platform(str, Enum):
    """Supported social media platforms."""

    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class PublishRequest(BaseModel):
    """Request model for the /publish endpoint."""

    channel_id: str = Field(
        ...,
        description="The channel identifier (e.g., 'timeline_b'). "
        "Used to dynamically resolve secrets.",
        examples=["timeline_b", "gaming_hub"],
    )
    video_url: str = Field(
        ...,
        description="Public URL of the video file.",
        examples=["https://storage.googleapis.com/timeline-b/scenario_20260115_020027.mp4"],
    )
    platforms: list[Platform] = Field(
        ...,
        description="List of platforms to upload to.",
        examples=[["youtube", "tiktok"]],
    )
    title: Optional[str] = Field(
        None,
        description="Video title (used by YouTube).",
    )
    description: Optional[str] = Field(
        None,
        description="Video description.",
    )
    caption: Optional[str] = Field(
        None,
        description="Short caption (used by TikTok, Instagram).",
    )


class PublishResponse(BaseModel):
    """Response model for the /publish endpoint."""

    status: str
    message: str
    channel_id: str
    platforms: list[str]
    job_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    version: str


class ValidateResponse(BaseModel):
    """Response model for secret validation."""

    channel_id: str
    platforms: dict[str, bool]
    all_valid: bool


# --- Application Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🚀 Universal Social Media Uploader starting up...")
    yield
    logger.info("👋 Universal Social Media Uploader shutting down...")


# --- FastAPI App ---


app = FastAPI(
    title="Universal Social Media Uploader",
    description=(
        "A serverless API for uploading videos to multiple social media platforms. "
        "Uses the 'No-Review' authentication strategy with dynamic secret resolution."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# --- Helper Functions ---


async def download_from_url(url: str, local_path: str) -> str:
    """
    Download a file from a public URL.

    Args:
        url: The public URL of the video file.
        local_path: The local path to save the file.

    Returns:
        The local path of the downloaded file.
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(local_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)

    logger.info(f"Downloaded {url} to {local_path}")
    return local_path


async def upload_to_platform(
    platform: Platform,
    channel_id: str,
    video_path: str,
    video_url: str,
    title: Optional[str],
    description: Optional[str],
    caption: Optional[str],
    dry_run: bool = False,
) -> dict:
    """
    Upload video to a specific platform.

    This function dynamically resolves secrets and dispatches to the appropriate
    platform uploader.

    Args:
        platform: The target platform.
        channel_id: The channel identifier for secret lookup.
        video_path: Local path to the video file (used by YouTube, TikTok).
        video_url: Public URL of the video file (used by Meta platforms).
        title: Video title (YouTube).
        description: Video description.
        caption: Short caption (TikTok, Instagram).
        dry_run: If True, validate secrets but don't upload.

    Returns:
        A dict with the upload result.
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Uploading to {platform.value} for channel {channel_id}")

    if platform == Platform.YOUTUBE:
        # Fetch YouTube secrets
        try:
            client_id = get_channel_secret(channel_id, "youtube", "client_id")
            client_secret = get_channel_secret(channel_id, "youtube", "client_secret")
            refresh_token = get_channel_secret(channel_id, "youtube", "refresh_token")

            if dry_run:
                return {"platform": platform.value, "status": "validated", "message": "Secrets found"}

            # Build credentials and metadata
            credentials = YouTubeCredentials(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
            metadata = YouTubeVideoMetadata(
                title=title or "Untitled Video",
                description=description or "",
                privacy_status="private",  # Default to private for safety
            )

            # Upload to YouTube
            return await youtube_upload_video(video_path, credentials, metadata)

        except Exception as e:
            return {"platform": platform.value, "status": "error", "message": str(e)}

    elif platform == Platform.TIKTOK:
        try:
            session_cookie = get_channel_secret(channel_id, "tiktok", "session_cookie")

            if dry_run:
                return {"platform": platform.value, "status": "validated", "message": "Secrets found"}

            # Build credentials and metadata
            credentials = TikTokCredentials(session_cookie=session_cookie)
            metadata = TikTokVideoMetadata(
                caption=caption or title or "",
            )

            # Upload to TikTok using Playwright
            return await tiktok_upload_video(video_path, credentials, metadata)

        except Exception as e:
            return {"platform": platform.value, "status": "error", "message": str(e)}

    elif platform == Platform.FACEBOOK:
        try:
            access_token = get_channel_secret(channel_id, "facebook", "access_token")
            page_id = get_channel_secret(channel_id, "facebook", "page_id")

            if dry_run:
                return {"platform": platform.value, "status": "validated", "message": "Secrets found"}

            # Build credentials and metadata
            credentials = MetaCredentials(
                access_token=access_token,
                page_id=page_id,
            )
            metadata = MetaVideoMetadata(
                title=title or "",
                description=description or caption or "",
            )

            # Facebook uses video_url directly (not local file)
            return await upload_to_facebook(video_url, credentials, metadata)

        except Exception as e:
            return {"platform": platform.value, "status": "error", "message": str(e)}

    elif platform == Platform.INSTAGRAM:
        try:
            access_token = get_channel_secret(channel_id, "instagram", "access_token")
            user_id = get_channel_secret(channel_id, "instagram", "user_id")

            if dry_run:
                return {"platform": platform.value, "status": "validated", "message": "Secrets found"}

            # Build credentials and metadata
            credentials = MetaCredentials(
                access_token=access_token,
                instagram_user_id=user_id,
            )
            metadata = MetaVideoMetadata(
                caption=caption or description or title or "",
            )

            # Instagram uses video_url directly (not local file)
            return await upload_to_instagram(video_url, credentials, metadata)

        except Exception as e:
            return {"platform": platform.value, "status": "error", "message": str(e)}

    return {"platform": platform.value, "status": "error", "message": "Unknown platform"}


async def process_publish_request(
    request: PublishRequest,
    dry_run: bool = False,
) -> list[dict]:
    """
    Process a publish request by downloading the video and uploading to all platforms.

    Args:
        request: The publish request.
        dry_run: If True, validate but don't upload.

    Returns:
        A list of results for each platform.
    """
    results = []

    # Create temp directory for video download
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Download video from public URL
        parsed_url = urlparse(request.video_url)
        video_filename = parsed_url.path.split("/")[-1] or "video.mp4"
        local_video_path = os.path.join(tmp_dir, video_filename)

        platforms_str = ", ".join(p.value for p in request.platforms)
        logger.info(f"🚀 [{request.channel_id}] Starting upload to {len(request.platforms)} platforms: {platforms_str}")

        if not dry_run:
            try:
                logger.info(f"📥 [{request.channel_id}] Downloading video: {video_filename}")
                await download_from_url(request.video_url, local_video_path)
                logger.info(f"📥 [{request.channel_id}] Download complete")
            except Exception as e:
                logger.error(f"❌ [{request.channel_id}] Video download failed: {e}")
                return [{"platform": "all", "status": "error", "message": f"Video download failed: {e}"}]

        # Upload to each platform
        for platform in request.platforms:
            logger.info(f"📤 [{request.channel_id}] Uploading to {platform.value}...")
            result = await upload_to_platform(
                platform=platform,
                channel_id=request.channel_id,
                video_path=local_video_path if not dry_run else "",
                video_url=request.video_url,
                title=request.title,
                description=request.description,
                caption=request.caption,
                dry_run=dry_run,
            )
            
            # Log result with appropriate emoji
            status = result.get("status", "unknown")
            if status == "success":
                video_id = result.get("video_id") or result.get("post_id") or result.get("media_id") or ""
                logger.info(f"✅ [{request.channel_id}] {platform.value}: Success (id: {video_id})")
            elif status == "validated":
                logger.info(f"✓ [{request.channel_id}] {platform.value}: Validated")
            else:
                error_msg = result.get("message", "Unknown error")[:100]
                logger.error(f"❌ [{request.channel_id}] {platform.value}: Failed - {error_msg}")
            
            results.append(result)

        # Summary
        success_count = sum(1 for r in results if r.get("status") == "success")
        logger.info(f"🏁 [{request.channel_id}] Upload complete: {success_count}/{len(results)} succeeded")

    return results


# --- API Endpoints ---


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )


@app.get("/validate/{channel_id}", response_model=ValidateResponse)
async def validate_secrets(
    channel_id: str,
    platforms: list[Platform] = Query(default=[Platform.YOUTUBE, Platform.TIKTOK]),
):
    """
    Validate that all required secrets exist for a channel.

    This endpoint checks if the necessary secrets are configured in
    GCP Secret Manager for the given channel and platforms.
    """
    platform_names = [p.value for p in platforms]
    validation_result = validate_channel_secrets(channel_id, platform_names)

    return ValidateResponse(
        channel_id=channel_id,
        platforms=validation_result,
        all_valid=all(validation_result.values()),
    )


@app.post("/publish", response_model=PublishResponse)
async def publish(
    request: PublishRequest,
    background_tasks: BackgroundTasks,
    dry_run: bool = Query(
        default=False,
        description="If true, validate secrets and video URI but don't upload.",
    ),
):
    """
    Publish a video to multiple social media platforms.

    This endpoint:
    1. Downloads the video from GCS to a temporary location.
    2. Dynamically resolves secrets using the Config-Driven Pattern.
    3. Uploads to each specified platform (in background if not dry_run).

    The response is immediate; uploads happen asynchronously.
    """
    platforms_str = ", ".join(p.value for p in request.platforms)
    logger.info(
        f"📨 [{request.channel_id}] Received publish request for {len(request.platforms)} platforms: {platforms_str}"
    )

    if dry_run:
        # Synchronous validation
        results = await process_publish_request(request, dry_run=True)
        all_valid = all(r.get("status") == "validated" for r in results)

        return PublishResponse(
            status="validated" if all_valid else "error",
            message=f"Dry run complete. Results: {results}",
            channel_id=request.channel_id,
            platforms=[p.value for p in request.platforms],
        )

    # Schedule actual upload as background task
    background_tasks.add_task(process_publish_request, request, False)

    return PublishResponse(
        status="accepted",
        message="Upload tasks scheduled. Check logs for progress.",
        channel_id=request.channel_id,
        platforms=[p.value for p in request.platforms],
        job_id=None,  # TODO: Generate job ID for tracking
    )


# --- Main Entry Point ---


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
