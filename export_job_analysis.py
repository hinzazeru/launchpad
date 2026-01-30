#!/usr/bin/env python3
"""Export jobs and match scores for analysis.

This script exports all jobs from the database along with their match scores
to a CSV file for manual review and analysis.
"""

import csv
from datetime import datetime
from src.database.db import SessionLocal
from src.database.models import JobPosting, MatchResult, Resume

def export_jobs_to_csv(filename="job_analysis.csv"):
    """Export all jobs with match scores to CSV."""
    session = SessionLocal()

    try:
        # Get the most recent resume
        resume = session.query(Resume).order_by(Resume.created_at.desc()).first()
        if not resume:
            print("No resume found!")
            return

        print(f"Using resume ID: {resume.id}")

        # Get all jobs with their match results
        jobs = session.query(JobPosting).order_by(JobPosting.created_at.desc()).all()

        print(f"Found {len(jobs)} total jobs in database")

        # Prepare CSV data
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'Job ID',
                'Title',
                'Company',
                'Location',
                'Posted Date',
                'URL',
                'Match Score (%)',
                'Skills Score (%)',
                'Experience Score (%)',
                'Required Skills',
                'Matching Skills',
                'Missing Skills',
                'Experience Required (years)',
                'Description Preview',
                'Imported Date'
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            matched_count = 0

            for job in jobs:
                # Get match result for this job
                match = session.query(MatchResult).filter(
                    MatchResult.job_id == job.id,
                    MatchResult.resume_id == resume.id
                ).first()

                # Convert skills lists to comma-separated strings
                required_skills = ', '.join(job.required_skills) if job.required_skills else ''
                matching_skills = ', '.join(match.matching_skills) if match and match.matching_skills else ''
                missing_skills = ', '.join(match.skill_gaps) if match and match.skill_gaps else ''

                # Truncate description to first 200 chars
                description_preview = job.description[:200] + '...' if job.description and len(job.description) > 200 else job.description or ''

                row = {
                    'Job ID': job.id,
                    'Title': job.title,
                    'Company': job.company,
                    'Location': job.location or '',
                    'Posted Date': job.posting_date.strftime('%Y-%m-%d %H:%M') if job.posting_date else '',
                    'URL': job.url or '',
                    'Match Score (%)': f"{int(match.match_score)}" if match else '',
                    'Skills Score (%)': f"{int(match.skills_score * 100)}" if match else '',
                    'Experience Score (%)': f"{int(match.experience_score * 100)}" if match else '',
                    'Required Skills': required_skills,
                    'Matching Skills': matching_skills,
                    'Missing Skills': missing_skills,
                    'Experience Required (years)': job.experience_required if job.experience_required else '',
                    'Description Preview': description_preview,
                    'Imported Date': job.created_at.strftime('%Y-%m-%d %H:%M') if job.created_at else ''
                }

                writer.writerow(row)

                if match:
                    matched_count += 1

        print(f"\n✅ Exported {len(jobs)} jobs to {filename}")
        print(f"   - {matched_count} jobs have been matched")
        print(f"   - {len(jobs) - matched_count} jobs not yet matched")
        print(f"\nYou can:")
        print(f"1. Open {filename} in Excel/Numbers to review")
        print(f"2. Import it to Google Sheets for analysis")
        print(f"3. Sort by 'Match Score (%)' to see highest matches first")

    finally:
        session.close()


if __name__ == "__main__":
    export_jobs_to_csv()
