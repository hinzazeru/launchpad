"""Telegram bot for remote job matcher control.

This module provides a Telegram interface to control the LinkedIn Job Matcher.
Users can run job searches, view matches, manage keyword profiles, and configure
scheduling - all from their phone via Telegram commands.

Key Components:
    TelegramBot: Main bot class with command handlers
    escape_markdown(): Helper to escape special characters in messages
    scheduled_job_callback(): Callback for JobQueue scheduled searches

Available Commands:
    /start - Welcome message
    /help - Show all commands
    /search [keyword] - Run job search
    /status - Show scheduler status
    /matches - View recent top matches
    /profiles - Manage keyword profiles
    /schedule - View/manage schedule
    /mute - Toggle notifications
    /cleanup - Clean old Google Sheets entries
    /config - Show configuration

Important Patterns:
    - Always use escape_markdown() for dynamic content in messages
    - Always check authorization with _check_authorization() first
    - Wrap command logic in try/except for error handling
    - Use Telegram's JobQueue for scheduling (not standalone APScheduler)

Example:
    >>> bot = TelegramBot()
    >>> bot.run()  # Starts polling for commands
"""

import logging
import asyncio
from datetime import datetime, time, timezone
from typing import Optional, Dict, Any, List, Callable
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults

from src.config import get_config
from src.scheduler.job_scheduler import JobScheduler
from src.database.db import SessionLocal
from src.database.models import MatchResult
from src.integrations.sheets_connector import SheetsConnector

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters in text.

    IMPORTANT: This function MUST be used for any dynamic content in Telegram
    messages that use parse_mode='Markdown'. Without escaping, characters like
    underscores in profile names (e.g., "senior_pm") will be interpreted as
    italic markers and cause "Can't parse entities" errors.

    Common failure case:
        profile_name = "senior_pm"
        msg = f"Profile: {profile_name}"  # FAILS - underscore breaks Markdown

    Correct usage:
        profile_name = escape_markdown("senior_pm")
        msg = f"Profile: {profile_name}"  # Works - underscore is escaped

    Args:
        text: Text to escape (can be None or any type, will be converted to str)

    Returns:
        Text with special characters escaped, or original text if None/empty
    """
    if not text:
        return text
    # Telegram Markdown special characters that need escaping
    # Reference: https://core.telegram.org/bots/api#markdownv2-style
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result


def format_job_freshness(posting_date: datetime, import_date: datetime = None) -> str:
    """Format job posting age as human-readable string with freshness indicator.

    Uses posting_date if available, otherwise falls back to import_date.
    Adds ⏰ indicator for jobs older than 2 days (considered "stale").

    Args:
        posting_date: When the job was posted on LinkedIn (can be None)
        import_date: When the job was imported to our database (fallback)

    Returns:
        Formatted string like "🕐 Posted today", "🕐 Posted 1d ago", "⏰ Posted 5d ago"
    """
    from datetime import timedelta

    # Use posting_date if available, otherwise import_date
    reference_date = posting_date or import_date
    if not reference_date:
        return ""

    now = datetime.now()
    # Handle timezone-aware datetimes
    if reference_date.tzinfo is not None:
        now = datetime.now(reference_date.tzinfo)

    delta = now - reference_date
    days = delta.days

    # Fresh indicator (≤2 days) vs stale indicator (>2 days)
    if days <= 2:
        emoji = "🕐"  # Fresh
    else:
        emoji = "⏰"  # Stale

    # Format the age string
    if days == 0:
        return f"{emoji} Posted today"
    elif days == 1:
        return f"{emoji} Posted 1d ago"
    else:
        return f"{emoji} Posted {days}d ago"


async def scheduled_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for scheduled job searches using Telegram's JobQueue.

    This function is called by the JobQueue at scheduled times (e.g., 08:00, 12:00).
    We use JobQueue instead of standalone APScheduler to avoid event loop conflicts
    with python-telegram-bot's run_polling() method.

    Args:
        context: Telegram callback context containing job data
    """
    bot: 'TelegramBot' = context.job.data
    logger.info("=" * 60)
    logger.info(f"JobQueue triggered scheduled search at {datetime.now()}")
    logger.info("=" * 60)

    try:
        # Run the scheduled search
        bot.scheduler.run_scheduled_search()
        logger.info("Scheduled search completed. Next runs managed by JobQueue.")
    except Exception as e:
        logger.error(f"Scheduled job search failed: {e}", exc_info=True)
        # Attempt to notify user of failure via Telegram
        try:
            if bot.scheduler.telegram_notify_callback:
                bot.scheduler.telegram_notify_callback(
                    f"⚠️ *Scheduled Search Failed*\n\n"
                    f"Error: {escape_markdown(str(e))}\n\n"
                    f"Check logs for details."
                )
        except Exception as notify_error:
            logger.error(f"Failed to send error notification: {notify_error}")


