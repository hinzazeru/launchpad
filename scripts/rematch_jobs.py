#!/usr/bin/env python
"""Re-run job matching on existing jobs with updated scoring logic.

Usage:
    python rematch_jobs.py                           # Use default resume, last 10 days
    python rematch_jobs.py --days 7                  # Last 7 days
    python rematch_jobs.py --resume my_resume.json   # Specific resume
    python rematch_jobs.py --export                  # Export to Google Sheets
    python rematch_jobs.py --dry-run                 # Preview without saving
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import SessionLocal, init_db
from src.database.models import JobPosting
from src.matching.engine import JobMatcher
from src.resume.parser import ResumeParser
from src.config import get_config
from src.integrations.gemini_client import get_gemini_reranker

# Constants
PROJECT_ROOT = Path(__file__).parent
RESUME_DIR = PROJECT_ROOT / "data" / "resumes"


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def get_default_resume() -> Path:
    """Find the first available resume in the resumes directory."""
    if not RESUME_DIR.exists():
        return None

    for ext in ['.json', '.txt', '.md']:
        for path in RESUME_DIR.glob(f'*{ext}'):
            return path
    return None


def load_resume(resume_path: Path):
    """Load and parse a resume file, returning a Resume-like object."""
    with open(resume_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = ResumeParser()
    parsed = parser.parse_auto(content)

    # Extract flat skills list
    flat_skills = []
    for category_skills in parsed.skills.values():
        flat_skills.extend(category_skills)

    # Estimate experience years
    import re
    experience_years = 0.0
    for role in parsed.roles:
        duration = role.duration.lower()
        year_match = re.findall(r'20\d{2}', duration)
        if len(year_match) >= 2:
            try:
                years = int(year_match[-1]) - int(year_match[0])
                experience_years += max(0, years)
            except:
                pass
        elif 'year' in duration:
            num_match = re.search(r'(\d+)', duration)
            if num_match:
                experience_years += float(num_match.group(1))

    # Create Resume-like object
    class ParsedResume:
        def __init__(self, skills, experience_years, domains=None):
            self.id = 0
            self.skills = skills
            self.experience_years = experience_years
            self.domains = domains or []

    return ParsedResume(
        skills=flat_skills,
        experience_years=experience_years,
        domains=[]
    ), parsed


def main():
    parser = argparse.ArgumentParser(description='Re-run job matching with updated scoring logic')
    parser.add_argument('--days', type=int, default=10, help='Number of days to look back (default: 10)')
    parser.add_argument('--resume', type=str, help='Resume filename (from data/resumes/)')
    parser.add_argument('--export', action='store_true', help='Export results to Google Sheets')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving matches')
    parser.add_argument('--min-score', type=float, default=0.0, help='Minimum score to display (default: 0)')
    args = parser.parse_args()

    print_header("JOB RE-MATCHING WITH UPDATED SCORING")

    config = get_config()

    # Load resume
    print_header("Step 1: Load Resume")

    if args.resume:
        resume_path = RESUME_DIR / args.resume
    else:
        resume_path = get_default_resume()

    if not resume_path or not resume_path.exists():
        print(f"ERROR: Resume not found: {resume_path}")
        print(f"Available resumes in {RESUME_DIR}:")
        if RESUME_DIR.exists():
            for f in RESUME_DIR.iterdir():
                print(f"  - {f.name}")
        sys.exit(1)

    resume, parsed_data = load_resume(resume_path)
    print(f"  Resume: {resume_path.name}")
    print(f"  Skills: {len(resume.skills)}")
    print(f"  Experience: {resume.experience_years:.0f} years")

    # Query jobs
    print_header("Step 2: Query Recent Jobs")

    init_db()
    db = SessionLocal()

    try:
        cutoff_date = datetime.now() - timedelta(days=args.days)

        from sqlalchemy import or_
        jobs = db.query(JobPosting).filter(
            or_(
                JobPosting.posting_date >= cutoff_date,
                (JobPosting.posting_date.is_(None)) & (JobPosting.import_date >= cutoff_date)
            )
        ).all()

        print(f"  Found {len(jobs)} jobs from the last {args.days} days")

        if not jobs:
            print("  No jobs to match.")
            db.close()
            sys.exit(0)

        # Filter sparse descriptions
        min_desc_length = 200
        quality_jobs = [j for j in jobs if j.description and len(j.description) >= min_desc_length]
        filtered = len(jobs) - len(quality_jobs)
        if filtered > 0:
            print(f"  Filtered {filtered} jobs with descriptions < {min_desc_length} chars")
        jobs = quality_jobs

        # Run matching
        print_header("Step 3: Run Matching Engine")

        matcher = JobMatcher()
        matches = matcher.match_jobs(resume, jobs, min_score=0.0)

        print(f"  Matched {len(matches)} jobs")

        # Gemini re-ranking
        print_header("Step 4: Gemini AI Re-ranking")

        gemini = get_gemini_reranker()
        if matches and gemini and gemini.is_available():
            print("  Running Gemini analysis...")
            try:
                matches, stats = gemini.rerank_matches(
                    matches=matches,
                    resume_skills=resume.skills or [],
                    experience_years=resume.experience_years or 0,
                    resume_domains=resume.domains or []
                )
                print(f"  Gemini re-ranked {len(matches)} matches")
            except Exception as e:
                print(f"  Gemini failed: {e}")
        else:
            print("  Gemini not available, using NLP scores only")

        # Calculate blended scores
        ai_weight = config.get("matching.gemini_rerank.blend_weights.ai", 0.75)
        nlp_weight = config.get("matching.gemini_rerank.blend_weights.nlp", 0.25)

        def get_blended_score(match):
            nlp = match.get('overall_score', 0)
            ai = match.get('gemini_score')
            if ai is not None:
                return (ai * ai_weight) + (nlp * nlp_weight)
            return nlp

        matches.sort(key=get_blended_score, reverse=True)

        # Display results
        print_header("Step 5: Results Summary")

        # Score distribution
        scores = [get_blended_score(m) for m in matches]

        bands = {
            '90%+': len([s for s in scores if s >= 0.90]),
            '80-89%': len([s for s in scores if 0.80 <= s < 0.90]),
            '70-79%': len([s for s in scores if 0.70 <= s < 0.80]),
            '60-69%': len([s for s in scores if 0.60 <= s < 0.70]),
            '50-59%': len([s for s in scores if 0.50 <= s < 0.60]),
            '<50%': len([s for s in scores if s < 0.50]),
        }

        print("\n  Score Distribution:")
        print("  " + "-" * 40)
        for band, count in bands.items():
            bar = "#" * min(count, 30)
            print(f"  {band:>8}: {count:3} {bar}")
        print("  " + "-" * 40)

        avg_score = sum(scores) / len(scores) if scores else 0
        print(f"\n  Total jobs: {len(matches)}")
        print(f"  Average score: {avg_score:.1%}")
        print(f"  High matches (70%+): {bands['90%+'] + bands['80-89%'] + bands['70-79%']}")

        # Top matches
        print_header("Step 6: Top Matches")

        for i, match in enumerate(matches[:10], 1):
            score = get_blended_score(match)
            if score < args.min_score:
                continue

            gemini_str = ""
            if match.get('gemini_score') is not None:
                gemini_str = f" (AI: {match['gemini_score']:.0%})"

            print(f"\n  #{i}: {match['job_title']}")
            print(f"      Company: {match['company']}")
            print(f"      Score: {score:.1%}{gemini_str}")
            print(f"      Skills: {match['skills_score']:.0%} | Exp: {match['experience_score']:.0%}")
            if match.get('matching_skills'):
                print(f"      Matched: {', '.join(match['matching_skills'][:5])}")

        # Save matches to database
        if not args.dry_run:
            print_header("Step 7: Save to Database")

            from src.database.models import MatchResult

            # Get job IDs being rematched
            job_ids = [m['job_id'] for m in matches]

            # Delete existing matches for these jobs
            deleted = db.query(MatchResult).filter(MatchResult.job_id.in_(job_ids)).delete(synchronize_session=False)
            print(f"  Deleted {deleted} existing match records")

            # Create new matches
            saved = 0
            for match in matches:
                blended = get_blended_score(match)
                new_match = MatchResult(
                    job_id=match['job_id'],
                    resume_id=resume.id,
                    match_score=round(blended * 100, 1),  # Store as 0-100
                    matching_skills=match.get('matching_skills', []),
                    experience_alignment=match.get('experience_alignment'),
                    gemini_score=round(match['gemini_score'] * 100, 1) if match.get('gemini_score') is not None else None,
                    gemini_reasoning=match.get('gemini_reasoning'),
                    missing_domains=match.get('missing_domains', []),
                )
                db.add(new_match)
                saved += 1

            db.commit()
            print(f"  Saved {saved} new match records")

        # Export to Sheets
        if args.export and not args.dry_run:
            print_header("Step 8: Export to Google Sheets")

            try:
                from src.integrations.sheets_connector import SheetsConnector
                sheets = SheetsConnector()

                if sheets.enabled:
                    exported = sheets.export_matches_batch(matches)
                    print(f"  Exported {exported} matches to Google Sheets")

                    spreadsheet_id = config.get("sheets.spreadsheet_id")
                    if spreadsheet_id:
                        print(f"  URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
                else:
                    print("  Google Sheets not configured")
            except Exception as e:
                print(f"  Export failed: {e}")
        elif args.export:
            print("\n  [DRY RUN] Would export to Google Sheets")

        if args.dry_run:
            print("\n  [DRY RUN] No matches saved to database")

    finally:
        db.close()

    print("\n" + "=" * 70)
    print("  Re-matching complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
