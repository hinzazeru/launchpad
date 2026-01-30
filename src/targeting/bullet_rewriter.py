"""Bullet rewriter module for generating AI-powered suggestions.

Wraps the GeminiBulletRewriter and integrates with RoleAnalysis.
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from src.integrations.gemini_client import GeminiBulletRewriter, get_bullet_rewriter
from src.targeting.role_analyzer import RoleAnalysis, BulletScore

logger = logging.getLogger(__name__)


@dataclass
class RewriteResult:
    """Result of rewriting bullets for a role."""
    role_title: str
    role_company: str
    bullets_processed: int
    bullets_rewritten: int
    results: List[BulletScore]


class BulletRewriter:
    """High-level interface for rewriting resume bullets."""

    def __init__(self, threshold: float = 0.7):
        """Initialize the bullet rewriter.

        Args:
            threshold: Only rewrite bullets with scores below this value
        """
        self.threshold = threshold
        self._gemini = get_bullet_rewriter()

    def is_available(self) -> bool:
        """Check if Gemini rewriting is available."""
        return self._gemini is not None and self._gemini.is_available()

    def rewrite_role_bullets(
        self,
        analysis: RoleAnalysis,
        job_title: str,
        company: str,
        job_description: str
    ) -> RewriteResult:
        """Generate AI suggestions for bullets in a role analysis.

        Args:
            analysis: RoleAnalysis object with scored bullets
            job_title: Target job title
            company: Target company name
            job_description: Full job description text

        Returns:
            RewriteResult with updated bullet scores including suggestions
        """
        if not self.is_available():
            logger.warning("Gemini not available, skipping bullet rewriting")
            return RewriteResult(
                role_title=analysis.role.title,
                role_company=analysis.role.company,
                bullets_processed=len(analysis.bullet_scores),
                bullets_rewritten=0,
                results=analysis.bullet_scores
            )

        updated_bullets = []
        bullets_rewritten = 0

        # Get all bullet texts for context
        all_bullets = [b.original for b in analysis.bullet_scores]

        for bullet_score in analysis.bullet_scores:
            if bullet_score.score < self.threshold:
                # Get other bullets for context
                other_bullets = [b for b in all_bullets if b != bullet_score.original]

                # Call Gemini for suggestions
                result = self._gemini.rewrite_bullet(
                    original_bullet=bullet_score.original,
                    score=bullet_score.score,
                    job_title=job_title,
                    company=company,
                    job_description=job_description,
                    role_title=analysis.role.title,
                    role_company=analysis.role.company,
                    other_bullets=other_bullets
                )

                # Update bullet score with suggestions and analysis
                bullet_score.suggestions = result.get('suggestions', [])
                bullet_score.analysis = result.get('analysis', '')
                bullets_rewritten += 1

                logger.debug(
                    f"Generated {len(bullet_score.suggestions)} suggestions for bullet: "
                    f"{bullet_score.original[:50]}..."
                )

            updated_bullets.append(bullet_score)

        return RewriteResult(
            role_title=analysis.role.title,
            role_company=analysis.role.company,
            bullets_processed=len(updated_bullets),
            bullets_rewritten=bullets_rewritten,
            results=updated_bullets
        )

    def rewrite_all_roles(
        self,
        analyses: List[RoleAnalysis],
        job_title: str,
        company: str,
        job_description: str
    ) -> List[RewriteResult]:
        """Generate AI suggestions for all roles.

        Args:
            analyses: List of RoleAnalysis objects
            job_title: Target job title
            company: Target company name
            job_description: Full job description text

        Returns:
            List of RewriteResult objects
        """
        results = []

        for i, analysis in enumerate(analyses):
            logger.info(
                f"Processing role {i+1}/{len(analyses)}: "
                f"{analysis.role.title} @ {analysis.role.company}"
            )

            result = self.rewrite_role_bullets(
                analysis=analysis,
                job_title=job_title,
                company=company,
                job_description=job_description
            )
            results.append(result)

        total_rewritten = sum(r.bullets_rewritten for r in results)
        logger.info(f"Completed: {total_rewritten} bullets rewritten across {len(results)} roles")

        return results


def get_rewriter(threshold: float = 0.7) -> BulletRewriter:
    """Factory function to get a BulletRewriter instance.

    Args:
        threshold: Score threshold for rewriting

    Returns:
        BulletRewriter instance
    """
    return BulletRewriter(threshold=threshold)
