#!/usr/bin/env python
"""Fetch jobs from Apify and save to database - debug version."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from src.database.db import SessionLocal, init_db
from src.importers.provider_factory import get_job_provider
from src.database import crud

def main():
    print("=" * 80)
    print("FETCH AND SAVE JOBS - DEBUG VERSION")
    print("=" * 80)

    # Initialize database
    init_db()
    db = SessionLocal()

    # Fetch jobs
    print("\nStep 1: Fetching jobs from Apify...")
    importer = get_job_provider()

    raw_jobs = importer.search_jobs(
        keywords="Product Manager",
        location="United States",
        max_results=20,
        posted_when="Past 24 hours"
    )

    print(f"* Retrieved {len(raw_jobs)} jobs from Apify")

    # Process and save jobs
    print("\nStep 2: Processing jobs...")
    saved_count = 0
    skipped_count = 0
    error_count = 0

    for i, raw_job in enumerate(raw_jobs, 1):
        try:
            # Normalize
            normalized = importer.normalize_job(raw_job)

            # Debug: Print first job details
            if i == 1:
                print(f"\nSample job #{i}:")
                print(f"  Title: {normalized.get('title', 'N/A')}")
                print(f"  Company: {normalized.get('company', 'N/A')}")
                print(f"  Location: {normalized.get('location', 'N/A')}")
                print(f"  Posting Date: {normalized.get('posting_date', 'N/A')}")
                print(f"  URL: {normalized.get('url', 'N/A')[:60]}...")

            # Check if required fields exist
            if not normalized.get('title') or not normalized.get('company'):
                print(f"  Skipping job #{i}: Missing title or company")
                skipped_count += 1
                continue

            # Check for duplicates
            existing = crud.get_job_by_title_company(
                db,
                title=normalized['title'],
                company=normalized['company']
            )

            if existing:
                print(f"  Skipping job #{i}: Duplicate ({normalized['title']} at {normalized['company']})")
                skipped_count += 1
                continue

            # Save to database (skip validation for now)
            job = crud.create_job_posting(
                db=db,
                title=normalized['title'],
                company=normalized['company'],
                location=normalized.get('location', ''),
                description=normalized.get('description', ''),
                required_skills=normalized.get('required_skills', []),
                experience_required=normalized.get('experience_required'),
                posting_date=normalized.get('posting_date') or datetime.utcnow(),
                url=normalized.get('url', ''),
                source='api'
            )
            saved_count += 1

            if saved_count <= 3:
                print(f"  ✓ Saved job #{i}: {job.title} at {job.company}")

        except Exception as e:
            print(f"  X Error with job #{i}: {e}")
            error_count += 1

    print(f"\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Total jobs retrieved: {len(raw_jobs)}")
    print(f"  Jobs saved:           {saved_count}")
    print(f"  Jobs skipped:         {skipped_count}")
    print(f"  Errors:               {error_count}")
    print("=" * 80)

    db.close()


if __name__ == "__main__":
    main()
