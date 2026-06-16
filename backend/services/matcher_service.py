"""Singleton JobMatcher service.

The matcher is lazily initialized on first use and reused thereafter. Matching
is Gemini-only; construction raises GeminiUnavailableError if Gemini is not
configured, so the singleton only caches a successfully-initialized matcher.
"""

import gc
import logging
import time
from typing import Optional

from src.matching.engine import JobMatcher

logger = logging.getLogger(__name__)

_matcher: Optional[JobMatcher] = None
_last_used: Optional[float] = None


def get_job_matcher(mode: str = "gemini") -> JobMatcher:
    """Get the singleton JobMatcher instance.

    Creates a new instance on first call, reuses it thereafter.

    Raises:
        GeminiUnavailableError: If Gemini matching is not available. The failed
            instance is not cached, so a later call can retry once Gemini recovers.
    """
    global _matcher, _last_used
    _last_used = time.time()
    if _matcher is None:
        logger.info("Initializing singleton JobMatcher (mode=%s)", mode)
        _matcher = JobMatcher(mode=mode)
    return _matcher


def unload_if_idle(idle_seconds: float = 1800.0) -> bool:
    """Unload the matcher if it has been idle for longer than idle_seconds.

    Returns True if the matcher was unloaded, False otherwise.
    """
    global _matcher, _last_used
    if _matcher is not None and _last_used is not None:
        if time.time() - _last_used > idle_seconds:
            logger.info(
                "JobMatcher idle for %.0fs — unloading to free memory",
                time.time() - _last_used,
            )
            release_job_matcher()
            return True
    return False


def release_job_matcher() -> None:
    """Release the singleton between scheduled runs.

    The matcher will be re-initialized on the next call to get_job_matcher().
    Kept for compatibility with the scheduler's release-after-run flow; the
    Gemini matcher is lightweight, so this is now mostly a no-op cleanup.
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
