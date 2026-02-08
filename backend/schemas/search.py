"""Pydantic schemas for the Search API.

Defines request/response models for the background job queue search architecture:
- POST /search/jobs returns immediately with search_id
- GET /search/jobs/{search_id} returns current progress for polling
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class SearchJobCreate(BaseModel):
    """Request schema for starting a new job search.

    This is the same as the existing JobSearchRequest but used for
    the new background job queue architecture.
    """
    keyword: str = Field(..., min_length=1, max_length=200, description="Job search keyword")
    location: str = Field(default="United States", max_length=200, description="Job location filter")
    job_type: Optional[str] = Field(default=None, description="Job type filter (fulltime, parttime, contract, etc.)")
    experience_level: Optional[str] = Field(default=None, description="Experience level filter")
    work_arrangement: Optional[str] = Field(default=None, description="Work arrangement filter (remote, hybrid, onsite)")
    max_results: int = Field(default=25, ge=1, le=100, description="Maximum jobs to fetch")
    resume_filename: str = Field(..., description="Resume filename from library")
    export_to_sheets: bool = Field(default=True, description="Export results to Google Sheets")


class SearchJobStartResponse(BaseModel):
    """Response when a search job is started.

    Returned immediately by POST /search/jobs. Client should poll
    GET /search/jobs/{search_id} for progress updates.
    """
    search_id: str = Field(..., description="UUID to poll for progress")
    status: str = Field(..., description="Initial status (always 'pending')")
    message: str = Field(..., description="Human-readable status message")


class SearchJobProgress(BaseModel):
    """Response schema for search progress polling.

    Returned by GET /search/jobs/{search_id}. Client should poll
    every 2-3 seconds until status is 'completed' or 'failed'.
    """
    search_id: str = Field(..., description="UUID of the search job")
    status: str = Field(..., description="Current status: pending, running, completed, failed")
    stage: str = Field(..., description="Current pipeline stage: initializing, fetching, importing, matching, exporting, completed, error")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage 0-100")
    message: Optional[str] = Field(default=None, description="Human-readable progress message")

    # Progress counters (populated as search progresses)
    jobs_found: Optional[int] = Field(default=None, description="Jobs found from LinkedIn")
    jobs_imported: Optional[int] = Field(default=None, description="Jobs imported to database")
    matches_found: Optional[int] = Field(default=None, description="Total matches generated")
    high_matches: Optional[int] = Field(default=None, description="High quality matches (85%+)")
    exported_count: Optional[int] = Field(default=None, description="Jobs exported to Google Sheets")

    # Final result (only when status='completed')
    result: Optional[dict] = Field(default=None, description="Full SearchResult when completed")

    # Error (only when status='failed')
    error: Optional[str] = Field(default=None, description="Error message when failed")

    # Timestamps
    created_at: datetime = Field(..., description="When search was started")
    updated_at: datetime = Field(..., description="When progress was last updated")

    class Config:
        from_attributes = True


class SearchJobListResponse(BaseModel):
    """Response schema for listing recent search jobs."""
    jobs: List[SearchJobProgress]
    total: int
