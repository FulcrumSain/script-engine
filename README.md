# Script Engine — Setup Guide

A team tool that takes any YouTube URL and generates 5 camera-ready short-form script variations, then exports them directly to Google Docs.

---

## How It Works

```
Team member pastes YouTube URL
        ↓
Backend fetches transcript
        ↓
Claude generates 5 scripts using your writing framework
        ↓
Scripts appear in the UI, exported to Google Docs
```

---

## Project Structure

```
scripttool/
├── backend/
│   ├── app.py              ← Flask API (Python)
│   └── requirements.txt
├── frontend/
│   └── index.html          ← Team UI (hosted on GitHub Pages)
├── render.yaml             ← Render.com deploy config
└── README.md
```

---

## Step 1 — Push to GitHub

1. Create a new GitHub repository (e.g. `script-engine`)
2. Upload all files from this folder into it
3. Keep the folder structure exactly as-is

---

## Step 2 — Deploy the Backend to Render (free)

The backend handles transcript fetching and AI generation. It needs to run on a server, not GitHub Pages.

1. Go to **[render.com](https://render.com)** and create a free account
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Render will detect `render.yaml` automatically — it sets everything up for you
5. Add your environment variable:
   - Key: `ANTHROPIC_API_KEY`
   - Value: your Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com))
6. Click **Deploy**
7. After deploy finishes, copy your Render URL (e.g. `https://script-engine-api.onrender.com`)

---

## Step 3 — Set Up Google OAuth (for Google Docs export)

This lets team members sign in with their own Google account and export scripts to their Drive.

### 3a. Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (call it `Script Engine`)
3. Enable these two APIs:
   - **Google Docs API**
   - **Google Drive API**
   (Search for each under "APIs & Services → Library")

### 3b. Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Name: `Script Engine`
5. Under **Authorised JavaScript origins**, add:
   - `https://YOUR-GITHUB-USERNAME.github.io` (your GitHub Pages URL)
   - `http://localhost:8080` (for local testing)
6. Click **Create**
7. Copy the **Client ID** (looks like `123456789-abc....apps.googleusercontent.com`)

### 3c. Set Up OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. User type: **External**
3. Fill in app name (`Script Engine`), your email
4. Add scopes:
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/drive.file`
   - `https://www.googleapis.com/auth/userinfo.profile`
5. Under **Test users**, add every email address on your team
6. Save

> **Note:** While in "Testing" mode, only added test users can sign in. To open it up, you'd submit for Google verification — but for a private team tool, test mode is fine indefinitely.

---

## Step 4 — Update the Frontend Config

Open `frontend/index.html` and find these two lines near the top of the `<script>` section:

```js
const API_URL = window.location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://YOUR-BACKEND-URL.onrender.com'; // ← update this
```

And in two places in the HTML, find:
```
data-client_id="YOUR_GOOGLE_CLIENT_ID"
client_id: 'YOUR_GOOGLE_CLIENT_ID',
```

Replace both `YOUR_GOOGLE_CLIENT_ID` with your actual Google OAuth Client ID.
Replace `YOUR-BACKEND-URL` with your Render URL.

Save and commit the file.

---

## Step 5 — Enable GitHub Pages

1. In your GitHub repo, go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/frontend` (or `/docs` if you rename the folder)

> **Tip:** If GitHub Pages only serves from root or `/docs`, either rename `frontend/` to `docs/`, or move `index.html` to the repo root.

4. Save — GitHub will give you a URL like `https://your-username.github.io/script-engine`
5. Share this URL with your team

---

## Step 6 — Test It

1. Open your GitHub Pages URL
2. Paste a YouTube URL with captions
3. Click **Generate Scripts**
4. Five scripts should appear within ~30 seconds
5. Click **Sign in with Google** → toggle **Export to Google Docs** → generate again
6. A Google Doc should appear in your Drive

---

## Local Development

To run the full tool locally:

```bash
# Backend
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python app.py
# → Running on http://localhost:5000

# Frontend (in a second terminal)
cd frontend
python -m http.server 8080
# → Open http://localhost:8080
```

---

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Render dashboard | Your Anthropic API key |

No other secrets needed — Google auth happens client-side.

---

## Costs

| Service | Cost |
|---|---|
| Render (backend) | Free tier (spins down after inactivity — first request after sleep takes ~30s) |
| GitHub Pages (frontend) | Free |
| Anthropic API | ~$0.05–0.15 per video (Claude Opus, ~4k output tokens) |
| Google APIs | Free for this usage level |

To avoid cold-start delays on Render, upgrade to the $7/mo paid plan — it keeps the server always-on.

---

## Troubleshooting

**"Failed to fetch" on generate**
- Check your `API_URL` in `index.html` points to the correct Render URL
- Make sure your Render service is deployed and healthy (check Render dashboard logs)
- Check CORS — the backend allows all origins by default

**"No transcript found"**
- The video doesn't have captions. Try a video with auto-generated or manual subtitles.

**Google sign-in not working**
- Make sure your GitHub Pages URL is in the "Authorised JavaScript origins" list in Google Cloud Console
- Make sure your email is added as a test user in the OAuth consent screen

**Scripts look wrong / missing sections**
- This can happen if Claude formats output slightly differently — check the Raw tab to see the full output
- The parser is flexible but if issues persist, the Raw tab always has the full content to copy

---

## Adding Team Members

No account system needed. Just share the GitHub Pages URL. Each person signs in with their own Google account to enable Docs export. Their scripts go to their own Google Drive.

---

## Updating the Writing Framework

The system prompt lives in `backend/app.py` at the top of the file in the `SYSTEM_PROMPT` variable. Edit it directly and redeploy (push to GitHub → Render auto-redeploys).
