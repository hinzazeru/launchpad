"""Main matching engine for comparing resumes against job postings.

Matching is Gemini-only: each job is scored by the Gemini AI matcher, which
returns component scores (skills, experience, seniority, domain) plus rich
insights (strengths, concerns, recommendations, detailed skill analysis).

There is no NLP fallback. If Gemini is unavailable or a match fails, the engine
raises GeminiUnavailableError so the caller can fail the search and retry later
rather than persisting a degraded result.

Key Classes:
    JobMatcher: Gemini-backed matching orchestrator
    GeminiUnavailableError: Raised when Gemini matching is unavailable/fails

Key Functions:
    create_job_matcher(): Factory function to create a JobMatcher instance

Usage Example:
    >>> from src.matching.engine import JobMatcher
    >>> from src.database.models import Resume, JobPosting
    >>>
    >>> matcher = JobMatcher()  # raises GeminiUnavailableError if not configured
    >>> result = matcher.match_job(resume, job_posting)
    >>> print(f"Match score: {result['overall_score'] * 100}%")
    >>> print(f"Strengths: {result.get('ai_strengths', [])}")
    >>> print(f"Recommendations: {result.get('ai_recommendations', [])}")

Configuration (config.yaml):
    matching:
      engine: "gemini"      # Gemini-only
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
from src.database import crud
from src.database.models import Resume, JobPosting, MatchResult
from src.config import get_config

logger = logging.getLogger(__name__)


class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini matching is required but unavailable or failed.

    Matching is Gemini-only: there is no NLP fallback. Callers should treat this
    as a transient failure and let the search be retried later rather than
    persisting a degraded result.
    """


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
    """Job matching engine that scores jobs against a resume using Gemini AI.

    Matching is Gemini-only. If Gemini is unavailable, JobMatcher raises
    GeminiUnavailableError at construction so callers can fail the search and
    retry later rather than serving degraded matches.
    """

    def __init__(self, mode: str = "gemini"):
        """Initialize job matcher.

        Args:
            mode: Retained for backward compatibility; matching is always Gemini.

        Raises:
            GeminiUnavailableError: If Gemini is not configured/available.
        """
        self.config = get_config()
        self.mode = "gemini"

        # Initialize Gemini matcher — required (no NLP fallback)
        self.gemini_matcher = None
        try:
            from src.matching.gemini_matcher import GeminiMatcher
            matcher = GeminiMatcher()
            if matcher.is_available():
                self.gemini_matcher = matcher
                logger.info("GeminiMatcher initialized")
        except Exception as e:
            raise GeminiUnavailableError(
                f"Failed to initialize GeminiMatcher: {e}"
            ) from e

        if self.gemini_matcher is None:
            raise GeminiUnavailableError(
                "Gemini matching is not available — check gemini.enabled and gemini.api_key"
            )

        # Get engine version from config
        self.engine_version = self.config.get_engine_version()

        # Load domain relationships for partial credit scoring
        self.domain_relationships = self._load_domain_relationships()

        # Load valid domain keys from domain_expertise.json for validation
        self.valid_domain_keys = self._load_valid_domain_keys()

    def _load_valid_domain_keys(self) -> set:
        """Load valid domain keys from domain_expertise.json.

        Used to filter out free-form domain strings from structured_requirements
        that don't match standardized keys (e.g., "SaaS" vs "b2b_saas").
        """
        expertise_path = Path(__file__).parent.parent.parent / "data" / "domain_expertise.json"
        try:
            if expertise_path.exists():
                with open(expertise_path) as f:
                    data = json.load(f)
                keys = set()
                for category in data.get("domains", {}).values():
                    keys.update(category.keys())
                logger.debug(f"Loaded {len(keys)} valid domain keys")
                return keys
        except Exception as e:
            logger.warning(f"Failed to load domain_expertise.json: {e}")
        return set()

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
                # Only include skill_matches above 0.75 confidence to suppress
                # low-confidence stretches (e.g. "Fintech" → "Hypergrowth Startup
                # Experience") that mislead the user into thinking unrelated skills
                # appear in the job description.
                'matching_skills': list(dict.fromkeys(
                    s.strip()
                    for m in result.skill_matches
                    if m.resume_skill and m.confidence >= 0.75
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

    def _hydrate_match_from_cache(
        self,
        cached: MatchResult,
        resume: Resume,
        job: JobPosting,
    ) -> Dict:
        """Rebuild a match-result dict from a previously-saved Gemini MatchResult,
        bypassing the Gemini API call. Mirrors the shape returned by
        _match_with_gemini so downstream consumers (rerank, save, UI) are
        agnostic to whether the result is fresh or cached.
        """
        skill_gaps_detailed = cached.skill_gaps_detailed or []
        skill_gaps = [
            g.get("skill")
            for g in skill_gaps_detailed
            if isinstance(g, dict) and g.get("skill")
        ]

        result = {
            "overall_score": (cached.ai_match_score or 0) / 100,
            "skills_score": (cached.skills_score or 0) / 100,
            "experience_score": (cached.experience_score or 0) / 100,
            "domain_score": (cached.domain_score or 0) / 100,
            "seniority_fit": (cached.seniority_fit or 0) / 100,
            "matching_skills": cached.matching_skills or [],
            "skill_gaps": skill_gaps,
            "matching_domains": [],
            "missing_domains": cached.missing_domains or [],
            "match_details": {},
            "extracted_skills": [],
            "resume_years": resume.experience_years or 0,
            "job_years_required": job.experience_required,
            "engine_version": cached.engine_version or self.engine_version,
            "match_engine": "gemini",
            "ai_match_score": cached.ai_match_score,
            "ai_skills_score": cached.skills_score,
            "ai_experience_score": cached.experience_score,
            "ai_seniority_fit": cached.seniority_fit,
            "ai_domain_score": cached.domain_score,
            "ai_strengths": cached.ai_strengths or [],
            "ai_concerns": cached.ai_concerns or [],
            "ai_recommendations": cached.ai_recommendations or [],
            "skill_matches": cached.skill_matches or [],
            "skill_gaps_detailed": skill_gaps_detailed,
            "match_confidence": cached.match_confidence,
            "gemini_reasoning": cached.gemini_reasoning,
            # Marker so save_match_results can skip duplicate DB rows.
            "cache_hit": True,
        }
        # Carry over previously-computed rerank fields so the reranker can
        # detect them and skip its own API call.
        if cached.gemini_score is not None:
            result["gemini_score"] = cached.gemini_score
        if cached.gemini_strengths:
            result["gemini_strengths"] = cached.gemini_strengths
        if cached.gemini_gaps:
            result["gemini_gaps"] = cached.gemini_gaps
        return result

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
        gemini_stats: Optional[GeminiStats] = None
    ) -> Dict:
        """Match a single job against a resume using Gemini AI.

        Matching is Gemini-only. On any Gemini failure this raises
        GeminiUnavailableError — there is no NLP fallback.

        Args:
            resume: Resume object from database
            job: JobPosting object from database
            gemini_stats: Optional GeminiStats object for tracking API usage

        Returns:
            Dictionary with match results including overall/component scores,
            matching skills, skill gaps, and AI insights (strengths, concerns,
            recommendations, detailed skill analysis).

        Raises:
            GeminiUnavailableError: If Gemini matching fails or returns empty.
        """
        if gemini_stats:
            gemini_stats.attempted += 1

        t0 = time.perf_counter()
        try:
            ai_result = self._match_with_gemini(resume, job)
        except Exception as e:
            reason = self._categorize_error(e)
            if gemini_stats:
                gemini_stats.add_failure(reason)
            raise GeminiUnavailableError(
                f"Gemini matching failed for '{job.title}' ({reason}): {e}"
            ) from e

        if not ai_result:
            if gemini_stats:
                gemini_stats.add_failure("empty_response")
            raise GeminiUnavailableError(
                f"Gemini returned empty result for '{job.title}'"
            )

        if gemini_stats:
            gemini_stats.succeeded += 1
            gemini_stats.add_timing((time.perf_counter() - t0) * 1000)
        return ai_result

    def match_jobs(
        self,
        resume: Resume,
        jobs: List[JobPosting],
        min_score: Optional[float] = None,
        top_n: Optional[int] = None,
        track_gemini_stats: bool = True,
        db_session=None,
        effective_resume_id: Optional[int] = None,
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

        # Pre-fetch cached Gemini matches and short-circuit those jobs to avoid
        # repaying API cost when the same (resume, job) was already scored.
        cached_results: List[Dict] = []
        jobs_to_match: List[JobPosting] = list(jobs)
        if db_session is not None:
            rid = (
                effective_resume_id
                if effective_resume_id is not None
                else getattr(resume, "id", 0)
            )
            if rid:
                candidate_ids = [j.id for j in jobs if getattr(j, "id", None)]
                if candidate_ids:
                    try:
                        cache_map = crud.get_cached_gemini_matches(
                            db_session, rid, candidate_ids
                        )
                    except Exception as e:
                        logger.warning(f"Cache lookup failed, falling back to full matching: {e}")
                        cache_map = {}

                    if cache_map:
                        jobs_to_match = []
                        for job in jobs:
                            cached = cache_map.get(getattr(job, "id", None))
                            if cached is not None:
                                hydrated = self._hydrate_match_from_cache(cached, resume, job)
                                if hydrated["overall_score"] >= min_score:
                                    hydrated.update(self._job_detail_fields(job))
                                    cached_results.append(hydrated)
                            else:
                                jobs_to_match.append(job)
                        logger.info(
                            f"Gemini cache: reused {len(cached_results)} prior matches, "
                            f"running fresh on {len(jobs_to_match)} jobs"
                        )

        # Use concurrent matching when Gemini is active and concurrency > 1.
        # The GeminiRateLimiter (threading.Lock) serialises API calls across threads,
        # so concurrent threads simply pipeline their calls through the rate limiter
        # instead of waiting for each to fully complete before starting the next.
        if concurrency > 1 and self.gemini_matcher and self.gemini_matcher.is_available():
            fresh_matches = self._match_jobs_concurrent(resume, jobs_to_match, min_score, concurrency, gemini_stats)
        else:
            fresh_matches = self._match_jobs_sequential(resume, jobs_to_match, min_score, gemini_stats)

        matches = cached_results + fresh_matches

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
        errors: List[Exception] = []
        errors_lock = threading.Lock()

        def _match_one(job: JobPosting) -> None:
            """Worker: match a single job and append to shared results list."""
            t0 = time.perf_counter()
            try:
                # match_job is thread-safe: reads-only from shared state,
                # and all Gemini calls are serialised by the rate limiter lock.
                result = self.match_job(resume, job, gemini_stats=None)
            except Exception as e:
                # Matching is Gemini-only — a failure aborts the whole batch.
                logger.warning(f"Gemini matching failed for '{job.title}': {e}")
                if gemini_stats is not None:
                    with stats_lock:
                        gemini_stats.attempted += 1
                        gemini_stats.add_failure(self._categorize_error(e))
                with errors_lock:
                    errors.append(e)
                return

            elapsed_ms = (time.perf_counter() - t0) * 1000
            if gemini_stats is not None:
                with stats_lock:
                    gemini_stats.attempted += 1
                    gemini_stats.succeeded += 1
                    gemini_stats.add_timing(elapsed_ms)

            if result['overall_score'] >= min_score:
                result.update(self._job_detail_fields(job))
                with matches_lock:
                    matches.append(result)

        # The ThreadPoolExecutor context manager waits for all futures on exit.
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="matcher") as executor:
            for job in jobs:
                executor.submit(_match_one, job)

        # Propagate the first failure so the search aborts and can be retried.
        if errors:
            first = errors[0]
            if isinstance(first, GeminiUnavailableError):
                raise first
            raise GeminiUnavailableError(f"Gemini matching failed: {first}") from first

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
            # Cache hits already have a saved MatchResult row; skip to avoid duplicates.
            if match.get("cache_hit"):
                continue
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

            # Prepare matching fields - domain_score plus AI fields for Gemini
            match_fields = {
                'match_engine': match.get('match_engine', 'gemini'),
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


def create_job_matcher(mode: str = "gemini") -> JobMatcher:
    """Factory function to create a JobMatcher instance.

    Args:
        mode: Retained for backward compatibility; matching is always Gemini.

    Returns:
        JobMatcher instance

    Raises:
        GeminiUnavailableError: If Gemini is not configured/available.
    """
    return JobMatcher(mode=mode)
