# Railway Deployment Guide

Deploy the LinkedIn Job Matcher to Railway with PostgreSQL for reliable scheduled job searches.

## Progress Status

### Completed ✅
- [x] GitHub repository created and code pushed
- [x] Repository structure fixed (files at root level)
- [x] Dockerfile created (multi-stage Python 3.10 build)
- [x] railway.json configuration (health checks, restart policy)
- [x] Procfile updated (Gunicorn + Uvicorn workers)
- [x] .dockerignore created
- [x] PostgreSQL migration script ready
- [x] Local PostgreSQL tested with data migration

### Pending ⏳
- [ ] Create Railway project
- [ ] Add PostgreSQL database on Railway
- [ ] Configure environment variables
- [ ] Deploy and verify

---

## Prerequisites

- GitHub repo: `empyre-github/linkedin-job-matcher` ✅
- Railway account: [https://railway.app](https://railway.app)

---

## Quick Deploy (When Ready)

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

## Configuration Files (Already Created)

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build with Python 3.10, PostgreSQL deps |
| `railway.json` | Health checks at `/api/health`, restart policy |
| `Procfile` | Gunicorn + Uvicorn workers |
| `.dockerignore` | Excludes 80+ unnecessary files from build |

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
