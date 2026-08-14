"""Statistical primitives for adverse-impact analysis.

Deliberately zero-dependency (stdlib only). This module is the numerical core of a
compliance tool, and compliance tools get vendored into environments the author does not
control, re-run years later to reproduce a filed audit, and read line-by-line by people
who are not Python programmers.

The predecessor library in this space (``pymetrics/audit-ai``, MIT) became unusable not
because its statistics were wrong but because it was pinned to a 2020 scientific-Python
stack. Pure stdlib cannot rot that way: an audit run in 2020 reproduces in 2030.

Every function here is exact or documented-approximate, and each cites its reference.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "TestResult",
    "fisher_exact_2x2",
    "normal_cdf",
    "standardized_mean_difference",
    "two_proportion_z",
    "wilson_interval",
]


@dataclass(frozen=True)
class TestResult:
    """Outcome of a significance test.

    Attributes:
        statistic: The test statistic, or ``None`` for exact tests that have none.
        p_value: Two-sided p-value unless the test name says otherwise.
        test: Human-readable name of the test performed.
        detail: Why this test was chosen, so a reader can check the choice was not
            made to produce a preferred answer.
    """

    statistic: float | None
    p_value: float
    test: str
    detail: str = ""

    @property
    def significant_at_05(self) -> bool:
        """Whether the result clears the p <= 0.05 bar named in 29 CFR 1607.14."""
        return self.p_value <= 0.05


def normal_cdf(x: float) -> float:
    """Standard normal CDF, via the stdlib error function.

    Exact to double precision; ``math.erf`` is not an approximation in the way a
    hand-rolled polynomial would be.
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> TestResult:
    """Two-sided Fisher's exact test on a 2x2 contingency table.

    The table is laid out as::

                     selected   not selected
        focal group      a            b
        reference        c            d

    Exact conditional test on the hypergeometric distribution, holding both margins
    fixed. The two-sided p-value is the total probability of every table with the same
    margins whose probability is no greater than the observed table's -- the standard
    "method of small p-values" convention, which is what R's ``fisher.test`` and
    ``scipy.stats.fisher_exact`` both use.

    This is the correct test when any expected cell count is small, which in employment
    auditing is routine: 29 CFR 1607.4(D) explicitly warns that rate differences based
    on small numbers may not evidence adverse impact.

    Args:
        a: Focal-group selections.
        b: Focal-group non-selections.
        c: Reference-group selections.
        d: Reference-group non-selections.

    Returns:
        A :class:`TestResult` with ``statistic=None`` (exact tests have no statistic).

    Raises:
        ValueError: If any count is negative or the table is empty.
    """
    if min(a, b, c, d) < 0:
        raise ValueError(f"cell counts must be non-negative, got ({a}, {b}, {c}, {d})")

    n = a + b + c + d
    if n == 0:
        raise ValueError("contingency table is empty")

    row1, row2 = a + b, c + d
    col1 = a + c

    # If a margin is zero the table is degenerate: only one arrangement is possible,
    # so nothing can be inferred and p = 1 is the honest answer.
    if row1 == 0 or row2 == 0 or col1 == 0 or (b + d) == 0:
        return TestResult(
            None, 1.0, "Fisher's exact (two-sided)", "degenerate table: a margin is zero"
        )

    def table_prob(a_val: int) -> float:
        """Hypergeometric probability of the table with this focal-selected count."""
        return (
            math.comb(row1, a_val)
            * math.comb(row2, col1 - a_val)
            / math.comb(n, col1)
        )

    # Support of a: bounded by both its row total and the column total.
    lo = max(0, col1 - row2)
    hi = min(row1, col1)

    observed = table_prob(a)
    # Relative tolerance guards against float noise excluding a table that is
    # mathematically equally-or-less probable.
    tolerance = observed * 1e-9
    p = sum(
        prob
        for a_val in range(lo, hi + 1)
        if (prob := table_prob(a_val)) <= observed + tolerance
    )

    return TestResult(
        None,
        min(1.0, p),
        "Fisher's exact (two-sided)",
        f"exact conditional test, n={n}; chosen because a cell count is small",
    )


