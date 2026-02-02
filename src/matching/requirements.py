"""Structured job requirements model for LLM-based matching."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum
from datetime import datetime


class SkillLevel(str, Enum):
    """Skill proficiency levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SeniorityLevel(str, Enum):
    """Job seniority levels."""
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    DIRECTOR = "director"


class RoleFocus(str, Enum):
    """Role focus type."""
    TECHNICAL = "technical"
    STRATEGIC = "strategic"
    HYBRID = "hybrid"


@dataclass
class SkillRequirement:
    """A single skill requirement with context."""
    name: str
    context: Optional[str] = None  # e.g., "for data pipelines", "in production environments"
    level: SkillLevel = SkillLevel.INTERMEDIATE
    years: Optional[int] = None  # Specific years required for this skill

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "context": self.context,
            "level": self.level.value if isinstance(self.level, SkillLevel) else self.level,
            "years": self.years
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillRequirement":
        level = data.get("level", "intermediate")
        if isinstance(level, str):
            try:
                level = SkillLevel(level)
            except ValueError:
                level = SkillLevel.INTERMEDIATE
        return cls(
            name=data.get("name", ""),
            context=data.get("context"),
            level=level,
            years=data.get("years")
        )


@dataclass
class StructuredRequirements:
    """
    Structured requirements extracted from a job description.

    This model captures the key requirements in a format optimized for
    LLM-based matching, distinguishing must-have from nice-to-have skills,
    capturing seniority expectations, and providing context for skills.
    """
    # Skills with importance levels
    must_have_skills: List[SkillRequirement] = field(default_factory=list)
    nice_to_have_skills: List[SkillRequirement] = field(default_factory=list)

    # Experience requirements
    min_years: Optional[int] = None
    max_years: Optional[int] = None  # For detecting overqualification
    seniority_level: SeniorityLevel = SeniorityLevel.MID

    # Domain requirements
    required_domains: List[str] = field(default_factory=list)
    preferred_domains: List[str] = field(default_factory=list)

    # Role context
    role_focus: RoleFocus = RoleFocus.HYBRID
    key_responsibilities: List[str] = field(default_factory=list)

    # Metadata
    extraction_model: str = ""
    extraction_timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "must_have_skills": [s.to_dict() for s in self.must_have_skills],
            "nice_to_have_skills": [s.to_dict() for s in self.nice_to_have_skills],
            "min_years": self.min_years,
            "max_years": self.max_years,
            "seniority_level": self.seniority_level.value if isinstance(self.seniority_level, SeniorityLevel) else self.seniority_level,
            "required_domains": self.required_domains,
            "preferred_domains": self.preferred_domains,
            "role_focus": self.role_focus.value if isinstance(self.role_focus, RoleFocus) else self.role_focus,
            "key_responsibilities": self.key_responsibilities,
            "extraction_model": self.extraction_model,
            "extraction_timestamp": self.extraction_timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StructuredRequirements":
        """Create from JSON dictionary."""
        if not data:
            return cls()

        # Parse seniority level
        seniority = data.get("seniority_level", "mid")
        if isinstance(seniority, str):
            try:
                seniority = SeniorityLevel(seniority)
            except ValueError:
                seniority = SeniorityLevel.MID

        # Parse role focus
        role_focus = data.get("role_focus", "hybrid")
        if isinstance(role_focus, str):
            try:
                role_focus = RoleFocus(role_focus)
            except ValueError:
                role_focus = RoleFocus.HYBRID

        return cls(
            must_have_skills=[SkillRequirement.from_dict(s) for s in data.get("must_have_skills", [])],
            nice_to_have_skills=[SkillRequirement.from_dict(s) for s in data.get("nice_to_have_skills", [])],
            min_years=data.get("min_years"),
            max_years=data.get("max_years"),
            seniority_level=seniority,
            required_domains=data.get("required_domains", []),
            preferred_domains=data.get("preferred_domains", []),
            role_focus=role_focus,
            key_responsibilities=data.get("key_responsibilities", []),
            extraction_model=data.get("extraction_model", ""),
            extraction_timestamp=data.get("extraction_timestamp")
        )

    def get_all_skills(self) -> List[str]:
        """Get all skill names (must-have + nice-to-have)."""
        return [s.name for s in self.must_have_skills] + [s.name for s in self.nice_to_have_skills]

    def get_must_have_skill_names(self) -> List[str]:
        """Get just must-have skill names."""
        return [s.name for s in self.must_have_skills]

    def get_nice_to_have_skill_names(self) -> List[str]:
        """Get just nice-to-have skill names."""
        return [s.name for s in self.nice_to_have_skills]


@dataclass
class SkillMatch:
    """A matched skill between job and resume."""
    job_skill: str
    resume_skill: str
    confidence: float  # 0-1 similarity score
    context: Optional[str] = None  # e.g., "Direct match", "Related skill"

    def to_dict(self) -> dict:
        return {
            "job_skill": self.job_skill,
            "resume_skill": self.resume_skill,
            "confidence": self.confidence,
            "context": self.context
        }


@dataclass
class SkillGap:
    """A skill gap identified during matching."""
    skill: str
    importance: str  # "must_have" or "nice_to_have"
    transferable_from: Optional[str] = None  # Related skill that could help

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "importance": self.importance,
            "transferable_from": self.transferable_from
        }


@dataclass
class GeminiMatchResult:
    """
    Rich matching result from Gemini LLM.

    Contains detailed scores, skill analysis, and actionable insights.
    """
    # Scores (0-100)
    overall_score: float
    skills_score: float
    experience_score: float
    seniority_fit: float
    domain_score: float

    # Detailed skill analysis
    skill_matches: List[SkillMatch] = field(default_factory=list)
    skill_gaps: List[SkillGap] = field(default_factory=list)

    # Insights
    strengths: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Metadata
    confidence: float = 0.0  # Model confidence in assessment (0-1)
    reasoning: str = ""  # Brief explanation of scoring

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "overall_score": self.overall_score,
            "skills_score": self.skills_score,
            "experience_score": self.experience_score,
            "seniority_fit": self.seniority_fit,
            "domain_score": self.domain_score,
            "skill_matches": [m.to_dict() for m in self.skill_matches],
            "skill_gaps": [g.to_dict() for g in self.skill_gaps],
            "strengths": self.strengths,
            "concerns": self.concerns,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeminiMatchResult":
        """Create from JSON dictionary."""
        return cls(
            overall_score=data.get("overall_score", 0),
            skills_score=data.get("skills_score", 0),
            experience_score=data.get("experience_score", 0),
            seniority_fit=data.get("seniority_fit", 0),
            domain_score=data.get("domain_score", 0),
            skill_matches=[
                SkillMatch(**m) for m in data.get("skill_matches", [])
            ],
            skill_gaps=[
                SkillGap(**g) for g in data.get("skill_gaps", [])
            ],
            strengths=data.get("strengths", []),
            concerns=data.get("concerns", []),
            recommendations=data.get("recommendations", []),
            confidence=data.get("confidence", 0),
            reasoning=data.get("reasoning", "")
        )
