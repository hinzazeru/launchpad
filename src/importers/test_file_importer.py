"""Unit tests for file-based job importer."""

import pytest
import os
from datetime import datetime
from src.importers.file_importer import (
    parse_text,
    parse_json,
    parse_csv,
    import_jobs_from_file,
)


@pytest.fixture
def fixtures_dir():
    """Get path to fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "../../tests/fixtures")


@pytest.fixture
def sample_json_path(fixtures_dir):
    """Get path to sample JSON file."""
    return os.path.join(fixtures_dir, "sample_jobs.json")


@pytest.fixture
def sample_csv_path(fixtures_dir):
    """Get path to sample CSV file."""
    return os.path.join(fixtures_dir, "sample_jobs.csv")


@pytest.fixture
def sample_text_path(fixtures_dir):
    """Get path to sample text file."""
    return os.path.join(fixtures_dir, "sample_jobs.txt")


def test_parse_json(sample_json_path):
    """Test parsing JSON file."""
    jobs = parse_json(sample_json_path)

    assert isinstance(jobs, list)
    assert len(jobs) > 0

    # Check first job
    job = jobs[0]
    assert 'title' in job
    assert 'company' in job
    assert 'posting_date' in job
    assert isinstance(job['posting_date'], datetime)
    assert job['source'] == 'json'


def test_parse_json_fields(sample_json_path):
    """Test JSON parsing extracts all fields."""
    jobs = parse_json(sample_json_path)
    job = jobs[0]

    assert job['title'] == 'Senior Product Manager'
    assert job['company'] == 'TechCorp'
    assert isinstance(job['required_skills'], list)
    assert 'Product Management' in job['required_skills']
    assert job['experience_required'] == 5
    assert job['url'].startswith('https://')


def test_parse_json_invalid_file():
    """Test parsing invalid JSON file."""
    import tempfile

    # Create temp file with invalid JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{invalid json content")
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_json(temp_path)
    finally:
        os.remove(temp_path)


def test_parse_csv(sample_csv_path):
    """Test parsing CSV file."""
    jobs = parse_csv(sample_csv_path)

    assert isinstance(jobs, list)
    assert len(jobs) > 0

    # Check first job
    job = jobs[0]
    assert 'title' in job
    assert 'company' in job
    assert 'posting_date' in job
    assert isinstance(job['posting_date'], datetime)
    assert job['source'] == 'csv'


def test_parse_csv_fields(sample_csv_path):
    """Test CSV parsing extracts all fields."""
    jobs = parse_csv(sample_csv_path)
    job = jobs[0]

    assert job['title'] == 'Senior Product Manager'
    assert job['company'] == 'TechCorp'
    assert isinstance(job['required_skills'], list)
    assert len(job['required_skills']) > 0


def test_parse_csv_skills_parsing(sample_csv_path):
    """Test CSV correctly parses comma-separated skills."""
    jobs = parse_csv(sample_csv_path)
    job = jobs[0]

    assert 'Product Management' in job['required_skills']
    assert 'Agile' in job['required_skills']
    assert 'Roadmapping' in job['required_skills']


def test_parse_text(sample_text_path):
    """Test parsing text file."""
    jobs = parse_text(sample_text_path)

    assert isinstance(jobs, list)
    assert len(jobs) > 0

    # Check first job
    job = jobs[0]
    assert 'title' in job
    assert 'company' in job
    assert job['source'] == 'text'


def test_parse_text_fields(sample_text_path):
    """Test text parsing extracts all fields."""
    jobs = parse_text(sample_text_path)
    job = jobs[0]

    assert 'Senior Product Manager' in job['title']
    assert job['company'] == 'TechCorp'
    assert 'location' in job
    assert isinstance(job['required_skills'], list)
    assert len(job['required_skills']) > 0


def test_parse_text_multiple_jobs(sample_text_path):
    """Test parsing multiple jobs from text file."""
    jobs = parse_text(sample_text_path)

    # Should have at least 2 jobs separated by "---"
    assert len(jobs) >= 2


def test_import_jobs_from_file_json(sample_json_path):
    """Test importing jobs from JSON file with validation."""
    valid_jobs, invalid_jobs = import_jobs_from_file(
        sample_json_path,
        file_type='json',
        validate_freshness=False  # Disable freshness for testing
    )

    assert len(valid_jobs) > 0
    # With freshness disabled, all should be valid
    assert len(invalid_jobs) == 0


def test_import_jobs_from_file_csv(sample_csv_path):
    """Test importing jobs from CSV file."""
    valid_jobs, invalid_jobs = import_jobs_from_file(
        sample_csv_path,
        file_type='csv',
        validate_freshness=False
    )

    assert len(valid_jobs) > 0
    assert len(invalid_jobs) == 0


def test_import_jobs_from_file_text(sample_text_path):
    """Test importing jobs from text file."""
    valid_jobs, invalid_jobs = import_jobs_from_file(
        sample_text_path,
        file_type='text',
        validate_freshness=False
    )

    assert len(valid_jobs) > 0


def test_import_jobs_infer_type_json(sample_json_path):
    """Test file type inference from extension."""
    valid_jobs, invalid_jobs = import_jobs_from_file(
        sample_json_path,
        validate_freshness=False
    )

    assert len(valid_jobs) > 0


def test_import_jobs_infer_type_csv(sample_csv_path):
    """Test file type inference for CSV."""
    valid_jobs, invalid_jobs = import_jobs_from_file(
        sample_csv_path,
        validate_freshness=False
    )

    assert len(valid_jobs) > 0


def test_import_jobs_with_freshness_validation():
    """Test import with freshness validation enabled."""
    import json
    import tempfile

    # Create temp JSON with today's date
    today = datetime.utcnow().strftime('%Y-%m-%d')
    fresh_jobs = {
        "jobs": [
            {
                "title": "Product Manager",
                "company": "TestCorp",
                "posting_date": today,
                "required_skills": ["PM", "Agile"]
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(fresh_jobs, f)
        temp_path = f.name

    try:
        valid_jobs, invalid_jobs = import_jobs_from_file(
            temp_path,
            validate_freshness=True
        )

        # Jobs with today's date should be valid
        assert len(valid_jobs) > 0
    finally:
        os.remove(temp_path)


def test_import_jobs_unsupported_extension():
    """Test import with unsupported file extension."""
    with pytest.raises(ValueError, match="Unsupported file type"):
        import_jobs_from_file("file.xlsx")


def test_import_jobs_normalization(sample_csv_path):
    """Test that imported jobs are normalized."""
    valid_jobs, invalid_jobs = import_jobs_from_file(
        sample_csv_path,
        validate_freshness=False
    )

    # Check normalization (trimmed whitespace, etc.)
    for job in valid_jobs:
        assert job['title'] == job['title'].strip()
        assert job['company'] == job['company'].strip()
        if 'required_skills' in job:
            assert isinstance(job['required_skills'], list)


def test_import_jobs_validation_errors(fixtures_dir):
    """Test that invalid jobs are caught."""
    # Create a temporary invalid JSON
    import json
    import tempfile

    invalid_data = {
        "jobs": [
            {
                "title": "Job without company"
                # Missing company and posting_date
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_data, f)
        temp_path = f.name

    try:
        valid_jobs, invalid_jobs = import_jobs_from_file(
            temp_path,
            validate_freshness=False
        )

        # Job should be invalid due to missing company
        assert len(invalid_jobs) > 0
        assert 'error' in invalid_jobs[0]

    finally:
        os.remove(temp_path)
