#!/usr/bin/env python3
"""
Re-rank recent jobs using Gemini AI.

This script fetches jobs from the database that were posted in the last N days
and re-ranks them using Gemini for more accurate scoring.

Usage:
    python3 scripts/rerank_recent_jobs.py [--days 7] [--min-score 65] [--force]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.db import SessionLocal
from src.database.models import JobPosting, MatchResult, Resume
from src.integrations.gemini_client import GeminiMatchReranker


def main():
    parser = argparse.ArgumentParser(description='Re-rank recent jobs using Gemini AI')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    parser.add_argument('--min-score', type=float, default=65, help='Minimum NLP match score to consider (default: 65)')
    parser.add_argument('--force', action='store_true', help='Re-rank even if already has gemini_score')
    parser.add_argument('--limit', type=int, default=50, help='Maximum jobs to re-rank (default: 50)')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("Gemini Re-Ranking Script")
    print(f"{'='*60}")
    print(f"Looking back: {args.days} days")
    print(f"Min NLP score: {args.min_score}")
    print(f"Force re-rank: {args.force}")
    print(f"Limit: {args.limit}")
    print()

    # Initialize Gemini reranker
    reranker = GeminiMatchReranker()
    if not reranker.is_available():
        print("ERROR: Gemini reranker not available. Check config.yaml:")
        print("  - gemini.enabled: true")
        print("  - gemini.api_key: <your-api-key>")
        print("  - matching.gemini_rerank.enabled: true")
        sys.exit(1)

    print(f"✓ Gemini reranker available (model: {reranker.model_name})")

    # Get database session
    session = SessionLocal()

    try:
        # Get cutoff date
        cutoff_date = datetime.now() - timedelta(days=args.days)
        print(f"✓ Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M')}")

        # Query jobs needing re-ranking
        query = (
            session.query(JobPosting, MatchResult, Resume)
            .join(MatchResult, JobPosting.id == MatchResult.job_id)
            .join(Resume, MatchResult.resume_id == Resume.id)
            .filter(JobPosting.posting_date >= cutoff_date)
            .filter(MatchResult.match_score >= args.min_score)
        )

        if not args.force:
            query = query.filter(MatchResult.gemini_score.is_(None))

        query = query.order_by(MatchResult.match_score.desc())
        query = query.limit(args.limit)

        results = query.all()
        print(f"✓ Found {len(results)} jobs to re-rank")

        if not results:
            print("\nNo jobs found matching criteria.")
            return

        # Get resume skills from first result (assuming single resume)
        _, _, resume = results[0]
        resume_skills = resume.skills or []
        experience_years = resume.experience_years or 0
        print(f"✓ Resume skills: {len(resume_skills)} skills, {experience_years} years experience")

        print(f"\n{'='*60}")
        print("Starting re-ranking...")
        print(f"{'='*60}\n")

        success_count = 0
        error_count = 0

        for i, (job, match, _) in enumerate(results):
            print(f"[{i+1}/{len(results)}] {job.title[:40]} @ {job.company[:20]}...")
            
            # Build match dict for reranker
            match_dict = {
                'job_id': job.id,
                'job_title': job.title,
                'company': job.company,
                'location': job.location or '',
                'description': job.description or '',
                'overall_score': match.match_score / 100,  # Convert to 0-1
            }

            # Evaluate with Gemini
            result = reranker._evaluate_match(
                match=match_dict,
                resume_skills=resume_skills,
                experience_years=experience_years,
                resume_domains=[]
            )

            if result.get('score') is not None:
                # Update match result
                match.gemini_score = result['score']
                match.gemini_reasoning = result.get('reasoning')
                # Update missing_domains if provided
                if result.get('gaps'):
                    match.missing_domains = result.get('gaps', [])
                
                session.commit()
                
                print(f"    ✓ Score: {result['score']:.2f} | {result.get('reasoning', '')[:50]}...")
                success_count += 1
            else:
                print(f"    ✗ Failed to get Gemini score")
                error_count += 1

        print(f"\n{'='*60}")
        print("Re-ranking Complete!")
        print(f"{'='*60}")
        print(f"✓ Successfully re-ranked: {success_count}")
        print(f"✗ Errors: {error_count}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    main()
