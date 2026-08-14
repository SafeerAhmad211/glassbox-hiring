"""Tests for adverse-impact analysis.

The worked example in ``TestUGESPWorkedExample`` is the one from the EEOC's own
Uniform Guidelines Q&A, which makes it a genuine external check on the four-fifths
implementation rather than a self-consistency test.
"""

from __future__ import annotations

import pytest

from glassbox.audit.impact import (
    FOUR_FIFTHS,
    LL144_MIN_SHARE,
    GroupOutcome,
    adverse_impact,
    impact_ratio_curve,
    outcomes_from_scores,
    score_gap_report,
)


class TestGroupOutcome:
    def test_selection_rate(self):
        assert GroupOutcome("A", 40, 100).selection_rate == 0.4

    def test_empty_group_rate_is_zero_not_error(self):
        assert GroupOutcome("A", 0, 0).selection_rate == 0.0

    def test_rejects_selected_over_total(self):
        with pytest.raises(ValueError, match="exceeds total"):
            GroupOutcome("A", 11, 10)

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="non-negative"):
            GroupOutcome("A", -1, 10)


class TestUGESPWorkedExample:
    """The canonical EEOC example: 80 of 100 white, 40 of 100 Black applicants hired.

    Rates 0.80 and 0.40; impact ratio 0.40/0.80 = 0.50, well below four-fifths.
    """

    @pytest.fixture
    def report(self):
        return adverse_impact(
            {"White": (80, 100), "Black": (40, 100)}, category="race/ethnicity"
        )

    def test_reference_is_highest_selecting_group(self, report):
        assert report.reference_group == "White"

    def test_impact_ratio(self, report):
        black = next(g for g in report.groups if g.name == "Black")
        assert black.impact_ratio == pytest.approx(0.5)

    def test_flags_adverse_impact(self, report):
        assert not report.passes_four_fifths
        assert report.min_impact_ratio == pytest.approx(0.5)
        assert [g.name for g in report.flagged_groups] == ["Black"]

    def test_reference_group_has_no_ratio(self, report):
        white = next(g for g in report.groups if g.name == "White")
        assert white.impact_ratio is None
        assert white.is_reference

    def test_disparity_is_statistically_significant(self, report):
        black = next(g for g in report.groups if g.name == "Black")
        assert black.significance is not None
        assert black.significance.significant_at_05

    def test_uses_z_test_when_cells_are_large(self, report):
        black = next(g for g in report.groups if g.name == "Black")
        assert "Z" in black.significance.test

    def test_shortfall_is_actionable(self, report):
        """To reach IR 0.8 against a 0.80 reference rate: 64 selections needed.

        64 - 40 = 24 additional. Note 0.8*0.8*100 == 64.00000000000001 in binary
        floating point; a naive ceil() yields 65 and over-states the remedy by one.
        """
        black = next(g for g in report.groups if g.name == "Black")
        assert black.shortfall == 24


class TestShortfallProperty:
    """Applying the reported shortfall must actually clear the four-fifths bar.

    This is the property the shortfall claims to have, checked directly across a wide
    grid rather than at one hand-worked point -- it is what catches off-by-one and
    floating-point drift in the remedy arithmetic.
    """

    @pytest.mark.parametrize("ref_selected", [1, 7, 40, 64, 80, 99, 100])
    @pytest.mark.parametrize("focal_total", [7, 33, 100, 257])
    def test_applying_shortfall_reaches_four_fifths(self, ref_selected, focal_total):
        report = adverse_impact(
            {"Ref": (ref_selected, 100), "Focal": (0, focal_total)},
        )
        focal = next(g for g in report.groups if g.name == "Focal")
        if focal.impact_ratio is None or focal.shortfall == 0:
            return

        remedied = adverse_impact(
            {"Ref": (ref_selected, 100), "Focal": (focal.shortfall, focal_total)},
        )
        remedied_focal = next(g for g in remedied.groups if g.name == "Focal")
        # The remedied group may itself become the reference; either way it must
        # no longer be flagged.
        assert not remedied_focal.flagged

    @pytest.mark.parametrize("focal_total", [7, 33, 100, 257])
    def test_shortfall_is_minimal(self, focal_total):
        """One fewer selection than reported must still fail -- no over-prescribing."""
        report = adverse_impact({"Ref": (80, 100), "Focal": (0, focal_total)})
        focal = next(g for g in report.groups if g.name == "Focal")
        if focal.shortfall <= 1:
            return

        under = adverse_impact(
            {"Ref": (80, 100), "Focal": (focal.shortfall - 1, focal_total)}
        )
        under_focal = next(g for g in under.groups if g.name == "Focal")
        assert under_focal.flagged


