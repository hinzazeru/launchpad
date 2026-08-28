"""Product management role profile.

Title vocabulary derived from measurement, not intuition: against 315 real job
postings from the last 7 days, the pipeline's literal
`title ILIKE '%Senior Product Manager%'` matched 142, while this include/exclude
vocabulary matches 268. The 126-job gap was genuine PM roles that were imported,
enriched, stored, and then never scored — Netflix, Adobe, Okta, NVIDIA, and a
Scotiabank wealth-management AI role among them.

The literal filter fails on three mundane patterns:
  - an inserted word   — "Senior GROWTH Product Manager"
  - an abbreviation    — "Sr. Product Mgr"
  - no seniority prefix — "Product Manager, Self Managed Service"
"""

from src.matching.role_profiles.base import RoleProfile

# "product mgr" and "prod mgr" are included because real postings use them
# (two eBay roles in the sample); the plain vocabulary missed them.
_TITLE_INCLUDE = [
    "product manager",
    "product mgr",
    "product owner",
    "product lead",
    "head of product",
    "director of product",
    "product director",
    "vp of product",
    "vp, product",
    "vp product",
    "group product manager",
    "technical product manager",
    "product management",
    "product strategist",
    "chief product officer",
    "cpo",
    "chef de produit",  # fr-CA postings are common in this corpus
]

# Titles containing these are hands-on engineering or adjacent-but-different
# functions, even when they also contain a product-sounding word. Verified
# against the same 315-job sample: the 47 dropped rows were Product Designer,
# Product Marketing Lead, Portfolio Manager, Data Scientist, and similar.
_TITLE_EXCLUDE = [
    "software engineer",
    "product engineer",
    "backend engineer",
    "frontend engineer",
    "full-stack",
    "fullstack",
    "full stack",
    "devops",
    "architect",
    "developer",
    "data engineer",
    "ml engineer",
    "machine learning engineer",
    "qa engineer",
    "sre",
    "staff engineer",
    "senior engineer",
    "product designer",
    "product marketing",
    "design manager",
    "data scientist",
]

PROFILE = RoleProfile(
    id="product_manager",
    display_name="Product Manager",
    title_include=_TITLE_INCLUDE,
    title_exclude=_TITLE_EXCLUDE,
)
