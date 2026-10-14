# Insta Auto-Poster

Posts a new web dev tip to Instagram every day, automatically.

Each day a GitHub Action:
1. picks the next tip (30 hand-written tips included, then optional AI-generated ones),
2. renders it as a 1080×1350 code-card image,
3. commits the image to this repo so Instagram can fetch it,
4. publishes it through the official Instagram Graph API,
5. refreshes your access token so it never expires.

No servers, no cost. Runs on GitHub Actions' free tier.

---

## One-time setup (~45 minutes)

### 1. Make your Instagram a professional account
Instagram app → **Settings → Account type and tools → Switch to professional account** → choose **Creator** (or Business). Personal accounts can't use the publishing API.

### 2. Create a Meta app and get an access token
1. Go to <https://developers.facebook.com> and log in. Create a developer account if asked.
2. **Create app**. When asked for a use case, pick the one for managing content on Instagram.
3. In the app dashboard, open **Instagram → API setup with Instagram business login**.
4. Under **Generate access tokens**, click **Add account** and log in with your Instagram account.
5. Copy the generated token. This is your `IG_ACCESS_TOKEN`. Treat it like a password.

The app can stay in development mode: it works for your own account because you're the app's owner. Meta changes this dashboard often, so the exact labels may differ slightly.

### 3. Test it on your computer (optional but recommended)
```powershell
# Windows PowerShell, in this folder
pip install -r requirements.txt
$env:IG_ACCESS_TOKEN = "paste-token-here"
python -m poster whoami          # should print your username
python -m poster preview --count 5   # renders sample images into .\preview
```

### 4. Put it on GitHub
1. Create a **public** repository, e.g. `insta-autoposter`. It must be public because Instagram downloads each image from the repo's public URL. Your token stays private in Secrets.
2. Push this folder to it.
3. Repo → **Settings → Secrets and variables → Actions**:

| Type | Name | Value |
|---|---|---|
| Secret | `IG_ACCESS_TOKEN` | the token from step 2 |
| Secret | `GH_PAT` | a GitHub fine-grained token for **this repo only** with **Secrets: Read and write**. Lets the workflow save the refreshed Instagram token. Without it you must replace the token manually every 60 days. |
| Secret | `GEMINI_API_KEY` | *optional*, free key from <https://aistudio.google.com>. Used to write new tips after the 30 built-in ones run out. Without it, the 30 tips repeat. |
| Variable | `IG_HANDLE` | your Instagram username without @ (shown on the image and caption) |

### 5. First run
1. Repo → **Actions → Daily Instagram post → Run workflow** with **dry run ✅**. Download the `post-preview` artifact to see the image.
2. Run it again with **dry run unchecked**. This publishes your first post.
3. From then on it posts automatically every day at **6:53 PM IST**.

---

## Customizing

- **Posting time:** edit the `cron` line in `.github/workflows/daily-post.yml` (it's in UTC; IST = UTC + 5:30).
- **Tips:** edit `poster/content.json`. Keep code lines under ~46 characters so the text stays large.
- **Design:** colors and layout are at the top of `poster/render.py`. Drop `bold.ttf`, `regular.ttf`, `mono.ttf` into a `fonts/` folder to use your own fonts.
- **Pause posting:** Actions → Daily Instagram post → **⋯ → Disable workflow**.
- **Facebook Login instead of Instagram Login:** set variable `GRAPH_HOST=graph.facebook.com` and secrets `IG_USER_ID` (Instagram business account id) and `IG_ACCESS_TOKEN` (a non-expiring Page or System User token). Token refresh is skipped in that mode.

## Troubleshooting

- **The run failed at "Publish".** Open the log. The error line shows Meta's message, for example an expired token or a missing permission.
- **"Already posted today".** The workflow won't post twice on the same date. That's intentional.
- **Instagram limits:** API publishing is capped at 100 posts per 24 hours. The script checks the remaining quota before posting.
