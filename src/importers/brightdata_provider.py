"""Bright Data provider for fetching LinkedIn job postings."""

import asyncio
import logging
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timezone

from src.importers.base_provider import JobProvider

logger = logging.getLogger(__name__)


class BrightDataJobProvider(JobProvider):
    """Bright Data API client for LinkedIn jobs.
    
    Uses Bright Data's LinkedIn Jobs dataset with trigger/poll pattern.
    """

    BASE_URL = "https://api.brightdata.com/datasets/v3"
    DATASET_ID = "gd_lpfll7v5hcqtkxl6l"  # LinkedIn job listings dataset

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Bright Data client.
        
        Args:
            api_key: Bright Data API key. If None, reads from config.yaml
            
        Raises:
            ValueError: If API key is not provided and not found in config
        """
        from src.config import get_config
        self.config = get_config()

        if api_key:
            self.api_key = api_key
        else:
            try:
                self.api_key = self.config.get_brightdata_api_key()
            except (FileNotFoundError, ValueError) as e:
                raise ValueError(
                    f"Bright Data API key is required. {str(e)}\n"
                    f"Either provide api_key parameter or set 'brightdata.api_key' in config.yaml"
                )

        # Get polling configuration
        self.poll_interval = self.config.get("brightdata.poll_interval_seconds", 5)
        self.poll_timeout = self.config.get("brightdata.poll_timeout_seconds", 600)

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "brightdata"

    async def search_jobs_async(
        self,
        keywords: Optional[str] = None,
        location: str = "United States",
        job_type: Optional[str] = None,
        max_results: int = 50,
        posted_when: str = "Past 24 hours",
        experience_level: Optional[str] = None,
        work_arrangement: Optional[str] = None,
        country_code: Optional[str] = None,
        company_name: Optional[str] = None,
        search_radius: Optional[str] = None,
        split_calls: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> List[Dict]:
        """Search for LinkedIn jobs using Bright Data API.
        
        Args:
            keywords: Job title or keywords
            location: Job location
            job_type: Employment type (Full-time, Part-time, etc.)
            max_results: Maximum number of jobs to fetch
            posted_when: Time filter
            experience_level: Experience level filter
            work_arrangement: Remote/Hybrid/On-site filter
            country_code: Country code (e.g., "US")
            company_name: Filter by company
            search_radius: Search radius (not used by Bright Data)
            split_calls: Ignored for Bright Data (single API call)
            progress_callback: Optional async callback for progress updates
        
        Returns:
            List of job posting dictionaries
        """
        # Build request payload
        request_body = {
            "location": location,
        }

        if keywords:
            request_body["keyword"] = keywords
        
        # Map time range to Bright Data format
        time_range_map = {
            "Past 24 hours": "Past 24 hours",
            "Past week": "Past Week",
            "Past month": "Past Month",
            "Any time": "Any Time"
        }
        request_body["time_range"] = time_range_map.get(posted_when, "Past 24 hours")

        if job_type:
            request_body["job_type"] = job_type
        
        if experience_level:
            request_body["experience_level"] = experience_level
        
        if work_arrangement:
            request_body["remote"] = work_arrangement
        
        if country_code:
            request_body["country"] = country_code

        if company_name:
            request_body["company"] = company_name

        # Step 1: Trigger the search
        if progress_callback:
            await progress_callback("Triggering Bright Data search...", 0.1)

        snapshot_id = await self._trigger_search(request_body, max_results)
        
        if progress_callback:
            await progress_callback(f"Search triggered (ID: {snapshot_id[:8]}...), polling for results...", 0.2)

        # Step 2: Poll for results
        jobs = await self._poll_results(snapshot_id, progress_callback)

        if progress_callback:
            await progress_callback(f"Fetched {len(jobs)} jobs from Bright Data", 1.0)

        return jobs

    async def _trigger_search(self, request_body: Dict, max_results: int) -> str:
        """Trigger a Bright Data job search.
        
        Args:
            request_body: Search parameters
            max_results: Maximum jobs to fetch
            
        Returns:
            snapshot_id for polling results
            
        Raises:
            Exception: If trigger request fails
        """
        url = f"{self.BASE_URL}/trigger"
        params = {
            "dataset_id": self.DATASET_ID,
            "include_errors": "true",
            "type": "discover_new",
            "discover_by": "keyword",
            "limit_per_input": max_results,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, headers=headers, json=[request_body]) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(
                        f"Bright Data trigger failed (status {resp.status}): {error_text}"
                    )
                
                data = await resp.json()
                snapshot_id = data.get("snapshot_id")
                
                if not snapshot_id:
                    raise Exception(f"No snapshot_id in Bright Data response: {data}")
                
                logger.info(f"Bright Data search triggered: {snapshot_id}")
                return snapshot_id

    async def _poll_results(
        self, 
        snapshot_id: str, 
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """Poll Bright Data for search results.
        
        Args:
            snapshot_id: The snapshot ID from trigger request
            progress_callback: Optional progress callback
            
        Returns:
            List of job dictionaries
            
        Raises:
            TimeoutError: If polling exceeds timeout
            Exception: If polling fails
        """
        url = f"{self.BASE_URL}/snapshot/{snapshot_id}"
        params = {"format": "json"}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        max_attempts = self.poll_timeout // self.poll_interval
        
        async with aiohttp.ClientSession() as session:
            for attempt in range(max_attempts):
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        # Data is ready
                        jobs = await resp.json()
                        logger.info(f"Bright Data returned {len(jobs)} jobs")
                        return jobs
                    
                    elif resp.status == 202:
                        # Still processing, wait and retry
                        if progress_callback:
                            progress = 0.2 + (0.7 * attempt / max_attempts)
                            await progress_callback(
                                f"Processing... (attempt {attempt + 1}/{max_attempts})", 
                                progress
                            )
                        await asyncio.sleep(self.poll_interval)
                    
                    else:
                        # Error status
                        error_text = await resp.text()
                        raise Exception(
                            f"Bright Data polling error (status {resp.status}): {error_text}"
                        )
            
            # Max attempts exceeded
            raise TimeoutError(
                f"Bright Data polling timeout after {self.poll_timeout}s "
                f"({max_attempts} attempts)"
            )

    def normalize_job(self, job_data: Dict) -> Dict:
        """Normalize Bright Data job data to standard format.
        
        Args:
            job_data: Raw job data from Bright Data
            
        Returns:
            Normalized job dictionary
        """
        # Try multiple possible URL field names from Bright Data response
        job_url = (
            job_data.get('url')
            or job_data.get('job_url')
            or job_data.get('link')
            or job_data.get('job_link')
            or job_data.get('URL')
            or ''
        )
        if not job_url:
            logger.warning(f"No URL found for job '{job_data.get('job_title', 'unknown')}'. Available keys: {list(job_data.keys())}")

        normalized = {
            'title': job_data.get('job_title', ''),
            'company': job_data.get('company_name', ''),
            'location': job_data.get('job_location', ''),
            'description': job_data.get('job_summary', ''),
            'url': job_url,
        }

        # Parse posting date
        posting_date_str = job_data.get('job_posted_date')
        if posting_date_str:
            try:
                if isinstance(posting_date_str, str):
                    # Bright Data typically returns cleaner date formats
                    # Handle ISO format with Z (UTC) or timezone offset
                    dt = datetime.fromisoformat(posting_date_str.replace('Z', '+00:00'))
                    normalized['posting_date'] = dt.replace(tzinfo=None) if dt.tzinfo else dt
                elif isinstance(posting_date_str, datetime):
                    dt = posting_date_str
                    normalized['posting_date'] = dt.replace(tzinfo=None) if dt.tzinfo else dt
            except Exception as e:
                logger.warning(f"Failed to parse Bright Data posting date '{posting_date_str}': {e}")
                normalized['posting_date'] = datetime.now(timezone.utc)
        else:
            normalized['posting_date'] = datetime.now(timezone.utc)

        # required_skills is populated later by NLP/Gemini extraction from job description text.
        # job_function (e.g., "Product Management") and job_industries (e.g., "Financial Services")
        # are LinkedIn metadata fields, not skills — including them causes false skill gap reports.
        normalized['required_skills'] = []

        # Parse experience from job_seniority_level
        seniority_level = job_data.get('job_seniority_level', '')
        if seniority_level:
            import re
            # Try to extract years from text like "5+ years"
            years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', str(seniority_level), re.IGNORECASE)
            if years_match:
                normalized['experience_required'] = float(years_match.group(1))
            else:
                # Map seniority levels to approximate years
                seniority_map = {
                    'entry': 0,
                    'associate': 0,
                    'junior': 1,
                    'mid': 3,
                    'mid-senior': 3,
                    'senior': 5,
                    'lead': 7,
                    'staff': 7,
                    'principal': 10,
                    'director': 12,
                    'executive': 15,
                }
                for level, years in seniority_map.items():
                    if level in str(seniority_level).lower():
                        normalized['experience_required'] = float(years)
                        break

        # Extract salary from job_base_pay_range (Bright Data advantage!)
        salary_range = job_data.get('job_base_pay_range')
        if salary_range:
            normalized['salary'] = salary_range

        # Extract domain requirements from description (using existing helper)
        from src.matching.skill_extractor import extract_domain_requirements
        description = normalized.get('description', '')
        if description:
            domains = extract_domain_requirements(description)
            if domains.get('required'):
                normalized['required_domains'] = domains['required']

        # Set source
        normalized['source'] = 'brightdata'

        return normalized

    def import_jobs(self, jobs: List[Dict]) -> int:
        """Import jobs to the database after normalization.

        Args:
            jobs: List of job dictionaries from Bright Data

        Returns:
            Number of jobs successfully imported
        """
        from src.database.db import SessionLocal
        from src.database.models import JobPosting
        from src.database.crud import get_existing_job_keys, get_existing_jobs_for_repost_check
        from src.importers.validators import normalize_job_data, validate_job_posting

        # Try to initialize Gemini for domain extraction and requirements extraction
        gemini_extractor = None
        requirements_extractor = None
        try:
            from src.integrations.gemini_client import GeminiDomainExtractor, GeminiRequirementsExtractor
            extractor = GeminiDomainExtractor()
            if extractor.is_available():
                gemini_extractor = extractor

            # Also initialize requirements extractor if enabled
            req_extractor = GeminiRequirementsExtractor()
            if req_extractor.is_available():
                requirements_extractor = req_extractor
        except Exception:
            pass  # Gemini not available, will use keyword extraction

        session = SessionLocal()
        imported_count = 0
        new_job_postings = []  # Track newly created jobs for Gemini extraction
        # Track jobs added in this batch to prevent duplicates
        seen_in_batch = set()

        try:
            # Phase 1: Normalize all jobs and collect dedup keys
            normalized_jobs = []
            for job in jobs:
                normalized_job = self.normalize_job(job)
                normalized_job = normalize_job_data(normalized_job)

                dedup_key = (
                    normalized_job['title'].strip().lower(),
                    normalized_job['company'].strip().lower()
                )

                if dedup_key in seen_in_batch:
                    continue

                is_valid, error = validate_job_posting(normalized_job, check_freshness=False)
                if not is_valid:
                    logger.debug(f"Skipping invalid job: {error}")
                    continue

                seen_in_batch.add(dedup_key)
                normalized_jobs.append((normalized_job, dedup_key))

            # Phase 2: Bulk check for existing jobs (1 query instead of N)
            if normalized_jobs:
                all_keys = [dk for _, dk in normalized_jobs]
                existing_jobs = get_existing_jobs_for_repost_check(session, all_keys)
                logger.debug(f"Bulk duplicate check: {len(all_keys)} candidates, {len(existing_jobs)} already exist")
            else:
                existing_jobs = {}

            # Phase 3: Create job objects for new entries; update posting_date for reposts
            repost_count_updated = 0
            for normalized_job, dedup_key in normalized_jobs:
                if dedup_key in existing_jobs:
                    existing_id, existing_date, existing_repost_count = existing_jobs[dedup_key]
                    incoming_date = normalized_job.get('posting_date')
                    if incoming_date and existing_date and incoming_date > existing_date:
                        existing_obj = session.query(JobPosting).filter(JobPosting.id == existing_id).first()
                        if existing_obj:
                            existing_obj.posting_date = incoming_date
                            existing_obj.is_repost = True
                            existing_obj.repost_count = existing_repost_count + 1
                            repost_count_updated += 1
                            logger.debug(f"Repost detected: {existing_obj.title} @ {existing_obj.company} (repost #{existing_obj.repost_count})")
                    continue

                job_posting = JobPosting(
                    title=normalized_job['title'],
                    company=normalized_job['company'],
                    location=normalized_job.get('location', ''),
                    description=normalized_job.get('description', ''),
                    required_skills=normalized_job.get('required_skills', []),
                    experience_required=normalized_job.get('experience_required', 0),
                    posting_date=normalized_job.get('posting_date'),
                    source=normalized_job.get('source', 'brightdata'),
                    url=normalized_job.get('url', ''),
                    salary=normalized_job.get('salary'),
                    required_domains=normalized_job.get('required_domains'),
                    domain_extraction_method='keyword' if normalized_job.get('required_domains') else None,
                )

                new_job_postings.append(job_posting)
                imported_count += 1

            if repost_count_updated:
                session.commit()
                logger.info(f"Updated {repost_count_updated} reposted jobs")

            # Bulk add and commit (with unique constraint fallback)
            if new_job_postings:
                try:
                    session.add_all(new_job_postings)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    if 'UNIQUE constraint failed' in str(e) or 'IntegrityError' in type(e).__name__:
                        logger.warning(f"Bulk insert hit unique constraint, falling back to one-by-one insert")
                        survived = []
                        for job in new_job_postings:
                            try:
                                session.add(job)
                                session.commit()
                                survived.append(job)
                            except Exception:
                                session.rollback()
                                imported_count -= 1
                                logger.debug(f"Skipping duplicate: {job.title} @ {job.company}")
                        new_job_postings = survived
                    else:
                        raise
            else:
                session.commit()

            # Run Gemini extraction on newly imported jobs (parallel)
            if new_job_postings and (gemini_extractor or requirements_extractor):
                from src.importers.enrichment import enrich_jobs_parallel
                enriched = enrich_jobs_parallel(
                    new_job_postings, gemini_extractor, requirements_extractor, session
                )
                logger.info(f"Enriched {enriched}/{len(new_job_postings)} jobs with Gemini")

            logger.info(f"Imported {imported_count} new jobs from Bright Data")
            return imported_count

        except Exception as e:
            logger.error(f"Error importing jobs: {e}", exc_info=True)
            session.rollback()
            raise
        finally:
            session.close()
