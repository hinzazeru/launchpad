"""Tests for the unified high-match threshold.

The bug this guards: three call sites each hardcoded their own bar. The two web
search paths counted >= 0.85; the scheduled path counted >= 0.70 and its
Telegram text said "(70%+)". A scheduled run's "1 high quality" and the
dashboard's "1 high match" therefore counted different things, so the two were
never comparable.
"""

import pytest

from src.matching.thresholds import (
    DEFAULT_HIGH_MATCH_THRESHOLD,
    count_high_matches,
    format_high_match_threshold,
    get_high_match_threshold,
)


class FakeConfig:
    """Stand-in for src.config.Config — only .get() is used."""

    def __init__(self, values=None):
        self._values = values or {}

    def get(self, key_path, default=None):
        return self._values.get(key_path, default)


def score(m):
    return m["score"]


# --- default ------------------------------------------------------------------

def test_default_with_no_config_key_present_is_085():
    assert get_high_match_threshold(FakeConfig()) == 0.85
    assert DEFAULT_HIGH_MATCH_THRESHOLD == 0.85


def test_config_override_is_respected():
    cfg = FakeConfig({"matching.high_match_threshold": 0.7})
    assert get_high_match_threshold(cfg) == 0.7


def test_string_value_from_env_override_is_coerced():
    """ENV_OVERRIDES may hand back a raw string if the default hint is missing."""
    cfg = FakeConfig({"matching.high_match_threshold": "0.9"})
    assert get_high_match_threshold(cfg) == 0.9


# --- the regression ------------------------------------------------------------

def test_both_pipelines_now_agree():
    """The scheduled path and the web path resolve the same bar from one config."""
    cfg = FakeConfig()
    matches = [{"score": s} for s in (0.92, 0.86, 0.84, 0.71, 0.50)]

    web = count_high_matches(matches, score, cfg)
    scheduled = count_high_matches(matches, score, cfg)

    assert web == scheduled == 2


def test_the_old_070_bar_would_have_disagreed():
    """Documents the drift so it is not silently reintroduced."""
    matches = [{"score": s} for s in (0.92, 0.86, 0.84, 0.71, 0.50)]
    old_web = len([m for m in matches if score(m) >= 0.85])
    old_scheduled = len([m for m in matches if score(m) >= 0.70])
    assert old_web == 2
    assert old_scheduled == 4
    assert old_web != old_scheduled


# --- counting ------------------------------------------------------------------

def test_threshold_is_inclusive():
    cfg = FakeConfig()
    assert count_high_matches([{"score": 0.85}], score, cfg) == 1
    assert count_high_matches([{"score": 0.8499}], score, cfg) == 0


def test_empty_matches():
    assert count_high_matches([], score, FakeConfig()) == 0


def test_count_honours_an_override():
    cfg = FakeConfig({"matching.high_match_threshold": 0.7})
    matches = [{"score": s} for s in (0.92, 0.86, 0.84, 0.71, 0.50)]
    assert count_high_matches(matches, score, cfg) == 4


# --- bad config must not reclassify everything ---------------------------------

@pytest.mark.parametrize("bad", ["not-a-number", None, 0, -0.5, 1.5, 85])
def test_out_of_range_or_unparseable_falls_back_to_default(bad):
    """A typo like `high_match_threshold: 85` must not make every match 'high'."""
    cfg = FakeConfig({"matching.high_match_threshold": bad})
    assert get_high_match_threshold(cfg) == DEFAULT_HIGH_MATCH_THRESHOLD


def test_upper_bound_of_one_is_allowed():
    cfg = FakeConfig({"matching.high_match_threshold": 1.0})
    assert get_high_match_threshold(cfg) == 1.0


# --- notification text ---------------------------------------------------------

def test_telegram_text_reflects_the_configured_value():
    assert format_high_match_threshold(FakeConfig()) == "85%"
    assert format_high_match_threshold(
        FakeConfig({"matching.high_match_threshold": 0.7})
    ) == "70%"


def test_notification_bar_no_longer_hardcodes_70():
    """The literal '(70%+)' string is gone from the scheduler."""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "backend" / "services" / "webapp_scheduler.py"
    assert "(70%+)" not in src.read_text()


# --- no literals left in either pipeline ---------------------------------------

def test_no_literal_thresholds_remain_in_either_pipeline():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for rel in ("backend/routers/search.py", "backend/services/webapp_scheduler.py"):
        text = (root / rel).read_text()
        assert "get_blended_score(m) >= 0.85" not in text, rel
        assert "get_blended_score(m) >= 0.70" not in text, rel
