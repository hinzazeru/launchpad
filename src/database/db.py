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