class TelegramBot:
    """Telegram bot for controlling the job matcher remotely.

    Commands:
    - /start - Welcome message and help
    - /help - Show available commands
    - /search - Run immediate job search
    - /status - Show scheduler status
    - /matches - Show recent top matches
    - /config - Show current configuration
    - /cleanup - Clean up old job matches from Google Sheets
    - /schedule - View and manage automated search schedule
    """

    def __init__(self):
        """Initialize the Telegram bot."""
        self.config = get_config()
        self.enabled = self.config.get("telegram.enabled", False)

        if not self.enabled:
            logger.info("Telegram bot is disabled in configuration")
            return

        self.bot_token = self.config.get("telegram.bot_token")
        self.allowed_user_id = self.config.get("telegram.allowed_user_id")

        if not self.bot_token:
            logger.error("Telegram bot token not configured")
            self.enabled = False
            return

        # Initialize scheduler for job searches
        self.scheduler = JobScheduler()

        # Register notification callback with scheduler
        self.scheduler.set_telegram_callback(self._send_push_notification)

        # Initialize sheets connector for cleanup command
        self.sheets_connector = SheetsConnector()

        # Set timezone for scheduled jobs
        self.local_tz = ZoneInfo("America/Toronto")
        defaults = Defaults(tzinfo=self.local_tz)

        # Build application with timezone defaults
        self.application = Application.builder().token(self.bot_token).defaults(defaults).build()

        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("matches", self.matches_command))
        self.application.add_handler(CommandHandler("config", self.config_command))
        self.application.add_handler(CommandHandler("cleanup", self.cleanup_command))
        self.application.add_handler(CommandHandler("schedule", self.schedule_command))
        self.application.add_handler(CommandHandler("profiles", self.profiles_command))
        self.application.add_handler(CommandHandler("mute", self.mute_command))
        self.application.add_handler(CommandHandler("perf", self.perf_command))
        self.application.add_handler(CommandHandler("domains", self.domains_command))

    def _check_authorization(self, update: Update) -> bool:
        """Check if user is authorized to use the bot.

        Args:
            update: Telegram update object

        Returns:
            bool: True if authorized, False otherwise
        """
        if not self.allowed_user_id:
            # If no user ID is set, allow anyone (not recommended)
            return True

        user_id = update.effective_user.id
        if str(user_id) != str(self.allowed_user_id):
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            return False

        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        welcome_message = (
            "👋 Welcome to LinkedIn Job Matcher Bot!\n\n"
            "I help you control your job search automation remotely.\n\n"
            "Available commands:\n"
            "/help - Show all commands\n"
            "/search - Run immediate job search\n"
            "/status - Check scheduler status\n"
            "/matches - View recent top matches\n"
            "/config - Show current configuration\n\n"
            "Let's find your dream job! 🚀"
        )

        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        help_message = (
            "📚 *Available Commands*\n\n"
            "*Job Search:*\n"
            "/search - Run search with active profile keywords\n"
            "/search <keyword> - Search for specific keyword only\n\n"
            "*Keyword Profiles:*\n"
            "/profiles - List all profiles\n"
            "/profiles <name> - Switch to profile\n"
            "/profiles create <name> <keyword> - Create\n"
            "/profiles delete <name> - Delete\n\n"
            "*Profile Settings:*\n"
            "/domains - View/manage your domain expertise\n"
            "/domains list - See all available domains\n"
            "/domains add <domain> - Add domain expertise\n\n"
            "*Monitoring:*\n"
            "/status - Show scheduler status and statistics\n"
            "/matches - View your top 5 recent matches\n"
            "/config - Display current configuration\n\n"
            "*Automation:*\n"
            "/schedule - View current schedule\n"
            "/schedule on/off - Enable/disable\n"
            "/mute - Toggle push notifications\n"
            "/perf - Toggle performance stats\n\n"
            "*Maintenance:*\n"
            "/cleanup - Remove old matches from Google Sheets\n"
        )

        await update.message.reply_text(help_message, parse_mode='Markdown')

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command - run immediate job search.

        Usage:
            /search - Uses configured keywords from config.yaml
            /search product manager - Searches only for "product manager"
            /search senior product manager remote - Searches only for "senior product manager remote"
        """
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        # Extract keywords from command (everything after /search)
        custom_keyword = None
        if context.args and len(context.args) > 0:
            custom_keyword = ' '.join(context.args)
            await update.message.reply_text(
                f"🔍 Starting job search for: *{custom_keyword}*\n"
                "This may take a few minutes. I'll notify you when it's done!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "🔍 Starting job search with configured keywords...\n"
                "This may take a few minutes. I'll notify you when it's done!"
            )

        try:
            # Run job search in background
            logger.info(f"Job search initiated by Telegram user {update.effective_user.id}")
            if custom_keyword:
                logger.info(f"Using custom keyword: {custom_keyword}")

            # Run search (with custom keyword if provided)
            perf_stats = self.scheduler.run_now(custom_keywords=custom_keyword)

            # Get results
            session = SessionLocal()
            try:
                # Get recent matches from the last 5 minutes (the ones we just created)
                from datetime import timedelta
                recent_time = datetime.now() - timedelta(minutes=5)

                # Get all recent matches to count total and high-scoring
                all_recent_matches = session.query(MatchResult)\
                    .filter(MatchResult.generated_date >= recent_time)\
                    .all()

                # Get high-scoring matches (≥70%)
                high_score_matches = [m for m in all_recent_matches if m.match_score >= 70]

                # Get blend weights for sorting
                ai_weight = self.config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
                nlp_weight = self.config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

                def get_blended_score(match):
                    nlp_score = match.match_score / 100  # Convert from 0-100 to 0-1
                    ai_score = match.gemini_score / 100 if match.gemini_score else None
                    if ai_score is not None:
                        return (ai_score * ai_weight) + (nlp_score * nlp_weight)
                    return nlp_score

                # Get top 5 for display, sorted by blended score
                top_matches = sorted(high_score_matches, key=get_blended_score, reverse=True)[:5]

                # Build Google Sheets URL
                spreadsheet_id = self.config.get("sheets.spreadsheet_id")
                sheets_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}" if spreadsheet_id else None

                # Build result message
                result_message = "✅ Job Search Completed!\n\n"

                # Show counts
                result_message += f"📊 Total jobs analyzed: {len(all_recent_matches)}\n"
                result_message += f"⭐ High-quality matches (≥70%): {len(high_score_matches)}\n\n"

                # Show top matches
                if top_matches:
                    from src.matching.skill_extractor import get_domain_display_name
                    result_message += f"🔝 Top {len(top_matches)} Matches:\n\n"

                    for i, match in enumerate(top_matches, 1):
                        score_pct = int(match.match_score)
                        emoji = "🔥" if score_pct >= 85 else "✨" if score_pct >= 75 else "⭐"
                        job = match.job_posting
                        job_url = job.url

                        # Create clickable title if URL exists
                        if job_url:
                            title_line = f"{emoji} [{escape_markdown(job.title)}]({job_url})"
                        else:
                            title_line = f"{emoji} *{escape_markdown(job.title)}*"

                        # Format company with domains
                        company_text = escape_markdown(job.company)
                        if job.required_domains:
                            domain_names = [get_domain_display_name(d) for d in job.required_domains[:2]]
                            company_text += f" ({', '.join(domain_names)})"

                        # Format scores line: Company (Domains) • 🤖 AI% • 📊 NLP%
                        if match.gemini_score:
                            ai_score = int(match.gemini_score)
                            scores_line = f"   {company_text} • 🤖 {ai_score}% • 📊 {score_pct}%"
                        else:
                            scores_line = f"   {company_text} • 📊 {score_pct}%"

                        result_message += f"{title_line}\n{scores_line}\n\n"

                # Add Google Sheets link
                if sheets_url:
                    result_message += f"\n📊 [View All Results in Google Sheets]({sheets_url})"
                else:
                    result_message += "\n📊 Check Google Sheets for full details"

                # Add performance stats if enabled
                if perf_stats and perf_stats.get('enabled'):
                    stages = perf_stats.get('stages', {})
                    result_message += f"\n\n⏱️ *Performance* ({perf_stats.get('total', 0):.1f}s total):\n"
                    if 'apify' in stages:
                        result_message += f"• Apify: {stages['apify']:.1f}s\n"
                    if 'import' in stages:
                        result_message += f"• Import \\+ AI: {stages['import']:.1f}s\n"
                    if 'matching' in stages:
                        result_message += f"• Matching: {stages['matching']:.1f}s\n"
                    if 'gemini_rerank' in stages and stages['gemini_rerank'] > 0:
                        rerank_details = perf_stats.get('gemini_rerank_details', {})
                        jobs_eval = rerank_details.get('jobs_evaluated', 0)
                        avg_time = rerank_details.get('avg_eval_time', 0)
                        result_message += f"• Gemini Re\\-rank: {stages['gemini_rerank']:.1f}s ({jobs_eval} jobs, {avg_time}s/job)\n"
                    if 'sheets' in stages:
                        result_message += f"• Sheets: {stages['sheets']:.1f}s"

                await update.message.reply_text(result_message, parse_mode='Markdown', disable_web_page_preview=True)

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error during job search: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error during job search:\n{str(e)}\n\n"
                "Please check the logs for details."
            )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show scheduler status."""
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        try:
            status = self.scheduler.get_status()

            if not status['enabled']:
                await update.message.reply_text(
                    "⚠️ Job scheduling is currently disabled.\n\n"
                    "Enable it in config.yaml to automate job searches."
                )
                return

            # Build status message
            status_msg = "📊 *Scheduler Status*\n\n"

            # Running status
            if status['running']:
                status_msg += "✅ Scheduler: Running\n"
            else:
                status_msg += "⏸ Scheduler: Stopped\n"

            # Mute status
            if status.get('muted'):
                status_msg += "🔇 Notifications: Muted\n"
            else:
                status_msg += "🔔 Notifications: On\n"

            # Configuration
            status_msg += f"\n*Configuration:*\n"
            profile_name = escape_markdown(status.get('active_profile', 'default'))
            status_msg += f"Profile: {profile_name}\n"
            keyword = status.get('search_keyword', '')
            if keyword:
                status_msg += f"Keyword: {escape_markdown(keyword)}\n"
            status_msg += f"Interval: Every {status['interval_hours']}h ({status['start_time']}\\-{status['end_time']})\n"

            # Next run
            if status.get('next_run'):
                status_msg += f"\n⏰ Next run: {status['next_run']}\n"

            # Statistics
            stats = status['stats']
            status_msg += f"\n*Statistics:*\n"
            status_msg += f"Total runs: {stats['total_runs']}\n"
            status_msg += f"Successful: {stats['successful_runs']}\n"
            status_msg += f"Failed: {stats['failed_runs']}\n"

            if stats.get('last_success'):
                status_msg += f"\nLast success: {stats['last_success']}\n"

            await update.message.reply_text(status_msg, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error getting status: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error getting status:\n{str(e)}"
            )

    async def matches_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /matches command - show recent top matches."""
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        try:
            from src.database.models import Resume
            from src.matching.skill_extractor import match_domains, get_domain_display_name

            session = SessionLocal()
            try:
                # Get user's resume domains
                resume = session.query(Resume).order_by(Resume.updated_at.desc()).first()
                user_domains = resume.domains if resume and resume.domains else []

                # Get top 5 matches from the last 7 days for FRESH jobs only
                from datetime import timedelta
                from src.database.models import JobPosting
                from sqlalchemy import or_

                week_ago = datetime.now() - timedelta(days=7)

                # Get max_job_age_days from config (default 7)
                from sqlalchemy import func

                max_job_age = self.config.get("matching.max_job_age_days", 7)
                job_cutoff = datetime.now() - timedelta(days=max_job_age)

                # Query recent matches for fresh jobs
                all_matches = session.query(MatchResult)\
                    .join(JobPosting, MatchResult.job_id == JobPosting.id)\
                    .filter(MatchResult.generated_date >= week_ago)\
                    .filter(
                        or_(
                            JobPosting.posting_date >= job_cutoff,
                            (JobPosting.posting_date.is_(None)) & (JobPosting.import_date >= job_cutoff)
                        )
                    )\
                    .limit(100)\
                    .all()

                # Get blend weights for sorting
                ai_weight = self.config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
                nlp_weight = self.config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

                def get_blended_score(match):
                    nlp_score = match.match_score / 100
                    ai_score = match.gemini_score / 100 if match.gemini_score else None
                    if ai_score is not None:
                        return (ai_score * ai_weight) + (nlp_score * nlp_weight)
                    return nlp_score

                # Sort by blended score
                all_matches_sorted = sorted(all_matches, key=get_blended_score, reverse=True)

                # Deduplicate by job_id, keeping highest blended score
                seen_jobs = set()
                matches = []
                for match in all_matches_sorted:
                    if match.job_id not in seen_jobs:
                        seen_jobs.add(match.job_id)
                        matches.append(match)
                        if len(matches) >= 5:
                            break

                if not matches:
                    await update.message.reply_text(
                        "📭 No matches found in the last 7 days.\n\n"
                        "Run /search to find new opportunities!"
                    )
                    return

                matches_msg = f"⭐ *Top {len(matches)} Matches (Last 7 Days)*\n\n"

                for i, match in enumerate(matches, 1):
                    score_pct = int(match.match_score)
                    job = match.job_posting

                    # Emoji based on score
                    emoji = "🔥" if score_pct >= 85 else "✨" if score_pct >= 75 else "⭐"

                    # Format title with link if URL available
                    if job.url:
                        title_line = f"{emoji} [{escape_markdown(job.title)}]({job.url})"
                    else:
                        title_line = f"{emoji} *{escape_markdown(job.title)}*"

                    # Format company with domains
                    company_text = escape_markdown(job.company)
                    if job.required_domains:
                        domain_names = [get_domain_display_name(d) for d in job.required_domains[:2]]
                        company_text += f" ({', '.join(domain_names)})"

                    # Format scores line: Company (Domains) • 🤖 AI% • 📊 NLP%
                    if match.gemini_score:
                        ai_score = int(match.gemini_score)
                        scores_line = f"   {company_text} • 🤖 {ai_score}% • 📊 {score_pct}%"
                    else:
                        scores_line = f"   {company_text} • 📊 {score_pct}%"

                    # Optional: salary and freshness on one line
                    extras = []
                    if job.salary:
                        extras.append(f"💰 {job.salary}")
                    freshness = format_job_freshness(job.posting_date, job.import_date)
                    if freshness:
                        extras.append(freshness)
                    extras_line = f"   {' • '.join(extras)}" if extras else ""

                    matches_msg += f"{title_line}\n{scores_line}\n"
                    if extras_line:
                        matches_msg += f"{extras_line}\n"
                    matches_msg += "\n"

                matches_msg += "📊 See Google Sheets for full details"

                await update.message.reply_text(matches_msg, parse_mode='Markdown')

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error getting matches: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error getting matches:\n{str(e)}"
            )

    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /config command - show current configuration."""
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        try:
            config_msg = "⚙️ *Current Configuration*\n\n"

            # Scheduling
            sched_enabled = self.config.get("scheduling.enabled", False)
            config_msg += f"*Scheduling:* {'✅ Enabled' if sched_enabled else '❌ Disabled'}\n"

            if sched_enabled:
                interval = self.config.get("scheduling.interval_hours", 24)
                start_time = self.config.get("scheduling.start_time", "09:00")
                config_msg += f"Interval: Every {interval} hours\n"
                if interval == 24:
                    config_msg += f"Time: {start_time} daily\n"

            # Sheets
            sheets_enabled = self.config.get("sheets.enabled", False)
            config_msg += f"\n*Google Sheets:* {'✅ Enabled' if sheets_enabled else '❌ Disabled'}\n"
            if sheets_enabled:
                threshold = int(self.config.get("sheets.export_min_score", 0.7) * 100)
                config_msg += f"Threshold: {threshold}%\n"

            # Matching
            config_msg += f"\n*Matching:*\n"
            min_score = int(self.config.get("matching.min_match_score", 0.6) * 100)
            config_msg += f"Min score: {min_score}%\n"

            skills_weight = int(self.config.get("matching.weights.skills", 0.45) * 100)
            exp_weight = int(self.config.get("matching.weights.experience", 0.35) * 100)
            domains_weight = int(self.config.get("matching.weights.domains", 0.20) * 100)
            config_msg += f"Weights: Skills {skills_weight}%, Experience {exp_weight}%, Domains {domains_weight}%\n"

            await update.message.reply_text(config_msg, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error showing config: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error showing config:\n{str(e)}"
            )

    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cleanup command - clean up old job matches from Google Sheets."""
        if not self._check_authorization(update):
            await update.message.reply_text(
                "❌ You are not authorized to use this bot."
            )
            return

        await update.message.reply_text(
            "🧹 Starting cleanup of old job matches...\n"
            "Removing entries older than 7 days from Google Sheets."
        )

        try:
            # Clean up Job Matches sheet
            matches_result = self.sheets_connector.cleanup_old_matches(days=7)

            # Build result message
            result_msg = "✅ *Cleanup Complete*\n\n"

            result_msg += "*Job Matches Sheet:*\n"
            if matches_result['success']:
                if matches_result['deleted_count'] > 0:
                    result_msg += f"🗑 Deleted: {matches_result['deleted_count']} old entries\n"
                    result_msg += f"📊 Remaining: {matches_result['remaining_count']} entries\n"
                else:
                    result_msg += "✓ No old entries to remove\n"
                    result_msg += f"📊 Total entries: {matches_result['remaining_count']}\n"
            else:
                result_msg += f"⚠️ {matches_result['message']}\n"

            await update.message.reply_text(result_msg, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error during cleanup:\n{str(e)}"
            )

    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /schedule command - view and manage automated search schedule."""
        if not self._check_authorization(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        try:
            args = context.args if context.args else []

            # No arguments - show current schedule
            if not args:
                status = self.scheduler.get_status()
                schedule_msg = "📅 *Automated Search Schedule*\n\n"

                if status['enabled']:
                    schedule_msg += "Status: ✅ *Enabled*\n\n"
                else:
                    schedule_msg += "Status: ❌ *Disabled*\n\n"

                schedule_msg += f"*Time Window:* {status['start_time']} - {status['end_time']}\n"
                schedule_msg += f"*Interval:* Every {status['interval_hours']} hours\n"
                schedule_msg += f"*Scheduled Times:* {', '.join(status.get('scheduled_times', []))}\n"

                if status.get('next_run'):
                    schedule_msg += f"\n⏰ *Next Run:* {status['next_run']}\n"

                schedule_msg += "\n*Commands:*\n"
                schedule_msg += "`/schedule on` - Enable\n"
                schedule_msg += "`/schedule off` - Disable\n"
                schedule_msg += "`/schedule 4` - Set 4-hour interval\n"
                schedule_msg += "`/schedule 08:00-22:00` - Set time window\n"

                await update.message.reply_text(schedule_msg, parse_mode='Markdown')
                return

            # Parse arguments
            arg = args[0].lower()

            # Enable/disable
            if arg == 'on':
                result = self.scheduler.update_schedule(enabled=True)
                await update.message.reply_text(
                    "✅ *Automated searches enabled!*\n\n"
                    f"Searches will run at: {', '.join(result['new_settings']['scheduled_times'])}",
                    parse_mode='Markdown'
                )
                return

            if arg == 'off':
                result = self.scheduler.update_schedule(enabled=False)
                await update.message.reply_text(
                    "❌ *Automated searches disabled.*\n\n"
                    "Use `/schedule on` to re-enable.",
                    parse_mode='Markdown'
                )
                return

            # Set interval (e.g., "4" for every 4 hours)
            if arg.isdigit():
                interval = int(arg)
                if interval < 1 or interval > 24:
                    await update.message.reply_text("❌ Interval must be between 1 and 24 hours.")
                    return

                result = self.scheduler.update_schedule(interval_hours=interval)
                await update.message.reply_text(
                    f"✅ *Schedule updated!*\n\n"
                    f"Interval: Every {interval} hours\n"
                    f"Searches at: {', '.join(result['new_settings']['scheduled_times'])}",
                    parse_mode='Markdown'
                )
                return

            # Set time window (e.g., "08:00-22:00")
            if '-' in arg and ':' in arg:
                try:
                    start_time, end_time = arg.split('-')
                    # Validate time format
                    for t in [start_time, end_time]:
                        h, m = map(int, t.split(':'))
                        if h < 0 or h > 23 or m < 0 or m > 59:
                            raise ValueError("Invalid time")

                    result = self.scheduler.update_schedule(start_time=start_time, end_time=end_time)
                    await update.message.reply_text(
                        f"✅ *Schedule updated!*\n\n"
                        f"Time window: {start_time} - {end_time}\n"
                        f"Searches at: {', '.join(result['new_settings']['scheduled_times'])}",
                        parse_mode='Markdown'
                    )
                    return
                except (ValueError, AttributeError):
                    await update.message.reply_text(
                        "❌ Invalid time format. Use HH:MM-HH:MM (e.g., 08:00-22:00)"
                    )
                    return

            # Unknown argument
            await update.message.reply_text(
                "❌ Unknown argument. Use:\n"
                "`/schedule` - View schedule\n"
                "`/schedule on/off` - Enable/disable\n"
                "`/schedule 4` - Set 4-hour interval\n"
                "`/schedule 08:00-22:00` - Set time window",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error in schedule command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def profiles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profiles command - list, switch, create, or delete profiles.

        Usage:
            /profiles - List all profiles
            /profiles <name> - Switch to profile
            /profiles create <name> <keyword> - Create profile
            /profiles delete <name> - Delete profile
        """
        if not self._check_authorization(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        try:
            args = context.args

            # No args - list all profiles
            if not args:
                profile_info = self.scheduler.get_profiles()
                active = profile_info['active_profile']
                profiles = profile_info['profiles']

                message = "📋 *Keyword Profiles*\n\n"

                for name, config in profiles.items():
                    keyword = config.get('keyword') or (config.get('keywords', [''])[0] if config.get('keywords') else '')
                    is_active = "✅ " if name == active else "   "
                    message += f"{is_active}*{escape_markdown(name)}*: {escape_markdown(keyword)}\n"

                message += f"\n_Active: {escape_markdown(active)}_\n"
                message += "_1 keyword = 1 API call per search_\n\n"
                message += "`/profiles <name>` to switch"

                await update.message.reply_text(message, parse_mode='Markdown')
                return

            action = args[0].lower()

            # Create profile: /profiles create <name> <keyword>
            if action == "create":
                if len(args) < 3:
                    await update.message.reply_text(
                        "❌ Usage: `/profiles create <name> <keyword>`\n\n"
                        "Example: `/profiles create tech Technical PM`",
                        parse_mode='Markdown'
                    )
                    return

                profile_name = args[1]
                keyword = ' '.join(args[2:])

                if not keyword:
                    await update.message.reply_text("❌ Please provide a keyword")
                    return

                result = self.scheduler.create_profile(profile_name, keyword)

                if result['success']:
                    await update.message.reply_text(
                        f"✅ *Profile created\\!*\n\n"
                        f"Name: *{escape_markdown(profile_name)}*\n"
                        f"Keyword: {escape_markdown(keyword)}\n\n"
                        f"Use `/profiles {escape_markdown(profile_name)}` to activate",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(f"❌ {result['error']}")
                return

            # Delete profile: /profiles delete <name>
            if action == "delete":
                if len(args) < 2:
                    await update.message.reply_text(
                        "❌ Usage: `/profiles delete <name>`",
                        parse_mode='Markdown'
                    )
                    return

                profile_name = args[1]
                result = self.scheduler.delete_profile(profile_name)

                if result['success']:
                    remaining = [escape_markdown(p) for p in result['remaining_profiles']]
                    await update.message.reply_text(
                        f"✅ Profile *{escape_markdown(profile_name)}* deleted\n\n"
                        f"Remaining: {', '.join(remaining)}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(f"❌ {result['error']}")
                return

            # Switch profile: /profiles <name>
            profile_name = action
            result = self.scheduler.set_active_profile(profile_name)

            if result['success']:
                keyword = result['keyword']
                await update.message.reply_text(
                    f"✅ *Switched to: {escape_markdown(profile_name)}*\n\nKeyword: {escape_markdown(keyword)}",
                    parse_mode='Markdown'
                )
            else:
                available = [escape_markdown(p) for p in result.get('available_profiles', [])]
                await update.message.reply_text(
                    f"❌ {result['error']}\n\nAvailable: {', '.join(available)}",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Error in profiles command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mute command - toggle notification mute."""
        if not self._check_authorization(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        try:
            result = self.scheduler.toggle_mute()

            if result['muted']:
                await update.message.reply_text(
                    "🔇 *Notifications muted*\n\n"
                    "Scheduled searches will still run, but you won't receive push notifications.\n\n"
                    "Use `/mute` again to unmute.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "🔔 *Notifications unmuted*\n\n"
                    "You'll receive push notifications for new matches.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Error in mute command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def perf_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /perf command - toggle performance stats display."""
        if not self._check_authorization(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        try:
            current = self.config.get("logging.show_performance_stats", False)
            new_value = not current
            self.config.set("logging.show_performance_stats", new_value)
            self.config.save()

            if new_value:
                await update.message.reply_text(
                    "⏱️ *Performance stats enabled*\n\n"
                    "Search results will show timing for each stage.\n\n"
                    "Use `/perf` again to disable.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "⏱️ *Performance stats disabled*\n\n"
                    "Use `/perf` again to enable.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Error in perf command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def domains_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /domains command - view/update domain expertise.

        Usage:
            /domains - View current domain expertise
            /domains add fintech ecommerce - Add domains to profile
            /domains remove fintech - Remove domain from profile
            /domains list - Show all available domains
        """
        if not self._check_authorization(update):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        try:
            from src.database.models import Resume
            from src.matching.skill_extractor import load_domain_expertise, get_domain_display_name

            args = context.args if context.args else []

            session = SessionLocal()
            try:
                resume = session.query(Resume).order_by(Resume.updated_at.desc()).first()

                if not resume:
                    await update.message.reply_text(
                        "❌ No resume found. Please upload a resume first."
                    )
                    return

                # Handle subcommands
                if not args:
                    # Show current domains
                    current_domains = resume.domains or []

                    if current_domains:
                        domains_list = "\n".join([
                            f"  • {escape_markdown(get_domain_display_name(d))}"
                            for d in current_domains
                        ])
                        msg = (
                            f"🏷️ *Your Domain Expertise*\n\n"
                            f"{domains_list}\n\n"
                            f"_Use `/domains add <domain>` to add more_\n"
                            f"_Use `/domains list` to see all options_"
                        )
                    else:
                        msg = (
                            "🏷️ *Your Domain Expertise*\n\n"
                            "_No domains set yet._\n\n"
                            "Add your domain expertise to improve job matching:\n"
                            "`/domains add fintech b2b_saas`\n\n"
                            "Use `/domains list` to see all available domains."
                        )

                    await update.message.reply_text(msg, parse_mode='Markdown')

                elif args[0].lower() == 'list':
                    # Show all available domains
                    expertise_data = load_domain_expertise()
                    domains = expertise_data.get("domains", {})

                    msg = "🏷️ *Available Domains*\n\n"

                    for category, category_domains in domains.items():
                        category_name = category.replace('_', ' ').title()
                        msg += f"*{category_name}:*\n"
                        for domain_key in sorted(category_domains.keys())[:8]:
                            display_name = get_domain_display_name(domain_key)
                            msg += f"  `{domain_key}` \\- {escape_markdown(display_name)}\n"
                        if len(category_domains) > 8:
                            msg += f"  _...and {len(category_domains) - 8} more_\n"
                        msg += "\n"

                    msg += "_Use `/domains add <domain_key>` to add_"
                    await update.message.reply_text(msg, parse_mode='MarkdownV2')

                elif args[0].lower() == 'add' and len(args) > 1:
                    # Add domains
                    domains_to_add = [d.lower() for d in args[1:]]
                    current_domains = resume.domains or []

                    # Validate domains exist
                    expertise_data = load_domain_expertise()
                    all_domains = expertise_data.get("domains", {})
                    valid_domain_keys = set()
                    for category_domains in all_domains.values():
                        valid_domain_keys.update(category_domains.keys())

                    added = []
                    invalid = []
                    already_exists = []

                    for d in domains_to_add:
                        if d not in valid_domain_keys:
                            invalid.append(d)
                        elif d in current_domains:
                            already_exists.append(d)
                        else:
                            current_domains.append(d)
                            added.append(d)

                    if added:
                        resume.domains = current_domains
                        session.commit()

                    msg_parts = []
                    if added:
                        added_names = [get_domain_display_name(d) for d in added]
                        msg_parts.append(f"✅ Added: {', '.join(added_names)}")
                    if already_exists:
                        msg_parts.append(f"ℹ️ Already in profile: {', '.join(already_exists)}")
                    if invalid:
                        msg_parts.append(f"❌ Invalid domains: {', '.join(invalid)}")
                        msg_parts.append("_Use `/domains list` to see valid options_")

                    await update.message.reply_text(
                        "\n".join(msg_parts),
                        parse_mode='Markdown'
                    )

                elif args[0].lower() == 'remove' and len(args) > 1:
                    # Remove domains
                    domains_to_remove = [d.lower() for d in args[1:]]
                    current_domains = resume.domains or []

                    removed = []
                    not_found = []

                    for d in domains_to_remove:
                        if d in current_domains:
                            current_domains.remove(d)
                            removed.append(d)
                        else:
                            not_found.append(d)

                    if removed:
                        resume.domains = current_domains
                        session.commit()

                    msg_parts = []
                    if removed:
                        removed_names = [get_domain_display_name(d) for d in removed]
                        msg_parts.append(f"✅ Removed: {', '.join(removed_names)}")
                    if not_found:
                        msg_parts.append(f"ℹ️ Not in profile: {', '.join(not_found)}")

                    await update.message.reply_text("\n".join(msg_parts))

                else:
                    await update.message.reply_text(
                        "📖 *Domain Commands*\n\n"
                        "`/domains` \\- View your domains\n"
                        "`/domains list` \\- See all available domains\n"
                        "`/domains add <domain>` \\- Add domain\\(s\\)\n"
                        "`/domains remove <domain>` \\- Remove domain\\(s\\)\n\n"
                        "Example: `/domains add fintech ecommerce`",
                        parse_mode='MarkdownV2'
                    )

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error in domains command: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error: {str(e)}")

    def _send_push_notification(self, message: str):
        """Send push notification to authorized user (called by scheduler).

        Args:
            message: Markdown-formatted message to send
        """
        import asyncio

        async def _send():
            try:
                bot = self.application.bot
                await bot.send_message(
                    chat_id=self.allowed_user_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                logger.info("Push notification sent successfully")
            except Exception as e:
                logger.error(f"Failed to send push notification: {e}")

        # Run async function in the event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_send())
            else:
                loop.run_until_complete(_send())
        except RuntimeError:
            # No event loop, create one
            asyncio.run(_send())

    def _setup_scheduled_jobs(self, job_queue) -> None:
        """Set up scheduled jobs using Telegram's JobQueue.

        DESIGN DECISION: We use python-telegram-bot's built-in JobQueue instead of
        standalone APScheduler (BackgroundScheduler or AsyncIOScheduler) because:

        1. run_polling() creates and manages its own asyncio event loop
        2. APScheduler's AsyncIOScheduler conflicts with this event loop
        3. APScheduler's BackgroundScheduler runs in a separate thread, causing
           issues when trying to call async Telegram methods
        4. JobQueue is fully integrated with the Application and handles all
           thread/async coordination automatically

        The timezone is set via Defaults(tzinfo=ZoneInfo("America/Toronto")) when
        building the Application, so all time objects here are timezone-naive but
        will be interpreted in EST/EDT.

        Args:
            job_queue: Telegram's JobQueue instance from Application
        """
        if not self.scheduler.enabled:
            logger.info("Job scheduling is disabled in configuration")
            return

        scheduled_times = self.scheduler.get_scheduled_times()
        if not scheduled_times:
            logger.warning("No scheduled times configured")
            return

        # Timezone is set via Application Defaults (America/Toronto)
        logger.info(f"Setting up JobQueue with scheduled times: {scheduled_times} (timezone: America/Toronto via Defaults)")

        # Add a daily job for each scheduled time
        # Time object without tzinfo - will use Application's default timezone
        for time_str in scheduled_times:
            hour, minute = map(int, time_str.split(':'))
            job_time = time(hour=hour, minute=minute)

            job_queue.run_daily(
                scheduled_job_callback,
                time=job_time,
                data=self,  # Pass bot instance to callback
                name=f"linkedin_search_{time_str}"
            )
            logger.info(f"Scheduled daily job at {time_str}")

        logger.info(f"JobQueue setup complete. {len(scheduled_times)} daily jobs scheduled.")

    def run(self):
        """Start the bot."""
        if not self.enabled:
            logger.error("Cannot start bot - Telegram bot is disabled or not configured")
            return False

        # Set up scheduled jobs using Telegram's JobQueue
        self._setup_scheduled_jobs(self.application.job_queue)

        logger.info("Starting Telegram bot...")
        logger.info(f"Bot is ready! Send /start to begin.")

        # Run the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

        return True

    async def send_notification(self, message: str):
        """Send a notification message to the authorized user.

        Args:
            message: Message to send
        """
        if not self.enabled or not self.allowed_user_id:
            return

        try:
            await self.application.bot.send_message(
                chat_id=self.allowed_user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
