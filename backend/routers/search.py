"""Search router for Resume Targeter API.

Provides endpoints for triggering job searches with real-time progress via SSE.
"""

import asyncio
import json
import logging
import time as time_module
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import get_config
from src.database.db import SessionLocal
from src.database.models import Resume, JobPosting, MatchResult, ScheduledSearch, SearchJob
from src.importers.provider_factory import get_job_provider
from src.matching.engine import JobMatcher
from src.integrations.gemini_client import get_gemini_reranker
from backend.services.matcher_service import get_job_matcher
from src.resume.parser import ResumeParser
from backend.limiter import limiter

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


class GeminiStatsResponse(BaseModel):
    """Statistics about Gemini API usage during matching."""
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    failure_reasons: List[str] = []


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
    gemini_stats: Optional[GeminiStatsResponse] = None


# Endpoints

@router.get("/defaults", response_model=SearchDefaults)
@limiter.limit("200/minute")
async def get_search_defaults(request: Request):
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


class SuggestedKeyword(BaseModel):
    """A suggested search keyword with usage count."""
    keyword: str
    count: int
    source: str  # "scheduled" or "job_titles"


class SuggestedKeywordsResponse(BaseModel):
    """Response with suggested keywords for search."""
    suggestions: List[SuggestedKeyword]


@router.get("/suggested-keywords", response_model=SuggestedKeywordsResponse)
@limiter.limit("200/minute")
async def get_suggested_keywords(request: Request, limit: int = 7):
    """Get suggested keywords based on past searches and common job titles.

    Combines:
    1. Keywords from scheduled searches (high priority)
    2. Most common job titles from imported jobs

    Args:
        limit: Maximum number of suggestions to return (default: 7)

    Returns:
        List of suggested keywords with counts
    """
    from sqlalchemy import func

    db = SessionLocal()
    suggestions = []
    seen_keywords = set()

    try:
        # 1. Get keywords from scheduled searches (most relevant)
        scheduled_keywords = (
            db.query(
                func.lower(ScheduledSearch.keyword).label('keyword'),
                func.count(ScheduledSearch.id).label('count')
            )
            .group_by(func.lower(ScheduledSearch.keyword))
            .order_by(func.count(ScheduledSearch.id).desc())
            .limit(limit)
            .all()
        )

        for kw, count in scheduled_keywords:
            normalized = kw.strip().title()
            if normalized.lower() not in seen_keywords:
                suggestions.append(SuggestedKeyword(
                    keyword=normalized,
                    count=count,
                    source="scheduled"
                ))
                seen_keywords.add(normalized.lower())

        # 2. Get most common job titles from imported jobs (if we need more)
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)

            # Get common job titles, normalizing variations
            common_titles = (
                db.query(
                    func.lower(JobPosting.title).label('title'),
                    func.count(JobPosting.id).label('count')
                )
                .group_by(func.lower(JobPosting.title))
                .order_by(func.count(JobPosting.id).desc())
                .limit(remaining + 10)  # Get extra to filter out duplicates
                .all()
            )

            for title, count in common_titles:
                if len(suggestions) >= limit:
                    break

                # Normalize the title for comparison
                normalized = title.strip().title()
                normalized_lower = normalized.lower()

                # Skip if already in suggestions or too similar
                if normalized_lower in seen_keywords:
                    continue

                # Skip very long titles (likely specific job posts, not search terms)
                if len(normalized) > 50:
                    continue

                suggestions.append(SuggestedKeyword(
                    keyword=normalized,
                    count=count,
                    source="job_titles"
                ))
                seen_keywords.add(normalized_lower)

        return SuggestedKeywordsResponse(suggestions=suggestions)

    finally:
        db.close()


