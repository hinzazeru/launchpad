"""Tests for repost-aware incremental matching.

The original bug: scheduled runs filtered candidates on
``JobPosting.import_date >= last_run_at``, but the repost path in
brightdata_provider refreshes ``posting_date`` and leaves ``import_date``
untouched. Every reposted role was therefore invisible to matching forever —
measured at 55 of the top 100 jobs scoring 85+, including a 97-scoring role
reposted 9 times that had not alerted since May.

The bug in the *first fix* (shipped in dc95c1b, corrected here): the repost
branch also required ``posting_date >= last_run_at``. ``last_run_at`` is
assigned at the START of the current run (``webapp_scheduler.py:216``), so that
asked for jobs posted after the run had already begun — never true. The branch
matched nothing in three days of production. These tests now use a realistic
``last_run_at`` (seconds old, not a day) and realistic posting dates (days old,
as LinkedIn actually supplies) so that mistake cannot pass again.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import and_, create_engine, or_
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.models import JobPosting, MatchResult, Resume
from src.matching.rematch_filter import (
    DEFAULT_REPOST_COOLDOWN_DAYS,
    format_repost_flag,
    get_repost_cooldown_days,
    incremental_candidate_filter,
)

NOW = datetime(2026, 9, 15, 12, 0, 0)

# Assigned at the start of the current run, so it is seconds old during
# matching — not the previous run's timestamp.
LAST_RUN = NOW - timedelta(seconds=30)

# What LinkedIn actually supplies: a posting made days ago, re-listed today.
TYPICAL_POSTING = NOW - timedelta(days=2)

FRESHNESS_DAYS = 7


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
    """Candidate ids under the incremental filter alone."""
    return [
        j.id for j in db.query(JobPosting).filter(
            incremental_candidate_filter(LAST_RUN, cooldown_days, now=NOW)
        ).all()
    ]


def candidates_with_freshness(db, cooldown_days=DEFAULT_REPOST_COOLDOWN_DAYS):
    """The real pipeline: freshness filter applied BEFORE the incremental one.

    Mirrors webapp_scheduler.py, where max_job_age_days is applied at lines
    485-493 and the incremental filter at 507. The repost branch relies on this
    ordering rather than re-deriving freshness itself.
    """
    cutoff = NOW - timedelta(days=FRESHNESS_DAYS)
    return [
        j.id for j in db.query(JobPosting)
        .filter(or_(
            JobPosting.posting_date >= cutoff,
            and_(JobPosting.posting_date.is_(None), JobPosting.import_date >= cutoff),
        ))
        .filter(incremental_candidate_filter(LAST_RUN, cooldown_days, now=NOW))
        .all()
    ]


# --- the original regression ---------------------------------------------------

def test_repost_with_old_import_date_is_a_candidate(db):
    """Imported 7 months ago, re-listed now, scored once long ago."""
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 2, 17),
        posting_date=TYPICAL_POSTING,
        is_repost=True,
        repost_count=10,
    )
    score(db, job, when=datetime(2026, 2, 17))

    assert job.id in candidates(db)
    assert job.id in candidates_with_freshness(db)


def test_import_date_only_filter_would_have_missed_it(db):
    """The pre-fix behaviour, kept so it cannot be silently reintroduced."""
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 2, 17),
        posting_date=TYPICAL_POSTING,
        is_repost=True,
        repost_count=10,
    )
    assert db.query(JobPosting).filter(JobPosting.import_date >= LAST_RUN).all() == []
    assert job.id in candidates(db)


# --- the dc95c1b regression ----------------------------------------------------

def test_posting_date_bound_would_have_matched_nothing(db):
    """The shipped-then-corrected bug.

    dc95c1b required `posting_date >= last_run_at`. Since last_run_at is the
    current run's start time and postings are hours-to-days old, that admitted
    nothing — confirmed by three days of production returning zero reposts.
    """
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 2, 17),
        posting_date=TYPICAL_POSTING,
        is_repost=True,
        repost_count=10,
    )

    broken = and_(JobPosting.is_repost.is_(True), JobPosting.posting_date >= LAST_RUN)
    assert db.query(JobPosting).filter(broken).all() == [], "the broken filter should match nothing"
    assert job.id in candidates(db), "the corrected filter must match it"


def test_repost_posted_today_still_qualifies(db):
    """Correcting the bound must not break the case it accidentally allowed."""
    job = make_job(
        db,
        title="Principal Product Manager",
        import_date=datetime(2026, 1, 1),
        posting_date=NOW,
        is_repost=True,
        repost_count=3,
    )
    assert job.id in candidates(db)


# --- cooldown ------------------------------------------------------------------

def test_repost_scored_within_cooldown_is_excluded(db):
    """A role re-listed 28 times must not alert 28 times."""
    job = make_job(
        db, title="Senior Product Manager",
        import_date=datetime(2026, 1, 1), posting_date=TYPICAL_POSTING,
        is_repost=True, repost_count=28,
    )
    score(db, job, when=NOW - timedelta(days=3))
    assert job.id not in candidates(db)


def test_repost_scored_just_outside_cooldown_is_included(db):
    job = make_job(
        db, title="Senior Product Manager",
        import_date=datetime(2026, 1, 1), posting_date=TYPICAL_POSTING,
        is_repost=True, repost_count=5,
    )
    score(db, job, when=NOW - timedelta(days=31))
    assert job.id in candidates(db)


def test_cooldown_of_zero_admits_every_repost(db):
    job = make_job(
        db, title="Senior Product Manager",
        import_date=datetime(2026, 1, 1), posting_date=TYPICAL_POSTING,
        is_repost=True, repost_count=5,
    )
    score(db, job, when=NOW - timedelta(hours=1))
    assert job.id not in candidates(db)
    assert job.id in candidates(db, cooldown_days=0)


def test_never_scored_repost_is_included(db):
    job = make_job(
        db, title="Principal Product Manager",
        import_date=datetime(2026, 1, 1), posting_date=TYPICAL_POSTING,
        is_repost=True, repost_count=3,
    )
    assert job.id in candidates(db)


# --- freshness is the caller's job ---------------------------------------------

def test_stale_repost_excluded_by_the_freshness_filter_not_this_one(db):
    """Documents the division of responsibility.

    The incremental filter deliberately admits a stale repost; the freshness
    filter upstream is what rejects it. Re-deriving freshness inside the repost
    branch is exactly what broke dc95c1b.
    """
    job = make_job(
        db, title="Stale Repost",
        import_date=datetime(2026, 1, 1),
        posting_date=NOW - timedelta(days=60),
        is_repost=True, repost_count=4,
    )
    assert job.id in candidates(db), "incremental filter alone admits it"
    assert job.id not in candidates_with_freshness(db), "freshness filter rejects it"


# --- unchanged behaviour -------------------------------------------------------

def test_newly_imported_job_still_matches(db):
    job = make_job(db, title="New Role", import_date=NOW, posting_date=TYPICAL_POSTING)
    assert job.id in candidates(db)


def test_newly_imported_job_included_even_if_scored_recently(db):
    """The cooldown gates reposts only; it must not block genuinely new jobs."""
    job = make_job(db, title="New Role", import_date=NOW, posting_date=TYPICAL_POSTING)
    score(db, job, when=NOW)
    assert job.id in candidates(db)


def test_stale_non_repost_stays_excluded(db):
    job = make_job(
        db, title="Old Role",
        import_date=datetime(2026, 5, 1), posting_date=datetime(2026, 5, 1),
    )
    assert job.id not in candidates(db)


def test_non_repost_imported_before_this_run_is_excluded(db):
    """Imported an hour ago by some other path, never flagged repost."""
    job = make_job(
        db, title="Other Role",
        import_date=NOW - timedelta(hours=1), posting_date=TYPICAL_POSTING,
    )
    assert job.id not in candidates(db)


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
        FakeConfig({"matching.repost_rematch_cooldown_days": 7})) == 7


def test_cooldown_accepts_string_from_env():
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": "14"})) == 14


@pytest.mark.parametrize("bad", ["nope", None, -5])
def test_bad_cooldown_falls_back(bad):
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": bad})
    ) == DEFAULT_REPOST_COOLDOWN_DAYS


def test_zero_cooldown_is_honoured_not_treated_as_missing():
    """0 disables the cooldown deliberately; it must not fall back to 30."""
    assert get_repost_cooldown_days(
        FakeConfig({"matching.repost_rematch_cooldown_days": 0})) == 0


# --- notification flag ---------------------------------------------------------

def test_repost_flag_surfaces_count():
    assert format_repost_flag(28) == " ⚠️ reposted 28x"
    assert format_repost_flag(2) == " ⚠️ reposted 2x"


@pytest.mark.parametrize("count", [0, 1, None])
def test_repost_flag_silent_for_first_listing(count):
    """A job seen once is not a repost; no marker."""
    assert format_repost_flag(count) == ""
