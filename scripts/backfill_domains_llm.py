#!/usr/bin/env python3
"""Backfill job domains using Gemini LLM extraction.

This script processes existing jobs in the database that haven't been
analyzed by the LLM yet, extracting domain information with higher accuracy.

Usage:
    python scripts/backfill_domains_llm.py [--limit N] [--dry-run] [--reprocess-all]

Options:
    --limit N       Process only N jobs (default: all)
    --dry-run       Show what would be processed without making changes
    --reprocess-all Reprocess all jobs, including those already processed by LLM
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.db import SessionLocal
from src.database.models import JobPosting
from src.integrations.gemini_client import GeminiDomainExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_domains(limit: int = None, dry_run: bool = False, reprocess_all: bool = False):
    """Process jobs with Gemini LLM for domain extraction.

    Args:
        limit: Maximum number of jobs to process (None = all)
        dry_run: If True, don't save changes
        reprocess_all: If True, reprocess jobs that already have LLM extraction
    """
    # Initialize Gemini
    extractor = GeminiDomainExtractor()

    if not extractor.is_available():
        logger.error("Gemini is not available. Check your config.yaml:")
        logger.error("  gemini:")
        logger.error("    enabled: true")
        logger.error("    api_key: YOUR_API_KEY")
        return

    session = SessionLocal()

    try:
        # Query jobs to process
        query = session.query(JobPosting).filter(JobPosting.description.isnot(None))

        if not reprocess_all:
            # Only process jobs not yet processed by LLM
            query = query.filter(
                (JobPosting.domain_extraction_method != 'llm') |
                (JobPosting.domain_extraction_method.is_(None))
            )

        if limit:
            query = query.limit(limit)

        jobs = query.all()
        total = len(jobs)

        if total == 0:
            logger.info("No jobs to process. All jobs already have LLM extraction.")
            return

        logger.info(f"Processing {total} jobs with Gemini...")
        if dry_run:
            logger.info("DRY RUN - no changes will be saved")

        processed = 0
        errors = 0

        for i, job in enumerate(jobs, 1):
            logger.info(f"[{i}/{total}] {job.title} @ {job.company}")

            if dry_run:
                logger.info(f"  Would extract domains for job ID {job.id}")
                processed += 1
                continue

            try:
                # Extract domains using Gemini
                result = extractor.extract_domains(
                    description=job.description,
                    company=job.company,
                    title=job.title
                )

                domains = result.get('domains', [])
                reasoning = result.get('reasoning', '')

                # Update job
                job.required_domains = domains if domains else None
                job.domain_extraction_method = 'llm'

                logger.info(f"  Domains: {domains}")
                logger.info(f"  Reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else f"  Reasoning: {reasoning}")

                processed += 1

                # Commit every 10 jobs to avoid losing progress
                if processed % 10 == 0:
                    session.commit()
                    logger.info(f"  Committed {processed} jobs so far...")

            except Exception as e:
                logger.error(f"  Error processing job {job.id}: {e}")
                errors += 1

        # Final commit
        if not dry_run:
            session.commit()

        logger.info("=" * 60)
        logger.info(f"Completed: {processed} processed, {errors} errors")

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill job domains using Gemini LLM')
    parser.add_argument('--limit', type=int, help='Process only N jobs')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--reprocess-all', action='store_true', help='Reprocess all jobs including LLM-processed')

    args = parser.parse_args()

    backfill_domains(
        limit=args.limit,
        dry_run=args.dry_run,
        reprocess_all=args.reprocess_all
    )


if __name__ == '__main__':
    main()
