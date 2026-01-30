"""Resume Bullet Point Targeter module.

This module provides tools for analyzing resume alignment against job descriptions
and generating AI-powered suggestions for improving bullet points.
"""

from src.targeting.role_analyzer import (
    RoleAnalyzer,
    RoleAnalysis,
    BulletScore,
)
from src.targeting.bullet_rewriter import (
    BulletRewriter,
    RewriteResult,
    get_rewriter,
)
from src.targeting.exporter import (
    ResumeExporter,
    BulletChange,
    ExportResult,
    get_exporter,
)

__all__ = [
    'RoleAnalyzer',
    'RoleAnalysis',
    'BulletScore',
    'BulletRewriter',
    'RewriteResult',
    'get_rewriter',
    'ResumeExporter',
    'BulletChange',
    'ExportResult',
    'get_exporter',
]
