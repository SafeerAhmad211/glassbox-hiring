"""Validation against independently published worked examples.

Every case here was computed by a third party and published before this library
existed. That makes them genuine external checks: if the implementation drifts, these
fail against numbers nobody here chose.

Sources are named per test. Where a source states a rounded figure (e.g. "67%"), the
test asserts the exact value and notes the published rounding, rather than loosening
the tolerance until it passes.
"""

from __future__ import annotations

import pytest

from glassbox.audit.impact import FOUR_FIFTHS, adverse_impact
from glassbox.audit.stats import fisher_exact_2x2, two_proportion_z


class TestPublishedFourFifthsExamples:
    """Worked examples published by HR/compliance sources."""

    def test_sixty_forty_selection_rates(self):
        """Men 60%, women 40% -> impact ratio 40/60 = 0.667.

        Published as "0.67 (67%)" — we assert the exact quotient.
        """
        report = adverse_impact({"Men": (60, 100), "Women": (40, 100)}, category="sex")
        women = next(g for g in report.groups if g.name == "Women")

        assert women.impact_ratio == pytest.approx(2 / 3, rel=1e-12)
        assert round(women.impact_ratio, 2) == 0.67
        assert women.flagged

    def test_skills_test_threshold_derivation(self):
        """If 60% of men pass, women must pass at >= 48% (0.8 * 60).

        Checks the boundary from both sides: 48% must clear, 47% must not.
        """
        at_threshold = adverse_impact({"Men": (60, 100), "Women": (48, 100)})
        below = adverse_impact({"Men": (60, 100), "Women": (47, 100)})

        women_at = next(g for g in at_threshold.groups if g.name == "Women")
        women_below = next(g for g in below.groups if g.name == "Women")

        assert women_at.impact_ratio == pytest.approx(0.8)
        assert not women_at.flagged, "exactly four-fifths must not flag"
        assert women_below.flagged

    def test_entry_level_engineering_example(self):
        """50 women / 30 hired (60%); 100 men / 80 hired (80%) -> IR 0.75, violated."""
        report = adverse_impact(
            {"Women": (30, 50), "Men": (80, 100)}, category="sex"
        )
        women = next(g for g in report.groups if g.name == "Women")

        assert women.selection_rate == pytest.approx(0.60)
        assert women.impact_ratio == pytest.approx(0.75)
        assert women.flagged
        assert not report.passes_four_fifths

    def test_personality_test_example(self):
        """80 White / 48 selected (60%); 40 Black / 12 selected (30%) -> IR 0.50.

        Note the unequal group sizes, which is where a naive implementation that
        compares raw counts rather than rates goes wrong.
        """
        report = adverse_impact(
            {"White": (48, 80), "Black": (12, 40)}, category="race/ethnicity"
        )
        black = next(g for g in report.groups if g.name == "Black")
        white = next(g for g in report.groups if g.name == "White")

        assert white.selection_rate == pytest.approx(0.60)
        assert black.selection_rate == pytest.approx(0.30)
        assert black.impact_ratio == pytest.approx(0.50)
        assert report.reference_group == "White"
        assert black.flagged

    def test_reference_group_is_rate_based_not_count_based(self):
        """The highest-*rate* group is the reference, not the largest group.

        A small group with a high rate must become the reference. Getting this wrong
        inverts the finding, and unequal group sizes are the norm in real data.
        """
        report = adverse_impact({"Large": (500, 1000), "Small": (9, 10)})

        assert report.reference_group == "Small"
        large = next(g for g in report.groups if g.name == "Large")
        assert large.impact_ratio == pytest.approx(0.5 / 0.9)
        assert large.flagged


class TestStatisticalReferenceValues:
    """Statistical results checkable against R and scipy."""

    def test_fisher_on_personality_example(self):
        """The published example's contingency table: p = 0.00340922...

        Verified against ``scipy.stats.fisher_exact([[12, 28], [48, 32]])``.
        """
        result = fisher_exact_2x2(12, 28, 48, 32)
        assert result.p_value == pytest.approx(0.0034092217678, abs=1e-12)
        assert result.significant_at_05

    def test_z_test_agrees_with_fisher_on_direction(self):
        """Both tests must agree the personality-test disparity is significant."""
        fisher = fisher_exact_2x2(12, 28, 48, 32)
        z = two_proportion_z(12, 40, 48, 80)

        assert fisher.significant_at_05
        assert z.significant_at_05
        assert z.statistic is not None and z.statistic < 0  # focal group lower

    def test_engineering_example_significance(self):
        """30/50 vs 80/100: real difference, and large enough to resolve."""
        result = two_proportion_z(30, 50, 80, 100)
        assert result.significant_at_05


class TestAgainstScipy:
    """Differential test against scipy's implementation.

    scipy is not a dependency -- the audit core is deliberately stdlib-only -- so
    these skip when it is absent. When it is present they are the strongest check
    available: an independent implementation of the same exact test, compared across
    a range of table shapes including degenerate ones.
    """

    @pytest.mark.parametrize(
        "table",
        [
            (12, 28, 48, 32),   # published personality-test example
            (3, 1, 1, 3),       # Fisher's tea tasting
            (8, 2, 1, 5),       # scipy documentation example
            (1, 49, 40, 10),    # extreme disparity
            (5, 5, 5, 5),       # parity
            (2, 7, 9, 3),       # small counts, reversed direction
            (0, 10, 10, 0),     # complete separation
            (1, 1, 1, 1),       # minimal table
            (15, 5, 5, 15),     # symmetric
            (100, 50, 50, 100), # large counts
            (0, 0, 5, 5),       # empty focal row
            (7, 0, 0, 7),       # zero cells on a diagonal
        ],
    )
    def test_fisher_matches_scipy(self, table):
        scipy_stats = pytest.importorskip("scipy.stats", reason="scipy not installed")
        a, b, c, d = table
        _, expected = scipy_stats.fisher_exact([[a, b], [c, d]])
        assert fisher_exact_2x2(a, b, c, d).p_value == pytest.approx(
            expected, rel=1e-9, abs=1e-15
        )


class TestRegressionAgainstKnownRatios:
    """Table-driven check across the full set of published ratios."""

    @pytest.mark.parametrize(
        "focal,focal_n,ref,ref_n,expected_ir,should_flag",
        [
            (40, 100, 60, 100, 2 / 3, True),      # 60/40 example
            (48, 100, 60, 100, 0.80, False),      # exactly at threshold
            (30, 50, 80, 100, 0.75, True),        # engineering example
            (12, 40, 48, 80, 0.50, True),         # personality test example
            (9, 10, 10, 10, 0.90, False),         # comfortably passing
            (0, 100, 50, 100, 0.00, True),        # total exclusion
            (50, 100, 50, 100, 1.00, False),      # parity
        ],
    )
    def test_published_and_boundary_ratios(
        self, focal, focal_n, ref, ref_n, expected_ir, should_flag
    ):
        report = adverse_impact({"Focal": (focal, focal_n), "Reference": (ref, ref_n)})
        focal_group = next(g for g in report.groups if g.name == "Focal")

        assert focal_group.impact_ratio == pytest.approx(expected_ir)
        assert focal_group.flagged is should_flag
        assert (focal_group.impact_ratio < FOUR_FIFTHS) is should_flag