def two_proportion_z(a: int, n_focal: int, c: int, n_reference: int) -> TestResult:
    """Two-sided two-proportion Z-test with pooled variance.

    Appropriate when both groups are large enough for the normal approximation. We use
    the pooled-proportion form, which is the standard choice when testing the null of
    equal proportions.

    .. math::
        z = \\frac{p_1 - p_2}{\\sqrt{\\bar{p}(1-\\bar{p})(1/n_1 + 1/n_2)}}

    Args:
        a: Focal-group selections.
        n_focal: Focal-group total.
        c: Reference-group selections.
        n_reference: Reference-group total.

    Returns:
        A :class:`TestResult`. If the pooled variance is zero (nobody selected, or
        everybody selected), returns p=1.0 rather than dividing by zero.

    Raises:
        ValueError: If either group is empty or selections exceed totals.
    """
    if n_focal <= 0 or n_reference <= 0:
        raise ValueError("group totals must be positive")
    if a > n_focal or c > n_reference:
        raise ValueError("selections cannot exceed group total")

    p1 = a / n_focal
    p2 = c / n_reference
    pooled = (a + c) / (n_focal + n_reference)
    variance = pooled * (1.0 - pooled) * (1.0 / n_focal + 1.0 / n_reference)

    if variance <= 0.0:
        return TestResult(
            0.0, 1.0, "two-proportion Z (pooled)", "zero variance: rates are identical"
        )

    z = (p1 - p2) / math.sqrt(variance)
    p = 2.0 * (1.0 - normal_cdf(abs(z)))
    return TestResult(
        z,
        min(1.0, p),
        "two-proportion Z (pooled)",
        f"normal approximation, n={n_focal + n_reference}",
    )


def standardized_mean_difference(
    focal: list[float], reference: list[float]
) -> float | None:
    """Cohen's *d* between two score distributions, using pooled SD.

    Used for *continuous* scores, before any cut score is applied. This is the metric
    that survives the threshold-dependence problem: an impact ratio changes as you move
    the cut score, but the standardized mean difference between two score distributions
    does not.

    Convention: positive *d* means the focal group scored **higher**.

    Args:
        focal: Scores for the focal group.
        reference: Scores for the reference group.

    Returns:
        Cohen's *d*, or ``None`` when it is undefined -- fewer than two observations in
        a group, or zero pooled variance. Returning ``None`` rather than 0.0 matters:
        "no difference" and "cannot be computed" are different findings.
    """
    n1, n2 = len(focal), len(reference)
    if n1 < 2 or n2 < 2:
        return None

    mean1 = sum(focal) / n1
    mean2 = sum(reference) / n2
    var1 = sum((x - mean1) ** 2 for x in focal) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in reference) / (n2 - 1)

    pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
    if pooled_var <= 0.0:
        return None

    return (mean1 - mean2) / math.sqrt(pooled_var)


def wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion.

    Preferred over the normal-approximation ("Wald") interval, which behaves badly for
    small samples and extreme proportions -- it can produce bounds below 0 or above 1,
    and its coverage collapses exactly where employment data tends to sit. Wilson stays
    inside [0, 1] and keeps nominal coverage at small n.

    Args:
        successes: Number of successes.
        total: Number of trials.
        z: Normal quantile; default is 1.96 for a 95% interval.

    Returns:
        ``(lower, upper)``, clamped to [0, 1]. Returns ``(0.0, 1.0)`` for ``total == 0``
        -- with no data, the honest interval is the whole range.

    Raises:
        ValueError: If ``total`` is negative or ``successes`` is out of range.
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    if total == 0:
        return (0.0, 1.0)
    if not 0 <= successes <= total:
        raise ValueError(f"successes ({successes}) must be in [0, {total}]")

    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = (p + z2 / (2.0 * total)) / denominator
    margin = (
        z * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total)) / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))
