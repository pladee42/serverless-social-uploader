# 🚀 Project Specification: "Universal Social Media Uploader" (No-Review Edition)

## 1. Project Overview & Constraints

I am building a **Serverless FastAPI** backend on **Google Cloud Run** to automate video uploads for my personal social media brands ("Timeline B", "Timeline C").

**The Problem:** Content creators need to upload video files to multiple platforms (YouTube, TikTok, Instagram, Facebook) programmatically. Official APIs are often expensive, restricted, or complex.

**Critical Constraint:** NO APP REVIEW
This system is for **internal/personal use only**. I will **not** submit this app for Facebook, TikTok, or Google verification. The code must strictly use "Developer/Testing" authentication methods that bypass the need for public app review.

**The Goal:**
A "Universal Adapter" API that accepts a video file (from GCS) and a generic `channel_id`, dynamically fetches the correct "Dev Mode" credentials from **GCP Secret Manager**, and uploads the content.

**Key Requirements:**

* **Infrastructure:** GCP Cloud Run (Serverless Docker Container).
* **Multi-Tenant Design:** The code must be **agnostic**. It should not know what "Timeline B" is. It should dynamically load configuration based on the request.
* **Zero-Cost Operation:** Designed to run within GCP Free Tier limits (scale to zero).

---

## 2. Authentication & "No-Review" Strategy

The code must implement the following authentication patterns to avoid App Review:

1. **YouTube (Testing/Internal Mode):**
* **Do NOT** use Service Accounts (they don't work for standard channels).
* **Do NOT** use the web-server OAuth flow (requires verified redirect URIs).
* **Strategy:** Use a locally generated **OAuth2 Refresh Token**. The API simply exchanges this refresh token for an access token on the fly.
* *Constraint:* I will manually re-authenticate weekly (if using Gmail) or rarely (if using Workspace Internal).


2. **Facebook & Instagram (Dev Mode):**
* **Strategy:** The app remains in "In Development" status.
* **Auth:** Use **Long-Lived User Access Tokens** (60-day expiry). The API should assume these tokens are stored in Secret Manager.


3. **TikTok (Browser Automation):**
* **Strategy:** Bypass the official API entirely (which requires strict review).
* **Auth:** Use **Session Cookies** extracted from a browser. The API will inject these cookies into a headless Chromium instance to simulate a logged-in user.

---

## 3. The "Open Source" Design Pattern (Critical)

To ensure this project is high-quality and "star-worthy" on GitHub, strictly follow this **Config-Driven Pattern**:

1. **No Hardcoding:** Never write `if channel == "Timeline B"`.
2. **Dynamic Secret Lookup:** The code must construct secret keys dynamically based on the input.
* *Formula:* `{CHANNEL_ID_UPPERCASE}_{PLATFORM}_{KEY_TYPE}`
* *Example:* If the request is for `channel_id="gaming_hub"`, the code automatically looks for a secret named `GAMING_HUB_TIKTOK_COOKIE`.

---

## 4. Architecture & Tech Stack

### **Core Stack**

* **Language:** Python 3.14+
* **Framework:** `FastAPI` (Async) with `Uvicorn`
* **Container:** Docker (Base image: `mcr.microsoft.com/playwright/python:v1.44.0-jammy` to support headless browser).
* **Infrastructure:** Google Cloud Run (Serverless).

### **Data Flow**

1. **Request:** POST `/publish` with `channel_id` (e.g., "timeline_b").
2. **Download:** Pull video from GCS to `/tmp/`.
3. **Config:** Look up secrets based on pattern: `{CHANNEL_ID}_TIKTOK_COOKIE`, `{CHANNEL_ID}_YT_REFRESH_TOKEN`.
4. **Execute:** Run uploaders in background tasks.

---

## 5. Module Specifications

### **A. `Dockerfile**`

* Must use the Microsoft Playwright base image.
* Install: `fastapi`, `uvicorn`, `google-cloud-storage`, `google-cloud-secret-manager`, `google-api-python-client`, `playwright`.
* Run `playwright install chromium` inside the build.

### **B. `main.py` (The Generic Gateway)**

* **Endpoint:** `POST /publish`
* **Logic:**
* Accept generic payload: `{"channel_id": "str", "video_uri": "str", "platforms": ["list"]}`.
* **Crucial:** Do not hardcode "Timeline B". Use `channel_id` to construct secret names dynamically.



### **C. `platforms/youtube.py` (The "Refresh Token" Flow)**

* **Input:** Video path, Title, Description, `client_id`, `client_secret`, `refresh_token`.
* **Logic:**
* Use `google.oauth2.credentials.Credentials` to rebuild credentials from the `refresh_token`.
* Upload using `googleapiclient.discovery.build('youtube', 'v3')`.
* *Note:* Handle "Resumable Uploads" for large files.



### **D. `platforms/tiktok.py` (The "Playwright" Flow)**

* **Input:** Video path, Caption, `session_cookie_string`.
* **Logic:**
* Launch `async_playwright` (Chromium).
* Inject cookie: `{"name": "sessionid", "value": cookie, "domain": ".tiktok.com"}`.
* Navigate to `https://www.tiktok.com/upload`.
* Wait for selectors (use text-based selectors like "Select file" to be robust).



### **E. `tools/get_youtube_token.py` (Local Script)**

* A standalone script I run on my laptop.
* Uses `InstalledAppFlow.from_client_secrets_file` with `run_console()`.
* **Purpose:** It prints the **Refresh Token** so I can paste it into GCP Secret Manager.

---

## 6. Development Prompts (Copy/Paste these to AI)

**Prompt 1: Infrastructure & "No-Review" Setup**

> "Generate a project structure for a FastAPI app on Google Cloud Run. Use the official Playwright Python image in the `Dockerfile`. Create `requirements.txt`.
> **Important:** This project uses 'No-Review' authentication. We will NOT use Service Accounts. We will use Refresh Tokens for Google and Session Cookies for TikTok. Structure the code to fetch these strings from Google Secret Manager dynamically based on a `channel_id`."

**Prompt 2: YouTube Module (Refresh Token Logic)**

> "Write `platforms/youtube.py`. It must authenticate using a **Refresh Token**, Client ID, and Client Secret passed as arguments (do not look for a credentials.json file). It should rebuild the `Credentials` object and upload a video. Also, provide a separate script `tools/get_youtube_token.py` that runs a local Console OAuth flow to help me generate that Refresh Token initially."

**Prompt 3: TikTok Module (Browser Automation)**

> "Write `platforms/tiktok.py` using `async_playwright`. The function receives a `sessionid` cookie string. It must launch a headless browser, inject the cookie to bypass the login screen, and upload a video file to TikTok. Include error handling for timeouts."

**Prompt 4: The Generic API**

> "Write `main.py`. It should have a `POST /publish` endpoint. It downloads the video from GCS to `/tmp`. Then, it constructs the secret names (e.g., `f'{channel_id.upper()}_YT_REFRESH_TOKEN'`) and calls the platform modules. Use `BackgroundTasks` so the API responds immediately."



