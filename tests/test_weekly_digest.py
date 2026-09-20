"""Tests for the weekly roles digest.

This runs 52 times a year and nobody is watching on the other 51 Mondays, so
the tests concentrate on the things that fail silently: the DST-sensitive week
window, the escaping that can drop a whole message, and the idempotency key
that stops a catch-up racing the cron into two digests.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.models import DigestLog, JobPosting, MatchResult, Resume
from src.notifications.weekly_digest import (
    TELEGRAM_MAX_MESSAGE_CHARS,
    _truncate,
    fetch_top_roles,
    format_week_label,
    previous_week_bounds,
    render_digest,
)

TZ = "America/Toronto"
WEBAPP = "https://launchpad.example.com"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Resume(id=1, skills=["product management"], experience_years=15.0))
    session.commit()
    yield session
    session.close()


class FakeJob:
    def __init__(self, title, company):
        self.title = title
        self.company = company


class FakeRole:
    """Stand-in for a MatchResult, so rendering tests need no database."""

    def __init__(self, score, title="Senior Product Manager", company="Acme"):
        self.match_score = score
        self.job_posting = FakeJob(title, company)


def add_match(db, *, title, company, score, generated, job_id=None):
    job = JobPosting(
        title=title,
        company=company,
        location="Toronto, ON",
        description="x" * 300,
        posting_date=generated,
        source="brightdata",
    )
    db.add(job)
    db.flush()
    match = MatchResult(
        job_id=job.id, resume_id=1, match_score=score, generated_date=generated
    )
    db.add(match)
    db.commit()
    return job, match


# ------------------------------------------------------------------- window

class TestPreviousWeekBounds:
    def test_on_a_monday_returns_the_week_that_just_ended(self):
        """The digest reports finished weeks, never the one starting today."""
        monday = datetime(2026, 9, 14, 8, 0, tzinfo=ZoneInfo(TZ))
        _start, _end, week_start = previous_week_bounds(monday, TZ)
        assert week_start.date() == datetime(2026, 9, 7).date()
        assert week_start.weekday() == 0

    def test_midweek_still_returns_last_completed_week(self):
        wednesday = datetime(2026, 9, 16, 15, 0, tzinfo=ZoneInfo(TZ))
        _start, _end, week_start = previous_week_bounds(wednesday, TZ)
        assert week_start.date() == datetime(2026, 9, 7).date()

    def test_window_is_seven_days_and_half_open(self):
        monday = datetime(2026, 9, 14, 8, 0, tzinfo=ZoneInfo(TZ))
        start, end, _ = previous_week_bounds(monday, TZ)
        assert end - start == timedelta(days=7)

    def test_spring_forward_week_is_167_hours(self):
        """DST is why this uses a zone and not a fixed offset. A hard-coded EST
        would silently shift the window by an hour twice a year.

        2026 springs forward on Sun Mar 8, so the week reported on Mon Mar 9
        (Mar 2-9) is the one that contains it and is an hour short.
        """
        monday_after = datetime(2026, 3, 9, 8, 0, tzinfo=ZoneInfo(TZ))
        start, end, _ = previous_week_bounds(monday_after, TZ)
        assert end - start == timedelta(hours=167)

    def test_fall_back_week_is_169_hours(self):
        """2026 falls back on Sun Nov 1; the week reported on Mon Nov 2 holds it."""
        monday_after = datetime(2026, 11, 2, 8, 0, tzinfo=ZoneInfo(TZ))
        start, end, _ = previous_week_bounds(monday_after, TZ)
        assert end - start == timedelta(hours=169)

    def test_week_without_a_transition_is_exactly_168_hours(self):
        monday = datetime(2026, 9, 14, 8, 0, tzinfo=ZoneInfo(TZ))
        start, end, _ = previous_week_bounds(monday, TZ)
        assert end - start == timedelta(hours=168)

    def test_year_boundary(self):
        jan = datetime(2027, 1, 4, 8, 0, tzinfo=ZoneInfo(TZ))
        _start, _end, week_start = previous_week_bounds(jan, TZ)
        assert week_start.year == 2026
        assert week_start.date() == datetime(2026, 12, 28).date()

    def test_bounds_are_naive_utc(self):
        """Stored and compared against naive-UTC columns."""
        monday = datetime(2026, 9, 14, 8, 0, tzinfo=ZoneInfo(TZ))
        start, end, _ = previous_week_bounds(monday, TZ)
        assert start.tzinfo is None and end.tzinfo is None


class TestFormatWeekLabel:
    def test_same_month(self):
        assert format_week_label(datetime(2026, 9, 1)) == "Sep 1-7"

    def test_across_a_month_boundary(self):
        assert format_week_label(datetime(2026, 8, 31)) == "Aug 31 - Sep 6"


# ---------------------------------------------------------------- rendering

class TestTruncate:
    def test_short_text_untouched(self):
        assert _truncate("Product Manager", 28) == "Product Manager"

    def test_long_title_clips_with_ellipsis_inside_the_budget(self):
        title = "Senior Product Manager, Payments Platform and Risk Infrastructure Team"
        assert len(title) == 70
        out = _truncate(title, 28)
        assert len(out) == 28 and out.endswith("…")

    def test_long_company_clips(self):
        company = "Really Long Company Name Inc"
        assert len(company) == 28
        out = _truncate(company, 12)
        assert len(out) == 12 and out.endswith("…")


class TestRenderDigest:
    def test_empty_week_still_sends_a_message(self):
        """A silent Monday must mean "nothing scored", never "it broke"."""
        out = render_digest([], "Sep 1-7", 78, 10, WEBAPP)
        assert "No roles scored 78%+" in out
        assert "<pre>" not in out
        assert "minScore=78" in out

    def test_table_renders_rows(self):
        roles = [FakeRole(91, "Staff PM, Growth", "Shopify"), FakeRole(84)]
        out = render_digest(roles, "Sep 1-7", 78, 10, WEBAPP)
        assert "<pre>" in out and "</pre>" in out
        assert " 91  " in out and " 84  " in out

    def test_no_blank_line_after_the_pre_tag(self):
        out = render_digest([FakeRole(91)], "Sep 1-7", 78, 10, WEBAPP)
        assert "<pre>\n" not in out

    def test_entities_in_company_are_escaped(self):
        """Telegram parses entities inside <pre> too; one raw & drops the
        entire message, not just its row.

        Company kept inside COMPANY_WIDTH so this tests escaping rather than
        truncation — truncation runs first, on the rendered text.
        """
        out = render_digest([FakeRole(88, "PM", "A <B> & Co")], "Sep 1-7", 78, 10, WEBAPP)
        assert "&amp;" in out
        assert "&lt;B&gt;" in out
        assert "A <B> & Co" not in out

    def test_entities_in_title_are_escaped(self):
        out = render_digest([FakeRole(88, "PM, R&D <Core>", "Acme")], "Sep 1-7", 78, 10, WEBAPP)
        assert "R&amp;D &lt;Core&gt;" in out

    def test_long_company_with_entities_truncates_then_escapes(self):
        """Truncation is on rendered width, so "&" costs one column, not five."""
        out = render_digest([FakeRole(88, "PM", "Smith & Co <Ltd>")], "Sep 1-7", 78, 10, WEBAPP)
        assert "&amp;" in out
        assert "…" in out

    def test_escaping_does_not_break_column_alignment(self):
        """Padding must be computed on raw width: "&" is 5 source chars as
        &amp; but renders as 1, so padding the escaped string shoves the row."""
        plain = render_digest([FakeRole(88, "Research & Dev PM", "Acme")], "Sep 1-7", 78, 10, WEBAPP)
        row = [ln for ln in plain.split("\n") if "88" in ln][0]
        # Unescape back to what the reader sees, then check the company column
        # starts where it does for a title with no entities.
        rendered = row.replace("&amp;", "&")
        control = render_digest([FakeRole(88, "Research and Dev PM", "Acme")], "Sep 1-7", 78, 10, WEBAPP)
        control_row = [ln for ln in control.split("\n") if "88" in ln][0]
        assert rendered.index("Acme") == control_row.index("Acme")

    def test_overflow_line_absent_when_within_max_rows(self):
        roles = [FakeRole(80 + i) for i in range(5)]
        out = render_digest(roles, "Sep 1-7", 78, 10, WEBAPP)
        assert "more at 78%+" not in out

    def test_overflow_line_present_when_over_max_rows(self):
        roles = [FakeRole(80) for _ in range(15)]
        out = render_digest(roles, "Sep 1-7", 78, 10, WEBAPP)
        assert "…and 5 more at 78%+" in out
        assert out.count("\n 80") <= 10

    def test_footer_links_to_the_filtered_view(self):
        out = render_digest([FakeRole(91)], "Sep 1-7", 78, 10, WEBAPP)
        assert f'href="{WEBAPP}/matches?minScore=78"' in out

    def test_trailing_slash_in_webapp_url_does_not_double(self):
        out = render_digest([FakeRole(91)], "Sep 1-7", 78, 10, WEBAPP + "/")
        assert "//matches" not in out

    def test_fits_telegram_limit_at_max_rows_25(self):
        """Verifies the config knob: 25 is the documented upper setting."""
        roles = [
            FakeRole(80, "Senior Product Manager, Payments Platform Team", "Wealthsimple")
            for _ in range(40)
        ]
        out = render_digest(roles, "Sep 1-7", 78, 25, WEBAPP)
        assert len(out) < TELEGRAM_MAX_MESSAGE_CHARS


# ------------------------------------------------------------------- query

class TestFetchTopRoles:
    def test_one_row_per_job_at_its_best_score(self, db):
        """A role rematched nightly must not fill the table."""
        now = datetime(2026, 9, 9, 12, 0)
        job = JobPosting(title="Senior PM", company="Acme", location="Toronto",
                         description="x" * 300, posting_date=now, source="brightdata")
        db.add(job)
        db.flush()
        for score in (79.0, 91.0, 85.0):
            db.add(MatchResult(job_id=job.id, resume_id=1, match_score=score,
                               generated_date=now))
        db.commit()

        roles = fetch_top_roles(db, now - timedelta(days=2), now + timedelta(days=2), 78)
        assert len(roles) == 1
        assert roles[0].match_score == 91.0

    def test_below_floor_excluded(self, db):
        now = datetime(2026, 9, 9, 12, 0)
        add_match(db, title="Low", company="A", score=77.0, generated=now)
        add_match(db, title="High", company="B", score=78.0, generated=now)
        roles = fetch_top_roles(db, now - timedelta(days=2), now + timedelta(days=2), 78)
        assert [r.job_posting.title for r in roles] == ["High"]

    def test_outside_window_excluded(self, db):
        now = datetime(2026, 9, 9, 12, 0)
        add_match(db, title="In", company="A", score=90.0, generated=now)
        add_match(db, title="Out", company="B", score=95.0,
                  generated=now - timedelta(days=30))
        roles = fetch_top_roles(db, now - timedelta(days=2), now + timedelta(days=2), 78)
        assert [r.job_posting.title for r in roles] == ["In"]

    def test_window_is_half_open_at_the_end(self, db):
        """A match exactly at `end` belongs to next week, not this one."""
        start = datetime(2026, 9, 7, 4, 0)
        end = datetime(2026, 9, 14, 4, 0)
        add_match(db, title="Boundary", company="A", score=90.0, generated=end)
        assert fetch_top_roles(db, start, end, 78) == []

    def test_sorted_best_first(self, db):
        now = datetime(2026, 9, 9, 12, 0)
        for title, score in [("Mid", 85.0), ("Top", 96.0), ("Low", 79.0)]:
            add_match(db, title=title, company=title, score=score, generated=now)
        roles = fetch_top_roles(db, now - timedelta(days=2), now + timedelta(days=2), 78)
        assert [r.job_posting.title for r in roles] == ["Top", "Mid", "Low"]

    def test_already_notified_roles_are_included(self, db):
        """Settled decision: the digest is a picture of the week, not a diff
        against what already alerted."""
        now = datetime(2026, 9, 9, 12, 0)
        _job, match = add_match(db, title="Alerted", company="A", score=90.0, generated=now)
        match.notified_at = now
        db.commit()
        roles = fetch_top_roles(db, now - timedelta(days=2), now + timedelta(days=2), 78)
        assert len(roles) == 1

    def test_empty_window_returns_empty_list(self, db):
        now = datetime(2026, 9, 9, 12, 0)
        assert fetch_top_roles(db, now, now + timedelta(days=7), 78) == []


# ------------------------------------------------------------------ DigestLog

class TestDigestLog:
    def test_table_created_on_fresh_sqlite(self, db):
        assert db.query(DigestLog).count() == 0

    def test_duplicate_week_start_rejected(self, db):
        """The idempotency key: a catch-up racing the cron cannot double-send."""
        from sqlalchemy.exc import IntegrityError

        week = datetime(2026, 9, 7, 4, 0)
        db.add(DigestLog(week_start=week, roles_count=5, min_score=78, status="sent"))
        db.commit()

        db.add(DigestLog(week_start=week, roles_count=9, min_score=78, status="sent"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_failed_status_is_recordable(self, db):
        """A broken send must be visible as a row, not as silence."""
        db.add(DigestLog(week_start=datetime(2026, 9, 7, 4, 0), roles_count=0,
                         min_score=78, status="failed",
                         error_message="Telegram rejected"))
        db.commit()
        row = db.query(DigestLog).one()
        assert row.status == "failed" and "Telegram" in row.error_message

    def test_min_score_is_stored_per_row(self, db):
        """Without it, roles_count stops being interpretable when the floor moves."""
        db.add(DigestLog(week_start=datetime(2026, 9, 7, 4, 0), roles_count=43,
                         min_score=78, status="sent"))
        db.commit()
        assert db.query(DigestLog).one().min_score == 78


# --------------------------------------------------------------------- config

class TestConfigOverrides:
    """Production runs with no config.yaml, so the env path is the real one."""

    def _resolve(self, keys, **env):
        """Resolve (key, default) pairs with `env` applied.

        Values are read *inside* the patch block. Returning the Config and
        calling .get() afterwards silently reads the unpatched environment,
        because `get()` looks at os.environ at call time — which is how the
        first version of this test "passed" a default back as an override.
        """
        import src.config as config_module

        with patch.dict("os.environ", env, clear=False):
            cfg = config_module.Config()
            return {key: cfg.get(key, default) for key, default in keys}

    KEYS = [
        ("notifications.weekly_digest.max_rows", 10),
        ("notifications.weekly_digest.min_score", 78),
        ("notifications.weekly_digest.enabled", True),
        ("notifications.weekly_digest.send_time", "08:00"),
    ]

    def test_env_overrides_apply_with_correct_types(self):
        got = self._resolve(
            self.KEYS,
            WEEKLY_DIGEST_MAX_ROWS="25",
            WEEKLY_DIGEST_MIN_SCORE="80",
            WEEKLY_DIGEST_ENABLED="false",
            WEEKLY_DIGEST_SEND_TIME="09:30",
        )
        assert got["notifications.weekly_digest.max_rows"] == 25
        assert got["notifications.weekly_digest.min_score"] == 80
        assert got["notifications.weekly_digest.enabled"] is False
        assert got["notifications.weekly_digest.send_time"] == "09:30"

    def test_falls_back_to_documented_defaults(self):
        """Production has no config.yaml and none of these env vars set."""
        got = self._resolve(self.KEYS)
        assert got["notifications.weekly_digest.max_rows"] == 10
        assert got["notifications.weekly_digest.min_score"] == 78
        assert got["notifications.weekly_digest.enabled"] is True
        assert got["notifications.weekly_digest.send_time"] == "08:00"
