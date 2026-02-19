"""CRUD operations for database models."""

from datetime import datetime
from typing import List, Optional, Set, Tuple
from sqlalchemy import func, or_, and_, tuple_
from sqlalchemy.orm import Session, joinedload
from src.database.models import Resume, JobPosting, MatchResult, ApplicationTracking


# Resume CRUD operations
def create_resume(
    db: Session,
    skills: List[str],
    experience_years: Optional[float] = None,
    job_titles: Optional[List[str]] = None,
    education: Optional[str] = None,
) -> Resume:
    """Create a new resume entry.

    Args:
        db: Database session
        skills: List of skills
        experience_years: Years of experience
        job_titles: List of previous job titles
        education: Education information

    Returns:
        Resume: Created resume object
    """
    resume = Resume(
        skills=skills,
        experience_years=experience_years,
        job_titles=job_titles or [],
        education=education,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_resume(db: Session, resume_id: int) -> Optional[Resume]:
    """Get a resume by ID.

    Args:
        db: Database session
        resume_id: Resume ID

    Returns:
        Resume or None if not found
    """
    return db.query(Resume).filter(Resume.id == resume_id).first()


def get_latest_resume(db: Session) -> Optional[Resume]:
    """Get the most recently updated resume.

    Args:
        db: Database session

    Returns:
        Resume or None if no resumes exist
    """
    return db.query(Resume).order_by(Resume.updated_at.desc()).first()


def update_resume(
    db: Session,
    resume_id: int,
    skills: Optional[List[str]] = None,
    experience_years: Optional[float] = None,
    job_titles: Optional[List[str]] = None,
    education: Optional[str] = None,
) -> Optional[Resume]:
    """Update an existing resume.

    Args:
        db: Database session
        resume_id: Resume ID
        skills: Updated skills list
        experience_years: Updated experience years
        job_titles: Updated job titles
        education: Updated education

    Returns:
        Resume or None if not found
    """
    resume = get_resume(db, resume_id)
    if not resume:
        return None

    if skills is not None:
        resume.skills = skills
    if experience_years is not None:
        resume.experience_years = experience_years
    if job_titles is not None:
        resume.job_titles = job_titles
    if education is not None:
        resume.education = education

    resume.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(resume)
    return resume


def delete_resume(db: Session, resume_id: int) -> bool:
    """Delete a resume by ID.

    Args:
        db: Database session
        resume_id: Resume ID

    Returns:
        True if deleted, False if not found
    """
    resume = get_resume(db, resume_id)
    if not resume:
        return False

    db.delete(resume)
    db.commit()
    return True


# JobPosting CRUD operations
def create_job_posting(
    db: Session,
    title: str,
    company: str,
    posting_date: datetime,
    description: Optional[str] = None,
    required_skills: Optional[List[str]] = None,
    experience_required: Optional[float] = None,
    source: Optional[str] = None,
    url: Optional[str] = None,
    location: Optional[str] = None,
    salary: Optional[str] = None,
) -> JobPosting:
    """Create a new job posting.

    Args:
        db: Database session
        title: Job title
        company: Company name
        posting_date: Date job was posted
        description: Job description
        required_skills: List of required skills
        experience_required: Required years of experience
        source: Source of job posting (api, csv, pdf, etc.)
        url: Job posting URL
        location: Job location
        salary: Salary information (e.g., "$120K-$150K")

    Returns:
        JobPosting: Created job posting object
    """
    job = JobPosting(
        title=title,
        company=company,
        posting_date=posting_date,
        description=description,
        required_skills=required_skills or [],
        experience_required=experience_required,
        source=source,
        url=url,
        location=location,
        salary=salary,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_posting(db: Session, job_id: int) -> Optional[JobPosting]:
    """Get a job posting by ID.

    Args:
        db: Database session
        job_id: Job posting ID

    Returns:
        JobPosting or None if not found
    """
    return db.query(JobPosting).filter(JobPosting.id == job_id).first()


def get_job_postings(
    db: Session, skip: int = 0, limit: int = 100
) -> List[JobPosting]:
    """Get all job postings with pagination.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of JobPosting objects
    """
    return db.query(JobPosting).offset(skip).limit(limit).all()


def get_job_by_title_company(
    db: Session, title: str, company: str
) -> Optional[JobPosting]:
    """Get a job posting by normalized title and company name.

    Uses SQL-level comparison for efficiency instead of loading all jobs
    into memory. Case-insensitive matching with whitespace normalization.

    Args:
        db: Database session
        title: Job title (will be normalized)
        company: Company name (will be normalized)

    Returns:
        JobPosting or None if not found
    """
    normalized_title = title.strip().lower()
    normalized_company = company.strip().lower()

    return db.query(JobPosting).filter(
        func.lower(func.trim(JobPosting.title)) == normalized_title,
        func.lower(func.trim(JobPosting.company)) == normalized_company
    ).first()


def get_existing_job_keys(
    db: Session, pairs: List[Tuple[str, str]], batch_size: int = 100
) -> Set[Tuple[str, str]]:
    """Check which (title, company) pairs already exist in the database.

    Performs a bulk query instead of N individual lookups.
    Chunks into batches to stay within SQLite OR-clause limits.

    Args:
        db: Database session
        pairs: List of (title, company) tuples (already normalized/lowered)
        batch_size: Max pairs per query batch

    Returns:
        Set of (normalized_title, normalized_company) tuples that exist
    """
    existing = set()
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i:i + batch_size]
        conditions = [
            and_(
                func.lower(func.trim(JobPosting.title)) == title,
                func.lower(func.trim(JobPosting.company)) == company,
            )
            for title, company in batch
        ]
        rows = db.query(
            func.lower(func.trim(JobPosting.title)),
            func.lower(func.trim(JobPosting.company)),
        ).filter(or_(*conditions)).all()
        existing.update((r[0], r[1]) for r in rows)
    return existing


def get_existing_jobs_for_repost_check(
    db: Session, pairs: List[Tuple[str, str]], batch_size: int = 100
) -> dict:
    """Return existing job info keyed by (title, company) for repost detection.

    Returns:
        Dict mapping (normalized_title, normalized_company) →
        (job_id, posting_date, repost_count)
    """
    result = {}
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i:i + batch_size]
        conditions = [
            and_(
                func.lower(func.trim(JobPosting.title)) == title,
                func.lower(func.trim(JobPosting.company)) == company,
            )
            for title, company in batch
        ]
        rows = db.query(
            func.lower(func.trim(JobPosting.title)),
            func.lower(func.trim(JobPosting.company)),
            JobPosting.id,
            JobPosting.posting_date,
            JobPosting.repost_count,
        ).filter(or_(*conditions)).all()
        for title, company, job_id, posting_date, repost_count in rows:
            result[(title, company)] = (job_id, posting_date, repost_count or 0)
    return result


