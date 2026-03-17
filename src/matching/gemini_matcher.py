"""Gemini LLM-based job matching for higher accuracy and richer insights.

This module provides AI-powered job matching that:
- Evaluates skill alignment with context awareness
- Assesses experience fit including seniority alignment
- Identifies strengths, concerns, and recommendations
- Provides detailed skill match/gap analysis
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from src.config import get_config
from src.integrations.gemini_client import clean_json_text, get_rate_limiter
from src.matching.requirements import (
    StructuredRequirements,
    GeminiMatchResult,
    SkillMatch,
    SkillGap
)

logger = logging.getLogger(__name__)


def _build_domain_label_map() -> Dict[str, str]:
    """Build a flat key→description map from data/domain_expertise.json."""
    path = Path(__file__).parent.parent.parent / "data" / "domain_expertise.json"
    try:
        with open(path) as f:
            data = json.load(f)
        label_map = {}
        for category in data.get("domains", {}).values():
            for key, info in category.items():
                if isinstance(info, dict) and "description" in info:
                    label_map[key] = info["description"]
        return label_map
    except Exception:
        return {}


_DOMAIN_LABELS: Dict[str, str] = _build_domain_label_map()


def _format_domains(domains: List[str]) -> str:
    """Format domain keys as 'Description (key)' for Gemini prompts.

    E.g. ['financial_services', 'fintech'] →
         'Financial services and capital markets (financial_services), Financial technology and services (fintech)'
    """
    if not domains:
        return "Not specified"
    parts = []
    for key in domains:
        label = _DOMAIN_LABELS.get(key)
        parts.append(f"{label} ({key})" if label else key)
    return ", ".join(parts)

# AI Matching prompt - comprehensive evaluation
AI_MATCH_PROMPT = """You are an expert job matching assistant. Evaluate how well this candidate matches the job requirements.

**CANDIDATE PROFILE:**
Skills: {resume_skills}
Experience: {experience_years} years
Domain Expertise: {resume_domains}
Recent Roles: {recent_roles}

**JOB REQUIREMENTS:**
Title: {job_title}
Company: {company}

Must-Have Skills:
{must_have_skills}

Nice-to-Have Skills:
{nice_to_have_skills}

Experience Required: {required_years}
Seniority Level: {seniority_level}
Required Domains: {required_domains}
Preferred Domains: {preferred_domains}
Key Responsibilities:
{responsibilities}

**SCORING CRITERIA:**
1. Skills Match (40%): How many must-have skills does the candidate have? Partial credit for related/transferable skills.
2. Experience Fit (25%): Is experience level appropriate? Consider both under-qualification AND over-qualification.
3. Seniority Alignment (20%): Does candidate's career stage match the role level?
4. Domain Relevance (15%): Does candidate have relevant industry experience?

