"""Domains router for managing user domain expertise.

Provides endpoints for listing available domains and managing
user's domain expertise settings for job matching.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.database.db import SessionLocal
from src.database.models import Resume

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to domain expertise data
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOMAIN_EXPERTISE_PATH = PROJECT_ROOT / "data" / "domain_expertise.json"


class DomainInfo(BaseModel):
    """Information about a single domain."""
    key: str
    name: str
    description: str


class DomainCategory(BaseModel):
    """A category of domains (e.g., industries, platforms)."""
    name: str
    domains: List[DomainInfo]


class AvailableDomainsResponse(BaseModel):
    """Response for available domains endpoint."""
    categories: Dict[str, List[DomainInfo]]


class UserDomainsResponse(BaseModel):
    """Response for user domains endpoint."""
    domains: List[str]


class UpdateDomainsRequest(BaseModel):
    """Request body for updating user domains."""
    domains: List[str]


def _load_domain_expertise() -> Dict[str, Any]:
    """Load domain expertise data from JSON file."""
    if not DOMAIN_EXPERTISE_PATH.exists():
        logger.warning(f"Domain expertise file not found: {DOMAIN_EXPERTISE_PATH}")
        return {"domains": {}}

    try:
        with open(DOMAIN_EXPERTISE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading domain expertise: {e}")
        return {"domains": {}}


def _get_all_valid_domain_keys() -> set:
    """Get set of all valid domain keys."""
    data = _load_domain_expertise()
    valid_keys = set()
    for category_domains in data.get("domains", {}).values():
        valid_keys.update(category_domains.keys())
    return valid_keys


def _format_domain_name(key: str) -> str:
    """Convert domain key to display name."""
    # Handle special cases
    special_names = {
        "b2b": "B2B",
        "b2b_saas": "B2B SaaS",
        "ai_ml": "AI/ML",
        "ar_vr": "AR/VR",
        "iot": "IoT",
        "hr_tech": "HR Tech",
    }
    if key in special_names:
        return special_names[key]

    # Default: title case with underscores to spaces
    return key.replace('_', ' ').title()


@router.get("/available", response_model=AvailableDomainsResponse)
async def get_available_domains():
    """Get all available domains organized by category.

    Returns domains from data/domain_expertise.json organized into
    industries, platforms, and technologies categories.
    """
    data = _load_domain_expertise()
    domains_data = data.get("domains", {})

    categories = {}

    for category_key, category_domains in domains_data.items():
        domain_list = []
        for domain_key, domain_info in category_domains.items():
            domain_list.append(DomainInfo(
                key=domain_key,
                name=_format_domain_name(domain_key),
                description=domain_info.get("description", "")
            ))
        # Sort alphabetically by name
        domain_list.sort(key=lambda d: d.name)
        categories[category_key] = domain_list

    return AvailableDomainsResponse(categories=categories)


@router.get("/user", response_model=UserDomainsResponse)
async def get_user_domains():
    """Get the current user's domain expertise.

    Returns the domains stored in the most recent Resume record.
    """
    session = SessionLocal()
    try:
        resume = session.query(Resume).order_by(Resume.updated_at.desc()).first()

        if not resume:
            return UserDomainsResponse(domains=[])

        return UserDomainsResponse(domains=resume.domains or [])
    finally:
        session.close()


@router.put("/user", response_model=UserDomainsResponse)
async def update_user_domains(request: UpdateDomainsRequest):
    """Update the current user's domain expertise.

    Validates that all provided domains exist in the valid domain list,
    then updates the most recent Resume record.
    """
    # Validate domains
    valid_keys = _get_all_valid_domain_keys()
    invalid_domains = [d for d in request.domains if d not in valid_keys]

    if invalid_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain keys: {', '.join(invalid_domains)}. Use GET /available to see valid domains."
        )

    session = SessionLocal()
    try:
        resume = session.query(Resume).order_by(Resume.updated_at.desc()).first()

        if not resume:
            raise HTTPException(
                status_code=404,
                detail="No resume found. Please upload a resume first."
            )

        # Update domains (deduplicate and sort for consistency)
        resume.domains = sorted(list(set(request.domains)))
        session.commit()

        logger.info(f"Updated user domains to: {resume.domains}")

        return UserDomainsResponse(domains=resume.domains)
    finally:
        session.close()
