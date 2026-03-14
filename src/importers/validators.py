"""Validators for job posting data."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List


def validate_24_hour_freshness(posting_date: datetime) -> bool:
    """Validate that job posting is within 24 hours.

    Args:
        posting_date: Job posting date

    Returns:
        bool: True if within 24 hours, False otherwise
    """
    current_time = datetime.now(timezone.utc)
    time_diff = current_time - posting_date

    return time_diff < timedelta(hours=24)


def validate_required_fields(job_data: Dict) -> tuple[bool, List[str]]:
    """Validate that job posting contains required fields.

    Args:
        job_data: Job posting dictionary

    Returns:
        Tuple of (is_valid, missing_fields)
    """
    required_fields = ['title', 'company', 'posting_date']
    missing_fields = []

    for field in required_fields:
        if field not in job_data or not job_data[field]:
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields


def validate_job_posting(job_data: Dict, check_freshness: bool = True) -> tuple[bool, Optional[str]]:
    """Validate complete job posting.

    Args:
        job_data: Job posting dictionary
        check_freshness: Whether to check 24-hour freshness filter

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    has_required, missing = validate_required_fields(job_data)
    if not has_required:
        return False, f"Missing required fields: {', '.join(missing)}"

    # Check freshness if enabled
    if check_freshness:
        posting_date = job_data.get('posting_date')

        # Ensure posting_date is a datetime object
        if not isinstance(posting_date, datetime):
            return False, "posting_date must be a datetime object"

        if not validate_24_hour_freshness(posting_date):
            return False, "Job posting is older than 24 hours"

    return True, None


def normalize_job_data(job_data: Dict) -> Dict:
    """Normalize job data fields.

    Args:
        job_data: Raw job data

    Returns:
        Normalized job data
    """
    normalized = job_data.copy()

    # Normalize title and company (trim whitespace)
    if 'title' in normalized:
        normalized['title'] = normalized['title'].strip()

    if 'company' in normalized:
        normalized['company'] = normalized['company'].strip()

    # Ensure skills is a list
    if 'required_skills' in normalized and not isinstance(normalized['required_skills'], list):
        if isinstance(normalized['required_skills'], str):
            # Split by comma if string
            normalized['required_skills'] = [s.strip() for s in normalized['required_skills'].split(',')]
        else:
            normalized['required_skills'] = []

    return normalized
