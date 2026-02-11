"""Database connection and initialization module."""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create declarative base for models
Base = declarative_base()

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///linkedin_job_matcher.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables and run lightweight migrations."""
    from src.database.models import Resume, JobPosting, MatchResult, ApplicationTracking

    # Deduplicate existing jobs before creating/enforcing the unique constraint
    _deduplicate_jobs_if_needed()

    Base.metadata.create_all(bind=engine)

    # Lightweight column migrations for SQLite (ALTER TABLE ADD COLUMN is safe to retry)
    if "sqlite" in DATABASE_URL:
        _migrate_sqlite()


def _migrate_sqlite():
    """Add missing columns to existing SQLite tables.

    SQLAlchemy's create_all() only creates new tables, not new columns.
    Each migration is idempotent — ALTER TABLE ADD COLUMN fails silently
    if the column already exists.
    """
    migrations = [
        "ALTER TABLE search_jobs ADD COLUMN cancellation_requested BOOLEAN DEFAULT 0",
        "ALTER TABLE scheduled_searches ADD COLUMN max_retries INTEGER DEFAULT 2",
        "ALTER TABLE scheduled_searches ADD COLUMN retry_delay_minutes INTEGER DEFAULT 10",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                # Column already exists — safe to ignore
                pass


def _deduplicate_jobs_if_needed():
    """Remove duplicate job postings before the unique constraint is enforced.

    Only runs if the job_postings table already exists (not on first startup).
    Idempotent — does nothing if no duplicates are found.
    """
    import logging
    from sqlalchemy import inspect

    logger = logging.getLogger(__name__)
    inspector = inspect(engine)

    # Skip if table doesn't exist yet (first run)
    if 'job_postings' not in inspector.get_table_names():
        return

    session = SessionLocal()
    try:
        from src.database.crud import deduplicate_existing_jobs
        removed = deduplicate_existing_jobs(session)
        if removed > 0:
            logger.info(f"Pre-migration dedup: removed {removed} duplicate job postings")
    except Exception as e:
        logger.warning(f"Job deduplication check failed (non-fatal): {e}")
        session.rollback()
    finally:
        session.close()


def get_db():
    """Get database session.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """Get a database session directly (for non-generator usage).

    Returns:
        Session: SQLAlchemy database session
    """
    return SessionLocal()
