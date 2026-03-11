# Security Guidelines

## Files That Must Never Be Committed

The following files are excluded via `.gitignore`. Do not commit them, ever:

| File | Contains |
|------|----------|
| `config.yaml` | API keys (Apify, Gemini, Telegram, Bright Data) |
| `.env` | Environment variable overrides |
| `credentials.json` | Google OAuth 2.0 client secret |
| `token.json` | Gmail OAuth access + refresh token |
| `sheets_token.json` | Google Sheets OAuth access + refresh token |
| `resume.txt` | Your personal resume (PII) |
| `*.db` / `*.sqlite` | Local database with job and match data |
| `dataset.json` | Scraped LinkedIn job data |
| `.claude/settings.local.json` | Claude Code settings (may contain allowed commands with secrets) |

Copy `config.yaml.example` → `config.yaml` and fill in your credentials locally.
Copy `docs/resume.example.txt` → `resume.txt` and replace with your actual resume.

---

## Pre-Publish Checklist

Before making this repository public or sharing it:

- [ ] `config.yaml` is not tracked (`git status` should not show it)
- [ ] `credentials.json`, `token.json`, `sheets_token.json` are not tracked
- [ ] `resume.txt` is not tracked
- [ ] No API keys appear in any tracked file (`git grep -i "apify_api\|sk-\|AIzaSy\|GOCSPX"`)
- [ ] `.env` is not tracked
- [ ] Local database files are not tracked

---

## If Credentials Are Compromised

If any credential file is accidentally committed or exposed:

1. **Revoke immediately** — do not wait:
   - **Apify API key**: [apify.com/account/integrations](https://console.apify.com/account/integrations)
   - **Bright Data key**: [brightdata.com/cp/api_access](https://brightdata.com/cp/api_access)
   - **Gemini API key**: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - **Telegram bot token**: Send `/revoke` to [@BotFather](https://t.me/BotFather)
   - **Google OAuth secret**: Delete and recreate in [Google Cloud Console](https://console.cloud.google.com/)
   - **Railway PostgreSQL**: Rotate credentials in Railway dashboard

2. **Purge from git history**:
   ```bash
   pip install git-filter-repo
   git-filter-repo --path <compromised-file> --invert-paths --force
   git push origin main --force
   ```

3. **Generate new credentials** and update Railway env vars:
   ```bash
   railway variable set KEY=new_value --service launchpad
   ```

---

## Reporting a Vulnerability

If you discover a security issue in this project, please open a GitHub issue or contact the maintainer directly. Do not disclose sensitive bugs publicly before they are addressed.
