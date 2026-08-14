"""Adverse-impact analysis under the EEOC Uniform Guidelines (29 CFR 1607).

Implements the four-fifths rule as the regulation actually defines it, including the
three qualifications that implementations usually drop:

1. A rate difference based on small numbers that is not statistically significant may
   *not* be adverse impact -- so an impact ratio is never reported without a
   significance test and the group sizes alongside it (1607.4(D)).
2. Passing 0.8 is not safety. Smaller differences can still constitute adverse impact
   when significant in both statistical and practical terms. Nothing here returns a
   "compliant" verdict; it returns findings.
3. The impact ratio is a **function of the cut score**. A tool can pass at the 50th
   percentile and fail at the 70th. :func:`impact_ratio_curve` makes that explicit,
   because a single ratio reported without its threshold is not reproducible.

Zero-dependency by design -- see :mod:`glassbox.audit.stats`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from .stats import (
    TestResult,
    fisher_exact_2x2,
    standardized_mean_difference,
    two_proportion_z,
    wilson_interval,
)

__all__ = [
    "FOUR_FIFTHS",
    "GroupImpact",
    "GroupOutcome",
    "ImpactReport",
    "ThresholdPoint",
    "adverse_impact",
    "impact_ratio_curve",
    "outcomes_from_scores",
    "score_gap_report",
]

#: The UGESP screening threshold, 29 CFR 1607.4(D). A ratio below this "will generally
#: be regarded by the Federal enforcement agencies as evidence of adverse impact".
FOUR_FIFTHS = 0.8

#: NYC Local Law 144 permits an independent auditor to exclude a category representing
#: less than 2% of the data from impact-ratio calculations.
LL144_MIN_SHARE = 0.02

#: Below this expected cell count we prefer Fisher's exact test to the normal
#: approximation. The convention traces to Cochran's rule for chi-square validity.
_SMALL_CELL = 5


@dataclass(frozen=True)
class GroupOutcome:
    """Observed selection counts for one demographic group.

    Args:
        name: Group label, e.g. ``"Black or African American"``.
        selected: Number selected (advanced, passed, hired -- whatever the decision is).
        total: Number considered.
    """

    name: str
    selected: int
    total: int

    def __post_init__(self) -> None:
        if self.total < 0 or self.selected < 0:
            raise ValueError(f"{self.name}: counts must be non-negative")
        if self.selected > self.total:
            raise ValueError(
                f"{self.name}: selected ({self.selected}) exceeds total ({self.total})"
            )

    @property
    def selection_rate(self) -> float:
        """Selection rate, or 0.0 for an empty group."""
        return self.selected / self.total if self.total else 0.0


@dataclass(frozen=True)
class GroupImpact:
    """Per-group findings. ``impact_ratio`` is ``None`` for the reference group.

    ``impact_ratio`` is a float for reporting and display. ``impact_ratio_exact`` is
    the same quantity as an exact rational, and it is what :attr:`flagged` compares
    against the threshold.

    The distinction is not pedantry. A group selected 64/100 against a reference of
    80/100 sits *exactly* at four-fifths, but in binary floating point the quotient is
    0.7999999999999999 -- so a float comparison reports adverse impact against a
    procedure that is precisely on the legal line. Selection counts are integers, so
    the ratio is always rational and there is no reason to accept that error.
    """

    name: str
    selected: int
    total: int
    selection_rate: float
    impact_ratio: float | None
    is_reference: bool
    rate_ci: tuple[float, float]
    significance: TestResult | None
    shortfall: int
    share_of_data: float
    impact_ratio_exact: Fraction | None = None

    @property
    def flagged(self) -> bool:
        """True when the impact ratio falls strictly below four-fifths.

        Uses exact rational comparison; a ratio of exactly 0.8 is not "less than
        four-fifths" and does not flag.
        """
        if self.impact_ratio_exact is not None:
            return self.impact_ratio_exact < Fraction(4, 5)
        return self.impact_ratio is not None and self.impact_ratio < FOUR_FIFTHS


@dataclass
class ImpactReport:
    """Adverse-impact findings for one demographic category.

    ``threshold`` is populated when outcomes were derived from continuous scores, and is
    part of the finding: the same tool yields different ratios at different cut scores.
    """

    category: str
    groups: list[GroupImpact]
    reference_group: str
    threshold: float | None = None
    threshold_label: str | None = None
    excluded: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def min_impact_ratio(self) -> float | None:
        """Smallest impact ratio across non-reference groups (the "minimum bias ratio")."""
        ratios = [g.impact_ratio for g in self.groups if g.impact_ratio is not None]
        return min(ratios) if ratios else None

    @property
    def flagged_groups(self) -> list[GroupImpact]:
        """Groups falling below four-fifths, worst first."""
        return sorted(
            (g for g in self.groups if g.flagged), key=lambda g: g.impact_ratio or 0.0
        )

    @property
    def passes_four_fifths(self) -> bool:
        """Whether every ratio clears 0.8.

        Named narrowly on purpose. This is *not* a compliance verdict: clearing the
        four-fifths screen does not establish that a selection procedure is lawful or
        valid, and 1607.4(D) says so directly.
        """
        mir = self.min_impact_ratio
        return mir is None or mir >= FOUR_FIFTHS


def _select_reference(outcomes: Sequence[GroupOutcome]) -> GroupOutcome:
    """Highest-selecting group, per 1607.4(D). Ties break on larger n, then name."""
    return max(outcomes, key=lambda o: (o.selection_rate, o.total, o.name))


def adverse_impact(
    outcomes: Iterable[GroupOutcome] | Mapping[str, tuple[int, int]],
    *,
    category: str = "unspecified",
    min_share: float = 0.0,
    threshold: float | None = None,
    threshold_label: str | None = None,
) -> ImpactReport:
    """Run a four-fifths analysis over one demographic category.

    Args:
        outcomes: Either ``GroupOutcome`` objects, or a mapping of
            ``{group_name: (selected, total)}`` for convenience.
        category: Category label, e.g. ``"race/ethnicity"`` or ``"sex"``.
        min_share: Exclude groups below this fraction of total data. Pass
            :data:`LL144_MIN_SHARE` (0.02) for a NYC Local Law 144 audit. Defaults to
            0.0 -- excluding nothing -- because silently dropping small groups is how a
            disparity disappears from a report.
        threshold: Cut score used to derive these outcomes, if any. Recorded in the
            report so the finding is reproducible.
        threshold_label: Human description of the cut, e.g. ``"70th percentile"``.

    Returns:
        An :class:`ImpactReport`.

    Raises:
        ValueError: If fewer than two groups have data.
    """
    if isinstance(outcomes, Mapping):
        outcomes = [
            GroupOutcome(name, selected, total)
            for name, (selected, total) in outcomes.items()
        ]
    outcomes = list(outcomes)

    populated = [o for o in outcomes if o.total > 0]
    excluded: list[tuple[str, str]] = [
        (o.name, "no observations") for o in outcomes if o.total == 0
    ]

    grand_total = sum(o.total for o in populated)
    if grand_total == 0:
        raise ValueError("no observations in any group")

    kept: list[GroupOutcome] = []
    for outcome in populated:
        share = outcome.total / grand_total
        if min_share > 0.0 and share < min_share:
            excluded.append(
                (
                    outcome.name,
                    f"represents {share:.2%} of data, below the "
                    f"{min_share:.0%} reporting threshold",
                )
            )
        else:
            kept.append(outcome)

    if len(kept) < 2:
        raise ValueError(
            f"need at least 2 groups with data to compute impact ratios, got {len(kept)}"
            f" (excluded: {[name for name, _ in excluded]})"
        )

    reference = _select_reference(kept)
    reference_rate = reference.selection_rate
    notes: list[str] = []

    if reference_rate == 0.0:
        notes.append(
            "No group had any selections; impact ratios are undefined. This usually "
            "means the cut score is above every observed score."
        )

    groups: list[GroupImpact] = []
    for outcome in kept:
        is_reference = outcome.name == reference.name

        exact_ratio: Fraction | None
        if is_reference or reference_rate == 0.0:
            ratio = None
            exact_ratio = None
        else:
            # Exact first, float derived from it -- see GroupImpact docstring.
            exact_ratio = Fraction(outcome.selected, outcome.total) / Fraction(
                reference.selected, reference.total
            )
            ratio = float(exact_ratio)

        significance: TestResult | None = None
        if not is_reference:
            a = outcome.selected
            b = outcome.total - outcome.selected
            c = reference.selected
            d = reference.total - reference.selected
            # Prefer the exact test when any cell is small -- 1607.4(D) turns on
            # exactly this situation.
            if min(a, b, c, d) < _SMALL_CELL:
                significance = fisher_exact_2x2(a, b, c, d)
            else:
                significance = two_proportion_z(a, outcome.total, c, reference.total)

        # Additional selections this group would need to reach a 0.8 ratio, holding
        # the reference rate fixed. Actionable in a way a bare ratio is not.
        #
        # Computed with exact rationals, not floats. In binary floating point
        # 0.8 * 0.8 * 100 == 64.00000000000001, so a plain ceil() returns 65 and the
        # report demands one more selection than the law does. That is a real
        # difference to a real person, so the arithmetic is exact.
        shortfall = 0
        if exact_ratio is not None and exact_ratio < Fraction(4, 5):
            target = (
                Fraction(4, 5)
                * Fraction(reference.selected, reference.total)
                * outcome.total
            )
            needed = -((-target.numerator) // target.denominator)  # exact ceiling
            shortfall = max(0, needed - outcome.selected)

        groups.append(
            GroupImpact(
                name=outcome.name,
                selected=outcome.selected,
                total=outcome.total,
                selection_rate=outcome.selection_rate,
                impact_ratio=ratio,
                is_reference=is_reference,
                rate_ci=wilson_interval(outcome.selected, outcome.total),
                significance=significance,
                shortfall=shortfall,
                share_of_data=outcome.total / grand_total,
                impact_ratio_exact=exact_ratio,
            )
        )

    small_groups = [g.name for g in groups if g.total < 30]
    if small_groups:
        notes.append(
            f"Small samples (n<30): {', '.join(small_groups)}. Per 29 CFR 1607.4(D), "
            "rate differences based on small numbers that are not statistically "
            "significant may not constitute adverse impact. Read the ratio together "
            "with the significance test, not alone."
        )

    flagged_but_insignificant = [
        g.name
        for g in groups
        if g.flagged and g.significance and not g.significance.significant_at_05
    ]
    if flagged_but_insignificant:
        notes.append(
            f"Below 0.8 but not significant at p<=0.05: "
            f"{', '.join(flagged_but_insignificant)}. Practically notable, "
            "statistically unresolved -- collect more data rather than concluding."
        )

    significant_but_passing = [
        g.name
        for g in groups
        if not g.flagged
        and g.impact_ratio is not None
        and g.significance
        and g.significance.significant_at_05
    ]
    if significant_but_passing:
        notes.append(
            f"Clears 0.8 yet statistically significant: {', '.join(significant_but_passing)}. "
            "1607.4(D) provides that smaller differences may still constitute adverse "
            "impact where significant in statistical and practical terms. Do not read "
            "the passing ratio as clearance."
        )

    return ImpactReport(
        category=category,
        groups=groups,
        reference_group=reference.name,
        threshold=threshold,
        threshold_label=threshold_label,
        excluded=excluded,
        notes=notes,
    )


def outcomes_from_scores(
    scores_by_group: Mapping[str, Sequence[float]],
    threshold: float,
    *,
    higher_is_better: bool = True,
) -> list[GroupOutcome]:
    """Convert continuous scores into selection counts at a cut score.

    Args:
        scores_by_group: ``{group_name: [score, ...]}``.
        threshold: The cut score. Selection is ``score >= threshold`` when
            ``higher_is_better``, else ``score <= threshold``.
        higher_is_better: Direction of the score scale.

    Returns:
        One :class:`GroupOutcome` per group.
    """
    outcomes = []
    for name, scores in scores_by_group.items():
        if higher_is_better:
            selected = sum(1 for s in scores if s >= threshold)
        else:
            selected = sum(1 for s in scores if s <= threshold)
        outcomes.append(GroupOutcome(name, selected, len(scores)))
    return outcomes


@dataclass(frozen=True)
class ThresholdPoint:
    """Impact ratio at one cut score."""

    threshold: float
    percentile: float | None
    min_impact_ratio: float | None
    overall_selection_rate: float
    passes: bool
    worst_group: str | None


def impact_ratio_curve(
    scores_by_group: Mapping[str, Sequence[float]],
    *,
    percentiles: Sequence[float] = (10, 20, 30, 40, 50, 60, 70, 80, 90),
    higher_is_better: bool = True,
    min_share: float = 0.0,
) -> list[ThresholdPoint]:
    """Sweep the cut score and report the impact ratio at each one.

    The single most under-reported fact about adverse-impact testing: **the impact ratio
    depends on the threshold.** The FAccT audit of pymetrics found its fairness search
    optimised the ratio at the 70th percentile while deploying tiers cut at both the
    50th and 70th -- two different ratios from one model.

    A tool that passes at your chosen cut may fail one notch away. Sweeping shows how
    close to a cliff the configuration sits.

    Args:
        scores_by_group: ``{group_name: [score, ...]}``.
        percentiles: Percentiles of the *pooled* score distribution to test.
        higher_is_better: Direction of the score scale.
        min_share: Passed through to :func:`adverse_impact`.

    Returns:
        One :class:`ThresholdPoint` per percentile, ascending. Percentiles whose
        analysis is degenerate (fewer than two groups with data) are skipped.

    Raises:
        ValueError: If no scores were supplied at all.
    """
    pooled = sorted(s for scores in scores_by_group.values() for s in scores)
    if not pooled:
        raise ValueError("no scores supplied")

    total_n = len(pooled)
    curve: list[ThresholdPoint] = []

    for pct in percentiles:
        # Nearest-rank percentile: simple, exact, and no interpolation artefacts to
        # explain to an auditor.
        index = min(total_n - 1, max(0, math.ceil(pct / 100.0 * total_n) - 1))
        threshold = pooled[index]

        outcomes = outcomes_from_scores(
            scores_by_group, threshold, higher_is_better=higher_is_better
        )
        try:
            report = adverse_impact(
                outcomes,
                min_share=min_share,
                threshold=threshold,
                threshold_label=f"{pct:g}th percentile",
            )
        except ValueError:
            continue

        selected_total = sum(g.selected for g in report.groups)
        considered = sum(g.total for g in report.groups)
        worst = report.flagged_groups[0].name if report.flagged_groups else None

        curve.append(
            ThresholdPoint(
                threshold=threshold,
                percentile=pct,
                min_impact_ratio=report.min_impact_ratio,
                overall_selection_rate=selected_total / considered if considered else 0.0,
                passes=report.passes_four_fifths,
                worst_group=worst,
            )
        )

    return curve


def score_gap_report(
    scores_by_group: Mapping[str, Sequence[float]],
    *,
    reference: str | None = None,
) -> dict[str, float | None]:
    """Standardized mean differences against a reference group.

    Threshold-free companion to the impact ratio. Because it compares distributions
    rather than pass rates, it does not move when the cut score moves -- so it answers
    "does this instrument score groups differently?" independently of "does this
    configuration select groups differently?"

    Args:
        scores_by_group: ``{group_name: [score, ...]}``.
        reference: Reference group name. Defaults to the highest-mean group.

    Returns:
        ``{group_name: cohens_d}``, positive meaning that group scored higher than the
        reference. The reference maps to 0.0. A group maps to ``None`` when *d* is
        undefined (n<2 or zero pooled variance) -- distinct from "no difference".

    Raises:
        ValueError: If fewer than two groups are supplied, or ``reference`` is unknown.
    """
    if len(scores_by_group) < 2:
        raise ValueError("need at least 2 groups")

    if reference is None:
        reference = max(
            scores_by_group,
            key=lambda g: (
                sum(scores_by_group[g]) / len(scores_by_group[g])
                if scores_by_group[g]
                else float("-inf")
            ),
        )
    if reference not in scores_by_group:
        raise ValueError(f"reference group {reference!r} not in data")

    baseline = scores_by_group[reference]
    return {
        name: 0.0
        if name == reference
        else standardized_mean_difference(list(scores), list(baseline))
        for name, scores in scores_by_group.items()
    }
