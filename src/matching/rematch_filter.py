"""Which jobs a scheduled run should re-score.

Scheduled runs match incrementally: only jobs imported since the previous run.
That filter reads ``JobPosting.import_date``, but the repost path in
``brightdata_provider.py:421-429`` refreshes ``posting_date`` and leaves
``import_date`` untouched. A role LinkedIn reposts therefore looks new by every
visible measure, passes the freshness window, and is still excluded from
matching forever — scored once on first sighting and never surfaced again.

Measured before this existed: **55 of the top 100 jobs at 85+ were reposts**,
including a 97-scoring role reposted 9 times and a 91-scoring Microsoft role
reposted 28 times, none of which had alerted since their first appearance.

Reposts are included here, with a cooldown so a job re-enters matching at most
once per ``cooldown_days``. Without it a role reposted 28 times would be
re-scored and re-alerted 28 times — the spam the original filter accidentally
prevented, which is the one thing it got right.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_, select

logger = logging.getLogger(__name__)

# A repost re-enters matching only if it has not been scored within this window.
DEFAULT_REPOST_COOLDOWN_DAYS = 30


def incremental_candidate_filter(
    last_run_at: datetime,
    cooldown_days: int = DEFAULT_REPOST_COOLDOWN_DAYS,
    now: Optional[datetime] = None,
):
    """SQLAlchemy filter for "what should this scheduled run score?".

    Two ways in:

    1. Genuinely new — imported since the last run.
    2. A repost re-listed since the last run, not scored within the cooldown.

    Args:
        last_run_at: Start of this run's window.
        cooldown_days: Minimum gap between re-scores of the same repost. Values
            <= 0 disable the cooldown, admitting every repost on every run.
        now: Override for testing.

    Returns:
        A filter expression to apply to a ``JobPosting`` query.
    """
    from src.database.models import JobPosting, MatchResult

    newly_imported = JobPosting.import_date >= last_run_at

    repost_relisted = and_(
        JobPosting.is_repost.is_(True),
        JobPosting.posting_date >= last_run_at,
    )

    if cooldown_days and cooldown_days > 0:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=cooldown_days)
        # Correlated EXISTS rather than a job_id IN (...) list: match_results is
        # the largest table here and the IN form materialises every recent id.
        scored_recently = (
            select(MatchResult.id)
            .where(MatchResult.job_id == JobPosting.id)
            .where(MatchResult.generated_date >= cutoff)
            .exists()
        )
        repost_relisted = and_(repost_relisted, ~scored_recently)

    return or_(newly_imported, repost_relisted)


def get_repost_cooldown_days(config=None) -> int:
    """Configured cooldown, falling back to the default on a bad value."""
    if config is None:
        from src.config import get_config
        config = get_config()

    raw = config.get("matching.repost_rematch_cooldown_days", DEFAULT_REPOST_COOLDOWN_DAYS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "matching.repost_rematch_cooldown_days=%r is not an integer; using %d",
            raw, DEFAULT_REPOST_COOLDOWN_DAYS,
        )
        return DEFAULT_REPOST_COOLDOWN_DAYS

    if value < 0:
        logger.warning(
            "matching.repost_rematch_cooldown_days=%d is negative; using %d",
            value, DEFAULT_REPOST_COOLDOWN_DAYS,
        )
        return DEFAULT_REPOST_COOLDOWN_DAYS

    return value


def format_repost_flag(repost_count: Optional[int]) -> str:
    """Short marker for notifications, e.g. ``" ⚠️ reposted 28x"``.

    Surfaced rather than hidden: a role relisted many times in an
    employer-tilted market is a signal worth seeing next to the score, not an
    implementation detail. Empty string when there is nothing to report.
    """
    if not repost_count or repost_count < 2:
        return ""
    return f" ⚠️ reposted {repost_count}x"
