"""Unit tests for Apify API importer."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from src.importers.apify_provider import ApifyJobProvider, ApifyJobImporter, create_apify_importer


@pytest.fixture
def mock_apify_response():
    """Mock Apify API response for vulnv/linkedin-jobs-scraper."""
    return [
        {
            'job_title': 'Senior Product Manager',
            'company_name': 'TechCorp',
            'job_location': 'San Francisco, CA',
            'job_summary': 'Great PM opportunity',
            'url': 'https://linkedin.com/jobs/123',
            'job_posted_date': datetime.utcnow().isoformat() + 'Z',
            'job_function': 'Product Management',
            'job_industries': 'Technology, Software',
            'job_seniority_level': '5+ years',
            'job_employment_type': 'Full-time',
        },
        {
            'job_title': 'Product Manager',
            'company_name': 'StartupHub',
            'job_location': 'Remote',
            'job_summary': 'Join our startup',
            'url': 'https://linkedin.com/jobs/456',
            'job_posted_date': datetime.utcnow().isoformat() + 'Z',
            'job_function': 'Product Management',
            'job_industries': 'Internet, Startups',
            'job_seniority_level': 'Mid-Senior level',
            'job_employment_type': 'Full-time',
        }
    ]


@pytest.fixture
def mock_old_job():
    """Mock old job posting (older than 24 hours)."""
    old_date = (datetime.utcnow() - timedelta(days=2)).isoformat() + 'Z'
    return {
        'job_title': 'Old Product Manager Job',
        'company_name': 'OldCompany',
        'job_location': 'NYC',
        'job_posted_date': old_date,
    }


def _make_mock_config(api_key=None, raise_on_key=False):
    """Create a mock config object with proper .get() behavior."""
    config = Mock()
    config.get.side_effect = lambda key, default=None: {
        "apify.use_mock_data": False,
        "apify.mock_data_file": "dataset.json",
    }.get(key, default)
    if raise_on_key:
        config.get_apify_api_key.side_effect = ValueError("API key not configured")
    elif api_key:
        config.get_apify_api_key.return_value = api_key
    return config


def test_apify_importer_initialization_with_key():
    """Test initializing Apify importer with API key."""
    importer = ApifyJobImporter(api_key='test_key_123')
    assert importer.api_key == 'test_key_123'
    assert importer.client is not None


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_apify_importer_initialization_without_key(mock_apify_client, mock_apify_client_async):
    """Test initializing without API key raises error."""
    mock_config = _make_mock_config(raise_on_key=True)
    with patch('src.config.get_config', return_value=mock_config):
        with pytest.raises(ValueError, match="Apify API key is required"):
            ApifyJobImporter()


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_apify_importer_reads_config_key(mock_apify_client, mock_apify_client_async):
    """Test reading API key from config."""
    mock_config = _make_mock_config(api_key='config_test_key')
    with patch('src.config.get_config', return_value=mock_config):
        importer = ApifyJobImporter()
        assert importer.api_key == 'config_test_key'


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_search_jobs_success(mock_apify_client, mock_apify_client_async, mock_apify_response):
    """Test successful job search."""
    # Setup mocks: .actor()/.dataset() are sync, .call()/.list_items() are async
    mock_actor = Mock()
    mock_actor.call = AsyncMock(return_value={'defaultDatasetId': 'dataset_123'})

    mock_dataset = Mock()
    mock_items = Mock()
    mock_items.items = mock_apify_response
    mock_dataset.list_items = AsyncMock(return_value=mock_items)

    mock_async_instance = Mock()
    mock_async_instance.actor.return_value = mock_actor
    mock_async_instance.dataset.return_value = mock_dataset

    mock_apify_client_async.return_value = mock_async_instance

    # Test
    importer = ApifyJobImporter(api_key='test_key')
    results = importer.search_jobs(keywords='Product Manager', location='San Francisco')

    assert len(results) == 2
    assert results == mock_apify_response
    mock_actor.call.assert_called_once()


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_search_jobs_with_parameters(mock_apify_client, mock_apify_client_async):
    """Test job search with all parameters."""
    # Setup mocks: .actor()/.dataset() are sync, .call()/.list_items() are async
    mock_actor = Mock()
    mock_actor.call = AsyncMock(return_value={'defaultDatasetId': 'dataset_123'})

    mock_dataset = Mock()
    mock_items = Mock()
    mock_items.items = []
    mock_dataset.list_items = AsyncMock(return_value=mock_items)

    mock_async_instance = Mock()
    mock_async_instance.actor.return_value = mock_actor
    mock_async_instance.dataset.return_value = mock_dataset

    mock_apify_client_async.return_value = mock_async_instance

    # Test
    importer = ApifyJobImporter(api_key='test_key')
    importer.search_jobs(
        keywords='Product Manager',
        location='Toronto, Ontario, Canada',
        job_type='Full-time',
        max_results=100,
        experience_level='Mid-Senior level',
        work_arrangement='Remote'
    )

    # Verify call was made with correct parameters (new API field names)
    call_args = mock_actor.call.call_args
    run_input = call_args.kwargs['run_input']

    assert run_input['keyword'] == 'Product Manager'
    assert run_input['location'] == 'Toronto, Ontario, Canada'
    assert run_input['job_type'] == 'Full-time'
    assert run_input['max_jobs'] == 100
    assert run_input['experience_level'] == 'Mid-Senior level'
    assert run_input['remote'] == 'Remote'
    assert run_input['time_range'] == 'Past 24 hours'  # Default value


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
@patch('asyncio.sleep', new_callable=AsyncMock)
def test_search_jobs_retry_logic(mock_sleep, mock_apify_client, mock_apify_client_async):
    """Test retry logic on API failures."""
    # Setup mocks to fail twice then succeed
    mock_actor = Mock()
    mock_actor.call = AsyncMock(side_effect=[
        Exception("API Error 1"),
        Exception("API Error 2"),
        {'defaultDatasetId': 'dataset_123'}
    ])

    mock_dataset = Mock()
    mock_items = Mock()
    mock_items.items = []
    mock_dataset.list_items = AsyncMock(return_value=mock_items)

    mock_async_instance = Mock()
    mock_async_instance.actor.return_value = mock_actor
    mock_async_instance.dataset.return_value = mock_dataset

    mock_apify_client_async.return_value = mock_async_instance

    # Test
    importer = ApifyJobImporter(api_key='test_key')
    results = importer.search_jobs(keywords='Product Manager')

    # Should have retried and eventually succeeded
    assert mock_actor.call.call_count == 3
    assert mock_sleep.call_count == 2  # Sleep between retries


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_search_jobs_max_retries_exceeded(mock_apify_client, mock_apify_client_async):
    """Test that max retries returns empty results (gather swallows exceptions)."""
    # Setup mock to always fail
    mock_actor = Mock()
    mock_actor.call = AsyncMock(side_effect=Exception("API Error"))

    mock_async_instance = Mock()
    mock_async_instance.actor.return_value = mock_actor

    mock_apify_client_async.return_value = mock_async_instance

    # Test - search_jobs_async uses gather(return_exceptions=True),
    # so failures result in empty list rather than raised exception
    importer = ApifyJobImporter(api_key='test_key')
    results = importer.search_jobs(keywords='Product Manager')
    assert results == []


def test_normalize_apify_job_standard_fields():
    """Test normalization of vulnv/linkedin-jobs-scraper job fields."""
    raw_job = {
        'job_title': 'Product Manager',
        'company_name': 'TechCorp',
        'job_location': 'SF',
        'job_summary': 'Great job',
        'url': 'https://example.com',
        'job_posted_date': '2024-01-15T10:00:00Z',
        'job_function': 'Product Management',
        'job_industries': 'Technology, Software',
        'job_seniority_level': '5 years',
    }

    importer = ApifyJobImporter(api_key='test_key')
    normalized = importer.normalize_job(raw_job)

    assert normalized['title'] == 'Product Manager'
    assert normalized['company'] == 'TechCorp'
    assert normalized['location'] == 'SF'
    assert normalized['description'] == 'Great job'
    assert normalized['url'] == 'https://example.com'
    assert normalized['required_skills'] == []  # Skills are populated later by NLP/Gemini extraction
    assert normalized['experience_required'] == 5.0
    assert normalized['source'] == 'api'


def test_normalize_apify_job_missing_fields():
    """Test normalization with missing optional fields."""
    raw_job = {
        'job_title': 'Senior PM',
        'company_name': 'StartupInc',
        'job_location': 'Remote',
        'job_summary': 'Amazing role',
        'url': 'https://job.com',
        # Missing: job_posted_date, job_function, job_industries, job_seniority_level
    }

    importer = ApifyJobImporter(api_key='test_key')
    normalized = importer.normalize_job(raw_job)

    assert normalized['title'] == 'Senior PM'
    assert normalized['company'] == 'StartupInc'
    assert normalized['location'] == 'Remote'
    assert isinstance(normalized['required_skills'], list)
    assert 'posting_date' in normalized  # Should default to current time
    assert normalized['source'] == 'api'


def test_normalize_apify_job_seniority_mapping():
    """Test seniority level to years mapping."""
    importer = ApifyJobImporter(api_key='test_key')

    test_cases = [
        ('Entry level', 0),
        ('Associate', 0),
        ('Junior', 1),
        ('Mid-Senior level', 3),
        ('Senior', 5),
        ('Lead', 7),
        ('Staff', 7),
        ('Principal', 10),
        ('Director', 12),
        ('Executive', 15),
    ]

    for seniority, expected_years in test_cases:
        raw_job = {
            'job_title': 'PM',
            'company_name': 'Corp',
            'job_seniority_level': seniority,
        }
        normalized = importer.normalize_job(raw_job)
        assert normalized.get('experience_required') == expected_years


def test_normalize_apify_job_missing_posting_date():
    """Test normalization defaults to current time when date missing."""
    raw_job = {
        'job_title': 'PM',
        'company_name': 'Corp',
    }

    importer = ApifyJobImporter(api_key='test_key')
    normalized = importer.normalize_job(raw_job)

    assert 'posting_date' in normalized
    assert isinstance(normalized['posting_date'], datetime)


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_fetch_and_validate_jobs(mock_apify_client, mock_apify_client_async, mock_apify_response):
    """Test fetching and validating jobs."""
    # Setup mocks: .actor()/.dataset() are sync, .call()/.list_items() are async
    mock_actor = Mock()
    mock_actor.call = AsyncMock(return_value={'defaultDatasetId': 'dataset_123'})

    mock_dataset = Mock()
    mock_items = Mock()
    mock_items.items = mock_apify_response
    mock_dataset.list_items = AsyncMock(return_value=mock_items)

    mock_async_instance = Mock()
    mock_async_instance.actor.return_value = mock_actor
    mock_async_instance.dataset.return_value = mock_dataset

    mock_apify_client_async.return_value = mock_async_instance

    # Test
    importer = ApifyJobImporter(api_key='test_key')
    valid_jobs, invalid_jobs = importer.fetch_and_validate_jobs(
        keywords='Product Manager',
        validate_freshness=False  # Disable for testing
    )

    assert len(valid_jobs) > 0
    assert all('title' in job for job in valid_jobs)
    assert all('company' in job for job in valid_jobs)


@patch('src.importers.apify_provider.ApifyClientAsync')
@patch('src.importers.apify_provider.ApifyClient')
def test_fetch_and_validate_jobs_with_freshness(mock_apify_client, mock_apify_client_async, mock_old_job):
    """Test freshness validation filters old jobs."""
    # Setup mocks: .actor()/.dataset() are sync, .call()/.list_items() are async
    mock_actor = Mock()
    mock_actor.call = AsyncMock(return_value={'defaultDatasetId': 'dataset_123'})

    mock_dataset = Mock()
    mock_items = Mock()
    mock_items.items = [mock_old_job]
    mock_dataset.list_items = AsyncMock(return_value=mock_items)

    mock_async_instance = Mock()
    mock_async_instance.actor.return_value = mock_actor
    mock_async_instance.dataset.return_value = mock_dataset

    mock_apify_client_async.return_value = mock_async_instance

    # Test
    importer = ApifyJobImporter(api_key='test_key')
    valid_jobs, invalid_jobs = importer.fetch_and_validate_jobs(
        keywords='Product Manager',
        validate_freshness=True
    )

    # Old job should be filtered out
    assert len(valid_jobs) == 0
    assert len(invalid_jobs) > 0
    assert 'older than 24 hours' in invalid_jobs[0]['error']


def test_create_apify_importer_factory():
    """Test factory function."""
    importer = create_apify_importer(api_key='factory_test_key')
    assert isinstance(importer, ApifyJobImporter)
    assert importer.api_key == 'factory_test_key'
