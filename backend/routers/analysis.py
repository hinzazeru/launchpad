"""Analysis router for Resume Targeter API.

Provides endpoints for analyzing resumes against jobs,
generating AI suggestions, and exporting tailored resumes.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import logging
import threading

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func, or_

from src.targeting.role_analyzer import RoleAnalyzer
from src.targeting.bullet_rewriter import BulletRewriter
from src.resume.parser import ResumeParser
from src.database.db import SessionLocal
from src.database.models import JobPosting, MatchResult, Resume
from backend.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_path_within_directory(file_path: Path, base_dir: Path) -> None:
    """Ensure file_path is within base_dir (prevent path traversal attacks)."""
    if not file_path.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")


# Output directory for tailored resumes
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "tailored_resumes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESUME_LIBRARY_DIR = PROJECT_ROOT / "data" / "resumes"

# Initialize services (lazy loading for heavy models with thread safety)
_analyzer = None
_rewriter = None
_parser = None
_init_lock = threading.Lock()


def get_analyzer():
    global _analyzer
    if _analyzer is None:
        with _init_lock:
            if _analyzer is None:  # Double-check after acquiring lock
                _analyzer = RoleAnalyzer()
    return _analyzer


def get_rewriter():
    global _rewriter
    if _rewriter is None:
        with _init_lock:
            if _rewriter is None:
                _rewriter = BulletRewriter()
    return _rewriter


def get_parser():
    global _parser
    if _parser is None:
        with _init_lock:
            if _parser is None:
                _parser = ResumeParser()
    return _parser


# Request/Response Models

class AnalyzeRequest(BaseModel):
    """Request to analyze a resume against a job."""
    resume_content: Optional[str] = Field(None, max_length=50000)
    resume_filename: Optional[str] = None
    job_id: Optional[int] = None
    job_description: Optional[str] = Field(None, max_length=20000)
    job_title: Optional[str] = Field(None, max_length=200)
    job_company: Optional[str] = Field(None, max_length=200)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class BulletScore(BaseModel):
    """Score for a single bullet point."""
    text: str
    score: float
    matched_keywords: List[str] = []
    missing_keywords: List[str] = []
    suggestions: List[str] = []


class RoleAnalysis(BaseModel):
    """Analysis for a single role."""
    company: str
    title: str
    duration: str
    alignment_score: float
    bullet_scores: List[BulletScore]
    low_scoring_count: int


class AnalyzeResponse(BaseModel):
    """Response from resume analysis."""
    success: bool
    overall_alignment: float
    total_bullets: int
    low_scoring_bullets: int
    roles: List[RoleAnalysis]
    job_title: Optional[str] = None
    job_company: Optional[str] = None


class SuggestionsRequest(BaseModel):
    """Request to generate AI suggestions for a role."""
    resume_content: Optional[str] = Field(None, max_length=50000)
    resume_filename: Optional[str] = None
    role_index: int
    job_title: str = Field(..., max_length=200)
    job_company: str = Field(..., max_length=200)
    job_description: str = Field(..., max_length=20000)
    job_id: Optional[int] = None



class SuggestionsResponse(BaseModel):
    """Response with AI-generated suggestions."""
    success: bool
    role_index: int
    bullet_suggestions: List[Dict[str, Any]]


class ExportRequest(BaseModel):
    """Request to export a tailored resume."""
    resume_content: Optional[str] = None
    resume_filename: Optional[str] = None
    selections: Dict[str, List[Dict[str, str]]]  # role_key -> list of {original, selected, type}
    company: str


class ExportResponse(BaseModel):
    """Response from resume export."""
    success: bool
    filename: str
    download_url: str
    changes_made: int


# History endpoint models

class RoleSummary(BaseModel):
    """Summary of a role in an analysis."""
    company: str
    title: str
    bullet_count: int
    has_suggestions: bool


class AnalysisHistoryItem(BaseModel):
    """A single analysis history entry."""
    match_id: int
    job_id: int
    job_title: str
    job_company: str
    job_location: Optional[str] = None
    job_url: Optional[str] = None
    resume_id: int
    match_score: float
    ai_match_score: Optional[float] = None
    match_engine: str
    generated_date: datetime
    has_bullet_suggestions: bool
    roles_summary: List[RoleSummary]
    ai_strengths_count: int
    ai_concerns_count: int


class AnalysisHistoryResponse(BaseModel):
    """Response for analysis history listing."""
    items: List[AnalysisHistoryItem]
    total: int
    skip: int
    limit: int


# Endpoints

@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("20/minute")
async def analyze_resume(request: Request, body: AnalyzeRequest):
    """Analyze a resume against a job description.

    Provides alignment scores for each role and bullet point.
    """
    # Get resume content
    if body.resume_content:
        resume_text = body.resume_content
    elif body.resume_filename:
        file_path = RESUME_LIBRARY_DIR / body.resume_filename
        validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume not found")
        with open(file_path) as f:
            resume_text = f.read()
    else:
        raise HTTPException(status_code=400, detail="Provide resume_content or resume_filename")

    # Get job description
    job_title = body.job_title or ""
    job_company = body.job_company or ""
    saved_suggestions = None  # Will be loaded if job_id provided

    if body.job_id:
        # Single session to fetch both job and match result (avoid N+1)
        session = SessionLocal()
        try:
            job = session.query(JobPosting).filter(JobPosting.id == body.job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            job_description = job.description
            job_title = job.title
            job_company = job.company

            # Also fetch saved suggestions in the same session
            match = session.query(MatchResult).filter(
                MatchResult.job_id == body.job_id
            ).first()
            if match and match.bullet_suggestions:
                saved_suggestions = match.bullet_suggestions
        finally:
            session.close()
    elif body.job_description:
        job_description = body.job_description
    else:
        raise HTTPException(status_code=400, detail="Provide job_id or job_description")

    # Run analysis
    analyzer = get_analyzer()

    from src.services.performance_logger import PerformanceLogger
    perf_logger = PerformanceLogger()

    try:
        with perf_logger.time('analyze_resume'):
            analyses = analyzer.analyze_all_roles(resume_text, job_description, job_title)
        
        # Determine status based on overall alignment
        # This is a bit arbitrary for status, but useful for logs
        perf_logger.record_count('roles_analyzed', len(analyses))
        
        # Save metrics
        db_session = SessionLocal()
        try:
            perf_logger.save(db_session, status='success', trigger_source='manual')
        finally:
            db_session.close()

    except Exception as e:
        # Save error metrics
        db_session = SessionLocal()
        try:
            perf_logger.record_api_call('analyze_resume', 0, 'error', error_message=str(e))
            perf_logger.save(db_session, status='error', trigger_source='manual', error_message=str(e))
        finally:
            db_session.close()
            
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # Build response
    roles = []
    total_bullets = 0
    low_scoring_bullets = 0

    for analysis in analyses:
        bullet_scores = []
        for bs in analysis.bullet_scores:
            bullet_scores.append(BulletScore(
                text=bs.original,
                score=bs.score,
                matched_keywords=bs.matched_keywords or [],
                missing_keywords=bs.missing_keywords or [],
                suggestions=bs.suggestions or []
            ))
            total_bullets += 1
            if bs.score < body.threshold:
                low_scoring_bullets += 1

        roles.append(RoleAnalysis(
            company=analysis.role.company,
            title=analysis.role.title,
            duration=analysis.role.duration,
            alignment_score=analysis.alignment_score,
            bullet_scores=bullet_scores,
            low_scoring_count=len(analysis.low_scoring_bullets)
        ))

    overall = analyzer.get_overall_alignment(analyses)

    # Inject any saved suggestions (already loaded in single query above)
    if saved_suggestions:
        for i, role in enumerate(roles):
            role_key = f"{role.company}_{role.title}"

            if role_key in saved_suggestions:
                role_data = saved_suggestions[role_key]

                for sugg in role_data:
                    bullet_idx = sugg['index']
                    if bullet_idx < len(roles[i].bullet_scores):
                        roles[i].bullet_scores[bullet_idx].suggestions = sugg['suggestions']

    return AnalyzeResponse(
        success=True,
        overall_alignment=overall,
        total_bullets=total_bullets,
        low_scoring_bullets=low_scoring_bullets,
        roles=roles,
        job_title=job_title,
        job_company=job_company
    )


@router.post("/suggestions", response_model=SuggestionsResponse)
@limiter.limit("20/minute")
async def generate_suggestions(request: Request, body: SuggestionsRequest):
    """Generate AI suggestions for a specific role's bullets.

    Only generates suggestions for low-scoring bullets (< 70%).
    """
    # Get resume content
    if body.resume_content:
        resume_text = body.resume_content
    elif body.resume_filename:
        file_path = RESUME_LIBRARY_DIR / body.resume_filename
        validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume not found")
        with open(file_path) as f:
            resume_text = f.read()
    else:
        raise HTTPException(status_code=400, detail="Provide resume_content or resume_filename")

    # Run analysis first to get bullet scores
    analyzer = get_analyzer()
    analyses = analyzer.analyze_all_roles(
        resume_text,
        body.job_description,
        body.job_title
    )

    if body.role_index >= len(analyses):
        raise HTTPException(status_code=400, detail="Invalid role_index")

    analysis = analyses[body.role_index]

    # Generate suggestions
    rewriter = get_rewriter()

    if not rewriter.is_available():
        raise HTTPException(
            status_code=503,
            detail="Gemini AI not configured. Add API key to config.yaml"
        )

    from src.services.performance_logger import PerformanceLogger
    perf_logger = PerformanceLogger()

    try:
        with perf_logger.time('generate_suggestions'):
            result = rewriter.rewrite_role_bullets(
                analysis=analysis,
                job_title=body.job_title,
                company=body.job_company,
                job_description=body.job_description
            )
            
        # Log AI API call details
        perf_logger.record_api_call(
            call_type='gemini_suggestions',
            duration_ms=perf_logger.timings.get('generate_suggestions', 0),
            status='success',
            tokens_used=None  # Can be populated if rewriter returns token usage
        )
        
        # Save metrics
        db_session = SessionLocal()
        try:
            perf_logger.save(db_session, status='success', trigger_source='manual')
        finally:
            db_session.close()

    except Exception as e:
        # Save error metrics
        db_session = SessionLocal()
        try:
            perf_logger.record_api_call('gemini_suggestions', 0, 'error', error_message=str(e))
            perf_logger.save(db_session, status='error', trigger_source='manual', error_message=str(e))
        finally:
            db_session.close()
            
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    # Build response
    bullet_suggestions = []
    for i, bullet_result in enumerate(result.results):
        bullet_suggestions.append({
            "index": i,
            "original": bullet_result.original,
            "score": analysis.bullet_scores[i].score if i < len(analysis.bullet_scores) else 0,
            "analysis": bullet_result.analysis,
            "suggestions": bullet_result.suggestions
        })

    # Save to Database if job_id is provided
    if body.job_id:
        session = SessionLocal()
        try:
            match = session.query(MatchResult).filter(MatchResult.job_id == body.job_id).first()

            if match:
                # Update the bullet_suggestions JSON
                # Structure: { "Company_Title": [ {suggestions...} ] }
                current_data = dict(match.bullet_suggestions) if match.bullet_suggestions else {}

                # Get role key from analysis
                analysis = analyses[body.role_index]
                role_key = f"{analysis.role.company}_{analysis.role.title}"

                current_data[role_key] = bullet_suggestions

                # Update and explicitly mark as dirty for SQLAlchemy to detect the change
                match.bullet_suggestions = current_data
                flag_modified(match, "bullet_suggestions")
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to save suggestions to DB: {e}")
        finally:
            session.close()

    return SuggestionsResponse(
        success=True,
        role_index=body.role_index,
        bullet_suggestions=bullet_suggestions
    )


@router.post("/export", response_model=ExportResponse)
@limiter.limit("20/minute")
async def export_tailored_resume(request: Request, body: ExportRequest):
    """Export a tailored resume with selected bullet changes."""
    # Get resume content
    if body.resume_content:
        resume_text = body.resume_content
    elif body.resume_filename:
        file_path = RESUME_LIBRARY_DIR / body.resume_filename
        validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume not found")
        with open(file_path) as f:
            resume_text = f.read()
    else:
        raise HTTPException(status_code=400, detail="Provide resume_content or resume_filename")

    # Parse resume
    parser = get_parser()
    structure = parser.parse_auto(resume_text)

    # Build new content
    lines = []

    # Summary
    if structure.summary:
        lines.append(structure.summary)
        lines.append("")

    # Experience header
    lines.append("Experience")
    lines.append("")

    # Process each role
    changes_made = 0
    for role in structure.roles:
        role_key = f"{role.company}_{role.title}"

        # Role header
        lines.append(role.company)
        lines.append(role.title)
        if role.duration:
            lines.append(role.duration)

        # Get selected bullets for this role
        if role_key in body.selections:
            for selection in body.selections[role_key]:
                lines.append(f"- {selection['selected']}")
                if selection.get('type') != 'original':
                    changes_made += 1
        else:
            for bullet in role.bullets:
                lines.append(f"- {bullet}")

        lines.append("")

    # Education
    if structure.education:
        lines.append(structure.education)

    content = "\n".join(lines)

    # Generate filename
    safe_company = "".join(c if c.isalnum() else "_" for c in body.company)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Resume_Tailored_{safe_company}_{date_str}.txt"

    # Save file
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w") as f:
        f.write(content)

    return ExportResponse(
        success=True,
        filename=filename,
        download_url=f"/api/analysis/download/{filename}",
        changes_made=changes_made
    )


@router.get("/download/{filename}")
@limiter.limit("60/minute")
async def download_tailored_resume(request: Request, filename: str):
    """Download a previously exported tailored resume."""
    file_path = OUTPUT_DIR / filename
    validate_path_within_directory(file_path, OUTPUT_DIR)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/plain"
    )


@router.get("/gemini-status")
@limiter.limit("200/minute")
async def gemini_status(request: Request):
    """Check if Gemini AI is available for suggestions."""
    rewriter = get_rewriter()
    return {
        "available": rewriter.is_available(),
        "message": "Ready" if rewriter.is_available() else "Not configured - add gemini.api_key to config.yaml"
    }


@router.get("/history", response_model=AnalysisHistoryResponse)
@limiter.limit("200/minute")
async def get_analysis_history(
    request: Request,
    search: Optional[str] = Query(None, description="Search job title"),
    resume_id: Optional[int] = Query(None, description="Filter by resume ID"),
    date_from: Optional[datetime] = Query(None, description="Filter by date from"),
    date_to: Optional[datetime] = Query(None, description="Filter by date to"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum match score"),
    max_score: Optional[float] = Query(None, ge=0, le=100, description="Maximum match score"),
    has_ai_suggestions: Optional[bool] = Query(None, description="Filter by AI suggestions present"),
    sort_by: str = Query("date", pattern="^(date|score)$", description="Sort by date or score"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
):
    """Get analysis history with filtering and pagination.

    Returns list of previously completed analyses with their
    AI-generated bullet suggestions status.
    """
    session = SessionLocal()
    try:
        # Build base query with join to JobPosting
        query = session.query(MatchResult).join(
            JobPosting, MatchResult.job_id == JobPosting.id
        )

        # Apply filters
        if search:
            query = query.filter(
                or_(
                    JobPosting.title.ilike(f"%{search}%"),
                    JobPosting.company.ilike(f"%{search}%")
                )
            )

        if resume_id is not None:
            query = query.filter(MatchResult.resume_id == resume_id)

        if date_from:
            query = query.filter(MatchResult.generated_date >= date_from)

        if date_to:
            query = query.filter(MatchResult.generated_date <= date_to)

        if min_score is not None:
            query = query.filter(MatchResult.match_score >= min_score)

        if max_score is not None:
            query = query.filter(MatchResult.match_score <= max_score)

        if has_ai_suggestions is not None:
            if has_ai_suggestions:
                # Has bullet suggestions (not null and not empty)
                query = query.filter(
                    MatchResult.bullet_suggestions.isnot(None),
                    MatchResult.bullet_suggestions != {}
                )
            else:
                # Does not have bullet suggestions
                query = query.filter(
                    or_(
                        MatchResult.bullet_suggestions.is_(None),
                        MatchResult.bullet_suggestions == {}
                    )
                )

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        if sort_by == "date":
            order_col = MatchResult.generated_date
        else:
            order_col = MatchResult.match_score

        if sort_order == "desc":
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(order_col.asc())

        # Apply pagination and eager load job posting
        query = query.options(joinedload(MatchResult.job_posting))
        results = query.offset(skip).limit(limit).all()

        # Build response items
        items = []
        for match in results:
            job = match.job_posting

            # Parse bullet_suggestions to build roles_summary
            roles_summary = []
            has_suggestions = False

            if match.bullet_suggestions:
                has_suggestions = True
                for role_key, suggestions in match.bullet_suggestions.items():
                    if '_' in role_key:
                        parts = role_key.rsplit('_', 1)
                        company = parts[0] if len(parts) > 1 else role_key
                        title = parts[1] if len(parts) > 1 else ''
                    else:
                        company = role_key
                        title = ''

                    bullet_count = len(suggestions) if isinstance(suggestions, list) else 0
                    roles_summary.append(RoleSummary(
                        company=company,
                        title=title,
                        bullet_count=bullet_count,
                        has_suggestions=bullet_count > 0
                    ))

            # Count AI insights
            ai_strengths_count = len(match.ai_strengths) if match.ai_strengths else 0
            ai_concerns_count = len(match.ai_concerns) if match.ai_concerns else 0

            items.append(AnalysisHistoryItem(
                match_id=match.id,
                job_id=match.job_id,
                job_title=job.title,
                job_company=job.company,
                job_location=job.location,
                job_url=job.url,
                resume_id=match.resume_id,
                match_score=match.match_score,
                ai_match_score=match.ai_match_score,
                match_engine=match.match_engine or 'nlp',
                generated_date=match.generated_date,
                has_bullet_suggestions=has_suggestions,
                roles_summary=roles_summary,
                ai_strengths_count=ai_strengths_count,
                ai_concerns_count=ai_concerns_count
            ))

        return AnalysisHistoryResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit
        )

    finally:
        session.close()


# Bullet suggestions detail models

class BulletSuggestionDetail(BaseModel):
    """Detail of a single bullet with its AI suggestions."""
    index: int
    original: str
    score: Optional[float] = None
    analysis: Optional[str] = None
    suggestions: List[str] = []


class RoleBulletSuggestions(BaseModel):
    """All bullet suggestions for a single role."""
    role_key: str
    company: str
    title: str
    bullets: List[BulletSuggestionDetail]


class MatchSuggestionsResponse(BaseModel):
    """Response with all bullet suggestions for a match."""
    match_id: int
    job_title: str
    job_company: str
    roles: List[RoleBulletSuggestions]
    total_bullets: int
    total_with_suggestions: int


@router.get("/history/{match_id}/suggestions", response_model=MatchSuggestionsResponse)
@limiter.limit("200/minute")
async def get_match_suggestions(request: Request, match_id: int):
    """Get bullet suggestions detail for a specific analysis match.

    Returns all saved AI bullet suggestions organized by role.
    """
    session = SessionLocal()
    try:
        match = session.query(MatchResult).options(
            joinedload(MatchResult.job_posting)
        ).filter(MatchResult.id == match_id).first()

        if not match:
            raise HTTPException(status_code=404, detail="Match not found")

        job = match.job_posting
        roles: List[RoleBulletSuggestions] = []
        total_bullets = 0
        total_with_suggestions = 0

        if match.bullet_suggestions:
            for role_key, suggestions_list in match.bullet_suggestions.items():
                # Parse role key
                if '_' in role_key:
                    parts = role_key.rsplit('_', 1)
                    company = parts[0] if len(parts) > 1 else role_key
                    title = parts[1] if len(parts) > 1 else ''
                else:
                    company = role_key
                    title = ''

                bullets: List[BulletSuggestionDetail] = []
                if isinstance(suggestions_list, list):
                    for sugg in suggestions_list:
                        total_bullets += 1
                        has_sugg = len(sugg.get('suggestions', [])) > 0
                        if has_sugg:
                            total_with_suggestions += 1

                        bullets.append(BulletSuggestionDetail(
                            index=sugg.get('index', 0),
                            original=sugg.get('original', ''),
                            score=sugg.get('score'),
                            analysis=sugg.get('analysis'),
                            suggestions=sugg.get('suggestions', [])
                        ))

                roles.append(RoleBulletSuggestions(
                    role_key=role_key,
                    company=company,
                    title=title,
                    bullets=bullets
                ))

        return MatchSuggestionsResponse(
            match_id=match.id,
            job_title=job.title,
            job_company=job.company,
            roles=roles,
            total_bullets=total_bullets,
            total_with_suggestions=total_with_suggestions
        )

    finally:
        session.close()
