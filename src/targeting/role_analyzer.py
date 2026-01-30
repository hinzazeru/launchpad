"""Role analyzer for comparing resume roles against job descriptions.

Uses NLP embeddings to score alignment between resume bullets and JD requirements.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import logging

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from src.resume.parser import ResumeRole, ResumeStructure, ResumeParser

logger = logging.getLogger(__name__)


@dataclass
class BulletScore:
    """Score and analysis for a single resume bullet point."""
    original: str
    score: float  # 0.0-1.0 alignment score
    matched_keywords: List[str] = field(default_factory=list)
    missing_keywords: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)  # AI alternatives (populated later)
    analysis: str = ""  # AI explanation of why score is low (populated later)


@dataclass
class RoleAnalysis:
    """Complete analysis of a resume role against a job description."""
    role: ResumeRole
    alignment_score: float  # 0.0-1.0 overall score for this role
    bullet_scores: List[BulletScore] = field(default_factory=list)

    @property
    def low_scoring_bullets(self) -> List[BulletScore]:
        """Get bullets that need improvement (below 70% threshold)."""
        return [b for b in self.bullet_scores if b.score < 0.7]

    @property
    def high_scoring_bullets(self) -> List[BulletScore]:
        """Get bullets that are well-aligned (70%+ threshold)."""
        return [b for b in self.bullet_scores if b.score >= 0.7]


class RoleAnalyzer:
    """Analyzes resume roles against job descriptions using NLP similarity."""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize with sentence transformer model.

        Args:
            model_name: HuggingFace model name for embeddings
        """
        self.model = SentenceTransformer(model_name)
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self.parser = ResumeParser()

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get cached embedding for text."""
        if text not in self._embedding_cache:
            self._embedding_cache[text] = self.model.encode(text)
        return self._embedding_cache[text]

    def _extract_jd_requirements(self, job_description: str) -> List[str]:
        """Extract key requirement sentences from job description.

        Args:
            job_description: Full job description text

        Returns:
            List of requirement/responsibility sentences
        """
        # Split into sentences/bullets
        lines = []
        for line in job_description.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Clean bullet markers
            if line.startswith(('-', '•', '*', '·')):
                line = line[1:].strip()
            if len(line) > 20:  # Filter out headers/short lines
                lines.append(line)

        return lines

    def _calculate_bullet_score(
        self,
        bullet: str,
        jd_requirements: List[str],
        jd_embeddings: np.ndarray
    ) -> Tuple[float, List[str], List[str]]:
        """Calculate alignment score for a single bullet.

        Args:
            bullet: Resume bullet text
            jd_requirements: List of JD requirement strings
            jd_embeddings: Pre-computed embeddings for JD requirements

        Returns:
            Tuple of (score, matched_keywords, missing_keywords)
        """
        bullet_embedding = self._get_embedding(bullet)

        # Calculate similarity to each JD requirement
        similarities = cosine_similarity(
            bullet_embedding.reshape(1, -1),
            jd_embeddings
        )[0]

        # Get top matching requirements
        top_indices = np.argsort(similarities)[-3:][::-1]

        matched_keywords = []
        missing_keywords = []

        for idx in top_indices:
            if similarities[idx] >= 0.4:
                # Extract key terms from matching requirement
                matched_keywords.append(jd_requirements[idx][:50] + "...")

        # Find requirements with low similarity (potential gaps)
        low_sim_indices = np.where(similarities < 0.3)[0][:3]
        for idx in low_sim_indices:
            missing_keywords.append(jd_requirements[idx][:50] + "...")

        # Score is the max similarity (how well this bullet matches ANY requirement)
        score = float(np.max(similarities))

        # Normalize to 0-1 range (cosine similarity is already -1 to 1, but usually positive)
        score = max(0.0, min(1.0, score))

        return score, matched_keywords, missing_keywords

    def analyze_role(
        self,
        role: ResumeRole,
        job_description: str,
        job_title: str = ""
    ) -> RoleAnalysis:
        """Analyze a single resume role against a job description.

        Args:
            role: ResumeRole to analyze
            job_description: Full job description text
            job_title: Optional job title for context

        Returns:
            RoleAnalysis with scores for each bullet
        """
        # Extract requirements from JD
        jd_requirements = self._extract_jd_requirements(job_description)

        if not jd_requirements:
            logger.warning("No requirements extracted from job description")
            return RoleAnalysis(
                role=role,
                alignment_score=0.0,
                bullet_scores=[]
            )

        # Pre-compute JD embeddings
        jd_embeddings = np.array([self._get_embedding(req) for req in jd_requirements])

        # Score each bullet
        bullet_scores = []
        total_score = 0.0

        for bullet in role.bullets:
            score, matched, missing = self._calculate_bullet_score(
                bullet, jd_requirements, jd_embeddings
            )

            bullet_scores.append(BulletScore(
                original=bullet,
                score=score,
                matched_keywords=matched,
                missing_keywords=missing
            ))
            total_score += score

        # Overall role alignment is average of bullet scores
        alignment_score = total_score / len(role.bullets) if role.bullets else 0.0

        return RoleAnalysis(
            role=role,
            alignment_score=alignment_score,
            bullet_scores=bullet_scores
        )

    def analyze_all_roles(
        self,
        resume_text: str,
        job_description: str,
        job_title: str = ""
    ) -> List[RoleAnalysis]:
        """Analyze all roles in a resume against a job description.

        Args:
            resume_text: Full resume text
            job_description: Full job description text
            job_title: Optional job title for context

        Returns:
            List of RoleAnalysis, one per resume role
        """
        # Parse resume
        resume_structure = self.parser.parse_auto(resume_text)

        # Analyze each role
        analyses = []
        for role in resume_structure.roles:
            analysis = self.analyze_role(role, job_description, job_title)
            analyses.append(analysis)

        # Sort by alignment score (highest first)
        analyses.sort(key=lambda a: a.alignment_score, reverse=True)

        return analyses

    def get_overall_alignment(self, analyses: List[RoleAnalysis]) -> float:
        """Calculate overall resume alignment from role analyses.

        Args:
            analyses: List of RoleAnalysis objects

        Returns:
            Overall alignment score (0.0-1.0)
        """
        if not analyses:
            return 0.0

        # Weight by recency (first roles in list are more relevant)
        weights = [1.0 / (i + 1) for i in range(len(analyses))]
        total_weight = sum(weights)

        weighted_sum = sum(
            a.alignment_score * w
            for a, w in zip(analyses, weights)
        )

        return weighted_sum / total_weight


def get_analyzer() -> RoleAnalyzer:
    """Factory function to get a RoleAnalyzer instance."""
    return RoleAnalyzer()
