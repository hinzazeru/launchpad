"""Provider factory for creating job data provider instances."""

import logging
from src.importers.base_provider import JobProvider

logger = logging.getLogger(__name__)


def get_job_provider(provider: str = None) -> JobProvider:
    """Factory function to get configured job provider.

    Args:
        provider: Override config setting. Options: 'brightdata', 'auto'
                 If None, reads from config.

    Returns:
        Configured JobProvider instance

    Raises:
        ValueError: If no valid provider is configured or available

    Examples:
        # Use config default
        provider = get_job_provider()

        # Override with specific provider
        provider = get_job_provider("brightdata")
    """
    from src.config import get_config
    config = get_config()

    if provider is None:
        provider = config.get_job_provider()

    # 'auto' is retained for backward compatibility with existing deployments;
    # Bright Data is the only provider, so both values resolve the same way.
    if provider in ("brightdata", "auto"):
        from src.importers.brightdata_provider import BrightDataJobProvider
        logger.info("Using Bright Data provider")
        return BrightDataJobProvider()

    raise ValueError(
        f"Unknown job provider: '{provider}'. Valid options: 'brightdata'"
    )
