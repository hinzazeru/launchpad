"""File-based job posting importer supporting PDF, text, JSON, and CSV formats."""

import json
import csv
import re
from datetime import datetime
from typing import List, Dict, Optional
from PyPDF2 import PdfReader
from src.importers.validators import validate_job_posting, normalize_job_data


def parse_pdf(file_path: str) -> List[Dict]:
    """Parse job postings from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        List of job posting dictionaries

    Raises:
        ValueError: If PDF cannot be parsed
    """
    try:
        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            text += page.extract_text()

        # Try to parse structured job postings from text
        jobs = parse_text_content(text)
        return jobs

    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")


def parse_text(file_path: str) -> List[Dict]:
    """Parse job postings from plain text or markdown file.

    Args:
        file_path: Path to text/markdown file

    Returns:
        List of job posting dictionaries
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return parse_text_content(content)


def parse_text_content(content: str) -> List[Dict]:
    """Parse job posting data from text content.

    Expects format like:
    Job Title: Senior Product Manager
    Company: Tech Corp
    Location: San Francisco, CA
    Posted: 2024-01-15
    Skills: Product Management, Agile, SQL
    Experience: 5 years
    URL: https://linkedin.com/jobs/123
    Description: ...

    Args:
        content: Text content

    Returns:
        List of job posting dictionaries
    """
    jobs = []

    # Split by job separator (blank lines or "---")
    job_blocks = re.split(r'\n\s*\n|---+', content)

    for block in job_blocks:
        if not block.strip():
            continue

        job_data = {}

        # Extract title
        title_match = re.search(r'(?:Job\s*)?Title:\s*(.+)', block, re.IGNORECASE)
        if title_match:
            job_data['title'] = title_match.group(1).strip()

        # Extract company
        company_match = re.search(r'Company:\s*(.+)', block, re.IGNORECASE)
        if company_match:
            job_data['company'] = company_match.group(1).strip()

        # Extract location
        location_match = re.search(r'Location:\s*(.+)', block, re.IGNORECASE)
        if location_match:
            job_data['location'] = location_match.group(1).strip()

        # Extract posting date
        date_match = re.search(r'Posted:\s*(\d{4}-\d{2}-\d{2})', block, re.IGNORECASE)
        if date_match:
            try:
                job_data['posting_date'] = datetime.strptime(date_match.group(1), '%Y-%m-%d')
            except:
                pass

        # Extract skills
        skills_match = re.search(r'Skills:\s*(.+)', block, re.IGNORECASE)
        if skills_match:
            skills_str = skills_match.group(1).strip()
            job_data['required_skills'] = [s.strip() for s in skills_str.split(',')]

        # Extract experience
        exp_match = re.search(r'Experience:\s*(\d+)\s*(?:years?|yrs?)', block, re.IGNORECASE)
        if exp_match:
            job_data['experience_required'] = float(exp_match.group(1))

        # Extract URL
        url_match = re.search(r'URL:\s*(.+)', block, re.IGNORECASE)
        if url_match:
            job_data['url'] = url_match.group(1).strip()

        # Extract description
        desc_match = re.search(r'Description:\s*(.+?)(?=\n(?:Job\s*)?Title:|$)', block, re.IGNORECASE | re.DOTALL)
        if desc_match:
            job_data['description'] = desc_match.group(1).strip()

        # Only add if we have minimum required fields
        if 'title' in job_data and 'company' in job_data:
            # Set default posting_date to now if not found
            if 'posting_date' not in job_data:
                job_data['posting_date'] = datetime.utcnow()

            job_data['source'] = 'text'
            jobs.append(job_data)

    return jobs


def parse_json(file_path: str) -> List[Dict]:
    """Parse job postings from JSON file.

    Expected format:
    {
        "jobs": [
            {
                "title": "...",
                "company": "...",
                "posting_date": "2024-01-15",
                ...
            }
        ]
    }

    Or just an array of jobs: [{...}, {...}]

    Args:
        file_path: Path to JSON file

    Returns:
        List of job posting dictionaries

    Raises:
        ValueError: If JSON cannot be parsed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle different JSON structures
        if isinstance(data, list):
            jobs = data
        elif isinstance(data, dict) and 'jobs' in data:
            jobs = data['jobs']
        else:
            raise ValueError("JSON must be an array or have a 'jobs' key")

        # Convert date strings to datetime objects
        for job in jobs:
            if 'posting_date' in job and isinstance(job['posting_date'], str):
                try:
                    job['posting_date'] = datetime.strptime(job['posting_date'], '%Y-%m-%d')
                except:
                    # Try ISO format
                    try:
                        job['posting_date'] = datetime.fromisoformat(job['posting_date'])
                    except:
                        job['posting_date'] = datetime.utcnow()

            job['source'] = 'json'

        return jobs

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse JSON: {str(e)}")


