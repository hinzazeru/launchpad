"""Company name canonicalization for cross-source deduplication.

Job postings arrive from providers that name the same employer differently:

    Bright Data (LinkedIn) : "D2L Corporation", "1Password", "League Inc."
    Greenhouse (ATS)       : board tokens — "d2l", "1password", "leagueinc"

The dedup key in ``crud.get_existing_jobs_for_repost_check`` and the
``uq_job_postings_title_company`` constraint both compare
``(lower(trim(title)), lower(trim(company)))``. Lowercasing alone collapses
"Faire"/"faire" but NOT "D2L Corporation"/"d2l" — so without canonicalization
the same job imported from two sources lands as two rows.

``canonical_company`` produces a comparison key only. It is deliberately NOT
written to ``JobPosting.company``, which keeps the human-readable display name
(providers should set that from a curated list, never from a board token).
"""

import re
from typing import Optional

# Legal-entity suffixes stripped before comparison. Order matters only in that
# multi-word forms must be tried before their single-word prefixes, so
# "corporation" isn't left as a dangling "corp" match.
_LEGAL_SUFFIXES = (
    "corporation",
    "incorporated",
    "limited",
    "holdings",
    "company",
    "group",
    "corp",
    "inc",
    "ltd",
    "llc",
    "plc",
    "gmbh",
    "sa",
    "nv",
    "ab",
    "co",
)

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def canonical_company(name: Optional[str]) -> str:
    """Return a normalized comparison key for a company name.

    Lowercases, strips punctuation and legal-entity suffixes, then removes all
    whitespace so token-style names ("leagueinc") and spaced display names
    ("League Inc.") converge.

    Returns "" for None/blank input rather than raising — callers treat an
    empty key as "cannot compare" and fall back to the raw name.

    >>> canonical_company("D2L Corporation")
    'd2l'
    >>> canonical_company("1Password")
    '1password'
    >>> canonical_company("League Inc.")
    'league'
    """
    if not name:
        return ""

    text = _PUNCT_RE.sub(" ", name.lower())
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""

    # Strip trailing legal suffixes repeatedly: "Acme Holdings Inc" -> "acme".
    # Guarded so a company whose whole name IS a suffix word (e.g. "Group")
    # isn't reduced to an empty key.
    changed = True
    while changed:
        changed = False
        for suffix in _LEGAL_SUFFIXES:
            if text.endswith(" " + suffix):
                stripped = text[: -(len(suffix) + 1)].strip()
                if stripped:
                    text = stripped
                    changed = True
                    break

    return text.replace(" ", "")


def same_company(a: Optional[str], b: Optional[str]) -> bool:
    """True if two company names refer to the same employer.

    Falls back to a raw case-insensitive comparison when either name
    canonicalizes to "" — better to under-merge than to collapse two unrelated
    blank-ish names together.
    """
    ca, cb = canonical_company(a), canonical_company(b)
    if not ca or not cb:
        return (a or "").strip().lower() == (b or "").strip().lower()
    return ca == cb
