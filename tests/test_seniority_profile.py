"""Tests for seniority-tier aggregation.

Three data hazards measured in the real corpus, each of which silently corrupts
the output rather than raising:

1. 22 of 601 `structured_requirements` rows hold JSON `null`, which satisfies
   SQL `IS NOT NULL` and then fails `.get()`.
2. `min_years` is mixed int/str across rows.
3. Raw skill strings fragment: 579 postings produced 1,313 distinct must-have
   strings, splitting `communication` (64) from `communication skills` (29).
"""

import json

import pytest

from src.analysis.seniority_profile import (
    build_profile,
    canonicalise,
    classify_responsibility,
    coerce_years,
    compare,
    parse_requirements,
    percentiles,
)
from src.analysis.seniority_tiers import TIER_LABELS, is_valid_tier, title_in_tier


class Row:
    def __init__(self, title="Principal Product Manager", requirements=None):
        self.title = title
        self.structured_requirements = requirements


# --- hazard 1: JSON null ------------------------------------------------------

@pytest.mark.parametrize("bad", [None, "null", "not json", "[1,2]", 42, "", b"x"])
def test_unusable_requirements_return_none(bad):
    assert parse_requirements(bad) is None


def test_dict_and_json_string_both_parse():
    assert parse_requirements({"a": 1}) == {"a": 1}
    assert parse_requirements(json.dumps({"a": 1})) == {"a": 1}


def test_json_null_rows_are_excluded_from_usable_count():
    rows = [Row(requirements={"min_years": 8}), Row(requirements="null"), Row(requirements=None)]
    profile = build_profile(rows)
    assert profile["n_postings"] == 3
    assert profile["n_usable"] == 1, "JSON-null rows must not count as usable"


# --- hazard 2: mixed-type min_years -------------------------------------------

@pytest.mark.parametrize("value,expected", [("8", 8.0), (8, 8.0), (8.0, 8.0), ("7.5", 7.5)])
def test_years_coerce(value, expected):
    assert coerce_years(value) == expected


@pytest.mark.parametrize("bad", ["eight", None, "", [], {}, 0, -1, 60])
def test_implausible_or_unparseable_years_dropped_not_raised(bad):
    assert coerce_years(bad) is None


# --- hazard 3: skill fragmentation --------------------------------------------

def test_canonicalise_folds_variants():
    mapping = {"communication skills": "communication", "communication": "communication"}
    assert canonicalise("Communication Skills", mapping) == "communication"
    assert canonicalise("communication", mapping) == "communication"


def test_unmapped_skill_passes_through_lowercased():
    """A partial map must degrade gradually, never drop the long tail."""
    assert canonicalise("Some Niche Skill", {}) == "some niche skill"


def test_skills_counted_once_per_posting():
    """A description repeating a skill is one role wanting it, not three."""
    rows = [Row(requirements={
        "must_have_skills": [{"name": "SQL"}, {"name": "sql"}, {"name": "Sql"}],
    })]
    profile = build_profile(rows)
    assert [i["count"] for i in profile["must_have"] if i["name"] == "sql"] == [1]


def test_bare_string_skills_are_accepted():
    """Some rows store plain strings rather than {name: ...} objects."""
    rows = [Row(requirements={"must_have_skills": ["product strategy"]})]
    assert build_profile(rows)["must_have"][0]["name"] == "product strategy"


# --- percentiles ---------------------------------------------------------------

def test_percentiles_on_known_input():
    p = percentiles([float(i) for i in range(1, 11)])
    assert (p["p25"], p["median"], p["p75"], p["min"], p["max"], p["n"]) == (3.0, 6.0, 8.0, 1.0, 10.0, 10)


def test_percentiles_empty_returns_nones_not_crash():
    p = percentiles([])
    assert p["median"] is None and p["n"] == 0


