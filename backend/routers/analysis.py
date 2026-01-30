"""Analysis router for Resume Targeter API.

Provides endpoints for analyzing resumes against jobs,
generating AI suggestions, and exporting tailored resumes.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import logging
import threading

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from src.targeting.role_analyzer import RoleAnalyzer
from src.targeting.bullet_rewriter import BulletRewriter
from src.resume.parser import ResumeParser
from src.database.db import SessionLocal
from src.database.models import JobPosting, MatchResult

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
    resume_content: Optional[str] = None
    resume_filename: Optional[str] = None
    job_id: Optional[int] = None
    job_description: Optional[str] = None
    job_title: Optional[str] = None
    job_company: Optional[str] = None
    threshold: float = 0.7


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
    resume_content: Optional[str] = None
    resume_filename: Optional[str] = None
    role_index: int
    job_title: str
    job_company: str
    job_description: str
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


# Endpoints

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(request: AnalyzeRequest):
    """Analyze a resume against a job description.

    Provides alignment scores for each role and bullet point.
    """
    # Get resume content
    if request.resume_content:
        resume_text = request.resume_content
    elif request.resume_filename:
        file_path = RESUME_LIBRARY_DIR / request.resume_filename
        validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume not found")
        with open(file_path) as f:
            resume_text = f.read()
    else:
        raise HTTPException(status_code=400, detail="Provide resume_content or resume_filename")

    # Get job description
    job_title = request.job_title or ""
    job_company = request.job_company or ""
    saved_suggestions = None  # Will be loaded if job_id provided

    if request.job_id:
        # Single session to fetch both job and match result (avoid N+1)
        session = SessionLocal()
        try:
            job = session.query(JobPosting).filter(JobPosting.id == request.job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            job_description = job.description
            job_title = job.title
            job_company = job.company

            # Also fetch saved suggestions in the same session
            match = session.query(MatchResult).filter(
                MatchResult.job_id == request.job_id
            ).first()
            if match and match.bullet_suggestions:
                saved_suggestions = match.bullet_suggestions
        finally:
            session.close()
    elif request.job_description:
        job_description = request.job_description
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
            perf_logger.save(db_session, status='success')
        finally:
            db_session.close()

    except Exception as e:
        # Save error metrics
        db_session = SessionLocal()
        try:
            perf_logger.record_api_call('analyze_resume', 0, 'error', error_message=str(e))
            perf_logger.save(db_session, status='error', error_message=str(e))
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
            if bs.score < request.threshold:
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
async def generate_suggestions(request: SuggestionsRequest):
    """Generate AI suggestions for a specific role's bullets.

    Only generates suggestions for low-scoring bullets (< 70%).
    """
    # Get resume content
    if request.resume_content:
        resume_text = request.resume_content
    elif request.resume_filename:
        file_path = RESUME_LIBRARY_DIR / request.resume_filename
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
        request.job_description,
        request.job_title
    )

    if request.role_index >= len(analyses):
        raise HTTPException(status_code=400, detail="Invalid role_index")

    analysis = analyses[request.role_index]

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
                job_title=request.job_title,
                company=request.job_company,
                job_description=request.job_description
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
            perf_logger.save(db_session, status='success')
        finally:
            db_session.close()
            
    except Exception as e:
        # Save error metrics
        db_session = SessionLocal()
        try:
            perf_logger.record_api_call('gemini_suggestions', 0, 'error', error_message=str(e))
            perf_logger.save(db_session, status='error', error_message=str(e))
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
    if request.job_id:
        session = SessionLocal()
        try:
            match = session.query(MatchResult).filter(MatchResult.job_id == request.job_id).first()

            if match:
                # Update the bullet_suggestions JSON
                # Structure: { "Company_Title": [ {suggestions...} ] }
                current_data = dict(match.bullet_suggestions) if match.bullet_suggestions else {}

                # Get role key from analysis
                analysis = analyses[request.role_index]
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
        role_index=request.role_index,
        bullet_suggestions=bullet_suggestions
    )


@router.post("/export", response_model=ExportResponse)
async def export_tailored_resume(request: ExportRequest):
    """Export a tailored resume with selected bullet changes."""
    # Get resume content
    if request.resume_content:
        resume_text = request.resume_content
    elif request.resume_filename:
        file_path = RESUME_LIBRARY_DIR / request.resume_filename
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
        if role_key in request.selections:
            for selection in request.selections[role_key]:
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
    safe_company = "".join(c if c.isalnum() else "_" for c in request.company)
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
async def download_tailored_resume(filename: str):
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
async def gemini_status():
    """Check if Gemini AI is available for suggestions."""
    rewriter = get_rewriter()
    return {
        "available": rewriter.is_available(),
        "message": "Ready" if rewriter.is_available() else "Not configured - add gemini.api_key to config.yaml"
    }
