"""Tests for role-profile title filtering.

Guards the behaviour that motivated the change: the previous
`title.ilike('%{keyword}%')` required the keyword to appear as one contiguous
phrase, so 126 of 315 real recent postings — Netflix, Adobe, Okta, NVIDIA,
Scotiabank among them — were imported and then never scored.
"""

import pytest

from src.matching.role_profiles import (
    GENERIC,
    get_profile,
    infer_profile_id,
    resolve_profile,
    title_matches,
)

PM = get_profile("product_manager")


# --- the titles the literal filter used to miss --------------------------------

@pytest.mark.parametrize("title", [
    "Senior Growth Product Manager",              # word inserted mid-phrase
    "Sr. Product Mgr, eBay Live - Discovery",     # abbreviated
    "Product Manager, Self Managed Service",      # no seniority prefix
    "Senior Staff Product Manager",
    "Product Manager – Orders Management",
    "Technical Product Manager - Veeva Labeling AI",
    "Senior AI Product Owner - Global Wealth Management",
    "VP, Product",
    "Head of Product",
    "Group Product Manager",
    "Chef de produit numérique",
])
def test_real_pm_titles_are_matched(title):
    assert title_matches(title, PM), f"should match: {title}"
    assert "senior product manager" not in title.lower(), (
        "this test is only meaningful for titles the literal filter missed"
    )


# --- titles that must stay excluded --------------------------------------------

@pytest.mark.parametrize("title", [
    "Senior Product Designer (Audiences & Data Hub)",
    "Product Marketing Lead - US (West Coast)",
    "Product Design Manager, Enterprise",
    "Staff Software Engineer",
    "Senior Data Scientist, Crypto",
    "Senior Portfolio Manager",
    "Backend Engineer, Product Platform",
])
def test_non_pm_titles_are_excluded(title):
    assert not title_matches(title, PM), f"should NOT match: {title}"


def test_exclude_beats_include():
    """A title carrying both an include and an exclude term is excluded."""
    assert not title_matches("Product Manager / Software Engineer", PM)


# --- profile resolution --------------------------------------------------------

def test_pm_keywords_infer_pm_profile():
    for kw in ("Senior Product Manager", "Principal Product Manager",
               "Product Owner", "Group Product Manager"):
        assert infer_profile_id(kw) == "product_manager", kw


def test_unknown_keyword_falls_back_to_generic():
    assert infer_profile_id("Data Scientist") == "generic"
    assert infer_profile_id("") == "generic"
    assert infer_profile_id(None) == "generic"


def test_generic_profile_matches_everything():
    """Empty vocabulary must not silently exclude — callers fall back to the
    literal keyword match, so the profile itself has to be permissive."""
    assert title_matches("Anything At All", GENERIC)
    assert GENERIC.title_include == []


def test_explicit_id_overrides_inference():
    assert resolve_profile("Data Scientist", "product_manager").id == "product_manager"


def test_unknown_profile_id_does_not_raise():
    assert get_profile("no_such_profile").id == "generic"


# --- SQL query construction ----------------------------------------------------

def test_apply_title_filter_falls_back_for_generic():
    """An unrecognised keyword must behave exactly as it does today."""
    from src.matching.title_filter import apply_title_filter

    class FakeQuery:
        def __init__(self):
            self.filters = []

        def filter(self, cond):
            self.filters.append(cond)
            return self

    q, profile = apply_title_filter(FakeQuery(), "Data Scientist")
    assert profile.id == "generic"
    assert len(q.filters) == 1  # the single literal ilike, not a vocabulary OR


def test_apply_title_filter_uses_vocabulary_for_pm():
    from src.matching.title_filter import apply_title_filter

    class FakeQuery:
        def __init__(self):
            self.filters = []

        def filter(self, cond):
            self.filters.append(cond)
            return self

    q, profile = apply_title_filter(FakeQuery(), "Senior Product Manager")
    assert profile.id == "product_manager"
    assert len(q.filters) == 1  # one and_() wrapping include-OR and exclude-NOT