def test_empty_cohort_does_not_divide_by_zero():
    profile = build_profile([])
    assert profile["n_usable"] == 0
    assert profile["must_have"] == []
    assert profile["responsibility_coverage"]["pct"] == 0.0


# --- comparison ----------------------------------------------------------------

def test_compare_identifies_distinctive_items():
    tier = {"must_have": [{"name": "strategy", "count": 60, "pct": 20.0},
                          {"name": "sql", "count": 30, "pct": 10.0}]}
    base = {"must_have": [{"name": "strategy", "count": 80, "pct": 8.0},
                          {"name": "sql", "count": 100, "pct": 10.0}]}
    result = compare(tier, base)
    distinctive = {r["name"]: r["delta"] for r in result["distinctive_to_tier"]}
    assert distinctive == {"strategy": 12.0}, "only strategy is more common in the tier"


def test_compare_uses_share_not_raw_count():
    """Cohorts differ ~5x in size; raw counts would make the baseline dominate."""
    tier = {"must_have": [{"name": "x", "count": 10, "pct": 50.0}]}
    base = {"must_have": [{"name": "x", "count": 100, "pct": 10.0}]}
    assert compare(tier, base)["distinctive_to_tier"][0]["delta"] == 40.0


def test_compare_handles_item_absent_from_baseline():
    tier = {"must_have": [{"name": "platform strategy", "count": 5, "pct": 4.4}]}
    assert compare(tier, {"must_have": []})["distinctive_to_tier"][0]["baseline_pct"] == 0.0


# --- responsibility themes -----------------------------------------------------

def test_classify_is_multi_label():
    themes = [
        {"name": "strategy", "keywords": ["product vision"]},
        {"name": "stakeholders", "keywords": ["align stakeholders"]},
    ]
    hits = classify_responsibility("define product vision and align stakeholders", themes)
    assert set(hits) == {"strategy", "stakeholders"}


def test_unmatched_responsibility_classifies_to_nothing():
    assert classify_responsibility("do an unrelated thing", [{"name": "s", "keywords": ["roadmap"]}]) == []


def test_coverage_is_reported_so_the_ui_can_caveat_it():
    rows = [Row(requirements={"key_responsibilities": ["own the roadmap", "something else"]})]
    themes = [{"name": "roadmap", "keywords": ["roadmap"]}]
    import src.analysis.seniority_profile as sp
    sp._theme_map = themes
    try:
        cov = build_profile(rows)["responsibility_coverage"]
        assert cov == {"classified": 1, "total": 2, "pct": 50.0}
    finally:
        sp._theme_map = None


# --- tier vocabulary -----------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Principal Product Manager",
    "Staff Product Manager",
    "Group Product Manager",
    "Staff, Product Manager - Offsite Ads",
    "Staff/Senior Product Manager",
    "Group/Lead Product Manager, Identity",
])
def test_principal_tier_membership(title):
    assert title_in_tier(title, "principal")


@pytest.mark.parametrize("title", [
    "Staffing Coordinator",                          # \bstaff\b must not match staffing
    "Product Group Technology Lead II",              # a team, not a seniority
    "Senior Product Manager, Client Product Group",  # trailing "Product Group"
    "Senior Product Manager",
    "Product Manager",
])
def test_principal_tier_exclusions(title):
    assert not title_in_tier(title, "principal")


def test_senior_tier_matches_abbreviations():
    for t in ("Senior Product Manager", "Sr. Product Manager", "Sr Product Manager"):
        assert title_in_tier(t, "senior")


def test_all_tier_matches_everything():
    assert title_in_tier("Anything At All", "all")


def test_unknown_tier_is_permissive_like_all():
    """Matches the salary endpoint's pre-existing behaviour."""
    assert title_in_tier("Product Manager", "nonsense")


def test_valid_tiers():
    assert is_valid_tier("principal") and is_valid_tier("all")
    assert not is_valid_tier("nope")
    assert set(TIER_LABELS) == {"senior", "lead", "principal", "group", "all"}
