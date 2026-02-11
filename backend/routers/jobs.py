"""Jobs router for Resume Targeter API.

Provides endpoints for listing and filtering matched jobs.
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.database.db import SessionLocal, get_db
from src.database.models import JobPosting, MatchResult

router = APIRouter()


class JobResponse(BaseModel):
    """Response model for a single job."""
    id: int
    title: str
    company: str
    description: str
    summary: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    posting_date: Optional[datetime] = None
    domains: List[str] = []
    match_score: float
    matching_skills: List[str] = []
    required_skills: List[str] = []
    gemini_score: Optional[float] = None
    gemini_reasoning: Optional[str] = None
    gemini_strengths: List[str] = []
    gemini_gaps: List[str] = []
    missing_domains: List[str] = []
    experience_alignment: Optional[str] = None

    # Score breakdown fields
    skills_matched_count: int = 0
    skills_required_count: int = 0
    skill_gaps: List[str] = []
    experience_required: Optional[float] = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Response model for job list."""
    jobs: List[JobResponse]
    total: int
    filtered: int


class JobFilters(BaseModel):
    """Request model for job filters."""
    min_score: float = 0
    max_score: float = 100
    recency_days: Optional[int] = None
    search: Optional[str] = None
    limit: int = 100


@router.get("", response_model=JobListResponse)
async def list_jobs(
    min_score: float = Query(0, ge=0, le=100, description="Minimum match score"),
    max_score: float = Query(100, ge=0, le=100, description="Maximum match score"),
    recency_days: Optional[int] = Query(None, ge=1, description="Jobs posted within N days"),
    search: Optional[str] = Query(None, description="Search in title/company"),
    sort_by: str = Query("score", pattern="^(score|date)$", description="Sort by 'score' or 'date'"),
    location_region: Optional[str] = Query(None, pattern="^(us|canada|remote)$", description="Filter by region: us, canada, or remote"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    session: Session = Depends(get_db)
):
    """List matched jobs with optional filters.

    - **min_score**: Minimum match score (0-100)
    - **recency_days**: Only include jobs posted within this many days
    - **search**: Filter by title or company name
    - **sort_by**: Sort order ('score' or 'date')
    - **limit**: Maximum number of results
    """
    # Base query
    query = (
        session.query(JobPosting, MatchResult)
        .join(MatchResult)
    )

    # Apply sorting
    if sort_by == "date":
        if sort_order == "asc":
            query = query.order_by(JobPosting.posting_date.asc())
        else:
            query = query.order_by(JobPosting.posting_date.desc())
    else:  # score
        if sort_order == "asc":
            query = query.order_by(MatchResult.match_score.asc())
        else:
            query = query.order_by(MatchResult.match_score.desc())

    # Get total count before filtering
    total = query.count()

    # Apply score filters
    if min_score > 0:
        query = query.filter(MatchResult.match_score >= min_score)
    if max_score < 100:
        query = query.filter(MatchResult.match_score <= max_score)

    # Apply recency filter
    if recency_days:
        cutoff = datetime.now() - timedelta(days=recency_days)
        query = query.filter(JobPosting.posting_date >= cutoff)

    # Apply location region filter
    if location_region == "us":
        query = query.filter(JobPosting.location.ilike("%United States%"))
    elif location_region == "canada":
        query = query.filter(JobPosting.location.ilike("%Canada%"))
    elif location_region == "remote":
        query = query.filter(
            or_(
                JobPosting.location.ilike("%remote%"),
                JobPosting.title.ilike("%remote%"),
            )
        )

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (JobPosting.title.ilike(search_term)) |
            (JobPosting.company.ilike(search_term))
        )

    # Apply limit
    # Fetch extra to handle potential duplicates from multiple resume matches or DB duplicates
    raw_results = query.limit(limit * 5).all()

    # Deduplicate by normalized title+company (not just ID) to handle DB duplicates
    seen_jobs = set()
    unique_results = []
    for job, match in raw_results:
        # Create a normalized key for deduplication
        dedup_key = (job.title.strip().lower(), job.company.strip().lower())
        if dedup_key not in seen_jobs:
            seen_jobs.add(dedup_key)
            unique_results.append((job, match))
            if len(unique_results) >= limit:
                break

    jobs = []
    for job, match in unique_results:
        matching_skills = match.matching_skills or []
        required_skills = job.required_skills or []
        # Calculate skill gaps (required but not matched)
        matching_skills_lower = {s.lower() for s in matching_skills}
        skill_gaps = [s for s in required_skills if s.lower() not in matching_skills_lower]

        jobs.append(JobResponse(
            id=job.id,
            title=job.title,
            company=job.company,
            description=job.description,
            summary=job.summary,
            url=job.url,
            location=job.location,
            salary=job.salary,
            posting_date=job.posting_date,
            domains=job.required_domains or [],
            required_skills=required_skills,
            match_score=match.match_score,
            matching_skills=matching_skills,
            gemini_score=match.gemini_score,
            gemini_reasoning=match.gemini_reasoning,
            gemini_strengths=match.gemini_strengths or [],
            gemini_gaps=match.gemini_gaps or [],
            missing_domains=match.missing_domains or [],
            experience_alignment=match.experience_alignment,
            # New fields
            skills_matched_count=len(matching_skills),
            skills_required_count=len(required_skills),
            skill_gaps=skill_gaps,
            experience_required=job.experience_required,
        ))

    return JobListResponse(
        jobs=jobs,
        total=total, # Note: Total might still include duplicates in count
        filtered=len(jobs)
    )


