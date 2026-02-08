#!/usr/bin/env python3
"""
Simplified Skill Gap Cleanup Script (No GeminiMatcher dependency)

This version extracts just the filtering logic without requiring the full GeminiMatcher class,
avoiding the pydantic import error.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict

# Add project root to path
sys.path.insert(0, '/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch')

from src.database.db import SessionLocal
from src.database.models import MatchResult, Resume
from sqlalchemy import and_

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_functional_role_gap(gap_skill: str, candidate_titles: List[str]) -> bool:
    """Check if a skill gap is actually a functional role the candidate already has.
    
    This is a standalone version of the logic from GeminiMatcher._is_functional_role_gap()
    """
    gap_lower = gap_skill.lower()
    
    # Define functional role mappings (gap keyword -> title keywords)
    role_mappings = {
        "product manag": ["product"],
        "software eng": ["engineer", "developer", "software"],
        "data scien": ["data scien"],
        "data engineer": ["data eng"],
        "data analy": ["data analy", "analyst"],
        "machine learning eng": ["ml eng", "machine learning"],
        "devops": ["devops", "sre", "site reliability"],
        "frontend": ["frontend", "front-end", "front end"],
        "backend": ["backend", "back-end", "back end"],
        "full stack": ["full stack", "fullstack"],
        "ui/ux": ["ui/ux", "ux design", "ui design"],
        "graphic design": ["graphic design", "visual design"],
        "marketing": ["marketing"],
        "sales": ["sales"],
        "business analy": ["business analy"],
        "project manag": ["project manag"],
        "program manag": ["program manag"],
        "scrum master": ["scrum master", "agile coach"],
    }
    
    # Check if gap matches any functional role the candidate has
    for gap_keyword, title_keywords in role_mappings.items():
        if gap_keyword in gap_lower:
            # Check if candidate has this role in their titles
            for title in candidate_titles:
                title_lower = title.lower()
                if any(keyword in title_lower for keyword in title_keywords):
                    return True  # Filter this gap - candidate has it
    
    return False  # Keep this gap - it's legitimate


def cleanup_skill_gaps(days: int = 7, min_score: int = 90, dry_run: bool = False):
    """Clean up skill gaps in recent high-score matches."""
    session = SessionLocal()
    
    try:
        # Calculate date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Query high-score matches from last N days
        matches = session.query(MatchResult).filter(
            and_(
                MatchResult.generated_date >= date_threshold,
                MatchResult.gemini_score >= min_score
            )
        ).all()
        
        logger.info(f"🔍 Found {len(matches)} matches from last {days} days with Gemini score >= {min_score}")
        
        if not matches:
            logger.info("No matches to process.")
            return
        
        # Group matches by resume
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
            resume = session.query(Resume).filter(Resume.id == resume_id).first()
            if not resume:
                logger.warning(f"Resume {resume_id} not found, skipping")
                continue
            
            candidate_titles = resume.job_titles or []
            if not candidate_titles:
                logger.debug(f"Resume {resume_id} has no job titles, skipping")
                continue
            
            logger.info(f"\n📋 Processing {len(resume_matches)} match(es) for resume {resume_id}")
            logger.info(f"   Candidate titles: {', '.join(candidate_titles[:3])}")
            
            # Process each match
            for match in resume_matches:
                # Parse skill_gaps_detailed (could be JSON string or list)
                try:
                    if isinstance(match.skill_gaps_detailed, str):
                        original_gaps = json.loads(match.skill_gaps_detailed)
                    else:
                        original_gaps = match.skill_gaps_detailed or []
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"  ⚠️  Match {match.id}: Cannot parse skill_gaps_detailed")
                    continue
                
                if not original_gaps:
                    continue
                
                # Filter gaps
                filtered_gaps = []
                removed = []
                
                for gap in original_gaps:
                    gap_skill = gap.get('skill', '').strip()
                    
                    if is_functional_role_gap(gap_skill, candidate_titles):
                        removed.append(gap_skill)
                    else:
                        filtered_gaps.append(gap)
                
                # Check if anything changed
                if removed:
                    total_gaps_removed += len(removed)
                    
                    logger.info(f"  📝 Match ID {match.id} (Score: {match.gemini_score})")
                    logger.info(f"     Removed: {', '.join(removed)}")
                    logger.info(f"     {len(original_gaps)} gaps → {len(filtered_gaps)} gaps")
                    
                    if not dry_run:
                        # Update - serialize back to JSON string if needed
                        if isinstance(match.skill_gaps_detailed, str):
                            match.skill_gaps_detailed = json.dumps(filtered_gaps)
                        else:
                            match.skill_gaps_detailed = filtered_gaps
                        total_updated += 1
        
        # Commit changes
        if not dry_run and total_updated > 0:
            session.commit()
            logger.info(f"\n✅ Successfully updated {total_updated} match(es)")
            logger.info(f"   Removed {total_gaps_removed} functional role gap(s)")
        elif dry_run:
            logger.info(f"\n🔍 DRY RUN: Would update {total_updated} match(es)")
            logger.info(f"   Would remove {total_gaps_removed} functional role gap(s)")
        else:
            logger.info("\nℹ️  No matches needed updating")
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Clean up skill gaps in recent matches')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without saving')
    parser.add_argument('--days', type=int, default=7, help='Days back to process (default: 7)')
    parser.add_argument('--min-score', type=int, default=90, help='Min score (default: 90)')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Retroactive Skill Gap Cleanup")
    logger.info("=" * 60)
    logger.info(f"Date range: Last {args.days} days")
    logger.info(f"Min Gemini score: {args.min_score}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")
    logger.info("=" * 60)
    
    cleanup_skill_gaps(days=args.days, min_score=args.min_score, dry_run=args.dry_run)
    
    logger.info("\n✨ Cleanup complete!")


if __name__ == "__main__":
    main()
