#!/usr/bin/env python3
"""3-way enrichment comparison: Original (3x Gemini) vs 2.0-flash Combined vs 2.5-flash Combined.

Pulls jobs from the database, runs all three approaches for each job, and
prints a side-by-side comparison table at the end.

Approaches:
  1. Original: 3 separate Gemini 2.0-flash calls (domains, summary, requirements)
  2. Gemini 2.0-flash Combined: 1 combined call with same model
  3. Gemini 2.5-flash Combined: 1 combined call with newer model

Usage:
    ./venv/bin/python scripts/test_combined_enrichment.py
    ./venv/bin/python scripts/test_combined_enrichment.py --jobs 10
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_config
from src.database.db import SessionLocal
from src.database.models import JobPosting
from src.integrations.gemini_client import (
    GeminiDomainExtractor,
    GeminiRequirementsExtractor,
    VALID_DOMAINS,
    _rate_limiter,
    clean_json_text,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Combined prompt ────────────────────────────────────────────────────────

COMBINED_ENRICHMENT_PROMPT = """Analyze this job posting and provide THREE outputs in a single JSON response.

**Company:** {company}
**Job Title:** {title}

**Job Description:**
{description}

---

Provide the following in ONE JSON response:

### 1. DOMAINS
Identify industry domains and technology platforms REQUIRED or strongly preferred.
- Only include domains explicitly required or strongly emphasized
- Do NOT include domains from incidental mentions (e.g., "healthcare benefits" ≠ healthcare industry)
- Consider the company's industry first, then specific role requirements
- Include PLATFORM domains (salesforce, atlassian, stripe, etc.) if they are tools required for the role
- Include TECHNOLOGY domains (ai_ml, data_engineering, devops, etc.) if the role involves working with those technologies

**Valid domains:**
Industries: ecommerce, fintech, banking, investment_management, asset_management, financial_services, b2b, b2b_saas, healthcare, edtech, adtech, martech, logistics, real_estate, gaming, media, cybersecurity, hr_tech, legal_tech, construction, travel, automotive, agriculture, energy, government, nonprofit
Platforms: salesforce, shopify, sap, oracle, workday, adobe, hubspot, stripe, twilio, zendesk, servicenow, atlassian, snowflake, databricks
Technologies: headless_cms, composable, blockchain, ai_ml, data_engineering, devops, mobile, iot, ar_vr, voice

### 2. SUMMARY
Write a 2-3 sentence summary (under 50 words):
- Focus on core responsibilities, key requirements, and what makes this role unique
- Be specific, avoid generic phrases
- Do NOT start with "This role", "The candidate", or repeat the job title
- Write in natural prose, no bullet points

