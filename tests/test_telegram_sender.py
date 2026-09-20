"""Tests for the shared Telegram send helper.

The bug this helper was extracted to fix: both original copies in
`webapp_scheduler.py` fired the POST and never looked at the response, so a
Telegram-side rejection — bad parse_mode, over-length body, revoked token —
was logged as a success. These tests exist mostly to keep that from coming
back, so the response-status cases carry the weight.
"""

import asyncio
from unittest.mock import patch

import pytest

from src.notifications.telegram_sender import (
    TELEGRAM_MAX_MESSAGE_CHARS,
    send_telegram_message,
    telegram_configured,
)


def run(coro):
    """Drive a coroutine from a sync test; the repo has no pytest-asyncio."""
    return asyncio.run(coro)


class FakeConfig:
    def __init__(self, token="token", chat="chat"):
        self.values = {"telegram.bot_token": token, "telegram.chat_id": chat}

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeResponse:
    def __init__(self, status, body=""):
        self.status = status
        self._body = body

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    """Records calls so "no HTTP attempted" is assertable, not assumed."""

    posts = []

    def __init__(self, response):
        self._response = response

    def post(self, url, json=None):
        FakeSession.posts.append((url, json))
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def clear_posts():
    FakeSession.posts = []
    yield
    FakeSession.posts = []


def patched_aiohttp(response):
    """Patch aiohttp.ClientSession to hand back our fake."""
    import aiohttp

    return patch.object(aiohttp, "ClientSession", lambda *a, **k: FakeSession(response))


class TestTelegramConfigured:
    def test_true_when_both_present(self):
        assert telegram_configured(FakeConfig()) is True

    def test_false_without_token(self):
        assert telegram_configured(FakeConfig(token=None)) is False

    def test_false_without_chat_id(self):
        assert telegram_configured(FakeConfig(chat=None)) is False


class TestSendTelegramMessage:
    def test_http_200_returns_true(self):
        with patched_aiohttp(FakeResponse(200)):
            assert run(send_telegram_message("hello", config=FakeConfig())) is True
        assert len(FakeSession.posts) == 1

    def test_http_400_returns_false_and_logs_body(self, caplog):
        """The whole reason this helper exists — the old code returned success
        here."""
        with patched_aiohttp(FakeResponse(400, "Bad Request: can't parse entities")):
            with caplog.at_level("WARNING"):
                result = run(send_telegram_message("hello", config=FakeConfig()))
        assert result is False
        assert "can't parse entities" in caplog.text

    def test_missing_token_makes_no_http_call(self):
        with patched_aiohttp(FakeResponse(200)):
            assert run(send_telegram_message("hi", config=FakeConfig(token=None))) is False
        assert FakeSession.posts == []

    def test_missing_chat_id_makes_no_http_call(self):
        with patched_aiohttp(FakeResponse(200)):
            assert run(send_telegram_message("hi", config=FakeConfig(chat=None))) is False
        assert FakeSession.posts == []

    def test_over_length_message_rejected_before_the_call(self):
        """Rejected up front rather than letting Telegram 400 it."""
        text = "x" * (TELEGRAM_MAX_MESSAGE_CHARS + 1)
        with patched_aiohttp(FakeResponse(200)):
            assert run(send_telegram_message(text, config=FakeConfig())) is False
        assert FakeSession.posts == []

    def test_exactly_at_the_limit_is_sent(self):
        text = "x" * TELEGRAM_MAX_MESSAGE_CHARS
        with patched_aiohttp(FakeResponse(200)):
            assert run(send_telegram_message(text, config=FakeConfig())) is True
        assert len(FakeSession.posts) == 1

    def test_empty_message_makes_no_http_call(self):
        with patched_aiohttp(FakeResponse(200)):
            assert run(send_telegram_message("", config=FakeConfig())) is False
        assert FakeSession.posts == []

    def test_parse_mode_is_sent_and_omittable(self):
        with patched_aiohttp(FakeResponse(200)):
            run(send_telegram_message("hi", config=FakeConfig(), parse_mode="HTML"))
        assert FakeSession.posts[-1][1]["parse_mode"] == "HTML"

        FakeSession.posts = []
        with patched_aiohttp(FakeResponse(200)):
            run(send_telegram_message("hi", config=FakeConfig(), parse_mode=""))
        assert "parse_mode" not in FakeSession.posts[-1][1]

    def test_network_failure_returns_false_rather_than_raising(self):
        """A notification failure must not break the thing being notified about."""
        import aiohttp

        def boom(*a, **k):
            raise OSError("network down")

        with patch.object(aiohttp, "ClientSession", boom):
            assert run(send_telegram_message("hi", config=FakeConfig())) is False

    def test_defaults_to_html_parse_mode(self):
        with patched_aiohttp(FakeResponse(200)):
            run(send_telegram_message("hi", config=FakeConfig()))
        assert FakeSession.posts[-1][1]["parse_mode"] == "HTML"

    def test_payload_carries_chat_id_and_text(self):
        with patched_aiohttp(FakeResponse(200)):
            run(send_telegram_message("body text", config=FakeConfig()))
        _url, payload = FakeSession.posts[-1]
        assert payload["chat_id"] == "chat"
        assert payload["text"] == "body text"


class TestRefactoredCallSites:
    """The two notifications that predate the helper must be unchanged in text.

    Acceptance criterion for the extraction: only the transport moved. A
    refactor that quietly reworded the alerts would be a behaviour change
    smuggled in as cleanup.
    """

    class FakeSchedule:
        id = 1
        name = "Daily Senior Product Manager"
        max_retries = 2

    def _capture(self, coro_factory):
        from unittest.mock import AsyncMock

        sender = AsyncMock(return_value=True)
        with patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=True):
            run(coro_factory())
        return sender

    def test_failure_notification_text_unchanged(self):
        from backend.services.webapp_scheduler import WebAppScheduler

        sched = WebAppScheduler()
        sender = self._capture(
            lambda: sched._send_failure_notification(self.FakeSchedule(), "Gemini unavailable")
        )

        text = sender.await_args.args[0]
        assert text == (
            '❌ Scheduled Search Failed: "Daily Senior Product Manager"\n'
            "\n"
            "Error: Gemini unavailable\n"
            "\n"
            "Retries configured: 2"
        )

    def test_run_notification_goes_through_the_helper(self):
        from backend.services.webapp_scheduler import WebAppScheduler

        sched = WebAppScheduler()
        result = {"high_matches": 2, "jobs_fetched": 40, "jobs_matched": 12,
                  "top_matches": [{"title": "Senior PM", "company": "Acme", "score": 91}]}
        sender = self._capture(
            lambda: sched._send_notification(self.FakeSchedule(), result)
        )

        text = sender.await_args.args[0]
        assert text.startswith('✅ Scheduled Search Complete: "Daily Senior Product Manager"')
        assert "1. Senior PM @ Acme (91%)" in text
        assert "View in Job Matches:" in text

    def test_unconfigured_telegram_skips_without_sending(self):
        from backend.services.webapp_scheduler import WebAppScheduler
        from unittest.mock import AsyncMock

        sched = WebAppScheduler()
        sender = AsyncMock()
        with patch("backend.services.webapp_scheduler.send_telegram_message", sender), \
             patch("backend.services.webapp_scheduler.telegram_configured", return_value=False):
            run(sched._send_failure_notification(self.FakeSchedule(), "boom"))
        assert sender.await_count == 0
