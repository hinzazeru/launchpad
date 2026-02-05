"""Apify provider for fetching LinkedIn job postings."""

import logging
import time
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import asyncio
from apify_client import ApifyClient, ApifyClientAsync
from src.importers.base_provider import JobProvider
from src.importers.validators import validate_job_posting, normalize_job_data

logger = logging.getLogger(__name__)


class ApifyJobProvider(JobProvider):
    """Apify API client for fetching LinkedIn job postings.
    
    Extends JobProvider base class to support provider abstraction.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Apify client.

        Args:
            api_key: Apify API key. If None, will be read from config.yaml.
                    Can be provided directly for testing purposes.

        Raises:
            ValueError: If API key is not provided and not found in config
        """
        # Load config to check for mock mode
        from src.config import get_config
        self.config = get_config()

        # Check if mock mode is enabled
        self.use_mock_data = self.config.get("apify.use_mock_data", False)
        self.mock_data_file = self.config.get("apify.mock_data_file", "dataset.json")

        # Only initialize Apify client if not using mock data
        if not self.use_mock_data:
            # Try to get API key from parameter, then config
            if api_key:
                self.api_key = api_key
            else:
                try:
                    self.api_key = self.config.get_apify_api_key()
                except (FileNotFoundError, ValueError) as e:
                    raise ValueError(
                        f"Apify API key is required. {str(e)}\n"
                        f"Either provide api_key parameter or set 'apify.api_key' in config.yaml"
                    )

            self.client = ApifyClient(self.api_key)
            self.async_client = ApifyClientAsync(self.api_key)
            self.max_retries = 3
            self.retry_delay = 2  # seconds
        else:
            # Mock mode - no API client needed
            self.client = None
            self.async_client = None
            self.api_key = None
            self.max_retries = 0
            self.retry_delay = 0

    def _load_mock_data(self) -> List[Dict]:
        """Load mock job data from JSON file.

        Returns:
            List of job posting dictionaries from mock data file

        Raises:
            FileNotFoundError: If mock data file doesn't exist
            ValueError: If mock data file contains invalid JSON
        """
        # Get project root (parent of src directory)
        project_root = Path(__file__).parent.parent.parent
        mock_file_path = project_root / self.mock_data_file

        if not mock_file_path.exists():
            raise FileNotFoundError(
                f"Mock data file not found: {mock_file_path}\n"
                f"Please ensure '{self.mock_data_file}' exists in the project root directory."
            )

        try:
            with open(mock_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Filter out error entries (entries with 'error' field)
            valid_jobs = [job for job in data if 'error' not in job]

            print(f"[MOCK MODE] Loaded {len(valid_jobs)} jobs from {self.mock_data_file}")
            return valid_jobs

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in mock data file: {e}")

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
        """Asynchronously search for LinkedIn jobs using Apify with parallel execution support.

        Args:
            keywords: Job title or keywords
            location: Job location
            job_type: Employment type
            max_results: Maximum number of jobs to collect
            posted_when: Time filter
            experience_level: Experience level
            work_arrangement: Remote/Hybrid/On-site filter
            country_code: Country code filter
            company_name: Filter by specific company
            search_radius: Search radius
            split_calls: Whether to split the request into parallel calls
            progress_callback: Optional async callback for progress updates.
                               Signature: async def callback(message: str, sub_progress: float)
                               sub_progress is 0.0-1.0 within the fetching stage

        Returns:
            List of job posting dictionaries
        """
        # If mock mode is enabled, load from file
        if self.use_mock_data:
            print(f"[MOCK MODE] Using mock data (ignoring search parameters)")
            if progress_callback:
                await progress_callback("Loading mock data...", 0.5)
            return self._load_mock_data()

        # Base input configuration
        base_input = {
            "location": location,
            "time_range": posted_when,
        }

        # Optional parameters
        if keywords:
            base_input["keyword"] = keywords
        if job_type:
            base_input["job_type"] = job_type
        if experience_level:
            base_input["experience_level"] = experience_level
        if work_arrangement:
            base_input["remote"] = work_arrangement
        if country_code:
            base_input["country"] = country_code
        if company_name:
            base_input["company"] = company_name
        if search_radius:
            base_input["location_radius"] = search_radius

        # Determine chunks for parallel execution
        chunks = []
        if split_calls and max_results >= 10:
            # Split into chunks of ~7-10 jobs (user suggestion: 3 calls for 7 each -> 21 total)
            # We'll use chunk size of 10 for simplicity
            chunk_size = 10
            num_chunks = (max_results + chunk_size - 1) // chunk_size
            
            # Limit parallelism to avoid excessive calls/costs (max 3 concurrent)
            num_chunks = min(num_chunks, 3)
            
            # Recalculate chunks based on limited concurrency
            jobs_per_chunk = (max_results + num_chunks - 1) // num_chunks
            
            for i in range(num_chunks):
                offset = i * jobs_per_chunk
                limit = min(jobs_per_chunk, max_results - offset)
                if limit > 0:
                    chunks.append({"start": offset, "limit": limit})
        else:
            chunks.append({"start": 0, "limit": max_results})

        num_chunks = len(chunks)
        
        # Report starting parallel calls
        if progress_callback:
            await progress_callback(f"Starting {num_chunks} parallel API call(s)...", 0.1)

        # Execute parallel calls with progress tracking
        completed_chunks = 0
        all_jobs = []
        
        async def execute_with_tracking(input_data: Dict, chunk_index: int) -> List[Dict]:
            """Execute a chunk and track completion."""
            nonlocal completed_chunks
            result = await self._execute_apify_run_async(input_data)
            completed_chunks += 1
            if progress_callback:
                progress = 0.1 + (0.8 * completed_chunks / num_chunks)
                await progress_callback(
                    f"API call {completed_chunks}/{num_chunks} complete ({len(result) if isinstance(result, list) else 0} jobs)",
                    progress
                )
            return result
        
        tasks = []
        for i, chunk in enumerate(chunks):
            input_copy = base_input.copy()
            input_copy["max_jobs"] = chunk["limit"]
            input_copy["start"] = chunk["start"]  # Assuming 'start' works for pagination
            
            tasks.append(execute_with_tracking(input_copy, i))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Report processing results
        if progress_callback:
            await progress_callback("Processing API responses...", 0.95)
        
        # Combine results
        for res in results:
            if isinstance(res, Exception):
                print(f"Apify chunk failed: {res}")
            elif isinstance(res, list):
                all_jobs.extend(res)
        
        if progress_callback:
            await progress_callback(f"Fetched {len(all_jobs)} total jobs", 1.0)
                
        return all_jobs

    async def _execute_apify_run_async(self, run_input: Dict) -> List[Dict]:
        """Execute a single Apify run asynchronously."""
        actor_id = "vulnv/linkedin-jobs-scraper"
        
        for attempt in range(self.max_retries):
            try:
                run = await self.async_client.actor(actor_id).call(run_input=run_input)
                
                if not run:
                    return []

                dataset_id = run.get("defaultDatasetId")
                if not dataset_id:
                    return []

                # Fetch items
                dataset_items = await self.async_client.dataset(dataset_id).list_items()
                return dataset_items.items
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    print(f"Failed to fetch job chunk after {self.max_retries} attempts: {e}")
                    raise e
        return []

    def search_jobs(
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
    ) -> List[Dict]:
        """Synchronous wrapper for search_jobs (legacy)."""
        # If needed, running async in sync
        # But prefer using search_jobs_async directly in async contexts
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.search_jobs_async(
            keywords, location, job_type, max_results, posted_when, 
            experience_level, work_arrangement, country_code, 
            company_name, search_radius, split_calls=False # Default to serial for legacy
        ))

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "apify"

    def normalize_job(self, job_data: Dict) -> Dict:
        """Normalize Apify job data to standard format for vulnv/linkedin-jobs-scraper.

        Args:
            job_data: Raw job data from vulnv/linkedin-jobs-scraper actor

        Returns:
            Normalized job dictionary
        """
        # Map vulnv/linkedin-jobs-scraper fields to our standard format
        normalized = {
            'title': job_data.get('job_title', ''),
            'company': job_data.get('company_name', ''),
            'location': job_data.get('job_location', ''),
            'description': job_data.get('job_summary', ''),
            'url': job_data.get('url', ''),
        }

        # Extract salary from description
        from src.matching.skill_extractor import extract_salary_from_description, extract_domain_requirements
        description = normalized.get('description', '')
        salary = extract_salary_from_description(description)
        if salary:
            normalized['salary'] = salary

        # Extract domain requirements from description
        domains = extract_domain_requirements(description)
        if domains.get('required'):
            normalized['required_domains'] = domains['required']

        # Parse posting date (ISO format: "2025-11-27T10:35:44.838Z")
        posting_date_str = job_data.get('job_posted_date')
        if posting_date_str:
            try:
                if isinstance(posting_date_str, str):
                    # Handle ISO format with Z (UTC) or timezone offset
                    dt = datetime.fromisoformat(posting_date_str.replace('Z', '+00:00'))
                    # Convert to naive UTC datetime to match the rest of the codebase
                    normalized['posting_date'] = dt.replace(tzinfo=None) if dt.tzinfo else dt
                elif isinstance(posting_date_str, datetime):
                    # Convert to naive UTC if timezone-aware
                    dt = posting_date_str
                    normalized['posting_date'] = dt.replace(tzinfo=None) if dt.tzinfo else dt
            except Exception:
                # If parsing fails, default to current time
                normalized['posting_date'] = datetime.utcnow()
        else:
            # Default to current time if no posting date found
            normalized['posting_date'] = datetime.utcnow()

        # Parse skills from job_function (comes as string like "Product Management")
        # Also extract from job_summary if needed
        skills = []
        job_function = job_data.get('job_function', '')
        if job_function:
            if isinstance(job_function, list):
                skills.extend(job_function)
            elif isinstance(job_function, str):
                skills.append(job_function)

        # Add job industries as additional context
        job_industries = job_data.get('job_industries', '')
        if job_industries:
            if isinstance(job_industries, list):
                skills.extend(job_industries)
            elif isinstance(job_industries, str):
                # Split by comma if it's a comma-separated string
                skills.extend([s.strip() for s in job_industries.split(',')])

        normalized['required_skills'] = skills

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

        # Set source
        normalized['source'] = 'api'

        return normalized

    def fetch_and_validate_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
        job_type: Optional[str] = None,
        max_results: int = 50,
        validate_freshness: bool = True,
    ) -> tuple[List[Dict], List[Dict]]:
        """Fetch jobs from Apify and validate them.

        Args:
            keywords: Job search keywords
            location: Job location
            job_type: Job type filter
            max_results: Maximum number of results
            validate_freshness: Whether to apply 24-hour freshness filter

        Returns:
            Tuple of (valid_jobs, invalid_jobs_with_reasons)
        """
        # Fetch jobs from API
        raw_jobs = self.search_jobs(
            keywords=keywords,
            location=location,
            job_type=job_type,
            max_results=max_results,
        )

        # Normalize and validate
        valid_jobs = []
        invalid_jobs = []

        for job in raw_jobs:
            # Normalize
            normalized_job = self.normalize_job(job)
            normalized_job = normalize_job_data(normalized_job)

            # Validate
            is_valid, error = validate_job_posting(normalized_job, check_freshness=validate_freshness)

            if is_valid:
                valid_jobs.append(normalized_job)
            else:
                invalid_jobs.append({
                    'job': normalized_job,
                    'error': error
                })

        return valid_jobs, invalid_jobs

    def import_jobs(self, jobs: List[Dict]) -> int:
        """Import jobs to the database after normalization.

        Args:
            jobs: List of job dictionaries from Apify

        Returns:
            Number of jobs successfully imported
        """
        from src.database.db import SessionLocal
        from src.database.models import JobPosting
        from src.database.crud import get_job_by_title_company
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
        # Track jobs added in this batch to prevent duplicates from parallel Apify chunks
        seen_in_batch = set()

        try:
            for job in jobs:
                # Normalize the job data
                normalized_job = self.normalize_job(job)
                normalized_job = normalize_job_data(normalized_job)

                # Create deduplication key (normalized title + company)
                dedup_key = (
                    normalized_job['title'].strip().lower(),
                    normalized_job['company'].strip().lower()
                )

                # Check if already added in this batch (prevents race condition with parallel chunks)
                if dedup_key in seen_in_batch:
                    continue

                # Validate basic data structure only (no freshness check)
                # All jobs from Apify are saved - freshness filtering happens during matching
                is_valid, error = validate_job_posting(normalized_job, check_freshness=False)

                if not is_valid:
                    logger.debug(f"Skipping invalid job: {error}")
                    continue

                # Check if job already exists (by normalized title + company)
                existing = get_job_by_title_company(
                    session,
                    normalized_job['title'],
                    normalized_job['company']
                )

                if existing:
                    continue  # Skip duplicates only

                # Mark as seen in this batch
                seen_in_batch.add(dedup_key)

                # Create new job posting (with keyword domains as fallback)
                job_posting = JobPosting(
                    title=normalized_job['title'],
                    company=normalized_job['company'],
                    location=normalized_job.get('location', ''),
                    description=normalized_job.get('description', ''),
                    required_skills=normalized_job.get('required_skills', []),
                    experience_required=normalized_job.get('experience_required', 0),
                    posting_date=normalized_job.get('posting_date'),
                    source=normalized_job.get('source', 'api'),
                    url=normalized_job.get('url', ''),
                    salary=normalized_job.get('salary'),
                    required_domains=normalized_job.get('required_domains'),
                    domain_extraction_method='keyword' if normalized_job.get('required_domains') else None,
                )

                session.add(job_posting)
                new_job_postings.append(job_posting)
                imported_count += 1

            # Commit to get job IDs
            session.commit()

            # Run Gemini extraction on newly imported jobs (domains + summaries)
            if gemini_extractor and new_job_postings:
                for job_posting in new_job_postings:
                    # Extract domains
                    try:
                        result = gemini_extractor.extract_domains(
                            description=job_posting.description or '',
                            company=job_posting.company,
                            title=job_posting.title
                        )
                        domains = result.get('domains', [])
                        if domains or result.get('reasoning'):  # Gemini responded
                            job_posting.required_domains = domains if domains else None
                            job_posting.domain_extraction_method = 'llm'
                    except Exception as e:
                        logger.warning(f"Gemini domain extraction failed for {job_posting.title}: {e}")
                        # Keep keyword extraction as fallback

                    # Generate summary
                    try:
                        summary = gemini_extractor.summarize_job(
                            description=job_posting.description or '',
                            company=job_posting.company,
                            title=job_posting.title
                        )
                        if summary:
                            job_posting.summary = summary
                    except Exception as e:
                        logger.warning(f"Gemini summarization failed for {job_posting.title}: {e}")
                        # Summary is optional

                session.commit()

            # Extract structured requirements for AI matching
            if requirements_extractor and new_job_postings:
                for job_posting in new_job_postings:
                    try:
                        requirements = requirements_extractor.extract_requirements(
                            description=job_posting.description or '',
                            title=job_posting.title,
                            company=job_posting.company
                        )
                        if requirements:
                            job_posting.structured_requirements = requirements
                            job_posting.requirements_extracted_at = datetime.utcnow()
                            job_posting.requirements_extraction_model = requirements_extractor.model_name
                    except Exception as e:
                        logger.warning(f"Requirements extraction failed for {job_posting.title}: {e}")
                        # Requirements extraction is optional - AI matching can still work without it

                session.commit()

            if self.use_mock_data:
                print(f"[MOCK MODE] Imported {imported_count} jobs (skipped freshness validation, duplicates filtered)")

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

        return imported_count


def create_apify_importer(api_key: Optional[str] = None) -> "ApifyJobProvider":
    """Factory function to create an Apify importer.

    Args:
        api_key: Optional API key. If None, reads from environment

    Returns:
        ApifyJobProvider instance
    """
    return ApifyJobProvider(api_key=api_key)


# Backward compatibility alias
ApifyJobImporter = ApifyJobProvider
