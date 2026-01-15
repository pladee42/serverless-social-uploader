"""
TikTok Video Uploader using Playwright.

This module implements browser automation to upload videos to TikTok
by injecting session cookies to bypass the login flow.

Authentication Flow:
    1. User manually extracts 'sessionid' cookie from their browser
    2. Cookie is stored in GCP Secret Manager as {CHANNEL_ID}_TIKTOK_SESSION_COOKIE
    3. Playwright injects the cookie and navigates to TikTok upload page
    4. Automation fills in the form and submits the video

Note:
    This approach bypasses TikTok's official API (which requires app review)
    and is intended for personal/internal use only.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# TikTok URLs
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"
TIKTOK_CREATOR_URL = "https://www.tiktok.com/creator"

# Timeouts
NAVIGATION_TIMEOUT = 120000  # 2 minutes for navigation (TikTok can be slow)
DEFAULT_TIMEOUT = 60000  # 60 seconds
UPLOAD_TIMEOUT = 300000  # 5 minutes for video processing


@dataclass
class TikTokCredentials:
    """Container for TikTok session credentials."""

    session_cookie: str


@dataclass
class TikTokVideoMetadata:
    """Metadata for the video to upload."""

    caption: str = ""
    allow_comments: bool = True
    allow_duet: bool = True
    allow_stitch: bool = True
    visibility: str = "public"  # "public", "friends", "private"


async def _inject_cookies(page: Page, session_cookie: str) -> None:
    """Inject the TikTok session cookie into the browser context."""
    cookies = [
        {
            "name": "sessionid",
            "value": session_cookie,
            "domain": ".tiktok.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }
    ]
    await page.context.add_cookies(cookies)
    logger.info("Injected TikTok session cookie")


async def _wait_for_upload_ready(page: Page) -> bool:
    """Wait for the upload page to be ready."""
    try:
        # Wait for the file input or upload button to appear
        await page.wait_for_selector(
            'input[type="file"], [class*="upload"], [data-testid*="upload"]',
            timeout=DEFAULT_TIMEOUT,
        )
        return True
    except PlaywrightTimeout:
        logger.error("Upload page did not load in time")
        return False


async def _upload_video_file(page: Page, video_path: str) -> bool:
    """Upload the video file using the file input."""
    try:
        # Find the file input (usually hidden)
        file_input = await page.query_selector('input[type="file"][accept*="video"]')

        if not file_input:
            # Try alternative selectors
            file_input = await page.query_selector('input[type="file"]')

        if file_input:
            await file_input.set_input_files(video_path)
            logger.info(f"Uploaded file: {video_path}")
            return True
        else:
            logger.error("Could not find file input element")
            return False

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return False


async def _fill_caption(page: Page, caption: str) -> bool:
    """Fill in the video caption."""
    try:
        # TikTok uses a contenteditable div for the caption
        caption_selectors = [
            '[data-testid="caption-editor"]',
            '[class*="DraftEditor"]',
            '[class*="caption"] [contenteditable="true"]',
            '[contenteditable="true"]',
        ]

        for selector in caption_selectors:
            caption_element = await page.query_selector(selector)
            if caption_element:
                await caption_element.click()
                await page.keyboard.type(caption, delay=50)
                logger.info(f"Filled caption: {caption[:50]}...")
                return True

        logger.warning("Could not find caption input, continuing without caption")
        return True

    except Exception as e:
        logger.error(f"Error filling caption: {e}")
        return False


async def _wait_for_video_processing(page: Page) -> bool:
    """Wait for TikTok to finish processing the uploaded video."""
    try:
        # Wait for processing indicator to appear and then disappear
        logger.info("Waiting for video processing...")

        # Look for the "Post" button to become enabled
        post_button_selectors = [
            'button:has-text("Post")',
            '[data-testid="post-button"]',
            'button[class*="post"]',
        ]

        for selector in post_button_selectors:
            try:
                await page.wait_for_selector(
                    f'{selector}:not([disabled])',
                    timeout=UPLOAD_TIMEOUT,
                )
                logger.info("Video processing complete, Post button is ready")
                return True
            except PlaywrightTimeout:
                continue

        logger.warning("Could not confirm video processing completion")
        return True  # Continue anyway

    except Exception as e:
        logger.error(f"Error waiting for video processing: {e}")
        return False


async def _click_post_button(page: Page) -> bool:
    """Click the Post button to publish the video."""
    try:
        post_button_selectors = [
            'button:has-text("Post")',
            '[data-testid="post-button"]',
            'button[class*="post"]',
            'button:has-text("Publish")',
        ]

        for selector in post_button_selectors:
            button = await page.query_selector(selector)
            if button:
                is_disabled = await button.get_attribute("disabled")
                if not is_disabled:
                    await button.click()
                    logger.info("Clicked Post button")

                    # Wait for confirmation
                    await asyncio.sleep(3)
                    return True

        logger.error("Could not find or click Post button")
        return False

    except Exception as e:
        logger.error(f"Error clicking post button: {e}")
        return False


async def upload_video(
    video_path: str,
    credentials: TikTokCredentials,
    metadata: TikTokVideoMetadata,
    headless: bool = True,
    screenshot_on_error: bool = True,
) -> dict:
    """
    Upload a video to TikTok using browser automation.

    Args:
        video_path: Local path to the video file.
        credentials: TikTokCredentials containing session cookie.
        metadata: TikTokVideoMetadata with caption, etc.
        headless: Whether to run browser in headless mode.
        screenshot_on_error: Whether to take screenshot on failure.

    Returns:
        A dict with upload result.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    file_size = os.path.getsize(video_path)
    logger.info(f"Uploading video to TikTok: {video_path} ({file_size / 1024 / 1024:.1f} MB)")

    browser: Optional[Browser] = None

    try:
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )

            # Create context with realistic viewport and locale
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/Los_Angeles",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
            )
            
            # Set default timeout for all operations
            context.set_default_timeout(DEFAULT_TIMEOUT)

            page = await context.new_page()

            # Inject session cookie
            await _inject_cookies(page, credentials.session_cookie)

            # Navigate to upload page with longer timeout and less strict wait
            logger.info(f"Navigating to {TIKTOK_UPLOAD_URL}")
            try:
                # Use domcontentloaded instead of networkidle (TikTok keeps loading)
                await page.goto(
                    TIKTOK_UPLOAD_URL,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT,
                )
                # Give the page a moment to stabilize
                await asyncio.sleep(3)
            except PlaywrightTimeout:
                logger.error("Navigation to TikTok timed out - TikTok may be blocking the request")
                if screenshot_on_error:
                    await page.screenshot(path="/tmp/tiktok_error_navigation.png")
                return {
                    "platform": "tiktok",
                    "status": "error",
                    "message": "Navigation timeout - TikTok may be blocking automated access",
                }

            # Check if we're logged in (should redirect to creator center)
            current_url = page.url
            if "login" in current_url.lower():
                logger.error("Session cookie is invalid or expired - redirected to login")
                return {
                    "platform": "tiktok",
                    "status": "error",
                    "message": "Session cookie expired. Please extract a new cookie.",
                }

            # Wait for upload page to be ready
            if not await _wait_for_upload_ready(page):
                if screenshot_on_error:
                    await page.screenshot(path="/tmp/tiktok_error_upload_page.png")
                return {
                    "platform": "tiktok",
                    "status": "error",
                    "message": "Upload page failed to load",
                }

            # Upload the video file
            if not await _upload_video_file(page, video_path):
                if screenshot_on_error:
                    await page.screenshot(path="/tmp/tiktok_error_file_upload.png")
                return {
                    "platform": "tiktok",
                    "status": "error",
                    "message": "Failed to upload video file",
                }

            # Wait for video processing
            if not await _wait_for_video_processing(page):
                if screenshot_on_error:
                    await page.screenshot(path="/tmp/tiktok_error_processing.png")
                return {
                    "platform": "tiktok",
                    "status": "error",
                    "message": "Video processing failed or timed out",
                }

            # Fill in caption
            if metadata.caption:
                await _fill_caption(page, metadata.caption)

            # Click Post button
            if not await _click_post_button(page):
                if screenshot_on_error:
                    await page.screenshot(path="/tmp/tiktok_error_post.png")
                return {
                    "platform": "tiktok",
                    "status": "error",
                    "message": "Failed to click Post button",
                }

            # Wait for success indication
            await asyncio.sleep(5)

            logger.info("✅ TikTok upload completed successfully!")
            return {
                "platform": "tiktok",
                "status": "success",
                "message": "Video uploaded successfully",
                "caption": metadata.caption[:50] + "..." if len(metadata.caption) > 50 else metadata.caption,
            }

    except Exception as e:
        logger.error(f"❌ TikTok upload error: {e}")
        return {
            "platform": "tiktok",
            "status": "error",
            "message": str(e),
        }

    finally:
        if browser:
            await browser.close()
