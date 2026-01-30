"""Pydantic schemas for the Scheduler API.

Defines request/response models for CRUD operations on scheduled searches.
"""

import re
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class ScheduleBase(BaseModel):
    """Base fields shared between create and response schemas."""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable schedule name")
    keyword: str = Field(..., min_length=1, max_length=200, description="Job search keyword")
    location: str = Field(default="Canada", max_length=200, description="Job location filter")
    job_type: Optional[str] = Field(default=None, description="Job type filter")
    experience_level: Optional[str] = Field(default=None, description="Experience level filter")
    work_arrangement: Optional[str] = Field(default=None, description="Work arrangement filter")
    max_results: int = Field(default=25, ge=1, le=100, description="Maximum jobs to fetch")
    resume_filename: str = Field(..., description="Resume filename from library")
    export_to_sheets: bool = Field(default=True, description="Export results to Google Sheets")
    enabled: bool = Field(default=True, description="Whether schedule is active")
    run_times: List[str] = Field(
        default=["08:00", "12:00", "16:00", "20:00"],
        description="Daily run times in HH:MM format (24-hour)"
    )
    timezone: str = Field(default="America/Toronto", description="Timezone for run times")

    @field_validator('run_times')
    @classmethod
    def validate_run_times(cls, v: List[str]) -> List[str]:
        """Validate that all run times are in HH:MM 24-hour format."""
        pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
        for time_str in v:
            if not pattern.match(time_str):
                raise ValueError(
                    f"Invalid time format: '{time_str}'. Use HH:MM (24-hour format, e.g., '08:00', '14:30')"
                )
        return sorted(set(v))  # Remove duplicates and sort


class ScheduleCreate(ScheduleBase):
    """Request schema for creating a new scheduled search."""
    pass


class ScheduleUpdate(BaseModel):
    """Request schema for updating an existing scheduled search.
    
    All fields are optional - only provided fields will be updated.
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    keyword: Optional[str] = Field(default=None, min_length=1, max_length=200)
    location: Optional[str] = Field(default=None, max_length=200)
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    work_arrangement: Optional[str] = None
    max_results: Optional[int] = Field(default=None, ge=1, le=100)
    resume_filename: Optional[str] = None
    export_to_sheets: Optional[bool] = None
    enabled: Optional[bool] = None
    run_times: Optional[List[str]] = None
    timezone: Optional[str] = None

    @field_validator('run_times')
    @classmethod
    def validate_run_times(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate run times if provided."""
        if v is None:
            return v
        pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
        for time_str in v:
            if not pattern.match(time_str):
                raise ValueError(
                    f"Invalid time format: '{time_str}'. Use HH:MM (24-hour format)"
                )
        return sorted(set(v))


class ScheduleResponse(ScheduleBase):
    """Response schema for a scheduled search."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    """Response schema for listing all schedules."""
    schedules: List[ScheduleResponse]
    total: int


class SchedulerStatus(BaseModel):
    """Response schema for scheduler status endpoint."""
    running: bool
    active_schedules: int
    next_run_at: Optional[datetime] = None
    next_schedule_name: Optional[str] = None


class ScheduleToggleResponse(BaseModel):
    """Response schema for toggling schedule enabled status."""
    id: int
    name: str
    enabled: bool
    next_run_at: Optional[datetime] = None
    message: str


class ScheduleRunNowResponse(BaseModel):
    """Response schema for triggering an immediate run."""
    id: int
    name: str
    message: str
    search_id: str  # UUID of the triggered search for tracking
