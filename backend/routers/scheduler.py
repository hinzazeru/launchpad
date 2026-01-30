"""Scheduler router for managing scheduled job searches.

Provides CRUD endpoints for scheduling automated job searches,
with integration to the WebAppScheduler service.
"""

import logging
from typing import List
import uuid

from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from src.database.db import SessionLocal
from src.database.models import ScheduledSearch
from backend.schemas.scheduler import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleListResponse,
    SchedulerStatus,
    ScheduleToggleResponse,
    ScheduleRunNowResponse,
)
from backend.services.webapp_scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Schedule CRUD Endpoints
# ============================================================================

@router.get("/schedules", response_model=ScheduleListResponse)
async def list_schedules():
    """List all scheduled searches."""
    db = SessionLocal()
    try:
        schedules = db.query(ScheduledSearch).order_by(
            ScheduledSearch.created_at.desc()
        ).all()
        
        return ScheduleListResponse(
            schedules=[ScheduleResponse.model_validate(s) for s in schedules],
            total=len(schedules)
        )
    finally:
        db.close()


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(schedule: ScheduleCreate):
    """Create a new scheduled search."""
    db = SessionLocal()
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
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: int):
    """Get details of a specific schedule."""
    db = SessionLocal()
    try:
        schedule = db.query(ScheduledSearch).filter(
            ScheduledSearch.id == schedule_id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return ScheduleResponse.model_validate(schedule)
    finally:
        db.close()


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: int, schedule_update: ScheduleUpdate):
    """Update an existing schedule."""
    db = SessionLocal()
    try:
        schedule = db.query(ScheduledSearch).filter(
            ScheduledSearch.id == schedule_id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
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
    finally:
        db.close()


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int):
    """Delete a schedule."""
    db = SessionLocal()
    try:
        schedule = db.query(ScheduledSearch).filter(
            ScheduledSearch.id == schedule_id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
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
    finally:
        db.close()


# ============================================================================
# Schedule Actions
# ============================================================================

@router.post("/schedules/{schedule_id}/toggle", response_model=ScheduleToggleResponse)
async def toggle_schedule(schedule_id: int):
    """Toggle a schedule's enabled status."""
    db = SessionLocal()
    try:
        schedule = db.query(ScheduledSearch).filter(
            ScheduledSearch.id == schedule_id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
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
    finally:
        db.close()


@router.post("/schedules/{schedule_id}/run-now", response_model=ScheduleRunNowResponse)
async def run_schedule_now(schedule_id: int, background_tasks: BackgroundTasks):
    """Trigger an immediate run of a schedule.
    
    The search runs in the background and returns immediately with a search ID
    that can be used to track progress.
    """
    db = SessionLocal()
    try:
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
                logger.error(f"Background search failed: {e}")
        
        background_tasks.add_task(run_search)
        
        logger.info(f"Triggered immediate run for schedule '{schedule.name}' (search_id={search_id})")
        
        return ScheduleRunNowResponse(
            id=schedule.id,
            name=schedule.name,
            message="Search started in background",
            search_id=search_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============================================================================
# Scheduler Status
# ============================================================================

@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status():
    """Get the current status of the scheduler."""
    scheduler = get_scheduler()
    status = scheduler.get_status()
    
    return SchedulerStatus(
        running=status['running'],
        active_schedules=status['active_schedules'],
        next_run_at=status['next_run_at'],
        next_schedule_name=status['next_schedule_name']
    )