**Important Guidelines:**
- A score of 75+ indicates a strong match
- A score of 60-74 indicates a moderate match with some gaps
- A score below 60 indicates significant misalignment
- Be realistic - most candidates won't have every skill
- Consider skill transferability (e.g., "React" skills transfer to "Vue")
- Seniority mismatch (too senior OR too junior) should impact score
- Write all text concisely without "the candidate" or third-person references
- skill_matches is REQUIRED — map every Must-Have and Nice-to-Have skill above to the closest skill in the candidate's profile. A match score above 60 must have at least 3 skill_matches entries.
- For skill_gaps, focus on ACTIONABLE, SPECIFIC skills the candidate could learn:
  * ✅ INCLUDE: Specific tools (e.g., "Kubernetes", "GraphQL"), frameworks, technologies, certifications
  * ✅ INCLUDE: Domain-specific skills (e.g., "Financial Modeling", "Clinical Trials")
  * ❌ EXCLUDE: Overly broad categories (e.g., "Information Technology", "Software Development", "Business")
  * ❌ EXCLUDE: Functional roles the candidate ALREADY has experience in (e.g., if candidate has been a PM for years, don't gap "Product Management")
  * ❌ EXCLUDE: Generic soft skills unless specifically critical

**Response format (JSON only, no markdown):**
{{
  "overall_score": 0-100,
  "skills_score": 0-100,
  "experience_score": 0-100,
  "seniority_fit": 0-100,
  "domain_score": 0-100,
  "skill_matches": [
    {{"job_skill": "Python", "resume_skill": "Python/Django", "confidence": 0.95, "context": "Direct match"}}
  ],
  "skill_gaps": [
    {{"skill": "Kubernetes", "importance": "must_have", "transferable_from": "Docker experience"}}
  ],
  "strengths": ["Strong PM background", "Relevant fintech experience"],
  "concerns": ["Missing cloud certifications", "No team lead experience mentioned"],
  "recommendations": ["Highlight scaling experience", "Mention cross-functional work"],
  "confidence": 0.85,
  "reasoning": "2-3 sentence summary of match quality"
}}
"""

# Simplified prompt for when structured requirements aren't available
AI_MATCH_SIMPLE_PROMPT = """You are an expert job matching assistant. Evaluate how well this candidate matches the job posting.

**CANDIDATE PROFILE:**
Skills: {resume_skills}
Experience: {experience_years} years
Domain Expertise: {resume_domains}

**JOB POSTING:**
Title: {job_title}
Company: {company}
Description:
{description}

**SCORING CRITERIA:**
1. Skills Match (40%): How well do candidate's skills match job requirements?
2. Experience Fit (25%): Is experience level appropriate for this role?
3. Seniority Alignment (20%): Does career stage match the role?
4. Domain Relevance (15%): Does candidate have relevant industry experience?

**Important Guidelines:**
- Write all text concisely without "the candidate" or third-person references
- skill_matches is REQUIRED — scan the job description for specific skills, tools, and technologies, then map each to the closest skill in the candidate's profile listed above. A match score above 60 must have at least 3 skill_matches entries.
- For skill_gaps, focus on ACTIONABLE, SPECIFIC skills the candidate could learn:
  * ✅ INCLUDE: Specific tools (e.g., "Kubernetes", "GraphQL"), frameworks, technologies, certifications
  * ✅ INCLUDE: Domain-specific skills (e.g., "Financial Modeling", "Clinical Trials")
  * ❌ EXCLUDE: Overly broad categories (e.g., "Information Technology", "Software Development", "Business")
  * ❌ EXCLUDE: Functional roles the candidate ALREADY has experience in (e.g., if candidate has been a PM for years, don't gap "Product Management")
  * ❌ EXCLUDE: Generic soft skills unless specifically critical

**Response format (JSON only, no markdown):**
{{
  "overall_score": 0-100,
  "skills_score": 0-100,
  "experience_score": 0-100,
  "seniority_fit": 0-100,
  "domain_score": 0-100,
  "skill_matches": [{{"job_skill": "SQL", "resume_skill": "SQL", "confidence": 1.0, "context": "Direct match"}}, {{"job_skill": "data analysis", "resume_skill": "Data Modeling", "confidence": 0.8, "context": "Related skill"}}],
  "skill_gaps": [{{"skill": "missing skill", "importance": "must_have|nice_to_have", "transferable_from": "related skill or null"}}],
  "strengths": ["strength 1", "strength 2"],
  "concerns": ["concern 1"],
  "recommendations": ["recommendation 1"],
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence summary"
}}
"""


class GeminiMatcher:
    """AI-powered job matching using Gemini LLM."""

    def __init__(self):
        """Initialize the Gemini matcher."""
        self.config = get_config()
        self.enabled = self.config.get("gemini.enabled", False)
        # Use best reasoning model for matching accuracy
        self.model_name = self.config.get("gemini.matcher.model", "gemini-3-flash")
        # Cheaper model for batch operations
        self.batch_model_name = self.config.get("gemini.matcher.batch_model", "gemini-3.1-flash-lite-preview")
        self.api_key = self.config.get("gemini.api_key")
        self.client = None

        if self.enabled and self.api_key:
            try:
                # Extended timeout for thinking models (gemini-3-*) which can take 30-90s.
                # Configured at client level — generate_content() has no request_options param
                # in google-genai SDK.
                self.client = genai.Client(
                    api_key=self.api_key,
                    http_options=types.HttpOptions(timeout=120_000),  # 120s in ms
                )
                self._rate_limiter = get_rate_limiter(self.model_name)
                self._batch_rate_limiter = get_rate_limiter(self.batch_model_name)
                logger.info(f"GeminiMatcher initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize GeminiMatcher: {e}")
                self.enabled = False

    def is_available(self) -> bool:
        """Check if Gemini matching is available."""
        return self.enabled and self.client is not None

    def match_job(
        self,
        resume_skills: List[str],
        experience_years: float,
        resume_domains: List[str],
        recent_roles: List[str],
        job_title: str,
        company: str,
        job_description: str,
        structured_requirements: Optional[Dict] = None,
        use_batch_model: bool = False
    ) -> Optional[GeminiMatchResult]:
        """Match a job against a resume using AI.

        Args:
            resume_skills: List of candidate skills
            experience_years: Years of experience
            resume_domains: List of domain expertise
            recent_roles: List of recent job titles
            job_title: Target job title
            company: Target company
            job_description: Full job description
            structured_requirements: Pre-extracted requirements (optional)
            use_batch_model: Use faster model for batch operations

        Returns:
            GeminiMatchResult with scores and insights, or None if failed
        """
        if not self.is_available():
            logger.warning("GeminiMatcher not available")
            return None

        model_name = self.batch_model_name if use_batch_model else self.model_name

        # Build prompt based on whether we have structured requirements
        if structured_requirements:
            prompt = self._build_structured_prompt(
                resume_skills=resume_skills,
                experience_years=experience_years,
                resume_domains=resume_domains,
                recent_roles=recent_roles,
                job_title=job_title,
                company=company,
                requirements=structured_requirements
            )
        else:
            prompt = self._build_simple_prompt(
                resume_skills=resume_skills,
                experience_years=experience_years,
                resume_domains=resume_domains,
                job_title=job_title,
                company=company,
                job_description=job_description
            )

        try:
            rate_limiter = self._batch_rate_limiter if use_batch_model else self._rate_limiter
            response = rate_limiter.call_with_retry(
                self.client.models.generate_content,
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low for consistent scoring
                    # max_output_tokens covers thinking + output tokens for gemini-3-* models.
                    # The thinking process consumes ~2000-6000 tokens; the full JSON response
                    # needs ~500-1000 tokens. 8192 reliably provides enough room for both
                    # (2048 was exhausted by thinking alone; 4096 had 70% truncation rate).
                    max_output_tokens=8192,
                    # NOTE: response_mime_type="application/json" intentionally omitted.
                    # Thinking models (gemini-3-*) return empty arrays in constrained JSON mode.
                    # clean_json_text() handles extracting JSON from free-form responses.
                ),
            )

            # Parse response with candidate context for filtering
            result = self._parse_response(response, job_title, recent_roles)
            if result:
                return result

        except Exception as e:
            logger.error(f"GeminiMatcher error for {job_title}: {e}")

        return None

    def _build_structured_prompt(
        self,
        resume_skills: List[str],
        experience_years: float,
        resume_domains: List[str],
        recent_roles: List[str],
        job_title: str,
        company: str,
        requirements: Dict
    ) -> str:
        """Build prompt using structured requirements."""
        # Format must-have skills
        must_have = requirements.get("must_have_skills") or []
        must_have_text = "\n".join([
            f"- {s.get('name', s) if isinstance(s, dict) else s}"
            + (f" ({s.get('context', '')})" if isinstance(s, dict) and s.get('context') else "")
            + (f" [{s.get('level', '')}]" if isinstance(s, dict) and s.get('level') else "")
            for s in must_have
        ]) if must_have else "Not specified"

        # Format nice-to-have skills
        nice_to_have = requirements.get("nice_to_have_skills") or []
        nice_to_have_text = "\n".join([
            f"- {s.get('name', s) if isinstance(s, dict) else s}"
            for s in nice_to_have
        ]) if nice_to_have else "Not specified"

        # Format experience
        min_years = requirements.get("min_years")
        max_years = requirements.get("max_years")
        if min_years and max_years:
            required_years = f"{min_years}-{max_years} years"
        elif min_years:
            required_years = f"{min_years}+ years"
        else:
            required_years = "Not specified"

        # Format responsibilities
        responsibilities = requirements.get("key_responsibilities") or []
        resp_text = "\n".join([f"- {r}" for r in responsibilities[:7]]) if responsibilities else "Not specified"

        return AI_MATCH_PROMPT.format(
            resume_skills=", ".join(resume_skills[:30]),
            experience_years=experience_years,
            resume_domains=_format_domains(resume_domains),
            recent_roles=", ".join(recent_roles[:5]) if recent_roles else "Not specified",
            job_title=job_title,
            company=company,
            must_have_skills=must_have_text,
            nice_to_have_skills=nice_to_have_text,
            required_years=required_years,
            seniority_level=requirements.get("seniority_level", "Not specified"),
            required_domains=", ".join(requirements.get("required_domains") or []) or "Not specified",
            preferred_domains=", ".join(requirements.get("preferred_domains") or []) or "Not specified",
            responsibilities=resp_text
        )

    def _build_simple_prompt(
        self,
        resume_skills: List[str],
        experience_years: float,
        resume_domains: List[str],
        job_title: str,
        company: str,
        job_description: str
    ) -> str:
        """Build prompt when structured requirements aren't available."""
        # Truncate description to save tokens
        max_desc = 6000
        if len(job_description) > max_desc:
            job_description = job_description[:max_desc] + "..."

        return AI_MATCH_SIMPLE_PROMPT.format(
            resume_skills=", ".join(resume_skills[:30]),
            experience_years=experience_years,
            resume_domains=_format_domains(resume_domains),
            job_title=job_title,
            company=company,
            description=job_description
        )

    def _parse_response(
        self,
        response,
        job_title: str,
        candidate_titles: Optional[List[str]] = None
    ) -> Optional[GeminiMatchResult]:
        """Parse Gemini response into GeminiMatchResult.

        Args:
            response: Gemini API response
            job_title: Job title for logging
            candidate_titles: List of candidate's recent job titles for filtering gaps
        """
        # Extract text from response
        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else 'unknown'
            logger.warning(f"Gemini returned no content for {job_title}. Finish reason: {finish_reason}")
            return None

        # Extract text parts only
        text_parts = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text_parts.append(part.text)

        if not text_parts:
            logger.warning(f"Gemini response has no text parts for {job_title}")
            return None

        response_text = "".join(text_parts)

        try:
            cleaned = clean_json_text(response_text)
            result = json.loads(cleaned)

            # Build skill matches
            skill_matches = []
            for m in result.get("skill_matches", []):
                if isinstance(m, dict):
                    skill_matches.append(SkillMatch(
                        job_skill=m.get("job_skill", ""),
                        resume_skill=m.get("resume_skill", ""),
                        confidence=float(m.get("confidence", 0)),
                        context=m.get("context")
                    ))

            # Build skill gaps with post-processing filter
            skill_gaps = []
            for g in result.get("skill_gaps", []):
                if isinstance(g, dict):
                    gap_skill = g.get("skill", "").strip()

                    # Filter out gaps that match candidate's proven functional expertise
                    if candidate_titles and self._is_functional_role_gap(gap_skill, candidate_titles):
                        logger.debug(f"Filtered skill gap '{gap_skill}' - candidate has proven experience")
                        continue

                    skill_gaps.append(SkillGap(
                        skill=gap_skill,
                        importance=g.get("importance", "nice_to_have"),
                        transferable_from=g.get("transferable_from")
                    ))

            # Sanity-check: if key list fields are all empty but overall_score is
            # non-zero, the response was likely truncated by the token budget.
            # Truncated thinking-model responses parse as valid JSON but have
            # empty arrays — the only observable symptom of a token-budget miss.
            strengths = result.get("strengths", [])
            concerns = result.get("concerns", [])
            recommendations = result.get("recommendations", [])
            overall_score = float(result.get("overall_score", 0))
            if overall_score > 0 and not skill_matches and not strengths and not concerns:
                logger.warning(
                    f"Gemini response for '{job_title}' has a non-zero score ({overall_score}) "
                    f"but empty skill_matches/strengths/concerns — possible token-budget truncation. "
                    f"Response length: {len(response_text)} chars. "
                    f"Consider increasing max_output_tokens if this recurs."
                )

            return GeminiMatchResult(
                overall_score=overall_score,
                skills_score=float(result.get("skills_score", 0)),
                experience_score=float(result.get("experience_score", 0)),
                seniority_fit=float(result.get("seniority_fit", 0)),
                domain_score=float(result.get("domain_score", 0)),
                skill_matches=skill_matches,
                skill_gaps=skill_gaps,
                strengths=strengths,
                concerns=concerns,
                recommendations=recommendations,
                confidence=float(result.get("confidence", 0)),
                reasoning=result.get("reasoning", "")
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini match response for {job_title}: {e}")
            logger.debug(f"Response text: {response_text[:500] if response_text else 'EMPTY'}")
            return None
        except Exception as e:
            logger.error(f"Error processing Gemini match for {job_title}: {e}")
            return None

    def _is_functional_role_gap(self, gap_skill: str, candidate_titles: List[str]) -> bool:
        """Check if a skill gap is actually a functional role the candidate already has.
        
        Args:
            gap_skill: The skill identified as a gap
            candidate_titles: List of candidate's recent job titles
            
        Returns:
            True if this gap should be filtered out (candidate has it), False otherwise
        """
        gap_lower = gap_skill.lower()
        
        # Define functional role mappings (gap keyword -> title keywords)
        role_mappings = {
            "product manag": ["product"],
            "software eng": ["engineer", "developer", "software"],
            "data scien": ["data scien"],
            "data engineer": ["data eng"],
            "data analy": ["data analy", "analyst"],
            "machine learning eng": ["ml eng", "machine learning"],
            "devops": ["devops", "sre", "site reliability"],
            "frontend": ["frontend", "front-end", "front end"],
            "backend": ["backend", "back-end", "back end"],
            "full stack": ["full stack", "fullstack"],
            "ui/ux": ["ui/ux", "ux design", "ui design"],
            "graphic design": ["graphic design", "visual design"],
            "marketing": ["marketing"],
            "sales": ["sales"],
            "business analy": ["business analy"],
            "project manag": ["project manag"],
            "program manag": ["program manag"],
            "scrum master": ["scrum master", "agile coach"],
        }
        
        # Check if gap matches any functional role the candidate has
        for gap_keyword, title_keywords in role_mappings.items():
            if gap_keyword in gap_lower:
                # Check if candidate has this role in their titles
                for title in candidate_titles:
                    title_lower = title.lower()
                    if any(keyword in title_lower for keyword in title_keywords):
                        return True  # Filter this gap - candidate has it
        
        return False  # Keep this gap - it's legitimate


def get_gemini_matcher() -> Optional[GeminiMatcher]:
    """Factory function to get a GeminiMatcher instance.

    Returns:
        GeminiMatcher if available, None otherwise
    """
    matcher = GeminiMatcher()
    if matcher.is_available():
        return matcher
    return None
