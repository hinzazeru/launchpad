# Job Scheduler Documentation

This guide explains how to set up and use the automated job scheduler for the LinkedIn Job Matcher. The scheduler runs automatically within a configurable time window, with results sent via Telegram notifications and exported to Google Sheets.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Configuration](#configuration)
4. [Keyword Profiles](#keyword-profiles)
5. [Telegram Bot Commands](#telegram-bot-commands)
6. [How It Works](#how-it-works)
7. [Monitoring and Logs](#monitoring-and-logs)
8. [Troubleshooting](#troubleshooting)
9. [Technical Details](#technical-details)

## Overview

The job scheduler automates the job search process:

- **Scheduled Searches**: Run searches automatically at configured intervals within a time window
- **Keyword Profiles**: Switch between different search keywords (e.g., "Product Manager", "Senior PM Remote")
- **Single API Call**: Each scheduled run uses one API call to minimize costs
- **Automatic Matching**: Match jobs against your resume
- **Telegram Notifications**: Get push notifications for new high-quality matches
- **Google Sheets Export**: Track all matches in a spreadsheet
- **Mute Control**: Pause notifications without stopping the scheduler

## Prerequisites

Before using the scheduler, ensure you have:

1. **Active Resume**: At least one resume created in the database
2. **Apify API Key**: Configured in `config.yaml`
3. **Telegram Bot**: Configured with bot token and user ID
4. **Google Sheets** (optional): Sheets integration configured for exports

## Configuration

### Basic Configuration

Open `config.yaml` and update the `scheduling` section:

```yaml
scheduling:
  enabled: true           # Enable the scheduler
  interval_hours: 4       # Run every 4 hours
  start_time: "08:00"     # Start of daily window
  end_time: "22:00"       # End of daily window
  active_profile: senior_pm  # Active keyword profile
  muted: false            # Notification mute status

  # Keyword profiles (single keyword per profile to minimize API costs)
  profiles:
    pm:
      keyword: Product Manager
    senior_pm:
      keyword: Senior Product Manager
    senior_pm_remote:
      keyword: Senior Product Manager Remote
    pm_remote:
      keyword: Product Manager Remote

  # Optional overrides (null = use defaults from search section)
  search_location: null
  max_results: null
  notify_on_new_matches: true
  only_notify_new: true
```

### Time Window Scheduling

The scheduler runs at specific hours within your configured time window:

| Config | Example | Scheduled Times |
|--------|---------|-----------------|
| `interval_hours: 4`, `start_time: 08:00`, `end_time: 22:00` | Every 4 hours | 08:00, 12:00, 16:00, 20:00 |
| `interval_hours: 6`, `start_time: 09:00`, `end_time: 21:00` | Every 6 hours | 09:00, 15:00, 21:00 |
| `interval_hours: 8`, `start_time: 08:00`, `end_time: 22:00` | Every 8 hours | 08:00, 16:00 |

## Keyword Profiles

Profiles allow you to switch between different search keywords without editing config files.

### Why Single Keyword Per Profile?

Each API call costs money. To minimize costs:
- **Old approach**: Multiple keywords = multiple API calls per run
- **New approach**: Single keyword per profile = 1 API call per run

With 4 runs per day at `interval_hours: 4`, you use only 4 API calls daily.

### Managing Profiles via Telegram

Use the `/profiles` command:

```
/profiles                    - List all profiles
/profiles pm                 - Switch to 'pm' profile
/profiles create tech_pm Technical Product Manager
                             - Create new profile
/profiles delete tech_pm     - Delete a profile
```

### Remote Job Searches

Profiles ending with "Remote" trigger special handling:
- Location automatically set to "North America"
- Work arrangement filter set to "Remote"
- The "Remote" suffix is stripped from the actual search keyword

Example: `Senior Product Manager Remote` searches for "Senior Product Manager" with remote filter.

## Telegram Bot Commands

The primary way to manage the scheduler is via Telegram:

| Command | Description |
|---------|-------------|
| `/status` | Show scheduler status, next run time, active profile |
| `/search` | Run an immediate job search |
| `/search [keyword]` | Search with custom keyword |
| `/matches` | Show recent top matches |
| `/profiles` | List keyword profiles |
| `/profiles <name>` | Switch to profile |
| `/profiles create <name> <keyword>` | Create new profile |
| `/profiles delete <name>` | Delete a profile |
| `/mute` | Toggle notification mute on/off |
| `/schedule` | View scheduled times |
| `/config` | Show current configuration |
| `/cleanup` | Clean old entries from Google Sheets (7 days) |

### Mute Functionality

Use `/mute` to pause push notifications:
- Scheduler continues running on schedule
- Jobs are still fetched, matched, and exported to Sheets
- No push notifications are sent
- Use `/mute` again to unmute

Useful when you don't want to be disturbed but want searches to continue.

## How It Works

### Job Search Cycle

When the scheduler runs (either on schedule or via `/search`):

1. **Gets Resume**: Queries database for most recent resume
2. **Fetches Jobs**: Calls Apify LinkedIn Jobs Scraper (1 API call)
3. **Imports to Database**: Stores new jobs, deduplicates existing ones
4. **Matches Jobs**: Runs matching algorithm against resume
5. **Saves Results**: Stores match results in database
6. **Exports to Sheets**: Batch exports matches to Google Sheets
7. **Sends Notifications**: Pushes Telegram notification for new matches (if not muted)

### Example Timeline

With `interval_hours: 4`, `start_time: 08:00`, `end_time: 22:00`:

```
08:00 - Search runs (Senior Product Manager)
12:00 - Search runs
16:00 - Search runs
20:00 - Search runs
22:00 - End of window (no more runs until 08:00 next day)
```

## Monitoring and Logs

### Check Status

Use `/status` in Telegram to see:
- Scheduler enabled/running status
- Active profile and keyword
- Mute status
- Next scheduled run time
- Run statistics (total, successful, failed)

### Log Files

Logs are written to `bot_output.log`:

```bash
tail -f bot_output.log
```

**Key log entries to look for**:
```
Scheduling job searches at hours: [8, 12, 16, 20]
Next scheduled run: 2025-12-09 20:00:00-05:00
Starting scheduled job search at 2025-12-09 16:00:00
Job linkedin_job_search executed successfully
```

## Troubleshooting

### Scheduled Job Didn't Run

**Symptoms**: No job search at expected time, no logs

**Possible Causes**:
1. Bot process not running
2. Scheduler not properly started
3. Wrong scheduler type (fixed in recent update)

**Solutions**:
1. Check if bot is running: `ps aux | grep run_telegram_bot`
2. Check logs for scheduler startup: `grep "Scheduler started" bot_output.log`
3. Restart the bot:
   ```bash
   pkill -9 -f "run_telegram_bot"
   nohup python run_telegram_bot.py > bot_output.log 2>&1 &
   ```

### No Notifications Received

**Check**:
1. Mute status: `/status` shows if muted
2. Match scores: Notifications only sent for matches >= 70%
3. Only new matches: Already-notified matches won't re-notify

**Solutions**:
- Unmute: `/mute`
- Lower threshold in config: `email.notify_min_score: 0.6`

### No Matches Found

**Possible Causes**:
1. Resume incomplete or missing skills
2. Keyword too specific
3. No new jobs posted in last 24 hours

**Solutions**:
- Try broader keywords
- Check resume has relevant skills listed
- Lower `matching.min_match_score` in config

### Bot Stops Unexpectedly

**Solutions**:
1. Run with `nohup` to survive terminal close:
   ```bash
   nohup python run_telegram_bot.py > bot_output.log 2>&1 &
   ```
2. Use a process manager (systemd, supervisor)
3. Check logs for errors

## Technical Details

### Telegram JobQueue with Timezone Support

The scheduler uses python-telegram-bot's built-in `JobQueue` for proper integration with the async event loop. This replaced standalone APScheduler which had event loop conflicts.

**Key implementation details:**
- Uses `Defaults(tzinfo=ZoneInfo("America/Toronto"))` when building the Application
- All scheduled times are interpreted in EST/EDT timezone
- Jobs are scheduled using `job_queue.run_daily()` with timezone-naive time objects
- The Application's Defaults automatically apply the correct timezone

**Why this approach:**
- python-telegram-bot's `run_polling()` manages its own event loop
- Standalone APScheduler (BackgroundScheduler/AsyncIOScheduler) had conflicts with this event loop
- The built-in JobQueue is fully integrated and reliable

### Database Schema

Match results are stored with:
- `match_score`: Overall match percentage
- `notified_at`: Timestamp when notification was sent (for only_notify_new feature)
- Links to job posting and resume

### API Cost Optimization

Each Apify API call costs money. The profile system ensures:
- 1 keyword per profile = 1 API call per search
- With `interval_hours: 4` and 4 runs/day = 4 API calls/day
- Compare to old multi-keyword approach which could use 12+ calls/day

## Starting the Scheduler

### Quick Start

```bash
cd LinkedInJobSearch
nohup venv/bin/python run_telegram_bot.py > bot_output.log 2>&1 &
```

### Verify It's Running

```bash
# Check process
ps aux | grep run_telegram_bot

# Check logs
tail -20 bot_output.log

# Send /status via Telegram
```

### Stop the Scheduler

```bash
pkill -9 -f "run_telegram_bot"
```

## Related Documentation

- [Telegram Bot Setup Guide](TELEGRAM_BOT.md)
- [Google Sheets Setup Guide](SHEETS_SETUP.md)
- [Email Setup Guide](EMAIL_SETUP.md)
