"""Tests for email notification functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.notifications.email_notifier import EmailNotifier


@pytest.fixture
def mock_config_disabled():
    """Mock configuration with email disabled."""
    with patch('src.notifications.email_notifier.get_config') as mock:
        config = Mock()
        config.get.side_effect = lambda key, default=None: {
            "email.enabled": False,
        }.get(key, default)
        mock.return_value = config
        yield config


@pytest.fixture
def mock_config_enabled():
    """Mock configuration with email enabled."""
    with patch('src.notifications.email_notifier.get_config') as mock:
        config = Mock()
        config.get.side_effect = lambda key, default=None: {
            "email.enabled": True,
            "email.credentials_path": "credentials.json",
            "email.token_path": "token.json",
            "email.from_address": "sender@gmail.com",
            "email.to_address": "recipient@gmail.com",
            "email.subject_template": "New Job Match: {job_title} at {company}",
            "email.notify_min_score": 0.7,
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
        'matching_skills': ['Python', 'SQL', 'Product Management', 'Agile', 'Data Analysis'],
        'skill_gaps': ['Machine Learning', 'AWS'],
    }


def test_email_notifier_initialization_disabled(mock_config_disabled):
    """Test EmailNotifier initialization when disabled."""
    notifier = EmailNotifier()

    assert notifier.enabled is False
    assert notifier.service is None


def test_email_notifier_initialization_enabled(mock_config_enabled):
    """Test EmailNotifier initialization when enabled."""
    notifier = EmailNotifier()

    assert notifier.enabled is True
    assert notifier.from_address == "sender@gmail.com"
    assert notifier.to_address == "recipient@gmail.com"
    assert notifier.notify_min_score == 0.7


def test_generate_job_match_html(mock_config_enabled, sample_match):
    """Test HTML email generation."""
    notifier = EmailNotifier()
    html = notifier.generate_job_match_html(sample_match)

    # Check key elements are present
    assert 'Senior Product Manager' in html
    assert 'TechCorp' in html
    assert '85%' in html
    assert 'Python' in html
    assert 'Machine Learning' in html


def test_generate_job_match_text(mock_config_enabled, sample_match):
    """Test plain text email generation."""
    notifier = EmailNotifier()
    text = notifier.generate_job_match_text(sample_match)

    # Check key elements are present
    assert 'Senior Product Manager' in text
    assert 'TechCorp' in text
    assert '85%' in text
    assert 'Python' in text
    assert 'Machine Learning' in text


def test_create_message(mock_config_enabled):
    """Test message creation."""
    notifier = EmailNotifier()

    message = notifier.create_message(
        to="recipient@gmail.com",
        subject="Test Subject",
        html_body="<html><body>Test HTML</body></html>",
        text_body="Test Text"
    )

    assert 'raw' in message
    assert isinstance(message['raw'], str)


def test_send_notification_when_disabled(mock_config_disabled, sample_match):
    """Test that notifications are not sent when disabled."""
    notifier = EmailNotifier()

    result = notifier.send_job_match_notification(sample_match)

    assert result is False


def test_send_notification_below_threshold(mock_config_enabled, sample_match):
    """Test that notifications are not sent when score is below threshold."""
    notifier = EmailNotifier()

    # Create match below threshold
    low_match = sample_match.copy()
    low_match['overall_score'] = 0.5  # Below 0.7 threshold

    result = notifier.send_job_match_notification(low_match)

    assert result is False


@patch('src.notifications.email_notifier.build')
@patch('src.notifications.email_notifier.Credentials')
def test_authenticate_with_existing_valid_token(mock_creds_class, mock_build, mock_config_enabled):
    """Test authentication with existing valid token."""
    # Mock existing valid credentials
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    # Mock Gmail service
    mock_service = Mock()
    mock_build.return_value = mock_service

    with patch('os.path.exists', return_value=True):
        notifier = EmailNotifier()
        result = notifier.authenticate()

    assert result is True
    assert notifier.service == mock_service


def test_authenticate_when_disabled(mock_config_disabled):
    """Test that authentication returns False when email is disabled."""
    notifier = EmailNotifier()

    result = notifier.authenticate()

    assert result is False


@patch('src.notifications.email_notifier.build')
@patch('src.notifications.email_notifier.Credentials')
def test_send_message_success(mock_creds_class, mock_build, mock_config_enabled):
    """Test sending message successfully."""
    # Setup mocks
    mock_creds = Mock()
    mock_creds.valid = True
    mock_creds_class.from_authorized_user_file.return_value = mock_creds

    mock_service = Mock()
    mock_build.return_value = mock_service

    # Mock send response
    mock_send = Mock()
    mock_send.execute.return_value = {'id': '123'}
    mock_service.users().messages().send.return_value = mock_send

    with patch('os.path.exists', return_value=True):
        notifier = EmailNotifier()
        notifier.authenticate()

        message = {'raw': 'test_message'}
        result = notifier.send_message(message)

    assert result is True


def test_send_message_without_service(mock_config_enabled):
    """Test that sending message without authentication fails."""
    notifier = EmailNotifier()

    message = {'raw': 'test_message'}
    result = notifier.send_message(message)

    assert result is False


def test_batch_notifications_disabled(mock_config_disabled, sample_match):
    """Test batch notifications when email is disabled."""
    notifier = EmailNotifier()

    matches = [sample_match, sample_match]
    sent_count = notifier.send_batch_notifications(matches)

    assert sent_count == 0


@patch('src.notifications.email_notifier.build')
@patch('src.notifications.email_notifier.Credentials')
def test_html_generation_with_long_skill_lists(mock_creds_class, mock_build, mock_config_enabled):
    """Test HTML generation handles long skill lists correctly."""
    notifier = EmailNotifier()

    # Create match with many skills
    match_with_many_skills = {
        'job_title': 'Product Manager',
        'company': 'TestCo',
        'location': 'NYC',
        'url': 'https://example.com',
        'overall_score': 0.8,
        'skills_score': 0.75,
        'experience_score': 0.85,
        'matching_skills': [f'Skill{i}' for i in range(15)],  # 15 skills
        'skill_gaps': [f'Gap{i}' for i in range(10)],  # 10 gaps
    }

    html = notifier.generate_job_match_html(match_with_many_skills)

    # Should show "+" for extra skills
    assert '+' in html
    assert 'Skill0' in html
    assert 'Gap0' in html


def test_subject_template_formatting(mock_config_enabled, sample_match):
    """Test that subject template is formatted correctly."""
    notifier = EmailNotifier()

    # Mock authentication
    notifier.service = Mock()

    # Get the subject by checking what would be created
    subject = notifier.subject_template.format(
        job_title=sample_match['job_title'],
        company=sample_match['company']
    )

    assert subject == "New Job Match: Senior Product Manager at TechCorp"


def test_html_email_has_required_sections(mock_config_enabled, sample_match):
    """Test that HTML email contains all required sections."""
    notifier = EmailNotifier()

    html = notifier.generate_job_match_html(sample_match)

    # Check for all required sections
    assert 'New Job Match Found!' in html
    assert 'Match Breakdown' in html
    assert 'Your Matching Skills' in html
    assert 'Skills to Develop' in html
    assert 'View Job Posting' in html
    assert sample_match['url'] in html