@router.get("/stats/summary")
async def get_job_stats(session: Session = Depends(get_db)):
    """Get summary statistics about matched jobs."""
    from sqlalchemy import func

    total = session.query(JobPosting).count()

    avg_score = session.query(func.avg(MatchResult.match_score)).scalar() or 0

    high_match = (
        session.query(MatchResult)
        .filter(MatchResult.match_score >= 85)
        .count()
    )

    recent = (
        session.query(JobPosting)
        .filter(JobPosting.posting_date >= datetime.now() - timedelta(days=7))
        .count()
    )

    return {
        "total_jobs": total,
        "average_match_score": round(avg_score, 1),
        "high_match_count": high_match,
        "recent_count": recent
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, session: Session = Depends(get_db)):
    """Get a single job by ID with full details."""
    result = (
        session.query(JobPosting, MatchResult)
        .join(MatchResult)
        .filter(JobPosting.id == job_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    job, match = result

    matching_skills = match.matching_skills or []
    required_skills = job.required_skills or []
    matching_skills_lower = {s.lower() for s in matching_skills}
    skill_gaps = [s for s in required_skills if s.lower() not in matching_skills_lower]

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        description=job.description,
        summary=job.summary,
        url=job.url,
        location=job.location,
        salary=job.salary,
        posting_date=job.posting_date,
        domains=job.required_domains or [],
        required_skills=required_skills,
        match_score=match.match_score,
        matching_skills=matching_skills,
        gemini_score=match.gemini_score,
        gemini_reasoning=match.gemini_reasoning,
        gemini_strengths=match.gemini_strengths or [],
        gemini_gaps=match.gemini_gaps or [],
        missing_domains=match.missing_domains or [],
        experience_alignment=match.experience_alignment,
        # New fields
        skills_matched_count=len(matching_skills),
        skills_required_count=len(required_skills),
        skill_gaps=skill_gaps,
        experience_required=job.experience_required,
    )


class RerankRequest(BaseModel):
    """Request model for re-ranking jobs."""
    days: int = 7
    min_score: float = 65
    limit: int = 25
    force: bool = False


class RerankResponse(BaseModel):
    """Response model for re-ranking results."""
    success: bool
    message: str
    jobs_processed: int
    jobs_succeeded: int
    jobs_failed: int


@router.post("/rerank", response_model=RerankResponse)
async def rerank_jobs(
    request: RerankRequest,
    session: Session = Depends(get_db)
):
    """Re-rank recent jobs using Gemini AI.
    
    This endpoint triggers Gemini re-ranking for jobs posted in the last N days
    that haven't been ranked yet (or all with force=true).
    """
    from src.integrations.gemini_client import GeminiMatchReranker
    from src.database.models import Resume
    
    # Initialize reranker
    reranker = GeminiMatchReranker()
    if not reranker.is_available():
        raise HTTPException(
            status_code=503,
            detail="Gemini reranker not available. Check gemini config in config.yaml"
        )
    
    # Get cutoff date
    cutoff_date = datetime.now() - timedelta(days=request.days)
    
    # Query jobs needing re-ranking
    query = (
        session.query(JobPosting, MatchResult)
        .join(MatchResult, JobPosting.id == MatchResult.job_id)
        .filter(JobPosting.posting_date >= cutoff_date)
        .filter(MatchResult.match_score >= request.min_score)
    )
    
    if not request.force:
        query = query.filter(MatchResult.gemini_score.is_(None))
    
    query = query.order_by(MatchResult.match_score.desc())
    query = query.limit(request.limit)
    
    results = query.all()
    
    if not results:
        return RerankResponse(
            success=True,
            message="No jobs found matching criteria",
            jobs_processed=0,
            jobs_succeeded=0,
            jobs_failed=0
        )
    
    # Get resume for skills
    resume = session.query(Resume).first()
    resume_skills = resume.skills if resume else []
    experience_years = resume.experience_years if resume else 0
    
    success_count = 0
    error_count = 0
    error_details = []
    
    for job, match in results:
        # Build match dict for reranker
        match_dict = {
            'job_id': job.id,
            'job_title': job.title,
            'company': job.company,
            'location': job.location or '',
            'description': job.description or '',
            'overall_score': match.match_score / 100,
        }
        
        try:
            # Evaluate with Gemini
            result = reranker._evaluate_match(
                match=match_dict,
                resume_skills=resume_skills,
                experience_years=experience_years,
                resume_domains=[]
            )
            
            if result.get('score') is not None:
                match.gemini_score = result['score']
                match.gemini_reasoning = result.get('reasoning')
                match.gemini_strengths = result.get('strengths', [])
                match.gemini_gaps = result.get('gaps', [])
                success_count += 1
            else:
                error_count += 1
                error_details.append({
                    'job': f"{job.title} @ {job.company}",
                    'error': 'No score returned from Gemini'
                })
        except Exception as e:
            error_count += 1
            error_details.append({
                'job': f"{job.title} @ {job.company}",
                'error': str(e)
            })
    
    session.commit()
    
    # Include error details in message if any
    message = f"Re-ranked {success_count} of {len(results)} jobs"
    if error_details and len(error_details) <= 3:
        message += f" | Errors: {[e['error'][:50] for e in error_details]}"
    
    return RerankResponse(
        success=True,
        message=message,
        jobs_processed=len(results),
        jobs_succeeded=success_count,
        jobs_failed=error_count
    )