def deduplicate_existing_jobs(db: Session) -> int:
    """Remove duplicate job postings, keeping the one with the highest ID.

    For each group of jobs sharing the same (lower(title), lower(company)),
    keeps the row with the highest ID and deletes the rest. Also reassigns
    any match_results or application_tracking from deleted rows to the kept row.

    Args:
        db: Database session

    Returns:
        Number of duplicate rows deleted
    """
    import logging
    logger = logging.getLogger(__name__)

    # Find duplicate groups: (lower_title, lower_company) with count > 1
    dupes = (
        db.query(
            func.lower(func.trim(JobPosting.title)).label('ltitle'),
            func.lower(func.trim(JobPosting.company)).label('lcompany'),
            func.count(JobPosting.id).label('cnt'),
        )
        .group_by('ltitle', 'lcompany')
        .having(func.count(JobPosting.id) > 1)
        .all()
    )

    if not dupes:
        return 0

    total_deleted = 0
    for ltitle, lcompany, cnt in dupes:
        # Get all IDs for this group, ordered by id desc (keep highest)
        rows = (
            db.query(JobPosting.id)
            .filter(
                func.lower(func.trim(JobPosting.title)) == ltitle,
                func.lower(func.trim(JobPosting.company)) == lcompany,
            )
            .order_by(JobPosting.id.desc())
            .all()
        )
        keep_id = rows[0][0]
        delete_ids = [r[0] for r in rows[1:]]

        # Reassign match_results from duplicates to the kept row
        db.query(MatchResult).filter(
            MatchResult.job_id.in_(delete_ids)
        ).update({MatchResult.job_id: keep_id}, synchronize_session=False)

        # Reassign application_tracking from duplicates to the kept row
        # Delete conflicting tracking entries first (kept row may already have one)
        existing_tracking = db.query(ApplicationTracking).filter(
            ApplicationTracking.job_id == keep_id
        ).first()
        if existing_tracking:
            db.query(ApplicationTracking).filter(
                ApplicationTracking.job_id.in_(delete_ids)
            ).delete(synchronize_session=False)
        else:
            # Move the first duplicate's tracking to the kept row, delete rest
            first_dupe_tracking = db.query(ApplicationTracking).filter(
                ApplicationTracking.job_id.in_(delete_ids)
            ).first()
            if first_dupe_tracking:
                first_dupe_tracking.job_id = keep_id
                other_ids = [d for d in delete_ids if d != first_dupe_tracking.job_id]
                if other_ids:
                    db.query(ApplicationTracking).filter(
                        ApplicationTracking.job_id.in_(other_ids)
                    ).delete(synchronize_session=False)

        # Delete the duplicate job postings
        db.query(JobPosting).filter(
            JobPosting.id.in_(delete_ids)
        ).delete(synchronize_session=False)

        total_deleted += len(delete_ids)

    db.commit()
    logger.info(f"Deduplicated job_postings: removed {total_deleted} duplicate rows from {len(dupes)} groups")
    return total_deleted


