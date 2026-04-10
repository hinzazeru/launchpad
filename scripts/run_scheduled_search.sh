#!/bin/bash
# LinkedIn Job Search - Scheduled Task
# Called by launchd - wakes Mac from sleep if needed, runs job, sleeps if idle
# Skips execution on weekends (Saturday and Sunday)

PROJECT_DIR="/Users/hinza/Documents/[20]_Project/ClaudeProjects/LinkedInJobSearch"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
LOG_FILE="${PROJECT_DIR}/launchd_search.log"

# Check if it's a weekend (Saturday=6, Sunday=0)
DAY_OF_WEEK=$(date +%w)
if [ "$DAY_OF_WEEK" -eq 0 ] || [ "$DAY_OF_WEEK" -eq 6 ]; then
    echo "$(date): Skipping scheduled search (weekend)" >> "${LOG_FILE}"
    exit 0
fi

echo "========================================" >> "${LOG_FILE}"
echo "$(date): Starting scheduled search" >> "${LOG_FILE}"

cd "${PROJECT_DIR}"

# Run the scheduled search
"${VENV_PYTHON}" -c "
from src.scheduler.job_scheduler import JobScheduler

scheduler = JobScheduler()

# Simple callback for Telegram notifications
def send_notification(message):
    import asyncio
    from telegram import Bot
    from src.config import get_config

    config = get_config()
    bot_token = config.get('telegram.bot_token')
    user_id = config.get('telegram.allowed_user_id')

    if bot_token and user_id:
        async def _send():
            bot = Bot(token=bot_token)
            await bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
        try:
            asyncio.run(_send())
        except Exception as e:
            print(f'Notification error: {e}')

scheduler.set_telegram_callback(send_notification)
scheduler.run_scheduled_search()
" >> "${LOG_FILE}" 2>&1

echo "$(date): Search completed" >> "${LOG_FILE}"

# Wait for notifications to be sent
sleep 10

# Sleep only if display is off (user not actively using Mac)
DISPLAY_STATE=$(ioreg -r -d 1 -n IODisplayWrangler 2>/dev/null | grep -i "currentpowerstate" | awk '{print $NF}')

if [ -n "$DISPLAY_STATE" ] && [ "$DISPLAY_STATE" -lt "4" ] 2>/dev/null; then
    echo "$(date): Display off, putting Mac to sleep" >> "${LOG_FILE}"
    pmset sleepnow
else
    echo "$(date): Display on or unknown, Mac will sleep on its own schedule" >> "${LOG_FILE}"
fi

echo "========================================" >> "${LOG_FILE}"
