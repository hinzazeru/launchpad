"""Job scheduler for automated LinkedIn job searches.

This module manages automated job searches, keyword profiles, and coordinates
between the Apify API, matching engine, and notification systems.

NOTE: Scheduling is handled by Telegram's JobQueue in telegram_bot.py.
This class provides the search pipeline orchestration and profile management.

Key Features:
    - Profile management (single keyword per profile for cost optimization)
    - Manual search triggering (run_now)
    - Search pipeline orchestration (fetch → import → match → notify)
    - Mute functionality for notifications
    - Statistics tracking

Key Classes:
    JobScheduler: Main scheduler class for job search orchestration

Usage Example:
    >>> from src.scheduler.job_scheduler import JobScheduler
    >>>
    >>> scheduler = JobScheduler()
    >>>
    >>> # Run manual search
    >>> scheduler.run_now()
    >>>
    >>> # Switch profile
    >>> scheduler.set_active_profile("senior_pm")
    >>>
    >>> # Get status
    >>> status = scheduler.get_status()
    >>> print(f"Active profile: {status['active_profile']}")

Configuration (config.yaml):
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
"""

import logging
import time as time_module
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable

from src.config import get_config
from src.database.db import SessionLocal
from src.database.models import Resume, JobPosting, MatchResult
from src.database import crud
from src.importers.provider_factory import get_job_provider
from backend.services.matcher_service import get_job_matcher
from src.integrations.sheets_connector import SheetsConnector
from src.integrations.gemini_client import GeminiMatchReranker


logger = logging.getLogger(__name__)


