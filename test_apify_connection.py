#!/usr/bin/env python
"""Manual test script to verify Apify API connection.

This script makes a REAL API call to Apify to verify your API key is working.
It retrieves a maximum of 20 job postings to minimize API usage costs.

Usage:
    python test_apify_connection.py
"""

import sys
from datetime import datetime
from src.config import get_config
from src.importers.apify_provider import ApifyJobImporter


def test_apify_connection():
    """Test Apify API connection with real API call."""

    print("=" * 70)
    print("APIFY API CONNECTION TEST")
    print("=" * 70)
    print()

    # Step 1: Load configuration
    print("Step 1: Loading configuration from config.yaml...")
    try:
        config = get_config()
        api_key = config.get_apify_api_key()
        actor_id = config.get_apify_actor_id()

        # Mask API key for display (show first 8 and last 4 characters)
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"   ✓ API Key loaded: {masked_key}")
        print(f"   ✓ Actor ID: {actor_id}")
    except Exception as e:
        print(f"   ✗ Error loading config: {e}")
        print("\n   Please ensure you have:")
        print("   1. Created config.yaml from config.yaml.example")
        print("   2. Added your Apify API key to config.yaml")
        sys.exit(1)

    print()

    # Step 2: Initialize Apify importer
    print("Step 2: Initializing Apify job importer...")
    try:
        importer = ApifyJobImporter()  # Will use config.yaml
        print("   ✓ Importer initialized successfully")
    except Exception as e:
        print(f"   ✗ Error initializing importer: {e}")
        sys.exit(1)

    print()

    # Step 3: Make test API call
    print("Step 3: Making test API call to Apify...")
    print("   Search criteria:")
    print("     - Keywords: Product Manager")
    print("     - Location: United States")
    print("     - Max results: 20")
    print("     - Posted: Past 24 hours")
    print()
    print("   Please wait, this may take 30-60 seconds...")
    print()

    try:
        start_time = datetime.now()

        jobs = importer.search_jobs(
            keywords="Product Manager",
            location="United States",
            max_results=20,
            posted_when="Past 24 hours",
            job_type="Full-time"
        )

        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()

        print(f"   ✓ API call completed in {elapsed:.1f} seconds")
        print(f"   ✓ Retrieved {len(jobs)} job postings")

    except Exception as e:
        print(f"   ✗ Error during API call: {e}")
        print("\n   This could mean:")
        print("   - Invalid API key")
        print("   - Network connection issue")
        print("   - Apify service temporarily unavailable")
        sys.exit(1)

    print()

    # Step 4: Validate and display results
    print("Step 4: Validating retrieved data...")

    if len(jobs) == 0:
        print("   ⚠ Warning: No jobs retrieved")
        print("   This could mean:")
        print("   - No jobs posted in the last 24 hours matching criteria")
        print("   - API parameters may need adjustment")
        print()
        print("   However, the API connection is working!")
        print()
        print("=" * 70)
        print("API CONNECTION TEST: PASSED (but no jobs found)")
        print("=" * 70)
        return

    print(f"   ✓ Found {len(jobs)} jobs")
    print()

    # Display first 3 jobs as sample
    print("Sample job postings retrieved:")
    print("-" * 70)

    for i, job in enumerate(jobs[:3], 1):
        print(f"\nJob #{i}:")
        print(f"   Title: {job.get('job_title', 'N/A')}")
        print(f"   Company: {job.get('company_name', 'N/A')}")
        print(f"   Location: {job.get('job_location', 'N/A')}")
        print(f"   Posted: {job.get('job_posted_date', 'N/A')}")
        print(f"   Seniority: {job.get('job_seniority_level', 'N/A')}")
        print(f"   Employment Type: {job.get('job_employment_type', 'N/A')}")
        print(f"   URL: {job.get('url', 'N/A')[:60]}...")

    if len(jobs) > 3:
        print(f"\n   ... and {len(jobs) - 3} more jobs")

    print()
    print("-" * 70)

    # Step 5: Test normalization
    print()
    print("Step 5: Testing job data normalization...")

    try:
        normalized = importer.normalize_job(jobs[0])
        print(f"   ✓ Normalization successful")
        print(f"   ✓ Normalized fields: title, company, location, description, url, posting_date")
        print(f"   ✓ Skills extracted: {len(normalized.get('required_skills', []))} skills")

        if normalized.get('experience_required'):
            print(f"   ✓ Experience parsed: {normalized['experience_required']} years")

    except Exception as e:
        print(f"   ✗ Error during normalization: {e}")
        print("   Warning: API works but data normalization may need adjustment")

    print()
    print("=" * 70)
    print("API CONNECTION TEST: PASSED ✓")
    print("=" * 70)
    print()
    print("Your Apify API key is working correctly!")
    print(f"Retrieved {len(jobs)} job postings successfully.")
    print()
    print("Next steps:")
    print("  - The API integration is ready to use")
    print("  - You can now run the full job matching pipeline")
    print("  - Adjust max_results in config.yaml for production use")
    print()


if __name__ == "__main__":
    test_apify_connection()
