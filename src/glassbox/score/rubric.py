"""Transparent rubric-based resume/JD matching.

Design constraint: **every point in the final score traces to a named requirement and
a quoted span of the resume.** There are no learned weights, no embeddings, and no
opaque similarity number. If a candidate scores 0.62, the report says which
requirements contributed what, and where in the document each match was found.

This is deliberately less clever than an embedding reranker, and that is the point. A
selection procedure that produces adverse impact must be defensible as job-related
under 29 CFR 1607.14. "Cosine similarity to the job description was 0.71" is not a
defence; "the candidate evidenced 4 of 5 required skills, and here are the lines" is.

Rubrics are also auditable input: :mod:`glassbox.audit.perturb` can run against a
rubric scorer to verify it is counterfactually invariant to names and pronouns, which
a keyword rubric trivially is -- and which an embedding scorer often is not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

__all__ = [
    "Evidence",
    "MatchResult",
    "Requirement",
    "RequirementScore",
    "Rubric",
    "score_resume",
]


def _normalise(text: str) -> str:
    """Casefold, strip accents, and collapse whitespace for robust matching.

    Accent stripping matters: a resume written "Zoë Martínez, Software Engineer" should
    match a "Martinez" or plain-ASCII requirement rather than silently missing.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).casefold()


@dataclass(frozen=True)
class Requirement:
    """One job requirement.

    Args:
        name: Human-readable label, e.g. ``"Python"``.
        patterns: Surface forms that evidence this requirement. Matched as whole words,
            case- and accent-insensitively. Include real synonyms
            (``["postgres", "postgresql"]``); do not include unrelated terms.
        weight: Relative contribution. Only ratios matter -- weights are normalised.
        required: If True, absence is reported as a hard gap. Required items still
            contribute their weight rather than zeroing the score, so a report can
            distinguish "close but missing one hard requirement" from "unqualified".
        category: Grouping label for reporting, e.g. ``"language"``, ``"tooling"``.

    Raises:
        ValueError: If ``patterns`` is empty or ``weight`` is not positive.
    """

    name: str
    patterns: tuple[str, ...]
    weight: float = 1.0
    required: bool = False
    category: str = "general"

    def __post_init__(self) -> None:
        if not self.patterns:
            raise ValueError(f"{self.name}: needs at least one pattern")
        if self.weight <= 0:
            raise ValueError(f"{self.name}: weight must be positive, got {self.weight}")


@dataclass(frozen=True)
class Evidence:
    """Where a requirement was matched.

    Attributes:
        pattern: The surface form that matched.
        line_number: 1-based line in the resume text.
        line: The full line, for display.
        start: Character offset of the match within the line.
    """

    pattern: str
    line_number: int
    line: str
    start: int


@dataclass(frozen=True)
class RequirementScore:
    """Per-requirement outcome."""

    requirement: Requirement
    matched: bool
    evidence: list[Evidence]
    weight_share: float
    points: float

    @property
    def missing_required(self) -> bool:
        """A hard requirement with no supporting evidence."""
        return self.requirement.required and not self.matched


@dataclass
class MatchResult:
    """Complete, attributable match outcome."""

    score: float
    requirement_scores: list[RequirementScore]
    resume_lines: list[str] = field(repr=False, default_factory=list)

    @property
    def matched(self) -> list[RequirementScore]:
        return [r for r in self.requirement_scores if r.matched]

    @property
    def gaps(self) -> list[RequirementScore]:
        """Unmatched requirements, most costly first."""
        return sorted(
            (r for r in self.requirement_scores if not r.matched),
            key=lambda r: r.weight_share,
            reverse=True,
        )

    @property
    def missing_required(self) -> list[RequirementScore]:
        return [r for r in self.requirement_scores if r.missing_required]

    def explain(self) -> str:
        """Render a full plain-text attribution of the score.

        The output accounts for 100% of the score. Anything a reader cannot find here
        did not contribute.

        Note:
            The result contains ``✓`` and ``✗``, which the default Windows console
            codepage (cp1252) cannot encode -- ``print()`` raises ``UnicodeEncodeError``
            there. Reconfigure the stream first::

                sys.stdout.reconfigure(encoding="utf-8", errors="replace")

            The ``glassbox`` CLI does this internally; see ``examples/end_to_end.py``
            for the same two lines in a standalone script.
        """
        lines = [
            f"Match score: {self.score:.3f}",
            "",
            "Every point below traces to a requirement and a line of the resume.",
            "",
        ]

        if self.missing_required:
            lines.append("MISSING REQUIRED:")
            lines.extend(
                f"  ✗ {r.requirement.name}  (would add {r.weight_share:.3f})"
                for r in self.missing_required
            )
            lines.append("")

        lines.append("MATCHED:")
        if not self.matched:
            lines.append("  (none)")
        for result in sorted(self.matched, key=lambda r: r.points, reverse=True):
            first = result.evidence[0]
            lines.append(
                f"  ✓ {result.requirement.name:<24} +{result.points:.3f}  "
                f"line {first.line_number}: {first.line.strip()[:60]!r}"
            )

        optional_gaps = [r for r in self.gaps if not r.requirement.required]
        if optional_gaps:
            lines.extend(["", "NOT EVIDENCED:"])
            lines.extend(
                f"  · {r.requirement.name:<24} (would add {r.weight_share:.3f})"
                for r in optional_gaps
            )

        return "\n".join(lines)


