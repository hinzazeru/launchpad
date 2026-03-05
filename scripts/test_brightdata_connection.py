"""
Real API connection test for Bright Data LinkedIn Jobs API.

This script tests the real Bright Data API with your actual credentials.
It's configured to fetch only 5 jobs to minimize API usage during testing.
"""

import asyncio
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from src.importers.brightdata_provider import BrightDataJobProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_brightdata_connection():
    """Test Bright Data API connection and data retrieval."""
    
    print("\n" + "=" * 80)
    print("Bright Data LinkedIn Jobs API - Connection Test")
    print("=" * 80 + "\n")
    
    try:
        # Initialize provider
        print("1. Initializing Bright Data provider...")
        provider = BrightDataJobProvider()
        print(f"   ✓ Provider initialized: {provider.provider_name}")
        print(f"   ✓ Poll interval: {provider.poll_interval}s")
        print(f"   ✓ Poll timeout: {provider.poll_timeout}s\n")
        
        # Test search with minimal results
        print("2. Triggering search for 'Product Manager' (max 5 results)...")
        start_time = datetime.now()
        
        jobs = await provider.search_jobs_async(
            keywords="Product Manager",
            location="United States",
            max_results=5,
            posted_when="Past 24 hours",
            progress_callback=async_progress_callback
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        print(f"\n   ✓ Search completed in {duration:.1f}s")
        print(f"   ✓ Jobs fetched: {len(jobs)}\n")
        
        if not jobs:
            print("   ⚠ No jobs returned. This might be due to:")
            print("      - No jobs matching the criteria in the past 24 hours")
            print("      - API quota limits")
            print("      - Search parameters too restrictive\n")
            return
        
        # Test normalization
        print("3. Testing job normalization...")
        for i, job in enumerate(jobs[:3], 1):  # Show first 3 jobs
            normalized = provider.normalize_job(job)
            
            print(f"\n   Job {i}:")
            print(f"   Title: {normalized.get('title', 'N/A')}")
            print(f"   Company: {normalized.get('company', 'N/A')}")
            print(f"   Location: {normalized.get('location', 'N/A')}")
            print(f"   Posting Date: {normalized.get('posting_date', 'N/A')}")
            print(f"   Salary: {normalized.get('salary', 'Not specified')}")
            print(f"   Skills: {', '.join(normalized.get('required_skills', [])[:3]) or 'None'}")
            print(f"   Experience: {normalized.get('experience_required', 'Not specified')} years")
            print(f"   URL: {normalized.get('url', 'N/A')[:60]}...")
            print(f"   Source: {normalized.get('source')}")
        
        if len(jobs) > 3:
            print(f"\n   ... and {len(jobs) - 3} more jobs")
        
        # Data quality analysis
        print("\n4. Data quality analysis:")
        with_salary = sum(1 for j in jobs if provider.normalize_job(j).get('salary'))
        with_skills = sum(1 for j in jobs if provider.normalize_job(j).get('required_skills'))
        with_experience = sum(1 for j in jobs if provider.normalize_job(j).get('experience_required'))
        
        print(f"   Jobs with salary info: {with_salary}/{len(jobs)} ({with_salary/len(jobs)*100:.0f}%)")
        print(f"   Jobs with skills: {with_skills}/{len(jobs)} ({with_skills/len(jobs)*100:.0f}%)")
        print(f"   Jobs with experience: {with_experience}/{len(jobs)} ({with_experience/len(jobs)*100:.0f}%)")
        
        print("\n" + "=" * 80)
        print("✅ BRIGHT DATA CONNECTION TEST PASSED")
        print("=" * 80 + "\n")
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease ensure:")
        print("1. Bright Data API key is set in config.yaml")
        print("2. API key is valid and has active credits\n")
        
    except TimeoutError as e:
        print(f"\n❌ Timeout Error: {e}")
        print("\nThe API took too long to respond. This might indicate:")
        print("1. Network connectivity issues")
        print("2. Bright Data service delays")
        print("3. Need to increase poll_timeout in config\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print()


async def async_progress_callback(message: str, progress: float):
    """Progress callback for async operations."""
    bar_length = 30
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    print(f"   Progress: [{bar}] {progress*100:.0f}% - {message}")


if __name__ == "__main__":
    asyncio.run(test_brightdata_connection())
