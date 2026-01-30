# Railway Deployment Guide

Deploy the LinkedIn Job Matcher to Railway with PostgreSQL for reliable scheduled job searches.

## Prerequisites

- GitHub repo: `empyre-github/linkedin-job-matcher`
- Railway account: [https://railway.app](https://railway.app)

---

## Quick Deploy (5 minutes)

### 1. Create Project
1. Go to [Railway Dashboard](https://railway.app/dashboard) → **"New Project"**
2. **"Deploy from GitHub repo"** → Select `linkedin-job-matcher`
3. Railway auto-detects the `Dockerfile` and builds

### 2. Add PostgreSQL
1. In project → **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Click PostgreSQL → **"Variables"** tab → **"Add Reference"**
3. Add `DATABASE_URL` to your web service

### 3. Set Environment Variables
In web service → **"Variables"**:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Auto-linked from PostgreSQL |
| `PYTHONPATH` | ✅ | Set to `/app` |
| `GEMINI_API_KEY` | ✅ | Google AI API key |
| `APIFY_API_KEY` | ✅ | Apify scraping key |
| `TELEGRAM_BOT_TOKEN` | Optional | For notifications |
| `TELEGRAM_CHAT_ID` | Optional | For notifications |

### 4. Generate Domain
1. Service → **"Settings"** → **"Networking"**
2. Click **"Generate Domain"**
3. Your app is live at `https://xxx.railway.app`

---

## Configuration Files

This repo includes Railway-optimized configuration:

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build with Python 3.10, PostgreSQL deps |
| `railway.json` | Health checks, restart policy, deploy settings |
| `Procfile` | Gunicorn + Uvicorn workers |
| `.dockerignore` | Excludes dev files from build |

---

## Health Check

Railway monitors `/api/health` every 30 seconds. The endpoint returns:

```json
{
  "status": "healthy",
  "database": true,
  "scheduler": "running"
}
```

---

## Data Migration (Optional)

### Migrate from local SQLite:
```bash
# Get DATABASE_URL from Railway (Settings → Variables)
export POSTGRES_URL="postgresql://postgres:xxx@xxx.railway.app:5432/railway"

# Run migration
python -m src.database.migrations.migrate_to_postgres
```

### Fresh start:
Skip migration — tables are created automatically on first startup.

---

## Verify Deployment

1. Visit `https://your-app.railway.app/api/health`
2. Check Railway **"Logs"** tab for startup messages
3. Test the scheduler: **Get Jobs** → **Scheduled** tab

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Add `PYTHONPATH=/app` to env vars |
| Database connection failed | Verify `DATABASE_URL` is set in web service |
| Build fails | Check Railway build logs for missing deps |
| Scheduler not starting | Check startup logs for scheduler init errors |

---

## Cost Estimate

| Component | Estimated Cost |
|-----------|----------------|
| Web Service | ~$5-7/month |
| PostgreSQL | ~$5/month |
| **Total** | **~$10-12/month** |

Railway provides $5 free monthly credit for hobby tier.
