"""Unit tests for job posting validators."""

import pytest
from datetime import datetime, timedelta
from src.importers.validators import (
    validate_24_hour_freshness,
    validate_required_fields,
    validate_job_posting,
    normalize_job_data,
)


def test_validate_24_hour_freshness_valid():
    """Test 24-hour freshness validation with valid date."""
    # Job posted 1 hour ago
    recent_date = datetime.utcnow() - timedelta(hours=1)
    assert validate_24_hour_freshness(recent_date) is True


def test_validate_24_hour_freshness_boundary():
    """Test 24-hour freshness at exact boundary."""
    # Job posted just under 24 hours ago should pass
    almost_24 = datetime.utcnow() - timedelta(hours=23, minutes=59)
    assert validate_24_hour_freshness(almost_24) is True

    # Job posted exactly 24 hours ago should fail
    exactly_24 = datetime.utcnow() - timedelta(hours=24)
    assert validate_24_hour_freshness(exactly_24) is False


def test_validate_24_hour_freshness_invalid():
    """Test 24-hour freshness validation with old date."""
    # Job posted 25 hours ago
    old_date = datetime.utcnow() - timedelta(hours=25)
    assert validate_24_hour_freshness(old_date) is False


def test_validate_24_hour_freshness_very_old():
    """Test 24-hour freshness with very old date."""
    # Job posted 7 days ago
    old_date = datetime.utcnow() - timedelta(days=7)
    assert validate_24_hour_freshness(old_date) is False


def test_validate_required_fields_complete():
    """Test validation with all required fields."""
    job_data = {
        'title': 'Product Manager',
        'company': 'TechCorp',
        'posting_date': datetime.utcnow()
    }

    is_valid, missing = validate_required_fields(job_data)
    assert is_valid is True
    assert len(missing) == 0


def test_validate_required_fields_missing_title():
    """Test validation with missing title."""
    job_data = {
        'company': 'TechCorp',
        'posting_date': datetime.utcnow()
    }

    is_valid, missing = validate_required_fields(job_data)
    assert is_valid is False
    assert 'title' in missing


def test_validate_required_fields_missing_multiple():
    """Test validation with multiple missing fields."""
    job_data = {
        'description': 'Some description'
    }

    is_valid, missing = validate_required_fields(job_data)
    assert is_valid is False
    assert 'title' in missing
    assert 'company' in missing
    assert 'posting_date' in missing


def test_validate_required_fields_empty_values():
    """Test validation with empty string values."""
    job_data = {
        'title': '',
        'company': 'TechCorp',
        'posting_date': datetime.utcnow()
    }

    is_valid, missing = validate_required_fields(job_data)
    assert is_valid is False
    assert 'title' in missing


def test_validate_job_posting_valid():
    """Test complete job posting validation with valid data."""
    job_data = {
        'title': 'Product Manager',
        'company': 'TechCorp',
        'posting_date': datetime.utcnow()
    }

    is_valid, error = validate_job_posting(job_data, check_freshness=True)
    assert is_valid is True
    assert error is None


def test_validate_job_posting_old_date():
    """Test validation with old posting date."""
    job_data = {
        'title': 'Product Manager',
        'company': 'TechCorp',
        'posting_date': datetime.utcnow() - timedelta(days=2)
    }

    is_valid, error = validate_job_posting(job_data, check_freshness=True)
    assert is_valid is False
    assert 'older than 24 hours' in error


def test_validate_job_posting_skip_freshness():
    """Test validation with freshness check disabled."""
    job_data = {
        'title': 'Product Manager',
        'company': 'TechCorp',
        'posting_date': datetime.utcnow() - timedelta(days=2)
    }

    is_valid, error = validate_job_posting(job_data, check_freshness=False)
    assert is_valid is True
    assert error is None


def test_validate_job_posting_invalid_date_type():
    """Test validation with invalid posting_date type."""
    job_data = {
        'title': 'Product Manager',
        'company': 'TechCorp',
        'posting_date': '2024-01-15'  # String instead of datetime
    }

    is_valid, error = validate_job_posting(job_data, check_freshness=True)
    assert is_valid is False
    assert 'datetime object' in error


def test_validate_job_posting_missing_fields():
    """Test validation with missing required fields."""
    job_data = {
        'title': 'Product Manager'
    }

    is_valid, error = validate_job_posting(job_data, check_freshness=False)
    assert is_valid is False
    assert 'Missing required fields' in error


def test_normalize_job_data_trim_whitespace():
    """Test normalization trims whitespace."""
    job_data = {
        'title': '  Product Manager  ',
        'company': '  TechCorp  '
    }

    normalized = normalize_job_data(job_data)
    assert normalized['title'] == 'Product Manager'
    assert normalized['company'] == 'TechCorp'


def test_normalize_job_data_skills_string_to_list():
    """Test normalization converts skills string to list."""
    job_data = {
        'title': 'PM',
        'company': 'Corp',
        'required_skills': 'Agile, Scrum, Product Management'
    }

    normalized = normalize_job_data(job_data)
    assert isinstance(normalized['required_skills'], list)
    assert 'Agile' in normalized['required_skills']
    assert 'Scrum' in normalized['required_skills']
    assert 'Product Management' in normalized['required_skills']


def test_normalize_job_data_skills_already_list():
    """Test normalization preserves skills list."""
    job_data = {
        'title': 'PM',
        'company': 'Corp',
        'required_skills': ['Agile', 'Scrum']
    }

    normalized = normalize_job_data(job_data)
    assert normalized['required_skills'] == ['Agile', 'Scrum']


def test_normalize_job_data_preserves_other_fields():
    """Test normalization preserves other fields."""
    job_data = {
        'title': 'PM',
        'company': 'Corp',
        'location': 'SF',
        'description': 'Great job',
        'url': 'https://example.com'
    }

    normalized = normalize_job_data(job_data)
    assert normalized['location'] == 'SF'
    assert normalized['description'] == 'Great job'
    assert normalized['url'] == 'https://example.com'
