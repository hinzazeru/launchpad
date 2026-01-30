"""Migration: Add scheduled_searches table and trigger_source columns.

This migration:
1. Creates the scheduled_searches table for storing scheduled job search configurations
2. Adds trigger_source and schedule_id columns to search_performance table

Run this migration before using the scheduled search feature.
"""

from sqlalchemy import text
from src.database.db import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_table_exists(connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = connection.execute(text(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    ))
    return result.fetchone() is not None


def check_column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = connection.execute(text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result]
    return column_name in columns


def migrate_up():
    """Create scheduled_searches table and add trigger columns to search_performance."""
    logger.info("Starting migration: add_scheduled_searches")

    with engine.connect() as connection:
        # 1. Create scheduled_searches table
        if check_table_exists(connection, "scheduled_searches"):
            logger.info("Table 'scheduled_searches' already exists. Skipping table creation.")
        else:
            logger.info("Creating 'scheduled_searches' table...")
            connection.execute(text("""
                CREATE TABLE scheduled_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    keyword VARCHAR(200) NOT NULL,
                    location VARCHAR(200) DEFAULT 'Canada',
                    job_type VARCHAR(50),
                    experience_level VARCHAR(50),
                    work_arrangement VARCHAR(50),
                    max_results INTEGER DEFAULT 25,
                    resume_filename VARCHAR(255) NOT NULL,
                    export_to_sheets BOOLEAN DEFAULT 1,
                    enabled BOOLEAN DEFAULT 1,
                    run_times JSON DEFAULT '["08:00", "12:00", "16:00", "20:00"]',
                    timezone VARCHAR(50) DEFAULT 'America/Toronto',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME,
                    last_run_at DATETIME,
                    next_run_at DATETIME,
                    last_run_status VARCHAR(20)
                )
            """))
            # Create index on enabled column
            connection.execute(text(
                "CREATE INDEX ix_scheduled_searches_enabled ON scheduled_searches(enabled)"
            ))
            logger.info("Table 'scheduled_searches' created successfully.")

        # 2. Add trigger_source column to search_performance
        if check_column_exists(connection, "search_performance", "trigger_source"):
            logger.info("Column 'trigger_source' already exists. Skipping.")
        else:
            logger.info("Adding 'trigger_source' column to search_performance...")
            connection.execute(text(
                "ALTER TABLE search_performance ADD COLUMN trigger_source VARCHAR(20) DEFAULT 'manual'"
            ))
            # Create index on trigger_source
            connection.execute(text(
                "CREATE INDEX ix_search_performance_trigger_source ON search_performance(trigger_source)"
            ))
            logger.info("Column 'trigger_source' added successfully.")

        # 3. Add schedule_id foreign key column to search_performance
        if check_column_exists(connection, "search_performance", "schedule_id"):
            logger.info("Column 'schedule_id' already exists. Skipping.")
        else:
            logger.info("Adding 'schedule_id' column to search_performance...")
            connection.execute(text(
                "ALTER TABLE search_performance ADD COLUMN schedule_id INTEGER REFERENCES scheduled_searches(id) ON DELETE SET NULL"
            ))
            # Create index on schedule_id
            connection.execute(text(
                "CREATE INDEX ix_search_performance_schedule_id ON search_performance(schedule_id)"
            ))
            logger.info("Column 'schedule_id' added successfully.")

        connection.commit()
        logger.info("Migration completed successfully!")


def migrate_down():
    """Remove scheduled_searches table and trigger columns.
    
    Note: SQLite doesn't support DROP COLUMN directly.
    """
    logger.warning("Downward migration not fully supported for SQLite.")
    
    with engine.connect() as connection:
        # Drop the scheduled_searches table
        if check_table_exists(connection, "scheduled_searches"):
            logger.info("Dropping 'scheduled_searches' table...")
            connection.execute(text("DROP TABLE scheduled_searches"))
            connection.commit()
            logger.info("Table 'scheduled_searches' dropped.")
        
        logger.warning("Columns 'trigger_source' and 'schedule_id' in search_performance cannot be dropped in SQLite.")
        logger.warning("To remove them, you would need to recreate the table.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        migrate_down()
    else:
        migrate_up()
