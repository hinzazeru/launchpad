"""Main matching engine for comparing resumes against job postings.

This module orchestrates the job matching process by combining skills matching
(NLP-based semantic similarity), experience matching (rule-based years comparison),
and domain matching (industry expertise alignment) to produce an overall compatibility score.

Score Calculation:
    Overall Score = (Skills × skills_weight) + (Experience × experience_weight) + (Domains × domains_weight)

    Default weights: skills=0.45, experience=0.35, domains=0.20 (configurable in config.yaml).

Key Classes:
    JobMatcher: Main matching orchestrator that combines skills, experience, and domain scores

Key Functions:
    create_job_matcher(): Factory function to create a JobMatcher instance

Usage Example:
    >>> from src.matching.engine import JobMatcher
    >>> from src.database.models import Resume, JobPosting
    >>>
    >>> matcher = JobMatcher()
    >>> result = matcher.match_job(resume, job_posting)
    >>> print(f"Match score: {result['overall_score'] * 100}%")
    >>> print(f"Matching skills: {result['matching_skills']}")
    >>> print(f"Skill gaps: {result['skill_gaps']}")
    >>> print(f"Missing domains: {result['missing_domains']}")

Configuration (config.yaml):
    matching:
      weights:
        skills: 0.45      # Weight for skills match
        experience: 0.35  # Weight for experience match
        domains: 0.20     # Weight for domain match
      min_match_score: 0.6  # Minimum score threshold
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from src.matching.skills_matcher import SkillsMatcher
from src.matching.skill_extractor import extract_skills_from_description, ALL_SKILLS
from src.database import crud
from src.database.models import Resume, JobPosting, MatchResult
from src.config import get_config

logger = logging.getLogger(__name__)


class JobMatcher:
    """Job matching engine that scores jobs against a resume."""

    def __init__(self, skills_matcher: Optional[SkillsMatcher] = None, preload_cache: bool = True):
        """Initialize job matcher.

        Args:
            skills_matcher: SkillsMatcher instance. If None, creates a new one.
            preload_cache: If True, pre-cache skill dictionary embeddings for performance.
        """
        # Pre-load skill dictionary embeddings for faster matching
        if skills_matcher:
            self.skills_matcher = skills_matcher
        elif preload_cache:
            logger.info("Initializing JobMatcher with pre-cached skill embeddings...")
            # Convert set to list for the skill dictionary
            skill_list = list(ALL_SKILLS)
            self.skills_matcher = SkillsMatcher(preload_skills=skill_list)
        else:
            self.skills_matcher = SkillsMatcher()

        self.config = get_config()

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
        skills_threshold: float = 0.5
    ) -> Dict:
        """Match a single job against a resume.

        Args:
            resume: Resume object from database
            job: JobPosting object from database
            skills_threshold: Minimum similarity for skill matching

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
            'extracted_skills': extracted_skills,  # Include for debugging
            'resume_years': resume.experience_years or 0,
            'job_years_required': job.experience_required,
            'engine_version': self.engine_version,
        }

    def match_jobs(
        self,
        resume: Resume,
        jobs: List[JobPosting],
        min_score: Optional[float] = None,
        top_n: Optional[int] = None
    ) -> List[Dict]:
        """Match multiple jobs against a resume and rank them.

        Args:
            resume: Resume object from database
            jobs: List of JobPosting objects
            min_score: Minimum overall score to include (uses config default if None)
            top_n: Return only top N matches (returns all if None)

        Returns:
            List of match dictionaries, sorted by overall_score descending.
            Each dict includes all match_job() results plus job details.
        """
        if min_score is None:
            min_score = self.config.get_min_match_score()

        matches = []

        for job in jobs:
            match_result = self.match_job(resume, job)

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

        return matches

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

            # Convert Gemini score from 0-1 to 0-100 (if present)
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
                missing_domains=match.get('missing_domains')
            )
            saved_results.append(result)

        return saved_results


def create_job_matcher(
    skills_matcher: Optional[SkillsMatcher] = None,
    preload_cache: bool = True
) -> JobMatcher:
    """Factory function to create a JobMatcher instance.

    Args:
        skills_matcher: Optional SkillsMatcher instance
        preload_cache: If True, pre-cache skill dictionary embeddings

    Returns:
        JobMatcher instance
    """
    return JobMatcher(skills_matcher=skills_matcher, preload_cache=preload_cache)
