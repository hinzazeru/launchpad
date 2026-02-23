"""Main matching engine for comparing resumes against job postings.

This module orchestrates the job matching process by combining skills matching
(NLP-based semantic similarity), experience matching (rule-based years comparison),
and domain matching (industry expertise alignment) to produce an overall compatibility score.

Supports two matching modes:
- NLP: Traditional embedding-based matching (faster, free, good accuracy)
- Gemini: AI-powered matching with richer insights (higher accuracy, costs per call)

Score Calculation (NLP mode):
    Overall Score = (Skills × skills_weight) + (Experience × experience_weight) + (Domains × domains_weight)

    Default weights: skills=0.45, experience=0.35, domains=0.20 (configurable in config.yaml).

Key Classes:
    JobMatcher: Main matching orchestrator that supports both NLP and Gemini modes

Key Functions:
    create_job_matcher(): Factory function to create a JobMatcher instance

Usage Example:
    >>> from src.matching.engine import JobMatcher
    >>> from src.database.models import Resume, JobPosting
    >>>
    >>> # NLP mode (default)
    >>> matcher = JobMatcher()
    >>> result = matcher.match_job(resume, job_posting)
    >>>
    >>> # Gemini mode (richer insights)
    >>> matcher = JobMatcher(mode="gemini")
    >>> result = matcher.match_job(resume, job_posting)
    >>> print(f"Match score: {result['overall_score'] * 100}%")
    >>> print(f"Strengths: {result.get('ai_strengths', [])}")
    >>> print(f"Recommendations: {result.get('ai_recommendations', [])}")

Configuration (config.yaml):
    matching:
      engine: "auto"  # "nlp", "gemini", or "auto"
      weights:
        skills: 0.45      # Weight for skills match
        experience: 0.35  # Weight for experience match
        domains: 0.20     # Weight for domain match
      min_match_score: 0.6  # Minimum score threshold
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from src.matching.skills_matcher import SkillsMatcher
from src.matching.skill_extractor import extract_skills_from_description, ALL_SKILLS
from src.database import crud
from src.database.models import Resume, JobPosting, MatchResult
from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class GeminiStats:
    """Statistics about Gemini API usage during job matching."""
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    failure_reasons: List[str] = field(default_factory=list)
    _timings_ms: List[float] = field(default_factory=list)

    def add_failure(self, reason: str) -> None:
        """Add a failure reason (unique only)."""
        self.failed += 1
        if reason not in self.failure_reasons:
            self.failure_reasons.append(reason)

    def add_timing(self, duration_ms: float) -> None:
        """Record per-job Gemini match duration."""
        self._timings_ms.append(duration_ms)

    def timing_summary(self) -> Optional[Dict]:
        """Compute timing percentile summary, or None if no timings recorded."""
        if not self._timings_ms:
            return None
        sorted_t = sorted(self._timings_ms)
        n = len(sorted_t)
        return {
            "count": n,
            "min_ms": round(sorted_t[0], 1),
            "max_ms": round(sorted_t[-1], 1),
            "avg_ms": round(sum(sorted_t) / n, 1),
            "p50_ms": round(sorted_t[n // 2], 1),
            "p90_ms": round(sorted_t[int(n * 0.9)], 1) if n >= 2 else round(sorted_t[-1], 1),
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "failure_reasons": self.failure_reasons
        }


class JobMatcher:
    """Job matching engine that scores jobs against a resume.

    Supports two matching modes:
    - "nlp": Traditional NLP-based matching (default, free, fast)
    - "gemini": AI-powered matching with richer insights (higher accuracy, costs per call)
    - "auto": Use Gemini if available and job has structured requirements, else NLP
    """

    def __init__(
        self,
        skills_matcher: Optional[SkillsMatcher] = None,
        preload_cache: bool = True,
        mode: str = "auto"
    ):
        """Initialize job matcher.

        Args:
            skills_matcher: SkillsMatcher instance. If None, creates a new one.
            preload_cache: If True, pre-cache skill dictionary embeddings for performance.
            mode: Matching mode - "nlp", "gemini", or "auto" (default).
        """
        self.config = get_config()

        # Determine mode from config if not explicitly set
        self.mode = mode
        if mode == "auto":
            self.mode = self.config.get("matching.engine", "auto")

        # Always initialize NLP matcher (used as fallback)
        if skills_matcher:
            self.skills_matcher = skills_matcher
        elif preload_cache:
            logger.info("Initializing JobMatcher with pre-cached skill embeddings...")
            skill_list = list(ALL_SKILLS)
            self.skills_matcher = SkillsMatcher(preload_skills=skill_list)
        else:
            self.skills_matcher = SkillsMatcher()

        # Initialize Gemini matcher if mode allows
        self.gemini_matcher = None
        if self.mode in ("gemini", "auto"):
            try:
                from src.matching.gemini_matcher import GeminiMatcher
                matcher = GeminiMatcher()
                if matcher.is_available():
                    self.gemini_matcher = matcher
                    logger.info(f"GeminiMatcher initialized (mode={self.mode})")
                elif self.mode == "gemini":
                    logger.warning("Gemini mode requested but not available, falling back to NLP")
                    self.mode = "nlp"
            except Exception as e:
                logger.warning(f"Failed to initialize GeminiMatcher: {e}")
                if self.mode == "gemini":
                    self.mode = "nlp"

        # Get matching weights from config
        weights = self.config.get_matching_weights()
        self.skills_weight = weights.get('skills', 0.45)
        self.experience_weight = weights.get('experience', 0.35)
        self.domains_weight = weights.get('domains', 0.20)

        # Get engine version from config
        self.engine_version = self.config.get_engine_version()

        # Load domain relationships for partial credit scoring
        self.domain_relationships = self._load_domain_relationships()

    def _load_domain_relationships(self) -> Dict:
        """Load domain relationships for partial credit scoring.

        Returns:
            Dict with 'config' and 'relationships' keys
        """
        rel_path = Path(__file__).parent.parent.parent / "data" / "domain_relationships.json"
        try:
            if rel_path.exists():
                with open(rel_path) as f:
                    data = json.load(f)
                    logger.debug(f"Loaded domain relationships with {len(data.get('relationships', {}))} domains")
                    return data
        except Exception as e:
            logger.warning(f"Failed to load domain_relationships.json: {e}")
        return {"config": {}, "relationships": {}}

    def preload_resume_skills(self, resume_skills: List[str]) -> int:
        """Pre-cache resume skill embeddings for faster matching.

        Args:
            resume_skills: List of skills from resume

        Returns:
            Number of new skills cached
        """
        if resume_skills:
            return self.skills_matcher.preload_embeddings(resume_skills)
        return 0

    def _should_use_gemini(self, job: JobPosting) -> bool:
        """Determine if Gemini should be used for this job.

        Args:
            job: JobPosting to evaluate

        Returns:
            True if Gemini should be used
        """
        if self.mode == "nlp":
            return False

        if self.mode == "gemini":
            return self.gemini_matcher is not None

        # Auto mode: prefer Gemini when available
        if self.gemini_matcher is None:
            return False

        # Use Gemini for all jobs in auto mode (structured requirements improve accuracy but aren't required)
        return True

    def _categorize_error(self, error: Exception) -> str:
        """Categorize a Gemini error for user-friendly reporting.

        Args:
            error: The exception that occurred

        Returns:
            A short, user-friendly error category string
        """
        error_str = str(error).lower()

        if "rate limit" in error_str or "quota" in error_str or "429" in error_str:
            return "rate_limit"
        if "timeout" in error_str or "timed out" in error_str:
            return "timeout"
        if "safety" in error_str or "blocked" in error_str:
            return "safety_blocked"
        if "parse" in error_str or "json" in error_str or "decode" in error_str:
            return "parse_error"
        if "connection" in error_str or "network" in error_str:
            return "connection_error"
        if "auth" in error_str or "key" in error_str or "401" in error_str or "403" in error_str:
            return "auth_error"

        return "api_error"

    def _match_with_gemini(
        self,
        resume: Resume,
        job: JobPosting
    ) -> Optional[Dict]:
        """Match using Gemini AI.

        Args:
            resume: Resume object
            job: JobPosting object

        Returns:
            Match result dict or None if failed
        """
        if not self.gemini_matcher:
            return None

        # Get structured requirements if available — but only use them if they
        # contain actual skill lists. Empty must_have_skills forces the simple
        # prompt which includes the full description and yields better skill matches.
        structured_requirements = getattr(job, 'structured_requirements', None)
        if structured_requirements:
            must_have = structured_requirements.get('must_have_skills') or []
            nice_to_have = structured_requirements.get('nice_to_have_skills') or []
            if not must_have and not nice_to_have:
                structured_requirements = None  # fall back to simple prompt

        # Get recent roles from resume job_titles
        recent_roles = resume.job_titles[:5] if resume.job_titles else []

        result = self.gemini_matcher.match_job(
            resume_skills=resume.skills or [],
            experience_years=resume.experience_years or 0,
            resume_domains=resume.domains or [],
            recent_roles=recent_roles,
            job_title=job.title,
            company=job.company,
            job_description=job.description or "",
            structured_requirements=structured_requirements,
            use_batch_model=False  # Use best model for single matches
        )

        if result:
            # Convert GeminiMatchResult to dict format matching NLP output
            return {
                'overall_score': result.overall_score / 100,  # Convert to 0-1 scale
                'skills_score': result.skills_score / 100,
                'experience_score': result.experience_score / 100,
                'domain_score': result.domain_score / 100,
                'seniority_fit': result.seniority_fit / 100,
                # Flatten comma-joined resume_skill strings and deduplicate.
                # Gemini sometimes packs multiple skills into one resume_skill value
                # (e.g. "SQL, Analytics, Snowflake") and can map several job skills to
                # the same resume skill, causing duplicate chips in the UI.
                'matching_skills': list(dict.fromkeys(
                    s.strip()
                    for m in result.skill_matches
                    if m.resume_skill
                    for s in m.resume_skill.split(',')
                    if s.strip()
                )),
                'skill_gaps': [g.skill for g in result.skill_gaps],
                'matching_domains': [],  # Not tracked separately in AI mode
                'missing_domains': [],
                'match_details': {},
                'extracted_skills': [],
                'resume_years': resume.experience_years or 0,
                'job_years_required': job.experience_required,
                'engine_version': self.engine_version,
                # AI-specific fields
                'match_engine': 'gemini',
                'ai_match_score': result.overall_score,
                'ai_skills_score': result.skills_score,
                'ai_experience_score': result.experience_score,
                'ai_seniority_fit': result.seniority_fit,
                'ai_domain_score': result.domain_score,
                'ai_strengths': result.strengths,
                'ai_concerns': result.concerns,
                'ai_recommendations': result.recommendations,
                'skill_matches': [m.to_dict() for m in result.skill_matches],
                'skill_gaps_detailed': [g.to_dict() for g in result.skill_gaps],
                'match_confidence': result.confidence,
                'gemini_reasoning': result.reasoning,
            }

        return None

    def calculate_experience_match(
        self,
        resume_years: float,
        job_years_required: Optional[float],
        max_years: Optional[float] = None
    ) -> float:
        """Calculate experience alignment score.

        Args:
            resume_years: Years of experience from resume
            job_years_required: Minimum years required by job (can be None)
            max_years: Maximum years preferred by job (can be None). When provided,
                       being above the range results in a slight overqualified penalty.

        Returns:
            Score from 0.0 to 1.0

        Scoring logic:
            - If job doesn't specify requirements: 0.4 (slightly penalized)
            - If resume in [min, max] range: 1.0 (perfect match)
            - If resume > max (overqualified): 0.85 (slight penalty)
            - If resume >= min (no max specified): 1.0
            - If resume < required: Scaled score based on deficit
                - 0-1 year deficit: 0.7
                - 1-2 year deficit: 0.5
                - 2-3 year deficit: 0.3
                - 3+ year deficit: 0.1
        """
        if job_years_required is None or job_years_required == 0:
            return 0.4  # No requirements specified - slightly penalize unknown

        # Check overqualified when max_years is known
        if max_years is not None and resume_years > max_years:
            return 0.85  # Overqualified - slight penalty but still viable

        if resume_years >= job_years_required:
            return 1.0  # Meets or exceeds minimum requirements

        # Calculate deficit
        deficit = job_years_required - resume_years

        # Score based on deficit (steeper penalties)
        if deficit <= 1:
            return 0.7  # 0-1 year short
        elif deficit <= 2:
            return 0.5  # 1-2 years short
        elif deficit <= 3:
            return 0.3  # 2-3 years short
        else:
            return 0.1  # 3+ years short

    def calculate_domain_match(
        self,
        resume_domains: List[str],
        job_domains: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """Calculate domain expertise alignment score with relationship support.

        Uses domain relationships for partial credit:
        - Exact match: 100% credit
        - Related domain: 70% credit (configurable)
        - Transferable domain: 40% credit (configurable)

        Args:
            resume_domains: List of domains from resume (e.g., ["fintech", "b2b_saas"])
            job_domains: List of required domains from job posting

        Returns:
            Tuple of (score, matching_domains, missing_domains):
                - score: 0.0-1.0 representing domain alignment
                - matching_domains: List of matched domains (with ~ for related, * for transferable)
                - missing_domains: List of required domains with no credit

        Scoring logic:
            - If job doesn't require specific domains: 0.5 (neutral score)
            - If resume has all required domains: 1.0 (perfect match)
            - Related domains (e.g., fintech for banking job): 70% credit
            - Transferable domains (e.g., ecommerce for fintech job): 40% credit
        """
        # Normalize domains to lowercase for comparison
        resume_set = {d.lower() for d in (resume_domains or [])}
        job_set = {d.lower() for d in (job_domains or [])}

        # If job doesn't require specific domains, neutral score
        if not job_set:
            return 0.5, [], []

        # Get relationship config weights
        rel_config = self.domain_relationships.get("config", {})
        related_weight = rel_config.get("related_weight", 0.7)
        transferable_weight = rel_config.get("transferable_weight", 0.4)
        relationships = self.domain_relationships.get("relationships", {})

        total_score = 0.0
        matching = []
        missing = []

        for job_domain in job_set:
            if job_domain in resume_set:
                # Exact match - full credit
                total_score += 1.0
                matching.append(job_domain)
            else:
                # Check for related/transferable domains
                job_rels = relationships.get(job_domain, {})
                related = {r.lower() for r in job_rels.get("related", [])}
                transferable = {t.lower() for t in job_rels.get("transferable", [])}

                # Check for related domain match (higher credit)
                related_matches = resume_set & related
                if related_matches:
                    total_score += related_weight
                    # Mark with ~ to indicate related match
                    matching.append(f"{job_domain}~{list(related_matches)[0]}")
                # Check for transferable domain match (lower credit)
                elif resume_set & transferable:
                    transferable_matches = resume_set & transferable
                    total_score += transferable_weight
                    # Mark with * to indicate transferable match
                    matching.append(f"{job_domain}*{list(transferable_matches)[0]}")
                else:
                    # No credit for this domain
                    missing.append(job_domain)

        # Calculate final score
        score = total_score / len(job_set)

        return round(score, 3), matching, missing

    def match_job(
        self,
        resume: Resume,
        job: JobPosting,
        skills_threshold: float = 0.5,
        force_nlp: bool = False,
        gemini_stats: Optional[GeminiStats] = None
    ) -> Dict:
        """Match a single job against a resume.

        Args:
            resume: Resume object from database
            job: JobPosting object from database
            skills_threshold: Minimum similarity for skill matching (NLP mode)
            force_nlp: Force NLP mode even if Gemini is available
            gemini_stats: Optional GeminiStats object for tracking API usage

        Returns:
            Dictionary with match results:
                - overall_score: Combined score (0.0-1.0)
                - skills_score: Skills match score (0.0-1.0)
                - experience_score: Experience match score (0.0-1.0)
                - domain_score: Domain match score (0.0-1.0)
                - matching_skills: List of matched skills
                - skill_gaps: List of job skills not covered
                - matching_domains: List of matched domains
                - missing_domains: List of required domains not in resume
                - match_details: Detailed skill matching info
                - match_engine: "nlp" or "gemini"

            AI mode includes additional fields:
                - ai_strengths: List of candidate strengths
                - ai_concerns: List of concerns
                - ai_recommendations: List of recommendations
                - skill_matches: Detailed skill match analysis
                - skill_gaps_detailed: Detailed gap analysis with transferability
        """
        # Try Gemini matching if appropriate
        if not force_nlp and self._should_use_gemini(job):
            if gemini_stats:
                gemini_stats.attempted += 1

            t0 = time.perf_counter()
            try:
                ai_result = self._match_with_gemini(resume, job)
                if ai_result:
                    if gemini_stats:
                        gemini_stats.succeeded += 1
                        gemini_stats.add_timing((time.perf_counter() - t0) * 1000)
                    return ai_result
                else:
                    # Gemini returned None (empty response)
                    if gemini_stats:
                        gemini_stats.add_failure("empty_response")
                    logger.warning(f"Gemini returned empty for '{job.title}', falling back to NLP")
            except Exception as e:
                if gemini_stats:
                    reason = self._categorize_error(e)
                    gemini_stats.add_failure(reason)
                logger.warning(f"Gemini matching failed for '{job.title}', falling back to NLP: {e}")

        # Fall back to NLP matching
        return self._match_with_nlp(resume, job, skills_threshold)

    def _match_with_nlp(
        self,
        resume: Resume,
        job: JobPosting,
        skills_threshold: float = 0.5
    ) -> Dict:
        """Match using NLP-based semantic similarity (original algorithm).

        Args:
            resume: Resume object from database
            job: JobPosting object from database
            skills_threshold: Minimum similarity for skill matching

        Returns:
            Dictionary with match results
        """
        # Use Gemini-extracted structured_requirements when available (more accurate than regex)
        structured_req = job.structured_requirements  # dict or None (JSON column)
        must_have_skills: List[str] = []
        nice_to_have_skills: List[str] = []
        extracted_skills: List[str] = []

        if structured_req:
            raw_must = structured_req.get('must_have_skills', [])
            raw_nice = structured_req.get('nice_to_have_skills', [])
            must_have_skills = [s['name'] if isinstance(s, dict) else s for s in raw_must if s]
            nice_to_have_skills = [s['name'] if isinstance(s, dict) else s for s in raw_nice if s]

        if must_have_skills or nice_to_have_skills:
            # Structured path: use Gemini-extracted skills with importance weights
            logger.debug(
                f"NLP using structured_requirements for '{job.title}': "
                f"{len(must_have_skills)} must-have, {len(nice_to_have_skills)} nice-to-have"
            )
            job_skills = must_have_skills + nice_to_have_skills
            skill_weights: Optional[Dict[str, float]] = {s: 2.0 for s in must_have_skills}
            skill_weights.update({s: 1.0 for s in nice_to_have_skills})
        else:
            # Fallback: regex extraction from description (original behavior)
            extracted_skills = extract_skills_from_description(job.description or "")
            if len(extracted_skills) < 3:
                logger.warning(
                    f"Low skill extraction ({len(extracted_skills)} skills) for job: "
                    f"'{job.title}' at '{job.company}' (desc len: {len(job.description or '')})"
                )
            job_skills = extracted_skills if extracted_skills else (job.required_skills or [])
            skill_weights = None

        # Skills matching (weighted when structured_requirements available)
        skills_score, matching_skills, match_details = self.skills_matcher.calculate_skills_match(
            resume_skills=resume.skills or [],
            job_skills=job_skills,
            threshold=skills_threshold,
            weights=skill_weights
        )

        # Experience matching — use min/max range from structured_requirements when available
        min_years = job.experience_required
        max_years: Optional[float] = None
        if structured_req:
            min_years = structured_req.get('min_years', min_years)
            max_years = structured_req.get('max_years')

        experience_score = self.calculate_experience_match(
            resume_years=resume.experience_years or 0,
            job_years_required=min_years,
            max_years=max_years
        )

        # Domain matching — prefer structured_requirements domains when available
        job_domains = job.required_domains or []
        if structured_req:
            sr_domains = structured_req.get('required_domains', [])
            if sr_domains:
                job_domains = sr_domains

        domain_score, matching_domains, missing_domains = self.calculate_domain_match(
            resume_domains=resume.domains or [],
            job_domains=job_domains
        )

        # Calculate weighted overall score
        overall_score = (
            skills_score * self.skills_weight +
            experience_score * self.experience_weight +
            domain_score * self.domains_weight
        )

        # Find skill gaps
        skill_gaps = self.skills_matcher.find_skill_gaps(
            resume_skills=resume.skills or [],
            job_skills=job_skills,
            threshold=skills_threshold
        )

        return {
            'overall_score': round(overall_score, 3),
            'skills_score': round(skills_score, 3),
            'experience_score': round(experience_score, 3),
            'domain_score': round(domain_score, 3),
            'matching_skills': matching_skills,
            'skill_gaps': skill_gaps,
            'matching_domains': matching_domains,
            'missing_domains': missing_domains,
            'match_details': match_details,
            'extracted_skills': extracted_skills,
            'resume_years': resume.experience_years or 0,
            'job_years_required': min_years,
            'engine_version': self.engine_version,
            'match_engine': 'nlp',
        }

    def match_jobs(
        self,
        resume: Resume,
        jobs: List[JobPosting],
        min_score: Optional[float] = None,
        top_n: Optional[int] = None,
        track_gemini_stats: bool = True
    ) -> Tuple[List[Dict], Optional[GeminiStats]]:
        """Match multiple jobs against a resume and rank them.

        Args:
            resume: Resume object from database
            jobs: List of JobPosting objects
            min_score: Minimum overall score to include (uses config default if None)
            top_n: Return only top N matches (returns all if None)
            track_gemini_stats: If True, track and return Gemini API usage stats

        Returns:
            Tuple of (matches, gemini_stats):
                - matches: List of match dictionaries, sorted by overall_score descending.
                  Each dict includes all match_job() results plus job details.
                - gemini_stats: GeminiStats object with API usage info, or None if not tracking
        """
        if min_score is None:
            min_score = self.config.get_min_match_score()

        gemini_stats = GeminiStats() if track_gemini_stats else None
        concurrency = self.config.get("gemini.matcher.concurrency", 1)

        # Use concurrent matching when Gemini is active and concurrency > 1.
        # The GeminiRateLimiter (threading.Lock) serialises API calls across threads,
        # so concurrent threads simply pipeline their calls through the rate limiter
        # instead of waiting for each to fully complete before starting the next.
        if concurrency > 1 and self.gemini_matcher and self.gemini_matcher.is_available():
            matches = self._match_jobs_concurrent(resume, jobs, min_score, concurrency, gemini_stats)
        else:
            matches = self._match_jobs_sequential(resume, jobs, min_score, gemini_stats)

        # Sort by overall score (descending)
        matches.sort(key=lambda x: x['overall_score'], reverse=True)

        # Return top N if specified
        if top_n:
            matches = matches[:top_n]

        # Log stats if tracking
        if gemini_stats and gemini_stats.attempted > 0:
            logger.info(
                f"Gemini stats: {gemini_stats.succeeded}/{gemini_stats.attempted} succeeded, "
                f"{gemini_stats.failed} failed"
                + (f" (reasons: {', '.join(gemini_stats.failure_reasons)})" if gemini_stats.failure_reasons else "")
            )

        return matches, gemini_stats

    def _match_jobs_sequential(
        self,
        resume: Resume,
        jobs: List[JobPosting],
        min_score: float,
        gemini_stats: Optional[GeminiStats],
    ) -> List[Dict]:
        """Sequential implementation of job matching (used when concurrency=1)."""
        matches = []
        for job in jobs:
            match_result = self.match_job(resume, job, gemini_stats=gemini_stats)
            if match_result['overall_score'] >= min_score:
                match_result.update(self._job_detail_fields(job))
                matches.append(match_result)
        return matches

    def _match_jobs_concurrent(
        self,
        resume: Resume,
        jobs: List[JobPosting],
        min_score: float,
        concurrency: int,
        gemini_stats: Optional[GeminiStats],
    ) -> List[Dict]:
        """Concurrent implementation of job matching using ThreadPoolExecutor.

        Each worker thread calls match_job() independently. The GeminiRateLimiter
        (threading.Lock) serialises API calls, so threads effectively pipeline their
        Gemini requests — each starts its call as soon as the previous thread's rate
        limit window expires, rather than waiting for the previous call to complete.
        """
        # Pre-load all ORM attributes that worker threads will access.
        # SQLAlchemy lazy-loading is not safe from non-owning threads; touching
        # every attribute here forces the queries to run in the main thread so
        # workers only read already-materialised Python values.
        _ = resume.skills, resume.experience_years, resume.domains, resume.job_titles
        for job in jobs:
            _ = (
                job.id, job.title, job.company, job.location, job.url,
                job.description, job.experience_required, job.posting_date,
                job.required_domains, job.required_skills, job.structured_requirements,
            )

        stats_lock = threading.Lock()
        matches = []
        matches_lock = threading.Lock()

        def _match_one(job: JobPosting) -> None:
            """Worker: match a single job and append to shared results list."""
            t0 = time.perf_counter()
            try:
                # match_job is thread-safe: reads-only from shared state,
                # and all Gemini calls are serialised by the rate limiter lock.
                result = self.match_job(resume, job, gemini_stats=None)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if gemini_stats is not None:
                    with stats_lock:
                        if self._should_use_gemini(job):
                            # Gemini was attempted for this job
                            gemini_stats.attempted += 1
                            if result.get('match_engine') == 'gemini':
                                gemini_stats.succeeded += 1
                                gemini_stats.add_timing(elapsed_ms)
                            else:
                                # Gemini was tried but fell back to NLP
                                gemini_stats.add_failure("nlp_fallback")

                if result['overall_score'] >= min_score:
                    result.update(self._job_detail_fields(job))
                    with matches_lock:
                        matches.append(result)

            except Exception as e:
                logger.error(f"Unexpected error matching '{job.title}': {e}", exc_info=True)
                if gemini_stats is not None:
                    with stats_lock:
                        gemini_stats.add_failure("exception")

        # The ThreadPoolExecutor context manager waits for all futures on exit.
        # _match_one swallows all exceptions internally (logging them), so there
        # are no exceptions to propagate from the futures.
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="matcher") as executor:
            for job in jobs:
                executor.submit(_match_one, job)

        return matches

    def _job_detail_fields(self, job: JobPosting) -> Dict:
        """Return the job-detail fields appended to every match result.

        Only plain/scalar values are included — no raw ORM objects.
        Storing the ORM object in the result dict is unsafe after the
        session closes (DetachedInstanceError on unloaded relations).
        """
        return {
            'job_id': job.id,
            'job_title': job.title,
            'company': job.company,
            'location': job.location,
            'url': job.url,
            'posting_date': job.posting_date,
            'description': job.description,
            'experience_required': job.experience_required,
            'required_domains': job.required_domains or [],
        }

    def save_match_results(
        self,
        db_session,
        resume_id: int,
        match_results: List[Dict]
    ) -> List[MatchResult]:
        """Save match results to database.

        Args:
            db_session: Database session
            resume_id: Resume ID
            match_results: List of match result dictionaries from match_jobs()

        Returns:
            List of created MatchResult objects
        """
        saved_results = []

        for match in match_results:
            # Convert score from 0-1 to 0-100 format for database storage
            score_as_percentage = match['overall_score'] * 100

            # gemini_score is already 0-100 from the reranker/matcher (if present)
            gemini_score = match.get('gemini_score')

            # Build experience alignment description (TEXT field, not float)
            resume_years = match.get('resume_years', 0)
            job_years = match.get('job_years_required')
            if job_years is not None:
                experience_alignment_text = f"Resume: {resume_years} years, Required: {job_years} years"
            else:
                experience_alignment_text = f"Resume: {resume_years} years, Required: Not specified"

            # Prepare matching fields - domain_score for all engines, AI fields for Gemini
            match_fields = {
                'match_engine': match.get('match_engine', 'nlp'),
            }

            # domain_score is saved for both NLP and Gemini matches
            # NLP: stored as 0-1 in match dict, convert to 0-100 for DB
            # Gemini: stored as 0-100 in ai_domain_score
            if match.get('match_engine') == 'gemini':
                match_fields['domain_score'] = match.get('ai_domain_score')
            else:
                # NLP domain_score is 0-1, convert to 0-100 for consistency
                nlp_domain_score = match.get('domain_score')
                if nlp_domain_score is not None:
                    match_fields['domain_score'] = nlp_domain_score * 100

            # Additional AI-specific fields (only for Gemini matching)
            if match.get('match_engine') == 'gemini':
                match_fields.update({
                    'ai_match_score': match.get('ai_match_score'),
                    'skills_score': match.get('ai_skills_score'),
                    'experience_score': match.get('ai_experience_score'),
                    'seniority_fit': match.get('ai_seniority_fit'),
                    'ai_strengths': match.get('ai_strengths'),
                    'ai_concerns': match.get('ai_concerns'),
                    'ai_recommendations': match.get('ai_recommendations'),
                    'skill_matches': match.get('skill_matches'),
                    'skill_gaps_detailed': match.get('skill_gaps_detailed'),
                    'match_confidence': match.get('match_confidence'),
                })

            # Strip None entries from all list fields before writing to the database.
            # Gemini can emit null items in JSON arrays; cleaning here keeps the DB
            # correct so every read path gets non-null lists without defensive filtering.
            def _clean_list(lst) -> list:
                return [x for x in (lst or []) if x is not None]

            if 'ai_strengths' in match_fields:
                match_fields['ai_strengths'] = _clean_list(match_fields.get('ai_strengths'))
            if 'ai_concerns' in match_fields:
                match_fields['ai_concerns'] = _clean_list(match_fields.get('ai_concerns'))
            if 'ai_recommendations' in match_fields:
                match_fields['ai_recommendations'] = _clean_list(match_fields.get('ai_recommendations'))

            result = crud.create_match_result(
                db=db_session,
                job_id=match['job_id'],
                resume_id=resume_id,
                match_score=score_as_percentage,
                matching_skills=_clean_list(match.get('matching_skills')),
                experience_alignment=experience_alignment_text,
                engine_version=match.get('engine_version'),
                gemini_score=gemini_score,
                gemini_reasoning=match.get('gemini_reasoning'),
                missing_domains=_clean_list(match.get('missing_domains')),
                **match_fields
            )
            saved_results.append(result)

        return saved_results


def create_job_matcher(
    skills_matcher: Optional[SkillsMatcher] = None,
    preload_cache: bool = True,
    mode: str = "auto"
) -> JobMatcher:
    """Factory function to create a JobMatcher instance.

    Args:
        skills_matcher: Optional SkillsMatcher instance
        preload_cache: If True, pre-cache skill dictionary embeddings
        mode: Matching mode - "nlp", "gemini", or "auto"

    Returns:
        JobMatcher instance
    """
    return JobMatcher(skills_matcher=skills_matcher, preload_cache=preload_cache, mode=mode)
