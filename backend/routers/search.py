"""Search router for Resume Targeter API.

Provides endpoints for triggering job searches with real-time progress via SSE.
"""

import json
import logging
import time as time_module
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_config
from src.database.db import SessionLocal
from src.database.models import Resume, JobPosting, MatchResult
from src.importers.api_importer import ApifyJobImporter
from src.matching.engine import JobMatcher
from src.integrations.gemini_client import get_gemini_reranker
from src.resume.parser import ResumeParser

logger = logging.getLogger(__name__)

router = APIRouter()

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
RESUME_LIBRARY_DIR = PROJECT_ROOT / "data" / "resumes"


def validate_path_within_directory(file_path: Path, base_dir: Path) -> None:
    """Ensure file_path is within base_dir (prevent path traversal attacks)."""
    if not file_path.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")


# Enums and Models

class SearchStage(str, Enum):
    """Stages of the job search pipeline."""
    INITIALIZING = "initializing"
    FETCHING = "fetching"
    IMPORTING = "importing"
    MATCHING = "matching"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    ERROR = "error"


class JobSearchRequest(BaseModel):
    """Request model for initiating a job search."""
    keyword: str = Field(..., min_length=1, max_length=200, description="Job title or keywords")
    location: str = Field(default="United States", description="Job location")
    job_type: Optional[str] = Field(default=None, description="Full-time, Part-time, Contract, etc.")
    experience_level: Optional[str] = Field(default=None, description="Entry level, Mid-Senior level, etc.")
    work_arrangement: Optional[str] = Field(default=None, description="Remote, Hybrid, On-site")
    max_results: int = Field(default=25, ge=1, le=100, description="Maximum jobs to fetch")
    resume_filename: str = Field(..., description="Resume filename from library")
    export_to_sheets: bool = Field(default=True, description="Export results to Google Sheets")


class SearchDefaults(BaseModel):
    """Default search parameters from config."""
    location: str
    max_results: int
    job_type: Optional[str]
    experience_level: Optional[str]
    work_arrangement: Optional[str]
    posted_when: str


class SearchProgress(BaseModel):
    """Progress update for SSE streaming."""
    stage: SearchStage
    progress: int  # 0-100
    message: str
    jobs_found: Optional[int] = None
    jobs_imported: Optional[int] = None
    matches_found: Optional[int] = None
    high_matches: Optional[int] = None
    exported_count: Optional[int] = None
    error: Optional[str] = None


class TopMatch(BaseModel):
    """A top matching job for results."""
    title: str
    company: str
    location: Optional[str]
    url: Optional[str]
    score: float
    gemini_score: Optional[float]


class SearchResult(BaseModel):
    """Final result of a job search."""
    success: bool
    jobs_fetched: int
    jobs_imported: int
    jobs_matched: int
    high_matches: int
    exported_to_sheets: int
    duration_seconds: float
    top_matches: List[TopMatch]
    fetched_jobs: List[TopMatch] = []
    sheets_url: Optional[str] = None


# Endpoints

@router.get("/defaults", response_model=SearchDefaults)
async def get_search_defaults():
    """Get default search parameters from config."""
    config = get_config()
    return SearchDefaults(
        location=config.get("search.default_location", "United States"),
        max_results=config.get("search.default_max_results", 50),
        job_type=config.get("search.default_job_type"),
        experience_level=config.get("search.default_experience_level"),
        work_arrangement=config.get("search.default_work_arrangement"),
        posted_when=config.get("search.default_posted_when", "Past 24 hours")
    )


