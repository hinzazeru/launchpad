"""Scheduler router for managing scheduled job searches.

Provides CRUD endpoints for scheduling automated job searches,
with integration to the WebAppScheduler service.
"""

import logging
from pathlib import Path
from typing import List
import uuid

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from src.database.db import SessionLocal, get_db
from src.database.models import ScheduledSearch, SearchPerformance

# Resume library path for validation
PROJECT_ROOT = Path(__file__).parent.parent.parent
RESUME_LIBRARY_DIR = PROJECT_ROOT / "data" / "resumes"
from backend.schemas.scheduler import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleListResponse,
    SchedulerStatus,
    ScheduleToggleResponse,
    ScheduleRunNowResponse,
    ScheduleRunHistory,
    ScheduleHistoryResponse,
)
from backend.services.webapp_scheduler import get_scheduler
from backend.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Schedule CRUD Endpoints
# ============================================================================

@router.get("/schedules", response_model=ScheduleListResponse)
@limiter.limit("200/minute")
async def list_schedules(request: Request, db: Session = Depends(get_db)):
    """List all scheduled searches."""
    schedules = db.query(ScheduledSearch).order_by(
        ScheduledSearch.created_at.desc()
    ).all()

    return ScheduleListResponse(
        schedules=[ScheduleResponse.model_validate(s) for s in schedules],
        total=len(schedules)
    )


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
@limiter.limit("60/minute")
async def create_schedule(request: Request, schedule: ScheduleCreate, db: Session = Depends(get_db)):
    """Create a new scheduled search."""
    # Validate resume file exists
    resume_path = RESUME_LIBRARY_DIR / schedule.resume_filename
    if not resume_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Resume file not found: {schedule.resume_filename}"
        )

    try:
        # Create database record
        db_schedule = ScheduledSearch(
            name=schedule.name,
            keyword=schedule.keyword,
            location=schedule.location,
            job_type=schedule.job_type,
            experience_level=schedule.experience_level,
            work_arrangement=schedule.work_arrangement,
            max_results=schedule.max_results,
            resume_filename=schedule.resume_filename,
            export_to_sheets=schedule.export_to_sheets,
            enabled=schedule.enabled,
            run_times=schedule.run_times,
            timezone=schedule.timezone,
            max_retries=schedule.max_retries,
            retry_delay_minutes=schedule.retry_delay_minutes,
            weekdays_only=schedule.weekdays_only,
        )

        db.add(db_schedule)
        db.commit()
        db.refresh(db_schedule)

        # Register with scheduler if enabled
        if schedule.enabled:
            scheduler = get_scheduler()
            if scheduler.running:
                scheduler.add_schedule(db_schedule)

        logger.info(f"Created schedule '{db_schedule.name}' (id={db_schedule.id})")

        return ScheduleResponse.model_validate(db_schedule)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
