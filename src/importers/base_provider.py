"""Base provider interface for job data sources."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class JobProvider(ABC):
    """Abstract base class for job data providers.
    
    Implementations must provide methods to search for jobs and normalize
    provider-specific data into a standard format.
    """

    @abstractmethod
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
        """Search for jobs and return raw provider data.
        
        Args:
            keywords: Job title or keywords to search for
            location: Geographic location for job search
            job_type: Employment type filter (Full-time, Part-time, etc.)
            max_results: Maximum number of jobs to return
            posted_when: Time filter (Past 24 hours, Past week, etc.)
            experience_level: Experience level filter
            work_arrangement: Remote/Hybrid/On-site filter
            country_code: Country code filter
            company_name: Filter by specific company
            search_radius: Search radius for location
            split_calls: Whether to split request into parallel calls (if supported)
            progress_callback: Optional async callback for progress updates
                              Signature: async def callback(message: str, sub_progress: float)
        
        Returns:
            List of job posting dictionaries in provider-specific format
        """
        pass

    @abstractmethod
    def normalize_job(self, job_data: Dict) -> Dict:
        """Normalize provider-specific data to standard format.
        
        Args:
            job_data: Raw job data from provider
        
        Returns:
            Normalized job dictionary with standard fields:
            - title: Job title
            - company: Company name
            - location: Job location
            - description: Job description/summary
            - url: Job posting URL
            - posting_date: When job was posted (datetime)
            - source: Provider identifier ('apify', 'brightdata', etc.)
            - required_skills: List of required skills
            - experience_required: Years of experience (float)
            - salary: Salary information (optional)
            - required_domains: List of required domains (optional)
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier.
        
        Returns:
            Provider name string (e.g., 'apify', 'brightdata')
        """
        pass
