# Railway Deployment Guide

LaunchPad is deployed on Railway with PostgreSQL.

## Live Deployment

- **URL**: https://YOUR_APP.up.railway.app
- **Project**: `rail-linkedin-project`
- **Service**: `launchpad`
- **Database**: Railway PostgreSQL (referenced via `DATABASE_URL`)

## Architecture

The Dockerfile uses a 3-stage build:

1. **Frontend** (Node 20): `npm ci` + `npm run build` produces `frontend/dist/`
2. **Python deps** (Python 3.10): CPU-only PyTorch first, then `requirements.txt`
3. **Production** (Python 3.10 slim): Copies built frontend + Python packages, runs Gunicorn

Key settings:
- Single Gunicorn worker (memory-constrained)
- `PRODUCTION=true` serves React build at `/`
- `${PORT:-8000}` for Railway's dynamic port assignment
- Healthcheck at `/api/health` with 120s timeout

## Environment Variables

All secrets are configured as Railway env vars. The app's `src/config.py` checks env vars first (via `ENV_OVERRIDES` mapping), then falls back to `config.yaml`, then defaults.

### Currently Set

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection (auto-referenced from Postgres service) |
| `APIFY_API_KEY` | Apify LinkedIn scraper API key |
| `BRIGHTDATA_API_KEY` | Bright Data API key |
| `GEMINI_API_KEY` | Google Gemini AI API key |
| `GEMINI_ENABLED` | `true` |
| `MATCHING_ENGINE` | `auto` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_ALLOWED_USER_ID` | Authorized Telegram user ID |
| `TELEGRAM_ENABLED` | `true` |
| `SHEETS_ENABLED` | `false` (OAuth tokens not available on Railway) |
| `JOB_PROVIDER` | `auto` |
| `SCHEDULING_ENABLED` | `false` |
| `PRODUCTION` | `true` |

### Adding New Variables

```bash
railway variable set KEY=value --service launchpad
```

To add a new env var override, also add it to `ENV_OVERRIDES` in `src/config.py`.

## Common Operations

### Deploy

```bash
# From project root (linked to Railway)
railway up --service launchpad

# Or push to main — Railway auto-deploys if GitHub integration is connected
```

### View Logs

```bash
railway logs --service launchpad
```

### Check Status

```bash
railway service status --service launchpad
```

### Set Variables

```bash
railway variable set KEY=value --service launchpad
railway variable list --kv --service launchpad
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Healthcheck fails | Check runtime logs — likely a missing module or OOM. Increase `healthcheckTimeout` in `railway.json` |
| `ModuleNotFoundError` | Add missing package to `requirements.txt` and redeploy |
| OOM / container killed | Reduce workers (currently 1), check if PyTorch is CPU-only |
| Frontend not served | Ensure `PRODUCTION=true` is set and `frontend/dist/` exists in image |
| Google Sheets fails | OAuth tokens require local browser flow; disable with `SHEETS_ENABLED=false` |
| Build fails at frontend | Ensure `frontend/package-lock.json` is committed and not in `.dockerignore` |

## Data Migration (SQLite to PostgreSQL)

### Fresh start
Tables are created automatically on first startup via SQLAlchemy `create_all()`.

### Migrate existing data
```bash
export POSTGRES_URL="postgresql://..."  # From Railway Variables
python -m src.database.migrations.migrate_to_postgres
```

## Cost Estimate

| Component | Estimated Cost |
|-----------|----------------|
| Web Service | ~$5-7/month |
| PostgreSQL | ~$5/month |
| **Total** | **~$10-12/month** |

Railway provides $5 free monthly credit for hobby tier.
