"""Adverse-impact and fairness auditing for employment selection procedures."""

from .impact import (
    FOUR_FIFTHS,
    LL144_MIN_SHARE,
    GroupImpact,
    GroupOutcome,
    ImpactReport,
    ThresholdPoint,
    adverse_impact,
    impact_ratio_curve,
    outcomes_from_scores,
    score_gap_report,
)
from .stats import (
    TestResult,
    fisher_exact_2x2,
    standardized_mean_difference,
    two_proportion_z,
    wilson_interval,
)

__all__ = [
    "FOUR_FIFTHS",
    "LL144_MIN_SHARE",
    "GroupImpact",
    "GroupOutcome",
    "ImpactReport",
    "TestResult",
    "ThresholdPoint",
    "adverse_impact",
    "fisher_exact_2x2",
    "impact_ratio_curve",
    "outcomes_from_scores",
    "score_gap_report",
    "standardized_mean_difference",
    "two_proportion_z",
    "wilson_interval",
]
