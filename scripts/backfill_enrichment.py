"""One-off script to backfill Gemini enrichment for jobs missing data.

Usage:
    DATABASE_URL=<railway_url> ./venv/bin/python scripts/backfill_enrichment.py

Or with railway CLI:
    railway run --service launchpad ./venv/bin/python scripts/backfill_enrichment.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

from src.database.models import JobPosting
from src.integrations.gemini_client import get_gemini_extractor, get_requirements_extractor
from src.importers.enrichment import enrich_jobs_parallel


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: Set DATABASE_URL environment variable")
        sys.exit(1)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Find jobs missing any enrichment data
        jobs = session.query(JobPosting).filter(
            or_(
                JobPosting.summary.is_(None),
                JobPosting.structured_requirements.is_(None),
            )
        ).all()

        print(f"Found {len(jobs)} jobs missing enrichment data")
        if not jobs:
            return

        gemini_extractor = get_gemini_extractor()
        requirements_extractor = get_requirements_extractor()

        if not gemini_extractor and not requirements_extractor:
            print("ERROR: No Gemini extractors available (check GEMINI_API_KEY)")
            sys.exit(1)

        print(f"Extractors: domains/summary={'yes' if gemini_extractor else 'no'}, "
              f"requirements={'yes' if requirements_extractor else 'no'}")
        print(f"Enriching {len(jobs)} jobs with max_workers=5...")

        enriched = enrich_jobs_parallel(
            jobs, gemini_extractor, requirements_extractor, session, max_workers=5
        )
        print(f"Done! Enriched {enriched}/{len(jobs)} jobs")

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
