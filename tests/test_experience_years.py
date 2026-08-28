"""Tests for total-experience calculation.

The bug this guards: a regex scanning the duration string for two 4-digit years
silently skipped any role ending in "Present" — the candidate's current role —
because "May 2023 - Present" contains only one year. On resume_2026 that
produced 13.0 years against a resume stating 15+, and experience is 25% of the
match score.
"""

from datetime import datetime

import pytest

from src.resume.experience import compute_experience_years


class Role:
    """Minimal stand-in for ResumeRole."""

    def __init__(self, duration="", start_date="", end_date=""):
        self.duration = duration
        self.start_date = start_date
        self.end_date = end_date


NOW = datetime(2026, 8, 28)


# --- the regression ------------------------------------------------------------

def test_current_role_is_counted():
    """The exact failure: a 'Present' role contributed zero."""
    roles = [Role(duration="May 2023 - Present", start_date="2023-05", end_date="present")]
    assert compute_experience_years(roles, now=NOW) == pytest.approx(3.3, abs=0.1)


def test_resume_2026_totals_15_not_13():
    roles = [
        Role("May 2023 - Present", "2023-05", "present"),
        Role("Dec 2018 - Apr 2021", "2018-12", "2021-04"),
        Role("Sep 2008 - Feb 2018", "2008-09", "2018-02"),
    ]
    assert compute_experience_years(roles, now=NOW) == pytest.approx(15.0, abs=0.2)


# --- structured dates ----------------------------------------------------------

def test_month_precision_not_whole_years():
    """Dec 2018 - Apr 2021 is 28 months = 2.3 years, not the 3 the old whole-year
    int subtraction gave. Elapsed time, so the final month is not counted."""
    roles = [Role("Dec 2018 - Apr 2021", "2018-12", "2021-04")]
    assert compute_experience_years(roles, now=NOW) == pytest.approx(2.3, abs=0.05)


@pytest.mark.parametrize("end", ["present", "Present", "CURRENT", "", None])
def test_current_markers_all_recognised(end):
    roles = [Role("x", "2024-08", end)]
    assert compute_experience_years(roles, now=NOW) == pytest.approx(2.0, abs=0.1)


def test_reversed_dates_do_not_go_negative():
    roles = [Role("bad", "2025-01", "2020-01")]
    assert compute_experience_years(roles, now=NOW) == 0.0


# --- plain-text fallback -------------------------------------------------------

def test_text_duration_with_present():
    roles = [Role(duration="May 2023 - Present")]
    assert compute_experience_years(roles, now=NOW) == pytest.approx(3.3, abs=0.2)


def test_text_bare_years_with_present():
    roles = [Role(duration="2015 - Present")]
    assert compute_experience_years(roles, now=NOW) == pytest.approx(11.7, abs=0.2)


def test_text_explicit_years_phrase():
    assert compute_experience_years([Role(duration="8 years")], now=NOW) == 8.0


def test_unparseable_duration_contributes_zero():
    assert compute_experience_years([Role(duration="a while")], now=NOW) == 0.0


def test_no_roles():
    assert compute_experience_years([], now=NOW) == 0.0


# --- real resumes --------------------------------------------------------------

def test_against_the_real_resume_file():
    from pathlib import Path

    from src.resume.parser import ResumeParser

    path = Path(__file__).resolve().parent.parent / "data" / "resumes" / "resume_2026.json"
    parsed = ResumeParser().parse_auto(path.read_text())
    years = compute_experience_years(parsed.roles, now=NOW)
    assert 14.5 <= years <= 15.5, f"expected ~15 years, got {years}"