class JobScheduler:
    """Job search orchestrator for LinkedIn job matching.

    This class coordinates job fetching, matching, and notifications.
    Scheduling is handled externally by Telegram's JobQueue.
    """

    def __init__(self):
        """Initialize the job scheduler."""
        self.config = get_config()
        self.enabled = self.config.get("scheduling.enabled", False)

        # Track statistics
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run': None,
            'last_success': None,
            'last_error': None,
        }

        # Initialize components
        self.provider = get_job_provider()
        self.matcher = get_job_matcher()  # Singleton — shares model with backend
        self.sheets_connector = SheetsConnector()
        self.gemini_reranker = GeminiMatchReranker()  # LLM-based match re-ranking

        # Pre-cache resume skills for faster matching
        self._preload_resume_skills()

        # Get scheduling configuration (for display purposes)
        self.interval_hours = self.config.get("scheduling.interval_hours", 24)
        self.start_time_str = self.config.get("scheduling.start_time", "08:00")
        self.end_time_str = self.config.get("scheduling.end_time", "22:00")

        # Load keyword profiles
        # DESIGN DECISION: Each profile has a SINGLE keyword to minimize API costs.
        self.active_profile = self.config.get("scheduling.active_profile", "pm")
        self.profiles = self.config.get("scheduling.profiles", {})
        self.search_keyword = self._get_profile_keyword(self.active_profile)

        # Notification settings
        self.notify_on_new_matches = self.config.get("scheduling.notify_on_new_matches", True)
        self.only_notify_new = self.config.get("scheduling.only_notify_new", True)
        self.muted = self.config.get("scheduling.muted", False)

        # Callback for sending Telegram notifications (set by TelegramBot)
        self.telegram_notify_callback: Optional[Callable] = None

        # Handle null values in config by falling back to defaults
        self.search_location = self.config.get("scheduling.search_location")
        if self.search_location is None:
            self.search_location = self.config.get("search.default_location", "United States")

        self.max_results = self.config.get("scheduling.max_results")
        if self.max_results is None:
            self.max_results = self.config.get("search.default_max_results", 20)

        if not self.enabled:
            logger.info("Job scheduling is disabled in configuration")

    def _preload_resume_skills(self):
        """Pre-cache resume skill embeddings for faster matching."""
        try:
            session = SessionLocal()
            try:
                resume = session.query(Resume).order_by(Resume.created_at.desc()).first()
                if resume and resume.skills:
                    cached_count = self.matcher.preload_resume_skills(resume.skills)
                    if cached_count > 0:
                        logger.info(f"Pre-cached {cached_count} resume skill embeddings")
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Could not preload resume skills: {e}")

    def get_scheduled_times(self) -> List[str]:
        """Get list of scheduled search times for today.

        Returns:
            List of time strings (e.g., ['08:00', '12:00', '16:00', '20:00'])
        """
        try:
            start_hour, start_minute = map(int, self.start_time_str.split(':'))
            end_hour, _ = map(int, self.end_time_str.split(':'))

            times = []
            current_hour = start_hour
            while current_hour <= end_hour:
                times.append(f"{current_hour:02d}:{start_minute:02d}")
                current_hour += self.interval_hours

            return times
        except (ValueError, AttributeError):
            return []

    def run_scheduled_search(self, custom_keywords=None) -> Optional[Dict]:
        """Run the scheduled job search.

        Args:
            custom_keywords: Optional list of keywords to override config (e.g., from Telegram bot)

        Returns:
            Dict with performance stats if tracking enabled, None otherwise

        This method executes the job search pipeline in stages:
        1. Fetches resume from database (critical - aborts if fails)
        2. Fetches jobs from LinkedIn via Apify (critical - aborts if fails)
        3. Imports jobs to database (continues with warning if fails)
        4. Matches jobs against resume (continues with warning if fails)
        5. Exports to Google Sheets (non-critical - continues if fails)
        6. Sends Telegram notifications (non-critical - continues if fails)

        Each stage has granular exception handling to allow better diagnostics
        and graceful degradation for non-critical operations.
        """
        current_time = datetime.now()
        logger.info("=" * 80)
        logger.info(f"Starting scheduled job search at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        self.stats['total_runs'] += 1
        self.stats['last_run'] = datetime.now()

        # Performance tracking
        perf_stats = {
            'enabled': self.config.get("logging.show_performance_stats", False),
            'total_start': time_module.perf_counter(),
            'stages': {}
        }

        # ========================================================================
        # STAGE 1: Resume Fetch (Critical - abort if fails)
        # ========================================================================
        stage_start = time_module.perf_counter()
        logger.info("[Stage 1/6] Fetching resume from database...")
        resume = None
        try:
            session = SessionLocal()
            try:
                resume = session.query(Resume).order_by(Resume.created_at.desc()).first()

                if not resume:
                    logger.error("[Stage 1] FAILED: No resume found. Please create a resume first.")
                    self.stats['failed_runs'] += 1
                    self.stats['last_error'] = "No resume found"
                    return self._finalize_perf_stats(perf_stats)

                logger.info(f"[Stage 1] SUCCESS: Using resume ID: {resume.id}")

            finally:
                session.close()

        except Exception as e:
            logger.error(f"[Stage 1] FAILED: Database error fetching resume: {e}", exc_info=True)
            self.stats['failed_runs'] += 1
            self.stats['last_error'] = f"Resume fetch failed: {e}"
            return self._finalize_perf_stats(perf_stats)
        perf_stats['stages']['resume'] = time_module.perf_counter() - stage_start

        # ========================================================================
        # STAGE 2: Apify Job Fetching (Critical - abort if fails)
        # ========================================================================
        stage_start = time_module.perf_counter()
        logger.info("[Stage 2/6] Fetching jobs from LinkedIn via Apify...")

        # Prepare search parameters
        if custom_keywords:
            keyword = custom_keywords if isinstance(custom_keywords, str) else custom_keywords[0]
            logger.info(f"Using custom keyword from Telegram: {keyword}")
        else:
            keyword = self.search_keyword if self.search_keyword else "Product Manager"
            logger.info(f"Using profile '{self.active_profile}' keyword: {keyword}")

        # Check if keyword ends with "Remote" for remote job search (case-insensitive)
        is_remote_search = keyword.strip().lower().endswith("remote")

        if is_remote_search:
            actual_keyword = keyword.strip()[:-6].strip()  # Remove "remote" suffix (6 chars)
            search_location = "United States"  # LinkedIn requires valid location; remote filter handles the rest
            work_arrangement = "Remote"
            logger.info(f"Remote job search detected!")
            logger.info(f"Searching for: {actual_keyword}")
            logger.info(f"Location: {search_location} (with remote filter)")
        else:
            actual_keyword = keyword
            search_location = self.search_location
            work_arrangement = None
            logger.info(f"Searching for: {keyword}")
            logger.info(f"Location: {search_location}")

        logger.info(f"Max results: {self.max_results}")

        jobs = []
        try:
            jobs = self.provider.search_jobs(
                keywords=actual_keyword,
                location=search_location,
                max_results=self.max_results,
                work_arrangement=work_arrangement
            )

            if not jobs:
                logger.warning(f"[Stage 2] WARNING: No jobs found for keyword: {keyword}")
            else:
                logger.info(f"[Stage 2] SUCCESS: Found {len(jobs)} jobs")

        except Exception as e:
            logger.error(f"[Stage 2] FAILED: Apify API error: {e}", exc_info=True)
            self.stats['failed_runs'] += 1
            self.stats['last_error'] = f"Apify job fetch failed: {e}"
            return self._finalize_perf_stats(perf_stats)
        perf_stats['stages']['apify'] = time_module.perf_counter() - stage_start
        perf_stats['jobs_fetched'] = len(jobs) if jobs else 0

        # If no jobs found, exit gracefully (not an error, just no results)
        if not jobs:
            logger.info("No jobs to process. Exiting.")
            self.stats['successful_runs'] += 1
            self.stats['last_success'] = datetime.now()
            return self._finalize_perf_stats(perf_stats)

        # ========================================================================
        # STAGE 3: Database Import (Continue with warning if fails)
        # ========================================================================
        stage_start = time_module.perf_counter()
        logger.info("[Stage 3/6] Importing jobs to database...")
        imported_count = 0
        try:
            imported_count = self.provider.import_jobs(jobs)
            logger.info(f"[Stage 3] SUCCESS: Imported {imported_count} new jobs")
        except Exception as e:
            logger.error(f"[Stage 3] FAILED: Database import error: {e}", exc_info=True)
            logger.warning("[Stage 3] Continuing with matching using fetched jobs...")
        perf_stats['stages']['import'] = time_module.perf_counter() - stage_start
        perf_stats['jobs_imported'] = imported_count

        # ========================================================================
        # STAGE 4: Job Matching (Continue with warning if fails)
        # ========================================================================
        stage_start = time_module.perf_counter()
        logger.info("[Stage 4/6] Matching jobs against resume...")
        all_matches = []
        try:
            db_session = SessionLocal()
            try:
                # Build query: filter by keyword AND location (unless remote search)
                query = db_session.query(JobPosting).filter(
                    JobPosting.title.ilike(f"%{actual_keyword}%")
                )

                # For regular searches, also filter by location to avoid matching
                # old jobs from different regions (e.g., US jobs when searching Canada)
                # For remote searches, skip location filter since remote jobs can be
                # listed from any location
                if not is_remote_search and search_location:
                    # Extract country/region from search_location for flexible matching
                    # e.g., "Canada" matches "Toronto, Ontario, Canada", "Canada", etc.
                    location_filter = search_location.split(',')[-1].strip()  # Get last part (usually country)
                    query = query.filter(JobPosting.location.ilike(f"%{location_filter}%"))
                    logger.info(f"Filtering jobs by location containing: '{location_filter}'")
                elif is_remote_search:
                    logger.info("Remote search - skipping location filter")

                # Filter by job freshness - only include jobs posted within max_job_age_days
                # This ensures we focus on recent listings, not stale month-old postings
                max_job_age_days = self.config.get("matching.max_job_age_days", 7)
                if max_job_age_days and max_job_age_days > 0:
                    from sqlalchemy import or_
                    cutoff_date = datetime.now() - timedelta(days=max_job_age_days)
                    # Use posting_date if available, otherwise fall back to import_date
                    query = query.filter(
                        or_(
                            JobPosting.posting_date >= cutoff_date,
                            # If posting_date is null, use import_date as fallback
                            (JobPosting.posting_date.is_(None)) & (JobPosting.import_date >= cutoff_date)
                        )
                    )
                    logger.info(f"Filtering jobs posted within last {max_job_age_days} days (since {cutoff_date.strftime('%Y-%m-%d')})")

                all_jobs = query.all()

                logger.info(f"Found {len(all_jobs)} total jobs in database matching criteria")

                # Match jobs with min_score=0.0 to get ALL jobs (not just high matches)
                matches = self.matcher.match_jobs(resume, all_jobs, min_score=0.0)

                # Gemini re-ranking (if enabled)
                if matches and self.gemini_reranker.is_available():
                    logger.info(f"[Stage 4a] Running Gemini re-ranking on top {self.gemini_reranker.top_n} matches...")
                    try:
                        matches, rerank_perf = self.gemini_reranker.rerank_matches(
                            matches=matches,
                            resume_skills=resume.skills or [],
                            experience_years=resume.experience_years or 0,
                            resume_domains=resume.domains or []
                        )
                        # Store detailed re-ranking performance stats
                        perf_stats['stages']['gemini_rerank'] = rerank_perf.get('total_time', 0)
                        perf_stats['gemini_rerank_details'] = {
                            'jobs_evaluated': rerank_perf.get('jobs_evaluated', 0),
                            'jobs_skipped': rerank_perf.get('jobs_skipped', 0),
                            'avg_eval_time': rerank_perf.get('avg_eval_time', 0),
                            'evaluation_times': rerank_perf.get('evaluation_times', [])
                        }
                        logger.info(f"[Stage 4a] Gemini re-ranking: {rerank_perf.get('jobs_evaluated', 0)} jobs in {rerank_perf.get('total_time', 0)}s (avg: {rerank_perf.get('avg_eval_time', 0)}s/job)")
                    except Exception as rerank_error:
                        logger.warning(f"[Stage 4a] Gemini re-ranking failed: {rerank_error}", exc_info=True)
                        perf_stats['stages']['gemini_rerank'] = 0

                if matches:
                    logger.info(f"Found {len(matches)} matches")

                    # Save match results to database for Telegram bot and tracking
                    try:
                        logger.info("Saving match results to database...")
                        saved_results = self.matcher.save_match_results(
                            db_session=db_session,
                            resume_id=resume.id,
                            match_results=matches
                        )
                        db_session.commit()
                        logger.info(f"Saved {len(saved_results)} match results to database")
                    except Exception as save_error:
                        logger.error(f"[Stage 4] WARNING: Failed to save match results: {save_error}", exc_info=True)
                        db_session.rollback()

                    all_matches.extend(matches)
                    logger.info(f"[Stage 4] SUCCESS: Matched {len(matches)} jobs")
                else:
                    logger.info("[Stage 4] SUCCESS: No matches found (all jobs below threshold)")

            finally:
                db_session.close()

        except Exception as e:
            logger.error(f"[Stage 4] FAILED: Matching error: {e}", exc_info=True)
            logger.warning("[Stage 4] Continuing to next stages...")
        perf_stats['stages']['matching'] = time_module.perf_counter() - stage_start
        perf_stats['matches_found'] = len(all_matches)

        # If no matches, exit gracefully
        if not all_matches:
            logger.info("\nNo matches found across all searches")
            self.stats['successful_runs'] += 1
            self.stats['last_success'] = datetime.now()
            return self._finalize_perf_stats(perf_stats)

        # Sort by blended score (AI + NLP weighted)
        ai_weight = self.config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
        nlp_weight = self.config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

        def get_blended_score(match):
            nlp_score = match.get('overall_score', 0)
            ai_score = match.get('gemini_score')
            if ai_score is not None:
                return (ai_score * ai_weight) + (nlp_score * nlp_weight)
            return nlp_score  # Fall back to NLP if no AI score

        all_matches.sort(key=get_blended_score, reverse=True)
        logger.info(f"\nTotal matches: {len(all_matches)}")
        top_blended = int(get_blended_score(all_matches[0]) * 100)
        logger.info(f"Top match: {all_matches[0]['job_title']} - {top_blended}% (blended)")

        # ========================================================================
        # STAGE 5: Google Sheets Export (Non-critical - continue if fails)
        # ========================================================================
        stage_start = time_module.perf_counter()
        logger.info("[Stage 5/6] Exporting to Google Sheets...")
        if self.sheets_connector.enabled and self.sheets_connector.auto_export:
            try:
                # Clean up old entries before exporting new matches
                logger.info("Cleaning up entries older than 7 days...")
                try:
                    cleanup_result = self.sheets_connector.cleanup_old_matches(days=7)
                    if cleanup_result['success']:
                        if cleanup_result['deleted_count'] > 0:
                            logger.info(f"Cleaned up {cleanup_result['deleted_count']} old entries")
                        else:
                            logger.info("No old entries to clean up")
                    else:
                        logger.warning(f"Cleanup warning: {cleanup_result['message']}")
                except Exception as cleanup_error:
                    logger.warning(f"[Stage 5] Cleanup failed (non-critical): {cleanup_error}")

                # Export high-quality matches
                exported_count = self.sheets_connector.export_matches_batch(all_matches)
                logger.info(f"Exported {exported_count} matches to Google Sheets")

                # Log ALL jobs to "Logs" sheet for analysis
                logger.info("Logging all jobs to 'Logs' sheet...")
                logged_count = self.sheets_connector.log_all_jobs_to_sheets(all_matches, sheet_name="Logs")
                logger.info(f"[Stage 5] SUCCESS: Logged {logged_count} jobs to 'Logs' sheet")

            except Exception as e:
                logger.error(f"[Stage 5] FAILED: Google Sheets export error: {e}", exc_info=True)
                logger.warning("[Stage 5] Continuing without Sheets export...")
        else:
            logger.info("[Stage 5] SKIPPED: Google Sheets export disabled")
        perf_stats['stages']['sheets'] = time_module.perf_counter() - stage_start

        # ========================================================================
        # STAGE 6: Telegram Notifications (Non-critical - continue if fails)
        # ========================================================================
        stage_start = time_module.perf_counter()
        logger.info("[Stage 6/6] Sending Telegram notifications...")
        if self.muted:
            logger.info("[Stage 6] SKIPPED: Notifications muted")
        elif not self.notify_on_new_matches:
            logger.info("[Stage 6] SKIPPED: Notifications disabled")
        elif not self.telegram_notify_callback:
            logger.info("[Stage 6] SKIPPED: No Telegram callback registered")
        else:
            try:
                self._send_telegram_notification()
                logger.info("[Stage 6] SUCCESS: Telegram notification sent")
            except Exception as e:
                logger.error(f"[Stage 6] FAILED: Telegram notification error: {e}", exc_info=True)
                logger.warning("[Stage 6] Continuing without notification...")
        perf_stats['stages']['notify'] = time_module.perf_counter() - stage_start

        # ========================================================================
        # COMPLETION
        # ========================================================================
        self.stats['successful_runs'] += 1
        self.stats['last_success'] = datetime.now()

        perf_stats = self._finalize_perf_stats(perf_stats)

        logger.info("\n" + "=" * 80)
        logger.info("Scheduled job search completed successfully")
        if perf_stats and perf_stats['enabled']:
            logger.info(f"Total time: {perf_stats['total']:.1f}s")
        logger.info("=" * 80)

        return perf_stats

    def _finalize_perf_stats(self, perf_stats: Dict) -> Optional[Dict]:
        """Finalize performance stats by calculating total time.

        Args:
            perf_stats: Dict with timing data

        Returns:
            Finalized perf_stats dict if enabled, None otherwise
        """
        if not perf_stats.get('enabled'):
            return None

        perf_stats['total'] = time_module.perf_counter() - perf_stats['total_start']
        del perf_stats['total_start']  # Remove internal tracking field
        return perf_stats

    def _send_telegram_notification(self):
        """Send Telegram push notification for new unnotified matches."""
        try:
            session = SessionLocal()
            try:
                # Get unnotified matches with score >= 70%
                unnotified_matches = crud.get_unnotified_matches(session, min_score=70.0)

                if not unnotified_matches:
                    logger.info("No new matches to notify about")
                    return

                # Build notification message
                message = f"🔔 *New Job Matches Found!*\n\n"
                message += f"Found {len(unnotified_matches)} new matches:\n\n"

                # Show top 5 matches
                for match in unnotified_matches[:5]:
                    score_pct = int(match.match_score)
                    emoji = "🔥" if score_pct >= 85 else "✨" if score_pct >= 75 else "⭐"

                    job = match.job_posting

                    # Format job freshness (posting age)
                    freshness = self._format_job_freshness(job.posting_date, job.import_date)

                    if job.url:
                        message += f"{emoji} [{job.title}]({job.url})\n"
                    else:
                        message += f"{emoji} {job.title}\n"
                    message += f"   📍 {job.company}\n"
                    message += f"   📊 Score: {score_pct}%"
                    if freshness:
                        message += f" | {freshness}"
                    if job.salary:
                        message += f"\n   💰 {job.salary}"
                    message += "\n\n"

                if len(unnotified_matches) > 5:
                    message += f"_...and {len(unnotified_matches) - 5} more matches_\n\n"

                message += "📊 Check Google Sheets for full details"

                # Send notification via callback
                if self.telegram_notify_callback:
                    self.telegram_notify_callback(message)
                    logger.info(f"Sent Telegram notification for {len(unnotified_matches)} new matches")

                # Mark matches as notified
                match_ids = [m.id for m in unnotified_matches]
                crud.mark_matches_as_notified(session, match_ids)
                logger.info(f"Marked {len(match_ids)} matches as notified")

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", exc_info=True)

    def _format_job_freshness(self, posting_date, import_date=None) -> str:
        """Format job posting age as human-readable string with freshness indicator.

        Uses posting_date if available, otherwise falls back to import_date.
        Adds ⏰ indicator for jobs older than 2 days (considered "stale").

        Args:
            posting_date: When the job was posted on LinkedIn (can be None)
            import_date: When the job was imported to our database (fallback)

        Returns:
            Formatted string like "🕐 today", "🕐 1d ago", "⏰ 5d ago"
        """
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

        # Format the age string (shorter format for inline display)
        if days == 0:
            return f"{emoji} today"
        elif days == 1:
            return f"{emoji} 1d ago"
        else:
            return f"{emoji} {days}d ago"

    def set_telegram_callback(self, callback: Callable):
        """Set the callback function for sending Telegram notifications.

        Args:
            callback: Async function that accepts a message string
        """
        self.telegram_notify_callback = callback
        logger.info("Telegram notification callback registered")

    def run_now(self, custom_keywords=None) -> Optional[Dict]:
        """Run a job search immediately (outside of schedule).

        Args:
            custom_keywords: Optional list of keywords to override config

        Returns:
            Dict with performance stats if tracking enabled, None otherwise
        """
        logger.info("Running immediate job search (outside of schedule)")
        return self.run_scheduled_search(custom_keywords=custom_keywords)

    def get_status(self) -> Dict:
        """Get scheduler status and statistics.

        Returns:
            Dict: Scheduler status information
        """
        scheduled_times = self.get_scheduled_times()

        return {
            'enabled': self.enabled,
            'interval_hours': self.interval_hours,
            'start_time': self.start_time_str,
            'end_time': self.end_time_str,
            'scheduled_times': scheduled_times,
            'active_profile': self.active_profile,
            'available_profiles': list(self.profiles.keys()),
            'search_keyword': self.search_keyword,
            'search_location': self.search_location,
            'muted': self.muted,
            'stats': self.stats,
        }

    def update_schedule(self, interval_hours: int = None, start_time: str = None,
                        end_time: str = None, enabled: bool = None) -> Dict:
        """Update schedule settings in config.

        Note: Actual scheduling is handled by Telegram's JobQueue. This method
        only updates the config values.

        Args:
            interval_hours: New interval in hours (e.g., 4, 6, 8)
            start_time: New start time (HH:MM format)
            end_time: New end time (HH:MM format)
            enabled: Enable or disable scheduling

        Returns:
            Dict with update status and new settings
        """
        changes = []

        if interval_hours is not None:
            self.interval_hours = interval_hours
            self.config.set("scheduling.interval_hours", interval_hours)
            changes.append(f"interval: {interval_hours}h")

        if start_time is not None:
            self.start_time_str = start_time
            self.config.set("scheduling.start_time", start_time)
            changes.append(f"start: {start_time}")

        if end_time is not None:
            self.end_time_str = end_time
            self.config.set("scheduling.end_time", end_time)
            changes.append(f"end: {end_time}")

        if enabled is not None:
            self.enabled = enabled
            self.config.set("scheduling.enabled", enabled)
            changes.append(f"enabled: {enabled}")

        # Save config changes
        self.config.save()

        return {
            'success': True,
            'changes': changes,
            'new_settings': {
                'enabled': self.enabled,
                'interval_hours': self.interval_hours,
                'start_time': self.start_time_str,
                'end_time': self.end_time_str,
                'scheduled_times': self.get_scheduled_times()
            }
        }

    def _get_profile_keyword(self, profile_name: str) -> str:
        """Get keyword for a specific profile (single keyword per profile)."""
        if profile_name in self.profiles:
            # Support both 'keyword' (new) and 'keywords' (legacy) formats
            profile = self.profiles[profile_name]
            if 'keyword' in profile:
                return profile['keyword']
            elif 'keywords' in profile and profile['keywords']:
                return profile['keywords'][0]  # Take first keyword for backwards compatibility
        return "Product Manager"

    def get_profiles(self) -> Dict:
        """Get all available profiles and their keywords."""
        return {
            'active_profile': self.active_profile,
            'profiles': self.profiles
        }

    def set_active_profile(self, profile_name: str) -> Dict:
        """Set the active keyword profile."""
        if profile_name not in self.profiles:
            return {
                'success': False,
                'error': f"Profile '{profile_name}' not found",
                'available_profiles': list(self.profiles.keys())
            }
        self.active_profile = profile_name
        self.search_keyword = self._get_profile_keyword(profile_name)
        self.config.set("scheduling.active_profile", profile_name)
        self.config.save()
        logger.info(f"Switched to profile '{profile_name}' with keyword: {self.search_keyword}")
        return {
            'success': True,
            'active_profile': profile_name,
            'keyword': self.search_keyword
        }

    def create_profile(self, profile_name: str, keyword: str) -> Dict:
        """Create a new keyword profile (single keyword per profile)."""
        if not profile_name or not keyword:
            return {'success': False, 'error': "Profile name and keyword are required"}
        self.profiles[profile_name] = {'keyword': keyword}
        self.config.set(f"scheduling.profiles.{profile_name}", {'keyword': keyword})
        self.config.save()
        logger.info(f"Created profile '{profile_name}' with keyword: {keyword}")
        return {'success': True, 'profile_name': profile_name, 'keyword': keyword}

    def delete_profile(self, profile_name: str) -> Dict:
        """Delete a keyword profile."""
        if profile_name not in self.profiles:
            return {'success': False, 'error': f"Profile '{profile_name}' not found"}
        if profile_name == self.active_profile:
            return {'success': False, 'error': "Cannot delete the active profile. Switch to another profile first."}
        del self.profiles[profile_name]
        self.config.set("scheduling.profiles", self.profiles)
        self.config.save()
        logger.info(f"Deleted profile '{profile_name}'")
        return {'success': True, 'deleted_profile': profile_name, 'remaining_profiles': list(self.profiles.keys())}

    def toggle_mute(self) -> Dict:
        """Toggle notification mute status."""
        self.muted = not self.muted
        self.config.set("scheduling.muted", self.muted)
        self.config.save()
        status = "muted" if self.muted else "unmuted"
        logger.info(f"Notifications {status}")
        return {'success': True, 'muted': self.muted}
