"""Tests for the weekly digest's scheduler wiring and send path.

The interesting failures here are all about *not* sending twice and *not*
staying silent: the cron replacing rather than duplicating itself, the
DigestLog row making a second send a no-op, the catch-up firing only when the
week was genuinely missed, and a failed send leaving a row behind rather than
looking like a quiet week.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.models import DigestLog, JobPosting, MatchResult, Resume


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    s.add(Resume(id=1, skills=["product management"], experience_years=15.0))
    s.commit()
    s.close()
    return factory


@pytest.fixture
def scheduler(session_factory):
    """A real WebAppScheduler bound to an in-memory DB, never started."""
    from backend.services import webapp_scheduler as mod

    with patch.object(mod, "SessionLocal", session_factory):
        sched = mod.WebAppScheduler()
        yield sched


class FakeConfig:
    def __init__(self, **overrides):
        self.values = {
            "notifications.weekly_digest.enabled": True,
            "notifications.weekly_digest.min_score": 78,
            "notifications.weekly_digest.max_rows": 10,
            "notifications.weekly_digest.send_time": "08:00",
            "webapp.url": "https://example.com",
            "telegram.bot_token": "token",
            "telegram.chat_id": "chat",
        }
        self.values.update(overrides)

    def get(self, key, default=None):
        return self.values.get(key, default)


def run(coro):
    """Drive a coroutine from a sync test.

    The repo has no pytest-asyncio and no other async tests. Marking these
    `@pytest.mark.asyncio` without the plugin does not fail — pytest *skips*
    them with a warning, which is how six tests covering idempotency and
    failure recording silently stopped running. Explicit asyncio.run cannot
    skip.
    """
    return asyncio.run(coro)


def seed_role(session_factory, *, score=90.0, when=None, title="Senior PM"):
    """Seed a match inside the window the digest actually reports.

    Defaults to midweek of the *previous* week. "3 days ago" lands in the
    current week, which the digest correctly ignores.
    """
    if when is None:
        from backend.services import webapp_scheduler as mod
        from src.notifications.weekly_digest import previous_week_bounds

        start, _end, _ = previous_week_bounds(
            datetime.now(timezone.utc), mod.DIGEST_TIMEZONE
        )
        when = start + timedelta(days=3)

    s = session_factory()
    job = JobPosting(title=title, company="Acme", location="Toronto",
                     description="x" * 300, posting_date=when, source="brightdata")
    s.add(job)
    s.flush()
    s.add(MatchResult(job_id=job.id, resume_id=1, match_score=score,
                      generated_date=when))
    s.commit()
    s.close()


# ------------------------------------------------------------- registration

class TestRegisterDigestJob:
    def test_registers_a_monday_cron(self, scheduler):
        from backend.services import webapp_scheduler as mod

        with patch.object(mod, "get_config", create=True), \
             patch("src.config.get_config", return_value=FakeConfig()):
            assert scheduler.register_digest_job() is True

        job = scheduler._scheduler.get_job(mod.DIGEST_JOB_ID)
        assert job is not None
        assert "mon" in str(job.trigger)

    def test_disabled_config_does_not_register(self, scheduler):
        from backend.services import webapp_scheduler as mod

        cfg = FakeConfig(**{"notifications.weekly_digest.enabled": False})
        with patch("src.config.get_config", return_value=cfg):
            assert scheduler.register_digest_job() is False
        assert scheduler._scheduler.get_job(mod.DIGEST_JOB_ID) is None

    def test_re_registering_replaces_rather_than_duplicates(self, scheduler):
        from backend.services import webapp_scheduler as mod

        with patch("src.config.get_config", return_value=FakeConfig()):
            scheduler.register_digest_job()
            scheduler.register_digest_job()

        matching = [j for j in scheduler._scheduler.get_jobs() if j.id == mod.DIGEST_JOB_ID]
        assert len(matching) == 1

    def test_invalid_send_time_falls_back_to_0800(self, scheduler):
        cfg = FakeConfig(**{"notifications.weekly_digest.send_time": "invalid"})
        with patch("src.config.get_config", return_value=cfg):
            assert scheduler._digest_send_time() == (8, 0)

    def test_out_of_range_send_time_falls_back(self, scheduler):
        cfg = FakeConfig(**{"notifications.weekly_digest.send_time": "25:99"})
        with patch("src.config.get_config", return_value=cfg):
            assert scheduler._digest_send_time() == (8, 0)

    def test_valid_send_time_is_used(self, scheduler):
        cfg = FakeConfig(**{"notifications.weekly_digest.send_time": "09:30"})
        with patch("src.config.get_config", return_value=cfg):
            assert scheduler._digest_send_time() == (9, 30)


# --------------------------------------------------------------------- send

class TestSendWeeklyDigest:
    def test_sends_and_records_one_row(self, scheduler, session_factory):
        seed_role(session_factory)
        sender = AsyncMock(return_value=True)

        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=True):
            result = run(scheduler.send_weekly_digest())

        assert result["sent"] is True
        assert sender.await_count == 1

        s = session_factory()
        rows = s.query(DigestLog).all()
        assert len(rows) == 1 and rows[0].status == "sent"
        s.close()

    def test_second_send_in_same_week_is_a_no_op(self, scheduler, session_factory):
        """The catch-up can race the real cron; only one digest may go out."""
        seed_role(session_factory)
        sender = AsyncMock(return_value=True)

        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=True):
            run(scheduler.send_weekly_digest())
            second = run(scheduler.send_weekly_digest())

        assert second.get("skipped") is True
        assert sender.await_count == 1

        s = session_factory()
        assert s.query(DigestLog).count() == 1
        s.close()

    def test_force_bypasses_the_idempotency_check(self, scheduler, session_factory):
        seed_role(session_factory)
        sender = AsyncMock(return_value=True)

        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=True):
            run(scheduler.send_weekly_digest())
            forced = run(scheduler.send_weekly_digest(force=True))

        assert forced.get("skipped") is not True
        assert sender.await_count == 2

    def test_failed_send_still_writes_a_row(self, scheduler, session_factory):
        """A broken send must be visible, not indistinguishable from silence."""
        seed_role(session_factory)
        sender = AsyncMock(return_value=False)

        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=True):
            result = run(scheduler.send_weekly_digest())

        assert result["sent"] is False
        s = session_factory()
        row = s.query(DigestLog).one()
        assert row.status == "failed" and row.error_message
        s.close()

    def test_empty_week_still_sends(self, scheduler, session_factory):
        sender = AsyncMock(return_value=True)

        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=True):
            result = run(scheduler.send_weekly_digest())

        assert result["roles_count"] == 0
        assert sender.await_count == 1
        assert "No roles scored" in sender.await_args.args[0]

    def test_unconfigured_telegram_records_failure(self, scheduler, session_factory):
        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=False):
            result = run(scheduler.send_weekly_digest())

        assert result["sent"] is False
        s = session_factory()
        assert s.query(DigestLog).one().status == "failed"
        s.close()


# ------------------------------------------------------------------ preview

class TestPreviewWeeklyDigest:
    def test_preview_writes_nothing_and_sends_nothing(self, scheduler, session_factory):
        seed_role(session_factory)
        sender = AsyncMock()

        with patch("src.config.get_config", return_value=FakeConfig()), \
             patch("backend.services.webapp_scheduler.send_telegram_message", sender):
            result = scheduler.preview_weekly_digest()

        assert sender.await_count == 0
        s = session_factory()
        assert s.query(DigestLog).count() == 0
        s.close()
        assert result["roles_count"] == 1

    def test_preview_reports_message_length(self, scheduler, session_factory):
        """So the 4096 limit can be checked before a send, not after one fails."""
        seed_role(session_factory)
        with patch("src.config.get_config", return_value=FakeConfig()):
            result = scheduler.preview_weekly_digest()
        assert result["message_length"] == len(result["message"])
        assert result["message_length"] < 4096


# ----------------------------------------------------------------- catch-up

class TestDigestCatchup:
    def test_no_catchup_when_a_row_already_exists(self, scheduler, session_factory):
        from backend.services import webapp_scheduler as mod
        from src.notifications.weekly_digest import previous_week_bounds

        _s, _e, week_start_local = previous_week_bounds(
            datetime.now(timezone.utc), mod.DIGEST_TIMEZONE
        )
        week_start = week_start_local.astimezone(timezone.utc).replace(tzinfo=None)

        s = session_factory()
        s.add(DigestLog(week_start=week_start, roles_count=3, min_score=78, status="sent"))
        s.commit()
        s.close()

        with patch("src.config.get_config", return_value=FakeConfig()):
            assert scheduler.schedule_digest_catchup() is False
        assert scheduler._scheduler.get_job(mod.DIGEST_CATCHUP_JOB_ID) is None

    def test_catchup_queued_when_the_week_was_missed(self, scheduler, session_factory):
        """Simulates a boot after send time with no row — the redeploy case.

        Needs prior history: a virgin install is handled separately below.
        """
        from backend.services import webapp_scheduler as mod

        s = session_factory()
        s.add(DigestLog(week_start=datetime(2020, 1, 6), roles_count=4,
                        min_score=78, status="sent"))
        s.commit()
        s.close()

        cfg = FakeConfig(**{"notifications.weekly_digest.send_time": "00:01"})
        with patch("src.config.get_config", return_value=cfg):
            queued = scheduler.schedule_digest_catchup()

        assert queued is True
        assert scheduler._scheduler.get_job(mod.DIGEST_CATCHUP_JOB_ID) is not None

    def test_no_catchup_on_a_virgin_install(self, scheduler, session_factory):
        """First deploy must not push an unrequested digest a minute after boot.

        A catch-up recovers a *missed* send; with no history nothing was missed.
        """
        from backend.services import webapp_scheduler as mod

        cfg = FakeConfig(**{"notifications.weekly_digest.send_time": "00:01"})
        with patch("src.config.get_config", return_value=cfg):
            assert scheduler.schedule_digest_catchup() is False
        assert scheduler._scheduler.get_job(mod.DIGEST_CATCHUP_JOB_ID) is None

    def test_disabled_config_never_queues_a_catchup(self, scheduler, session_factory):
        cfg = FakeConfig(**{
            "notifications.weekly_digest.enabled": False,
            "notifications.weekly_digest.send_time": "00:01",
        })
        with patch("src.config.get_config", return_value=cfg):
            assert scheduler.schedule_digest_catchup() is False
