# 🚀 Universal Social Media Uploader

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Cloud Run](https://img.shields.io/badge/Google%20Cloud-Run-4285F4.svg)](https://cloud.google.com/run)
[![Deploy](https://github.com/pladee42/serverless-social-uploader/actions/workflows/deploy.yml/badge.svg)](https://github.com/pladee42/serverless-social-uploader/actions/workflows/deploy.yml)

A **serverless FastAPI** application for uploading videos to multiple social media platforms (YouTube, TikTok, Instagram, Facebook) from a single API call.

> ⚠️ **Personal Use Only**: This project uses "No-Review" authentication strategies designed for internal/personal use. It is not intended for public app distribution.

---

## ✨ Features

- **🎯 Single API Endpoint** — Upload to multiple platforms with one `POST /publish` request
- **🔐 Config-Driven Secrets** — Dynamic secret resolution using `{CHANNEL_ID}_{PLATFORM}_{KEY}` pattern
- **📺 YouTube** — OAuth2 Refresh Token flow with resumable uploads
- **🎵 TikTok (Experimental)** — Playwright automation (Subject to bot detection on Cloud IPs)
- **📸 Meta** — Instagram & Facebook via Graph API v24.0
- **🔗 Cross-Posting** — Instagram Reels auto-share to Facebook for **combined view counts**
- **☁️ Serverless** — Runs on Google Cloud Run with scale-to-zero
- **🆓 Zero Cost** — Designed for GCP Free Tier
- **🚀 CI/CD** — Auto-deploy via GitHub Actions

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
  - Artifact Registry API enabled
- Docker (for local container testing)

### 1. Clone & Install

```bash
git clone https://github.com/pladee42/serverless-social-uploader.git
cd serverless-social-uploader

# Create environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up Platform Credentials

```bash
# YouTube - OAuth2 tokens
python tools/get_youtube_token.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT

# TikTok - Session cookie
python tools/get_tiktok_cookie.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT

# Meta (Facebook/Instagram) - Access tokens
python tools/get_meta_token.py --save --channel-id YOUR_CHANNEL --project YOUR_PROJECT
```

### 3. Run Locally

```bash
export GCP_PROJECT=your-project-id
uvicorn main:app --reload --port 8080
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8080/

# Validate secrets exist
curl "http://localhost:8080/validate/YOUR_CHANNEL?platforms=youtube&platforms=tiktok"

# Publish video (dry run)
curl -X POST "http://localhost:8080/publish?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "YOUR_CHANNEL",
    "video_url": "https://storage.googleapis.com/your-bucket/video.mp4",
    "platforms": ["youtube", "tiktok", "facebook", "instagram"],
    "title": "My Video Title",
    "description": "Video description"
  }'
```

---

## 📁 Project Structure

```
serverless-social-uploader/
├── main.py                       # FastAPI application
├── Dockerfile                    # Container with Playwright support
├── requirements.txt              # Python dependencies
├── platforms/
│   ├── youtube.py               # YouTube uploader (OAuth2 Refresh Token)
│   ├── tiktok.py                # TikTok uploader (Playwright Browser)
│   └── meta.py                  # Facebook/Instagram (Graph API)
├── utils/
│   └── secrets.py               # Dynamic secret resolution
├── tools/
│   ├── get_youtube_token.py     # YouTube OAuth2 token generator
│   ├── get_tiktok_cookie.py     # TikTok session cookie helper
│   └── get_meta_token.py        # Meta access token helper
└── .github/
    └── workflows/
        └── deploy.yml           # GitHub Actions CI/CD
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

**Example for channel "my_channel":**
- `MY_CHANNEL_YOUTUBE_CLIENT_ID`
- `MY_CHANNEL_YOUTUBE_CLIENT_SECRET`
- `MY_CHANNEL_YOUTUBE_REFRESH_TOKEN`
- `MY_CHANNEL_TIKTOK_SESSION_COOKIE`
- `MY_CHANNEL_FACEBOOK_ACCESS_TOKEN`
- `MY_CHANNEL_FACEBOOK_PAGE_ID`
- `MY_CHANNEL_INSTAGRAM_ACCESS_TOKEN`
- `MY_CHANNEL_INSTAGRAM_USER_ID`

---

##  Deployment

### Option 1: GitHub Actions (Recommended)

1. Fork this repository
2. Add secrets in **Settings → Secrets and variables → Actions**:
   - `GCP_SA_KEY` — Service account JSON key
3. Add variables:
   - `GCP_PROJECT` — Your GCP project ID
   - `GCP_REGION` — Deployment region (e.g., `us-central1`)
4. Push to `main` branch — auto-deploys!

**Required GCP IAM Roles for Service Account:**
- `roles/run.admin`
- `roles/iam.serviceAccountUser`
- `roles/cloudbuild.builds.editor`
- `roles/storage.admin`
- `roles/artifactregistry.admin`
- `roles/serviceusage.serviceUsageConsumer`

### Option 2: Manual Deploy

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

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
- `platforms` — List of platforms to validate

### `POST /publish`
Upload video to multiple platforms.

**Request Body:**
```json
{
  "channel_id": "string",
  "video_url": "string",
  "platforms": ["youtube", "tiktok", "facebook", "instagram"],
  "title": "string",
  "description": "string",
  "caption": "string",
  "share_to_facebook": false
}
```

**Query Parameters:**
- `dry_run` — If true, validate without uploading (default: `false`)

> **💡 Cross-Posting:** Set `share_to_facebook: true` to cross-post Instagram Reels to Facebook with combined view counts. Facebook will be skipped if also in platforms list.

> **Note:** Cross-posting requires both `INSTAGRAM_USER_ID` and `FACEBOOK_PAGE_ID` secrets configured.

---

## ⚠️ Known Limitations

### TikTok Bot Detection
TikTok employs aggressive bot detection that frequently blocks data center IP addresses (such as Google Cloud Run).
- **Symptom**: `Navigation timeout` or `Page.goto` errors.
- **Workaround**: Run the service **locally** on your machine where residential IP reputation is better.
- **Long-term Solution**: I am evaluating the official [TikTok Content Posting API](https://developers.tiktok.com/products/content-posting-api/), which requires a formal App Review process.

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

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) — Modern, fast web framework
- [Playwright](https://playwright.dev/) — Browser automation
- [Google Cloud](https://cloud.google.com/) — Infrastructure

---

<p align="center">
  Made with ❤️ for content creators who value automation
</p>