class TestPassingCase:
    def test_no_flag_when_ratio_above_threshold(self):
        report = adverse_impact({"A": (50, 100), "B": (45, 100)})
        assert report.passes_four_fifths
        assert report.min_impact_ratio == pytest.approx(0.9)
        assert report.flagged_groups == []

    def test_exactly_at_threshold_passes(self):
        """IR == 0.8 exactly is not "less than four-fifths", so it does not flag."""
        report = adverse_impact({"A": (50, 100), "B": (40, 100)})
        assert report.min_impact_ratio == pytest.approx(FOUR_FIFTHS)
        assert report.passes_four_fifths

    def test_no_shortfall_when_passing(self):
        report = adverse_impact({"A": (50, 100), "B": (45, 100)})
        assert all(g.shortfall == 0 for g in report.groups)


class TestSmallSampleHandling:
    def test_uses_fisher_when_cells_are_small(self):
        report = adverse_impact({"A": (4, 5), "B": (1, 5)})
        b = next(g for g in report.groups if g.name == "B")
        assert "Fisher" in b.significance.test

    def test_warns_about_small_samples(self):
        report = adverse_impact({"A": (4, 5), "B": (1, 5)})
        assert any("Small samples" in n for n in report.notes)
        assert any("1607.4(D)" in n for n in report.notes)

    def test_flags_but_notes_insignificance(self):
        """The 1607.4(D) carve-out: big ratio gap, too few people to conclude."""
        report = adverse_impact({"A": (3, 4), "B": (1, 4)})
        assert not report.passes_four_fifths
        assert any("not significant" in n for n in report.notes)

    def test_notes_significant_disparity_that_still_passes(self):
        """The reverse carve-out: passes 0.8 but significant, so not clearance."""
        report = adverse_impact({"A": (900, 1000), "B": (760, 1000)})
        assert report.passes_four_fifths
        assert any("Clears 0.8" in n for n in report.notes)


class TestExclusions:
    def test_ll144_two_percent_exclusion(self):
        """LL144 permits excluding categories under 2% of the data."""
        report = adverse_impact(
            {"A": (50, 100), "B": (40, 100), "Tiny": (0, 3)},
            min_share=LL144_MIN_SHARE,
        )
        assert any(name == "Tiny" for name, _ in report.excluded)
        assert "Tiny" not in [g.name for g in report.groups]

    def test_exclusion_reason_is_recorded(self):
        report = adverse_impact(
            {"A": (50, 100), "B": (40, 100), "Tiny": (0, 3)},
            min_share=LL144_MIN_SHARE,
        )
        reason = next(r for name, r in report.excluded if name == "Tiny")
        assert "1.46%" in reason or "%" in reason

    def test_nothing_excluded_by_default(self):
        """Default min_share=0 keeps small groups: dropping them silently hides disparity."""
        report = adverse_impact({"A": (50, 100), "B": (40, 100), "Tiny": (0, 3)})
        assert "Tiny" in [g.name for g in report.groups]

    def test_empty_groups_are_excluded_with_reason(self):
        report = adverse_impact({"A": (50, 100), "B": (40, 100), "Empty": (0, 0)})
        assert ("Empty", "no observations") in report.excluded

    def test_raises_when_fewer_than_two_groups_remain(self):
        with pytest.raises(ValueError, match="at least 2 groups"):
            adverse_impact({"A": (50, 100), "Tiny": (0, 1)}, min_share=0.5)


class TestDegenerateCases:
    def test_nobody_selected_anywhere(self):
        """Cut score above every score: ratios undefined, and the report says why."""
        report = adverse_impact({"A": (0, 100), "B": (0, 100)})
        assert report.min_impact_ratio is None
        assert report.passes_four_fifths  # vacuously; the note carries the finding
        assert any("undefined" in n for n in report.notes)

    def test_everyone_selected_everywhere(self):
        report = adverse_impact({"A": (100, 100), "B": (100, 100)})
        assert report.min_impact_ratio == pytest.approx(1.0)

    def test_accepts_group_outcome_objects(self):
        report = adverse_impact(
            [GroupOutcome("A", 50, 100), GroupOutcome("B", 40, 100)]
        )
        assert report.min_impact_ratio == pytest.approx(0.8)


