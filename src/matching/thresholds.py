"""The bar a match must clear to count as "high quality".

This existed as three disagreeing literals: the two web-search paths in
``backend/routers/search.py`` counted ``>= 0.85`` while the scheduled path in
``backend/services/webapp_scheduler.py`` counted ``>= 0.70``, and the Telegram
notification hardcoded "(70%+)" in its text.

The consequence was silent and worse than the duplication itself: a scheduled
run reporting "1 high quality" and the dashboard reporting "1 high match" were
measuring different things, so the two numbers were never comparable — and the
Telegram counts read optimistically against the UI the user checks them in.

0.85 is the unified value. Configurable via ``matching.high_match_threshold``
(or the ``MATCHING_HIGH_MATCH_THRESHOLD`` env var on Railway, where there is no
config.yaml).
"""

import logging
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

DEFAULT_HIGH_MATCH_THRESHOLD = 0.85

_CONFIG_KEY = "matching.high_match_threshold"


def get_high_match_threshold(config: Optional[Any] = None) -> float:
    """Return the configured high-match threshold as a 0.0-1.0 float.

    Falls back to :data:`DEFAULT_HIGH_MATCH_THRESHOLD` when unset, unparseable,
    or outside (0, 1]. A bad config value must not silently reclassify every
    match, so it is logged and ignored rather than honoured.
    """
    if config is None:
        from src.config import get_config
        config = get_config()

    raw = config.get(_CONFIG_KEY, DEFAULT_HIGH_MATCH_THRESHOLD)

    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "%s=%r is not a number; using %s",
            _CONFIG_KEY, raw, DEFAULT_HIGH_MATCH_THRESHOLD,
        )
        return DEFAULT_HIGH_MATCH_THRESHOLD

    if not 0.0 < value <= 1.0:
        logger.warning(
            "%s=%s is outside (0, 1]; using %s",
            _CONFIG_KEY, value, DEFAULT_HIGH_MATCH_THRESHOLD,
        )
        return DEFAULT_HIGH_MATCH_THRESHOLD

    return value


def format_high_match_threshold(config: Optional[Any] = None) -> str:
    """The threshold as it appears in user-facing text, e.g. ``"85%"``."""
    return f"{round(get_high_match_threshold(config) * 100)}%"


def count_high_matches(
    matches: Iterable,
    score_fn: Callable[[Any], float],
    config: Optional[Any] = None,
) -> int:
    """Count matches whose score clears the high-match threshold."""
    threshold = get_high_match_threshold(config)
    return sum(1 for m in matches if score_fn(m) >= threshold)
