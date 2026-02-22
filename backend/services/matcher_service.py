"""Singleton JobMatcher service.

Avoids recreating the ~80MB SentenceTransformer model on every search request.
The matcher is lazily initialized on first use and reused thereafter.
"""

import gc
import logging
from typing import Optional

from src.matching.engine import JobMatcher

logger = logging.getLogger(__name__)

_matcher: Optional[JobMatcher] = None


def get_job_matcher(mode: str = "auto") -> JobMatcher:
    """Get the singleton JobMatcher instance.

    Creates a new instance on first call, reuses it thereafter.
    The SentenceTransformer model (~80MB) is loaded once and kept in memory.
    """
    global _matcher
    if _matcher is None:
        logger.info("Initializing singleton JobMatcher (mode=%s)", mode)
        _matcher = JobMatcher(mode=mode)
    return _matcher


def release_job_matcher() -> None:
    """Release the singleton to free ~80MB+ of model memory between scheduled runs.

    The matcher will be re-initialized on the next call to get_job_matcher(),
    adding ~5-10s reload time. Call this after a scheduled search completes to
    return memory to baseline between runs.
    """
    global _matcher
    if _matcher is not None:
        logger.info("Releasing singleton JobMatcher to free memory")
        _matcher = None
        gc.collect()


def reset_job_matcher() -> None:
    """Reset the singleton for testing or config reload."""
    global _matcher
    _matcher = None
