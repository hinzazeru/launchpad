"""Configuration management for LinkedIn Job Matcher."""

import json
import os
import logging
import re
import yaml
from typing import Any, Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# Mapping of config dot-paths to environment variable names.
# When set, env vars take priority over config.yaml values.
ENV_OVERRIDES: Dict[str, str] = {
    "apify.api_key": "APIFY_API_KEY",
    "apify.actor_id": "APIFY_ACTOR_ID",
    "brightdata.api_key": "BRIGHTDATA_API_KEY",
    "gemini.api_key": "GEMINI_API_KEY",
    "gemini.enabled": "GEMINI_ENABLED",
    "telegram.bot_token": "TELEGRAM_BOT_TOKEN",
    "telegram.allowed_user_id": "TELEGRAM_ALLOWED_USER_ID",
    "telegram.chat_id": "TELEGRAM_CHAT_ID",
    "telegram.enabled": "TELEGRAM_ENABLED",
    "webapp.url": "WEBAPP_URL",
    "sheets.spreadsheet_id": "SHEETS_SPREADSHEET_ID",
    "sheets.credentials_path": "SHEETS_CREDENTIALS_PATH",
    "sheets.token_path": "SHEETS_TOKEN_PATH",
    "sheets.enabled": "SHEETS_ENABLED",
    "email.enabled": "EMAIL_ENABLED",
    "email.from_address": "EMAIL_FROM_ADDRESS",
    "email.to_address": "EMAIL_TO_ADDRESS",
    "email.credentials_path": "EMAIL_CREDENTIALS_PATH",
    "email.token_path": "EMAIL_TOKEN_PATH",
    "database.url": "DATABASE_URL",
    "job_provider.provider": "JOB_PROVIDER",
    "matching.engine": "MATCHING_ENGINE",
    "scheduling.enabled": "SCHEDULING_ENABLED",
    "admin.token": "ADMIN_TOKEN",
    "gemini.rate_limit.min_interval_ms": "GEMINI_RATE_LIMIT_MIN_INTERVAL_MS",
    "gemini.rate_limit.thinking_min_interval_ms": "GEMINI_RATE_LIMIT_THINKING_MIN_INTERVAL_MS",
    "gemini.rate_limit.max_retries": "GEMINI_RATE_LIMIT_MAX_RETRIES",
    "gemini.rate_limit.circuit_breaker_cooldown_s": "GEMINI_RATE_LIMIT_COOLDOWN_S",
    "gemini.matcher.concurrency": "GEMINI_MATCHER_CONCURRENCY",
}


