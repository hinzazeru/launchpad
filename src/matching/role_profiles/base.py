"""Shape of a role profile.

A role profile is everything that changes when searching for a different KIND of
role. Today that is title vocabulary; the shape leaves room for the rubric and
panel content described in tasks/tasks-hiring-panel-triage.md without requiring
those to exist yet.

Deliberately NOT part of a profile: anything about the CANDIDATE. Their résumé,
domains, and experience are the same person regardless of which role type is
being searched, so that stays in the matching prompt.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class RoleProfile:
    id: str
    display_name: str

    # A title must contain at least one include term, and no exclude term, to be
    # considered this kind of role. Compared against a normalized title (see
    # normalize_title) so punctuation and spacing differences don't matter.
    title_include: List[str] = field(default_factory=list)
    title_exclude: List[str] = field(default_factory=list)

    # Reserved for later phases; unused today.
    match_framing: str = ""
