"""Admin endpoints for production maintenance operations."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
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


@router.post("/rematch-by-gap", dependencies=[Depends(_require_admin)])
def rematch_by_gap(skill: str = Query(..., description="Skill gap text to search for (case-insensitive)")):
    """Re-run Gemini matching for all jobs that have a specific skill gap."""
    from backend.services.matcher_service import get_job_matcher

    db = SessionLocal()
    try:
        # Find all match results where skill_gaps_detailed contains the skill (JSON text search)
        all_matches = db.query(MatchResult).filter(
            MatchResult.skill_gaps_detailed != None
        ).all()

        skill_lower = skill.lower()
        target_ids = [
            m.job_id for m in all_matches
            if skill_lower in json.dumps(m.skill_gaps_detailed or []).lower()
        ]

        if not target_ids:
            return {"status": "none_found", "skill": skill, "checked": len(all_matches)}

        logger.info(f"rematch-by-gap '{skill}': found {len(target_ids)} jobs to rematch")

        matcher = get_job_matcher()
        updated, skipped, failed = 0, 0, 0

        for job_id in target_ids:
            try:
                job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
                match_record = db.query(MatchResult).filter(MatchResult.job_id == job_id).first()
                resume = db.query(Resume).filter(Resume.id == match_record.resume_id).first()
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
                logger.info(f"  rematched job {job_id} ({job.title} @ {job.company})")
            except Exception as e:
                logger.error(f"  failed job {job_id}: {e}")
                db.rollback()
                failed += 1

        return {"skill": skill, "found": len(target_ids), "updated": updated, "skipped": skipped, "failed": failed}
    finally:
        db.close()
