"""Tests for repost-aware incremental matching.

The bug this guards: scheduled runs filtered candidates on
``JobPosting.import_date >= last_run_at``, but the repost path in
brightdata_provider refreshes ``posting_date`` and leaves ``import_date``
untouched. Every reposted role was therefore invisible to matching forever —
measured at 55 of the top 100 jobs scoring 85+, including a 97-scoring role
reposted 9 times that had not alerted since May.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.models import JobPosting, MatchResult, Resume
from src.matching.rematch_filter import (
    DEFAULT_REPOST_COOLDOWN_DAYS,
    format_repost_flag,
    get_repost_cooldown_days,
    incremental_candidate_filter,
)

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
LAST_RUN = NOW - timedelta(days=1)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Resume(id=1, skills=["product management"], experience_years=15.0))
    session.commit()
    yield session
    session.close()


def make_job(db, *, title, import_date, posting_date, is_repost=False, repost_count=0):
    job = JobPosting(
        title=title,
        company=f"{title} Co",
        description="x" * 300,
        posting_date=posting_date,
        import_date=import_date,
        is_repost=is_repost,
        repost_count=repost_count,
    )
    db.add(job)
    db.commit()
    return job


def score(db, job, when, value=88.0):
    db.add(MatchResult(job_id=job.id, resume_id=1, match_score=value, generated_date=when))
    db.commit()


def candidates(db, cooldown_days=DEFAULT_REPOST_COOLDOWN_DAYS):
    naive_last_run = LAST_RUN.replace(tzinfo=None)
    return (
        db.query(JobPosting)
        .filter(incremental_candidate_filter(naive_last_run, cooldown_days, now=NOW.replace(tzinfo=None)))
        .all()
    )


# --- the regression ------------------------------------------------------------

def test_repost_relisted_since_last_run_is_now_a_candidate(db):
    """The exact failure: old import_date, fresh posting_date, never matched."""
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 2, 17),        # imported 7 months ago
        posting_date=NOW.replace(tzinfo=None),    # re-listed today
        is_repost=True,
        repost_count=10,
    )
    score(db, job, when=datetime(2026, 2, 17))    # scored once, long ago

    assert job.id in [j.id for j in candidates(db)]


def test_old_import_date_filter_alone_would_have_missed_it(db):
    """Documents the previous behaviour so it is not silently reintroduced."""
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 2, 17),
        posting_date=NOW.replace(tzinfo=None),
        is_repost=True,
        repost_count=10,
    )
    old_filter = JobPosting.import_date >= LAST_RUN.replace(tzinfo=None)
    assert db.query(JobPosting).filter(old_filter).all() == []
    assert job.id in [j.id for j in candidates(db)]


# --- cooldown ------------------------------------------------------------------

def test_repost_scored_within_cooldown_is_excluded(db):
    """A role re-listed 28 times must not alert 28 times."""
    job = make_job(
        db,
        title="Senior Product Manager",
        import_date=datetime(2026, 1, 1),
        posting_date=NOW.replace(tzinfo=None),
        is_repost=True,
        repost_count=28,
    )
    score(db, job, when=NOW.replace(tzinfo=None) - timedelta(days=3))  # scored recently

    assert job.id not in [j.id for j in candidates(db)]


def test_repost_scored_just_outside_cooldown_is_included(db):
    job = make_job(
        db,
        title="Senior Product Manager",
        import_date=datetime(2026, 1, 1),
        posting_date=NOW.replace(tzinfo=None),
        is_repost=True,
        repost_count=5,
    )
    score(db, job, when=NOW.replace(tzinfo=None) - timedelta(days=31))

    assert job.id in [j.id for j in candidates(db)]


def test_cooldown_of_zero_admits_every_repost(db):
    job = make_job(
        db,
        title="Senior Product Manager",
        import_date=datetime(2026, 1, 1),
        posting_date=NOW.replace(tzinfo=None),
        is_repost=True,
        repost_count=5,
    )
    score(db, job, when=NOW.replace(tzinfo=None) - timedelta(hours=1))

    assert job.id not in [j.id for j in candidates(db)]
    assert job.id in [j.id for j in candidates(db, cooldown_days=0)]


def test_never_scored_repost_is_included_regardless_of_cooldown(db):
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 1, 1),
        posting_date=NOW.replace(tzinfo=None),
        is_repost=True,
        repost_count=3,
    )
    assert job.id in [j.id for j in candidates(db)]


# --- unchanged behaviour -------------------------------------------------------

def test_newly_imported_job_still_matches(db):
    job = make_job(
        db,
        title="New Role",
        import_date=NOW.replace(tzinfo=None),
        posting_date=NOW.replace(tzinfo=None),
    )
    assert job.id in [j.id for j in candidates(db)]


def test_newly_imported_job_is_included_even_if_scored_recently(db):
    """The cooldown gates reposts only; it must not block genuinely new jobs."""
    job = make_job(
        db,
        title="New Role",
        import_date=NOW.replace(tzinfo=None),
        posting_date=NOW.replace(tzinfo=None),
    )
    score(db, job, when=NOW.replace(tzinfo=None))
    assert job.id in [j.id for j in candidates(db)]


def test_stale_non_repost_stays_excluded(db):
    """An ordinary old job must not become a candidate."""
    job = make_job(
        db,
        title="Old Role",
        import_date=datetime(2026, 5, 1),
        posting_date=datetime(2026, 5, 1),
    )
    assert job.id not in [j.id for j in candidates(db)]


def test_repost_not_relisted_since_last_run_is_excluded(db):
    """is_repost alone is not enough — it must be re-listed in this window."""
    job = make_job(
        db,
        title="Old Repost",
        import_date=datetime(2026, 1, 1),
        posting_date=datetime(2026, 6, 1),  # last re-listed in June
        is_repost=True,
        repost_count=4,
    )
    assert job.id not in [j.id for j in candidates(db)]


# --- config --------------------------------------------------------------------

class FakeConfig:
    def __init__(self, values=None):
        self._values = values or {}

    def get(self, key, default=None):
        return self._values.get(key, default)


def test_cooldown_default_is_30():
    assert get_repost_cooldown_days(FakeConfig()) == 30
    assert DEFAULT_REPOST_COOLDOWN_DAYS == 30


def test_cooldown_override():
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": 7})
    ) == 7


def test_cooldown_accepts_string_from_env():
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": "14"})
    ) == 14


@pytest.mark.parametrize("bad", ["nope", None, -5])
def test_bad_cooldown_falls_back(bad):
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": bad})
    ) == DEFAULT_REPOST_COOLDOWN_DAYS


def test_zero_cooldown_is_honoured_not_treated_as_missing():
    """0 disables the cooldown deliberately; it must not fall back to 30."""
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": 0})
    ) == 0


# --- notification flag ---------------------------------------------------------

def test_repost_flag_surfaces_count():
    assert format_repost_flag(28) == " ⚠️ reposted 28x"
    assert format_repost_flag(2) == " ⚠️ reposted 2x"


@pytest.mark.parametrize("count", [0, 1, None])
def test_repost_flag_silent_for_first_listing(count):
    """A job seen once is not a repost; no marker."""
    assert format_repost_flag(count) == ""
