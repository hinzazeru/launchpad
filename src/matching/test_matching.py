"""Critical unit tests for job matching engine."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from src.matching.skills_matcher import SkillsMatcher
from src.matching.engine import JobMatcher
from src.database.models import Resume, JobPosting


# ===== Critical Skills Matcher Tests =====

def test_skills_matcher_initialization():
    """Test creating SkillsMatcher instance."""
    matcher = SkillsMatcher()
    assert matcher.model is not None


def test_calculate_skills_match_exact():
    """Test exact skill matching - core functionality."""
    matcher = SkillsMatcher()

    resume_skills = ["Python", "SQL", "Data Analysis"]
    job_skills = ["Python", "SQL", "Data Analysis"]

    score, matches, details = matcher.calculate_skills_match(resume_skills, job_skills)

    assert score == 1.0  # Perfect match
    assert len(matches) == 3


def test_calculate_skills_match_semantic():
    """Test semantic similarity matching - key feature."""
    matcher = SkillsMatcher()

    resume_skills = ["Python Programming", "Database Queries", "Machine Learning"]
    job_skills = ["Python", "SQL", "AI"]

    score, matches, details = matcher.calculate_skills_match(resume_skills, job_skills, threshold=0.5)

    # Should match semantically
    assert score > 0.5
    assert len(matches) >= 2


# ===== Critical Job Matcher Tests =====

@pytest.fixture
def mock_config():
    """Mock configuration."""
    with patch('src.matching.engine.get_config') as mock:
        config_instance = Mock()
        config_instance.get_matching_weights.return_value = {
            'skills': 0.5,
            'experience': 0.5
        }
        config_instance.get_min_match_score.return_value = 0.6
        mock.return_value = config_instance
        yield config_instance


@pytest.fixture
def sample_resume():
    """Create sample resume for testing."""
    resume = Resume(
        id=1,
        skills=["Python", "SQL", "Data Analysis", "Product Management"],
        experience_years=5.0,
        job_titles=["Product Manager", "Associate Product Manager"],
        education="MBA"
    )
    return resume


@pytest.fixture
def sample_job_high_match():
    """Create job posting that should match well."""
    job = JobPosting(
        id=1,
        title="Senior Product Manager",
        company="TechCorp",
        location="San Francisco, CA",
        description="Looking for PM with Python and SQL experience",
        required_skills=["Python", "SQL", "Product Management"],
        experience_required=5.0,
        posting_date=datetime.utcnow(),
        url="https://example.com/job1"
    )
    return job


@pytest.fixture
def sample_job_low_match():
    """Create job posting that should match poorly."""
    job = JobPosting(
        id=2,
        title="Senior Software Engineer",
        company="CodeCo",
        location="New York, NY",
        description="Looking for engineer with Java and C++",
        required_skills=["Java", "C++", "Kubernetes"],
        experience_required=8.0,
        posting_date=datetime.utcnow(),
        url="https://example.com/job2"
    )
    return job


def test_job_matcher_initialization(mock_config):
    """Test JobMatcher initialization."""
    matcher = JobMatcher()
    assert matcher.skills_matcher is not None
    assert matcher.skills_weight == 0.5
    assert matcher.experience_weight == 0.5


def test_calculate_experience_match_exact(mock_config):
    """Test experience matching when resume meets requirements."""
    matcher = JobMatcher()

    score = matcher.calculate_experience_match(resume_years=5.0, job_years_required=5.0)
    assert score == 1.0


def test_calculate_experience_match_deficit(mock_config):
    """Test experience matching with deficit."""
    matcher = JobMatcher()

    # 1 year deficit
    score = matcher.calculate_experience_match(resume_years=4.0, job_years_required=5.0)
    assert score == 0.8

    # 3+ year deficit
    score = matcher.calculate_experience_match(resume_years=1.0, job_years_required=5.0)
    assert score == 0.2


def test_match_job_high_match(mock_config, sample_resume, sample_job_high_match):
    """Test matching a well-suited job - critical end-to-end test."""
    matcher = JobMatcher()

    result = matcher.match_job(sample_resume, sample_job_high_match)

    assert 'overall_score' in result
    assert 'skills_score' in result
    assert 'experience_score' in result

    # Should have high scores
    assert result['overall_score'] > 0.7
    assert result['skills_score'] > 0.7
    assert result['experience_score'] == 1.0


def test_match_job_low_match(mock_config, sample_resume, sample_job_low_match):
    """Test matching a poorly-suited job - critical end-to-end test."""
    matcher = JobMatcher()

    result = matcher.match_job(sample_resume, sample_job_low_match)

    # Should have lower scores
    assert result['overall_score'] < 0.6
    assert result['skills_score'] < 0.5


def test_match_jobs_ranking(mock_config, sample_resume):
    """Test that jobs are ranked by score - critical for user experience."""
    matcher = JobMatcher()

    # Create multiple jobs with varying match quality
    job1 = JobPosting(
        id=1, title="PM - Perfect Match",
        company="A", location="SF",
        required_skills=["Python", "SQL", "Product Management"],
        experience_required=5.0,
        posting_date=datetime.utcnow(), url="http://a.com"
    )

    job2 = JobPosting(
        id=2, title="Engineer - Poor Match",
        company="B", location="LA",
        required_skills=["Java", "C++"],
        experience_required=10.0,
        posting_date=datetime.utcnow(), url="http://b.com"
    )

    jobs = [job2, job1]  # Intentionally out of order

    matches = matcher.match_jobs(sample_resume, jobs, min_score=0.0)

    # Should be sorted by score (descending)
    assert matches[0]['overall_score'] >= matches[1]['overall_score']
    assert matches[0]['job_title'] == "PM - Perfect Match"
