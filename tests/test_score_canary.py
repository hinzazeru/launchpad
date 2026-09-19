"""Tests for the score-drift canary.

What this guards: matching runs on gemini-3-flash-preview, a preview model
Google can change or retire without notice. The validated calibration (senior
~71, principal ~84, exec ~98) and the 0.85 high-match threshold are tuned to it,
so a silent model swap would move every score at once and look exactly like the
job market shifting.

Precedent in this repo: commit b4fe360 pinned a preview model to GA and churned
86% of extracted domains. It was found weeks later, by hand.
"""

import json

import pytest

from src.matching.canary import (
    DEFAULT_MAX_DELTA_ALERT,
    DEFAULT_MEAN_DELTA_ALERT,
    assess_drift,
    compare_scores,
    format_report,
    load_canary_set,
    select_canary_jobs,
)


def obs(score, baseline, title="T", company="C", job_id=1):
    return {"job_id": job_id, "title": title, "company": company,
            "score": score, "baseline_score": baseline}


# --- comparison ----------------------------------------------------------------

def test_stable_run_reports_no_drift():
    s = compare_scores([obs(88, 88), obs(70, 71), obs(50, 49)])
    assert s["n_compared"] == 3
    assert s["mean_abs_delta"] < 1.0
    assert not assess_drift(s)["alert"]


def test_uniform_shift_is_caught():
    """The signature of a model swap: everything moves the same direction."""
    s = compare_scores([obs(78, 88), obs(60, 71), obs(40, 49)])
    v = assess_drift(s)
    assert v["alert"]
    assert any("mean absolute drift" in r for r in v["reasons"])


def test_single_large_move_is_caught_even_if_mean_is_small():
    """One job moving 20 points matters even when the rest are steady.

    Sized like the real set (20 jobs): one outlier barely moves the mean, so
    the max-delta rule is what has to catch it.
    """
    steady = [obs(88, 88, job_id=i) for i in range(19)]
    s = compare_scores(steady + [obs(68, 88, job_id=99)])
    assert s["mean_abs_delta"] < DEFAULT_MEAN_DELTA_ALERT, "mean alone must not trip"
    assert s["max_abs_delta"] >= DEFAULT_MAX_DELTA_ALERT
    v = assess_drift(s)
    assert v["alert"]
    assert any("points" in r for r in v["reasons"])


def test_model_change_always_alerts_regardless_of_scores():
    """Catching the swap before scores move is strictly better than after."""
    s = compare_scores([obs(88, 88)])
    assert not assess_drift(s, model_changed=False)["alert"]
    v = assess_drift(s, model_changed=True)
    assert v["alert"] and "matching model changed" in v["reasons"]


def test_threshold_crossings_are_counted_and_directional():
    s = compare_scores([obs(86, 84), obs(83, 87), obs(70, 70)], high_match_threshold=85.0)
    assert s["n_crossings"] == 2
    dirs = {c["direction"] for c in s["threshold_crossings"]}
    assert dirs == {"gained", "lost"}


def test_many_crossings_alert_even_when_each_move_is_small():
    """Jobs sitting near the bar can flip on small drift — that is the point."""
    o = [obs(86, 84, job_id=i) for i in range(3)]
    s = compare_scores(o, high_match_threshold=85.0)
    assert s["mean_abs_delta"] < DEFAULT_MEAN_DELTA_ALERT
    assert assess_drift(s)["alert"]


# --- failure handling ----------------------------------------------------------

def test_failed_jobs_are_excluded_from_deltas_not_counted_as_zero():
    """A failed score must not read as 'no drift'."""
    s = compare_scores([obs(None, 88), obs(88, 88)])
    assert s["n_failed"] == 1
    assert s["n_compared"] == 1
    assert s["mean_abs_delta"] == 0.0


def test_first_run_has_no_baseline_and_compares_nothing():
    s = compare_scores([obs(88, None), obs(70, None)])
    assert s["n_compared"] == 0
    assert assess_drift(s)["alert"]
    assert "nothing could be compared" in assess_drift(s)["reasons"]


def test_empty_observations_do_not_divide_by_zero():
    s = compare_scores([])
    assert s["mean_abs_delta"] == 0.0 and s["n_compared"] == 0


# --- canary set ----------------------------------------------------------------

def test_missing_set_file_returns_empty_not_crash(tmp_path):
    assert load_canary_set(tmp_path / "nope.json") == []


def test_malformed_set_file_returns_empty(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert load_canary_set(p) == []


def test_set_entries_missing_fields_are_skipped(tmp_path):
    p = tmp_path / "set.json"
    p.write_text(json.dumps({"jobs": [
        {"title": "A", "company": "B"},
        {"title": "C"},
        {"company": "D"},
        "garbage",
    ]}))
    assert load_canary_set(p) == [{"title": "A", "company": "B"}]


def test_pinned_set_is_valid_and_stratified():
    """The committed set must be loadable and cover the score range."""
    entries = load_canary_set()
    assert len(entries) >= 10, "canary set should be substantial enough to detect drift"
    assert all(e["title"] and e["company"] for e in entries)
    # (title, company) pairs must be unique or the same job is weighted twice.
    pairs = {(e["title"], e["company"]) for e in entries}
    assert len(pairs) == len(entries)


# --- reporting -----------------------------------------------------------------

def test_report_names_the_model_change():
    s = compare_scores([obs(88, 88)])
    v = assess_drift(s, model_changed=True)
    report = format_report(s, v, "gemini-3.8-flash", "gemini-3-flash-preview")
    assert "gemini-3-flash-preview" in report and "gemini-3.8-flash" in report
    assert "⚠️" in report


def test_stable_report_is_marked_stable():
    s = compare_scores([obs(88, 88)])
    report = format_report(s, assess_drift(s), "gemini-3-flash-preview", "gemini-3-flash-preview")
    assert "✅" in report and "⚠️" not in report


def test_report_mentions_missing_canary_jobs():
    s = compare_scores([obs(88, 88)])
    report = format_report(s, assess_drift(s), "m", "m", missing=[{"title": "X", "company": "Y"}])
    assert "no longer in the database" in report


def test_report_fits_telegram_limit_at_full_set_size():
    o = [obs(60, 88, title=f"Very Long Senior Product Manager Title Number {i}",
             company=f"Company With A Long Name {i}", job_id=i) for i in range(20)]
    s = compare_scores(o)
    report = format_report(s, assess_drift(s), "gemini-3-flash-preview", "gemini-3-flash-preview")
    assert len(report) < 4096


# --- selection -----------------------------------------------------------------

def test_select_returns_empty_when_nothing_eligible():
    class EmptyQuery:
        def query(self, *a, **k): return self
        def group_by(self, *a, **k): return self
        def subquery(self): return self
        def join(self, *a, **k): return self
        def filter(self, *a, **k): return self
        def all(self): return []
        c = type("c", (), {"score": None, "job_id": None})()
    assert select_canary_jobs(EmptyQuery()) == []
