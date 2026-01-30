import sys
import os
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.database.db import get_db_session
from src.database.models import JobPosting
from src.integrations.gemini_client import get_gemini_extractor

def main():
    print("Initiating summary backfill...")
    db = get_db_session()
    extractor = get_gemini_extractor()
    
    if not extractor or not extractor.is_available():
        print("Gemini extractor not available.")
        return

    # Filter: Posted in last 14 days, no summary
    cutoff = datetime.utcnow() - timedelta(days=14)
    query = db.query(JobPosting).filter(
        JobPosting.posting_date >= cutoff,
        JobPosting.summary == None
    )
    
    count = query.count()
    print(f"Found {count} jobs posted since {cutoff.strftime('%Y-%m-%d')} needing summaries.")
    
    if count == 0:
        print("All recent jobs have summaries!")
        return

    print(f"Starting backfill for {count} jobs (rate limit: ~4s/job)...")
    
    # Process
    jobs = query.all()
    for i, job in enumerate(jobs):
        try:
            print(f"[{i+1}/{count}] {job.title[:40]}...", end=" ", flush=True)
            summary = extractor.summarize_job(job.description or "", job.company, job.title)
            
            if summary:
                job.summary = summary
                db.commit()
                print("Done")
            else:
                print("Skipped (Empty)")
            
            time.sleep(4.1)

        except Exception as e:
            print(f"Error: {e}")
            db.rollback()

if __name__ == "__main__":
    main()