def delete_job_posting(db: Session, job_id: int) -> bool:
    """Delete a job posting by ID.

    Args:
        db: Database session
        job_id: Job posting ID

    Returns:
        True if deleted, False if not found
    """
    job = get_job_posting(db, job_id)
    if not job:
        return False

    db.delete(job)
    db.commit()
    return True


# MatchResult CRUD operations
def create_match_result(
    db: Session,
    job_id: int,
    resume_id: int,
    match_score: float,
    matching_skills: Optional[List[str]] = None,
    experience_alignment: Optional[str] = None,
    engine_version: Optional[str] = None,
    gemini_score: Optional[float] = None,
    gemini_reasoning: Optional[str] = None,
    missing_domains: Optional[List[str]] = None,
    **kwargs
) -> MatchResult:
    """Create a new match result.

    Args:
        db: Database session
        job_id: Job posting ID
        resume_id: Resume ID
        match_score: Match score (0-100)
        matching_skills: List of matched skills
        experience_alignment: Experience alignment description
        engine_version: Matching engine version (e.g., "1.0.0")
        gemini_score: Gemini LLM re-ranking score (0-100)
        gemini_reasoning: Gemini's explanation for the match quality
        missing_domains: List of required domains the candidate lacks
        **kwargs: Additional AI matching fields (ai_match_score, ai_strengths, etc.)

    Returns:
        MatchResult: Created match result object
    """
    match = MatchResult(
        job_id=job_id,
        resume_id=resume_id,
        match_score=match_score,
        matching_skills=matching_skills or [],
        experience_alignment=experience_alignment,
        engine_version=engine_version,
        gemini_score=gemini_score,
        gemini_reasoning=gemini_reasoning,
        missing_domains=missing_domains,
        # AI matching fields (pass through from kwargs)
        ai_match_score=kwargs.get('ai_match_score'),
        skills_score=kwargs.get('skills_score'),
        experience_score=kwargs.get('experience_score'),
        seniority_fit=kwargs.get('seniority_fit'),
        domain_score=kwargs.get('domain_score'),
        ai_strengths=kwargs.get('ai_strengths'),
        ai_concerns=kwargs.get('ai_concerns'),
        ai_recommendations=kwargs.get('ai_recommendations'),
        skill_matches=kwargs.get('skill_matches'),
        skill_gaps_detailed=kwargs.get('skill_gaps_detailed'),
        match_engine=kwargs.get('match_engine', 'nlp'),
        match_confidence=kwargs.get('match_confidence'),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def get_match_result(db: Session, match_id: int) -> Optional[MatchResult]:
    """Get a match result by ID.

    Args:
        db: Database session
        match_id: Match result ID

    Returns:
        MatchResult or None if not found
    """
    return db.query(MatchResult).filter(MatchResult.id == match_id).first()


def get_matches_by_resume(
    db: Session, resume_id: int, min_score: Optional[float] = None
) -> List[MatchResult]:
    """Get all match results for a resume.

    Args:
        db: Database session
        resume_id: Resume ID
        min_score: Optional minimum match score filter

    Returns:
        List of MatchResult objects ordered by score descending
    """
    query = db.query(MatchResult).filter(MatchResult.resume_id == resume_id)

    if min_score is not None:
        query = query.filter(MatchResult.match_score >= min_score)

    return query.order_by(MatchResult.match_score.desc()).all()


def get_all_matches(
    db: Session, skip: int = 0, limit: int = 100, min_score: Optional[float] = None
) -> List[MatchResult]:
    """Get all match results with pagination and filtering.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        min_score: Optional minimum match score

    Returns:
        List of MatchResult objects with joined job_posting and resume
    """
    query = db.query(MatchResult).options(
        joinedload(MatchResult.job_posting),
        joinedload(MatchResult.resume)
    )

    if min_score is not None:
        query = query.filter(MatchResult.match_score >= min_score)

    return query.order_by(MatchResult.match_score.desc(), MatchResult.generated_date.desc()).offset(skip).limit(limit).all()


def get_matches_by_job(db: Session, job_id: int) -> List[MatchResult]:
    """Get all match results for a job posting.

    Args:
        db: Database session
        job_id: Job posting ID

    Returns:
        List of MatchResult objects
    """
    return db.query(MatchResult).filter(MatchResult.job_id == job_id).all()


def get_unnotified_matches(
    db: Session, min_score: float = 70.0
) -> List[MatchResult]:
    """Get match results for jobs that haven't been notified yet.

    This checks if the JOB has ever been notified (across any MatchResult),
    not just if this specific MatchResult was notified. This prevents
    duplicate notifications for the same job across multiple search runs.

    Args:
        db: Database session
        min_score: Minimum match score to include (default: 70%)

    Returns:
        List of MatchResult objects for jobs never notified before
    """

    # Subquery: job_ids that have been notified before
    notified_job_ids = (
        db.query(MatchResult.job_id)
        .filter(MatchResult.notified_at.isnot(None))
        .distinct()
        .subquery()
    )

    # Get the best (highest score) match for each unnotified job
    # Using a subquery to get max score per job, then joining
    best_match_subquery = (
        db.query(
            MatchResult.job_id,
            func.max(MatchResult.match_score).label('max_score')
        )
        .filter(MatchResult.match_score >= min_score)
        .filter(~MatchResult.job_id.in_(notified_job_ids))
        .group_by(MatchResult.job_id)
        .subquery()
    )

    # Get the actual MatchResult objects for the best matches
    # Use joinedload to eagerly load related objects and avoid N+1 queries
    return (
        db.query(MatchResult)
        .options(
            joinedload(MatchResult.job_posting),
            joinedload(MatchResult.resume)
        )
        .join(
            best_match_subquery,
            (MatchResult.job_id == best_match_subquery.c.job_id) &
            (MatchResult.match_score == best_match_subquery.c.max_score)
        )
        .order_by(MatchResult.match_score.desc())
        .all()
    )


def mark_matches_as_notified(
    db: Session, match_ids: List[int]
) -> int:
    """Mark match results as notified.

    Args:
        db: Database session
        match_ids: List of match result IDs to mark as notified

    Returns:
        Number of matches updated
    """
    if not match_ids:
        return 0

    updated = (
        db.query(MatchResult)
        .filter(MatchResult.id.in_(match_ids))
        .update({MatchResult.notified_at: datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    return updated


# ApplicationTracking CRUD operations
def create_application_tracking(
    db: Session,
    job_id: int,
    status: str = "Saved",
    notes: Optional[str] = None,
) -> ApplicationTracking:
    """Create a new application tracking entry.

    Args:
        db: Database session
        job_id: Job posting ID
        status: Application status (Saved, Applied, Interviewing, Rejected, Offer)
        notes: Optional notes

    Returns:
        ApplicationTracking: Created tracking object
    """
    tracking = ApplicationTracking(
        job_id=job_id,
        status=status,
        notes=notes,
    )
    db.add(tracking)
    db.commit()
    db.refresh(tracking)
    return tracking


def get_application_tracking(
    db: Session, tracking_id: int
) -> Optional[ApplicationTracking]:
    """Get application tracking by ID.

    Args:
        db: Database session
        tracking_id: Tracking ID

    Returns:
        ApplicationTracking or None if not found
    """
    return (
        db.query(ApplicationTracking)
        .filter(ApplicationTracking.id == tracking_id)
        .first()
    )


def get_application_tracking_by_job(
    db: Session, job_id: int
) -> Optional[ApplicationTracking]:
    """Get application tracking by job ID.

    Args:
        db: Database session
        job_id: Job posting ID

    Returns:
        ApplicationTracking or None if not found
    """
    return (
        db.query(ApplicationTracking)
        .filter(ApplicationTracking.job_id == job_id)
        .first()
    )


def get_applications_by_status(
    db: Session, status: str
) -> List[ApplicationTracking]:
    """Get all applications with a specific status.

    Args:
        db: Database session
        status: Status to filter by

    Returns:
        List of ApplicationTracking objects
    """
    return (
        db.query(ApplicationTracking)
        .filter(ApplicationTracking.status == status)
        .order_by(ApplicationTracking.status_date.desc())
        .all()
    )


def update_application_status(
    db: Session,
    job_id: int,
    status: str,
    notes: Optional[str] = None,
) -> Optional[ApplicationTracking]:
    """Update application tracking status.

    Args:
        db: Database session
        job_id: Job posting ID
        status: New status
        notes: Optional notes to add/update

    Returns:
        ApplicationTracking or None if not found
    """
    tracking = get_application_tracking_by_job(db, job_id)
    if not tracking:
        return None

    tracking.status = status
    tracking.status_date = datetime.utcnow()
    if notes is not None:
        tracking.notes = notes

    db.commit()
    db.refresh(tracking)
    return tracking


def delete_application_tracking(db: Session, tracking_id: int) -> bool:
    """Delete application tracking by ID.

    Args:
        db: Database session
        tracking_id: Tracking ID

    Returns:
        True if deleted, False if not found
    """
    tracking = get_application_tracking(db, tracking_id)
    if not tracking:
        return False

    db.delete(tracking)
    db.commit()
    return True
