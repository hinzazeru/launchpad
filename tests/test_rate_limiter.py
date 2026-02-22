"""Tests for GeminiRateLimiter, _is_thinking_model, and the shared key limiter.

Covers:
- Two-tier rate limiting: per-model limiter gates through shared upstream
- Circuit breaker: local and upstream both trip on quota exhaustion
- Thinking model classification: explicit prefix list, not broad substrings
- Shared key limiter: lazily created, never baked in at import time
- Combined rate enforcement: calls from different models serialised through shared gate
"""

import time
import threading
import pytest
from unittest.mock import patch, MagicMock, call

import src.integrations.gemini_client as gclient
from src.integrations.gemini_client import (
    GeminiRateLimiter,
    _is_thinking_model,
    get_rate_limiter,
    _DEFAULT_THINKING_MODEL_PREFIXES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_module_state():
    """Clear shared key limiter and per-model cache before and after each test."""
    def _clear():
        with gclient._rate_limiter_cache_lock:
            gclient._rate_limiter_cache.clear()
        with gclient._shared_key_limiter_lock:
            gclient._shared_key_limiter = None

    _clear()
    yield
    _clear()


# ---------------------------------------------------------------------------
# _is_thinking_model()
# ---------------------------------------------------------------------------

class TestIsThinkingModel:
    def test_known_prefix_flash(self):
        assert _is_thinking_model("gemini-2.5-flash") is True

    def test_known_prefix_pro(self):
        assert _is_thinking_model("gemini-2.5-pro") is True

    def test_known_variant_lite(self):
        # startswith("gemini-2.5-flash") — variant still classified as thinking
        assert _is_thinking_model("gemini-2.5-flash-lite") is True

    def test_flash_8b_in_list(self):
        assert _is_thinking_model("gemini-2.5-flash-8b") is True

    def test_exp_prefix(self):
        assert _is_thinking_model("gemini-exp-1206") is True

    def test_flash_20_is_not_thinking(self):
        assert _is_thinking_model("gemini-2.0-flash") is False

    def test_flash_15_is_not_thinking(self):
        assert _is_thinking_model("gemini-1.5-flash") is False

    def test_no_false_positive_125pro(self):
        # The OLD "2.5" substring heuristic would match this; prefix list should not
        assert _is_thinking_model("gemini-1.25-pro") is False

    def test_no_false_positive_version_suffix(self):
        # "2.5" appearing in a suffix of a non-thinking model
        assert _is_thinking_model("gemini-2.0-flash-v2.5") is False

    def test_config_override_adds_custom_model(self):
        mock_config = MagicMock()
        mock_config.get.return_value = ["gemini-custom-think"]
        with patch("src.integrations.gemini_client.get_config", return_value=mock_config):
            assert _is_thinking_model("gemini-custom-think-v1") is True

    def test_config_override_excludes_default_models(self):
        # When config returns a custom list, only those prefixes match
        mock_config = MagicMock()
        mock_config.get.return_value = ["gemini-custom"]
        with patch("src.integrations.gemini_client.get_config", return_value=mock_config):
            # gemini-2.5-flash is NOT in the custom list
            assert _is_thinking_model("gemini-2.5-flash") is False
            # but the custom prefix does match
            assert _is_thinking_model("gemini-custom-model") is True

    def test_config_fallback_on_error(self):
        with patch("src.integrations.gemini_client.get_config", side_effect=RuntimeError("no config")):
            # Falls back to _DEFAULT_THINKING_MODEL_PREFIXES
            assert _is_thinking_model("gemini-2.5-flash") is True
            assert _is_thinking_model("gemini-2.0-flash") is False


# ---------------------------------------------------------------------------
# GeminiRateLimiter — standalone (no upstream)
# ---------------------------------------------------------------------------

class TestGeminiRateLimiterStandalone:
    def test_enforces_min_interval(self):
        """Second call must wait for the minimum interval to elapse."""
        limiter = GeminiRateLimiter(min_interval=0.05)
        t0 = time.monotonic()
        limiter.wait()   # first call — no wait
        limiter.wait()   # second call — should sleep ~50ms
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.04, f"Expected ≥40ms, got {elapsed*1000:.1f}ms"

    def test_allows_call_after_interval_elapses(self):
        """No sleep needed when enough time has already passed."""
        limiter = GeminiRateLimiter(min_interval=0.05)
        limiter.wait()
        time.sleep(0.06)  # let the interval expire
        t0 = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.02, f"Expected <20ms (no sleep needed), got {elapsed*1000:.1f}ms"

    def test_call_with_retry_success(self):
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=0)
        result = limiter.call_with_retry(lambda: "ok")
        assert result == "ok"

    def test_circuit_breaker_blocks_calls(self):
        limiter = GeminiRateLimiter(min_interval=0.001, circuit_breaker_cooldown=60.0)
        limiter._trip_circuit_breaker()
        assert limiter.circuit_open is True
        fn = MagicMock(return_value="ok")
        with pytest.raises(Exception, match="circuit breaker open"):
            limiter.call_with_retry(fn)
        fn.assert_not_called()

    def test_circuit_breaker_expires(self):
        limiter = GeminiRateLimiter(min_interval=0.001, circuit_breaker_cooldown=60.0)
        limiter._circuit_open_until = time.monotonic() - 1  # already expired
        assert limiter.circuit_open is False
        result = limiter.call_with_retry(lambda: "ok")
        assert result == "ok"

    def test_429_triggers_retry(self):
        """Function is retried on 429 errors and returns the successful result."""
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=2)
        call_count = [0]

        def fn():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("429 quota exceeded")
            return "ok"

        with patch("time.sleep"):  # skip actual backoff sleep
            result = limiter.call_with_retry(fn)

        assert result == "ok"
        assert call_count[0] == 3

    def test_all_retries_exhausted_trips_circuit_breaker(self):
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=1, circuit_breaker_cooldown=60.0)

        def fn():
            raise Exception("Resource exhausted")

        with patch("time.sleep"):
            with pytest.raises(Exception, match="Resource exhausted"):
                limiter.call_with_retry(fn)

        assert limiter.circuit_open is True

    def test_non_429_raises_immediately_without_retry(self):
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=2)
        call_count = [0]

        def fn():
            call_count[0] += 1
            raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            limiter.call_with_retry(fn)

        assert call_count[0] == 1  # no retry

    def test_circuit_not_tripped_on_non_429(self):
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=0)
        with pytest.raises(ValueError):
            limiter.call_with_retry(lambda: (_ for _ in ()).throw(ValueError("oops")))
        assert limiter.circuit_open is False

    def test_thread_safety_multiple_waiters(self):
        """Multiple threads must each wait the minimum interval."""
        limiter = GeminiRateLimiter(min_interval=0.02)
        timestamps = []
        lock = threading.Lock()

        def do_wait():
            limiter.wait()
            with lock:
                timestamps.append(time.monotonic())

        threads = [threading.Thread(target=do_wait) for _ in range(3)]
        t0 = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 3 threads through a 20ms limiter should take at least 40ms total
        total = time.monotonic() - t0
        assert total >= 0.035, f"Expected ≥35ms for 3 serialized slots, got {total*1000:.1f}ms"


