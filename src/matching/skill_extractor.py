"""Extract skills from job description text.

This module provides skill extraction from job descriptions using a curated
dictionary of ~180 skills across 7 categories. It also supports skill
relationships loaded from a JSON config file for enhanced matching.

Key Functions:
    extract_skills_from_description(): Extract skills from text
    get_related_skills(): Get related skills for a given skill
    load_skill_relationships(): Load relationships from JSON config

Skill Relationships:
    Related skills are defined in data/skill_relationships.json and can be
    edited without code changes. Related skills receive partial credit
    (default 0.7x) during matching.
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Comprehensive skill dictionary organized by category
# Skills are stored in lowercase for matching
SKILL_DICTIONARY: Dict[str, List[str]] = {
    "product_management": [
        "product management",
        "product manager",
        "data product management",
        "data product manager",
        "product strategy",
        "product roadmap",
        "roadmap",
        "product lifecycle",
        "product development",
        "product discovery",
        "product vision",
        "product owner",
        "prd",
        "product requirements",
        "requirements document",
        "user stories",
        "backlog",
        "backlog management",
        "prioritization",
        "feature prioritization",
        "mvp",
        "minimum viable product",
        "go-to-market",
        "gtm",
        "product launch",
        "beta testing",
        "user acceptance testing",
        "uat",
    ],
    "metrics_analytics": [
        "metrics",
        "kpis",
        "okrs",
        "analytics",
        "data analysis",
        "data-driven",
        "a/b testing",
        "ab testing",
        "experimentation",
        "hypothesis testing",
        "user research",
        "customer research",
        "market research",
        "competitive analysis",
        "customer insights",
        "product analytics",
        "funnel analysis",
        "cohort analysis",
        "retention analysis",
        "conversion rate",
        "nps",
        "customer satisfaction",
    ],
    "technical": [
        "sql",
        "python",
        "javascript",
        "java",
        "api",
        "apis",
        "rest api",
        "graphql",
        "microservices",
        "architecture",
        "technical architecture",
        "system design",
        "backend",
        "frontend",
        "full stack",
        "cloud",
        "aws",
        "azure",
        "gcp",
        "google cloud",
        "database",
        "data warehouse",
        "etl",
        "data pipeline",
        "machine learning",
        "ml",
        "artificial intelligence",
        "ai",
        "deep learning",
        "nlp",
        "natural language processing",
        "computer vision",
        "data science",
        "big data",
        "spark",
        "hadoop",
        "tableau",
        "power bi",
        "looker",
        "amplitude",
        "mixpanel",
        "segment",
    ],
    "methodologies": [
        "agile",
        "scrum",
        "kanban",
        "lean",
        "waterfall",
        "sprint",
        "sprint planning",
        "retrospective",
        "stand-up",
        "jira",
        "confluence",
        "asana",
        "trello",
        "notion",
        "design thinking",
        "user-centered design",
        "ux",
        "user experience",
        "ui",
        "user interface",
        "design sprint",
        "rapid prototyping",
        "wireframing",
        "figma",
        "sketch",
    ],
    "business": [
        "b2b",
        "b2c",
        "saas",
        "enterprise",
        "smb",
        "marketplace",
        "platform",
        "e-commerce",
        "ecommerce",
        "fintech",
        "healthtech",
        "edtech",
        "martech",
        "adtech",
        "revenue",
        "monetization",
        "pricing",
        "business model",
        "unit economics",
        "p&l",
        "profit and loss",
        "roi",
        "business case",
        "market sizing",
        "tam",
        "sam",
        "som",
    ],
    "collaboration": [
        "cross-functional",
        "cross functional",
        "stakeholder",
        "stakeholder management",
        "stakeholder alignment",
        "executive",
        "c-suite",
        "leadership",
        "team leadership",
        "mentoring",
        "coaching",
        "collaboration",
        "communication",
        "presentation",
        "storytelling",
        "influence",
        "negotiation",
        "conflict resolution",
        "alignment",
        "consensus building",
    ],
    "engineering_partnership": [
        "engineering",
        "engineering team",
        "development team",
        "technical team",
        "data science team",
        "design team",
        "research team",
        "marketing team",
        "sales team",
        "customer success",
        "support team",
        "operations",
        "devops",
        "qa",
        "quality assurance",
        "testing",
        "release management",
        "deployment",
        "ci/cd",
    ],
}

# Flatten all skills into a single set for quick lookup
ALL_SKILLS: Set[str] = set()
for category_skills in SKILL_DICTIONARY.values():
    ALL_SKILLS.update(category_skills)


def extract_skills_from_description(description: str) -> List[str]:
    """Extract skills from job description text.

    Args:
        description: Job description text

    Returns:
        List of unique skills found in the description
    """
    if not description:
        return []

    # Normalize text for matching
    text_lower = description.lower()

    # Track found skills (use set to avoid duplicates)
    found_skills: Set[str] = set()

    # Search for each skill in the text
    for skill in ALL_SKILLS:
        # Use word boundary matching to avoid partial matches
        # e.g., "api" shouldn't match "capital"
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            # Store the skill in title case for consistency
            found_skills.add(skill.title())

    # Sort for consistent ordering
    return sorted(found_skills)


def extract_skills_by_category(description: str) -> Dict[str, List[str]]:
    """Extract skills from job description, organized by category.

    Args:
        description: Job description text

    Returns:
        Dictionary mapping category names to lists of found skills
    """
    if not description:
        return {}

    text_lower = description.lower()
    result: Dict[str, List[str]] = {}

    for category, skills in SKILL_DICTIONARY.items():
        found = []
        for skill in skills:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found.append(skill.title())
        if found:
            result[category] = sorted(found)

    return result


def get_skill_count() -> int:
    """Return total number of skills in the dictionary."""
    return len(ALL_SKILLS)


def add_custom_skills(skills: List[str]) -> None:
    """Add custom skills to the dictionary.

    Args:
        skills: List of skill strings to add
    """
    for skill in skills:
        ALL_SKILLS.add(skill.lower())


# ============================================================================
# Skill Relationships Support
# ============================================================================

# Cache for loaded skill relationships
_skill_relationships_cache: Optional[Dict] = None
_related_skill_weight: float = 0.7


def _get_relationships_file_path() -> Path:
    """Get the path to the skill relationships JSON file."""
    # Look for file relative to project root
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent  # src/matching -> src -> project root
    return project_root / "data" / "skill_relationships.json"


def load_skill_relationships(force_reload: bool = False) -> Dict:
    """Load skill relationships from JSON config file.

    Relationships are cached after first load for performance.

    Args:
        force_reload: If True, reload from file even if cached

    Returns:
        Dictionary with relationship data, or empty dict if file not found
    """
    global _skill_relationships_cache, _related_skill_weight

    if _skill_relationships_cache is not None and not force_reload:
        return _skill_relationships_cache

    relationships_path = _get_relationships_file_path()

    if not relationships_path.exists():
        logger.warning(f"Skill relationships file not found: {relationships_path}")
        _skill_relationships_cache = {}
        return _skill_relationships_cache

    try:
        with open(relationships_path, 'r') as f:
            data = json.load(f)

        # Extract config
        config = data.get("config", {})
        _related_skill_weight = config.get("related_skill_weight", 0.7)

        # Flatten relationships from all categories into a single lookup dict
        # Convert all keys to lowercase for case-insensitive matching
        flat_relationships: Dict[str, List[str]] = {}
        relationships = data.get("relationships", {})

        for category, skills in relationships.items():
            for skill, related in skills.items():
                skill_lower = skill.lower()
                # Merge if skill already exists from another category
                if skill_lower in flat_relationships:
                    existing = set(flat_relationships[skill_lower])
                    existing.update([r.lower() for r in related])
                    flat_relationships[skill_lower] = list(existing)
                else:
                    flat_relationships[skill_lower] = [r.lower() for r in related]

        _skill_relationships_cache = flat_relationships
        logger.info(f"Loaded {len(flat_relationships)} skill relationships from {relationships_path}")
        return _skill_relationships_cache

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing skill relationships JSON: {e}")
        _skill_relationships_cache = {}
        return _skill_relationships_cache
    except Exception as e:
        logger.error(f"Error loading skill relationships: {e}")
        _skill_relationships_cache = {}
        return _skill_relationships_cache


def get_related_skills(skill: str) -> List[str]:
    """Get related skills for a given skill.

    Args:
        skill: The skill to find relationships for

    Returns:
        List of related skill names (lowercase), or empty list if none found
    """
    relationships = load_skill_relationships()
    skill_lower = skill.lower()
    return relationships.get(skill_lower, [])


def get_related_skill_weight() -> float:
    """Get the weight multiplier for related skill matches.

    Returns:
        Weight multiplier (default 0.7, configurable in JSON)
    """
    # Ensure relationships are loaded to get the weight
    load_skill_relationships()
    return _related_skill_weight


def is_related_skill(skill1: str, skill2: str) -> bool:
    """Check if two skills are related.

    Args:
        skill1: First skill
        skill2: Second skill

    Returns:
        True if skills are related (in either direction)
    """
    skill1_lower = skill1.lower()
    skill2_lower = skill2.lower()

    # Check both directions
    related_to_skill1 = get_related_skills(skill1_lower)
    if skill2_lower in related_to_skill1:
        return True

    related_to_skill2 = get_related_skills(skill2_lower)
    if skill1_lower in related_to_skill2:
        return True

    return False


def get_skill_with_relationships(skill: str) -> Tuple[str, List[str]]:
    """Get a skill and all its related skills.

    Useful for expanding a skill search to include related terms.

    Args:
        skill: The skill to expand

    Returns:
        Tuple of (original skill, list of related skills)
    """
    return (skill, get_related_skills(skill))


def extract_salary_from_description(description: str) -> Optional[str]:
    """Extract salary information from job description text.

    Looks for common salary patterns and returns a normalized string representation.
    Supports annual salaries (40K-500K range) and hourly rates ($15-$300/hr).

    Args:
        description: Job description text

    Returns:
        Salary string (e.g., "$120K-$150K", "$95,000", "$60-$70/hr") or None if not found

    Examples:
        >>> extract_salary_from_description("Salary: $120,000 - $150,000 per year")
        "$120,000-$150,000"
        >>> extract_salary_from_description("Compensation: 80K-100K")
        "$80K-$100K"
        >>> extract_salary_from_description("Rate: $60.00/hr - $70.00/hr")
        "$60-$70/hr"
        >>> extract_salary_from_description("No salary listed")
        None
    """
    if not description:
        return None

    # --- Hourly rate patterns (checked first to avoid misclassification) ---
    # Matches /hr, /hour, /hrs, /hours (with optional space before slash)
    _HR = r'/\s*(?:hr|hour|hrs|hours)'

    hourly_patterns = [
        # CA$/USD$ prefix hourly ranges: CA$75.00/hr - CA$85.00/hr
        (r'(CA|US)\$\s*(\d+(?:\.\d+)?)\s*' + _HR + r'\s*[-–to]+\s*(?:(?:CA|US)\$\s*)?(\d+(?:\.\d+)?)\s*' + _HR,
         'ca_hourly_range'),
        # Plain hourly ranges: $60/hr - $70/hr, $40–$80 /hour
        (r'\$\s*(\d+(?:\.\d+)?)\s*' + _HR + r'\s*[-–to]+\s*\$?\s*(\d+(?:\.\d+)?)\s*' + _HR,
         'plain_hourly_range'),
        # Plain range where only the second value has /hr: $40 - $80/hr
        (r'\$\s*(\d+(?:\.\d+)?)\s*[-–to]+\s*\$?\s*(\d+(?:\.\d+)?)\s*' + _HR,
         'plain_hourly_range'),
        # Single CA$/USD$ hourly: CA$75/hr
        (r'(CA|US)\$\s*(\d+(?:\.\d+)?)\s*' + _HR,
         'ca_hourly_single'),
        # Single plain hourly: $75/hr
        (r'\$\s*(\d+(?:\.\d+)?)\s*' + _HR,
         'plain_hourly_single'),
    ]

    for pattern, kind in hourly_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if not match:
            continue
        try:
            if kind == 'ca_hourly_range':
                prefix, r1, r2 = match.group(1), match.group(2), match.group(3)
                num1, num2 = float(r1), float(r2)
                if 15 <= num1 <= 300 and 15 <= num2 <= 300:
                    return f"{prefix}${int(num1)}-${int(num2)}/hr"
            elif kind == 'plain_hourly_range':
                num1, num2 = float(match.group(1)), float(match.group(2))
                if 15 <= num1 <= 300 and 15 <= num2 <= 300:
                    return f"${int(num1)}-${int(num2)}/hr"
            elif kind == 'ca_hourly_single':
                prefix, num1 = match.group(1), float(match.group(2))
                if 15 <= num1 <= 300:
                    return f"{prefix}${int(num1)}/hr"
            elif kind == 'plain_hourly_single':
                num1 = float(match.group(1))
                if 15 <= num1 <= 300:
                    return f"${int(num1)}/hr"
        except (ValueError, IndexError):
            continue

    # --- Annual salary patterns ---
    # Priority order: ranges first, then single values.
    # Each tuple is (pattern, is_range, has_currency_prefix).
    annual_patterns = [
        # USD$/CA$/CAD$ prefix ranges with optional "per year" between numbers:
        #   USD$190,000 per year - USD$211,000 per year
        #   CA$120,000 - CA$150,000
        (r'(?:USD|CAD|CA)\$\s*(\d{2,3},?\d{3})(?:\.\d+)?(?:\s*(?:per\s+year|annually|/yr|/year))?\s*[-–to]+\s*(?:(?:USD|CAD|CA)\$\s*)?(\d{2,3},?\d{3})(?:\.\d+)?',
         True, False),
        # CAD/USD (space, no $) ranges: CAD 120,000 - 150,000
        (r'(?:CAD|USD)\s+(\d{2,3},?\d{3})(?:\.\d+)?\s*[-–to]+\s*(\d{2,3},?\d{3})(?:\.\d+)?',
         True, False),
        # Plain $ range with optional "per year" between numbers:
        #   $120,000 per year - $150,000 per year  or  $120,000 - $150,000
        (r'\$\s*(\d{2,3},?\d{3})(?:\.\d+)?(?:\s*(?:per\s+year|annually|/yr|/year))?\s*[-–to]+\s*\$?\s*(\d{2,3},?\d{3})(?:\.\d+)?',
         True, False),
        # "and" as range separator: between $160,360 and $240,540
        (r'\$\s*(\d{2,3},?\d{3})(?:\.\d+)?\s+and\s+\$?\s*(\d{2,3},?\d{3})(?:\.\d+)?',
         True, False),
        # K ranges: $120K - $150K, $120K-$150K
        (r'\$\s*(\d{2,3})[kK]\s*[-–to]+\s*\$?\s*(\d{2,3})[kK]',
         True, False),
        # Bare K ranges: 120K-150K
        (r'(\d{2,3})[kK]\s*[-–to]+\s*(\d{2,3})[kK]',
         True, False),
        # USD$/CA$/CAD$ single values: USD$190,000
        (r'(?:USD|CAD|CA)\$\s*(\d{2,3},?\d{3})(?:\.\d+)?(?:\s*(?:per\s+year|annually|/yr|/year))?',
         False, False),
        # CAD/USD (space) single values: CAD 120,000
        (r'(?:CAD|USD)\s+(\d{2,3},?\d{3})(?:\.\d+)?',
         False, False),
        # Plain $ single: $120,000
        (r'\$\s*(\d{2,3},?\d{3})(?:\.\d+)?(?:\s*(?:per\s+year|annually|/yr|/year))?',
         False, False),
        # K single: $120K
        (r'\$\s*(\d{2,3})[kK]',
         False, False),
    ]

    for pattern, is_range, _ in annual_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if not match:
            continue
        try:
            num1_str = match.group(1).replace(',', '')
            num1 = int(float(num1_str))

            if num1 < 1000:  # K format (e.g., 120 → 120K)
                if num1 < 40 or num1 > 500:
                    continue
            else:  # Full dollar amount
                if num1 < 40000 or num1 > 500000:
                    continue

            if is_range:
                num2_str = match.group(2).replace(',', '')
                num2 = int(float(num2_str))
                if num1 < 1000:
                    if num2 < 40 or num2 > 500:
                        continue
                    return f"${num1}K-${num2}K"
                else:
                    if num2 < 40000 or num2 > 500000:
                        continue
                    return f"${num1:,}-${num2:,}"
            else:
                if num1 < 1000:
                    return f"${num1}K"
                else:
                    return f"${num1:,}"

        except (ValueError, IndexError):
            continue

    return None


# ============================================================================
# Domain Expertise Extraction
# ============================================================================

# Cache for loaded domain expertise data
_domain_expertise_cache: Optional[Dict] = None


def _get_domain_expertise_file_path() -> Path:
    """Get the path to the domain expertise JSON file."""
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    return project_root / "data" / "domain_expertise.json"


def load_domain_expertise(force_reload: bool = False) -> Dict:
    """Load domain expertise dictionary from JSON config file.

    Args:
        force_reload: If True, reload from file even if cached

    Returns:
        Dictionary with domain expertise data, or empty dict if file not found
    """
    global _domain_expertise_cache

    if _domain_expertise_cache is not None and not force_reload:
        return _domain_expertise_cache

    expertise_path = _get_domain_expertise_file_path()

    if not expertise_path.exists():
        logger.warning(f"Domain expertise file not found: {expertise_path}")
        _domain_expertise_cache = {"config": {}, "domains": {}}
        return _domain_expertise_cache

    try:
        with open(expertise_path, 'r') as f:
            data = json.load(f)

        _domain_expertise_cache = data
        domain_count = sum(len(cat) for cat in data.get("domains", {}).values())
        logger.info(f"Loaded {domain_count} domain definitions from {expertise_path}")
        return _domain_expertise_cache

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing domain expertise JSON: {e}")
        _domain_expertise_cache = {"config": {}, "domains": {}}
        return _domain_expertise_cache
    except Exception as e:
        logger.error(f"Error loading domain expertise: {e}")
        _domain_expertise_cache = {"config": {}, "domains": {}}
        return _domain_expertise_cache


def extract_domain_requirements(description: str) -> Dict[str, List[str]]:
    """Extract domain expertise requirements from job description.

    Identifies industries, platforms, and technologies mentioned in the job
    description and categorizes them as required or preferred based on
    surrounding context.

    Args:
        description: Job description text

    Returns:
        Dictionary with keys:
            - 'required': List of domain names that appear to be required
            - 'preferred': List of domain names that are nice-to-have
            - 'all': List of all domains mentioned (for backward compatibility)

    Example:
        >>> result = extract_domain_requirements("Must have ecommerce experience. Shopify knowledge is a plus.")
        >>> result['required']
        ['ecommerce']
        >>> result['preferred']
        ['shopify']
    """
    if not description:
        return {'required': [], 'preferred': [], 'all': []}

    expertise_data = load_domain_expertise()
    config = expertise_data.get("config", {})
    domains = expertise_data.get("domains", {})

    required_keywords = config.get("required_keywords", [
        "must have", "required", "essential", "mandatory",
        "need experience in", "expertise in", "background in"
    ])
    preferred_keywords = config.get("preferred_keywords", [
        "nice to have", "preferred", "bonus", "ideally", "plus if you have"
    ])

    text_lower = description.lower()

    found_domains: Dict[str, str] = {}  # domain_name -> 'required' or 'preferred'

    # Search through all domain categories
    for category, category_domains in domains.items():
        for domain_name, domain_data in category_domains.items():
            keywords = domain_data.get("keywords", [])

            for keyword in keywords:
                keyword_lower = keyword.lower()
                # Use word boundary matching
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                match = re.search(pattern, text_lower)

                if match:
                    # Check context around the match to determine if required or preferred
                    start_pos = max(0, match.start() - 100)
                    end_pos = min(len(text_lower), match.end() + 50)
                    context = text_lower[start_pos:end_pos]

                    # Determine requirement level
                    is_required = any(req in context for req in required_keywords)
                    is_preferred = any(pref in context for pref in preferred_keywords)

                    # If already found, don't downgrade from required to preferred
                    if domain_name in found_domains:
                        if found_domains[domain_name] == 'required':
                            continue
                        elif is_required:
                            found_domains[domain_name] = 'required'
                    else:
                        if is_required:
                            found_domains[domain_name] = 'required'
                        elif is_preferred:
                            found_domains[domain_name] = 'preferred'
                        else:
                            # Default to required if mentioned without context
                            found_domains[domain_name] = 'required'

                    break  # Found this domain, move to next

    # Build result
    required = [d for d, level in found_domains.items() if level == 'required']
    preferred = [d for d, level in found_domains.items() if level == 'preferred']

    return {
        'required': sorted(required),
        'preferred': sorted(preferred),
        'all': sorted(found_domains.keys())
    }


def get_domain_display_name(domain_key: str) -> str:
    """Get human-readable display name for a domain.

    Args:
        domain_key: Internal domain key (e.g., 'headless_cms')

    Returns:
        Display name (e.g., 'Headless CMS')
    """
    expertise_data = load_domain_expertise()
    domains = expertise_data.get("domains", {})

    for category_domains in domains.values():
        if domain_key in category_domains:
            # Use description if available, otherwise format the key
            return category_domains[domain_key].get(
                "description",
                domain_key.replace('_', ' ').title()
            )

    # Fallback: format the key nicely
    return domain_key.replace('_', ' ').title()


def match_domains(job_domains: List[str], resume_domains: List[str]) -> Dict:
    """Match job domain requirements against resume domains.

    Args:
        job_domains: List of domains required by the job
        resume_domains: List of domains the candidate has experience in

    Returns:
        Dictionary with:
            - 'matched': List of domains that match
            - 'missing': List of required domains candidate lacks
            - 'match_ratio': Float 0-1 indicating match percentage
    """
    if not job_domains:
        return {'matched': [], 'missing': [], 'match_ratio': 1.0}

    # Normalize for comparison
    job_set = {d.lower() for d in job_domains}
    resume_set = {d.lower() for d in resume_domains}

    matched = list(job_set & resume_set)
    missing = list(job_set - resume_set)

    match_ratio = len(matched) / len(job_set) if job_set else 1.0

    return {
        'matched': sorted(matched),
        'missing': sorted(missing),
        'match_ratio': match_ratio
    }
