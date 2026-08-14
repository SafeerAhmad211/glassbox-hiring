"""Counterfactual perturbation testing for resume screeners.

Adverse-impact analysis (:mod:`glassbox.audit.impact`) requires demographic labels for
real applicants. Most people who want to audit a screener cannot get those: the labels
are sensitive, often uncollected, and gated behind the very organisation being audited.

This module needs none of them.

**The idea, and where it comes from.** HireVue's patent US 2019/0057356 A1 describes
building a "digital fingerprint" of a protected attribute, projecting it onto candidates
who lack that attribute, and measuring the effect on their score -- synthesising a
counterfactual to expose what the model does to someone who merely *presents* those
features. Inverted for text, that becomes far cheaper: hold a resume fixed, change one
signal that correlates with a protected class -- a first name, a women's college, a
pronoun, a caregiving gap -- and measure the score delta. Same counterfactual logic, no
protected attribute ever collected.

**What a finding here means.** A non-zero delta is evidence that the scorer is sensitive
to a signal that is not job-related. It is *not* a legal conclusion, and it is not the
same construct as adverse impact -- a screener can be perfectly counterfactually
invariant and still produce disparate outcomes through correlated legitimate features
(and vice versa). Run both.

**Scope.** The name lists are a research instrument, not a claim about anyone. Names
are grouped by their measured *perceptual* association in the audit-study literature
(Bertrand & Mullainathan 2004 and successors), because what matters is the inference a
model draws, not anyone's actual identity. No individual's demographics are asserted or
inferred.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

__all__ = [
    "DEFAULT_PERTURBATIONS",
    "NAME_SETS",
    "Perturbation",
    "PerturbationReport",
    "PerturbationResult",
    "affiliation_swap",
    "employment_gap",
    "name_swap",
    "pronoun_swap",
    "run_perturbation_audit",
]

Scorer = Callable[[str], float]

#: Given names grouped by the perceptual association measured in correspondence-audit
#: studies. Drawn from the design of Bertrand & Mullainathan (2004), "Are Emily and
#: Greg More Employable than Lakisha and Jamal?", AER 94(4), and later replications.
#:
#: These are research instruments for probing a *model's* inference. They do not
#: describe any real person, and the grouping is a statement about signal, not identity.
NAME_SETS: dict[str, list[str]] = {
    "white_associated_male": [
        "Todd Wilson", "Brad Miller", "Geoffrey Baker", "Brett Murphy", "Greg Walsh",
    ],
    "white_associated_female": [
        "Allison Baker", "Anne Murphy", "Emily Walsh", "Jill Miller", "Laurie Wilson",
    ],
    "black_associated_male": [
        "Darnell Jackson", "Hakim Washington", "Jamal Jones", "Leroy Booker", "Tyrone Banks",
    ],
    "black_associated_female": [
        "Aisha Washington", "Ebony Jackson", "Keisha Jones", "Lakisha Banks", "Tamika Booker",
    ],
    "hispanic_associated": [
        "Carlos Ramirez", "Jose Hernandez", "Luis Torres", "Maria Gonzalez", "Sofia Vargas",
    ],
    "asian_associated": [
        "Chen Wei", "Hiroshi Tanaka", "Mei Lin", "Priya Nair", "Rajesh Gupta",
    ],
}

_PRONOUN_MAP: dict[str, dict[str, str]] = {
    "he": {"he": "he", "him": "him", "his": "his", "himself": "himself"},
    "she": {"he": "she", "him": "her", "his": "her", "himself": "herself"},
    "they": {"he": "they", "him": "them", "his": "their", "himself": "themselves"},
}


@dataclass(frozen=True)
class Perturbation:
    """A single counterfactual edit.

    Args:
        name: Identifier, e.g. ``"name:black_associated_female"``.
        dimension: What is being varied, e.g. ``"name"`` or ``"pronoun"``. Results are
            aggregated within a dimension.
        apply: Function mapping an original resume to its perturbed variant.
        note: Human-readable description of the edit.
    """

    name: str
    dimension: str
    apply: Callable[[str], str]
    note: str = ""


@dataclass(frozen=True)
class PerturbationResult:
    """Effect of one perturbation across a corpus of resumes."""

    perturbation: str
    dimension: str
    n_resumes: int
    baseline_mean: float
    perturbed_mean: float
    deltas: list[float] = field(repr=False, default_factory=list)

    @property
    def mean_delta(self) -> float:
        """Mean signed score change. Positive means the perturbation *raised* scores."""
        return self.perturbed_mean - self.baseline_mean

    @property
    def max_abs_delta(self) -> float:
        """Largest single-resume swing -- a mean near zero can hide large offsetting moves."""
        return max((abs(d) for d in self.deltas), default=0.0)

    @property
    def n_changed(self) -> int:
        """How many resumes changed score at all."""
        return sum(1 for d in self.deltas if d != 0.0)

    @property
    def stdev_delta(self) -> float | None:
        """Standard deviation of deltas, or ``None`` with fewer than two resumes."""
        return statistics.stdev(self.deltas) if len(self.deltas) > 1 else None


@dataclass
class PerturbationReport:
    """Findings across all perturbations."""

    results: list[PerturbationResult]
    n_resumes: int
    invariance_tolerance: float

    @property
    def is_invariant(self) -> bool:
        """True when no perturbation moved any score beyond the tolerance.

        Counterfactual invariance is the property being tested. It is a necessary
        condition for a defensible screener, not a sufficient one.
        """
        return all(r.max_abs_delta <= self.invariance_tolerance for r in self.results)

    @property
    def violations(self) -> list[PerturbationResult]:
        """Perturbations that moved scores beyond tolerance, largest effect first."""
        return sorted(
            (r for r in self.results if r.max_abs_delta > self.invariance_tolerance),
            key=lambda r: abs(r.mean_delta),
            reverse=True,
        )

    def dimension_spread(self) -> dict[str, float]:
        """Per dimension, the gap between its best- and worst-treated variant.

        This is the headline number. If swapping only the name moves the mean score by
        0.15 on a 0-1 scale, that is the screener's name sensitivity, and no amount of
        aggregate accuracy explains it away.
        """
        by_dimension: dict[str, list[float]] = {}
        for result in self.results:
            by_dimension.setdefault(result.dimension, []).append(result.perturbed_mean)
        return {
            dimension: max(means) - min(means)
            for dimension, means in by_dimension.items()
            if len(means) > 1
        }


def name_swap(replacement: str, *, original_pattern: str | None = None) -> Callable[[str], str]:
    """Replace the candidate name with ``replacement``.

    Assumes the name is the first non-empty line, which is the near-universal resume
    convention. Pass ``original_pattern`` to target a specific name by regex instead.

    Args:
        replacement: The name to substitute in.
        original_pattern: Optional regex identifying the name to replace.

    Returns:
        A function mapping resume text to its perturbed variant.
    """

    def apply(text: str) -> str:
        if original_pattern is not None:
            return re.sub(original_pattern, replacement, text, count=1)

        lines = text.split("\n")
        for index, line in enumerate(lines):
            if line.strip():
                lines[index] = replacement
                return "\n".join(lines)
        return text

    return apply


def pronoun_swap(target: str) -> Callable[[str], str]:
    """Rewrite third-person pronouns to ``target`` ('he', 'she', or 'they').

    Case-preserving and word-boundary aware, so "his" inside "history" is untouched.

    Args:
        target: One of ``"he"``, ``"she"``, ``"they"``.

    Returns:
        A function mapping resume text to its perturbed variant.

    Raises:
        ValueError: If ``target`` is not a supported pronoun set.
    """
    if target not in _PRONOUN_MAP:
        raise ValueError(f"target must be one of {sorted(_PRONOUN_MAP)}, got {target!r}")

    mapping = _PRONOUN_MAP[target]
    # Every inflected form of every supported pronoun set maps into the target set,
    # so the swap is idempotent and works regardless of the source resume's pronouns.
    all_forms = {
        form.lower(): mapping[canonical]
        for source in _PRONOUN_MAP.values()
        for canonical, form in source.items()
    }

    pattern = re.compile(
        r"\b(" + "|".join(sorted(all_forms, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )

    def apply(text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            word = match.group(0)
            new = all_forms[word.lower()]
            if word.isupper():
                return new.upper()
            if word[0].isupper():
                return new.capitalize()
            return new

        return pattern.sub(replace, text)

    return apply


def affiliation_swap(original: str, replacement: str) -> Callable[[str], str]:
    """Replace an institution or organisation name.

    Probes proxy discrimination: a screener that never sees a demographic attribute can
    still key on a women's college, an HBCU, a religious institution, or a foreign
    university and reach the same result.

    Args:
        original: Substring to find (matched case-insensitively, whole-word).
        replacement: Substring to substitute.
    """
    pattern = re.compile(rf"\b{re.escape(original)}\b", re.IGNORECASE)

    def apply(text: str) -> str:
        return pattern.sub(replacement, text)

    return apply


def employment_gap(years: int = 2, *, gap_text: str | None = None) -> Callable[[str], str]:
    """Append an explicit career break to the experience section.

    Career gaps correlate with caregiving, illness, and disability, and are penalised by
    many screeners. Because the gap is *added* text rather than substituted, this
    measures the penalty directly.

    Args:
        years: Length of the break in years.
        gap_text: Override the inserted text entirely.
    """
    text_to_add = gap_text or (
        f"\nCareer break ({years} year{'s' if years != 1 else ''}) "
        "for family caregiving responsibilities.\n"
    )

    def apply(text: str) -> str:
        return text.rstrip() + "\n" + text_to_add

    return apply


def _default_perturbations() -> list[Perturbation]:
    """Name and pronoun probes covering the standard audit-study design."""
    perturbations = [
        Perturbation(
            name=f"name:{group}",
            dimension="name",
            apply=name_swap(names[0]),
            note=f"candidate name replaced with {names[0]!r} ({group})",
        )
        for group, names in NAME_SETS.items()
    ]
    perturbations += [
        Perturbation(
            name=f"pronoun:{pronoun}",
            dimension="pronoun",
            apply=pronoun_swap(pronoun),
            note=f"third-person pronouns rewritten to {pronoun!r}",
        )
        for pronoun in ("he", "she", "they")
    ]
    return perturbations


#: Standard probe set: one name per association group, plus the three pronoun sets.
DEFAULT_PERTURBATIONS: list[Perturbation] = _default_perturbations()


def run_perturbation_audit(
    resumes: Sequence[str],
    scorer: Scorer,
    *,
    perturbations: Sequence[Perturbation] | None = None,
    invariance_tolerance: float = 1e-9,
) -> PerturbationReport:
    """Score each resume before and after each perturbation.

    Args:
        resumes: Resume texts. Use real ones you are authorised to test with, or
            synthetic ones -- the method works either way, since each resume is
            compared only against itself.
        scorer: Any callable mapping resume text to a score. Wrap an HTTP call, a
            local model, or a keyword rubric.
        perturbations: Probes to apply. Defaults to :data:`DEFAULT_PERTURBATIONS`.
        invariance_tolerance: Absolute score change treated as noise. Keep at
            effectively zero for deterministic scorers; raise it for stochastic ones
            (an LLM judge at temperature > 0 has genuine run-to-run variance, and you
            should measure that variance first rather than guessing this number).

    Returns:
        A :class:`PerturbationReport`.

    Raises:
        ValueError: If ``resumes`` is empty or ``invariance_tolerance`` is negative.
    """
    if not resumes:
        raise ValueError("no resumes supplied")
    if invariance_tolerance < 0:
        raise ValueError("invariance_tolerance must be non-negative")

    probes = list(perturbations) if perturbations is not None else DEFAULT_PERTURBATIONS

    baselines = [scorer(resume) for resume in resumes]
    baseline_mean = sum(baselines) / len(baselines)

    results = []
    for probe in probes:
        perturbed_scores = [scorer(probe.apply(resume)) for resume in resumes]
        deltas = [p - b for p, b in zip(perturbed_scores, baselines, strict=True)]
        results.append(
            PerturbationResult(
                perturbation=probe.name,
                dimension=probe.dimension,
                n_resumes=len(resumes),
                baseline_mean=baseline_mean,
                perturbed_mean=sum(perturbed_scores) / len(perturbed_scores),
                deltas=deltas,
            )
        )

    return PerturbationReport(
        results=results,
        n_resumes=len(resumes),
        invariance_tolerance=invariance_tolerance,
    )
