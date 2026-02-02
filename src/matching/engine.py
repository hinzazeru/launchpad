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

import logging
from dataclasses import dataclass, field
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

    def add_failure(self, reason: str) -> None:
        """Add a failure reason (unique only)."""
        self.failed += 1
        if reason not in self.failure_reasons:
            self.failure_reasons.append(reason)

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

        # Get structured requirements if available
        structured_requirements = getattr(job, 'structured_requirements', None)

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
                'matching_skills': [m.resume_skill for m in result.skill_matches],
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
        job_years_required: Optional[float]
    ) -> float:
        """Calculate experience alignment score.

        Args:
            resume_years: Years of experience from resume
            job_years_required: Years required by job (can be None)

        Returns:
            Score from 0.0 to 1.0

        Scoring logic:
            - If job doesn't specify requirements: 0.4 (slightly penalized)
            - If resume >= required: 1.0 (perfect match)
            - If resume < required: Scaled score based on deficit
                - 0-1 year deficit: 0.7
                - 1-2 year deficit: 0.5
                - 2-3 year deficit: 0.3
                - 3+ year deficit: 0.1
        """
        if job_years_required is None or job_years_required == 0:
            return 0.4  # No requirements specified - slightly penalize unknown

        if resume_years >= job_years_required:
            return 1.0  # Meets or exceeds requirements

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
        """Calculate domain expertise alignment score.

        Args:
            resume_domains: List of domains from resume (e.g., ["fintech", "b2b_saas"])
            job_domains: List of required domains from job posting

        Returns:
            Tuple of (score, matching_domains, missing_domains):
                - score: 0.0-1.0 representing domain alignment
                - matching_domains: List of domains that match
                - missing_domains: List of required domains not in resume

        Scoring logic:
            - If job doesn't require specific domains: 0.5 (neutral score)
            - If resume has all required domains: 1.0 (perfect match)
            - Partial credit for partial overlap: overlap_count / required_count
        """
        # Normalize domains to lowercase for comparison
        resume_set = {d.lower() for d in (resume_domains or [])}
        job_set = {d.lower() for d in (job_domains or [])}

        # If job doesn't require specific domains, perfect score
        if not job_set:
            return 0.5, [], []

        # Find matching and missing domains
        matching = list(resume_set & job_set)
        missing = list(job_set - resume_set)

        # Calculate score based on overlap
        score = len(matching) / len(job_set) if job_set else 0.5

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

            try:
                ai_result = self._match_with_gemini(resume, job)
                if ai_result:
                    if gemini_stats:
                        gemini_stats.succeeded += 1
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
        # Extract skills from job description (preferred over LinkedIn tags)
        extracted_skills = extract_skills_from_description(job.description or "")

        # Log warning for sparse skill extraction
        if len(extracted_skills) < 3:
            logger.warning(
                f"Low skill extraction ({len(extracted_skills)} skills) for job: "
                f"'{job.title}' at '{job.company}' (desc len: {len(job.description or '')})"
            )

        # Use extracted skills if available, fall back to required_skills field
        job_skills = extracted_skills if extracted_skills else (job.required_skills or [])

        # Skills matching
        skills_score, matching_skills, match_details = self.skills_matcher.calculate_skills_match(
            resume_skills=resume.skills or [],
            job_skills=job_skills,
            threshold=skills_threshold
        )

        # Experience matching
        experience_score = self.calculate_experience_match(
            resume_years=resume.experience_years or 0,
            job_years_required=job.experience_required
        )

        # Domain matching
        domain_score, matching_domains, missing_domains = self.calculate_domain_match(
            resume_domains=resume.domains or [],
            job_domains=job.required_domains or []
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
            'job_years_required': job.experience_required,
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

        matches = []
        gemini_stats = GeminiStats() if track_gemini_stats else None

        for job in jobs:
            match_result = self.match_job(resume, job, gemini_stats=gemini_stats)

            # Only include if meets minimum score
            if match_result['overall_score'] >= min_score:
                # Add job details to match result
                match_result['job'] = job
                match_result['job_id'] = job.id
                match_result['job_title'] = job.title
                match_result['company'] = job.company
                match_result['location'] = job.location
                match_result['url'] = job.url
                match_result['posting_date'] = job.posting_date
                match_result['description'] = job.description
                match_result['experience_required'] = job.experience_required
                match_result['required_domains'] = job.required_domains or []

                matches.append(match_result)

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

            # Convert Gemini score from 0-1 to 0-100 (if present - for old re-ranker)
            gemini_score = match.get('gemini_score')
            if gemini_score is not None:
                gemini_score = gemini_score * 100

            # Build experience alignment description (TEXT field, not float)
            resume_years = match.get('resume_years', 0)
            job_years = match.get('job_years_required')
            if job_years is not None:
                experience_alignment_text = f"Resume: {resume_years} years, Required: {job_years} years"
            else:
                experience_alignment_text = f"Resume: {resume_years} years, Required: Not specified"

            # Prepare AI-specific fields (if using Gemini matching)
            ai_fields = {}
            if match.get('match_engine') == 'gemini':
                ai_fields = {
                    'ai_match_score': match.get('ai_match_score'),
                    'skills_score': match.get('ai_skills_score'),
                    'experience_score': match.get('ai_experience_score'),
                    'seniority_fit': match.get('ai_seniority_fit'),
                    'domain_score': match.get('ai_domain_score'),
                    'ai_strengths': match.get('ai_strengths'),
                    'ai_concerns': match.get('ai_concerns'),
                    'ai_recommendations': match.get('ai_recommendations'),
                    'skill_matches': match.get('skill_matches'),
                    'skill_gaps_detailed': match.get('skill_gaps_detailed'),
                    'match_engine': 'gemini',
                    'match_confidence': match.get('match_confidence'),
                }

            result = crud.create_match_result(
                db=db_session,
                job_id=match['job_id'],
                resume_id=resume_id,
                match_score=score_as_percentage,
                matching_skills=match['matching_skills'],
                experience_alignment=experience_alignment_text,
                engine_version=match.get('engine_version'),
                gemini_score=gemini_score,
                gemini_reasoning=match.get('gemini_reasoning'),
                missing_domains=match.get('missing_domains'),
                **ai_fields
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
