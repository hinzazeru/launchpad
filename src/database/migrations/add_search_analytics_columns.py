"""Migration: Add search analytics columns to search_performance.

This migration adds:
1. gemini_attempted - Number of Gemini match attempts
2. gemini_succeeded - Number of successful Gemini matches
3. gemini_failed - Number of failed Gemini matches
4. gemini_failure_reasons - JSON array of failure reason strings
5. rematch_type - Type of rematch ('incremental', 'full_resume', 'full_engine', 'full_both')
6. jobs_skipped - Number of jobs skipped by smart rematch
7. gemini_timing_summary - JSON object with min/max/avg/p50/p90 timing stats
"""

from sqlalchemy import text
from src.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (supports SQLite and PostgreSQL)."""
    try:
        # Try PostgreSQL first
        result = connection.execute(text(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table_name}' AND column_name = '{column_name}'"
        ))
        return result.fetchone() is not None
    except Exception:
        # Fall back to SQLite
        result = connection.execute(text(f"PRAGMA table_info({table_name})"))
        columns = [row[1] for row in result]
        return column_name in columns


COLUMNS = [
    ("gemini_attempted", "INTEGER"),
    ("gemini_succeeded", "INTEGER"),
    ("gemini_failed", "INTEGER"),
    ("gemini_failure_reasons", "TEXT"),  # JSON stored as TEXT for SQLite compat
    ("rematch_type", "VARCHAR(30)"),
    ("jobs_skipped", "INTEGER"),
    ("gemini_timing_summary", "TEXT"),  # JSON stored as TEXT for SQLite compat
]


def migrate_up():
    """Add search analytics columns to search_performance."""
    logger.info("Starting migration: add_search_analytics_columns")

    with engine.connect() as connection:
        for col_name, col_type in COLUMNS:
            if check_column_exists(connection, "search_performance", col_name):
                logger.info(f"Column '{col_name}' already exists. Skipping.")
            else:
                logger.info(f"Adding '{col_name}' column to search_performance...")
                connection.execute(text(
                    f"ALTER TABLE search_performance ADD COLUMN {col_name} {col_type}"
                ))
                logger.info(f"Column '{col_name}' added successfully.")

        connection.commit()
        logger.info("Migration completed successfully!")


def migrate_down():
    """Remove search analytics columns.

    Note: SQLite doesn't support DROP COLUMN directly.
    """
    logger.warning("Downward migration not fully supported for SQLite.")
    logger.warning("Columns cannot be dropped in SQLite.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
