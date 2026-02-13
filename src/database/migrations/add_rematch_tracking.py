"""Migration: Add smart rematch tracking columns to scheduled_searches.

This migration adds:
1. resume_content_hash - SHA256 of resume file to detect resume changes
2. last_engine_version - Engine version used in last run to detect config changes

These columns enable incremental matching: only newly imported jobs are matched
unless the resume or engine version changed, which triggers a full rematch.
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


def migrate_up():
    """Add rematch tracking columns to scheduled_searches."""
    logger.info("Starting migration: add_rematch_tracking")

    with engine.connect() as connection:
        # 1. Add resume_content_hash column
        if check_column_exists(connection, "scheduled_searches", "resume_content_hash"):
            logger.info("Column 'resume_content_hash' already exists. Skipping.")
        else:
            logger.info("Adding 'resume_content_hash' column to scheduled_searches...")
            connection.execute(text(
                "ALTER TABLE scheduled_searches ADD COLUMN resume_content_hash VARCHAR(64)"
            ))
            logger.info("Column 'resume_content_hash' added successfully.")

        # 2. Add last_engine_version column
        if check_column_exists(connection, "scheduled_searches", "last_engine_version"):
            logger.info("Column 'last_engine_version' already exists. Skipping.")
        else:
            logger.info("Adding 'last_engine_version' column to scheduled_searches...")
            connection.execute(text(
                "ALTER TABLE scheduled_searches ADD COLUMN last_engine_version VARCHAR(20)"
            ))
            logger.info("Column 'last_engine_version' added successfully.")

        connection.commit()
        logger.info("Migration completed successfully!")


def migrate_down():
    """Remove rematch tracking columns.

    Note: SQLite doesn't support DROP COLUMN directly.
    """
    logger.warning("Downward migration not fully supported for SQLite.")
    logger.warning("Columns 'resume_content_hash' and 'last_engine_version' cannot be dropped in SQLite.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
