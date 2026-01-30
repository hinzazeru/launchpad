"""Web App Scheduler Service.

APScheduler-based service for running scheduled job searches.
Integrates with the existing search pipeline and tracks trigger source.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from src.database.db import SessionLocal
from src.database.models import ScheduledSearch, SearchPerformance

logger = logging.getLogger(__name__)


class WebAppScheduler:
    """Scheduler service for automated job searches.
    
    Uses APScheduler with AsyncIO scheduler for FastAPI compatibility.
    Schedules are loaded from the database at startup.
    """
    
    def __init__(self):
        """Initialize the scheduler with memory job store."""
        self._scheduler = AsyncIOScheduler(
            jobstores={'default': MemoryJobStore()},
            job_defaults={
                'max_instances': 1,  # Prevent overlapping runs
                'coalesce': True,    # Combine missed runs
                'misfire_grace_time': 300  # 5 minute grace period
            },
            timezone=ZoneInfo('America/Toronto')
        )
        self._running = False
    
    @property
    def running(self) -> bool:
        """Check if scheduler is running."""
        return self._running and self._scheduler.running
    
    def start(self) -> None:
        """Start the scheduler."""
        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("WebAppScheduler started")
    
    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("WebAppScheduler stopped")
    
    def load_schedules_from_db(self) -> int:
        """Load all enabled schedules from database and register jobs.
        
        Should be called at application startup.
        
        Returns:
            Number of schedules loaded
        """
        db = SessionLocal()
        try:
            schedules = db.query(ScheduledSearch).filter(
                ScheduledSearch.enabled == True
            ).all()
            
            loaded = 0
            for schedule in schedules:
                try:
                    self._register_schedule_jobs(schedule)
                    loaded += 1
                except Exception as e:
                    logger.error(f"Failed to load schedule {schedule.id}: {e}")
            
            logger.info(f"Loaded {loaded} schedules from database")
            return loaded
        finally:
            db.close()
    
    def add_schedule(self, schedule: ScheduledSearch) -> None:
        """Add a new schedule to the scheduler.
        
        Args:
            schedule: ScheduledSearch model instance
        """
        if not schedule.enabled:
            logger.debug(f"Schedule {schedule.id} is disabled, skipping registration")
            return
        
        self._register_schedule_jobs(schedule)
        logger.info(f"Added schedule '{schedule.name}' (id={schedule.id}) with {len(schedule.run_times or [])} daily times")
    
    def remove_schedule(self, schedule_id: int) -> None:
        """Remove a schedule from the scheduler.
        
        Args:
            schedule_id: ID of the schedule to remove
        """
        # Remove all jobs for this schedule (one per run_time)
        removed = 0
        for job in self._scheduler.get_jobs():
            if job.id.startswith(f"schedule_{schedule_id}_"):
                job.remove()
                removed += 1
        
        if removed > 0:
            logger.info(f"Removed {removed} jobs for schedule {schedule_id}")
        else:
            logger.debug(f"No jobs found for schedule {schedule_id}")
    
    def update_schedule(self, schedule: ScheduledSearch) -> None:
        """Update an existing schedule in the scheduler.
        
        Removes old jobs and adds new ones based on updated config.
        
        Args:
            schedule: Updated ScheduledSearch model instance
        """
        self.remove_schedule(schedule.id)
        if schedule.enabled:
            self.add_schedule(schedule)
    
    def _register_schedule_jobs(self, schedule: ScheduledSearch) -> None:
        """Register APScheduler jobs for a schedule.
        
        Creates one job per run_time in the schedule.
        
        Args:
            schedule: ScheduledSearch model instance
        """
        tz = ZoneInfo(schedule.timezone or 'America/Toronto')
        run_times = schedule.run_times or ["08:00", "12:00", "16:00", "20:00"]
        
        for time_str in run_times:
            hour, minute = map(int, time_str.split(':'))
            job_id = f"schedule_{schedule.id}_{time_str.replace(':', '')}"
            
            # Remove existing job if present
            existing = self._scheduler.get_job(job_id)
            if existing:
                existing.remove()
            
            # Add new job with cron trigger
            self._scheduler.add_job(
                func=self.execute_scheduled_search,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
                id=job_id,
                args=[schedule.id],
                name=f"{schedule.name} @ {time_str}"
            )
        
        # Update next_run_at in database
        self._update_next_run(schedule.id)
    
    async def execute_scheduled_search(self, schedule_id: int) -> Dict[str, Any]:
        """Execute a scheduled search.
        
        Runs the full search pipeline and records metrics with trigger_source='scheduled'.
        
        Args:
            schedule_id: ID of the schedule to execute
            
        Returns:
            Dict with search results or error info
        """
        db = SessionLocal()
        result = {'success': False, 'schedule_id': schedule_id}
        
        try:
            # Get schedule from database
            schedule = db.query(ScheduledSearch).filter(
                ScheduledSearch.id == schedule_id
            ).first()
            
            if not schedule:
                logger.error(f"Schedule {schedule_id} not found")
                result['error'] = 'Schedule not found'
                return result
            
            if not schedule.enabled:
                logger.info(f"Schedule {schedule_id} is disabled, skipping execution")
                result['error'] = 'Schedule is disabled'
                return result
            
            logger.info(f"Executing scheduled search: '{schedule.name}' (id={schedule_id})")
            
            # Update last_run_at
            schedule.last_run_at = datetime.utcnow()
            db.commit()
            
            # Execute the search pipeline
            search_result = await self._run_search_pipeline(
                db=db,
                schedule=schedule
            )
            
            # Update schedule status
            schedule.last_run_status = 'success' if search_result.get('success') else 'error'
            self._update_next_run(schedule_id, db)
            db.commit()
            
            # Send Telegram notification if configured
            if search_result.get('success'):
                await self._send_notification(schedule, search_result)
            
            result = search_result
            result['success'] = True
            
        except Exception as e:
            logger.error(f"Scheduled search {schedule_id} failed: {e}", exc_info=True)
            result['error'] = str(e)
            
            # Update status to error
            try:
                schedule = db.query(ScheduledSearch).filter(
                    ScheduledSearch.id == schedule_id
                ).first()
                if schedule:
                    schedule.last_run_status = 'error'
                    db.commit()
            except Exception:
                db.rollback()
        finally:
            db.close()
        
        return result
    
    async def _run_search_pipeline(
        self,
        db: Session,
        schedule: ScheduledSearch
    ) -> Dict[str, Any]:
        """Run the job search pipeline for a scheduled search.
        
        This is a non-streaming version of the search pipeline from search.py.
        
        Args:
            db: Database session
            schedule: ScheduledSearch model
            
        Returns:
            Dict with search results
        """
        import time as time_module
        import re
        from datetime import timedelta
        from pathlib import Path
        from sqlalchemy import or_
        
        from src.config import get_config
        from src.database.models import Resume, JobPosting, MatchResult
        from src.importers.api_importer import ApifyJobImporter
        from src.matching.engine import JobMatcher
        from src.integrations.gemini_client import get_gemini_reranker
        from src.resume.parser import ResumeParser
        from src.services.performance_logger import PerformanceLogger
        
        start_time = time_module.perf_counter()
        config = get_config()
        perf_logger = PerformanceLogger()
        
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        RESUME_LIBRARY_DIR = PROJECT_ROOT / "data" / "resumes"
        
        result = {
            'success': False,
            'jobs_fetched': 0,
            'jobs_imported': 0,
            'jobs_matched': 0,
            'high_matches': 0,
            'top_matches': []
        }
        
        try:
            # ====================================================================
            # STAGE 1: Initialize - Load resume
            # ====================================================================
            with perf_logger.time('initialize'):
                file_path = RESUME_LIBRARY_DIR / schedule.resume_filename
                if not file_path.exists():
                    raise FileNotFoundError(f"Resume not found: {schedule.resume_filename}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    resume_content = f.read()
                
                parser = ResumeParser()
                parsed = parser.parse_auto(resume_content)
                
                # Extract skills
                flat_skills = []
                for category_skills in parsed.skills.values():
                    flat_skills.extend(category_skills)
                
                # Estimate experience years
                experience_years = 0.0
                for role in parsed.roles:
                    duration = role.duration.lower()
                    year_match = re.findall(r'20\d{2}', duration)
                    if len(year_match) >= 2:
                        try:
                            years = int(year_match[-1]) - int(year_match[0])
                            experience_years += max(0, years)
                        except:
                            pass
                    elif 'year' in duration:
                        num_match = re.search(r'(\d+)', duration)
                        if num_match:
                            experience_years += float(num_match.group(1))
                
                class ParsedResume:
                    def __init__(self, skills, experience_years, domains=None):
                        self.id = 0
                        self.skills = skills
                        self.experience_years = experience_years
                        self.domains = domains or []
                
                resume = ParsedResume(flat_skills, experience_years, [])
                logger.info(f"Parsed resume: {len(flat_skills)} skills, {experience_years} years")
            
            # ====================================================================
            # STAGE 2: Fetch jobs from Apify
            # ====================================================================
            with perf_logger.time('fetch'):
                keyword = schedule.keyword.strip()
                is_remote_search = keyword.lower().endswith("remote")
                
                if is_remote_search:
                    actual_keyword = keyword[:-6].strip()
                    search_location = "United States"
                    work_arrangement = "Remote"
                else:
                    actual_keyword = keyword
                    search_location = schedule.location or "Canada"
                    work_arrangement = schedule.work_arrangement
                
                importer = ApifyJobImporter()
                jobs = await importer.search_jobs_async(
                    keywords=actual_keyword,
                    location=search_location,
                    job_type=schedule.job_type,
                    max_results=schedule.max_results or 25,
                    experience_level=schedule.experience_level,
                    work_arrangement=work_arrangement,
                    split_calls=True
                )
                
                result['jobs_fetched'] = len(jobs) if jobs else 0
                
                if not jobs:
                    logger.info(f"No jobs found for scheduled search '{schedule.name}'")
                    result['success'] = True
                    return result
            
            # ====================================================================
            # STAGE 3: Import jobs to database
            # ====================================================================
            with perf_logger.time('import'):
                jobs_imported = importer.import_jobs(jobs)
                result['jobs_imported'] = jobs_imported
            
            # ====================================================================
            # STAGE 4: Match jobs against resume
            # ====================================================================
            with perf_logger.time('match'):
                # Query matching jobs
                query = db.query(JobPosting).filter(
                    JobPosting.title.ilike(f"%{actual_keyword}%")
                )
                
                is_remote_request = is_remote_search or work_arrangement == "Remote"
                if not is_remote_request and search_location:
                    location_filter = search_location.split(',')[-1].strip()
                    query = query.filter(JobPosting.location.ilike(f"%{location_filter}%"))
                
                max_job_age_days = config.get("matching.max_job_age_days", 7)
                if max_job_age_days and max_job_age_days > 0:
                    cutoff_date = datetime.now() - timedelta(days=max_job_age_days)
                    query = query.filter(
                        or_(
                            JobPosting.posting_date >= cutoff_date,
                            (JobPosting.posting_date.is_(None)) & (JobPosting.import_date >= cutoff_date)
                        )
                    )
                
                all_jobs = query.all()
                
                # Filter low-quality jobs
                min_description_length = 200
                all_jobs = [j for j in all_jobs if j.description and len(j.description) >= min_description_length]
                
                # Deduplicate
                seen_jobs = {}
                for job in all_jobs:
                    dedup_key = (job.title.strip().lower(), job.company.strip().lower())
                    if dedup_key not in seen_jobs or (job.posting_date and (
                        not seen_jobs[dedup_key].posting_date or
                        job.posting_date > seen_jobs[dedup_key].posting_date
                    )):
                        seen_jobs[dedup_key] = job
                all_jobs = list(seen_jobs.values())
                
                # Run matching
                matcher = JobMatcher()
                matches = matcher.match_jobs(resume, all_jobs, min_score=0.0)
                
                # Gemini re-ranking
                gemini_reranker = get_gemini_reranker()
                if matches and gemini_reranker and gemini_reranker.is_available():
                    try:
                        with perf_logger.time('gemini_rerank'):
                            matches, _ = gemini_reranker.rerank_matches(
                                matches=matches,
                                resume_skills=resume.skills or [],
                                experience_years=resume.experience_years or 0,
                                resume_domains=resume.domains or []
                            )
                        perf_logger.record_count('gemini_calls', 1)
                    except Exception as e:
                        logger.warning(f"Gemini re-ranking failed: {e}")
                
                # Save match results
                resume_id_for_save = resume.id
                if resume_id_for_save == 0:
                    db_resume = db.query(Resume).first()
                    if db_resume:
                        resume_id_for_save = db_resume.id
                
                if matches and resume_id_for_save > 0:
                    try:
                        matcher.save_match_results(
                            db_session=db,
                            resume_id=resume_id_for_save,
                            match_results=matches
                        )
                        db.commit()
                    except Exception as e:
                        logger.warning(f"Failed to save matches: {e}")
                        db.rollback()
                
                # Sort by blended score
                ai_weight = config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
                nlp_weight = config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)
                
                def get_blended_score(match):
                    nlp_score = match.get('overall_score', 0)
                    ai_score = match.get('gemini_score')
                    if ai_score is not None:
                        return (ai_score * ai_weight) + (nlp_score * nlp_weight)
                    return nlp_score
                
                matches.sort(key=get_blended_score, reverse=True)
                
                result['jobs_matched'] = len(matches)
                result['high_matches'] = len([m for m in matches if get_blended_score(m) >= 0.70])
                result['top_matches'] = [
                    {
                        'title': m.get('job_title', 'Unknown'),
                        'company': m.get('company', 'Unknown'),
                        'score': round(get_blended_score(m) * 100, 1)
                    }
                    for m in matches[:5]
                ]
            
            # ====================================================================
            # STAGE 5: Export to Google Sheets
            # ====================================================================
            if schedule.export_to_sheets and matches:
                with perf_logger.time('export'):
                    try:
                        from src.integrations.sheets_connector import SheetsConnector
                        sheets = SheetsConnector()
                        
                        if sheets.enabled:
                            sheets.cleanup_old_matches(days=7)
                            result['exported_count'] = sheets.export_matches_batch(matches)
                    except Exception as e:
                        logger.warning(f"Sheets export failed: {e}")
            
            # Record performance metrics with trigger_source
            duration = time_module.perf_counter() - start_time
            perf_logger.record_count('jobs_fetched', result['jobs_fetched'])
            perf_logger.record_count('jobs_imported', result['jobs_imported'])
            perf_logger.record_count('jobs_matched', result['jobs_matched'])
            perf_logger.record_count('high_matches', result['high_matches'])
            
            perf_logger.save(
                db,
                status='success',
                trigger_source='scheduled',
                schedule_id=schedule.id
            )
            
            result['success'] = True
            result['duration_seconds'] = round(duration, 1)
            
            logger.info(
                f"Scheduled search '{schedule.name}' complete: "
                f"{result['jobs_matched']} matches, {result['high_matches']} high quality"
            )
            
        except Exception as e:
            logger.error(f"Search pipeline failed: {e}", exc_info=True)
            result['error'] = str(e)
            
            # Record failed performance metrics
            try:
                perf_logger.save(
                    db,
                    status='error',
                    trigger_source='scheduled',
                    schedule_id=schedule.id,
                    error_stage='pipeline',
                    error_message=str(e)
                )
            except Exception:
                pass
        
        return result
    
    async def _send_notification(
        self,
        schedule: ScheduledSearch,
        result: Dict[str, Any]
    ) -> None:
        """Send Telegram notification for completed scheduled search.
        
        Args:
            schedule: The schedule that was executed
            result: Search results dict
        """
        try:
            from src.config import get_config
            config = get_config()
            
            # Check if Telegram is configured
            bot_token = config.get("telegram.bot_token")
            chat_id = config.get("telegram.chat_id")
            
            if not bot_token or not chat_id:
                return
            
            # Build notification message
            high_matches = result.get('high_matches', 0)
            top_matches = result.get('top_matches', [])
            
            if high_matches == 0:
                return  # Don't notify if no high-quality matches
            
            message_lines = [
                f"🔔 Scheduled Search Complete: \"{schedule.name}\"",
                "",
                f"Found {high_matches} high-quality matches (70%+):"
            ]
            
            for i, match in enumerate(top_matches[:3], 1):
                title = match.get('title', 'Unknown')
                company = match.get('company', 'Unknown')
                score = match.get('score', 0)
                message_lines.append(f"{i}. {title} @ {company} ({score}%)")
            
            webapp_url = config.get("webapp.url", "http://localhost:5173")
            message_lines.extend([
                "",
                f"View in Job Matches: {webapp_url}/matches"
            ])
            
            message = "\n".join(message_lines)
            
            # Send via Telegram API
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                await session.post(url, json={
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                })
            
            logger.info(f"Sent Telegram notification for schedule '{schedule.name}'")
            
        except Exception as e:
            logger.warning(f"Failed to send Telegram notification: {e}")
    
    def _update_next_run(self, schedule_id: int, db: Optional[Session] = None) -> None:
        """Calculate and update the next_run_at for a schedule.
        
        Args:
            schedule_id: Schedule ID to update
            db: Optional database session (creates new one if not provided)
        """
        close_db = db is None
        if db is None:
            db = SessionLocal()
        
        try:
            schedule = db.query(ScheduledSearch).filter(
                ScheduledSearch.id == schedule_id
            ).first()
            
            if not schedule:
                return
            
            # Find next run from APScheduler jobs
            next_run = None
            for job in self._scheduler.get_jobs():
                if job.id.startswith(f"schedule_{schedule_id}_"):
                    if job.next_run_time:
                        if next_run is None or job.next_run_time < next_run:
                            next_run = job.next_run_time
            
            schedule.next_run_at = next_run
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update next_run_at: {e}")
            db.rollback()
        finally:
            if close_db:
                db.close()
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status.
        
        Returns:
            Dict with scheduler status info
        """
        jobs = self._scheduler.get_jobs()
        
        # Find next job across all schedules
        next_run = None
        next_schedule_name = None
        for job in jobs:
            if job.next_run_time:
                if next_run is None or job.next_run_time < next_run:
                    next_run = job.next_run_time
                    next_schedule_name = job.name
        
        return {
            'running': self.running,
            'active_schedules': len(set(
                j.id.split('_')[1] for j in jobs if j.id.startswith('schedule_')
            )),
            'total_jobs': len(jobs),
            'next_run_at': next_run.isoformat() if next_run else None,
            'next_schedule_name': next_schedule_name
        }
    
    async def trigger_now(self, schedule_id: int) -> Dict[str, Any]:
        """Trigger an immediate run of a schedule.
        
        Args:
            schedule_id: ID of schedule to run
            
        Returns:
            Dict with run status
        """
        import uuid
        search_id = str(uuid.uuid4())
        
        logger.info(f"Triggering immediate run for schedule {schedule_id}")
        result = await self.execute_scheduled_search(schedule_id)
        result['search_id'] = search_id
        
        return result


# Global scheduler instance
_scheduler: Optional[WebAppScheduler] = None


def get_scheduler() -> WebAppScheduler:
    """Get the global scheduler instance.
    
    Creates a new instance if one doesn't exist.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = WebAppScheduler()
    return _scheduler


def init_scheduler() -> WebAppScheduler:
    """Initialize and start the scheduler.
    
    Should be called at application startup.
    """
    scheduler = get_scheduler()
    scheduler.start()
    scheduler.load_schedules_from_db()
    return scheduler


def shutdown_scheduler() -> None:
    """Shutdown the scheduler.
    
    Should be called at application shutdown.
    """
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
