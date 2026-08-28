"""Title filtering for the match stage.

Replaces `JobPosting.title.ilike('%{keyword}%')`, which required the search
keyword to appear as one contiguous phrase in the title. Measured against 315
real postings from the last 7 days, that literal filter matched 142 while the
role-profile vocabulary matches 268 — 126 genuine PM roles were imported,
enriched, stored, and then never scored because the title filter excluded them
before the matcher ever saw them.

The three failure patterns, all mundane:
    inserted word     "Senior GROWTH Product Manager"
    abbreviation      "Sr. Product Mgr"
    no prefix         "Product Manager, Self Managed Service"

Kept as one helper used by both `backend/routers/search.py` and
`backend/services/webapp_scheduler.py`, which already carry ~300 lines of
near-duplicate match-stage code that has drifted before.
"""

import logging
from typing import Optional

from sqlalchemy import and_, not_, or_

from src.database.models import JobPosting
from src.matching.role_profiles import RoleProfile, resolve_profile, title_filter_terms

logger = logging.getLogger(__name__)


def apply_title_filter(
    query,
    keyword: str,
    profile: Optional[RoleProfile] = None,
    explicit_profile_id: Optional[str] = None,
):
    """Add the title condition to a JobPosting query.

    Falls back to the original literal `ilike('%keyword%')` when the resolved
    profile has no title vocabulary (the `generic` profile). That fallback is
    deliberate: an unrecognised keyword must behave exactly as it does today
    rather than silently matching nothing or everything.

    Returns (query, profile) so callers can log or report which profile applied.
    """
    profile = profile or resolve_profile(keyword, explicit_profile_id)
    include, exclude = title_filter_terms(profile)

    if not include:
        logger.info(
            f"Title filter: no vocabulary for profile '{profile.id}', "
            f"falling back to literal match on '{keyword}'"
        )
        return query.filter(JobPosting.title.ilike(f"%{keyword}%")), profile

    conditions = [or_(*[JobPosting.title.ilike(f"%{t}%") for t in include])]
    if exclude:
        conditions.append(
            not_(or_(*[JobPosting.title.ilike(f"%{t}%") for t in exclude]))
        )

    logger.info(
        f"Title filter: profile '{profile.id}' "
        f"({len(include)} include / {len(exclude)} exclude terms) "
        f"replacing literal match on '{keyword}'"
    )
    return query.filter(and_(*conditions)), profile
