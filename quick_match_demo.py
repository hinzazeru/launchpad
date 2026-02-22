#!/usr/bin/env python
"""Quick demo - parse resume and match against existing jobs (no API call)."""

import sys
from src.database.db import SessionLocal, init_db
from src.resume.parser import parse_resume
from src.resume.storage import save_resume_from_file
from src.database import crud


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def simple_skill_match(resume_skills, job_skills):
    """Simple keyword-based skill matching."""
    if not job_skills:
        return 1.0, []
    if not resume_skills:
        return 0.0, []

    resume_lower = [s.lower() for s in resume_skills]
    job_lower = [s.lower() for s in job_skills]

    matches = []
    for job_skill in job_lower:
        for resume_skill in resume_lower:
            if job_skill in resume_skill or resume_skill in job_skill:
                matches.append(resume_skills[resume_lower.index(resume_skill)])
                break

    score = len(matches) / len(job_skills) if job_skills else 0
    return score, list(set(matches))


def calculate_experience_match(resume_years, job_years):
    """Calculate experience match."""
    if not job_years:
        return 1.0
    if resume_years >= job_years:
        return 1.0

    deficit = job_years - resume_years
    if deficit <= 1:
        return 0.8
    elif deficit <= 2:
        return 0.6
    elif deficit <= 3:
        return 0.4
    else:
        return 0.2


def main():
    print_header("QUICK JOB MATCHER DEMO")
    print("Using existing jobs from database (from earlier API test)")
    print()

    # Initialize database
    print("Step 1: Initialize Database")
    init_db()
    db = SessionLocal()
    print("* Database ready")

    # Parse resume
    print("\nStep 2: Parse Resume")
    try:
        resume_data = parse_resume("resume.txt")
        print(f"* Resume parsed successfully")
        print(f"  - Skills: {len(resume_data.get('skills', []))}")
        print(f"  - Experience: {resume_data.get('experience_years', 0)} years")

        resume = save_resume_from_file(db, "resume.txt")
        print(f"* Resume saved (ID: {resume.id})")
    except Exception as e:
        print(f"X Error: {e}")
        db.close()
        sys.exit(1)

    # Get jobs from database
    print("\nStep 3: Load Jobs from Database")
    jobs = crud.get_job_postings(db)
    print(f"* Found {len(jobs)} jobs in database")

    if len(jobs) == 0:
        print("\nX No jobs found. Please run test_apify_connection.py first.")
        db.close()
        sys.exit(1)

    # Match jobs (simple keyword matching)
    print("\nStep 4: Match Jobs (Keyword-Based)")
    print("Calculating: 50% skills + 50% experience...")

    matches = []
    for job in jobs:
        skills_score, matching_skills = simple_skill_match(
            resume.skills or [],
            job.required_skills or []
        )

        exp_score = calculate_experience_match(
            resume.experience_years or 0,
            job.experience_required
        )

        overall = (skills_score * 0.5) + (exp_score * 0.5)

        matches.append({
            'job': job,
            'overall_score': overall,
            'skills_score': skills_score,
            'experience_score': exp_score,
            'matching_skills': matching_skills
        })

    # Sort by score
    matches.sort(key=lambda x: x['overall_score'], reverse=True)
    print(f"* Matched {len(matches)} jobs")

    # Display top matches
    print_header("TOP JOB MATCHES")

    for i, match in enumerate(matches[:10], 1):
        separator = "=" * 80
        print(f"\n{separator}")
        print(f"Match #{i}: {match['job_title']} at {match['company']}")
        print(separator)

        marker = " (TOP MATCH!)" if match['overall_score'] >= 0.7 else ""
        print(f"  Overall Score:     {match['overall_score']:.1%}{marker}")
        print(f"  Skills Match:      {match['skills_score']:.1%}")
        print(f"  Experience Match:  {match['experience_score']:.1%}")
        print(f"  Location:          {job.location}")
        print(f"  URL:               {job.url[:70]}...")

        if match['matching_skills']:
            print(f"\n  Matching Skills ({len(match['matching_skills'])}):")
            for skill in match['matching_skills'][:5]:
                print(f"    - {skill}")

    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"  Total jobs:           {len(matches)}")
    print(f"  High matches (>=70%): {len([m for m in matches if m['overall_score'] >= 0.7])}")
    print(f"  Good matches (>=50%): {len([m for m in matches if m['overall_score'] >= 0.5])}")
    if matches:
        print(f"  Average score:        {sum(m['overall_score'] for m in matches) / len(matches):.1%}")
    print("=" * 80)

    db.close()
    print("\n* Demo completed!")
    print("\nNote: This used simple keyword matching.")
    print("For semantic NLP matching, run: python run_matching_demo.py")
    print()


if __name__ == "__main__":
    main()
