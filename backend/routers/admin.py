"""Admin endpoints for production maintenance operations."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import get_config
from src.database.db import SessionLocal
from src.database.models import JobPosting
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