# ---------------------------------------------------------------------------
# GeminiRateLimiter — two-tier (with upstream)
# ---------------------------------------------------------------------------

class TestGeminiRateLimiterWithUpstream:
    def test_upstream_acquire_slot_called_before_local(self):
        """wait() must call upstream._acquire_slot() before its own _acquire_slot()."""
        upstream = MagicMock(spec=GeminiRateLimiter)
        upstream.circuit_open = False
        limiter = GeminiRateLimiter(min_interval=0.001, upstream=upstream)

        call_order = []
        upstream._acquire_slot.side_effect = lambda: call_order.append("upstream")

        # Monkey-patch local _acquire_slot to track order
        original = limiter._acquire_slot
        def track_local():
            call_order.append("local")
            original()
        limiter._acquire_slot = track_local

        limiter.wait()
        assert call_order == ["upstream", "local"], f"Unexpected order: {call_order}"

    def test_upstream_circuit_open_blocks_call(self):
        """If upstream circuit is open, call_with_retry raises without calling fn."""
        upstream = GeminiRateLimiter(min_interval=0.001, circuit_breaker_cooldown=60.0)
        upstream._trip_circuit_breaker()

        limiter = GeminiRateLimiter(min_interval=0.001, upstream=upstream)
        fn = MagicMock(return_value="ok")

        with pytest.raises(Exception, match="shared circuit breaker open"):
            limiter.call_with_retry(fn)

        fn.assert_not_called()

    def test_quota_exhaustion_trips_local_circuit_breaker(self):
        upstream = GeminiRateLimiter(min_interval=0.001, circuit_breaker_cooldown=0.1)
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=0, upstream=upstream)

        with patch("time.sleep"):
            with pytest.raises(Exception, match="Resource exhausted"):
                limiter.call_with_retry(lambda: (_ for _ in ()).throw(Exception("Resource exhausted")))

        assert limiter.circuit_open is True

    def test_quota_exhaustion_trips_upstream_circuit_breaker(self):
        """When quota is exhausted, the shared key-level circuit must also open."""
        upstream = GeminiRateLimiter(min_interval=0.001, circuit_breaker_cooldown=60.0)
        limiter = GeminiRateLimiter(min_interval=0.001, max_retries=0, upstream=upstream)

        with patch("time.sleep"):
            with pytest.raises(Exception, match="Resource exhausted"):
                limiter.call_with_retry(lambda: (_ for _ in ()).throw(Exception("Resource exhausted")))

        assert upstream.circuit_open is True, "Upstream circuit breaker must open on quota exhaustion"

    def test_combined_rate_limiting_serialises_calls(self):
        """Two models sharing one upstream must be serialised through the upstream gate.

        With upstream min_interval=50ms and two sequential calls from different models,
        the gap between calls must be ≥ 50ms (enforced by the shared upstream slot).
        """
        upstream = GeminiRateLimiter(min_interval=0.05)
        flash = GeminiRateLimiter(min_interval=0.05, upstream=upstream)
        thinking = GeminiRateLimiter(min_interval=0.2, upstream=upstream)

        timestamps = []

        def record():
            timestamps.append(time.monotonic())
            return "ok"

        flash.call_with_retry(record)
        thinking.call_with_retry(record)

        gap = timestamps[1] - timestamps[0]
        assert gap >= 0.045, (
            f"Gap {gap*1000:.1f}ms < upstream minimum 50ms — "
            "calls from different models were NOT serialised by shared upstream"
        )

    def test_no_upstream_means_no_upstream_gate(self):
        """Standalone limiter (upstream=None) has no upstream gate."""
        limiter = GeminiRateLimiter(min_interval=0.001, upstream=None)
        assert limiter._upstream is None
        # Should work fine with no upstream
        result = limiter.call_with_retry(lambda: "ok")
        assert result == "ok"


