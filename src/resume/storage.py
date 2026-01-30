"""Resume storage module for saving and retrieving resumes from database."""

from typing import Optional
from sqlalchemy.orm import Session
from src.resume.parser import parse_resume
from src.database import crud
from src.database.models import Resume


def save_resume_from_file(db: Session, file_path: str) -> Resume:
    """Parse resume file and save to database.

    Args:
        db: Database session
        file_path: Path to resume file

    Returns:
        Resume: Created resume object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported
    """
    # Parse resume
    parsed_data = parse_resume(file_path)

    # Create resume in database
    resume = crud.create_resume(
        db=db,
        skills=parsed_data['skills'],
        experience_years=parsed_data['experience_years'],
        job_titles=parsed_data['job_titles'],
        education=parsed_data['education'],
    )

    return resume


def update_resume_from_file(db: Session, resume_id: int, file_path: str) -> Optional[Resume]:
    """Parse resume file and update existing resume in database.

    Args:
        db: Database session
        resume_id: Resume ID to update
        file_path: Path to resume file

    Returns:
        Resume: Updated resume object or None if not found

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported
    """
    # Parse resume
    parsed_data = parse_resume(file_path)

    # Update resume in database
    resume = crud.update_resume(
        db=db,
        resume_id=resume_id,
        skills=parsed_data['skills'],
        experience_years=parsed_data['experience_years'],
        job_titles=parsed_data['job_titles'],
        education=parsed_data['education'],
    )

    return resume


def get_active_resume(db: Session) -> Optional[Resume]:
    """Get the most recently updated resume (active resume).

    Args:
        db: Database session

    Returns:
        Resume: Latest resume or None if no resumes exist
    """
    return crud.get_latest_resume(db)


def get_resume_by_id(db: Session, resume_id: int) -> Optional[Resume]:
    """Get resume by ID.

    Args:
        db: Database session
        resume_id: Resume ID

    Returns:
        Resume or None if not found
    """
    return crud.get_resume(db, resume_id)
