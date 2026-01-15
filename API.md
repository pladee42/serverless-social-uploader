# API Reference

The `serverless-social-uploader` service provides a single main endpoint for publishing videos. Authentication for the destination platforms (YouTube, TikTok, etc.) is handled internally via GCP Secret Manager based on the provided `channel_id`.

## Base URL : `[YOUR_SERVICE_URL]` (e.g., `http://localhost:8080` or your Cloud Run URL)

## Endpoints

### 1. Publish Video
**Endpoint:** `POST /publish`

Initiates a video upload to the specified social media platforms. The service downloads the video from the public URL and uploads it asynchronously.

**Headers:**
- `Content-Type`: `application/json`

**Query Parameters:**
- `dry_run` (boolean, optional): If `true`, validates secrets and video URL availability without performing the actual upload. Default is `false`.

**Request Body (JSON):**

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `channel_id` | string | **Yes** | Identifier to resolve secrets (e.g., `"timeline_b"`). Secrets must exist in GCP Secret Manager (e.g., `TIMELINE_B_YOUTUBE_REFRESH_TOKEN`). |
| `video_url` | string | **Yes** | Publicly accessible URL of the video file (mp4). |
| `platforms` | array | **Yes** | List of target platforms: `"youtube"`, `"tiktok"`, `"facebook"`, `"instagram"`. |
| `title` | string | No | Video title (used by YouTube, Facebook). |
| `description` | string | No | Long description (used by YouTube, Facebook). |
| `caption` | string | No | Short caption (used by TikTok, Instagram). |
| `tags` | array | No | List of tags (used by YouTube). |
| `ai_generated`| boolean| No | Flags content as AI-generated (default: `false`). |
| `privacy_status`| string | No | `"private"`, `"unlisted"`, or `"public"` (default: `"private"`). |
| `category_id` | string | No | YouTube category ID (default: `"27"` for Entertainment). |
| `share_to_facebook` | boolean | No | If `true` and uploading to Instagram, enables cross-posting to Facebook (skips separate FB upload). |

**Example Request:**

```json
{
  "channel_id": "timeline_b",
  "video_url": "https://storage.googleapis.com/my-bucket/video.mp4",
  "platforms": ["youtube", "tiktok", "instagram"],
  "title": "What if Napoleon won? #history",
  "description": "An alternate history deep dive.\n\n#history #documentary",
  "caption": "Napoleon's victory? 🤯 #althistory",
  "tags": ["history", "education", "napoleon"],
  "ai_generated": true,
  "privacy_status": "public",
  "share_to_facebook": true
}
```

**Response (200 OK):**

```json
{
  "status": "accepted",
  "message": "Upload tasks scheduled. Check logs for progress.",
  "channel_id": "timeline_b",
  "platforms": ["youtube", "tiktok", "instagram"],
  "job_id": null
}
```

### 2. Validation (Optional)
**Endpoint:** `GET /validate/{channel_id}`

Checks if the necessary credentials (secrets) exist in GCP Secret Manager for the given channel.

**Query Parameters:**
- `platforms`: List of platforms to check (e.g., `?platforms=youtube&platforms=tiktok`).

**Response:**
```json
{
  "channel_id": "timeline_b",
  "platforms": {
    "youtube": true,
    "tiktok": false
  },
  "all_valid": false
}
```
