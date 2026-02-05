"""Provider factory for creating job data provider instances."""

import logging
from src.importers.base_provider import JobProvider

logger = logging.getLogger(__name__)


def get_job_provider(provider: str = None) -> JobProvider:
    """Factory function to get configured job provider.
    
    Args:
        provider: Override config setting. Options: 'apify', 'brightdata', 'auto'
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
        
        # Auto mode with fallback
        provider = get_job_provider("auto")
    """
    from src.config import get_config
    config = get_config()

    if provider is None:
        provider = config.get_job_provider()

    if provider == "auto":
        # Try Bright Data first, fall back to Apify
        try:
            from src.importers.brightdata_provider import BrightDataJobProvider
            instance = BrightDataJobProvider()
            logger.info("Using Bright Data provider (auto mode)")
            return instance
        except ValueError as e:
            # Bright Data not configured, try Apify
            logger.info(f"Bright Data not available ({e}), trying Apify fallback...")
            try:
                from src.importers.apify_provider import ApifyJobProvider
                instance = ApifyJobProvider()
                logger.info("Using Apify provider (fallback from auto mode)")
                return instance
            except ValueError:
                raise ValueError(
                    "No job provider configured. "
                    "Please configure either 'brightdata.api_key' or 'apify.api_key' in config.yaml"
                )

    elif provider == "brightdata":
        from src.importers.brightdata_provider import BrightDataJobProvider
        logger.info("Using Bright Data provider")
        return BrightDataJobProvider()

    elif provider == "apify":
        from src.importers.apify_provider import ApifyJobProvider
        logger.info("Using Apify provider")
        return ApifyJobProvider()

    else:
        raise ValueError(
            f"Unknown job provider: '{provider}'. "
            f"Valid options: 'apify', 'brightdata', 'auto'"
        )
