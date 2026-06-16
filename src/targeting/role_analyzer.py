"""Role analyzer for comparing resume roles against job descriptions.

Uses Gemini to score how well each resume bullet aligns with a job description's
requirements. There is no NLP/embedding fallback — if Gemini is unavailable,
analysis raises so the caller can return a clear "retry later" error.
"""

from typing import List, Dict
from dataclasses import dataclass, field
import logging

from src.resume.parser import ResumeRole, ResumeParser

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
    """Analyzes resume roles against job descriptions using Gemini scoring."""

    def __init__(self):
        """Initialize with a Gemini bullet scorer.

        The scorer is None if Gemini is not configured/available; callers should
        check is_available() and surface a 503 rather than calling analyze_*.
        """
        from src.integrations.gemini_client import get_bullet_rewriter
        self.scorer = get_bullet_rewriter()
        self.parser = ResumeParser()

    def is_available(self) -> bool:
        """Check if Gemini-based scoring is available."""
        return self.scorer is not None and self.scorer.is_available()

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

        Raises:
            RuntimeError: If Gemini scoring is unavailable.
        """
        if not role.bullets:
            return RoleAnalysis(role=role, alignment_score=0.0, bullet_scores=[])

        if not self.is_available():
            raise RuntimeError("Gemini scoring unavailable — cannot analyze role")

        scored = self.scorer.score_bullets(role.bullets, job_description, job_title)

        bullet_scores: List[BulletScore] = []
        total_score = 0.0
        for bullet, result in zip(role.bullets, scored):
            score = result.get("score", 0.0)
            bullet_scores.append(BulletScore(
                original=bullet,
                score=score,
                matched_keywords=result.get("matched", []),
                missing_keywords=result.get("missing", []),
            ))
            total_score += score

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
            List of RoleAnalysis, one per resume role, sorted by alignment desc.

        Raises:
            RuntimeError: If Gemini scoring is unavailable.
        """
        if not self.is_available():
            raise RuntimeError("Gemini scoring unavailable — cannot analyze resume")

        resume_structure = self.parser.parse_auto(resume_text)

        analyses = []
        for role in resume_structure.roles:
            analyses.append(self.analyze_role(role, job_description, job_title))

        # Sort by alignment score (highest first)
        analyses.sort(key=lambda a: a.alignment_score, reverse=True)

        return analyses

    def get_overall_alignment(self, analyses: List[RoleAnalysis]) -> float:
        """Calculate overall resume alignment from role analyses.

        Args:
            analyses: List of RoleAnalysis objects

        Returns:
            Overall alignment score (0.0-1.0), weighted by recency.
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
