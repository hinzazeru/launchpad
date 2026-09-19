"""The reposts_rematched counter must reach the database.

Why this exists: the first repost fix (dc95c1b) shipped with a filter that
matched nothing and ran for three days in production with zero effect. Nothing
measured it, so nothing reported it — it surfaced only because a human asked for
a review. This counter makes that class of silent no-op self-reporting, and
these tests make sure the counter itself cannot silently stop working.

A persistent 0 in `search_performance.reposts_rematched` now means the repost
branch is admitting nothing.
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.models import SearchPerformance


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


# --- schema --------------------------------------------------------------------

def test_column_exists_on_search_performance(session_factory):
    engine, _ = session_factory
    cols = {c["name"] for c in inspect(engine).get_columns("search_performance")}
    assert "reposts_rematched" in cols


def test_column_is_in_the_startup_migration_list():
    """Postgres gets no columns from create_all(), only from this list."""
    from pathlib import Path

    main = (Path(__file__).resolve().parent.parent / "backend" / "main.py").read_text()
    assert '("search_performance", "reposts_rematched", "INTEGER")' in main, (
        "column must be in backend/main.py migrations or it will never exist on Postgres"
    )


def test_column_is_exposed_in_the_history_schema():
    """A metric nobody can read is not wired up."""
    from backend.schemas.scheduler import ScheduleRunHistory

    assert "reposts_rematched" in ScheduleRunHistory.model_fields


# --- persistence ---------------------------------------------------------------

def test_recorded_count_is_persisted(session_factory):
    engine, Session = session_factory
    from src.services.performance_logger import PerformanceLogger

    db = Session()
    try:
        logger = PerformanceLogger(search_id="test-search-1")
        logger.record_count("jobs_matched", 12)
        logger.record_count("reposts_rematched", 7)
        logger.save(session=db, status="success")

        row = db.query(SearchPerformance).filter_by(search_id="test-search-1").one()
        assert row.reposts_rematched == 7
    finally:
        db.close()


def test_zero_is_persisted_not_dropped(session_factory):
    """0 is the whole point — it must not be stored as NULL."""
    engine, Session = session_factory
    from src.services.performance_logger import PerformanceLogger

    db = Session()
    try:
        logger = PerformanceLogger(search_id="test-search-0")
        logger.record_count("reposts_rematched", 0)
        logger.save(session=db, status="success")

        row = db.query(SearchPerformance).filter_by(search_id="test-search-0").one()
        assert row.reposts_rematched == 0, "a zero must be recorded, not lost"
        assert row.reposts_rematched is not None
    finally:
        db.close()


def test_absent_count_stays_null(session_factory):
    """Runs that never reached matching leave it NULL, distinct from 0."""
    engine, Session = session_factory
    from src.services.performance_logger import PerformanceLogger

    db = Session()
    try:
        logger = PerformanceLogger(search_id="test-search-none")
        logger.save(session=db, status="error", error_message="fetch failed")

        row = db.query(SearchPerformance).filter_by(search_id="test-search-none").one()
        assert row.reposts_rematched is None
    finally:
        db.close()


# --- counting logic ------------------------------------------------------------

class FakeJob:
    def __init__(self, id, is_repost=False, repost_count=0):
        self.id = id
        self.is_repost = is_repost
        self.repost_count = repost_count


def count_reposts(all_jobs, matches):
    """Mirrors webapp_scheduler: count matches whose job was a repost."""
    repost_ids = {j.id for j in all_jobs if j.is_repost}
    return sum(1 for m in matches if m.get("job_id") in repost_ids)


def test_counts_only_matched_reposts():
    """A repost that was a candidate but scored below threshold is not counted."""
    all_jobs = [FakeJob(1, True, 5), FakeJob(2, True, 3), FakeJob(3)]
    matches = [{"job_id": 1}, {"job_id": 3}]
    assert count_reposts(all_jobs, matches) == 1


def test_zero_when_no_reposts_matched():
    all_jobs = [FakeJob(1), FakeJob(2)]
    matches = [{"job_id": 1}, {"job_id": 2}]
    assert count_reposts(all_jobs, matches) == 0


def test_all_matches_can_be_reposts():
    """The catch-up case: a backlog run where every match is a repost."""
    all_jobs = [FakeJob(i, True, 4) for i in range(1, 6)]
    matches = [{"job_id": i} for i in range(1, 6)]
    assert count_reposts(all_jobs, matches) == 5
