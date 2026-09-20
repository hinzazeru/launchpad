"""Monday-morning summary of last week's top-scoring roles.

Live alerts fire at `matching.high_match_threshold` (0.85). Over Sep 1-7 that
produced 9 alerts while 34 further roles scored 78-84 and were never surfaced —
Wealthsimple, Cohere, Workday, Mozilla, Google and Amazon among them, many of
them Toronto or Canada-wide Staff/Principal PM roles. Dropping the live bar to
catch them would restore roughly 12 alerts a day of noise, so this sweeps the
band underneath once a week instead. Live alert behaviour is untouched.

Everything here is pure except `fetch_top_roles`, which only reads. The window
maths and the rendering are therefore testable without a database or a bot
token, which matters for a thing that runs 52 times a year and is watched by
nobody on the other 51 Mondays.

Two rendering constraints worth stating up front, both verified against the
real client rather than assumed:

- **Telegram does not render links inside `<pre>`.** An aligned table and
  tappable per-role links are mutually exclusive. The table wins; a single
  footer link covers the overflow.
- **Telegram still parses HTML entities inside `<pre>`.** A company named
  `Smith & Co <Ltd>` breaks the entire message, not just its own row, so title
  and company are escaped even though they sit in a preformatted block.
"""

import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/Toronto"

# Column budget for the <pre> table. Telegram's mobile client wraps somewhere
# around 40 monospace chars in portrait; 3 + 28 + 12 plus separators sits under
# that, and wrapping would destroy the alignment the table exists for.
TITLE_WIDTH = 28
COMPANY_WIDTH = 12

TELEGRAM_MAX_MESSAGE_CHARS = 4096


def previous_week_bounds(
    now: Optional[datetime] = None,
    tz_name: str = DEFAULT_TIMEZONE,
) -> Tuple[datetime, datetime, datetime]:
    """The week that just ended: previous Mon 00:00 → Sun 24:00, local.

    Returns `(start_utc, end_utc, week_start_local)`. The bounds are half-open
    (`start <= t < end`) so a role matched at 23:59:59 on Sunday lands in the
    week it belongs to and is not double-counted next Monday.

    Uses the zone rather than a fixed offset so it tracks DST exactly like the
    search schedules do. Across a spring-forward boundary the week is 167 hours
    long, not 168, and hard-coding EST would silently shift the window by an
    hour twice a year.

    Called on a Monday it returns the week that *ended* yesterday, never the
    one that started this morning — the digest reports finished weeks.
    """
    tz = ZoneInfo(tz_name)
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)

    # Monday of the current week, then step back seven days.
    this_monday = now_local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=now_local.weekday()
    )
    week_start_local = this_monday - timedelta(days=7)
    week_end_local = this_monday

    return (
        week_start_local.astimezone(timezone.utc).replace(tzinfo=None),
        week_end_local.astimezone(timezone.utc).replace(tzinfo=None),
        week_start_local,
    )


def format_week_label(week_start_local: datetime) -> str:
    """`"Sep 1-7"`, or `"Aug 31 - Sep 6"` when the week straddles a month."""
    week_end_local = week_start_local + timedelta(days=6)
    if week_start_local.month == week_end_local.month:
        return f"{week_start_local:%b} {week_start_local.day}-{week_end_local.day}"
    return (
        f"{week_start_local:%b} {week_start_local.day} - "
        f"{week_end_local:%b} {week_end_local.day}"
    )


def _truncate(text: str, width: int) -> str:
    """Clip to `width`, marking the clip with a single-character ellipsis.

    The ellipsis is counted inside the budget rather than added to it, so every
    cell is exactly `width` chars and the columns stay aligned — which is the
    only reason this is a `<pre>` block at all.
    """
    text = (text or "").strip()
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def fetch_top_roles(
    db,
    start_utc: datetime,
    end_utc: datetime,
    min_score: float,
) -> List[Any]:
    """Best MatchResult per job in the window, highest score first.

    Mirrors the max-score-per-job subquery in `crud.get_unnotified_matches`
    rather than inventing a second pattern for the same question. A job
    re-matched three times during the week appears once, at its best score —
    otherwise a single role rematched nightly would fill the table.

    Deliberately does NOT filter on `notified_at`: the digest includes roles
    that already alerted during the week (settled decision), because its job is
    a complete picture of the week rather than a diff against the alerts.
    """
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload

    from src.database.models import MatchResult

    best = (
        db.query(
            MatchResult.job_id,
            func.max(MatchResult.match_score).label("max_score"),
        )
        .filter(MatchResult.match_score >= min_score)
        .filter(MatchResult.generated_date >= start_utc)
        .filter(MatchResult.generated_date < end_utc)
        .group_by(MatchResult.job_id)
        .subquery()
    )

    rows = (
        db.query(MatchResult)
        .options(joinedload(MatchResult.job_posting))
        .join(
            best,
            (MatchResult.job_id == best.c.job_id)
            & (MatchResult.match_score == best.c.max_score),
        )
        .order_by(MatchResult.match_score.desc())
        .all()
    )

    # A job with two MatchResults tied at the same max score matches the join
    # twice. Collapse on job_id, keeping the first (already the best-ordered).
    seen, deduped = set(), []
    for row in rows:
        if row.job_id in seen:
            continue
        seen.add(row.job_id)
        deduped.append(row)
    return deduped


def render_digest(
    roles: List[Any],
    week_label: str,
    min_score: float,
    max_rows: int,
    webapp_url: str,
) -> str:
    """The Telegram message body, as HTML.

    An empty week still produces a message. A silent Monday must mean "nothing
    scored", never "the pipeline broke" — and those two are indistinguishable
    to the reader if nothing arrives.
    """
    floor = int(min_score)
    total = len(roles)
    link = f"{webapp_url.rstrip('/')}/matches?minScore={floor}"

    if total == 0:
        return "\n".join([
            f"📋 <b>Weekly Roles — {escape(week_label)}</b>",
            "",
            f"No roles scored {floor}%+ last week.",
            "",
            f'<a href="{escape(link, quote=True)}">Open Job Matches →</a>',
        ])

    rows = []
    for role in roles[:max_rows]:
        job = getattr(role, "job_posting", None)
        title = _truncate(getattr(job, "title", "") or "", TITLE_WIDTH)
        company = _truncate(getattr(job, "company", "") or "", COMPANY_WIDTH)
        score = int(round(getattr(role, "match_score", 0) or 0))
        # Pad on the RAW text, then escape the padded cell. Escaping first and
        # padding second aligns on source length, so a single "&" (5 chars as
        # &amp;, 1 char rendered) would shove that row four columns left.
        # escape() leaves spaces alone, so the padding survives it.
        cell = f"{title:<{TITLE_WIDTH}}"
        rows.append(f"{score:>3}  {escape(cell)}  {escape(company)}")

    lines = [
        f"📋 <b>Weekly Roles — {escape(week_label)}</b>",
        "",
        f"{total} role{'s' if total != 1 else ''} scored {floor}%+",
        "",
        # No newline between the tag and the first row: Telegram renders one
        # there as a blank leading line inside the block.
        "<pre>" + "\n".join(rows) + "</pre>",
    ]

    if total > max_rows:
        lines.append(f"…and {total - max_rows} more at {floor}%+")

    lines.extend([
        "",
        f'<a href="{escape(link, quote=True)}">View all {total} →</a>',
    ])

    return "\n".join(lines)
