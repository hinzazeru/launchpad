"""Total years of professional experience from parsed resume roles.

Replaces a regex duplicated across three call sites that scanned the
human-readable duration string for 4-digit years::

    year_match = re.findall(r'20\\d{2}', duration)
    if len(year_match) >= 2:
        experience_years += int(year_match[-1]) - int(year_match[0])

That has two defects, both of which understate experience:

1. A CURRENT role contributes ZERO. "May 2023 - Present" yields one year, not
   two, so the branch never fires and the role is silently skipped — the single
   most important role on the resume.
2. Whole-year subtraction only. "Dec 2018 - Apr 2021" counted as 3 years rather
   than 2.4.

Measured on resume_2026: the regex produced 13.0 years against a resume stating
15+. Experience is 25% of the match score, so every job was scored against a
candidate two years more junior than the real one.

JSON resumes already carry structured `start_date`/`end_date` (YYYY-MM), which
this uses when available. Plain-text resumes fall back to parsing the duration
string, now handling "Present" and month precision.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

_PRESENT = {"present", "current", "now", "ongoing", ""}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "May 2023", "Sept. 2008", "december 2018"
_MONTH_YEAR_RE = re.compile(r"([a-z]{3,9})\.?\s+((?:19|20)\d{2})", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _parse_iso_month(value: Optional[str]) -> Optional[tuple]:
    """'2023-05' -> (2023, 5). Returns None for 'present' or unparseable input."""
    if not value:
        return None
    v = value.strip().lower()
    if v in _PRESENT:
        return None
    parts = v.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        if 1 <= month <= 12 and 1900 <= year <= 2200:
            return (year, month)
    except (ValueError, IndexError):
        pass
    return None


def _months_between(start: tuple, end: tuple) -> int:
    return max(0, (end[0] - start[0]) * 12 + (end[1] - start[1]))


def _is_current(end_value: Optional[str]) -> bool:
    return (end_value or "").strip().lower() in _PRESENT


def _from_duration(duration: str, now: tuple) -> float:
    """Fallback for plain-text resumes: parse the display string.

    Handles "May 2023 - Present" by treating the missing end as today, which is
    exactly the case the old regex dropped.
    """
    if not duration:
        return 0.0
    text = duration.strip()

    pairs = _MONTH_YEAR_RE.findall(text)
    parsed = [
        (int(y), _MONTHS[m[:3].lower()])
        for m, y in pairs
        if m[:3].lower() in _MONTHS
    ]

    if parsed:
        start = parsed[0]
        if len(parsed) >= 2:
            end = parsed[1]
        else:
            # One month-year found: current role if the text says so, else
            # look for a bare trailing year ("May 2023 - 2025").
            years = _YEAR_RE.findall(text)
            if len(years) >= 2:
                end = (int(years[-1]), start[1])
            elif re.search(r"present|current|now", text, re.IGNORECASE):
                end = now
            else:
                return 0.0
        return _months_between(start, end) / 12

    # No month names at all — fall back to bare years, still handling "present".
    years = _YEAR_RE.findall(text)
    if years:
        start = (int(years[0]), 1)
        if len(years) >= 2:
            end = (int(years[-1]), 1)
        elif re.search(r"present|current|now", text, re.IGNORECASE):
            end = now
        else:
            return 0.0
        return _months_between(start, end) / 12

    # "5 years of experience"
    match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*year", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0


def compute_experience_years(roles: List, now: Optional[datetime] = None) -> float:
    """Sum experience across roles, preferring structured dates.

    Roles are summed independently rather than measured span-to-span, matching
    the previous behaviour. Overlapping roles therefore double-count — a known
    limitation, unchanged here so this fix stays scoped to the "Present" bug.

    Returns years rounded to one decimal.
    """
    reference = now or datetime.now()
    now_tuple = (reference.year, reference.month)
    total_months = 0.0

    for role in roles:
        start_raw = getattr(role, "start_date", "") or ""
        end_raw = getattr(role, "end_date", "") or ""
        start = _parse_iso_month(start_raw)

        if start:
            end = now_tuple if _is_current(end_raw) else (_parse_iso_month(end_raw) or now_tuple)
            total_months += _months_between(start, end)
            continue

        # No usable structured dates — plain-text resume path.
        duration = getattr(role, "duration", "") or ""
        total_months += _from_duration(duration, now_tuple) * 12

    return round(total_months / 12, 1)
