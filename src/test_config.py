"""Unit tests for configuration loader."""

import pytest
import os
import tempfile
from pathlib import Path
from src.config import Config, get_config


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    Config._instance = None
    Config._config_data = None
    Config._config_path = None
    yield
    # Cleanup after test
    Config._instance = None
    Config._config_data = None
    Config._config_path = None


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_content = """
database:
  url: "sqlite:///test.db"

apify:
  api_key: "test_api_key_123"
  actor_id: "test/actor"

search:
  default_location: "Test City"
  default_max_results: 100
  default_posted_when: "Past week"
  default_job_type: "Contract"

matching:
  weights:
    skills: 0.6
    experience: 0.4
  min_match_score: 0.75
  enforce_24h_freshness: false

pm_skills:
  - "Product Management"
  - "Agile"
  - "SQL"

email:
  enabled: true
  service: "gmail"
  from_address: "test@example.com"
  notify_min_score: 0.8

scheduling:
  enabled: true
  interval_hours: 12
  start_time: "08:00"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def invalid_config_file():
    """Create an invalid YAML config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


def test_config_loads_from_file(temp_config_file):
    """Test loading configuration from file."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.get("database.url") == "sqlite:///test.db"
    assert config.get("apify.api_key") == "test_api_key_123"


def test_config_get_with_default(temp_config_file):
    """Test getting config value with default."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    # Existing value
    assert config.get("apify.api_key") == "test_api_key_123"

    # Non-existent value with default
    assert config.get("nonexistent.key", "default_value") == "default_value"

    # Non-existent value without default
    assert config.get("nonexistent.key") is None


def test_config_raises_on_missing_file():
    """Test that missing config file raises error."""
    config = Config(auto_load=False)
    config._config_data = None  # Reset

    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        config.load_config("/nonexistent/path/config.yaml")


def test_config_raises_on_invalid_yaml(invalid_config_file):
    """Test that invalid YAML raises error."""
    config = Config(auto_load=False)
    config._config_data = None  # Reset

    with pytest.raises(ValueError, match="Invalid YAML"):
        config.load_config(invalid_config_file)


def test_get_apify_api_key(temp_config_file):
    """Test getting Apify API key."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.get_apify_api_key() == "test_api_key_123"


def test_get_apify_api_key_raises_on_missing():
    """Test that missing API key raises error."""
    config_content = """
apify:
  api_key: "YOUR_APIFY_API_KEY_HERE"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    try:
        config = Config(auto_load=False)
        config.load_config(temp_path)

        with pytest.raises(ValueError, match="Apify API key is not configured"):
            config.get_apify_api_key()
    finally:
        os.unlink(temp_path)


def test_get_apify_actor_id(temp_config_file):
    """Test getting Apify actor ID."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.get_apify_actor_id() == "test/actor"


def test_get_database_url(temp_config_file):
    """Test getting database URL."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.get_database_url() == "sqlite:///test.db"


def test_get_search_defaults(temp_config_file):
    """Test getting search defaults."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    defaults = config.get_search_defaults()

    assert defaults['location'] == "Test City"
    assert defaults['max_results'] == 100
    assert defaults['posted_when'] == "Past week"
    assert defaults['job_type'] == "Contract"


def test_get_matching_weights(temp_config_file):
    """Test getting matching weights."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    weights = config.get_matching_weights()

    assert weights['skills'] == 0.6
    assert weights['experience'] == 0.4
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_get_matching_weights_raises_on_invalid_sum():
    """Test that invalid weight sum raises error."""
    config_content = """
matching:
  weights:
    skills: 0.6
    experience: 0.3
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    try:
        config = Config(auto_load=False)
        config.load_config(temp_path)

        with pytest.raises(ValueError, match="Matching weights must sum to 1.0"):
            config.get_matching_weights()
    finally:
        os.unlink(temp_path)


def test_get_min_match_score(temp_config_file):
    """Test getting minimum match score."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.get_min_match_score() == 0.75


def test_enforce_24h_freshness(temp_config_file):
    """Test getting freshness enforcement setting."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.enforce_24h_freshness() is False


def test_get_pm_skills(temp_config_file):
    """Test getting PM skills list."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    skills = config.get_pm_skills()

    assert isinstance(skills, list)
    assert "Product Management" in skills
    assert "Agile" in skills
    assert "SQL" in skills


def test_is_email_enabled(temp_config_file):
    """Test checking if email is enabled."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.is_email_enabled() is True


def test_get_email_config(temp_config_file):
    """Test getting email configuration."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    email_config = config.get_email_config()

    assert email_config['service'] == 'gmail'
    assert email_config['from_address'] == 'test@example.com'
    assert email_config['notify_min_score'] == 0.8


def test_is_scheduling_enabled(temp_config_file):
    """Test checking if scheduling is enabled."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.is_scheduling_enabled() is True


def test_get_scheduling_config(temp_config_file):
    """Test getting scheduling configuration."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    sched_config = config.get_scheduling_config()

    assert sched_config['interval_hours'] == 12
    assert sched_config['start_time'] == "08:00"


def test_config_reload(temp_config_file):
    """Test reloading configuration."""
    config = Config(auto_load=False)
    config.load_config(temp_config_file)

    assert config.get("apify.api_key") == "test_api_key_123"

    # Modify the file
    with open(temp_config_file, 'w') as f:
        f.write("apify:\n  api_key: 'new_key_456'\n")

    # Reload
    config.reload()

    assert config.get("apify.api_key") == "new_key_456"


def test_get_config_singleton():
    """Test that get_config returns singleton instance."""
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2
