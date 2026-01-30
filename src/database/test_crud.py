"""Unit tests for CRUD operations."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.db import Base
from src.database.models import Resume, JobPosting, MatchResult, ApplicationTracking
from src.database import crud


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


# Resume CRUD tests
def test_create_resume(db_session):
    """Test creating a resume."""
    skills = ["Product Management", "Agile", "Scrum"]
    resume = crud.create_resume(
        db_session,
        skills=skills,
        experience_years=5.0,
        job_titles=["Product Manager", "Associate PM"],
        education="MBA",
    )

    assert resume.id is not None
    assert resume.skills == skills
    assert resume.experience_years == 5.0
    assert resume.job_titles == ["Product Manager", "Associate PM"]
    assert resume.education == "MBA"
    assert resume.created_at is not None


def test_get_resume(db_session):
    """Test getting a resume by ID."""
    resume = crud.create_resume(
        db_session, skills=["Product Management"], experience_years=3.0
    )

    fetched_resume = crud.get_resume(db_session, resume.id)
    assert fetched_resume is not None
    assert fetched_resume.id == resume.id
    assert fetched_resume.skills == ["Product Management"]


def test_get_latest_resume(db_session):
    """Test getting the latest resume."""
    resume1 = crud.create_resume(db_session, skills=["Skill1"])
    resume2 = crud.create_resume(db_session, skills=["Skill2"])

    latest = crud.get_latest_resume(db_session)
    assert latest is not None
    assert latest.id == resume2.id


def test_update_resume(db_session):
    """Test updating a resume."""
    resume = crud.create_resume(db_session, skills=["Old Skill"], experience_years=2.0)

    updated = crud.update_resume(
        db_session,
        resume.id,
        skills=["New Skill"],
        experience_years=5.0,
    )

    assert updated is not None
    assert updated.skills == ["New Skill"]
    assert updated.experience_years == 5.0
    assert updated.updated_at > updated.created_at


def test_delete_resume(db_session):
    """Test deleting a resume."""
    resume = crud.create_resume(db_session, skills=["Test"])

    result = crud.delete_resume(db_session, resume.id)
    assert result is True

    deleted = crud.get_resume(db_session, resume.id)
    assert deleted is None


# JobPosting CRUD tests
def test_create_job_posting(db_session):
    """Test creating a job posting."""
    posting_date = datetime.utcnow()
    job = crud.create_job_posting(
        db_session,
        title="Senior Product Manager",
        company="Tech Corp",
        posting_date=posting_date,
        description="Great opportunity",
        required_skills=["Product Management", "Agile"],
        experience_required=5.0,
        source="api",
        url="https://example.com/job/123",
        location="San Francisco, CA",
    )

    assert job.id is not None
    assert job.title == "Senior Product Manager"
    assert job.company == "Tech Corp"
    assert job.posting_date == posting_date
    assert job.required_skills == ["Product Management", "Agile"]
    assert job.experience_required == 5.0


def test_get_job_posting(db_session):
    """Test getting a job posting by ID."""
    job = crud.create_job_posting(
        db_session,
        title="Product Manager",
        company="Company A",
        posting_date=datetime.utcnow(),
    )

    fetched_job = crud.get_job_posting(db_session, job.id)
    assert fetched_job is not None
    assert fetched_job.id == job.id
    assert fetched_job.title == "Product Manager"


def test_get_job_postings(db_session):
    """Test getting multiple job postings with pagination."""
    for i in range(5):
        crud.create_job_posting(
            db_session,
            title=f"Job {i}",
            company=f"Company {i}",
            posting_date=datetime.utcnow(),
        )

    jobs = crud.get_job_postings(db_session, skip=0, limit=3)
    assert len(jobs) == 3

    jobs_page2 = crud.get_job_postings(db_session, skip=3, limit=3)
    assert len(jobs_page2) == 2


def test_get_job_by_title_company(db_session):
    """Test getting a job by normalized title and company."""
    crud.create_job_posting(
        db_session,
        title="Product Manager",
        company="Tech Corp",
        posting_date=datetime.utcnow(),
    )

    # Test case-insensitive search
    job = crud.get_job_by_title_company(db_session, "PRODUCT MANAGER", "tech corp")
    assert job is not None
    assert job.title == "Product Manager"
    assert job.company == "Tech Corp"

    # Test with extra whitespace
    job2 = crud.get_job_by_title_company(
        db_session, "  Product Manager  ", "  Tech Corp  "
    )
    assert job2 is not None


def test_delete_job_posting(db_session):
    """Test deleting a job posting."""
    job = crud.create_job_posting(
        db_session, title="Test Job", company="Test Co", posting_date=datetime.utcnow()
    )

    result = crud.delete_job_posting(db_session, job.id)
    assert result is True

    deleted = crud.get_job_posting(db_session, job.id)
    assert deleted is None


# MatchResult CRUD tests
def test_create_match_result(db_session):
    """Test creating a match result."""
    resume = crud.create_resume(db_session, skills=["Product Management"])
    job = crud.create_job_posting(
        db_session, title="PM", company="Company", posting_date=datetime.utcnow()
    )

    match = crud.create_match_result(
        db_session,
        job_id=job.id,
        resume_id=resume.id,
        match_score=85.5,
        matching_skills=["Product Management"],
        experience_alignment="Good match",
    )

    assert match.id is not None
    assert match.job_id == job.id
    assert match.resume_id == resume.id
    assert match.match_score == 85.5
    assert match.matching_skills == ["Product Management"]


def test_get_match_result(db_session):
    """Test getting a match result by ID."""
    resume = crud.create_resume(db_session, skills=["Test"])
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )
    match = crud.create_match_result(
        db_session, job_id=job.id, resume_id=resume.id, match_score=75.0
    )

    fetched_match = crud.get_match_result(db_session, match.id)
    assert fetched_match is not None
    assert fetched_match.match_score == 75.0


def test_get_matches_by_resume(db_session):
    """Test getting matches for a resume."""
    resume = crud.create_resume(db_session, skills=["Product Management"])
    job1 = crud.create_job_posting(
        db_session, title="Job 1", company="Co 1", posting_date=datetime.utcnow()
    )
    job2 = crud.create_job_posting(
        db_session, title="Job 2", company="Co 2", posting_date=datetime.utcnow()
    )

    crud.create_match_result(
        db_session, job_id=job1.id, resume_id=resume.id, match_score=90.0
    )
    crud.create_match_result(
        db_session, job_id=job2.id, resume_id=resume.id, match_score=70.0
    )

    # Get all matches
    matches = crud.get_matches_by_resume(db_session, resume.id)
    assert len(matches) == 2
    assert matches[0].match_score == 90.0  # Ordered by score descending

    # Get matches with minimum score
    matches_filtered = crud.get_matches_by_resume(db_session, resume.id, min_score=80.0)
    assert len(matches_filtered) == 1
    assert matches_filtered[0].match_score == 90.0


def test_get_matches_by_job(db_session):
    """Test getting matches for a job."""
    resume = crud.create_resume(db_session, skills=["Test"])
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )

    crud.create_match_result(
        db_session, job_id=job.id, resume_id=resume.id, match_score=80.0
    )

    matches = crud.get_matches_by_job(db_session, job.id)
    assert len(matches) == 1
    assert matches[0].job_id == job.id


# ApplicationTracking CRUD tests
def test_create_application_tracking(db_session):
    """Test creating application tracking."""
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )

    tracking = crud.create_application_tracking(
        db_session, job_id=job.id, status="Applied", notes="Submitted via email"
    )

    assert tracking.id is not None
    assert tracking.job_id == job.id
    assert tracking.status == "Applied"
    assert tracking.notes == "Submitted via email"


def test_get_application_tracking(db_session):
    """Test getting application tracking by ID."""
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )
    tracking = crud.create_application_tracking(db_session, job_id=job.id)

    fetched = crud.get_application_tracking(db_session, tracking.id)
    assert fetched is not None
    assert fetched.id == tracking.id


def test_get_application_tracking_by_job(db_session):
    """Test getting application tracking by job ID."""
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )
    tracking = crud.create_application_tracking(db_session, job_id=job.id)

    fetched = crud.get_application_tracking_by_job(db_session, job.id)
    assert fetched is not None
    assert fetched.job_id == job.id


def test_get_applications_by_status(db_session):
    """Test getting applications by status."""
    job1 = crud.create_job_posting(
        db_session, title="Job 1", company="Co 1", posting_date=datetime.utcnow()
    )
    job2 = crud.create_job_posting(
        db_session, title="Job 2", company="Co 2", posting_date=datetime.utcnow()
    )

    crud.create_application_tracking(db_session, job_id=job1.id, status="Applied")
    crud.create_application_tracking(db_session, job_id=job2.id, status="Applied")

    applied = crud.get_applications_by_status(db_session, "Applied")
    assert len(applied) == 2

    rejected = crud.get_applications_by_status(db_session, "Rejected")
    assert len(rejected) == 0


def test_update_application_status(db_session):
    """Test updating application status."""
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )
    tracking = crud.create_application_tracking(
        db_session, job_id=job.id, status="Saved"
    )
    original_status_date = tracking.status_date

    updated = crud.update_application_status(
        db_session, job_id=job.id, status="Applied", notes="Applied today"
    )

    assert updated is not None
    assert updated.status == "Applied"
    assert updated.notes == "Applied today"
    assert updated.status_date >= original_status_date


def test_delete_application_tracking(db_session):
    """Test deleting application tracking."""
    job = crud.create_job_posting(
        db_session, title="Job", company="Co", posting_date=datetime.utcnow()
    )
    tracking = crud.create_application_tracking(db_session, job_id=job.id)

    result = crud.delete_application_tracking(db_session, tracking.id)
    assert result is True

    deleted = crud.get_application_tracking(db_session, tracking.id)
    assert deleted is None