# ---------------------------------------------------------------------------
# get_rate_limiter() and _get_shared_key_limiter()
# ---------------------------------------------------------------------------

class TestGetRateLimiter:
    def test_returns_same_instance_for_same_model(self):
        l1 = get_rate_limiter("gemini-2.0-flash")
        l2 = get_rate_limiter("gemini-2.0-flash")
        assert l1 is l2

    def test_different_models_get_different_instances(self):
        flash = get_rate_limiter("gemini-2.0-flash")
        thinking = get_rate_limiter("gemini-2.5-flash")
        assert flash is not thinking

    def test_every_per_model_limiter_has_upstream(self):
        flash = get_rate_limiter("gemini-2.0-flash")
        thinking = get_rate_limiter("gemini-2.5-flash")
        assert flash._upstream is not None, "Flash limiter must have an upstream"
        assert thinking._upstream is not None, "Thinking limiter must have an upstream"

    def test_different_models_share_the_same_upstream(self):
        """Flash and thinking limiters must reference the exact same upstream object."""
        flash = get_rate_limiter("gemini-2.0-flash")
        thinking = get_rate_limiter("gemini-2.5-flash")
        assert flash._upstream is thinking._upstream, (
            "Both model limiters must share the same key-level upstream — "
            "isolated upstreams would allow exceeding the combined quota"
        )

    def test_shared_key_limiter_has_no_upstream(self):
        """The root key-level limiter must not have its own upstream (it is the root)."""
        flash = get_rate_limiter("gemini-2.0-flash")
        key_limiter = flash._upstream
        assert key_limiter._upstream is None, "Key limiter must be the root (upstream=None)"

    def test_thinking_model_has_longer_interval_than_flash(self):
        flash = get_rate_limiter("gemini-2.0-flash")
        thinking = get_rate_limiter("gemini-2.5-flash")
        assert thinking._min_interval > flash._min_interval, (
            f"Thinking interval {thinking._min_interval}s should be > "
            f"flash interval {flash._min_interval}s"
        )

    def test_shared_limiter_not_created_at_import_time(self):
        """The shared key limiter must be None until first get_rate_limiter() call.

        This verifies the fix for Issue #6: no import-time config reads.
        """
        # reset_module_state fixture cleared _shared_key_limiter at test start
        assert gclient._shared_key_limiter is None, (
            "Shared key limiter was created at import time — "
            "it should be lazily created on first use only"
        )
        # After calling get_rate_limiter, it should now exist
        get_rate_limiter("gemini-2.0-flash")
        assert gclient._shared_key_limiter is not None

    def test_config_drives_thinking_interval(self):
        """Thinking model interval reads from config if available."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "gemini.rate_limit.thinking_min_interval_ms": 3000,
            "gemini.rate_limit.min_interval_ms": 400,
            "gemini.rate_limit.max_retries": 2,
            "gemini.rate_limit.circuit_breaker_cooldown_s": 120.0,
            "gemini.rate_limit.thinking_model_prefixes": _DEFAULT_THINKING_MODEL_PREFIXES,
        }.get(key, default)

        with patch("src.integrations.gemini_client.get_config", return_value=mock_config):
            thinking = get_rate_limiter("gemini-2.5-flash")

        assert thinking._min_interval == pytest.approx(3.0), (
            f"Expected 3000ms from config, got {thinking._min_interval*1000:.0f}ms"
        )
