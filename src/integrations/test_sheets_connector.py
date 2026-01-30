"""Tests for Google Sheets connector."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.integrations.sheets_connector import SheetsConnector


@pytest.fixture
def mock_config_disabled():
    """Mock configuration with Sheets disabled."""
    with patch('src.integrations.sheets_connector.get_config') as mock:
        config = Mock()
        config.get.side_effect = lambda key, default=None: {
            "sheets.enabled": False,
        }.get(key, default)
        mock.return_value = config
        yield config


@pytest.fixture
def mock_config_enabled():
    """Mock configuration with Sheets enabled."""
    with patch('src.integrations.sheets_connector.get_config') as mock:
        config = Mock()
        config.get.side_effect = lambda key, default=None: {
            "sheets.enabled": True,
            "sheets.spreadsheet_id": "test_spreadsheet_id",
            "sheets.sheet_name": "Job Matches",
            "sheets.credentials_path": "credentials.json",
            "sheets.token_path": "sheets_token.json",
            "sheets.export_min_score": 0.7,
            "sheets.auto_export": True,
            "sheets.include_skill_gaps": True,
            "sheets.include_matching_skills": True,
            "sheets.max_skills_display": 10,
        }.get(key, default)
        mock.return_value = config
        yield config


@pytest.fixture
def sample_match():
    """Sample job match for testing."""
    return {
        'job_title': 'Senior Product Manager',
        'company': 'TechCorp',
        'location': 'San Francisco, CA',
        'url': 'https://example.com/job/123',
        'overall_score': 0.85,
        'skills_score': 0.9,
        'experience_score': 0.8,
        'matching_skills': ['Python', 'SQL', 'Product Management', 'Agile'],
        'skill_gaps': ['Machine Learning', 'AWS'],
        'match_id': 1,
        'resume_id': 1,
    }


def test_sheets_connector_initialization_disabled(mock_config_disabled):
    """Test SheetsConnector initialization when disabled."""
    connector = SheetsConnector()

    assert connector.enabled is False
    assert connector.service is None


def test_sheets_connector_initialization_enabled(mock_config_enabled):
    """Test SheetsConnector initialization when enabled."""
    connector = SheetsConnector()

    assert connector.enabled is True
    assert connector.spreadsheet_id == "test_spreadsheet_id"
    assert connector.sheet_name == "Job Matches"
    assert connector.export_min_score == 0.7


def test_authenticate_when_disabled(mock_config_disabled):
    """Test that authentication returns False when Sheets is disabled."""
    connector = SheetsConnector()

    result = connector.authenticate()

    assert result is False


@patch('src.integrations.sheets_connector.build')
@patch('src.integrations.sheets_connector.Credentials')
def test_authenticate_with_existing_valid_token(mock_creds_class, mock_build, mock_config_enabled):
    """Test authentication with existing valid token."""
    # Mock existing valid credentials
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    # Mock Sheets service
    mock_service = Mock()
    mock_build.return_value = mock_service

    with patch('os.path.exists', return_value=True):
        connector = SheetsConnector()
        result = connector.authenticate()

    assert result is True
    assert connector.service == mock_service


def test_export_when_disabled(mock_config_disabled, sample_match):
    """Test that exports are not performed when Sheets is disabled."""
    connector = SheetsConnector()

    result = connector.export_match(sample_match)

    assert result is False


def test_export_below_threshold(mock_config_enabled, sample_match):
    """Test that matches below threshold are not exported."""
    connector = SheetsConnector()

    # Create match below threshold
    low_match = sample_match.copy()
    low_match['overall_score'] = 0.5  # Below 0.7 threshold

    result = connector.export_match(low_match)

    assert result is False


def test_prepare_row_data(mock_config_enabled, sample_match):
    """Test row data preparation."""
    connector = SheetsConnector()

    row_data = connector._prepare_row_data(sample_match)

    # Check that row has expected number of columns
    assert len(row_data) > 10  # At least basic columns
    assert row_data[1] == 'Senior Product Manager'  # Job title
    assert row_data[2] == 'TechCorp'  # Company
    assert row_data[4] == 85.0  # Overall score as percentage
    assert row_data[5] == 90.0  # Skills score
    assert row_data[6] == 80.0  # Experience score


def test_prepare_row_data_with_long_skill_lists(mock_config_enabled):
    """Test row data preparation with many skills."""
    connector = SheetsConnector()

    match_with_many_skills = {
        'job_title': 'Product Manager',
        'company': 'TestCo',
        'location': 'NYC',
        'url': 'https://example.com',
        'overall_score': 0.8,
        'skills_score': 0.75,
        'experience_score': 0.85,
        'matching_skills': [f'Skill{i}' for i in range(15)],  # 15 skills
        'skill_gaps': [f'Gap{i}' for i in range(12)],  # 12 gaps
        'match_id': 1,
        'resume_id': 1,
    }

    row_data = connector._prepare_row_data(match_with_many_skills)

    # Check that skills are truncated with "+X more" indicator
    matching_skills_cell = row_data[7]  # Matching skills column
    assert '+' in matching_skills_cell
    assert 'more' in matching_skills_cell


@patch('src.integrations.sheets_connector.build')
@patch('src.integrations.sheets_connector.Credentials')
def test_export_match_success(mock_creds_class, mock_build, mock_config_enabled, sample_match):
    """Test successful single match export."""
    # Setup mocks
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    mock_service = Mock()
    mock_build.return_value = mock_service

    # Mock append response
    mock_append = Mock()
    mock_append.execute.return_value = {'updates': {'updatedRows': 1}}
    mock_service.spreadsheets().values().append.return_value = mock_append

    with patch('os.path.exists', return_value=True):
        connector = SheetsConnector()
        connector.authenticate()

        result = connector.export_match(sample_match)

    assert result is True


def test_batch_export_when_disabled(mock_config_disabled, sample_match):
    """Test batch export when Sheets is disabled."""
    connector = SheetsConnector()

    matches = [sample_match, sample_match]
    exported_count = connector.export_matches_batch(matches)

    assert exported_count == 0


@patch('src.integrations.sheets_connector.build')
@patch('src.integrations.sheets_connector.Credentials')
def test_batch_export_filters_by_threshold(mock_creds_class, mock_build, mock_config_enabled):
    """Test batch export filters matches by threshold."""
    # Setup mocks
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    mock_service = Mock()
    mock_build.return_value = mock_service

    # Mock append response
    mock_append = Mock()
    mock_append.execute.return_value = {'updates': {'updatedRows': 2}}
    mock_service.spreadsheets().values().append.return_value = mock_append

    matches = [
        {'job_title': 'PM1', 'company': 'Co1', 'location': 'SF', 'url': 'http://1',
         'overall_score': 0.85, 'skills_score': 0.9, 'experience_score': 0.8,
         'matching_skills': [], 'skill_gaps': [], 'match_id': 1, 'resume_id': 1},
        {'job_title': 'PM2', 'company': 'Co2', 'location': 'NYC', 'url': 'http://2',
         'overall_score': 0.5, 'skills_score': 0.6, 'experience_score': 0.4,
         'matching_skills': [], 'skill_gaps': [], 'match_id': 2, 'resume_id': 1},
        {'job_title': 'PM3', 'company': 'Co3', 'location': 'LA', 'url': 'http://3',
         'overall_score': 0.75, 'skills_score': 0.8, 'experience_score': 0.7,
         'matching_skills': [], 'skill_gaps': [], 'match_id': 3, 'resume_id': 1},
    ]

    with patch('os.path.exists', return_value=True):
        connector = SheetsConnector()
        connector.authenticate()

        exported_count = connector.export_matches_batch(matches)

    # Should export 2 matches (>= 0.7 threshold), not 3
    assert exported_count == 2


def test_get_sheet_id(mock_config_enabled):
    """Test getting sheet ID from sheet name."""
    connector = SheetsConnector()
    connector.service = Mock()

    # Mock spreadsheet metadata
    mock_metadata = {
        'sheets': [
            {'properties': {'sheetId': 123, 'title': 'Job Matches'}},
            {'properties': {'sheetId': 456, 'title': 'Other Sheet'}},
        ]
    }
    connector.service.spreadsheets().get().execute.return_value = mock_metadata

    sheet_id = connector._get_sheet_id()

    assert sheet_id == 123
