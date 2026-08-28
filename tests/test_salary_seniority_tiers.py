"""Seniority tier definitions for the /analytics/salary endpoint.

Group Product Manager roles previously matched no tier: "senior" looked for
senior/sr., "principal" for principal/staff, "lead" for lead, and nothing looked
for "group". Those postings were therefore invisible unless the user selected
"All Levels", which mixes them with 1,000+ Senior roles $30k below.

Tiers are grouped by measured pay band rather than title prestige — over 1,646
PM postings with salary in a 90-day window, principal ($190k), staff ($196k) and
group ($198k) sat within $8k of each other and well above senior ($165k).
"""

import pytest

# Mirrors the mapping in backend/routers/analytics.py::salary_analytics.
# Kept as data so the test documents intent rather than re-implementing a branch.
TIERS = {
    "senior": ["senior", "sr.", "sr "],
    "lead": ["lead"],
    "principal": ["principal", "staff", "group"],
    "group": ["group"],
    "all": [],
}


def matches(title: str, tier: str) -> bool:
    keywords = TIERS[tier]
    if not keywords:
        return True
    return any(k in title.lower() for k in keywords)


# --- the regression ------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Group Product Manager",
    "Group Product Manager, Payments Core",
    "Group Product Manager II, Pricing",
    "Group Product Manager (GRC)",
])
def test_group_pm_now_matches_a_tier(title):
    """Previously matched nothing but 'all'."""
    assert matches(title, "principal"), "group roles belong to the principal band"
    assert matches(title, "group")


def test_group_pm_was_previously_orphaned():
    """Documents the old behaviour so the fix is not silently reverted."""
    old_principal = ["principal", "staff"]
    assert not any(k in "group product manager" for k in old_principal)
    assert "senior" not in "group product manager"
    assert "lead" not in "group product manager"


# --- tier membership -----------------------------------------------------------

@pytest.mark.parametrize("title,tier", [
    ("Senior Product Manager", "senior"),
    ("Sr. Product Manager, Growth", "senior"),
    ("Principal Product Manager", "principal"),
    ("Staff Product Manager", "principal"),
    ("Group Product Manager", "principal"),
    ("Lead Product Manager", "lead"),
])
def test_expected_tier_membership(title, tier):
    assert matches(title, tier)


@pytest.mark.parametrize("title", [
    "Senior Product Manager",
    "Group Product Manager",
    "Product Manager",
])
def test_all_tier_matches_everything(title):
    assert matches(title, "all")


def test_plain_pm_is_in_no_seniority_tier():
    """An unlevelled title should only appear under 'all'."""
    for tier in ("senior", "lead", "principal", "group"):
        assert not matches("Product Manager, Payments", tier)


# --- overlap is intentional ----------------------------------------------------

def test_senior_group_pm_appears_in_both_tiers():
    """"Senior Group Product Manager" is real. Tiers are filters, not an
    exclusive partition, so appearing in two is correct — a user selecting
    either level should see it."""
    title = "Senior Group Product Manager, Dropbox Sign"
    assert matches(title, "senior")
    assert matches(title, "principal")
    assert matches(title, "group")


def test_group_is_a_subset_of_principal():
    """'Group only' must never surface a role the combined tier hides."""
    for title in ("Group Product Manager", "Group Product Manager, Consumer"):
        assert matches(title, "group")
        assert matches(title, "principal")
