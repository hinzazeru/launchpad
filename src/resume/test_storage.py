"""Unit tests for resume storage."""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.db import Base
from src.resume.storage import (
    save_resume_from_file,
    update_resume_from_file,
    get_active_resume,
    get_resume_by_id,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_resume_path():
    """Get path to sample resume fixture."""
    return os.path.join(
        os.path.dirname(__file__),
        "../../tests/fixtures/sample_resume.txt"
    )


def test_save_resume_from_file(db_session, sample_resume_path):
    """Test saving a resume from file."""
    resume = save_resume_from_file(db_session, sample_resume_path)

    assert resume is not None
    assert resume.id is not None
    assert isinstance(resume.skills, list)
    assert len(resume.skills) > 0
    assert resume.experience_years is not None
    assert resume.experience_years >= 5.0
    assert isinstance(resume.job_titles, list)
    assert len(resume.job_titles) > 0
    assert resume.education is not None


def test_save_resume_invalid_file(db_session):
    """Test saving resume with invalid file extension."""
    with pytest.raises(ValueError):
        save_resume_from_file(db_session, "resume.pdf")


def test_save_resume_missing_file(db_session):
    """Test saving resume with missing file."""
    with pytest.raises(FileNotFoundError):
        save_resume_from_file(db_session, "nonexistent.txt")


def test_update_resume_from_file(db_session, sample_resume_path):
    """Test updating an existing resume from file."""
    # First create a resume
    original_resume = save_resume_from_file(db_session, sample_resume_path)
    original_id = original_resume.id
    original_created = original_resume.created_at

    # Update the same resume
    updated_resume = update_resume_from_file(
        db_session, original_id, sample_resume_path
    )

    assert updated_resume is not None
    assert updated_resume.id == original_id
    assert updated_resume.created_at == original_created
    assert updated_resume.updated_at >= original_created


def test_update_resume_nonexistent(db_session, sample_resume_path):
    """Test updating a non-existent resume."""
    updated = update_resume_from_file(db_session, 999, sample_resume_path)
    assert updated is None


def test_get_active_resume(db_session, sample_resume_path):
    """Test getting the active (latest) resume."""
    # Create first resume
    resume1 = save_resume_from_file(db_session, sample_resume_path)

    # Create second resume
    resume2 = save_resume_from_file(db_session, sample_resume_path)

    # Get active resume (should be the latest)
    active = get_active_resume(db_session)

    assert active is not None
    assert active.id == resume2.id


def test_get_active_resume_empty_db(db_session):
    """Test getting active resume when database is empty."""
    active = get_active_resume(db_session)
    assert active is None


def test_get_resume_by_id(db_session, sample_resume_path):
    """Test getting resume by ID."""
    resume = save_resume_from_file(db_session, sample_resume_path)

    fetched = get_resume_by_id(db_session, resume.id)

    assert fetched is not None
    assert fetched.id == resume.id
    assert fetched.skills == resume.skills


def test_get_resume_by_id_not_found(db_session):
    """Test getting resume with non-existent ID."""
    fetched = get_resume_by_id(db_session, 999)
    assert fetched is None
