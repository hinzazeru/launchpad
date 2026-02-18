"""Skills matching using semantic similarity.

This module provides NLP-based skill matching using sentence-transformers for
semantic similarity. It also supports related skills matching where partial
credit is given for skills that are related but not exact matches.

Key Features:
    - Semantic similarity matching using embeddings
    - Related skills support with configurable partial credit
    - Embedding caching for performance
    - Skill gap analysis

Related Skills:
    When a job requires "Python" but the resume has "Data Science", the matcher
    can recognize these as related skills (if configured in skill_relationships.json)
    and give partial credit (default 0.7x).
"""

import logging
import threading
from typing import List, Tuple, Dict, Optional
from sentence_transformers import SentenceTransformer, util
import numpy as np

from src.matching.skill_extractor import (
    get_related_skills,
    get_related_skill_weight,
    is_related_skill,
)

logger = logging.getLogger(__name__)


class SkillsMatcher:
    """Semantic skills matcher using sentence-transformers."""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', preload_skills: Optional[List[str]] = None):
        """Initialize skills matcher with sentence transformer model.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default is 'all-MiniLM-L6-v2' (fast and accurate for semantic similarity)
            preload_skills: Optional list of skills to pre-cache embeddings for.
                           This improves performance by computing embeddings once at startup.
        """
        self.model = SentenceTransformer(model_name)
        self._cache = {}  # Cache embeddings for performance
        self._cache_lock = threading.Lock()  # Thread safety for cache access

        # Pre-cache embeddings if skills provided
        if preload_skills:
            self.preload_embeddings(preload_skills)

    def preload_embeddings(self, skills: List[str]) -> int:
        """Pre-compute and cache embeddings for given skills.

        Args:
            skills: List of skill strings to pre-cache

        Returns:
            Number of new skills cached
        """
        # Normalize skills
        normalized = [s.strip().lower() for s in skills]

        with self._cache_lock:
            # Filter out already cached skills
            uncached = [s for s in normalized if s not in self._cache]

            if not uncached:
                logger.debug("All skills already cached")
                return 0

            # Batch encode all uncached skills at once (more efficient)
            logger.info(f"Pre-caching embeddings for {len(uncached)} skills...")
            embeddings = self.model.encode(uncached, convert_to_tensor=False, show_progress_bar=False)

            for skill, emb in zip(uncached, embeddings):
                self._cache[skill] = emb

            logger.info(f"Pre-cached {len(uncached)} skill embeddings (total cache: {len(self._cache)})")
            return len(uncached)

    def calculate_skills_match(
        self,
        resume_skills: List[str],
        job_skills: List[str],
        threshold: float = 0.5,
        use_related_skills: bool = True,
        weights: Optional[Dict[str, float]] = None
    ) -> Tuple[float, List[str], Dict[str, float]]:
        """Calculate skills match score using semantic similarity and related skills.

        The matching process:
        1. First, check for semantic similarity matches (full credit)
        2. For unmatched skills, check if resume has related skills (partial credit)

        Args:
            resume_skills: List of skills from resume
            job_skills: List of required skills from job posting
            threshold: Minimum similarity threshold to consider a match (0.0-1.0)
            use_related_skills: Whether to check for related skills (default True)
            weights: Optional dict of job_skill -> importance weight. When provided,
                     the score is a weighted average (e.g. must-have=2.0, nice-to-have=1.0).
                     When None, all skills are weighted equally (backward-compatible).

        Returns:
            Tuple of:
                - Match score (0.0-1.0): Weighted percentage of job skills matched
                - List of matching skills from resume
                - Dict of job_skill -> match details with similarity scores

        Example:
            resume = ["Python", "Data Analysis", "SQL"]
            job = ["Python Programming", "Database Queries", "JavaScript"]
            score, matches, details = matcher.calculate_skills_match(resume, job)
            # score ≈ 0.67 (Python and SQL match, JavaScript doesn't)
            # matches = ["Python", "SQL"]
            # details = {"Python Programming": {"matched_skill": "Python", "similarity": 0.85, "match_type": "direct"}, ...}
        """
        if not job_skills:
            return 0.3, [], {}  # Penalize sparse job descriptions

        if not resume_skills:
            return 0.0, [], {}  # No skills = no match

        # Normalize skills (lowercase, strip)
        resume_skills_norm = [s.strip().lower() for s in resume_skills]
        job_skills_norm = [s.strip().lower() for s in job_skills]

        # Get embeddings
        resume_embeddings = self._get_embeddings(resume_skills_norm)
        job_embeddings = self._get_embeddings(job_skills_norm)

        # Calculate similarity matrix
        similarity_matrix = util.cos_sim(job_embeddings, resume_embeddings)

        # For each job skill, find best matching resume skill
        matched_skills = []
        match_details = {}
        total_score = 0.0  # Accumulate weighted scores
        related_skill_weight = get_related_skill_weight() if use_related_skills else 0.0

        for i, job_skill in enumerate(job_skills):
            job_skill_norm = job_skills_norm[i]

            # Get similarity scores for this job skill against all resume skills
            similarities = similarity_matrix[i].numpy()
            best_match_idx = int(np.argmax(similarities))
            best_score = float(similarities[best_match_idx])

            if best_score >= threshold:
                # Direct semantic match - full credit
                total_score += 1.0
                matched_resume_skill = resume_skills[best_match_idx]
                matched_skills.append(matched_resume_skill)
                match_details[job_skill] = {
                    'matched_skill': matched_resume_skill,
                    'similarity': best_score,
                    'match_type': 'direct',
                    'credit': 1.0
                }
            elif use_related_skills:
                # Check for related skills match
                related_match = self._find_related_skill_match(
                    job_skill_norm,
                    resume_skills,
                    resume_skills_norm
                )
                if related_match:
                    # Related skill match - partial credit
                    total_score += related_skill_weight
                    matched_skills.append(related_match['resume_skill'])
                    match_details[job_skill] = {
                        'matched_skill': related_match['resume_skill'],
                        'similarity': related_skill_weight,  # Use weight as similarity for related
                        'match_type': 'related',
                        'credit': related_skill_weight,
                        'relationship': f"{job_skill_norm} ↔ {related_match['resume_skill_norm']}"
                    }

        # Calculate overall match score
        if weights:
            # Weighted average: must-have skills count more than nice-to-have
            total_weight = sum(weights.get(s, 1.0) for s in job_skills)
            weighted_credit = sum(
                match_details.get(s, {}).get('credit', 0.0) * weights.get(s, 1.0)
                for s in job_skills
            )
            match_score = weighted_credit / total_weight if total_weight > 0 else 0.0
        else:
            match_score = total_score / len(job_skills) if job_skills else 0.0

        # Remove duplicates from matched_skills while preserving order
        unique_matched_skills = list(dict.fromkeys(matched_skills))

        return match_score, unique_matched_skills, match_details

    def _find_related_skill_match(
        self,
        job_skill: str,
        resume_skills: List[str],
        resume_skills_norm: List[str]
    ) -> Optional[Dict]:
        """Find a related skill match from resume skills.

        Args:
            job_skill: Job skill to match (lowercase)
            resume_skills: Original resume skills list
            resume_skills_norm: Normalized (lowercase) resume skills

        Returns:
            Dict with match info if found, None otherwise
        """
        # Get skills related to this job skill
        related_to_job = set(get_related_skills(job_skill))

        if not related_to_job:
            return None

        # Check if any resume skill is in the related skills list
        for idx, resume_skill_norm in enumerate(resume_skills_norm):
            if resume_skill_norm in related_to_job:
                return {
                    'resume_skill': resume_skills[idx],
                    'resume_skill_norm': resume_skill_norm
                }

            # Also check reverse: if resume skill has job_skill as related
            related_to_resume = set(get_related_skills(resume_skill_norm))
            if job_skill in related_to_resume:
                return {
                    'resume_skill': resume_skills[idx],
                    'resume_skill_norm': resume_skill_norm
                }

        return None

    def _get_embeddings(self, skills: List[str]) -> np.ndarray:
        """Get embeddings for skills with caching.

        Args:
            skills: List of skill strings

        Returns:
            numpy array of embeddings
        """
        with self._cache_lock:
            # Check cache for each skill
            uncached_skills = []
            uncached_indices = []

            for i, skill in enumerate(skills):
                if skill not in self._cache:
                    uncached_skills.append(skill)
                    uncached_indices.append(i)

            # Compute embeddings for uncached skills
            if uncached_skills:
                new_embeddings = self.model.encode(uncached_skills, convert_to_tensor=False)
                for skill, embedding in zip(uncached_skills, new_embeddings):
                    self._cache[skill] = embedding

            # Retrieve all embeddings from cache
            embeddings = [self._cache[skill] for skill in skills]

            return np.array(embeddings)

    def find_skill_gaps(
        self,
        resume_skills: List[str],
        job_skills: List[str],
        threshold: float = 0.5
    ) -> List[str]:
        """Identify job skills not covered by resume.

        Args:
            resume_skills: List of skills from resume
            job_skills: List of required skills from job posting
            threshold: Minimum similarity threshold

        Returns:
            List of job skills that are not matched by resume skills
        """
        if not job_skills:
            return []

        _, _, match_details = self.calculate_skills_match(
            resume_skills, job_skills, threshold
        )

        # Skills that weren't matched
        gaps = [skill for skill in job_skills if skill not in match_details]

        return gaps

    def clear_cache(self):
        """Clear the embedding cache."""
        with self._cache_lock:
            self._cache = {}


def create_skills_matcher(
    model_name: str = 'all-MiniLM-L6-v2',
    preload_skills: Optional[List[str]] = None
) -> SkillsMatcher:
    """Factory function to create a SkillsMatcher instance.

    Args:
        model_name: Name of sentence-transformers model
        preload_skills: Optional list of skills to pre-cache embeddings for

    Returns:
        SkillsMatcher instance
    """
    return SkillsMatcher(model_name=model_name, preload_skills=preload_skills)
