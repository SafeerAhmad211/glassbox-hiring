"""Tests for the statistical primitives.

Reference values come from published examples and from R's ``fisher.test`` /
``scipy.stats``, so these tests catch drift against the wider ecosystem rather than
merely asserting that the code agrees with itself.
"""

from __future__ import annotations

import pytest

from glassbox.audit.stats import (
    fisher_exact_2x2,
    normal_cdf,
    standardized_mean_difference,
    two_proportion_z,
    wilson_interval,
)


class TestFisherExact:
    def test_fishers_tea_tasting(self):
        """Fisher's original tea-tasting experiment: p = 0.4857142857...

        The canonical 2x2 exact test. If this drifts, the hypergeometric enumeration
        or the small-p-value convention has broken.
        """
        result = fisher_exact_2x2(3, 1, 1, 3)
        assert result.p_value == pytest.approx(0.4857142857142857, rel=1e-12)
        assert not result.significant_at_05

    def test_scipy_documented_example(self):
        """``scipy.stats.fisher_exact([[8, 2], [1, 5]])`` gives p = 0.034965034965..."""
        result = fisher_exact_2x2(8, 2, 1, 5)
        assert result.p_value == pytest.approx(0.034965034965034975, rel=1e-12)
        assert result.significant_at_05

    def test_no_statistic_for_exact_test(self):
        assert fisher_exact_2x2(3, 1, 1, 3).statistic is None

    def test_symmetry_under_row_swap(self):
        """Swapping which group is focal must not change a two-sided p-value."""
        assert fisher_exact_2x2(8, 2, 1, 5).p_value == pytest.approx(
            fisher_exact_2x2(1, 5, 8, 2).p_value, rel=1e-12
        )

    def test_identical_rates_give_p_near_one(self):
        assert fisher_exact_2x2(5, 5, 5, 5).p_value == pytest.approx(1.0, abs=1e-12)

    def test_degenerate_table_returns_one(self):
        """A zero margin permits only one arrangement; p=1 is the honest answer."""
        result = fisher_exact_2x2(0, 10, 0, 10)
        assert result.p_value == 1.0
        assert "degenerate" in result.detail

    def test_p_value_never_exceeds_one(self):
        """Float accumulation must not push the summed probability past 1.0."""
        for a, b, c, d in [(1, 1, 1, 1), (2, 3, 3, 2), (7, 7, 7, 7), (1, 20, 20, 1)]:
            assert 0.0 <= fisher_exact_2x2(a, b, c, d).p_value <= 1.0

    def test_strong_disparity_is_significant(self):
        result = fisher_exact_2x2(1, 49, 40, 10)
        assert result.p_value < 1e-10

    def test_rejects_negative_counts(self):
        with pytest.raises(ValueError, match="non-negative"):
            fisher_exact_2x2(-1, 5, 5, 5)

    def test_rejects_empty_table(self):
        with pytest.raises(ValueError, match="empty"):
            fisher_exact_2x2(0, 0, 0, 0)


class TestTwoProportionZ:
    def test_known_z_statistic(self):
        """Hand-computed: p1=0.4, p2=0.6, pooled=0.5, n=100 each.

        z = (0.4-0.6) / sqrt(0.25 * (1/100 + 1/100)) = -0.2 / 0.0707107 = -2.828427
        """
        result = two_proportion_z(40, 100, 60, 100)
        assert result.statistic == pytest.approx(-2.8284271247, rel=1e-8)
        assert result.p_value == pytest.approx(0.004677734981, rel=1e-6)
        assert result.significant_at_05

    def test_identical_rates_give_zero_z(self):
        result = two_proportion_z(50, 100, 50, 100)
        assert result.statistic == pytest.approx(0.0)
        assert result.p_value == pytest.approx(1.0)

    def test_zero_variance_does_not_divide_by_zero(self):
        """Nobody selected in either group: rates are identical, not disparate."""
        result = two_proportion_z(0, 50, 0, 50)
        assert result.p_value == 1.0
        assert "zero variance" in result.detail

    def test_everybody_selected(self):
        assert two_proportion_z(50, 50, 50, 50).p_value == 1.0

    def test_rejects_empty_group(self):
        with pytest.raises(ValueError, match="positive"):
            two_proportion_z(0, 0, 5, 10)

    def test_rejects_selections_over_total(self):
        with pytest.raises(ValueError, match="cannot exceed"):
            two_proportion_z(11, 10, 5, 10)


class TestNormalCdf:
    @pytest.mark.parametrize(
        "x,expected",
        [
            (0.0, 0.5),
            (1.959963984540054, 0.975),
            (-1.959963984540054, 0.025),
            (1.0, 0.8413447460685429),
            (-3.0, 0.0013498980316301035),
        ],
    )
    def test_known_quantiles(self, x, expected):
        assert normal_cdf(x) == pytest.approx(expected, rel=1e-12)


class TestStandardizedMeanDifference:
    def test_known_cohens_d(self):
        """Focal mean 2, reference mean 4, pooled SD 1.0 -> d = -2.0.

        Negative because the focal group scored *lower*, per the documented
        convention (positive d means focal scored higher).
        """
        focal = [1.0, 2.0, 3.0]
        reference = [3.0, 4.0, 5.0]
        assert standardized_mean_difference(focal, reference) == pytest.approx(-2.0)

    def test_sign_convention_focal_higher_is_positive(self):
        d = standardized_mean_difference([10.0, 11.0, 12.0], [1.0, 2.0, 3.0])
        assert d is not None and d > 0

    def test_identical_distributions_give_zero(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        assert standardized_mean_difference(xs, list(xs)) == pytest.approx(0.0)

    def test_none_when_group_too_small(self):
        """None, not 0.0 -- 'cannot compute' is a different finding from 'no difference'."""
        assert standardized_mean_difference([1.0], [1.0, 2.0, 3.0]) is None

    def test_none_when_zero_variance(self):
        assert standardized_mean_difference([5.0] * 4, [5.0] * 4) is None


class TestWilsonInterval:
    def test_contains_point_estimate(self):
        lo, hi = wilson_interval(40, 100)
        assert lo < 0.4 < hi

    def test_known_bounds(self):
        """40/100 at 95%: Wilson gives approximately (0.3094, 0.4979)."""
        lo, hi = wilson_interval(40, 100)
        assert lo == pytest.approx(0.3094, abs=5e-4)
        assert hi == pytest.approx(0.4979, abs=5e-4)

    def test_stays_within_unit_interval_at_extremes(self):
        """Where the Wald interval would escape [0, 1], Wilson must not."""
        for successes, total in [(0, 10), (10, 10), (1, 3), (0, 1)]:
            lo, hi = wilson_interval(successes, total)
            assert 0.0 <= lo <= hi <= 1.0

    def test_no_data_gives_full_range(self):
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_interval_narrows_with_more_data(self):
        narrow = wilson_interval(400, 1000)
        wide = wilson_interval(4, 10)
        assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])

    def test_rejects_out_of_range_successes(self):
        with pytest.raises(ValueError, match="must be in"):
            wilson_interval(11, 10)
