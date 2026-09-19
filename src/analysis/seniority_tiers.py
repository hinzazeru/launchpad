"""Seniority tier vocabulary — one definition, two consumers.

``salary_analytics`` and the seniority-profile endpoint must classify roles the
same way; two copies of this mapping would drift the way the high-match
threshold did (0.85 in the web path vs 0.70 in the scheduler, unnoticed for
weeks because each looked reasonable in isolation).

Tiers are grouped by observed pay band rather than title prestige. Measured over
1,646 PM postings with salary in a 90-day window:

    senior/sr.   n=1064  median $165,000
    lead         n=  84  median $175,000
    principal    n= 128  median $190,000
    staff        n=  77  median $196,400
    group        n=  26  median $198,000

principal / staff / group sit within $8k of each other, so they form one tier —
which also lifts that bucket from 128 to ~230 samples. Before this grouping,
"group" matched no tier at all and Group PM roles were invisible outside "all".

Matching is by word boundary, not substring. Measured over 4,032 distinct
product titles, substring matching admitted 9 false positives — "Product Group
Technology Lead II", "EHR for Practice Groups", "Senior Product Manager, Client
Product Group" — none of them Principal-tier roles. A trailing-space variant
("staff ", "group product") was tried first and was worse: it dropped genuine
members like "Staff, Product Manager", "Staff/Senior Product Manager" and
"Group/Lead Product Manager". The word-boundary form removes all 9 false
positives and loses nothing.
"""

import re
from typing import Dict, List, Pattern

# \bstaff\b deliberately excludes "staffing" while admitting "Staff," and
# "Staff/". The (?<!product ) lookbehind drops trailing "... Product Group",
# which names a team rather than a seniority.
TIER_PATTERNS: Dict[str, Pattern] = {
    "senior": re.compile(r"\bsenior\b|\bsr\.?\b", re.I),
    "lead": re.compile(r"\blead\b", re.I),
    "principal": re.compile(r"\bprincipal\b|\bstaff\b|(?<!product )\bgroup\b", re.I),
    # Group PM in isolation. Thin (n~26) — the combined "principal" tier is the
    # better default; this exists for when the distinction matters.
    "group": re.compile(r"(?<!product )\bgroup\b", re.I),
}

# Human-readable, for UI labels and error messages.
TIER_LABELS: Dict[str, str] = {
    "senior": "Senior",
    "lead": "Lead",
    "principal": "Principal / Staff / Group",
    "group": "Group only",
    "all": "All levels",
}

VALID_TIERS: List[str] = list(TIER_LABELS.keys())

DEFAULT_TIER = "principal"
DEFAULT_BASELINE = "senior"


def title_in_tier(title: str, tier: str) -> bool:
    """Whether a job title belongs to ``tier``.

    ``all`` — and any unrecognised tier — matches everything, matching the
    permissive behaviour the salary endpoint already had.
    """
    pattern = TIER_PATTERNS.get((tier or "").strip().lower())
    if pattern is None:
        return True
    return bool(pattern.search(title or ""))


def is_valid_tier(tier: str) -> bool:
    return (tier or "").strip().lower() in TIER_LABELS


def filter_titles_by_tier(rows, tier: str, key=lambda r: r.title):
    """Filter any row sequence by tier, given an accessor for the title."""
    if (tier or "").strip().lower() == "all":
        return list(rows)
    return [r for r in rows if title_in_tier(key(r), tier)]