def _coerce_value(value: str, default: Any = None) -> Any:
    """Coerce a string env var value to the appropriate Python type.

    Uses the default's type as a hint when available, otherwise infers from content.
    """
    # Use default's type as a hint
    if default is not None:
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes")
        if isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return value
        if isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return value

    # No default hint — infer from string content
    lower = value.lower()
    if lower in ("true", "1", "yes"):
        return True
    if lower in ("false", "0", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


class Config:
    """Configuration loader and accessor.

    Use get_config() to obtain the singleton instance.
    """

    _config_data = None
    _config_path = None

    def __init__(self, auto_load: bool = True):
        """Initialize configuration loader.

        Args:
            auto_load: Whether to automatically load config on initialization.
                      Set to False for testing purposes.
        """
        if self._config_data is None and auto_load:
            try:
                self.load_config()
            except FileNotFoundError:
                # Config file doesn't exist yet, that's okay
                # It will be loaded when needed
                pass

    def load_config(self, config_path: Optional[str] = None):
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file. Defaults to config.yaml in project root.

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid YAML
        """
        if config_path is None:
            # Use previously stored path if available, otherwise default
            if self._config_path:
                config_path = self._config_path
            else:
                # Default to config.yaml in project root
                project_root = Path(__file__).parent.parent
                config_path = project_root / "config.yaml"

        if not os.path.exists(config_path):
            # Config file is optional — env vars can supply all values
            logger.info(
                f"Config file not found at {config_path}; "
                f"using environment variables and defaults only."
            )
            self._config_data = {}
            return

        # Store the path for future reloads
        self._config_path = config_path

        try:
            with open(config_path, 'r') as f:
                self._config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Lookup order:
        1. Environment variable (if key_path is in ENV_OVERRIDES)
        2. YAML config file value
        3. Provided default

        Args:
            key_path: Dot-separated path to config value (e.g., "apify.api_key")
            default: Default value if key doesn't exist

        Returns:
            Configuration value or default

        Example:
            config = Config()
            api_key = config.get("apify.api_key")
            min_score = config.get("matching.min_match_score", 0.6)
        """
        # 1. Check environment variable override
        env_var = ENV_OVERRIDES.get(key_path)
        if env_var is not None:
            env_value = os.environ.get(env_var)
            if env_value is not None:
                return _coerce_value(env_value, default)

        # 2. Check YAML config
        if self._config_data is None:
            self.load_config()

        keys = key_path.split('.')
        value = self._config_data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_apify_api_key(self) -> str:
        """Get Apify API key from config.

        Returns:
            Apify API key

        Raises:
            ValueError: If API key is not configured
        """
        api_key = self.get("apify.api_key")
        if not api_key or api_key == "YOUR_APIFY_API_KEY_HERE":
            raise ValueError(
                "Apify API key is not configured. "
                "Please set 'apify.api_key' in config.yaml"
            )
        return api_key

    def get_apify_actor_id(self) -> str:
        """Get Apify actor ID from config.

        Returns:
            Apify actor ID (defaults to vulnv/linkedin-jobs-scraper)
        """
        return self.get("apify.actor_id", "vulnv/linkedin-jobs-scraper")

    def get_brightdata_api_key(self) -> str:
        """Get Bright Data API key from config.

        Returns:
            Bright Data API key

        Raises:
            ValueError: If API key is not configured
        """
        api_key = self.get("brightdata.api_key")
        if not api_key or api_key == "YOUR_BRIGHTDATA_API_KEY_HERE":
            raise ValueError(
                "Bright Data API key is not configured. "
                "Please set 'brightdata.api_key' in config.yaml"
            )
        return api_key

    def get_job_provider(self) -> str:
        """Get configured job provider.

        Returns:
            Job provider name ('apify', 'brightdata', or 'auto')
            Defaults to 'apify' for backward compatibility
        """
        return self.get("job_provider.provider", "apify")

    def get_database_url(self) -> str:
        """Get database URL from config.

        Returns:
            Database connection URL
        """
        return self.get("database.url", "sqlite:///linkedin_job_matcher.db")

    def get_search_defaults(self) -> Dict[str, Any]:
        """Get default search parameters.

        Returns:
            Dictionary of default search parameters
        """
        return {
            'location': self.get("search.default_location", "United States"),
            'max_results': self.get("search.default_max_results", 50),
            'posted_when': self.get("search.default_posted_when", "Past 24 hours"),
            'job_type': self.get("search.default_job_type", "Full-time"),
            'experience_level': self.get("search.default_experience_level"),
            'work_arrangement': self.get("search.default_work_arrangement"),
            'search_radius': self.get("search.default_search_radius"),
        }

    def _load_matching_weights_file(self) -> dict:
        """Load data/matching_weights.json (git-tracked, no secrets)."""
        path = Path(__file__).parent.parent / "data" / "matching_weights.json"
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def get_matching_weights(self) -> Dict[str, float]:
        """Get matching algorithm weights.

        Loads from data/matching_weights.json first (git-tracked), then falls back
        to config.yaml overrides, then hardcoded defaults.

        Returns:
            Dictionary with 'skills', 'experience', and 'domains' weights

        Raises:
            ValueError: If weights don't sum to 1.0
        """
        file_weights = self._load_matching_weights_file().get("nlp_weights", {})
        weights = {
            'skills':     self.get("matching.weights.skills",     file_weights.get("skills",     0.45)),
            'experience': self.get("matching.weights.experience", file_weights.get("experience", 0.35)),
            'domains':    self.get("matching.weights.domains",    file_weights.get("domains",    0.20)),
        }

        total = sum(weights.values())
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(
                f"Matching weights must sum to 1.0, got {total}. "
                f"Please check data/matching_weights.json or matching.weights in config.yaml"
            )

        return weights

    def get_gemini_blend_weights(self) -> Dict[str, float]:
        """Get Gemini/NLP blend weights for re-ranking.

        Loads from data/matching_weights.json first (git-tracked), then falls back
        to config.yaml overrides, then hardcoded defaults.

        Returns:
            Dictionary with 'ai' and 'nlp' blend weights
        """
        file_weights = self._load_matching_weights_file().get("gemini_blend_weights", {})
        return {
            'ai':  self.get("matching.gemini_rerank.blend_weights.ai",  file_weights.get("ai",  0.75)),
            'nlp': self.get("matching.gemini_rerank.blend_weights.nlp", file_weights.get("nlp", 0.25)),
        }

    def get_min_match_score(self) -> float:
        """Get minimum match score threshold.

        Returns:
            Minimum match score (0.0 - 1.0)
        """
        return self.get("matching.min_match_score", 0.6)

    def get_engine_version(self) -> str:
        """Get matching engine version.

        Returns:
            Engine version string (semantic versioning format: v{major}.{minor}.{patch})
        """
        version = self.get("matching.engine_version", "1.0.0")

        # Validate semantic versioning format
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            raise ValueError(
                f"Invalid engine version format: {version}. "
                f"Must be in semantic versioning format (e.g., '1.0.0')"
            )

        return version

    def enforce_24h_freshness(self) -> bool:
        """Check if 24-hour freshness validation is enabled.

        Returns:
            True if freshness validation is enforced
        """
        return self.get("matching.enforce_24h_freshness", True)

    def get_pm_skills(self) -> list:
        """Get Product Management skills dictionary.

        Returns:
            List of PM skills for matching and parsing
        """
        return self.get("pm_skills", [])

    def is_email_enabled(self) -> bool:
        """Check if email notifications are enabled.

        Returns:
            True if email notifications are enabled
        """
        return self.get("email.enabled", False)

    def get_email_config(self) -> Dict[str, Any]:
        """Get email configuration.

        Returns:
            Dictionary of email settings
        """
        return {
            'service': self.get("email.service", "gmail"),
            'credentials_path': self.get("email.credentials_path", "credentials.json"),
            'token_path': self.get("email.token_path", "token.json"),
            'from_address': self.get("email.from_address"),
            'to_address': self.get("email.to_address"),
            'subject_template': self.get("email.subject_template", "New Job Match: {job_title} at {company}"),
            'notify_min_score': self.get("email.notify_min_score", 0.7),
        }

    def is_scheduling_enabled(self) -> bool:
        """Check if job scheduling is enabled.

        Returns:
            True if scheduling is enabled
        """
        return self.get("scheduling.enabled", False)

    def get_scheduling_config(self) -> Dict[str, Any]:
        """Get scheduling configuration.

        Returns:
            Dictionary of scheduling settings
        """
        return {
            'interval_hours': self.get("scheduling.interval_hours", 24),
            'start_time': self.get("scheduling.start_time", "08:00"),
            'end_time': self.get("scheduling.end_time", "22:00"),
        }

    def set(self, key_path: str, value: Any) -> None:
        """Set configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., "scheduling.interval_hours")
            value: Value to set

        Example:
            config.set("scheduling.interval_hours", 4)
            config.set("scheduling.enabled", True)
        """
        if self._config_data is None:
            self.load_config()

        keys = key_path.split('.')
        data = self._config_data

        # Navigate to parent of the key we want to set
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]

        # Set the final key
        data[keys[-1]] = value

    def save(self) -> bool:
        """Save current configuration to file.

        Uses file locking to prevent corruption from concurrent writes.

        Returns:
            True if save successful, False otherwise
        """
        import fcntl

        if self._config_path is None or self._config_data is None:
            return False

        try:
            with open(self._config_path, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    yaml.dump(self._config_data, f, default_flow_style=False, sort_keys=False)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}", exc_info=True)
            return False

    def reload(self):
        """Reload configuration from file."""
        self._config_data = None
        self.load_config()


# Global config instance
_config_instance = None


def get_config() -> Config:
    """Get global config instance.

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