@router.post("/jobs")
async def search_jobs(request: JobSearchRequest):
    """Execute job search pipeline with SSE progress streaming.

    Pipeline stages:
    1. INITIALIZING (0-10%): Validate inputs, load resume
    2. FETCHING (10-40%): Call Apify LinkedIn scraper
    3. IMPORTING (40-50%): Save jobs to database
    4. MATCHING (50-80%): Run NLP matching + Gemini rerank
    5. EXPORTING (80-95%): Export to Google Sheets
    6. COMPLETED (100%): Return final results
    """

    async def generate_progress() -> AsyncGenerator[str, None]:
        """Async generator that yields SSE events during pipeline execution."""
        start_time = time_module.perf_counter()
        config = get_config()

        def send_progress(progress: SearchProgress) -> str:
            return f"data: {progress.model_dump_json()}\n\n"

        from src.services.performance_logger import PerformanceLogger
        perf_logger = PerformanceLogger()
        
        # ====================================================================
        # STAGE 1: Initialize (0-10%)
        # ====================================================================
        init_timer = perf_logger.time('initialize')
        init_timer.__enter__()
        
        yield send_progress(SearchProgress(
            stage=SearchStage.INITIALIZING,
            progress=0,
            message="Starting search..."
        ))

        # Validate resume file
        file_path = RESUME_LIBRARY_DIR / request.resume_filename
        try:
            validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)
        except HTTPException:
            yield send_progress(SearchProgress(
                stage=SearchStage.ERROR,
                progress=0,
                message="Invalid resume path",
                error="Access denied - invalid resume path"
            ))
            return

        if not file_path.exists():
            yield send_progress(SearchProgress(
                stage=SearchStage.ERROR,
                progress=0,
                message="Resume not found",
                error=f"Resume file not found: {request.resume_filename}"
            ))
            return

        # Load and parse resume from file
        yield send_progress(SearchProgress(
            stage=SearchStage.INITIALIZING,
            progress=5,
            message="Loading resume..."
        ))

        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                resume_content = f.read()

            # Parse the resume
            parser = ResumeParser()
            parsed = parser.parse_auto(resume_content)

            # Extract flat skills list from categorized skills dict
            flat_skills = []
            for category_skills in parsed.skills.values():
                flat_skills.extend(category_skills)

            # Estimate experience years from roles (count years from durations)
            experience_years = 0.0
            for role in parsed.roles:
                # Try to extract years from duration string like "2020 - 2023" or "3 years"
                duration = role.duration.lower()
                import re
                # Match year ranges like "2020 - 2023"
                year_match = re.findall(r'20\d{2}', duration)
                if len(year_match) >= 2:
                    try:
                        years = int(year_match[-1]) - int(year_match[0])
                        experience_years += max(0, years)
                    except:
                        pass
                # Match "X years" pattern
                elif 'year' in duration:
                    num_match = re.search(r'(\d+)', duration)
                    if num_match:
                        experience_years += float(num_match.group(1))

            # Create a Resume-like object for the matcher
            # Using a simple class that mimics the Resume model interface
            class ParsedResume:
                def __init__(self, skills, experience_years, domains=None):
                    self.id = 0  # Temporary ID
                    self.skills = skills
                    self.experience_years = experience_years
                    self.domains = domains or []

            resume = ParsedResume(
                skills=flat_skills,
                experience_years=experience_years,
                domains=[]  # Could extract from parsed data if available
            )

            logger.info(f"Parsed resume: {len(flat_skills)} skills, {experience_years} years experience")

        except Exception as e:
            logger.error(f"Failed to parse resume: {e}", exc_info=True)
            yield send_progress(SearchProgress(
                stage=SearchStage.ERROR,
                progress=5,
                message="Failed to parse resume",
                error=f"Could not parse resume file: {str(e)}"
            ))
            return

        yield send_progress(SearchProgress(
            stage=SearchStage.INITIALIZING,
            progress=10,
            message=f"Resume loaded: {len(flat_skills)} skills, {experience_years:.0f} years exp"
        ))

        init_timer.__exit__(None, None, None)

        # ====================================================================
        # STAGE 2: Fetch jobs from Apify (10-40%)
        # ====================================================================
        fetch_timer = perf_logger.time('fetch')
        fetch_timer.__enter__()
        
        yield send_progress(SearchProgress(
            stage=SearchStage.FETCHING,
            progress=15,
            message=f"Fetching jobs for '{request.keyword}'..."
        ))

        # Handle remote keyword suffix
        keyword = request.keyword.strip()
        is_remote_search = keyword.lower().endswith("remote")

        if is_remote_search:
            actual_keyword = keyword[:-6].strip()  # Remove "remote" suffix
            search_location = "United States"
            work_arrangement = "Remote"
        else:
            actual_keyword = keyword
            search_location = request.location
            work_arrangement = request.work_arrangement

        # Initialize jobs variable
        jobs = [] 
        importer = None
        
        try:
            importer = ApifyJobImporter()
            jobs = await importer.search_jobs_async(
                keywords=actual_keyword,
                location=search_location,
                job_type=request.job_type,
                max_results=request.max_results,
                experience_level=request.experience_level,
                work_arrangement=work_arrangement,
                split_calls=True  # Enable parallel execution
            )
        except Exception as e:
            logger.error(f"Apify fetch failed: {e}", exc_info=True)
            yield send_progress(SearchProgress(
                stage=SearchStage.ERROR,
                progress=15,
                message="Failed to fetch jobs",
                error=f"Apify API error: {str(e)}"
            ))
            return

        jobs_fetched = len(jobs) if jobs else 0

        if not jobs:
            yield send_progress(SearchProgress(
                stage=SearchStage.COMPLETED,
                progress=100,
                message="No jobs found matching criteria",
                jobs_found=0,
                jobs_imported=0,
                matches_found=0,
                high_matches=0,
                exported_count=0
            ))
            return

        yield send_progress(SearchProgress(
            stage=SearchStage.FETCHING,
            progress=40,
            message=f"Found {jobs_fetched} jobs",
            jobs_found=jobs_fetched
        ))

        fetch_timer.__exit__(None, None, None)

        # ====================================================================
        # STAGE 3: Import jobs to database (40-50%)
        # ====================================================================
        import_timer = perf_logger.time('import')
        import_timer.__enter__()
        
        yield send_progress(SearchProgress(
            stage=SearchStage.IMPORTING,
            progress=42,
            message="Importing jobs to database...",
            jobs_found=jobs_fetched
        ))

        jobs_imported = 0
        try:
            jobs_imported = importer.import_jobs(jobs)
        except Exception as e:
            logger.warning(f"Import failed (continuing): {e}")

        yield send_progress(SearchProgress(
            stage=SearchStage.IMPORTING,
            progress=50,
            message=f"Imported {jobs_imported} new jobs",
            jobs_found=jobs_fetched,
            jobs_imported=jobs_imported
        ))

        import_timer.__exit__(None, None, None)

        # ====================================================================
        # STAGE 4: Match jobs against resume (50-80%)
        # ====================================================================
        match_timer = perf_logger.time('match')
        match_timer.__enter__()
        
        yield send_progress(SearchProgress(
            stage=SearchStage.MATCHING,
            progress=52,
            message="Matching jobs against resume...",
            jobs_found=jobs_fetched,
            jobs_imported=jobs_imported
        ))

        all_matches = []
        try:
            db_session = SessionLocal()
            try:
                # Query jobs matching keyword and location
                query = db_session.query(JobPosting).filter(
                    JobPosting.title.ilike(f"%{actual_keyword}%")
                )

                # Apply location filter for non-remote searches
                # Skip location filter if user selected Remote (via keyword OR dropdown)
                is_remote_request = is_remote_search or work_arrangement == "Remote"
                if not is_remote_request and search_location:
                    location_filter = search_location.split(',')[-1].strip()
                    query = query.filter(JobPosting.location.ilike(f"%{location_filter}%"))

                # Apply freshness filter
                max_job_age_days = config.get("matching.max_job_age_days", 7)
                if max_job_age_days and max_job_age_days > 0:
                    from sqlalchemy import or_
                    cutoff_date = datetime.now() - timedelta(days=max_job_age_days)
                    query = query.filter(
                        or_(
                            JobPosting.posting_date >= cutoff_date,
                            (JobPosting.posting_date.is_(None)) & (JobPosting.import_date >= cutoff_date)
                        )
                    )

                all_jobs = query.all()

                # Filter out low-quality jobs (sparse descriptions)
                min_description_length = 200
                quality_jobs = [
                    job for job in all_jobs
                    if job.description and len(job.description) >= min_description_length
                ]
                filtered_count = len(all_jobs) - len(quality_jobs)
                if filtered_count > 0:
                    logger.info(f"Filtered {filtered_count} jobs with descriptions < {min_description_length} chars")
                all_jobs = quality_jobs

                # Deduplicate by (title, company) - keep the most recent posting
                seen_jobs = {}
                for job in all_jobs:
                    dedup_key = (job.title.strip().lower(), job.company.strip().lower())
                    if dedup_key not in seen_jobs or (job.posting_date and (
                        not seen_jobs[dedup_key].posting_date or
                        job.posting_date > seen_jobs[dedup_key].posting_date
                    )):
                        seen_jobs[dedup_key] = job
                deduped_count = len(all_jobs) - len(seen_jobs)
                if deduped_count > 0:
                    logger.info(f"Removed {deduped_count} duplicate jobs")
                all_jobs = list(seen_jobs.values())

                yield send_progress(SearchProgress(
                    stage=SearchStage.MATCHING,
                    progress=55,
                    message=f"Analyzing {len(all_jobs)} jobs...",
                    jobs_found=jobs_fetched,
                    jobs_imported=jobs_imported
                ))

                # Run matching
                matcher = JobMatcher()
                matches = matcher.match_jobs(resume, all_jobs, min_score=0.0)

                yield send_progress(SearchProgress(
                    stage=SearchStage.MATCHING,
                    progress=65,
                    message=f"Found {len(matches)} matches, running AI analysis...",
                    jobs_found=jobs_fetched,
                    jobs_imported=jobs_imported,
                    matches_found=len(matches)
                ))

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
                        perf_logger.record_api_call(
                            call_type='gemini_rerank',
                            duration_ms=perf_logger.timings.get('gemini_rerank', 0),
                            status='success',
                            tokens_used=None # Populate if available
                        )
                    except Exception as rerank_error:
                        logger.warning(f"Gemini re-ranking failed: {rerank_error}")
                        perf_logger.record_api_call(
                            call_type='gemini_rerank',
                            duration_ms=0,
                            status='error',
                            error_message=str(rerank_error)
                        )

                # Save match results to database
                # For file-based resumes (web app), use the first resume in DB as reference
                resume_id_for_save = resume.id
                if resume_id_for_save == 0:
                    # Get first resume from database for linking
                    db_resume = db_session.query(Resume).first()
                    if db_resume:
                        resume_id_for_save = db_resume.id

                if matches and resume_id_for_save > 0:
                    try:
                        matcher.save_match_results(
                            db_session=db_session,
                            resume_id=resume_id_for_save,
                            match_results=matches
                        )
                        db_session.commit()
                        logger.info(f"Saved {len(matches)} matches to database")
                    except Exception as save_error:
                        logger.warning(f"Failed to save matches: {save_error}")
                        db_session.rollback()

                all_matches = matches

            finally:
                db_session.close()

        except Exception as e:
            logger.error(f"Matching failed: {e}", exc_info=True)
            yield send_progress(SearchProgress(
                stage=SearchStage.ERROR,
                progress=65,
                message="Matching failed",
                error=str(e),
                jobs_found=jobs_fetched,
                jobs_imported=jobs_imported
            ))
            return

        # Sort by blended score
        ai_weight = config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
        nlp_weight = config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

        def get_blended_score(match):
            nlp_score = match.get('overall_score', 0)
            ai_score = match.get('gemini_score')
            if ai_score is not None:
                return (ai_score * ai_weight) + (nlp_score * nlp_weight)
            return nlp_score

        all_matches.sort(key=get_blended_score, reverse=True)

        # Count high matches (>=70%)
        high_matches = len([m for m in all_matches if get_blended_score(m) >= 0.70])

        yield send_progress(SearchProgress(
            stage=SearchStage.MATCHING,
            progress=80,
            message=f"Matching complete: {high_matches} high-quality matches",
            jobs_found=jobs_fetched,
            jobs_imported=jobs_imported,
            matches_found=len(all_matches),
            high_matches=high_matches
        ))

        match_timer.__exit__(None, None, None)

        # ====================================================================
        # STAGE 5: Export to Google Sheets (80-95%)
        # ====================================================================
        export_timer = perf_logger.time('export')
        export_timer.__enter__()
        
        exported_count = 0
        sheets_url = None

        if request.export_to_sheets and all_matches:
            yield send_progress(SearchProgress(
                stage=SearchStage.EXPORTING,
                progress=82,
                message="Exporting to Google Sheets...",
                jobs_found=jobs_fetched,
                jobs_imported=jobs_imported,
                matches_found=len(all_matches),
                high_matches=high_matches
            ))

            try:
                from src.integrations.sheets_connector import SheetsConnector
                sheets = SheetsConnector()

                if sheets.enabled:
                    # Cleanup old entries
                    try:
                        sheets.cleanup_old_matches(days=7)
                    except Exception:
                        pass

                    # Export matches
                    exported_count = sheets.export_matches_batch(all_matches)

                    # Get sheets URL
                    spreadsheet_id = config.get("sheets.spreadsheet_id")
                    if spreadsheet_id:
                        sheets_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

                    yield send_progress(SearchProgress(
                        stage=SearchStage.EXPORTING,
                        progress=95,
                        message=f"Exported {exported_count} matches to Sheets",
                        jobs_found=jobs_fetched,
                        jobs_imported=jobs_imported,
                        matches_found=len(all_matches),
                        high_matches=high_matches,
                        exported_count=exported_count
                    ))
                else:
                    yield send_progress(SearchProgress(
                        stage=SearchStage.EXPORTING,
                        progress=95,
                        message="Google Sheets not configured",
                        jobs_found=jobs_fetched,
                        jobs_imported=jobs_imported,
                        matches_found=len(all_matches),
                        high_matches=high_matches,
                        exported_count=0
                    ))

            except Exception as e:
                logger.warning(f"Sheets export failed: {e}")
                yield send_progress(SearchProgress(
                    stage=SearchStage.EXPORTING,
                    progress=95,
                    message=f"Sheets export failed: {str(e)}",
                    jobs_found=jobs_fetched,
                    jobs_imported=jobs_imported,
                    matches_found=len(all_matches),
                    high_matches=high_matches,
                    exported_count=0
                ))
        else:
            yield send_progress(SearchProgress(
                stage=SearchStage.EXPORTING,
                progress=95,
                message="Skipping Sheets export",
                jobs_found=jobs_fetched,
                jobs_imported=jobs_imported,
                matches_found=len(all_matches),
                high_matches=high_matches,
                exported_count=0
            ))

        export_timer.__exit__(None, None, None)

        # ====================================================================
        # STAGE 6: Complete (100%)
        # ====================================================================
        duration = time_module.perf_counter() - start_time

        # Build top matches
        top_matches = []
        for match in all_matches[:5]:
            top_matches.append(TopMatch(
                title=match.get('job_title', 'Unknown'),
                company=match.get('company', 'Unknown'),
                location=match.get('location'),
                url=match.get('url'),
                score=round(get_blended_score(match) * 100, 1),
                gemini_score=round(match.get('gemini_score', 0) * 100, 1) if match.get('gemini_score') else None
            ))

        # Build fetched jobs preview (top 20)
        fetched_jobs = []
        if jobs:
            try:
                # We reuse the importer (if available) to normalize raw jobs
                # If importer not available (e.g. error in fetch), jobs is likely empty anyway
                norm_importer = importer if importer else ApifyJobImporter()
                
                count = 0
                for job in jobs:
                        
                    try:
                        norm = norm_importer.normalize_apify_job(job)
                        fetched_jobs.append(TopMatch(
                            title=norm.get('title', 'Unknown'),
                            company=norm.get('company', 'Unknown'),
                            location=norm.get('location'),
                            url=norm.get('url'),
                            score=0.0,
                            gemini_score=None
                        ))
                        count += 1
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Error building fetched jobs preview: {e}")

        # Build final result
        result = SearchResult(
            success=True,
            jobs_fetched=jobs_fetched,
            jobs_imported=jobs_imported,
            jobs_matched=len(all_matches),
            high_matches=high_matches,
            exported_to_sheets=exported_count,
            duration_seconds=round(duration, 1),
            top_matches=top_matches,
            fetched_jobs=fetched_jobs,
            sheets_url=sheets_url
        )
        
        # Save performance metrics
        try:
            perf_logger.record_count('jobs_fetched', jobs_fetched)
            perf_logger.record_count('jobs_imported', jobs_imported)
            perf_logger.record_count('jobs_matched', len(all_matches))
            perf_logger.record_count('high_matches', high_matches)
            
            db_session = SessionLocal()
            try:
                perf_logger.save(db_session, status='success')
            finally:
                db_session.close()
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

        # Send final completed event with full result
        final_progress = SearchProgress(
            stage=SearchStage.COMPLETED,
            progress=100,
            message=f"Search complete in {duration:.1f}s",
            jobs_found=jobs_fetched,
            jobs_imported=jobs_imported,
            matches_found=len(all_matches),
            high_matches=high_matches,
            exported_count=exported_count
        )

        yield f"data: {final_progress.model_dump_json()}\n\n"
        yield f"data: {json.dumps({'type': 'result', 'data': result.model_dump()})}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
