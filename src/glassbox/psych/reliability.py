"""Reliability, norming, and validity ceilings.

A gamified assessment that produces a number is not yet a measurement. What makes a
score meaningful is evidence about its **reliability** (does it measure consistently?)
and **validity** (does it measure the thing you claim, and predict what you claim?).

This module implements the standard indices, plus the one result most often omitted
from vendor materials: :func:`max_validity`, the ceiling that reliability places on any
correlation a test can have with job performance. A test with reliability 0.60 cannot
correlate with a perfectly-measured criterion above 0.77, no matter how good the model
on top of it. Reporting a validity coefficient without the reliability that bounds it
omits the number that says whether the claim is even possible.

Zero-dependency, stdlib only -- same rationale as :mod:`glassbox.audit.stats`.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

__all__ = [
    "cronbach_alpha",
    "interpret_reliability",
    "max_validity",
    "percentile_rank",
    "spearman_brown",
    "split_half_reliability",
    "standard_error_of_measurement",
    "z_score",
]


def cronbach_alpha(item_scores: Sequence[Sequence[float]]) -> float | None:
    """Cronbach's alpha: internal consistency across items.

    .. math::
        \\alpha = \\frac{k}{k-1}\\left(1 - \\frac{\\sum_i \\sigma^2_i}{\\sigma^2_t}\\right)

    .. note::
       Alpha is routinely over-interpreted. It is a lower bound on reliability only
       under tau-equivalence, it rises mechanically with the number of items, and a
       high alpha does **not** establish unidimensionality. Report it alongside item
       count, and do not treat 0.7 as a magic threshold.

    Args:
        item_scores: One sequence per respondent, each holding that respondent's score
            on every item. All rows must be the same length.

    Returns:
        Alpha, or ``None`` when undefined -- fewer than 2 items, fewer than 2
        respondents, or zero total variance.

    Raises:
        ValueError: If rows have differing lengths.
    """
    if len(item_scores) < 2:
        return None

    n_items = len(item_scores[0])
    if n_items < 2:
        return None
    if any(len(row) != n_items for row in item_scores):
        raise ValueError("all respondents must have scores on the same number of items")

    item_variances = []
    for index in range(n_items):
        column = [row[index] for row in item_scores]
        item_variances.append(statistics.variance(column))

    totals = [sum(row) for row in item_scores]
    total_variance = statistics.variance(totals)

    if total_variance <= 0:
        return None

    k = n_items
    return (k / (k - 1)) * (1.0 - sum(item_variances) / total_variance)


def split_half_reliability(
    first_half: Sequence[float], second_half: Sequence[float]
) -> float | None:
    """Split-half reliability, Spearman-Brown corrected to full-test length.

    Args:
        first_half: Each respondent's score on one half of the items.
        second_half: The same respondents' scores on the other half, same order.

    Returns:
        Corrected reliability, or ``None`` if the correlation is undefined.

    Raises:
        ValueError: If the halves differ in length.
    """
    if len(first_half) != len(second_half):
        raise ValueError("halves must cover the same respondents")

    correlation = _pearson(first_half, second_half)
    return None if correlation is None else spearman_brown(correlation, factor=2.0)


def spearman_brown(reliability: float, factor: float) -> float:
    """Predict reliability after changing test length by ``factor``.

    .. math::
        r' = \\frac{n \\cdot r}{1 + (n-1) r}

    Args:
        reliability: Current reliability.
        factor: Length multiplier. 2.0 doubles the test.

    Returns:
        Predicted reliability.

    Raises:
        ValueError: If ``factor`` is not positive, or the denominator vanishes
            (reliability = -1 at factor 2, which is not a meaningful input).
    """
    if factor <= 0:
        raise ValueError("factor must be positive")

    denominator = 1.0 + (factor - 1.0) * reliability
    if denominator == 0:
        raise ValueError("undefined: denominator is zero for this reliability/factor")
    return (factor * reliability) / denominator


def standard_error_of_measurement(sd: float, reliability: float) -> float:
    """Standard error of measurement.

    .. math::
        SEM = \\sigma \\sqrt{1 - r}

    The number that should accompany every reported score. With SD 15 and reliability
    0.80, SEM is 6.7 -- so a candidate scoring 105 and one scoring 98 are not
    meaningfully different, and ranking them is noise.

    Args:
        sd: Standard deviation of scores in the reference population.
        reliability: Reliability coefficient in [0, 1].

    Returns:
        The SEM, in score units.

    Raises:
        ValueError: If ``sd`` is negative or ``reliability`` is outside [0, 1].
    """
    if sd < 0:
        raise ValueError("sd must be non-negative")
    if not 0.0 <= reliability <= 1.0:
        raise ValueError(f"reliability must be in [0, 1], got {reliability}")
    return sd * math.sqrt(1.0 - reliability)


def max_validity(
    test_reliability: float, criterion_reliability: float = 1.0
) -> float:
    """Maximum possible correlation between a test and a criterion.

    .. math::
        r_{max} = \\sqrt{r_{xx} \\cdot r_{yy}}

    The correction-for-attenuation ceiling. A test cannot correlate with job
    performance more strongly than the square root of the product of the two
    reliabilities -- an unbreakable bound, independent of the modelling on top.

    This is the number to demand when a vendor reports a validity coefficient. If a
    claimed validity exceeds this ceiling, either the reliability estimate or the
    validity estimate is wrong.

    Args:
        test_reliability: Reliability of the assessment.
        criterion_reliability: Reliability of the job-performance measure. Defaults to
            1.0, which is generous -- supervisor ratings, the usual criterion, are
            typically estimated well below 0.60, which lowers the ceiling sharply.

    Returns:
        The maximum attainable validity coefficient.

    Raises:
        ValueError: If either reliability is outside [0, 1].
    """
    for name, value in (
        ("test_reliability", test_reliability),
        ("criterion_reliability", criterion_reliability),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1], got {value}")
    return math.sqrt(test_reliability * criterion_reliability)


def percentile_rank(score: float, norms: Sequence[float]) -> float:
    """Percentile rank of ``score`` within a norm sample.

    Uses the standard definition counting half of tied scores, which avoids the
    boundary artefacts of strict "below" counting.

    Args:
        score: The score to rank.
        norms: Reference-population scores.

    Returns:
        Percentile in [0, 100].

    Raises:
        ValueError: If ``norms`` is empty.
    """
    if not norms:
        raise ValueError("norm sample is empty")

    below = sum(1 for n in norms if n < score)
    equal = sum(1 for n in norms if n == score)
    return 100.0 * (below + 0.5 * equal) / len(norms)


def z_score(score: float, norms: Sequence[float]) -> float | None:
    """Standardise ``score`` against a norm sample.

    Args:
        score: The score to standardise.
        norms: Reference-population scores.

    Returns:
        The z-score, or ``None`` if the norm sample has fewer than 2 values or zero
        variance.

    Raises:
        ValueError: If ``norms`` is empty.
    """
    if not norms:
        raise ValueError("norm sample is empty")
    if len(norms) < 2:
        return None

    sd = statistics.stdev(norms)
    if sd == 0:
        return None
    return (score - statistics.mean(norms)) / sd


def interpret_reliability(reliability: float, *, use: str = "research") -> str:
    """Plain-language interpretation of a reliability coefficient.

    Args:
        reliability: The coefficient.
        use: ``"research"`` for group-level work, or ``"selection"`` for
            individual decisions, which demands a higher standard.

    Returns:
        A sentence naming the standard applied.

    Raises:
        ValueError: If ``use`` is not recognised.
    """
    if use not in {"research", "selection"}:
        raise ValueError("use must be 'research' or 'selection'")

    if use == "selection":
        # Individual high-stakes decisions demand more than group-level research.
        if reliability >= 0.90:
            return "Adequate for individual high-stakes decisions."
        if reliability >= 0.80:
            return (
                "Marginal for individual decisions; report confidence intervals and do "
                "not rank candidates within a standard error of each other."
            )
        return (
            "Insufficient for individual selection decisions. Score differences between "
            "candidates are largely measurement error."
        )

    if reliability >= 0.80:
        return "Good for group-level research."
    if reliability >= 0.70:
        return "Acceptable for group-level research."
    if reliability >= 0.60:
        return "Weak; interpret with caution even at group level."
    return "Poor; the score is dominated by measurement error."


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation, or ``None`` when undefined."""
    if len(xs) < 2 or len(xs) != len(ys):
        return None

    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    if var_x <= 0 or var_y <= 0:
        return None
    return covariance / math.sqrt(var_x * var_y)
