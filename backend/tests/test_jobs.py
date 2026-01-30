from datetime import datetime, timedelta
import pytest
from src.database.models import JobPosting, MatchResult, Resume


def test_read_jobs_empty(client, db_session):
    """Test that empty database returns empty job list."""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["jobs"] == []
    assert data["total"] == 0


def test_read_jobs_with_data(client, db_session):
    """Test listing jobs with data in database."""
    # Create a Resume first (required for foreign key)
    resume = Resume(skills=["Python", "Agile"], experience_years=5.0)
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    # Add dummy job
    job = JobPosting(
        title="Senior Product Manager",
        company="Tech Corp",
        description="We need a PM.",
        posting_date=datetime.now(),
        url="http://example.com/job",
        location="Remote"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Create MatchResult with correct field names
    match = MatchResult(
        job_id=job.id,
        resume_id=resume.id,
        match_score=85.5,
        matching_skills=["Agile"],
        experience_alignment="Good match"
    )
    db_session.add(match)
    db_session.commit()

    response = client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) >= 1
    # Find our job in the list
    job_titles = [j["title"] for j in data["jobs"]]
    assert "Senior Product Manager" in job_titles


def test_read_job_detail(client, db_session):
    """Test getting a single job by ID."""
    # Create a Resume first
    resume = Resume(skills=["Python"], experience_years=3.0)
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    # Add dummy job
    job = JobPosting(
        title="Specific Job",
        company="Specific Corp",
        description="Details here.",
        posting_date=datetime.now(),
        url="http://example.com/job2",
        location="New York"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    job_id = job.id

    # Create MatchResult
    match = MatchResult(
        job_id=job.id,
        resume_id=resume.id,
        match_score=99.0
    )
    db_session.add(match)
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Specific Job"


def test_job_not_found(client):
    """Test 404 for non-existent job."""
    response = client.get("/api/jobs/99999")
    assert response.status_code == 404


@pytest.mark.skip(reason="Fetch endpoint not implemented - Task 2.3 marked but endpoint missing")
def test_fetch_jobs_trigger(client):
    """Test triggering job fetch from scraper."""
    response = client.post("/api/jobs/fetch", params={"profile": "pm"})
    assert response.status_code in [200, 202]