@router.post("/jobs")
@limiter.limit("10/minute")
async def search_jobs(request: Request, job_req: JobSearchRequest):
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
        file_path = RESUME_LIBRARY_DIR / job_req.resume_filename
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
                error=f"Resume file not found: {job_req.resume_filename}"
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
            resume_domains = []
            for category_name, category_skills in parsed.skills.items():
                if category_name.lower() == 'domains':
                    # Store domain names for mapping later
                    resume_domains = list(category_skills)
                else:
                    flat_skills.extend(category_skills)

            # Map resume domain names to domain expertise keys
            # Load domain expertise config for mapping
            domain_expertise_path = Path(__file__).parent.parent.parent / "data" / "domain_expertise.json"
            mapped_domains = []
            if domain_expertise_path.exists():
                try:
                    with open(domain_expertise_path, 'r') as f:
                        domain_config = json.load(f)
                    
                    # Build reverse lookup: keyword -> domain key
                    domain_lookup = {}
                    for category in ['industries', 'platforms', 'technologies']:
                        if category in domain_config.get('domains', {}):
                            for domain_key, domain_data in domain_config['domains'][category].items():
                                # Add the domain key itself
                                domain_lookup[domain_key.lower()] = domain_key
                                # Add keywords
                                for keyword in domain_data.get('keywords', []):
                                    domain_lookup[keyword.lower()] = domain_key
                    
                    # Map resume domains to domain keys
                    for domain_name in resume_domains:
                        domain_lower = domain_name.lower().replace(' ', '_')
                        # Try direct match first
                        if domain_lower in domain_lookup:
                            mapped_domains.append(domain_lookup[domain_lower])
                        else:
                            # Try keyword matching
                            for keyword, domain_key in domain_lookup.items():
                                if keyword in domain_lower or domain_lower in keyword:
                                    mapped_domains.append(domain_key)
                                    break
                    
                    # Remove duplicates while preserving order
                    mapped_domains = list(dict.fromkeys(mapped_domains))
                    logger.info(f"Mapped resume domains: {resume_domains} -> {mapped_domains}")
                except Exception as e:
                    logger.warning(f"Failed to load domain expertise config: {e}")

            # Estimate experience years from roles (count years from durations)
            experience_years = 0.0
            import re
            for role in parsed.roles:
                # Try to extract years from duration string like "2020 - 2023" or "3 years"
                duration = role.duration.lower()
                # Match year ranges like "2020 - 2023"
                year_match = re.findall(r'20\d{2}', duration)
                if len(year_match) >= 2:
                    try:
                        years = int(year_match[-1]) - int(year_match[0])
                        experience_years += max(0, years)
                    except ValueError:
                        pass
                # Match "X years" pattern
                elif 'year' in duration:
                    num_match = re.search(r'(\d+)', duration)
                    if num_match:
                        experience_years += float(num_match.group(1))

            # Create a Resume-like object for the matcher
            # Using a simple class that mimics the Resume model interface
            class ParsedResume:
                def __init__(self, skills, experience_years, domains=None, job_titles=None):
                    self.id = 0  # Temporary ID
                    self.skills = skills
                    self.experience_years = experience_years
                    self.domains = domains or []
                    self.job_titles = job_titles or []

            # Extract recent job titles from parsed roles
            recent_titles = [role.title for role in parsed.roles[:5]] if parsed.roles else []

            resume = ParsedResume(
                skills=flat_skills,
                experience_years=experience_years,
                domains=mapped_domains,
                job_titles=recent_titles
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
            message=f"Fetching jobs for '{job_req.keyword}'..."
        ))

        # Handle remote keyword suffix
        keyword = job_req.keyword.strip()
        is_remote_search = keyword.lower().endswith("remote")

        if is_remote_search:
            actual_keyword = keyword[:-6].strip()  # Remove "remote" suffix
            search_location = "United States"
            work_arrangement = "Remote"
        else:
            actual_keyword = keyword
            search_location = job_req.location
            work_arrangement = job_req.work_arrangement

        # Initialize jobs variable
        jobs = [] 
        importer = None
        
        # Progress queue for collecting updates from async callback
        progress_queue: List[SearchProgress] = []
        
        async def apify_progress_callback(message: str, sub_progress: float):
            """Collect progress updates from Apify calls."""
            # Map sub_progress (0.0-1.0) to overall progress (15-38)
            overall_progress = 15 + int(sub_progress * 23)
            progress_queue.append(SearchProgress(
                stage=SearchStage.FETCHING,
                progress=overall_progress,
                message=message
            ))
        
        try:
            provider = get_job_provider()
            jobs = await provider.search_jobs_async(
                keywords=actual_keyword,
                location=search_location,
                job_type=job_req.job_type,
                max_results=job_req.max_results,
                experience_level=job_req.experience_level,
                work_arrangement=work_arrangement,
                split_calls=True,  # Enable parallel execution
                progress_callback=apify_progress_callback
            )
            
            # Yield any progress updates that were collected during async execution
            for prog in progress_queue:
                yield send_progress(prog)
                
        except Exception as e:
            logger.error(f"Job fetch failed: {e}", exc_info=True)
            yield send_progress(SearchProgress(
                stage=SearchStage.ERROR,
                progress=15,
                message="Failed to fetch jobs",
                error=f"Job fetch error: {str(e)}"
            ))
            return

        # Deduplicate fetched jobs by (title, company) - split_calls can return duplicates
        if jobs:
            seen_raw = {}
            for job in jobs:
                try:
                    norm = provider.normalize_job(job)
                    title = norm.get('title', '').strip().lower()
                    company = norm.get('company', '').strip().lower()
                    dedup_key = (title, company)
                    if dedup_key not in seen_raw:
                        seen_raw[dedup_key] = job
                except Exception:
                    continue
            duplicate_count = len(jobs) - len(seen_raw)
            if duplicate_count > 0:
                logger.info(f"Removed {duplicate_count} duplicate jobs from Apify results")
            jobs = list(seen_raw.values())
            del seen_raw  # Free dedup dict

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
            jobs_imported = provider.import_jobs(jobs)
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
                # IMPORTANT: Only match against jobs fetched in THIS session
                # Convert raw fetched jobs to JobPosting-like objects for matching
                # This prevents wasting Gemini resources on old jobs in the database
                
                # Normalize and convert fetched jobs to JobPosting objects
                fetched_job_objects = []
                for raw_job in jobs:
                    try:
                        normalized = provider.normalize_job(raw_job)
                        
                        # Query DB to get the full JobPosting object (if it was imported)
                        # This gets domain extractions, summaries, etc. from the import stage
                        from src.database.crud import get_job_by_title_company
                        db_job = get_job_by_title_company(
                            db_session,
                            normalized.get('title', ''),
                            normalized.get('company', '')
                        )
                        
                        if db_job:
                            fetched_job_objects.append(db_job)
                        else:
                            # Job wasn't imported (duplicate or invalid) - skip it
                            continue
                            
                    except Exception as e:
                        logger.warning(f"Failed to process fetched job for matching: {e}")
                        continue
                
                all_jobs = fetched_job_objects
                del fetched_job_objects  # No longer needed; raw API list also done
                del jobs                 # Free raw API response list

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

                yield send_progress(SearchProgress(
                    stage=SearchStage.MATCHING,
                    progress=55,
                    message=f"Analyzing {len(all_jobs)} jobs...",
                    jobs_found=jobs_fetched,
                    jobs_imported=jobs_imported
                ))

                # Run matching (auto mode uses Gemini AI if available)
                matcher = get_job_matcher()
                matches, gemini_stats = matcher.match_jobs(resume, all_jobs, min_score=0.0)

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
                            matches = gemini_reranker.rerank_matches(
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
        # Supports both new AI matching (ai_match_score) and old re-ranker (gemini_score)
        ai_weight = config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
        nlp_weight = config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

        def get_blended_score(match):
            # Check if this is a new AI match (match_engine == 'gemini')
            if match.get('match_engine') == 'gemini':
                # New AI matching - overall_score already reflects AI score
                return match.get('overall_score', 0)

            # Legacy: check for re-ranker score
            nlp_score = match.get('overall_score', 0)
            ai_score = match.get('gemini_score')
            if ai_score is not None:
                return (ai_score * ai_weight) + (nlp_score * nlp_weight)
            return nlp_score

        all_matches.sort(key=get_blended_score, reverse=True)

        # Count high matches (>=85%)
        high_matches = len([m for m in all_matches if get_blended_score(m) >= 0.85])

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

        if job_req.export_to_sheets and all_matches:
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
                gemini_score=round(match.get('gemini_score', 0), 1) if match.get('gemini_score') else None
            ))

        # Build fetched jobs preview (already deduplicated after fetch)
        fetched_jobs = []
        if jobs:
            try:
                norm_importer = importer if importer else get_job_provider()
                for job in jobs:
                    try:
                        norm = norm_importer.normalize_job(job)
                        fetched_jobs.append(TopMatch(
                            title=norm.get('title', 'Unknown'),
                            company=norm.get('company', 'Unknown'),
                            location=norm.get('location'),
                            url=norm.get('url'),
                            score=0.0,
                            gemini_score=None
                        ))
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Error building fetched jobs preview: {e}")

        # Build gemini stats response if available
        gemini_stats_response = None
        if gemini_stats:
            gemini_stats_response = GeminiStatsResponse(
                attempted=gemini_stats.attempted,
                succeeded=gemini_stats.succeeded,
                failed=gemini_stats.failed,
                failure_reasons=gemini_stats.failure_reasons
            )

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
            sheets_url=sheets_url,
            gemini_stats=gemini_stats_response
        )
        
        # Save performance metrics
        try:
            perf_logger.record_count('jobs_fetched', jobs_fetched)
            perf_logger.record_count('jobs_imported', jobs_imported)
            perf_logger.record_count('jobs_matched', len(all_matches))
            perf_logger.record_count('high_matches', high_matches)

            # Record Gemini matching stats
            if gemini_stats:
                perf_logger.record_count('gemini_attempted', gemini_stats.attempted)
                perf_logger.record_count('gemini_succeeded', gemini_stats.succeeded)
                perf_logger.record_count('gemini_failed', gemini_stats.failed)
                if gemini_stats.failure_reasons:
                    perf_logger.record_extra('gemini_failure_reasons', gemini_stats.failure_reasons)
                timing = gemini_stats.timing_summary()
                if timing:
                    perf_logger.record_extra('gemini_timing_summary', timing)

            db_session = SessionLocal()
            try:
                perf_logger.save(db_session, status='success', trigger_source='manual')
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


