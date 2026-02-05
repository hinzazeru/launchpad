#!/usr/bin/env python
"""Demo script to parse resume, fetch jobs, and run matching engine."""

import sys
from datetime import datetime
from src.database.db import SessionLocal, init_db
from src.resume.parser import parse_resume
from src.resume.storage import save_resume_from_file
from src.importers.provider_factory import get_job_provider
from src.importers.validators import validate_job_posting, normalize_job_data
from src.database import crud
from src.database.models import JobPosting
from src.matching.engine import JobMatcher


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def main():
    """Run the matching demo."""

    print_header("LINKEDIN JOB MATCHER - DEMO")
    print("This demo will:")
    print("  1. Parse your resume from resume.txt")
    print("  2. Fetch Product Manager jobs from LinkedIn (via Apify)")
    print("  3. Match jobs against your resume using NLP")
    print("  4. Display top matches ranked by relevance")
    print()

    # Initialize database
    print_header("Step 1: Initialize Database")
    init_db()
    print("* Database initialized")

    # Parse and save resume
    print_header("Step 2: Parse Resume")
    resume_path = "resume.txt"

    try:
        resume_data = parse_resume(resume_path)

        print(f"* Resume parsed successfully")
        print(f"  - Skills extracted: {len(resume_data.get('skills', []))} skills")
        print(f"  - Experience: {resume_data.get('experience_years', 0)} years")
        print(f"  - Job titles: {len(resume_data.get('job_titles', []))} titles")
        print(f"  - Education: {resume_data.get('education', 'Not found')}")

        print("\nTop skills identified:")
        for skill in resume_data.get('skills', [])[:10]:
            print(f"  - {skill}")

    except Exception as e:
        print(f"X Error parsing resume: {e}")
        sys.exit(1)

    # Save resume to database
    print_header("Step 3: Save Resume to Database")
    db = SessionLocal()

    try:
        resume = save_resume_from_file(db, resume_path)
        print(f"* Resume saved to database (ID: {resume.id})")

    except Exception as e:
        print(f"X Error saving resume: {e}")
        db.close()
        sys.exit(1)

    # Fetch jobs from Apify
    print_header("Step 4: Fetch Jobs from LinkedIn via Apify")
    print("Searching for: Product Manager jobs")
    print("Location: United States")
    print("Max results: 20")
    print("Posted: Past 24 hours")
    print("\nThis may take 30-60 seconds...")

    try:
        importer = get_job_provider()

        raw_jobs = importer.search_jobs(
            keywords="Product Manager",
            location="United States",
            max_results=20,
            posted_when="Past 24 hours",
            job_type="Full-time"
        )

        print(f"\n* Retrieved {len(raw_jobs)} jobs from Apify")

        # Normalize and save jobs to database
        print("\nProcessing and saving jobs to database...")
        saved_jobs = []

        for raw_job in raw_jobs:
            # Normalize
            normalized = importer.normalize_job(raw_job)
            normalized = normalize_job_data(normalized)

            # Validate
            is_valid, error = validate_job_posting(normalized, check_freshness=True)

            if is_valid:
                # Check for duplicates
                existing = crud.get_job_by_title_company(
                    db,
                    title=normalized['title'],
                    company=normalized['company']
                )

                if not existing:
                    # Save to database
                    job = crud.create_job_posting(
                        db=db,
                        title=normalized['title'],
                        company=normalized['company'],
                        location=normalized.get('location', ''),
                        description=normalized.get('description', ''),
                        required_skills=normalized.get('required_skills', []),
                        experience_required=normalized.get('experience_required'),
                        posting_date=normalized['posting_date'],
                        url=normalized.get('url', ''),
                        source='api'
                    )
                    saved_jobs.append(job)

        print(f"* Saved {len(saved_jobs)} unique jobs to database")

        if len(saved_jobs) == 0:
            print("\n! No new jobs to match. Exiting.")
            db.close()
            sys.exit(0)

    except Exception as e:
        print(f"X Error fetching jobs: {e}")
        db.close()
        sys.exit(1)

    # Run matching engine
    print_header("Step 5: Run Matching Engine")
    print("Analyzing job matches using NLP-based semantic similarity...")
    print("Weighting: 50% skills match + 50% experience match")

    try:
        matcher = JobMatcher()

        # Get all jobs from database
        all_jobs = crud.get_job_postings(db)
        print(f"\nTotal jobs in database: {len(all_jobs)}")

        # Match jobs against resume
        matches = matcher.match_jobs(
            resume=resume,
            jobs=all_jobs,
            min_score=0.0,  # Get all matches for demo
            top_n=None
        )

        print(f"* Matched {len(matches)} jobs")

        # Save match results
        saved_results = matcher.save_match_results(
            db_session=db,
            resume_id=resume.id,
            match_results=matches
        )

        print(f"* Saved {len(saved_results)} match results to database")

    except Exception as e:
        print(f"X Error during matching: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        sys.exit(1)

    # Display results
    print_header("Step 6: Top Job Matches")

    if len(matches) == 0:
        print("No matches found.")
    else:
        # Filter to matches with score >= 0.5 for display
        high_matches = [m for m in matches if m['overall_score'] >= 0.5]

        if len(high_matches) == 0:
            print("No high-quality matches (score >= 0.5) found.")
            print(f"\nShowing all {len(matches)} matches:")
            high_matches = matches[:10]  # Show top 10

        for i, match in enumerate(high_matches[:10], 1):
            separator = "=" * 80
            print(f"\n{separator}")
            print(f"Match #{i}: {match['job_title']} at {match['company']}")
            print(separator)
            score_marker = " (TOP MATCH!)" if match['overall_score'] >= 0.7 else ""
            print(f"  Overall Score:     {match['overall_score']:.1%}{score_marker}")
            print(f"  Skills Match:      {match['skills_score']:.1%}")
            print(f"  Experience Match:  {match['experience_score']:.1%}")
            print(f"  Location:          {match['location']}")
            print(f"  URL:               {match['url'][:70]}...")

            # Show matching skills
            if match['matching_skills']:
                print(f"\n  Matching Skills ({len(match['matching_skills'])}):")
                for skill in match['matching_skills'][:5]:
                    print(f"    - {skill}")
                if len(match['matching_skills']) > 5:
                    print(f"    ... and {len(match['matching_skills']) - 5} more")

            # Show skill gaps
            if match['skill_gaps']:
                print(f"\n  Skill Gaps ({len(match['skill_gaps'])}):")
                for gap in match['skill_gaps'][:3]:
                    print(f"    - {gap}")
                if len(match['skill_gaps']) > 3:
                    print(f"    ... and {len(match['skill_gaps']) - 3} more")

    print("\n" + "=" * 80)
    print(f"  SUMMARY")
    print("=" * 80)
    print(f"  Total jobs analyzed:      {len(matches)}")
    print(f"  High matches (>=70%):     {len([m for m in matches if m['overall_score'] >= 0.7])}")
    print(f"  Good matches (>=50%):     {len([m for m in matches if m['overall_score'] >= 0.5])}")
    print(f"  Average match score:      {sum(m['overall_score'] for m in matches) / len(matches):.1%}")
    print("=" * 80)

    # Close database
    db.close()

    print("\n* Demo completed successfully!")
    print("\nNext steps:")
    print("  - Review top matches in detail")
    print("  - Adjust matching weights in config.yaml if needed")
    print("  - Set up email notifications for high matches")
    print("  - Schedule automated job searches")
    print()


if __name__ == "__main__":
    main()
