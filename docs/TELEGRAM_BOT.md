# Telegram Bot Setup & Deployment Guide

Control your LinkedIn Job Matcher from anywhere using Telegram! This guide covers everything from creating your bot to deploying it on free cloud services.

## Table of Contents

1. [Overview](#overview)
2. [Creating Your Telegram Bot](#creating-your-telegram-bot)
3. [Local Setup & Testing](#local-setup--testing)
4. [Using the Bot](#using-the-bot)
5. [Cloud Deployment](#cloud-deployment)
6. [Troubleshooting](#troubleshooting)

## Overview

The Telegram bot allows you to:
- ✅ Run job searches remotely from your phone
- ✅ Check scheduler status and next run time
- ✅ View recent top matches
- ✅ Switch between keyword profiles
- ✅ Mute/unmute notifications
- ✅ Monitor your job search from anywhere

**Available Commands:**
- `/start` - Welcome message and help
- `/help` - Show all commands
- `/search` - Run immediate job search
- `/search [keyword]` - Search with custom keyword
- `/status` - Check scheduler status, active profile, mute status
- `/matches` - View top 5 recent matches
- `/profiles` - Manage keyword profiles (list, switch, add, delete)
- `/mute` - Toggle notification mute on/off
- `/schedule` - View scheduled run times
- `/cleanup` - Clean old entries from Google Sheets (removes entries older than 7 days)
- `/config` - Show current configuration

## Creating Your Telegram Bot

### Step 1: Talk to @BotFather

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Choose a name for your bot (e.g., "My Job Matcher")
4. Choose a username (must end in 'bot', e.g., "myjobmatcher_bot")
5. Bot

Father will send you a **bot token** - save this!

**Example:**
```
Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Step 2: Get Your Telegram User ID

1. Search for `@userinfobot` on Telegram
2. Start a chat and send any message
3. The bot will reply with your user ID
4. Save this number (e.g., `123456789`)

**Why?** This ensures only YOU can control your bot!

### Step 3: Configure the Bot

Open `config.yaml` and update the telegram section:

```yaml
# Telegram Bot Configuration
telegram:
  enabled: true  # Enable the bot
  bot_token: "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"  # Your token from BotFather
  allowed_user_id: "123456789"  # Your user ID from @userinfobot
```

## Local Setup & Testing

### Test the Bot Locally

Before deploying to the cloud, test it on your computer:

```bash
python run_telegram_bot.py
```

**Expected output:**
```
================================================================================
LinkedIn Job Matcher - Telegram Bot
================================================================================

✓ Configuration validated

================================================================================
Bot is starting...
Open Telegram and send /start to your bot to begin!

Available commands:
  /start - Welcome message
  /help - Show all commands
  /search - Run immediate job search
  /status - Check scheduler status
  /matches - View recent top matches
  /config - Show current configuration

Press Ctrl+C to stop the bot
================================================================================
```

### Test Commands

1. Open Telegram
2. Search for your bot by username (e.g., `@myjobmatcher_bot`)
3. Send `/start`
4. Try other commands like `/status` or `/matches`

**Tip:** The bot responds instantly to status/matches but `/search` takes a few minutes.

## Using the Bot

### Run a Job Search

```
You: /search
Bot: 🔍 Starting job search...
     This may take a few minutes. I'll notify you when it's done!

[Few minutes later]

Bot: ✅ Job search completed!

     Found 3 matches:

     1. Senior Product Manager
        📍 TechCorp
        ⭐ Score: 92%

     2. Product Manager - SaaS
        📍 CloudSolutions Ltd
        ⭐ Score: 85%

     3. Technical Product Manager
        📍 StartupXYZ
        ⭐ Score: 78%

     📧 Check your email for full details
     📊 View all matches in Google Sheets
```

### Check Status

```
You: /status
Bot: 📊 Scheduler Status

     ✅ Scheduler: Running
     🔔 Notifications: Active

     Configuration:
     • Profile: senior_pm
     • Keyword: Senior Product Manager
     • Schedule: 08:00, 12:00, 16:00, 20:00
     • Location: Canada

     ⏰ Next run: 2025-12-09 20:00:00

     Statistics:
     Total runs: 15
     Successful: 15
     Failed: 0
```

### Manage Profiles

```
You: /profiles
Bot: 📋 Keyword Profiles

     ✅ senior_pm: Senior Product Manager
        pm: Product Manager
        senior_pm_remote: Senior Product Manager Remote
        pm_remote: Product Manager Remote

     Active: senior_pm
     1 keyword = 1 API call per search

     /profiles <name> to switch
```

**Profile Commands:**
- `/profiles` - List all profiles
- `/profiles <name>` - Switch to profile (e.g., `/profiles pm`)
- `/profiles create <name> <keyword>` - Create new profile
- `/profiles delete <name>` - Delete a profile

### Mute Notifications

```
You: /mute
Bot: 🔇 Notifications muted

     Scheduled searches will continue running.
     Jobs will be matched and exported to Sheets.
     No push notifications will be sent.

     Use /mute again to unmute.
```

### View Recent Matches

```
You: /matches
Bot: ⭐ Top 5 Matches (Last 7 Days)

     🔥 Senior Product Manager - AI/ML
     📍 TechCorp Inc.
     📊 Overall: 92% | Skills: 95% | Exp: 88%
     📅 Nov 28, 2025

     ✨ Product Manager - SaaS Platform
     📍 CloudSolutions Ltd
     📊 Overall: 85% | Skills: 82% | Exp: 88%
     📅 Nov 27, 2025

     💡 Check your email or Google Sheets for full details!
```

## Cloud Deployment

Deploy your bot to run 24/7 for free! Choose one of these platforms:

### Option 1: Railway (Recommended - Easiest)

**Why Railway:** Simple setup, generous free tier, great for beginners.

#### Setup Steps:

1. **Create Railway Account**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Prepare Your Code**
   ```bash
   # Create a Procfile
   echo "worker: python run_telegram_bot.py" > Procfile

   # Create runtime.txt
   echo "python-3.10" > runtime.txt

   # Ensure requirements.txt includes telegram
   pip freeze > requirements.txt
   ```

3. **Create .railwayignore** (exclude files):
   ```
   venv/
   __pycache__/
   *.pyc
   *.db
   *.log
   .env
   credentials.json
   token.json
   sheets_token.json
   ```

4. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   gh repo create linkedin-job-matcher --private
   git push origin main
   ```

5. **Deploy on Railway**
   - Click "New Project" on Railway
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway will auto-detect and deploy!

6. **Set Environment Variables**
   - In Railway dashboard, go to Variables
   - Add these (Railway supports config files, but env vars are more secure):
     - `TELEGRAM_BOT_TOKEN`: Your bot token
     - `TELEGRAM_USER_ID`: Your user ID
     - `APIFY_API_KEY`: Your Apify key

   - Update code to read from environment variables if needed

7. **Start the Worker**
   - Railway auto-starts the Procfile worker
   - Check logs to confirm bot is running

**Cost:** $5 credit free, then $5/month (includes 500 hours - enough for 24/7)

---

### Option 2: Render

**Why Render:** Generous free tier, similar to Railway.

#### Setup Steps:

1. **Create Render Account**
   - Go to [render.com](https://render.com)
   - Sign up with GitHub

2. **Create render.yaml**:
   ```yaml
   services:
     - type: worker
       name: telegram-bot
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: python run_telegram_bot.py
       envVars:
         - key: TELEGRAM_BOT_TOKEN
           sync: false
         - key: TELEGRAM_USER_ID
           sync: false
         - key: APIFY_API_KEY
           sync: false
   ```

3. **Deploy**
   - Push code to GitHub
   - In Render dashboard, click "New +"
   - Select "Blueprint"
   - Connect your GitHub repo
   - Render reads render.yaml and deploys

4. **Set Environment Variables**
   - In Render dashboard, go to Environment
   - Add your bot token, user ID, and Apify key

**Cost:** Free tier includes 750 hours/month (enough for 24/7)

---

### Option 3: Fly.io

**Why Fly.io:** More control, good free tier.

#### Setup Steps:

1. **Install Fly CLI**
   ```bash
   # Mac
   brew install flyctl

   # Linux
   curl -L https://fly.io/install.sh | sh

   # Windows
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Login and Initialize**
   ```bash
   flyctl auth login
   flyctl launch
   ```

3. **Configure fly.toml** (auto-generated, but verify):
   ```toml
   app = "linkedin-job-matcher"

   [build]
     builder = "paketobuildpacks/builder:base"

   [[services]]
     internal_port = 8080
     protocol = "tcp"

   [env]
     PORT = "8080"
   ```

4. **Set Secrets**
   ```bash
   flyctl secrets set TELEGRAM_BOT_TOKEN="your_token"
   flyctl secrets set TELEGRAM_USER_ID="your_id"
   flyctl secrets set APIFY_API_KEY="your_key"
   ```

5. **Deploy**
   ```bash
   flyctl deploy
   ```

6. **Monitor**
   ```bash
   flyctl logs
   ```

**Cost:** Free tier includes 3 shared CPUs (enough for the bot)

---

## File Structure for Deployment

Ensure your project has these files for cloud deployment:

```
linkedin-job-matcher/
├── src/
│   └── bot/
│       └── telegram_bot.py
├── config.yaml              # Config file (exclude secrets!)
├── run_telegram_bot.py      # Main bot script
├── requirements.txt         # Python dependencies
├── Procfile                 # For Railway/Heroku
├── runtime.txt              # Python version
├── render.yaml              # For Render
├── fly.toml                 # For Fly.io
└── .gitignore               # Exclude secrets
```

### Important Files:

**requirements.txt:**
```
python-telegram-bot==22.5
SQLAlchemy==2.0.23
PyYAML==6.0.1
apify-client==1.5.0
google-api-python-client==2.108.0
google-auth==2.25.2
google-auth-oauthlib==1.2.0
APScheduler==3.10.4
```

**Procfile:**
```
worker: python run_telegram_bot.py
```

**runtime.txt:**
```
python-3.10
```

**.gitignore:**
```
venv/
*.pyc
__pycache__/
*.db
*.log
config.yaml
credentials.json
token.json
sheets_token.json
.env
```

## Environment Variables (Cloud)

For security, use environment variables in production instead of config.yaml:

**Modify `src/config.py`** to read from environment:
```python
import os

# Telegram config
config["telegram.bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", config.get("telegram.bot_token"))
config["telegram.allowed_user_id"] = os.getenv("TELEGRAM_USER_ID", config.get("telegram.allowed_user_id"))
config["apify.api_key"] = os.getenv("APIFY_API_KEY", config.get("apify.api_key"))
```

Then set these in your cloud platform:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_USER_ID`
- `APIFY_API_KEY`

## Troubleshooting

### Bot Doesn't Respond

**Issue:** Send messages but bot doesn't reply

**Solutions:**
1. Check bot is running: `flyctl logs` or Railway logs
2. Verify bot token is correct
3. Ensure you're messaging the right bot
4. Check user_id matches (try removing it temporarily)

---

### "Not Authorized" Error

**Issue:** Bot says "You are not authorized"

**Solution:**
1. Get your user ID from @userinfobot again
2. Update `allowed_user_id` in config
3. Restart the bot

---

### Search Takes Too Long / Times Out

**Issue:** `/search` command times out

**Solutions:**
1. This is normal for large searches (can take 2-5 minutes)
2. Reduce `max_results` in config
3. Limit `search_keywords` to 1-2 keywords
4. Check Apify API limits

---

### Bot Stops After a While

**Issue:** Bot works initially but stops responding

**Solutions:**
1. **Railway/Render:** Check if worker is still running
2. **Free tier limitations:** Some platforms sleep apps after inactivity
3. **Solution:** Use a cron job to ping the bot or upgrade to paid tier

---

### Database/File Issues in Cloud

**Issue:** Can't find database or files

**Solutions:**
1. **SQLite:** Won't persist on free tiers (use PostgreSQL instead)
2. **Files:** Use cloud storage (S3, Google Cloud Storage)
3. **Quick fix:** Use in-memory database for testing

---

### Credentials Not Found

**Issue:** "credentials.json not found" in cloud

**Solutions:**
1. Upload credentials as environment variable (base64 encoded)
2. Use Secrets/Environment Variables for OAuth tokens
3. Store in cloud secret managers (Railway secrets, etc.)

## Best Practices

### Security

1. ✅ **Never commit secrets** - Use .gitignore
2. ✅ **Use environment variables** for production
3. ✅ **Set allowed_user_id** - Don't let anyone control your bot
4. ✅ **Rotate tokens** if exposed

### Monitoring

1. ✅ Check logs regularly (daily at first)
2. ✅ Set up alerts if bot goes down (Render/Railway offer this)
3. ✅ Monitor API usage (Apify dashboard)

### Cost Management

1. ✅ Start with free tiers
2. ✅ Monitor usage to avoid surprise bills
3. ✅ Set up billing alerts
4. ✅ Limit `max_results` and search frequency

## Next Steps

1. ✅ Create your bot with @BotFather
2. ✅ Test locally with `python run_telegram_bot.py`
3. ✅ Choose a cloud platform (Railway recommended for beginners)
4. ✅ Deploy and test
5. ✅ Start controlling your job search remotely!

For questions or issues, check the main project README or create an issue on GitHub.

Happy job hunting! 🚀
