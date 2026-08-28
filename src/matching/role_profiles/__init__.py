"""Role profiles: which job titles count as a given kind of role.

Resolution is inference-with-override so no schema change is needed. A schedule's
free-text `keyword` ("Senior Product Manager", "Principal Product Manager") is
mapped to a profile; an explicit id or a config `role_profiles.keyword_map` entry
overrides that when inference guesses wrong.

Falls back to a permissive `generic` profile that reproduces today's behaviour, so
an unrecognised keyword never silently narrows a search.
"""

import logging
import re
from typing import Dict, List, Optional

from src.matching.role_profiles.base import RoleProfile
from src.matching.role_profiles.product_manager import PROFILE as PRODUCT_MANAGER

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_ID = "generic"

# Empty include list = "no title vocabulary", which callers treat as
# "fall back to the literal keyword match". This is what makes an unknown
# keyword behave exactly as it does today rather than matching nothing.
GENERIC = RoleProfile(id="generic", display_name="Generic (keyword match)")

_PROFILES: Dict[str, RoleProfile] = {
    PRODUCT_MANAGER.id: PRODUCT_MANAGER,
    GENERIC.id: GENERIC,
}

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def normalize_title(text: Optional[str]) -> str:
    """Lowercase, drop punctuation, collapse whitespace.

    Makes "Sr. Product Manager", "Sr Product Manager" and "SR. PRODUCT MANAGER"
    compare equal, and lets a term like "vp product" match "VP, Product".
    """
    if not text:
        return ""
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", text.lower())).strip()


def get_profile(profile_id: Optional[str]) -> RoleProfile:
    """Look up a profile, falling back to generic rather than raising."""
    if not profile_id:
        return GENERIC
    profile = _PROFILES.get(profile_id)
    if profile is None:
        logger.warning(f"Unknown role profile '{profile_id}', using generic")
        return GENERIC
    return profile


def list_profiles() -> List[RoleProfile]:
    return list(_PROFILES.values())


def infer_profile_id(keyword: Optional[str]) -> str:
    """Infer a profile from a search keyword.

    Deterministic: the profile whose longest matching include-term appears in the
    keyword wins, so "Principal Product Manager" resolves via "product manager"
    rather than by accident of dict ordering.
    """
    title = normalize_title(keyword)
    if not title:
        return DEFAULT_PROFILE_ID

    best_id, best_len = DEFAULT_PROFILE_ID, 0
    for profile in _PROFILES.values():
        for term in profile.title_include:
            t = normalize_title(term)
            if t and t in title and len(t) > best_len:
                best_id, best_len = profile.id, len(t)
    return best_id


def resolve_profile(keyword: Optional[str], explicit_id: Optional[str] = None) -> RoleProfile:
    """Pick the profile for a search: explicit id, then config map, then inference."""
    if explicit_id:
        return get_profile(explicit_id)

    try:
        from src.config import get_config

        mapping = get_config().get("role_profiles.keyword_map", {}) or {}
        if keyword and keyword in mapping:
            return get_profile(mapping[keyword])
    except Exception:  # config is optional; never let it break a search
        pass

    return get_profile(infer_profile_id(keyword))


def title_filter_terms(profile: RoleProfile) -> tuple:
    """(include, exclude) terms ready for SQL ILIKE patterns.

    Lowercased only — NOT punctuation-stripped. These are matched against raw
    stored titles via ILIKE, so a term must appear literally: "vp product" would
    not match "VP, Product". Punctuation variants are therefore listed
    explicitly in the profile rather than normalized away here.

    An empty include list signals "no vocabulary", which callers must treat as a
    fall back to literal keyword matching.
    """
    return (
        [t.lower().strip() for t in profile.title_include if t and t.strip()],
        [t.lower().strip() for t in profile.title_exclude if t and t.strip()],
    )


def title_matches(title: Optional[str], profile: RoleProfile) -> bool:
    """Python-side equivalent of the SQL filter, for tests and verification."""
    include, exclude = title_filter_terms(profile)
    t = (title or "").lower()
    if any(x in t for x in exclude):
        return False
    if not include:
        return True
    return any(i in t for i in include)


__all__ = [
    "RoleProfile",
    "DEFAULT_PROFILE_ID",
    "GENERIC",
    "get_profile",
    "list_profiles",
    "infer_profile_id",
    "resolve_profile",
    "normalize_title",
    "title_filter_terms",
    "title_matches",
]