def parse_csv(file_path: str) -> List[Dict]:
    """Parse job postings from CSV file.

    Expected columns: title, company, posting_date, location, required_skills,
                     experience_required, url, description

    Args:
        file_path: Path to CSV file

    Returns:
        List of job posting dictionaries

    Raises:
        ValueError: If CSV cannot be parsed
    """
    try:
        jobs = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                job_data = {}

                # Map CSV columns to job data
                if 'title' in row:
                    job_data['title'] = row['title']
                if 'company' in row:
                    job_data['company'] = row['company']
                if 'location' in row:
                    job_data['location'] = row['location']
                if 'description' in row:
                    job_data['description'] = row['description']
                if 'url' in row:
                    job_data['url'] = row['url']

                # Parse posting date
                if 'posting_date' in row and row['posting_date']:
                    try:
                        job_data['posting_date'] = datetime.strptime(row['posting_date'], '%Y-%m-%d')
                    except:
                        job_data['posting_date'] = datetime.utcnow()
                else:
                    job_data['posting_date'] = datetime.utcnow()

                # Parse skills (comma-separated)
                if 'required_skills' in row and row['required_skills']:
                    job_data['required_skills'] = [s.strip() for s in row['required_skills'].split(',')]

                # Parse experience
                if 'experience_required' in row and row['experience_required']:
                    try:
                        job_data['experience_required'] = float(row['experience_required'])
                    except:
                        pass

                job_data['source'] = 'csv'
                jobs.append(job_data)

        return jobs

    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {str(e)}")


def import_jobs_from_file(
    file_path: str,
    file_type: Optional[str] = None,
    validate_freshness: bool = True
) -> tuple[List[Dict], List[Dict]]:
    """Import jobs from file with validation.

    Args:
        file_path: Path to file
        file_type: Optional file type ('pdf', 'text', 'json', 'csv').
                  If None, will be inferred from extension
        validate_freshness: Whether to apply 24-hour freshness filter

    Returns:
        Tuple of (valid_jobs, invalid_jobs_with_reasons)

    Raises:
        ValueError: If file type is not supported or file cannot be parsed
    """
    # Infer file type from extension if not provided
    if file_type is None:
        if file_path.endswith('.pdf'):
            file_type = 'pdf'
        elif file_path.endswith(('.txt', '.md')):
            file_type = 'text'
        elif file_path.endswith('.json'):
            file_type = 'json'
        elif file_path.endswith('.csv'):
            file_type = 'csv'
        else:
            raise ValueError("Unsupported file type. Use .pdf, .txt, .md, .json, or .csv")

    # Parse based on file type
    if file_type == 'pdf':
        jobs = parse_pdf(file_path)
    elif file_type == 'text':
        jobs = parse_text(file_path)
    elif file_type == 'json':
        jobs = parse_json(file_path)
    elif file_type == 'csv':
        jobs = parse_csv(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    # Validate and normalize jobs
    valid_jobs = []
    invalid_jobs = []

    for job in jobs:
        # Normalize data
        job = normalize_job_data(job)

        # Validate
        is_valid, error = validate_job_posting(job, check_freshness=validate_freshness)

        if is_valid:
            valid_jobs.append(job)
        else:
            invalid_jobs.append({
                'job': job,
                'error': error
            })

    return valid_jobs, invalid_jobs