@limiter.limit("200/minute")
async def get_schedule(request: Request, schedule_id: int, db: Session = Depends(get_db)):
    """Get details of a specific schedule."""
    schedule = db.query(ScheduledSearch).filter(
        ScheduledSearch.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return ScheduleResponse.model_validate(schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
@limiter.limit("60/minute")
async def update_schedule(request: Request, schedule_id: int, schedule_update: ScheduleUpdate, db: Session = Depends(get_db)):
    """Update an existing schedule."""
    schedule = db.query(ScheduledSearch).filter(
        ScheduledSearch.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Validate resume file if being updated
    if schedule_update.resume_filename:
        resume_path = RESUME_LIBRARY_DIR / schedule_update.resume_filename
        if not resume_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Resume file not found: {schedule_update.resume_filename}"
            )

    try:
        # Update only provided fields
        update_data = schedule_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(schedule, field, value)

        db.commit()
        db.refresh(schedule)

        # Update scheduler registration
        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.update_schedule(schedule)

        logger.info(f"Updated schedule '{schedule.name}' (id={schedule.id})")

        return ScheduleResponse.model_validate(schedule)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedules/{schedule_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_schedule(request: Request, schedule_id: int, db: Session = Depends(get_db)):
    """Delete a schedule."""
    schedule = db.query(ScheduledSearch).filter(
        ScheduledSearch.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    try:
        # Remove from scheduler first
        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.remove_schedule(schedule_id)

        # Delete from database
        db.delete(schedule)
        db.commit()

        logger.info(f"Deleted schedule (id={schedule_id})")

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Schedule Actions
# ============================================================================

@router.post("/schedules/{schedule_id}/toggle", response_model=ScheduleToggleResponse)
@limiter.limit("60/minute")
async def toggle_schedule(request: Request, schedule_id: int, db: Session = Depends(get_db)):
    """Toggle a schedule's enabled status."""
    schedule = db.query(ScheduledSearch).filter(
        ScheduledSearch.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    try:
        # Toggle enabled status
        schedule.enabled = not schedule.enabled
        db.commit()
        db.refresh(schedule)

        # Update scheduler registration
        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.update_schedule(schedule)

        status_text = "enabled" if schedule.enabled else "disabled"
        logger.info(f"Schedule '{schedule.name}' (id={schedule_id}) {status_text}")

        return ScheduleToggleResponse(
            id=schedule.id,
            name=schedule.name,
            enabled=schedule.enabled,
            next_run_at=schedule.next_run_at,
            message=f"Schedule {status_text}"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to toggle schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedules/{schedule_id}/run-now", response_model=ScheduleRunNowResponse)
@limiter.limit("10/minute")
async def run_schedule_now(request: Request, schedule_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger an immediate run of a schedule.

    The search runs in the background and returns immediately with a search ID
    that can be used to track progress.
    """
    schedule = db.query(ScheduledSearch).filter(
        ScheduledSearch.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Generate search ID for tracking
    search_id = str(uuid.uuid4())

    # Get scheduler and trigger background execution
    scheduler = get_scheduler()

    if not scheduler.running:
        raise HTTPException(
            status_code=503,
            detail="Scheduler is not running"
        )

    # Run in background
    async def run_search():
        try:
            await scheduler.execute_scheduled_search(schedule_id)
        except Exception as e:
            logger.error(f"Background search failed: {e}", exc_info=True)

    background_tasks.add_task(run_search)

    logger.info(f"Triggered immediate run for schedule '{schedule.name}' (search_id={search_id})")

    return ScheduleRunNowResponse(
        id=schedule.id,
        name=schedule.name,
        message="Search started in background",
        search_id=search_id
    )


# ============================================================================
# Schedule History
# ============================================================================

@router.get("/schedules/{schedule_id}/history", response_model=ScheduleHistoryResponse)
@limiter.limit("200/minute")
async def get_schedule_history(
    request: Request,
    schedule_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get run history for a specific schedule."""
    # Verify schedule exists
    schedule = db.query(ScheduledSearch).filter(
        ScheduledSearch.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Query SearchPerformance for this schedule
    query = db.query(SearchPerformance).filter(
        SearchPerformance.schedule_id == schedule_id
    ).order_by(SearchPerformance.created_at.desc())

    total = query.count()
    runs = query.limit(limit).all()

    return ScheduleHistoryResponse(
        runs=[
            ScheduleRunHistory(
                search_id=run.search_id,
                created_at=run.created_at,
                status=run.status or 'unknown',
                total_duration_ms=run.total_duration_ms,
                jobs_fetched=run.jobs_fetched or 0,
                jobs_matched=run.jobs_matched or 0,
                high_matches=run.high_matches or 0,
                error_message=run.error_message,
            )
            for run in runs
        ],
        total=total
    )


# ============================================================================
# Scheduler Status
# ============================================================================

@router.get("/status", response_model=SchedulerStatus)
@limiter.limit("200/minute")
async def get_scheduler_status(request: Request):
    """Get the current status of the scheduler."""
    scheduler = get_scheduler()
    status = scheduler.get_status()
    
    return SchedulerStatus(
        running=status['running'],
        active_schedules=status['active_schedules'],
        next_run_at=status['next_run_at'],
        next_schedule_name=status['next_schedule_name']
    )