class TestOutcomesFromScores:
    def test_counts_at_or_above_threshold(self):
        outcomes = outcomes_from_scores({"A": [1.0, 2.0, 3.0, 4.0]}, threshold=3.0)
        assert outcomes[0].selected == 2

    def test_lower_is_better_direction(self):
        outcomes = outcomes_from_scores(
            {"A": [1.0, 2.0, 3.0, 4.0]}, threshold=2.0, higher_is_better=False
        )
        assert outcomes[0].selected == 2


class TestImpactRatioCurve:
    """The threshold-dependence result from the FAccT pymetrics audit."""

    def test_which_group_is_disadvantaged_flips_with_threshold(self):
        """The strongest form of threshold dependence: the *harmed group changes*.

        Group B's scores are compressed into the middle of the range. A low cut
        admits all of B but only the top 61% of A, so A is disadvantaged. A high cut
        excludes B entirely while A's top scorers sail through, reversing it.

        An audit reporting one ratio at one undisclosed threshold could describe
        either group as the harmed one, from the same model and the same data.
        """
        scores = {
            "A": [float(i) for i in range(100)],
            "B": [float(40 + (i % 20)) for i in range(100)],
        }
        curve = impact_ratio_curve(scores, percentiles=(20, 90))
        worst = {p.percentile: p.worst_group for p in curve}

        assert worst[20] == "A"
        assert worst[90] == "B"

    def test_ratio_varies_materially_with_threshold(self):
        scores = {
            "A": [float(i) for i in range(100)],
            "B": [float(40 + (i % 20)) for i in range(100)],
        }
        curve = impact_ratio_curve(scores, percentiles=(20, 50, 90))
        ratios = [p.min_impact_ratio for p in curve if p.min_impact_ratio is not None]
        assert max(ratios) - min(ratios) > 0.3

    def test_pymetrics_tier_thresholds_can_disagree(self):
        """pymetrics searched for fairness at the 70th but deployed cuts at 50th too."""
        scores = {
            "A": [float(i) for i in range(200)],
            "B": [float(i % 130) for i in range(200)],
        }
        curve = impact_ratio_curve(scores, percentiles=(50, 70))
        assert len(curve) == 2
        assert curve[0].min_impact_ratio != curve[1].min_impact_ratio

    def test_selection_rate_falls_as_threshold_rises(self):
        scores = {"A": [float(i) for i in range(100)], "B": [float(i) for i in range(100)]}
        curve = impact_ratio_curve(scores, percentiles=(10, 50, 90))
        rates = [p.overall_selection_rate for p in curve]
        assert rates == sorted(rates, reverse=True)

    def test_identifies_worst_group(self):
        scores = {"A": [float(i) for i in range(100)], "B": [0.0] * 100}
        curve = impact_ratio_curve(scores, percentiles=(90,))
        assert curve[0].worst_group == "B"

    def test_raises_on_empty_input(self):
        with pytest.raises(ValueError, match="no scores"):
            impact_ratio_curve({"A": [], "B": []})


class TestScoreGapReport:
    def test_reference_group_is_zero(self):
        gaps = score_gap_report({"A": [5.0, 6.0, 7.0], "B": [1.0, 2.0, 3.0]})
        assert gaps["A"] == 0.0

    def test_lower_scoring_group_is_negative(self):
        gaps = score_gap_report({"A": [5.0, 6.0, 7.0], "B": [1.0, 2.0, 3.0]})
        assert gaps["B"] is not None and gaps["B"] < 0

    def test_threshold_free_unlike_impact_ratio(self):
        """The point of this metric: no cut score is involved, so none can be gamed.

        A uniform 10-point shift over 0..99 (pooled SD 29.011) gives d = -0.34469.
        """
        scores = {"A": [float(i) for i in range(100)], "B": [float(i) - 10 for i in range(100)]}
        assert score_gap_report(scores)["B"] == pytest.approx(-0.34469, abs=1e-5)

    def test_explicit_reference(self):
        gaps = score_gap_report(
            {"A": [5.0, 6.0, 7.0], "B": [1.0, 2.0, 3.0]}, reference="B"
        )
        assert gaps["B"] == 0.0
        assert gaps["A"] is not None and gaps["A"] > 0

    def test_rejects_unknown_reference(self):
        with pytest.raises(ValueError, match="not in data"):
            score_gap_report({"A": [1.0, 2.0], "B": [1.0, 2.0]}, reference="C")

    def test_none_for_ungoverned_group(self):
        """A single-observation group yields None, not a fake zero."""
        gaps = score_gap_report({"A": [1.0, 2.0, 3.0], "B": [2.0]})
        assert gaps["B"] is None
