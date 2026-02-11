# Railway Deployment Guide

## Prerequisites

- A [Railway](https://railway.app) account
- GitHub repository connected to Railway
- All API keys and tokens ready (see Environment Variables below)

## 1. Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project** > **Deploy from GitHub Repo**
3. Select your LaunchPad repository
4. Railway will detect the `Dockerfile` and begin building automatically

## 2. Add PostgreSQL Database

1. In your Railway project, click **New** > **Database** > **PostgreSQL**
2. Railway auto-provisions the database and sets `DATABASE_URL` in the linked service
3. Connect the database to your app service:
   - Click your app service > **Variables** > **Reference Variables**
   - Add `DATABASE_URL` referencing the Postgres service's `DATABASE_URL`

The app will use this instead of the default SQLite path.

## 3. Environment Variables

Set these in your Railway service under **Variables**. All secrets should be configured here instead of config.yaml.

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (auto-set if you reference the Postgres service) |
| `APIFY_API_KEY` | Apify API key for LinkedIn job scraping |

### Telegram Bot

| Variable | Description |
|----------|-------------|
| `TELEGRAM_ENABLED` | `true` to enable the Telegram bot |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | Your Telegram user ID (for authorization) |

### Google Gemini AI

| Variable | Description |
|----------|-------------|
| `GEMINI_ENABLED` | `true` to enable Gemini AI matching |
| `GEMINI_API_KEY` | Google Gemini API key |
| `MATCHING_ENGINE` | `gemini`, `nlp`, or `auto` (default: `auto`) |

### Google Sheets Export

| Variable | Description |
|----------|-------------|
| `SHEETS_ENABLED` | `true` to enable Sheets export |
| `SHEETS_SPREADSHEET_ID` | Target Google Sheets spreadsheet ID |
| `SHEETS_CREDENTIALS_PATH` | Path to OAuth credentials file (see OAuth section) |
| `SHEETS_TOKEN_PATH` | Path to OAuth token file |

### Email Notifications

| Variable | Description |
|----------|-------------|
| `EMAIL_ENABLED` | `true` to enable email notifications |
| `EMAIL_FROM_ADDRESS` | Sender email address |
| `EMAIL_TO_ADDRESS` | Recipient email address |
| `EMAIL_CREDENTIALS_PATH` | Path to Gmail OAuth credentials |
| `EMAIL_TOKEN_PATH` | Path to Gmail OAuth token |

### Scheduling

| Variable | Description |
|----------|-------------|
| `SCHEDULING_ENABLED` | `true` to enable automatic scheduled searches |

### Other

| Variable | Description |
|----------|-------------|
| `JOB_PROVIDER` | `apify` (default) or `brightdata` |
| `BRIGHTDATA_API_KEY` | Bright Data API key (if using brightdata provider) |

## 4. Google OAuth Tokens (Sheets & Gmail)

Google Sheets and Gmail use OAuth tokens that require an initial interactive browser flow. Since Railway has no browser, generate these locally first:

1. **Run the app locally** with `SHEETS_ENABLED=true` / `EMAIL_ENABLED=true`
2. Complete the OAuth consent flow in your browser
3. This creates `token.json` (and/or `email_token.json`) locally
4. **Upload the token file to Railway:**
   - Option A: Store the token JSON as a Railway env var (e.g. `SHEETS_TOKEN_JSON`) and modify the app to write it to a file on startup
   - Option B: Use a Railway volume mount to persist the token file
   - Option C: Store in the database (requires code changes)

The simplest approach is Option B — add a Railway volume at `/app/secrets/` and upload your token files there.

## 5. Volume Mounts (Optional)

If you need persistent file storage (e.g., for OAuth tokens, uploaded resumes):

1. In Railway, click your service > **Settings** > **Volumes**
2. Add a volume mounted at `/app/data/persistent/`
3. Update token paths in env vars to point to this mount

## 6. Deployment

### Automatic Deploys

Railway deploys automatically on every push to the connected branch. The multi-stage Dockerfile:
1. Builds the React frontend with Node.js
2. Installs Python dependencies
3. Copies everything into a slim production image
4. Starts Gunicorn with Uvicorn workers

### Manual Deploy

From Railway dashboard: click **Deploy** > **Deploy Now** to trigger a build from the latest commit.

### Health Check

The app exposes `/api/health` which Railway monitors automatically (configured in `railway.json`). If the health check fails 3 times, Railway restarts the service.

## 7. Custom Domain

1. Go to your service > **Settings** > **Networking**
2. Click **Generate Domain** for a `*.up.railway.app` subdomain
3. Or add a custom domain and update your DNS records

## 8. Monitoring & Logs

- **Logs**: Click your service > **Deployments** > select a deployment > **View Logs**
- **Metrics**: Railway provides CPU, memory, and network metrics on the service dashboard
- **Alerts**: Configure deploy notifications in project settings

## 9. Telegram Bot Considerations

The Telegram bot uses long-polling (`run_polling()`), which runs indefinitely alongside the web server. The current architecture starts both in the same process. For Railway:

- This works in a single service — the bot runs in a background thread while Gunicorn serves HTTP
- If you need to scale the web server independently, consider splitting into two Railway services:
  - **Web service**: Gunicorn serving the API + frontend
  - **Worker service**: Telegram bot only (use a different start command)

## Troubleshooting

### Build fails at frontend stage
- Ensure `frontend/package-lock.json` is committed (required for `npm ci`)
- Check Node.js compatibility — the Dockerfile uses Node 20

### App crashes on startup
- Check that `DATABASE_URL` is set and the Postgres service is running
- Look at deploy logs for missing env vars or import errors

### Health check fails
- The health endpoint is `/api/health` — verify it responds locally first
- Railway's `PORT` env var is set automatically; the app binds to `${PORT:-8000}`

### Database migrations
- The app uses SQLAlchemy with `create_all()` — tables are created automatically on first run
- For schema changes, you may need to drop and recreate tables, or add Alembic migrations

### OAuth token expired
- Google OAuth tokens expire periodically
- Re-run the OAuth flow locally, then re-upload the refreshed token file
