"""
Data Migration Script: SQLite to PostgreSQL

Migrates all data from the local SQLite database to a PostgreSQL database.
Preserves IDs and relationships.

Usage:
    # Set the target PostgreSQL URL
    export POSTGRES_URL="postgresql://user:pass@host:5432/dbname"
    
    # Run migration
    python -m src.database.migrations.migrate_to_postgres
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from src.database.db import Base
from src.database.models import (
    Resume, JobPosting, MatchResult, ApplicationTracking,
    LikedBullet, ScheduledSearch, SearchPerformance, APICallMetric
)


# Source SQLite database
SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///linkedin_job_matcher.db")

# Target PostgreSQL database
POSTGRES_URL = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL"))

# Tables in dependency order (foreign keys point forward)
TABLES_IN_ORDER = [
    (Resume, "resumes"),
    (JobPosting, "job_postings"),
    (MatchResult, "match_results"),
    (ApplicationTracking, "application_tracking"),
    (LikedBullet, "liked_bullets"),
    (ScheduledSearch, "scheduled_searches"),
    (SearchPerformance, "search_performance"),
    (APICallMetric, "api_call_metrics"),
]


def migrate():
    """Run the migration from SQLite to PostgreSQL."""
    
    if not POSTGRES_URL or "postgresql" not in POSTGRES_URL:
        print("ERROR: POSTGRES_URL must be set to a PostgreSQL connection string")
        print("Example: export POSTGRES_URL='postgresql://user:pass@localhost:5432/linkedin_jobs'")
        sys.exit(1)
    
    print(f"Source: {SQLITE_URL}")
    print(f"Target: {POSTGRES_URL.split('@')[0]}@...")  # Hide password
    print()
    
    # Connect to both databases
    sqlite_engine = create_engine(SQLITE_URL)
    postgres_engine = create_engine(POSTGRES_URL)
    
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    sqlite_session = SqliteSession()
    postgres_session = PostgresSession()
    
    try:
        # Create tables in PostgreSQL
        print("Creating tables in PostgreSQL...")
        Base.metadata.create_all(bind=postgres_engine)
        print("✓ Tables created\n")
        
        total_migrated = 0
        
        # Pre-fetch valid resume IDs for FK validation
        valid_resume_ids = set()
        try:
            from src.database.models import Resume
            valid_resume_ids = set(r.id for r in sqlite_session.query(Resume.id).all())
            print(f"Valid resume IDs: {valid_resume_ids}")
        except:
            pass
        
        for model_class, table_name in TABLES_IN_ORDER:
            print(f"Migrating {table_name}...")
            
            # Count source rows
            source_count = sqlite_session.query(model_class).count()
            
            if source_count == 0:
                print(f"  → 0 rows (empty table)")
                continue
            
            # Check if target already has data
            target_count = postgres_session.query(model_class).count()
            if target_count > 0:
                print(f"  ⚠ Target already has {target_count} rows, skipping")
                continue
            
            # Fetch all rows from SQLite
            rows = sqlite_session.query(model_class).all()
            
            # Filter out orphaned match_results (with invalid resume_id)
            if table_name == "match_results" and valid_resume_ids:
                original_count = len(rows)
                rows = [r for r in rows if r.resume_id in valid_resume_ids]
                skipped = original_count - len(rows)
                if skipped > 0:
                    print(f"  ⚠ Skipping {skipped} orphaned records (invalid resume_id)")
            
            # Bulk insert into PostgreSQL
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                
                for row in batch:
                    # Expunge from SQLite session and make transient
                    sqlite_session.expunge(row)
                    # Convert to dict and create new object
                    row_dict = {c.key: getattr(row, c.key) 
                               for c in inspect(row).mapper.column_attrs}
                    new_obj = model_class(**row_dict)
                    postgres_session.merge(new_obj)
                
                postgres_session.flush()
            
            postgres_session.commit()
            migrated_count = postgres_session.query(model_class).count()
            print(f"  ✓ {migrated_count} rows migrated")
            total_migrated += migrated_count
        
        # Reset sequences for PostgreSQL auto-increment
        print("\nResetting PostgreSQL sequences...")
        for model_class, table_name in TABLES_IN_ORDER:
            try:
                max_id = postgres_session.execute(
                    text(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
                ).scalar()
                if max_id > 0:
                    postgres_session.execute(
                        text(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id})")
                    )
            except Exception as e:
                # Some tables might not have sequences
                pass
        postgres_session.commit()
        print("✓ Sequences reset\n")
        
        print(f"Migration complete! {total_migrated} total rows migrated.")
        
    except Exception as e:
        postgres_session.rollback()
        print(f"\nERROR: Migration failed: {e}")
        raise
    finally:
        sqlite_session.close()
        postgres_session.close()


def verify():
    """Verify migration by comparing row counts."""
    print("\nVerifying migration...")
    
    sqlite_engine = create_engine(SQLITE_URL)
    postgres_engine = create_engine(POSTGRES_URL)
    
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    sqlite_session = SqliteSession()
    postgres_session = PostgresSession()
    
    all_match = True
    
    for model_class, table_name in TABLES_IN_ORDER:
        sqlite_count = sqlite_session.query(model_class).count()
        postgres_count = postgres_session.query(model_class).count()
        
        status = "✓" if sqlite_count == postgres_count else "✗"
        if sqlite_count != postgres_count:
            all_match = False
        
        print(f"  {status} {table_name}: SQLite={sqlite_count}, PostgreSQL={postgres_count}")
    
    sqlite_session.close()
    postgres_session.close()
    
    if all_match:
        print("\n✓ All tables verified successfully!")
    else:
        print("\n⚠ Some tables have mismatched counts")
    
    return all_match


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--verify-only", action="store_true", help="Only verify, don't migrate")
    args = parser.parse_args()
    
    if args.verify_only:
        verify()
    else:
        migrate()
        verify()
