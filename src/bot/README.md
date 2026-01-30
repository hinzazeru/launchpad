# Bot Module

Telegram bot for remote control of the LinkedIn Job Matcher.

## Overview

This module provides a Telegram interface to control job searches, view matches, manage profiles, and configure the scheduler - all from your phone.

## Files

| File | Purpose |
|------|---------|
| `telegram_bot.py` | Main bot implementation with all command handlers |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all available commands |
| `/search` | Run job search with active profile |
| `/search <keyword>` | Run search with custom keyword |
| `/status` | Show scheduler status, profile, next run |
| `/matches` | View top 5 recent matches (last 7 days) |
| `/profiles` | List all keyword profiles |
| `/profiles <name>` | Switch to a profile |
| `/profiles create <name> <keyword>` | Create new profile |
| `/profiles delete <name>` | Delete a profile |
| `/schedule` | View scheduled run times |
| `/schedule on/off` | Enable/disable scheduler |
| `/mute` | Toggle push notifications |
| `/cleanup` | Remove old entries from Google Sheets |
| `/config` | Show current configuration |

## Architecture

```
TelegramBot
├── __init__()           # Register command handlers, initialize scheduler
├── Command Handlers     # Async methods for each /command
├── _check_authorization()  # Verify user is allowed
├── _send_push_notification()  # Send async notifications
├── _setup_scheduled_jobs()    # Configure JobQueue
└── run()                # Start polling
```

## Key Patterns

### Authorization Check

Every command must verify the user:

```python
async def some_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not self._check_authorization(update):
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    # ... rest of command
```

### Markdown Escaping

**Critical**: Always escape dynamic content to prevent parse errors:

```python
from src.bot.telegram_bot import escape_markdown

# User-provided or database content must be escaped
profile_name = escape_markdown(status.get('active_profile', 'default'))
msg = f"Profile: {profile_name}"
```

Special characters that break Markdown: `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`

### Error Handling

Wrap command logic in try/except:

```python
try:
    # command logic
    await update.message.reply_text(result, parse_mode='Markdown')
except Exception as e:
    logger.error(f"Error in command: {e}", exc_info=True)
    await update.message.reply_text(f"❌ Error: {str(e)}")
```

## Adding a New Command

1. **Register handler** in `__init__()`:
   ```python
   self.application.add_handler(CommandHandler("newcmd", self.newcmd_command))
   ```

2. **Implement the method**:
   ```python
   async def newcmd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
       """Handle /newcmd command - description here."""
       if not self._check_authorization(update):
           await update.message.reply_text("❌ You are not authorized.")
           return

       # Your logic here
       await update.message.reply_text("Response", parse_mode='Markdown')
   ```

3. **Update help message** in `help_command()`

4. **Update documentation**:
   - `docs/TELEGRAM_BOT.md`
   - `docs/ARCHITECTURE.md`
   - `docs/SCHEDULER.md` (if scheduler-related)

## Scheduling

The bot uses **python-telegram-bot's JobQueue** (not standalone APScheduler) to avoid event loop conflicts with `run_polling()`.

Jobs are scheduled in `_setup_scheduled_jobs()`:

```python
job_queue.run_daily(
    scheduled_job_callback,
    time=time(hour=8, minute=0),
    data=self,
    name="linkedin_search_08:00"
)
```

Timezone is set via `Defaults(tzinfo=ZoneInfo("America/Toronto"))` when building the Application.

## Configuration

Required in `config.yaml`:

```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"      # From @BotFather
  allowed_user_id: "YOUR_USER_ID"  # From @userinfobot
```

## Security

- Only `allowed_user_id` can execute commands
- Bot token should never be committed to git
- Use environment variables in production

## Dependencies

- `python-telegram-bot`: Bot framework with JobQueue
- `src.scheduler.job_scheduler`: Job search orchestration
- `src.database`: Match results storage
- `src.integrations.sheets_connector`: Google Sheets export