@dataclass
class Rubric:
    """A weighted set of requirements.

    Args:
        requirements: The requirements.
        name: Label for the role.

    Raises:
        ValueError: If no requirements are supplied or names are not unique.
    """

    requirements: list[Requirement]
    name: str = "unnamed role"

    def __post_init__(self) -> None:
        if not self.requirements:
            raise ValueError("rubric needs at least one requirement")
        names = [r.name for r in self.requirements]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate requirement names: {sorted(duplicates)}")

    @property
    def total_weight(self) -> float:
        return sum(r.weight for r in self.requirements)

    @classmethod
    def from_skills(
        cls,
        required: list[str] | None = None,
        preferred: list[str] | None = None,
        *,
        name: str = "unnamed role",
        required_weight: float = 2.0,
    ) -> Rubric:
        """Build a rubric from plain skill lists.

        Args:
            required: Must-have skills.
            preferred: Nice-to-have skills.
            name: Role label.
            required_weight: Weight of a required skill relative to a preferred one.

        Returns:
            A :class:`Rubric`.

        Raises:
            ValueError: If both lists are empty.
        """
        requirements = [
            Requirement(
                skill, (skill,), weight=required_weight, required=True, category="required"
            )
            for skill in (required or [])
        ]
        requirements += [
            Requirement(skill, (skill,), weight=1.0, category="preferred")
            for skill in (preferred or [])
        ]
        if not requirements:
            raise ValueError("supply at least one required or preferred skill")
        return cls(requirements, name=name)


def _find_evidence(pattern: str, lines: list[str], normalised: list[str]) -> list[Evidence]:
    """Locate whole-word occurrences of ``pattern`` across resume lines."""
    needle = _normalise(pattern)
    if not needle:
        return []

    # Word-boundary match on the normalised text. Patterns containing regex
    # metacharacters (C++, .NET) are escaped; \b behaves poorly next to non-word
    # characters, so we anchor on a lookaround that accepts any non-alphanumeric.
    escaped = re.escape(needle)
    regex = re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")

    return [
        Evidence(pattern=pattern, line_number=index + 1, line=lines[index], start=match.start())
        for index, haystack in enumerate(normalised)
        if (match := regex.search(haystack))
    ]


def score_resume(resume_text: str, rubric: Rubric) -> MatchResult:
    """Score a resume against a rubric.

    Args:
        resume_text: Plain text of the resume, ideally from
            :func:`glassbox.parse.layout.column_aware_reading_order`.
        rubric: The rubric to score against.

    Returns:
        A :class:`MatchResult` whose ``score`` lies in [0, 1] and whose per-requirement
        breakdown sums exactly to it.
    """
    lines = resume_text.split("\n")
    normalised = [_normalise(line) for line in lines]
    total_weight = rubric.total_weight

    scores = []
    for requirement in rubric.requirements:
        evidence: list[Evidence] = []
        for pattern in requirement.patterns:
            evidence.extend(_find_evidence(pattern, lines, normalised))

        weight_share = requirement.weight / total_weight
        matched = bool(evidence)
        scores.append(
            RequirementScore(
                requirement=requirement,
                matched=matched,
                evidence=evidence,
                weight_share=weight_share,
                points=weight_share if matched else 0.0,
            )
        )

    return MatchResult(
        score=sum(s.points for s in scores),
        requirement_scores=scores,
        resume_lines=lines,
    )
