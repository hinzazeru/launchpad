# Scheduler Module

Job scheduling and orchestration for automated LinkedIn job searches.

## Overview

This module manages automated job searches, including scheduling, profile management, and coordination between the Apify API, matching engine, and notification systems.

## Files

| File | Purpose |
|------|---------|
| `job_scheduler.py` | Main scheduler logic, profile management, search orchestration |

## Architecture

```
JobScheduler
├── Configuration
│   ├── enabled: bool
│   ├── interval_hours: int
│   ├── start_time / end_time: str
│   ├── active_profile: str
│   └── muted: bool
│
├── Profile Management
│   ├── get_profiles()
│   ├── set_active_profile()
│   ├── create_profile()
│   └── delete_profile()
│
├── Schedule Management
│   ├── get_status()
│   ├── get_scheduled_times()
│   └── update_schedule()
│
├── Search Execution
│   ├── run_now()              # Manual trigger
│   └── run_scheduled_search() # Scheduled trigger
│
└── Notifications
    ├── toggle_mute()
    └── set_telegram_callback()
```

## Important: Scheduling Implementation

**We use Telegram's JobQueue, NOT standalone APScheduler.**

The scheduling is implemented in `telegram_bot.py` using:

```python
from telegram.ext import Application, Defaults
from zoneinfo import ZoneInfo

# Timezone set via Application Defaults
defaults = Defaults(tzinfo=ZoneInfo("America/Toronto"))
application = Application.builder().token(token).defaults(defaults).build()

# Jobs scheduled via JobQueue
job_queue.run_daily(callback, time=time(hour=8, minute=0))
```

**Why not APScheduler?**
- `python-telegram-bot`'s `run_polling()` manages its own event loop
- Standalone APScheduler (BackgroundScheduler/AsyncIOScheduler) conflicts with this
- The built-in JobQueue is fully integrated and reliable

## Profile System

Each profile has a single keyword to minimize API costs:

```yaml
profiles:
  pm:
    keyword: Product Manager
  senior_pm:
    keyword: Senior Product Manager
  senior_pm_remote:
    keyword: Senior Product Manager Remote
```

**Cost optimization**: 1 keyword = 1 API call per search. With 4 runs/day, that's only 4 API calls.

### Remote Job Handling

Keywords ending with "Remote" trigger special handling:
- Location set to "North America"
- Work arrangement filter set to "Remote"
- "Remote" suffix stripped from actual search term

## Usage

### Get Current Status

```python
from src.scheduler.job_scheduler import JobScheduler

scheduler = JobScheduler()
status = scheduler.get_status()

print(status['enabled'])        # True/False
print(status['active_profile']) # "senior_pm"
print(status['muted'])          # True/False
print(status['next_run'])       # "2025-12-10 08:00:00"
print(status['stats'])          # {"total_runs": 10, "successful_runs": 10, ...}
```

### Run Manual Search

```python
# Use active profile keyword
scheduler.run_now()

# Use custom keyword (one-time override)
scheduler.run_now(custom_keywords="Technical Product Manager")
```

### Manage Profiles

```python
# List profiles
profiles = scheduler.get_profiles()

# Switch profile
scheduler.set_active_profile("pm")

# Create profile
scheduler.create_profile("tech_pm", "Technical Product Manager")

# Delete profile
scheduler.delete_profile("tech_pm")
```

### Toggle Mute

```python
result = scheduler.toggle_mute()
print(result['muted'])  # True/False
```

## Configuration

In `config.yaml`:

```yaml
scheduling:
  enabled: true
  interval_hours: 4
  start_time: "08:00"
  end_time: "22:00"
  active_profile: senior_pm
  muted: false

  profiles:
    pm:
      keyword: Product Manager
    senior_pm:
      keyword: Senior Product Manager

  notify_on_new_matches: true
  only_notify_new: true

matching:
  max_job_age_days: 7  # Only match jobs posted within this many days (0 = disabled)

search:
  default_location: Canada  # Location filter for regular searches
```

## Scheduled Times Calculation

Based on `interval_hours`, `start_time`, and `end_time`:

| Config | Scheduled Times |
|--------|-----------------|
| interval: 4, start: 08:00, end: 22:00 | 08:00, 12:00, 16:00, 20:00 |
| interval: 6, start: 09:00, end: 21:00 | 09:00, 15:00, 21:00 |
| interval: 8, start: 08:00, end: 22:00 | 08:00, 16:00 |

## Search Pipeline

When a search runs (manual or scheduled), the pipeline executes in 6 stages:

1. **Stage 1 - Resume Fetch** (Critical): Load most recent resume from database
2. **Stage 2 - Apify Job Fetch** (Critical): Call LinkedIn Jobs Scraper API (1 call)
3. **Stage 3 - Database Import**: Validate, deduplicate, store new jobs
4. **Stage 4 - Job Matching**: Filter and match jobs against resume
   - Filter by keyword (job title contains search term)
   - Filter by location (e.g., "Canada") - skipped for remote searches
   - Filter by freshness (`max_job_age_days`, default: 7 days)
   - Run NLP matching algorithm
   - Save match results to database
5. **Stage 5 - Google Sheets Export**: Export matches and logs (non-critical)
6. **Stage 6 - Telegram Notification**: Send push notification (non-critical)

Each stage has granular exception handling:
- Stages 1-2 abort on failure (critical)
- Stages 3-6 continue with warnings if they fail (graceful degradation)

## Integration with Telegram Bot

The scheduler is initialized in `TelegramBot.__init__()`:

```python
self.scheduler = JobScheduler()
self.scheduler.set_telegram_callback(self._send_push_notification)
```

The bot's JobQueue triggers `run_scheduled_search()` at configured times.