### 3. REQUIREMENTS
Extract structured requirements:
- Distinguish MUST-HAVE vs NICE-TO-HAVE skills
- For each skill: name, context (how it's used), level (beginner/intermediate/advanced/expert), years (null if unspecified)
- Identify seniority level, required/preferred domains, role focus
- Keep key_responsibilities to top 5-7 items

**Response format (JSON only, no markdown):**
{{
  "domains": {{
    "domains": ["domain1", "domain2"],
    "reasoning": "Brief explanation"
  }},
  "summary": "The 2-3 sentence summary text here.",
  "requirements": {{
    "must_have_skills": [
      {{"name": "Python", "context": "for backend development", "level": "advanced", "years": 3}}
    ],
    "nice_to_have_skills": [
      {{"name": "Kubernetes", "context": null, "level": "intermediate", "years": null}}
    ],
    "min_years": 5,
    "max_years": 10,
    "seniority_level": "senior",
    "required_domains": ["fintech"],
    "preferred_domains": ["payments"],
    "role_focus": "hybrid",
    "key_responsibilities": ["Lead product roadmap", "Partner with engineering"]
  }}
}}

Use null for unknown values. If no specific domains are required, use an empty list.
Valid seniority levels: entry, mid, senior, staff, principal, director
Valid role focus: technical, strategic, hybrid"""


# ── LLM Backends ──────────────────────────────────────────────────────────

def call_gemini_combined(prompt: str, config, model_override: str = None) -> str:
    """Call Gemini API with the combined prompt, return raw response text."""
    import google.generativeai as genai
    from google.generativeai import types

    model_name = model_override or config.get("gemini.extractor.model", "gemini-2.0-flash")
    api_key = config.get("gemini.api_key")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    response = _rate_limiter.call_with_retry(
        model.generate_content,
        prompt,
        generation_config=types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=1500,
            response_mime_type="application/json",
        ),
    )

    if response.candidates and response.candidates[0].content.parts:
        try:
            return response.text or ""
        except ValueError:
            parts = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    parts.append(part.text)
            return "".join(parts)
    return ""


# ── Original 3-call approach ──────────────────────────────────────────────

def original_extract(
    description: str,
    title: str,
    company: str,
    extractor: GeminiDomainExtractor,
    req_extractor: GeminiRequirementsExtractor,
) -> Dict:
    """Run the original 3 separate Gemini calls."""
    result = {}
    calls = 0

    t0 = time.time()

    # 1. Domain extraction
    domain_result = extractor.extract_domains(
        description=description, company=company, title=title
    )
    calls += 1
    result["domains"] = domain_result.get("domains", [])
    result["domain_reasoning"] = domain_result.get("reasoning", "")

    # 2. Summary
    summary = extractor.summarize_job(
        description=description, company=company, title=title
    )
    calls += 1
    result["summary"] = summary or ""

    # 3. Requirements
    requirements = req_extractor.extract_requirements(
        description=description, title=title, company=company
    )
    calls += 1
    result["requirements"] = requirements or {}

    result["time_seconds"] = round(time.time() - t0, 2)
    result["api_calls"] = calls
    return result


# ── Combined 1-call approach ──────────────────────────────────────────────

def combined_extract(
    description: str,
    title: str,
    company: str,
    config,
    req_extractor: GeminiRequirementsExtractor,
    model_override: str = None,
) -> Dict:
    """Run the combined single call using Gemini with an optional model override."""
    max_chars = 10000
    desc_truncated = description[:max_chars] + "..." if len(description) > max_chars else description

    prompt = COMBINED_ENRICHMENT_PROMPT.format(
        company=company or "Unknown",
        title=title or "Unknown",
        description=desc_truncated,
    )

    t0 = time.time()

    response_text = call_gemini_combined(prompt, config, model_override=model_override)

    if not response_text:
        elapsed = round(time.time() - t0, 2)
        return {
            "domains": [],
            "domain_reasoning": "No response",
            "summary": "",
            "requirements": {},
            "time_seconds": elapsed,
            "api_calls": 1,
            "error": "No content returned",
        }

    cleaned = clean_json_text(response_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        elapsed = round(time.time() - t0, 2)
        logger.error(f"  JSON parse error: {e}")
        logger.debug(f"  Raw response: {response_text[:500]}")
        return {
            "domains": [],
            "domain_reasoning": "",
            "summary": "",
            "requirements": {},
            "time_seconds": elapsed,
            "api_calls": 1,
            "error": f"JSON parse error: {e}",
        }

    if not isinstance(parsed, dict):
        elapsed = round(time.time() - t0, 2)
        return {
            "domains": [],
            "domain_reasoning": "",
            "summary": "",
            "requirements": {},
            "time_seconds": elapsed,
            "api_calls": 1,
            "error": f"Expected dict, got {type(parsed).__name__}",
        }

    # Extract domains
    domain_section = parsed.get("domains", {})
    if isinstance(domain_section, dict):
        raw_domains = domain_section.get("domains", [])
        domain_reasoning = domain_section.get("reasoning", "")
    elif isinstance(domain_section, list):
        raw_domains = domain_section
        domain_reasoning = ""
    else:
        raw_domains = []
        domain_reasoning = ""

    valid_domains = [d for d in (raw_domains or []) if d in VALID_DOMAINS]

    # Extract summary
    summary = parsed.get("summary", "")
    if isinstance(summary, str):
        summary = summary.strip()
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]
    else:
        summary = ""

    # Extract and normalize requirements
    requirements_raw = parsed.get("requirements", {})
    if requirements_raw and isinstance(requirements_raw, dict):
        requirements = req_extractor._normalize_result(requirements_raw)
        requirements["extraction_model"] = model_override or "gemini-default"
        requirements["extraction_timestamp"] = datetime.utcnow().isoformat()
    else:
        requirements = {}

    elapsed = round(time.time() - t0, 2)
    return {
        "domains": valid_domains,
        "domain_reasoning": domain_reasoning,
        "summary": summary,
        "requirements": requirements,
        "time_seconds": elapsed,
        "api_calls": 1,
    }


# ── Comparison helpers ────────────────────────────────────────────────────

def compare_domains(original: List[str], combined: List[str]) -> Dict:
    """Compare two domain lists."""
    orig_set = set(original)
    comb_set = set(combined)
    intersection = orig_set & comb_set
    only_orig = orig_set - comb_set
    only_comb = comb_set - orig_set

    if not orig_set and not comb_set:
        match_pct = 100.0
    elif not orig_set or not comb_set:
        match_pct = 0.0 if (orig_set or comb_set) else 100.0
    else:
        match_pct = len(intersection) / len(orig_set | comb_set) * 100

    return {
        "match_pct": round(match_pct, 1),
        "shared": sorted(intersection),
        "only_original": sorted(only_orig),
        "only_combined": sorted(only_comb),
    }


def compare_requirements(original: Dict, combined: Dict) -> Dict:
    """Compare two requirements dicts."""
    if not original and not combined:
        return {"match": "both_empty"}
    if not original or not combined:
        return {"match": "one_empty", "original_empty": not original, "combined_empty": not combined}

    comparisons = {}

    # Seniority
    comparisons["seniority_match"] = original.get("seniority_level") == combined.get("seniority_level")
    comparisons["seniority_original"] = original.get("seniority_level")
    comparisons["seniority_combined"] = combined.get("seniority_level")

    # Role focus
    comparisons["role_focus_match"] = original.get("role_focus") == combined.get("role_focus")
    comparisons["role_focus_original"] = original.get("role_focus")
    comparisons["role_focus_combined"] = combined.get("role_focus")

    # Years
    comparisons["min_years_match"] = original.get("min_years") == combined.get("min_years")
    comparisons["min_years_original"] = original.get("min_years")
    comparisons["min_years_combined"] = combined.get("min_years")

    # Must-have skills (compare by name)
    orig_skills = {s["name"].lower() for s in original.get("must_have_skills", []) if isinstance(s, dict)}
    comb_skills = {s["name"].lower() for s in combined.get("must_have_skills", []) if isinstance(s, dict)}
    skill_intersection = orig_skills & comb_skills
    if orig_skills or comb_skills:
        skill_overlap = len(skill_intersection) / len(orig_skills | comb_skills) * 100
    else:
        skill_overlap = 100.0
    comparisons["must_have_skill_overlap_pct"] = round(skill_overlap, 1)
    comparisons["must_have_only_original"] = sorted(orig_skills - comb_skills)
    comparisons["must_have_only_combined"] = sorted(comb_skills - orig_skills)

    # Required domains
    orig_domains = set(original.get("required_domains") or [])
    comb_domains = set(combined.get("required_domains") or [])
    comparisons["req_domains_match"] = orig_domains == comb_domains
    comparisons["req_domains_original"] = sorted(orig_domains)
    comparisons["req_domains_combined"] = sorted(comb_domains)

    return comparisons


def print_comparison_table(
    results: List[Dict],
    orig_stats: Dict,
    gemini_stats: Dict,
    alt_stats: Dict,
    extractor_model: str,
    alt_model: str,
):
    """Print a formatted side-by-side comparison table."""
    n = len(results)

    # Compute metrics for each approach
    def calc_metrics(key: str) -> Dict:
        domain_matches = [r["comparisons"][key]["domain_match_pct"] for r in results]
        avg_domain = sum(domain_matches) / len(domain_matches) if domain_matches else 0
        perfect_domain = sum(1 for m in domain_matches if m == 100.0)

        seniority_matches = sum(
            1 for r in results
            if isinstance(r["comparisons"][key]["requirements"], dict)
            and r["comparisons"][key]["requirements"].get("seniority_match", False)
        )

        skill_overlaps = [
            r["comparisons"][key]["requirements"]["must_have_skill_overlap_pct"]
            for r in results
            if isinstance(r["comparisons"][key]["requirements"], dict)
            and "must_have_skill_overlap_pct" in r["comparisons"][key]["requirements"]
        ]
        avg_skill = sum(skill_overlaps) / len(skill_overlaps) if skill_overlaps else 0

        return {
            "avg_domain": avg_domain,
            "perfect_domain": perfect_domain,
            "seniority_matches": seniority_matches,
            "avg_skill": avg_skill,
        }

    gemini_metrics = calc_metrics("gemini_combined")
    alt_metrics = calc_metrics("alt_combined")

    # Truncate model names for column headers
    col3 = alt_model[:15]

    # Table
    header = f"\n{'=' * 78}"
    logger.info(header)
    logger.info("3-WAY COMPARISON TABLE")
    logger.info(f"{'=' * 78}")
    logger.info(f"  Jobs tested: {n}")
    logger.info(f"  Baseline: {extractor_model} (3 separate calls)")
    logger.info(f"{'─' * 78}")

    row_fmt = "  {:<28s} {:>16s} {:>16s} {:>16s}"
    logger.info(row_fmt.format(
        "Metric",
        "Original (3x)",
        f"{extractor_model[:15]} 1x",
        f"{col3} 1x",
    ))
    logger.info(f"  {'─' * 76}")

    # Domain match avg — original is baseline so "—"
    logger.info(row_fmt.format(
        "Domain match avg",
        "— (baseline)",
        f"{gemini_metrics['avg_domain']:.1f}%",
        f"{alt_metrics['avg_domain']:.1f}%",
    ))

    # Perfect domain matches
    logger.info(row_fmt.format(
        "Perfect domain matches",
        "— (baseline)",
        f"{gemini_metrics['perfect_domain']}/{n}",
        f"{alt_metrics['perfect_domain']}/{n}",
    ))

    # Seniority matches
    logger.info(row_fmt.format(
        "Seniority matches",
        "— (baseline)",
        f"{gemini_metrics['seniority_matches']}/{n}",
        f"{alt_metrics['seniority_matches']}/{n}",
    ))

    # Skill overlap avg
    logger.info(row_fmt.format(
        "Skill overlap avg",
        "— (baseline)",
        f"{gemini_metrics['avg_skill']:.1f}%",
        f"{alt_metrics['avg_skill']:.1f}%",
    ))

    logger.info(f"  {'─' * 76}")

    # Total time
    logger.info(row_fmt.format(
        "Total time",
        f"{orig_stats['time']:.1f}s",
        f"{gemini_stats['time']:.1f}s",
        f"{alt_stats['time']:.1f}s",
    ))

    # API calls
    logger.info(row_fmt.format(
        "API calls",
        str(orig_stats["calls"]),
        str(gemini_stats["calls"]),
        str(alt_stats["calls"]),
    ))

    # Errors
    logger.info(row_fmt.format(
        "Errors",
        str(orig_stats["errors"]),
        str(gemini_stats["errors"]),
        str(alt_stats["errors"]),
    ))

    logger.info(f"{'=' * 78}")

    # Speedup
    if orig_stats["time"] > 0:
        if gemini_stats["time"] > 0:
            logger.info(f"  {extractor_model} combined speedup: {orig_stats['time'] / gemini_stats['time']:.1f}x")
        if alt_stats["time"] > 0:
            logger.info(f"  {alt_model} combined speedup: {orig_stats['time'] / alt_stats['time']:.1f}x")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="3-way enrichment comparison")
    parser.add_argument("--jobs", type=int, default=25,
                        help="Number of jobs to test (default: 25)")
    args = parser.parse_args()

    num_jobs = args.jobs

    ALT_MODEL = "gemini-2.5-flash"

    logger.info("=" * 70)
    logger.info("3-Way Enrichment Comparison Test")
    logger.info("  1) Original: Gemini 3x separate calls (baseline)")
    logger.info("  2) Gemini 2.0-flash Combined: 1x combined call (same model)")
    logger.info(f"  3) {ALT_MODEL} Combined: 1x combined call (newer model)")
    logger.info("=" * 70)

    config = get_config()

    # Validate API key
    gemini_key = config.get("gemini.api_key")
    if not gemini_key:
        logger.error("Set gemini.api_key in config.yaml")
        sys.exit(1)

    base_model = config.get("gemini.extractor.model", "gemini-2.0-flash")
    logger.info(f"Baseline model: {base_model}")
    logger.info(f"Alt model: {ALT_MODEL}")

    # Initialize Gemini extractors (always needed for baseline)
    extractor = GeminiDomainExtractor()
    req_extractor = GeminiRequirementsExtractor()

    if not extractor.is_available():
        logger.error("Gemini extractor not available. Check config.")
        sys.exit(1)
    if not req_extractor.is_available():
        logger.error("Gemini requirements extractor not available. Check config.")
        sys.exit(1)

    logger.info(f"Baseline model: {extractor.model_name}")

    # Fetch jobs from the database
    session = SessionLocal()
    try:
        jobs = (
            session.query(JobPosting)
            .filter(JobPosting.description.isnot(None))
            .filter(JobPosting.description != "")
            .order_by(JobPosting.id.desc())
            .limit(num_jobs)
            .all()
        )
        job_data = [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "description": j.description,
            }
            for j in jobs
        ]
    finally:
        session.close()

    logger.info(f"Loaded {len(job_data)} jobs from database")

    if not job_data:
        logger.error("No jobs found in database. Run a search first.")
        sys.exit(1)

    # Run comparisons — all 3 approaches per job
    results = []
    orig_stats = {"time": 0.0, "calls": 0, "errors": 0}
    gemini_stats = {"time": 0.0, "calls": 0, "errors": 0}
    alt_stats = {"time": 0.0, "calls": 0, "errors": 0}

    for i, job in enumerate(job_data):
        logger.info(f"\n{'─' * 60}")
        logger.info(f"[{i+1}/{len(job_data)}] {job['title']} @ {job['company']}")
        logger.info(f"{'─' * 60}")

        # ── 1. Original (3 Gemini calls) ──
        try:
            logger.info("  Running ORIGINAL (3 Gemini calls)...")
            orig = original_extract(
                description=job["description"],
                title=job["title"],
                company=job["company"],
                extractor=extractor,
                req_extractor=req_extractor,
            )
            logger.info(f"  Original: {orig['time_seconds']}s, {orig['api_calls']} calls")
        except Exception as e:
            logger.error(f"  Original failed: {e}")
            orig = {"domains": [], "summary": "", "requirements": {}, "time_seconds": 0, "api_calls": 3, "error": str(e)}
            orig_stats["errors"] += 1

        # ── 2. Gemini 2.0-flash Combined (1 call) ──
        try:
            logger.info(f"  Running {base_model} COMBINED (1 call)...")
            gemini_comb = combined_extract(
                description=job["description"],
                title=job["title"],
                company=job["company"],
                config=config,
                req_extractor=req_extractor,
            )
            logger.info(f"  {base_model} Combined: {gemini_comb['time_seconds']}s, {gemini_comb['api_calls']} calls")
            if gemini_comb.get("error"):
                logger.warning(f"  {base_model} Combined error: {gemini_comb['error']}")
                gemini_stats["errors"] += 1
        except Exception as e:
            logger.error(f"  {base_model} Combined failed: {e}")
            gemini_comb = {"domains": [], "summary": "", "requirements": {}, "time_seconds": 0, "api_calls": 1, "error": str(e)}
            gemini_stats["errors"] += 1

        # ── 3. Alt model Combined (1 call) ──
        try:
            logger.info(f"  Running {ALT_MODEL} COMBINED (1 call)...")
            alt_comb = combined_extract(
                description=job["description"],
                title=job["title"],
                company=job["company"],
                config=config,
                req_extractor=req_extractor,
                model_override=ALT_MODEL,
            )
            logger.info(f"  {ALT_MODEL} Combined: {alt_comb['time_seconds']}s, {alt_comb['api_calls']} calls")
            if alt_comb.get("error"):
                logger.warning(f"  {ALT_MODEL} Combined error: {alt_comb['error']}")
                alt_stats["errors"] += 1
        except Exception as e:
            logger.error(f"  {ALT_MODEL} Combined failed: {e}")
            alt_comb = {"domains": [], "summary": "", "requirements": {}, "time_seconds": 0, "api_calls": 1, "error": str(e)}
            alt_stats["errors"] += 1

        # ── Compare both combined approaches against original ──
        gemini_domain_cmp = compare_domains(orig["domains"], gemini_comb["domains"])
        alt_domain_cmp = compare_domains(orig["domains"], alt_comb["domains"])
        gemini_req_cmp = compare_requirements(orig.get("requirements", {}), gemini_comb.get("requirements", {}))
        alt_req_cmp = compare_requirements(orig.get("requirements", {}), alt_comb.get("requirements", {}))

        result = {
            "job_id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "original": {
                "domains": orig["domains"],
                "summary": orig["summary"][:200] if orig["summary"] else "",
                "requirements_seniority": orig.get("requirements", {}).get("seniority_level"),
                "requirements_min_years": orig.get("requirements", {}).get("min_years"),
                "requirements_must_have_count": len(orig.get("requirements", {}).get("must_have_skills", [])),
                "time_seconds": orig["time_seconds"],
                "api_calls": orig["api_calls"],
            },
            "gemini_combined": {
                "domains": gemini_comb["domains"],
                "summary": gemini_comb["summary"][:200] if gemini_comb["summary"] else "",
                "requirements_seniority": gemini_comb.get("requirements", {}).get("seniority_level"),
                "requirements_min_years": gemini_comb.get("requirements", {}).get("min_years"),
                "requirements_must_have_count": len(gemini_comb.get("requirements", {}).get("must_have_skills", [])),
                "time_seconds": gemini_comb["time_seconds"],
                "api_calls": gemini_comb["api_calls"],
                "error": gemini_comb.get("error"),
            },
            "alt_combined": {
                "model": ALT_MODEL,
                "domains": alt_comb["domains"],
                "summary": alt_comb["summary"][:200] if alt_comb["summary"] else "",
                "requirements_seniority": alt_comb.get("requirements", {}).get("seniority_level"),
                "requirements_min_years": alt_comb.get("requirements", {}).get("min_years"),
                "requirements_must_have_count": len(alt_comb.get("requirements", {}).get("must_have_skills", [])),
                "time_seconds": alt_comb["time_seconds"],
                "api_calls": alt_comb["api_calls"],
                "error": alt_comb.get("error"),
            },
            "comparisons": {
                "gemini_combined": {
                    "domain_match_pct": gemini_domain_cmp["match_pct"],
                    "domain_only_original": gemini_domain_cmp["only_original"],
                    "domain_only_combined": gemini_domain_cmp["only_combined"],
                    "requirements": gemini_req_cmp,
                },
                "alt_combined": {
                    "domain_match_pct": alt_domain_cmp["match_pct"],
                    "domain_only_original": alt_domain_cmp["only_original"],
                    "domain_only_combined": alt_domain_cmp["only_combined"],
                    "requirements": alt_req_cmp,
                },
            },
        }
        results.append(result)

        orig_stats["time"] += orig["time_seconds"]
        orig_stats["calls"] += orig["api_calls"]
        gemini_stats["time"] += gemini_comb["time_seconds"]
        gemini_stats["calls"] += gemini_comb["api_calls"]
        alt_stats["time"] += alt_comb["time_seconds"]
        alt_stats["calls"] += alt_comb["api_calls"]

        # Print quick per-job comparison
        logger.info(f"  Domains vs original: {base_model}={gemini_domain_cmp['match_pct']}% | {ALT_MODEL}={alt_domain_cmp['match_pct']}%")
        logger.info(f"    Original:        {orig['domains']}")
        logger.info(f"    {base_model}: {gemini_comb['domains']}")
        logger.info(f"    {ALT_MODEL}: {alt_comb['domains']}")

        for label, req_cmp in [(base_model, gemini_req_cmp), (ALT_MODEL, alt_req_cmp)]:
            if isinstance(req_cmp, dict) and "seniority_match" in req_cmp:
                logger.info(f"  {label} — Seniority: {'MATCH' if req_cmp['seniority_match'] else 'DIFF'} "
                            f"(orig={req_cmp['seniority_original']}, comb={req_cmp['seniority_combined']}), "
                            f"Skills overlap: {req_cmp['must_have_skill_overlap_pct']}%")

    # ── Print comparison table ────────────────────────────────────────
    print_comparison_table(results, orig_stats, gemini_stats, alt_stats, extractor.model_name, ALT_MODEL)

    # ── Save detailed results to JSON ─────────────────────────────────
    output_path = Path(__file__).parent / "enrichment_comparison_3way.json"

    # Compute summary metrics for JSON
    def calc_summary_metrics(key: str) -> Dict:
        domain_matches = [r["comparisons"][key]["domain_match_pct"] for r in results]
        avg_domain = sum(domain_matches) / len(domain_matches) if domain_matches else 0
        perfect_domain = sum(1 for m in domain_matches if m == 100.0)

        seniority_matches = sum(
            1 for r in results
            if isinstance(r["comparisons"][key]["requirements"], dict)
            and r["comparisons"][key]["requirements"].get("seniority_match", False)
        )

        skill_overlaps = [
            r["comparisons"][key]["requirements"]["must_have_skill_overlap_pct"]
            for r in results
            if isinstance(r["comparisons"][key]["requirements"], dict)
            and "must_have_skill_overlap_pct" in r["comparisons"][key]["requirements"]
        ]
        avg_skill = sum(skill_overlaps) / len(skill_overlaps) if skill_overlaps else 0

        return {
            "avg_domain_match_pct": round(avg_domain, 1),
            "perfect_domain_matches": perfect_domain,
            "seniority_matches": seniority_matches,
            "avg_skill_overlap_pct": round(avg_skill, 1),
        }

    gemini_summary = calc_summary_metrics("gemini_combined")
    alt_summary = calc_summary_metrics("alt_combined")

    with open(output_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "baseline_model": extractor.model_name,
                "gemini_combined_model": base_model,
                "alt_combined_model": ALT_MODEL,
                "jobs_tested": len(results),
                "summary": {
                    "original": {
                        "total_time": round(orig_stats["time"], 1),
                        "total_calls": orig_stats["calls"],
                        "errors": orig_stats["errors"],
                    },
                    "gemini_combined": {
                        **gemini_summary,
                        "total_time": round(gemini_stats["time"], 1),
                        "total_calls": gemini_stats["calls"],
                        "errors": gemini_stats["errors"],
                    },
                    "alt_combined": {
                        "model": ALT_MODEL,
                        **alt_summary,
                        "total_time": round(alt_stats["time"], 1),
                        "total_calls": alt_stats["calls"],
                        "errors": alt_stats["errors"],
                    },
                },
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )
    logger.info(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
