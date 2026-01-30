"""Migration: Add engine_version column to match_results table.

This migration adds the engine_version column to the match_results table
to track which version of the matching algorithm was used for each match.

Run this migration before using the updated matching system.
"""

from sqlalchemy import text
from src.database.db import engine, SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table.

    Args:
        connection: Database connection
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        bool: True if column exists, False otherwise
    """
    # For SQLite, use PRAGMA table_info
    result = connection.execute(text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result]
    return column_name in columns


def migrate_up():
    """Add engine_version column to match_results table."""
    logger.info("Starting migration: add_engine_version_to_match_results")

    with engine.connect() as connection:
        # Check if column already exists
        if check_column_exists(connection, "match_results", "engine_version"):
            logger.info("Column 'engine_version' already exists in match_results table. Skipping migration.")
            return

        # Add the column
        logger.info("Adding 'engine_version' column to match_results table...")
        connection.execute(text(
            "ALTER TABLE match_results ADD COLUMN engine_version VARCHAR(20)"
        ))
        connection.commit()

        logger.info("Migration completed successfully!")
        logger.info("Column 'engine_version' added to match_results table.")


def migrate_down():
    """Remove engine_version column from match_results table.

    Note: SQLite doesn't support DROP COLUMN directly.
    This would require recreating the table, which is risky for production data.
    """
    logger.warning("Downward migration not supported for SQLite.")
    logger.warning("To remove engine_version column, you would need to:")
    logger.warning("1. Create a new table without the column")
    logger.warning("2. Copy data from old table to new table")
    logger.warning("3. Drop old table and rename new table")
    raise NotImplementedError("Downward migration not implemented for SQLite")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