# ========================================================================
# Config & Health Endpoints
# ========================================================================

class GeminiConfigStatus(BaseModel):
    """Gemini configuration status for frontend."""
    enabled: bool
    matcher_enabled: bool
    has_api_key: bool
    mode: str
    model: Optional[str] = None


class GeminiHealthResponse(BaseModel):
    """Gemini API health check response."""
    available: bool
    model: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@router.get("/config/gemini-status", response_model=GeminiConfigStatus)
@limiter.limit("200/minute")
async def get_gemini_config_status(request: Request):
    """Get Gemini configuration status for frontend display.

    Returns configuration state so frontend can show appropriate warnings
    if Gemini is not properly configured.
    """
    config = get_config()

    return GeminiConfigStatus(
        enabled=config.get("gemini.enabled", False),
        matcher_enabled=config.get("gemini.matcher.enabled", False),
        has_api_key=bool(config.get("gemini.api_key")),
        mode=config.get("matching.engine", "auto"),
        model=config.get("gemini.matcher.model") if config.get("gemini.enabled") else None
    )


@router.get("/health/gemini", response_model=GeminiHealthResponse)
@limiter.limit("200/minute")
async def check_gemini_health(request: Request):
    """Check Gemini API availability.

    Performs a lightweight test to verify Gemini API is reachable
    and properly configured. Used for pre-search validation.
    """
    config = get_config()

    # Check if Gemini is even enabled
    if not config.get("gemini.enabled", False):
        return GeminiHealthResponse(
            available=False,
            error="Gemini is not enabled in configuration"
        )

    if not config.get("gemini.api_key"):
        return GeminiHealthResponse(
            available=False,
            error="Gemini API key not configured"
        )

    # Try to test the connection
    try:
        from src.integrations.gemini_client import GeminiClient

        client = GeminiClient()
        if not client.enabled:
            return GeminiHealthResponse(
                available=False,
                error="Gemini client initialization failed"
            )

        # Perform a lightweight test
        result = client.test_connection()

        return GeminiHealthResponse(
            available=result.get("available", False),
            model=result.get("model"),
            latency_ms=result.get("latency_ms"),
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return GeminiHealthResponse(
            available=False,
            error=str(e)
        )


# ========================================================================
# Background Job Queue Endpoints (Resilient to disconnections)
# ========================================================================

from backend.schemas.search import (
    SearchJobCreate,
    SearchJobStartResponse,
    SearchJobProgress,
    SearchJobListResponse
)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/jobs/start", response_model=SearchJobStartResponse)
@limiter.limit("10/minute")
async def start_search_job(
    request: Request,
    job_req: JobSearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a job search in the background.

    Returns immediately with a search_id that can be polled for progress.
    This endpoint is resilient to browser disconnections - results are
    persisted to the database and can be retrieved later.
    """
    # Generate unique search ID
    search_id = str(uuid.uuid4())

    # Validate resume file
    file_path = RESUME_LIBRARY_DIR / job_req.resume_filename
    try:
        validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Access denied - invalid resume path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Resume file not found: {job_req.resume_filename}")

    # Create SearchJob record
    search_job = SearchJob(
        search_id=search_id,
        status='pending',
        stage='initializing',
        progress=0,
        message='Search queued',
        keyword=job_req.keyword,
        location=job_req.location,
        job_type=job_req.job_type,
        experience_level=job_req.experience_level,
        work_arrangement=job_req.work_arrangement,
        max_results=job_req.max_results,
        resume_filename=job_req.resume_filename,
        export_to_sheets=job_req.export_to_sheets,
        trigger_source='manual',
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db.add(search_job)
    db.commit()

    # Start background task
    background_tasks.add_task(execute_search_job, search_id)

    logger.info(f"Started search job {search_id} for keyword '{job_req.keyword}'")

    return SearchJobStartResponse(
        search_id=search_id,
        status='pending',
        message='Search started in background'
    )


@router.get("/jobs/{search_id}/status", response_model=SearchJobProgress)
@limiter.limit("200/minute")
async def get_search_status(request: Request, search_id: str, db: Session = Depends(get_db)):
    """Get the current progress of a search job.

    Poll this endpoint every 2-3 seconds to get updates.
    Once status is 'completed' or 'failed', polling can stop.
    """
    search_job = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()

    if not search_job:
        raise HTTPException(status_code=404, detail="Search job not found")

    return SearchJobProgress(
        search_id=search_job.search_id,
        status=search_job.status,
        stage=search_job.stage,
        progress=search_job.progress,
        message=search_job.message,
        jobs_found=search_job.jobs_found,
        jobs_imported=search_job.jobs_imported,
        matches_found=search_job.matches_found,
        high_matches=search_job.high_matches,
        exported_count=search_job.exported_count,
        result=search_job.result if search_job.status == 'completed' else None,
        error=search_job.error if search_job.status == 'failed' else None,
        created_at=search_job.created_at,
        updated_at=search_job.updated_at or search_job.created_at
    )


@router.get("/jobs/recent", response_model=SearchJobListResponse)
@limiter.limit("200/minute")
async def list_recent_search_jobs(request: Request, limit: int = 10, db: Session = Depends(get_db)):
    """List recent search jobs for recovery after disconnection."""
    jobs = db.query(SearchJob).order_by(SearchJob.created_at.desc()).limit(limit).all()

    return SearchJobListResponse(
        jobs=[
            SearchJobProgress(
                search_id=job.search_id,
                status=job.status,
                stage=job.stage,
                progress=job.progress,
                message=job.message,
                jobs_found=job.jobs_found,
                jobs_imported=job.jobs_imported,
                matches_found=job.matches_found,
                high_matches=job.high_matches,
                exported_count=job.exported_count,
                result=job.result if job.status == 'completed' else None,
                error=job.error if job.status == 'failed' else None,
                created_at=job.created_at,
                updated_at=job.updated_at or job.created_at
            )
            for job in jobs
        ],
        total=len(jobs)
    )


@router.post("/jobs/{search_id}/cancel")
@limiter.limit("60/minute")
async def cancel_search_job(request: Request, search_id: str, db: Session = Depends(get_db)):
    """Request cancellation of a running search job.

    The pipeline checks for cancellation between stages and will stop
    at the next checkpoint, saving partial results.
    """
    search_job = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()

    if not search_job:
        raise HTTPException(status_code=404, detail="Search job not found")

    if search_job.status in ('completed', 'failed'):
        raise HTTPException(status_code=400, detail=f"Search already {search_job.status}")

    search_job.cancellation_requested = True
    db.commit()

    logger.info(f"Cancellation requested for search job {search_id}")
    return {"search_id": search_id, "message": "Cancellation requested"}


class SearchCancelledException(Exception):
    """Raised when a search job is cancelled by the user."""
    pass


def _check_cancelled(db, search_job):
    """Check if cancellation has been requested and handle it.

    Refreshes the SearchJob from DB to pick up the cancellation flag
    set by the cancel endpoint (running in a different request context).
    """
    db.refresh(search_job)
    if search_job.cancellation_requested:
        search_job.status = 'failed'
        search_job.error = 'Search cancelled by user'
        search_job.stage = 'cancelled'
        db.commit()
        raise SearchCancelledException()


def execute_search_job(search_id: str):
    """Execute the search pipeline in background.

    This function runs the full search pipeline and updates the SearchJob
    record with progress at each stage. Results are persisted to the database.

    Called via BackgroundTasks - runs in a thread pool.
    """
    # Run the async function in an event loop
    asyncio.run(_execute_search_job_async(search_id))


async def _execute_search_job_async(search_id: str):
    """Async implementation of the search pipeline."""
    db = SessionLocal()
    start_time = time_module.perf_counter()
    config = get_config()

    try:
        search_job = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()
        if not search_job:
            logger.error(f"Search job {search_id} not found")
            return

        def update_progress(stage: str, progress: int, message: str, **kwargs):
            """Update progress in database."""
            search_job.stage = stage
            search_job.progress = progress
            search_job.message = message
            for key, value in kwargs.items():
                if hasattr(search_job, key) and value is not None:
                    setattr(search_job, key, value)
            search_job.updated_at = datetime.now(timezone.utc)
            db.commit()

        # Update status to running
        search_job.status = 'running'
        update_progress('initializing', 0, 'Starting search...')

        # ================================================================
        # STAGE 1: Initialize (0-10%)
        # ================================================================
        file_path = RESUME_LIBRARY_DIR / search_job.resume_filename

        update_progress('initializing', 5, 'Loading resume...')

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                resume_content = f.read()

            parser = ResumeParser()
            parsed = parser.parse_auto(resume_content)

            # Extract skills and domains
            flat_skills = []
            resume_domains = []
            for category_name, category_skills in parsed.skills.items():
                if category_name.lower() == 'domains':
                    resume_domains = list(category_skills)
                else:
                    flat_skills.extend(category_skills)

            # Map domains
            domain_expertise_path = Path(__file__).parent.parent.parent / "data" / "domain_expertise.json"
            mapped_domains = []
            if domain_expertise_path.exists():
                try:
                    with open(domain_expertise_path, 'r') as f:
                        domain_config = json.load(f)
                    domain_lookup = {}
                    for category in ['industries', 'platforms', 'technologies']:
                        if category in domain_config.get('domains', {}):
                            for domain_key, domain_data in domain_config['domains'][category].items():
                                domain_lookup[domain_key.lower()] = domain_key
                                for keyword in domain_data.get('keywords', []):
                                    domain_lookup[keyword.lower()] = domain_key
                    for domain_name in resume_domains:
                        domain_lower = domain_name.lower().replace(' ', '_')
                        if domain_lower in domain_lookup:
                            mapped_domains.append(domain_lookup[domain_lower])
                    mapped_domains = list(dict.fromkeys(mapped_domains))
                except Exception as e:
                    logger.warning(f"Failed to load domain expertise config: {e}")

            # Calculate experience years
            import re
            experience_years = 0.0
            for role in parsed.roles:
                duration = role.duration.lower()
                year_match = re.findall(r'20\d{2}', duration)
                if len(year_match) >= 2:
                    try:
                        years = int(year_match[-1]) - int(year_match[0])
                        experience_years += max(0, years)
                    except ValueError:
                        pass
                elif 'year' in duration:
                    num_match = re.search(r'(\d+)', duration)
                    if num_match:
                        experience_years += float(num_match.group(1))

            # Create resume object
            class ParsedResume:
                def __init__(self, skills, experience_years, domains=None, job_titles=None):
                    self.id = 0
                    self.skills = skills
                    self.experience_years = experience_years
                    self.domains = domains or []
                    self.job_titles = job_titles or []

            recent_titles = [role.title for role in parsed.roles[:5]] if parsed.roles else []
            resume = ParsedResume(
                skills=flat_skills,
                experience_years=experience_years,
                domains=mapped_domains,
                job_titles=recent_titles
            )

            update_progress('initializing', 10,
                           f"Resume loaded: {len(flat_skills)} skills, {experience_years:.0f} years exp")

        except Exception as e:
            logger.error(f"Failed to parse resume: {e}", exc_info=True)
            search_job.status = 'failed'
            search_job.error = f"Could not parse resume: {str(e)}"
            db.commit()
            return

        # Cancellation checkpoint: after resume loading
        _check_cancelled(db, search_job)

        # ================================================================
        # STAGE 2: Fetch jobs from Apify (10-40%)
        # ================================================================
        update_progress('fetching', 15, f"Fetching jobs for '{search_job.keyword}'...")

        keyword = search_job.keyword.strip()
        is_remote_search = keyword.lower().endswith("remote")

        if is_remote_search:
            actual_keyword = keyword[:-6].strip()
            search_location = "United States"
            work_arrangement = "Remote"
        else:
            actual_keyword = keyword
            search_location = search_job.location
            work_arrangement = search_job.work_arrangement

        jobs = []
        importer = None

        try:
            importer = get_job_provider()
            jobs = await importer.search_jobs_async(
                keywords=actual_keyword,
                location=search_location,
                job_type=search_job.job_type,
                max_results=search_job.max_results,
                experience_level=search_job.experience_level,
                work_arrangement=work_arrangement,
                split_calls=True
            )
        except Exception as e:
            logger.error(f"Job fetch failed: {e}", exc_info=True)
            search_job.status = 'failed'
            search_job.error = f"Job fetch error: {str(e)}"
            db.commit()
            return

        # Deduplicate
        if jobs and importer:
            seen_raw = {}
            for job in jobs:
                try:
                    norm = importer.normalize_job(job)
                    title = norm.get('title', '').strip().lower()
                    company = norm.get('company', '').strip().lower()
                    dedup_key = (title, company)
                    if dedup_key not in seen_raw:
                        seen_raw[dedup_key] = job
                except Exception:
                    continue
            jobs = list(seen_raw.values())

        jobs_fetched = len(jobs) if jobs else 0
        update_progress('fetching', 40, f"Found {jobs_fetched} jobs", jobs_found=jobs_fetched)

        # Cancellation checkpoint: after fetching
        _check_cancelled(db, search_job)

        if not jobs:
            search_job.status = 'completed'
            search_job.result = SearchResult(
                success=True, jobs_fetched=0, jobs_imported=0, jobs_matched=0,
                high_matches=0, exported_to_sheets=0, duration_seconds=0,
                top_matches=[], fetched_jobs=[]
            ).model_dump()
            update_progress('completed', 100, 'No jobs found matching criteria',
                           jobs_found=0, jobs_imported=0, matches_found=0, high_matches=0)
            return

        # ================================================================
        # STAGE 3: Import jobs (40-50%)
        # ================================================================
        update_progress('importing', 42, 'Importing jobs to database...', jobs_found=jobs_fetched)

        jobs_imported = 0
        try:
            jobs_imported = importer.import_jobs(jobs)
        except Exception as e:
            logger.warning(f"Import failed (continuing): {e}")

        update_progress('importing', 50, f"Imported {jobs_imported} new jobs",
                       jobs_found=jobs_fetched, jobs_imported=jobs_imported)

        # Cancellation checkpoint: after importing
        _check_cancelled(db, search_job)

        # ================================================================
        # STAGE 4: Match jobs (50-80%)
        # ================================================================
        update_progress('matching', 52, 'Matching jobs against resume...',
                       jobs_found=jobs_fetched, jobs_imported=jobs_imported)

        all_matches = []
        gemini_stats = None

        try:
            db_session = SessionLocal()
            try:
                from sqlalchemy import or_

                query = db_session.query(JobPosting).filter(
                    JobPosting.title.ilike(f"%{actual_keyword}%")
                )

                # Skip DB location filter for remote searches and broad geographic terms
                BROAD_LOCATIONS = {"north america", "south america", "europe", "asia", "worldwide", "global", "anywhere"}
                is_remote_request = is_remote_search or work_arrangement == "Remote"
                is_broad_location = search_location and search_location.strip().lower() in BROAD_LOCATIONS
                if not is_remote_request and not is_broad_location and search_location:
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

                all_jobs = query.limit(500).all()

                # Filter low quality
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
                del seen_jobs  # Free dedup dict

                update_progress('matching', 55, f"Analyzing {len(all_jobs)} jobs...",
                               jobs_found=jobs_fetched, jobs_imported=jobs_imported)

                # Run matching
                matcher = get_job_matcher()
                matches, gemini_stats = matcher.match_jobs(resume, all_jobs, min_score=0.0)

                update_progress('matching', 65, f"Found {len(matches)} matches, running AI analysis...",
                               jobs_found=jobs_fetched, jobs_imported=jobs_imported, matches_found=len(matches))

                # Cancellation checkpoint: before expensive Gemini re-ranking
                _check_cancelled(db, search_job)

                # Gemini re-ranking
                gemini_reranker = get_gemini_reranker()
                if matches and gemini_reranker and gemini_reranker.is_available():
                    try:
                        matches = gemini_reranker.rerank_matches(
                            matches=matches,
                            resume_skills=resume.skills or [],
                            experience_years=resume.experience_years or 0,
                            resume_domains=resume.domains or []
                        )
                    except Exception as rerank_error:
                        logger.warning(f"Gemini re-ranking failed: {rerank_error}")

                # Save matches
                resume_id_for_save = resume.id
                if resume_id_for_save == 0:
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
                    except Exception as save_error:
                        logger.warning(f"Failed to save matches: {save_error}")
                        db_session.rollback()

                all_matches = matches

            finally:
                db_session.close()

        except Exception as e:
            logger.error(f"Matching failed: {e}", exc_info=True)
            search_job.status = 'failed'
            search_job.error = str(e)
            db.commit()
            return

        # Sort matches
        ai_weight = config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
        nlp_weight = config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

        def get_blended_score(match):
            if match.get('match_engine') == 'gemini':
                return match.get('overall_score', 0)
            nlp_score = match.get('overall_score', 0)
            ai_score = match.get('gemini_score')
            if ai_score is not None:
                return (ai_score * ai_weight) + (nlp_score * nlp_weight)
            return nlp_score

        all_matches.sort(key=get_blended_score, reverse=True)
        high_matches = len([m for m in all_matches if get_blended_score(m) >= 0.85])

        update_progress('matching', 80, f"Matching complete: {high_matches} high-quality matches",
                       jobs_found=jobs_fetched, jobs_imported=jobs_imported,
                       matches_found=len(all_matches), high_matches=high_matches)

        # ================================================================
        # STAGE 5: Export (80-95%)
        # ================================================================
        exported_count = 0
        sheets_url = None

        if search_job.export_to_sheets and all_matches:
            update_progress('exporting', 82, 'Exporting to Google Sheets...',
                           jobs_found=jobs_fetched, jobs_imported=jobs_imported,
                           matches_found=len(all_matches), high_matches=high_matches)

            try:
                from src.integrations.sheets_connector import SheetsConnector
                sheets = SheetsConnector()

                if sheets.enabled:
                    try:
                        sheets.cleanup_old_matches(days=7)
                    except Exception:
                        pass

                    exported_count = sheets.export_matches_batch(all_matches)
                    spreadsheet_id = config.get("sheets.spreadsheet_id")
                    if spreadsheet_id:
                        sheets_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

                    update_progress('exporting', 95, f"Exported {exported_count} matches to Sheets",
                                   jobs_found=jobs_fetched, jobs_imported=jobs_imported,
                                   matches_found=len(all_matches), high_matches=high_matches,
                                   exported_count=exported_count)
            except Exception as e:
                logger.warning(f"Sheets export failed: {e}")
                update_progress('exporting', 95, f"Sheets export failed: {str(e)}",
                               exported_count=0)
        else:
            update_progress('exporting', 95, 'Skipping Sheets export', exported_count=0)

        # ================================================================
        # STAGE 6: Complete (100%)
        # ================================================================
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
                gemini_score=round(match.get('gemini_score', 0), 1) if match.get('gemini_score') else None
            ))

        # Build fetched jobs preview
        fetched_jobs = []
        if jobs and importer:
            for job in jobs:
                try:
                    norm = importer.normalize_job(job)
                    fetched_jobs.append(TopMatch(
                        title=norm.get('title', 'Unknown'),
                        company=norm.get('company', 'Unknown'),
                        location=norm.get('location'),
                        url=norm.get('url'),
                        score=0.0,
                        gemini_score=None
                    ))
                except Exception:
                    continue

        # Build gemini stats
        gemini_stats_response = None
        if gemini_stats:
            gemini_stats_response = GeminiStatsResponse(
                attempted=gemini_stats.attempted,
                succeeded=gemini_stats.succeeded,
                failed=gemini_stats.failed,
                failure_reasons=gemini_stats.failure_reasons
            )

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
            sheets_url=sheets_url,
            gemini_stats=gemini_stats_response
        )

        # Save to database
        search_job.status = 'completed'
        search_job.result = result.model_dump()
        update_progress('completed', 100, f"Search complete in {duration:.1f}s",
                       jobs_found=jobs_fetched, jobs_imported=jobs_imported,
                       matches_found=len(all_matches), high_matches=high_matches,
                       exported_count=exported_count)

        logger.info(f"Search job {search_id} completed: {high_matches} high matches in {duration:.1f}s")

    except SearchCancelledException:
        logger.info(f"Search job {search_id} was cancelled by user")
    except Exception as e:
        logger.error(f"Search job {search_id} failed: {e}", exc_info=True)
        try:
            search_job = db.query(SearchJob).filter(SearchJob.search_id == search_id).first()
            if search_job:
                search_job.status = 'failed'
                search_job.stage = 'error'
                search_job.error = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
