"""Transparent, fully-attributable resume scoring."""

from .rubric import (
    Evidence,
    MatchResult,
    Requirement,
    RequirementScore,
    Rubric,
    score_resume,
)

__all__ = [
    "Evidence",
    "MatchResult",
    "Requirement",
    "RequirementScore",
    "Rubric",
    "score_resume",
]
