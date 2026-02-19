"""Admin endpoints for production maintenance operations."""

import json
import logging
import threading
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import get_config
from src.database.db import SessionLocal
from src.database.models import JobPosting, MatchResult, Resume
from src.matching.skill_extractor import extract_salary_from_description

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    token = get_config().get("admin.token")
    if not token or not credentials or credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/backfill-salary", dependencies=[Depends(_require_admin)])
def backfill_salary():
    """Re-run salary extraction on all jobs with NULL salary."""
    db = SessionLocal()
    try:
        jobs = db.query(JobPosting).filter(
            JobPosting.salary == None,
            JobPosting.description != None,
            JobPosting.description != "",
        ).all()

        total = len(jobs)
        updated = 0
        skipped = 0

        for job in jobs:
            salary = extract_salary_from_description(job.description)
            if salary:
                job.salary = salary
                updated += 1
            else:
                skipped += 1

        if updated:
            db.commit()

        logger.info(f"backfill-salary: updated={updated}, skipped={skipped}, total={total}")
        return {"updated": updated, "skipped": skipped, "total": total}
    finally:
        db.close()


@router.post("/rematch-job/{job_id}", dependencies=[Depends(_require_admin)])
def rematch_job(job_id: int):
    """Re-run Gemini matching for a specific job and update the stored result."""
    from backend.services.matcher_service import get_job_matcher

    db = SessionLocal()
    try:
        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        match_record = db.query(MatchResult).filter(MatchResult.job_id == job_id).first()
        if not match_record:
            raise HTTPException(status_code=404, detail=f"No match result found for job {job_id}")

        resume = db.query(Resume).filter(Resume.id == match_record.resume_id).first()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        matcher = get_job_matcher()
        result = matcher.match_job(resume, job)

        if result.get("match_engine") != "gemini":
            return {"status": "skipped", "reason": "Gemini not available; NLP result unchanged"}

        # Update the stored match result with fresh Gemini data
        match_record.ai_match_score = result.get("ai_match_score")
        match_record.skills_score = result.get("ai_skills_score")
        match_record.experience_score = result.get("ai_experience_score")
        match_record.seniority_fit = result.get("ai_seniority_fit")
        match_record.domain_score = result.get("ai_domain_score")
        match_record.ai_strengths = result.get("ai_strengths")
        match_record.ai_concerns = result.get("ai_concerns")
        match_record.ai_recommendations = result.get("ai_recommendations")
        match_record.skill_matches = result.get("skill_matches")
        match_record.skill_gaps_detailed = result.get("skill_gaps_detailed")
        match_record.match_confidence = result.get("match_confidence")
        match_record.match_engine = "gemini"

        db.commit()

        gaps = result.get("skill_gaps_detailed") or []
        logger.info(f"rematch-job {job_id}: success, {len(gaps)} gaps")
        return {
            "status": "updated",
            "job_id": job_id,
            "ai_match_score": result.get("ai_match_score"),
            "skill_gaps": [g.get("skill") if isinstance(g, dict) else str(g) for g in gaps],
        }
    finally:
        db.close()


def _do_rematch(label: str, job_ids: list):
    """Background worker: rematch a list of job IDs. Runs in a thread."""
    from backend.services.matcher_service import get_job_matcher
    matcher = get_job_matcher()
    updated, skipped, failed = 0, 0, 0

    for job_id in job_ids:
        db = SessionLocal()
        try:
            job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
            match_record = db.query(MatchResult).filter(MatchResult.job_id == job_id).first()
            resume = db.query(Resume).filter(Resume.id == match_record.resume_id).first() if match_record else None
            if not job or not match_record or not resume:
                skipped += 1
                continue

            result = matcher.match_job(resume, job)
            if result.get("match_engine") != "gemini":
                skipped += 1
                continue

            match_record.ai_match_score = result.get("ai_match_score")
            match_record.skills_score = result.get("ai_skills_score")
            match_record.experience_score = result.get("ai_experience_score")
            match_record.seniority_fit = result.get("ai_seniority_fit")
            match_record.domain_score = result.get("ai_domain_score")
            match_record.ai_strengths = result.get("ai_strengths")
            match_record.ai_concerns = result.get("ai_concerns")
            match_record.ai_recommendations = result.get("ai_recommendations")
            match_record.skill_matches = result.get("skill_matches")
            match_record.skill_gaps_detailed = result.get("skill_gaps_detailed")
            match_record.match_confidence = result.get("match_confidence")
            match_record.match_engine = "gemini"
            db.commit()
            updated += 1
            logger.info(f"{label}: updated job {job_id} ({job.title} @ {job.company})")
        except Exception as e:
            logger.error(f"{label}: failed job {job_id}: {e}")
            db.rollback()
            failed += 1
        finally:
            db.close()

    logger.info(f"{label} complete: updated={updated}, skipped={skipped}, failed={failed}")


@router.post("/rematch-stale", dependencies=[Depends(_require_admin)])
def rematch_stale(background_tasks: BackgroundTasks):
    """Re-run Gemini matching for all jobs with match_engine='gemini' but no ai_match_score (stale results)."""
    db = SessionLocal()
    try:
        stale = db.query(MatchResult.job_id).filter(
            MatchResult.match_engine == "gemini",
            MatchResult.ai_match_score == None,
        ).all()
        job_ids = [r.job_id for r in stale]
    finally:
        db.close()

    if not job_ids:
        return {"status": "none_found", "queued": 0}

    t = threading.Thread(target=_do_rematch, args=("rematch-stale", job_ids), daemon=True)
    t.start()

    logger.info(f"rematch-stale: queued {len(job_ids)} jobs in background")
    return {"status": "started", "queued": len(job_ids)}


def _do_rematch_by_gap(skill: str, job_ids: list):
    _do_rematch(f"rematch-by-gap '{skill}'", job_ids)


@router.post("/rematch-by-gap", dependencies=[Depends(_require_admin)])
def rematch_by_gap(
    background_tasks: BackgroundTasks,
    skill: str = Query(..., description="Skill gap text to search for (case-insensitive)"),
):
    """Re-run Gemini matching for all jobs that have a specific skill gap (runs in background)."""
    db = SessionLocal()
    try:
        all_matches = db.query(MatchResult).filter(MatchResult.skill_gaps_detailed != None).all()
        skill_lower = skill.lower()
        target_ids = [
            m.job_id for m in all_matches
            if skill_lower in json.dumps(m.skill_gaps_detailed or []).lower()
        ]
    finally:
        db.close()

    if not target_ids:
        return {"status": "none_found", "skill": skill}

    # Run in background thread so the request returns immediately
    t = threading.Thread(target=_do_rematch_by_gap, args=(skill, target_ids), daemon=True)
    t.start()

    logger.info(f"rematch-by-gap '{skill}': queued {len(target_ids)} jobs in background")
    return {"status": "started", "skill": skill, "queued": len(target_ids)}
