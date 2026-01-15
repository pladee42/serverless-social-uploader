# 🚀 Universal Social Media Uploader

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Cloud Run](https://img.shields.io/badge/Google%20Cloud-Run-4285F4.svg)](https://cloud.google.com/run)

A **serverless FastAPI** application for uploading videos to multiple social media platforms (YouTube, TikTok, Instagram, Facebook) from a single API call.

> ⚠️ **Personal Use Only**: This project uses "No-Review" authentication strategies designed for internal/personal use. It is not intended for public app distribution.

---

## ✨ Features

- **🎯 Single API Endpoint** — Upload to multiple platforms with one `POST /publish` request
- **🔐 Config-Driven Secrets** — Dynamic secret resolution using `{CHANNEL_ID}_{PLATFORM}_{KEY}` pattern
- **📺 YouTube** — OAuth2 Refresh Token flow with resumable uploads
- **🎵 TikTok** — Browser automation via Playwright (coming soon)
- **📸 Meta** — Instagram & Facebook via Graph API (coming soon)
- **☁️ Serverless** — Runs on Google Cloud Run with scale-to-zero
- **🆓 Zero Cost** — Designed for GCP Free Tier

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     POST /publish                            │
│  { channel_id, video_url, platforms: ["youtube", "tiktok"] }│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Secret Manager                            │
│  Pattern: {CHANNEL_ID}_{PLATFORM}_{KEY}                      │
│  Example: TIMELINE_B_YOUTUBE_REFRESH_TOKEN                   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ YouTube  │   │  TikTok  │   │   Meta   │
        │ (OAuth2) │   │(Browser) │   │ (Token)  │
        └──────────┘   └──────────┘   └──────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.14+
- Google Cloud account with:
  - Cloud Run API enabled
  - Secret Manager API enabled
- Docker (for deployment)

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/serverless-social-uploader.git
cd serverless-social-uploader

# Create conda environment
conda create -n social-mng python=3.14 -c conda-forge
conda activate social-mng

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up YouTube Credentials

```bash
# Download OAuth2 credentials from Google Cloud Console
# Save as client_secret.json in the project root

# Generate and save tokens to Secret Manager
python tools/get_youtube_token.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT
```

### 3. Run Locally

```bash
uvicorn main:app --reload --port 8080
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8080/

# Validate secrets exist
curl "http://localhost:8080/validate/timeline_b?platforms=youtube"

# Publish video (dry run)
curl -X POST http://localhost:8080/publish?dry_run=true \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "timeline_b",
    "video_url": "https://storage.googleapis.com/your-bucket/video.mp4",
    "platforms": ["youtube"],
    "title": "My Video Title",
    "description": "Video description"
  }'
```

---

## 📁 Project Structure

```
serverless-social-uploader/
├── main.py                    # FastAPI application
├── Dockerfile                 # Container with Playwright support
├── requirements.txt           # Python dependencies
├── platforms/
│   ├── youtube.py            # YouTube uploader (Refresh Token)
│   ├── tiktok.py             # TikTok uploader (Browser) [WIP]
│   └── meta.py               # Facebook/Instagram [WIP]
├── utils/
│   └── secrets.py            # Dynamic secret resolution
└── tools/
    └── get_youtube_token.py  # Local OAuth2 token generator
```

---

## 🔐 Authentication Strategies

| Platform | Strategy | Secret Keys Required |
|----------|----------|---------------------|
| YouTube | OAuth2 Refresh Token | `CLIENT_ID`, `CLIENT_SECRET`, `REFRESH_TOKEN` |
| TikTok | Browser Session Cookie | `SESSION_COOKIE` |
| Facebook | Long-Lived User Token | `ACCESS_TOKEN`, `PAGE_ID` |
| Instagram | Long-Lived User Token | `ACCESS_TOKEN`, `USER_ID` |

### Secret Naming Convention

All secrets follow the pattern: `{CHANNEL_ID}_{PLATFORM}_{KEY}`

**Example for channel "timeline_b":**
- `TIMELINE_B_YOUTUBE_CLIENT_ID`
- `TIMELINE_B_YOUTUBE_CLIENT_SECRET`
- `TIMELINE_B_YOUTUBE_REFRESH_TOKEN`
- `TIMELINE_B_TIKTOK_SESSION_COOKIE`

---

## 🐳 Deployment to Cloud Run

```bash
# Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy social-uploader \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 300
```

---

## 📚 API Reference

### `GET /`
Health check endpoint.

**Response:**
```json
{ "status": "healthy", "version": "0.1.0" }
```

### `GET /validate/{channel_id}`
Validate that secrets exist for a channel.

**Query Parameters:**
- `platforms` — List of platforms to validate (default: `["youtube", "tiktok"]`)

### `POST /publish`
Upload video to multiple platforms.

**Request Body:**
```json
{
  "channel_id": "string",
  "video_url": "string",
  "platforms": ["youtube", "tiktok"],
  "title": "string",
  "description": "string",
  "caption": "string"
}
```

**Query Parameters:**
- `dry_run` — If true, validate without uploading (default: `false`)

---

## 🛠️ Development

### Running Tests

```bash
pytest tests/
```

### Interactive API Docs

Once running, visit:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

---

## 📄 License

MIT License — feel free to use this for your own projects!

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) — Modern, fast web framework
- [Playwright](https://playwright.dev/) — Browser automation
- [Google Cloud](https://cloud.google.com/) — Infrastructure

---

<p align="center">
  Made with ❤️ for content creators who value automation
</p>
