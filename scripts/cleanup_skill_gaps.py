#!/usr/bin/env python3
"""
Retroactive Skill Gap Cleanup Script

This script applies the new skill gap filtering logic to existing high-score matches
from the last 7 days, removing functional role gaps that candidates clearly possess
through their job history.

Usage:
    python scripts/cleanup_skill_gaps.py [--dry-run] [--days 7] [--min-score 90]
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, '/Users/hinza/Documents/[20]_Project/ClaudeProjects/LinkedInJobSearch')

from src.database.db import SessionLocal
from src.database.models import MatchResult, Resume
from src.matching.gemini_matcher import GeminiMatcher
from sqlalchemy import and_

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def filter_skill_gaps(
    skill_gaps_detailed: List[Dict],
    candidate_titles: List[str],
    matcher: GeminiMatcher
) -> List[Dict]:
    """Apply filtering logic to skill gaps.
    
    Args:
        skill_gaps_detailed: List of skill gap dicts with {skill, importance, transferable_from}
        candidate_titles: List of candidate's job titles
        matcher: GeminiMatcher instance for filtering logic
        
    Returns:
        Filtered list of skill gaps
    """
    if not skill_gaps_detailed or not candidate_titles:
        return skill_gaps_detailed or []
    
    filtered_gaps = []
    removed_count = 0
    
    for gap in skill_gaps_detailed:
        gap_skill = gap.get('skill', '').strip()
        
        # Apply the same filtering logic from GeminiMatcher
        if matcher._is_functional_role_gap(gap_skill, candidate_titles):
            logger.debug(f"  🗑️  Removing: {gap_skill}")
            removed_count += 1
        else:
            filtered_gaps.append(gap)
    
    if removed_count > 0:
        logger.info(f"  ✅ Removed {removed_count} functional role gap(s)")
    
    return filtered_gaps


def cleanup_skill_gaps(days: int = 7, min_score: int = 90, dry_run: bool = False):
    """Clean up skill gaps in recent high-score matches.
    
    Args:
        days: Number of days back to process
        min_score: Minimum Gemini score to process
        dry_run: If True, show what would be changed without saving
    """
    session = SessionLocal()
    matcher = GeminiMatcher()
    
    try:
        # Calculate date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Query high-score matches from last N days
        # Note: Using gemini_score (not overall_score) and generated_date (not created_at)
        matches = session.query(MatchResult).filter(
            and_(
                MatchResult.generated_date >= date_threshold,
                MatchResult.gemini_score >= min_score
            )
        ).all()
        
        logger.info(f"🔍 Found {len(matches)} matches from last {days} days with score >= {min_score}")
        
        if not matches:
            logger.info("No matches to process.")
            return
        
        # Group matches by resume to get candidate titles once per resume
        matches_by_resume = {}
        for match in matches:
            resume_id = match.resume_id
            if resume_id not in matches_by_resume:
                matches_by_resume[resume_id] = []
            matches_by_resume[resume_id].append(match)
        
        total_updated = 0
        total_gaps_removed = 0
        
        # Process each resume's matches
        for resume_id, resume_matches in matches_by_resume.items():
            # Get candidate's resume and job titles
            resume = session.query(Resume).filter(Resume.id == resume_id).first()
            if not resume:
                logger.warning(f"Resume {resume_id} not found, skipping")
                continue
            
            candidate_titles = resume.job_titles or []
            if not candidate_titles:
                logger.debug(f"Resume {resume_id} has no job titles, skipping filtering")
                continue
            
            logger.info(f"\n📋 Processing {len(resume_matches)} match(es) for resume {resume_id}")
            logger.info(f"   Candidate titles: {', '.join(candidate_titles[:3])}")
            
            # Process each match for this resume
            for match in resume_matches:
                original_gaps = match.skill_gaps_detailed or []
                if not original_gaps:
                    continue
                
                # Apply filtering
                filtered_gaps = filter_skill_gaps(
                    original_gaps,
                    candidate_titles,
                    matcher
                )
                
                # Check if anything changed
                if len(filtered_gaps) < len(original_gaps):
                    gaps_removed = len(original_gaps) - len(filtered_gaps)
                    total_gaps_removed += gaps_removed
                    
                    logger.info(f"  📝 Match ID {match.id} (Gemini Score: {match.gemini_score})")
                    logger.info(f"     Before: {len(original_gaps)} gaps → After: {len(filtered_gaps)} gaps")
                    
                    if not dry_run:
                        # Update the match
                        match.skill_gaps_detailed = filtered_gaps
        
        # Commit changes
        if not dry_run and total_updated > 0:
            session.commit()
            logger.info(f"\n✅ Successfully updated {total_updated} match(es)")
            logger.info(f"   Removed {total_gaps_removed} functional role gap(s) total")
        elif dry_run:
            logger.info(f"\n🔍 DRY RUN: Would update {total_updated} match(es)")
            logger.info(f"   Would remove {total_gaps_removed} functional role gap(s) total")
        else:
            logger.info("\nℹ️  No matches needed updating")
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description='Clean up skill gaps in recent high-score matches'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without saving'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days back to process (default: 7)'
    )
    parser.add_argument(
        '--min-score',
        type=int,
        default=90,
        help='Minimum overall score to process (default: 90)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Retroactive Skill Gap Cleanup")
    logger.info("=" * 60)
    logger.info(f"Date range: Last {args.days} days")
    logger.info(f"Min score: {args.min_score}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")
    logger.info("=" * 60)
    
    cleanup_skill_gaps(
        days=args.days,
        min_score=args.min_score,
        dry_run=args.dry_run
    )
    
    logger.info("\n✨ Cleanup complete!")


if __name__ == "__main__":
    main()
