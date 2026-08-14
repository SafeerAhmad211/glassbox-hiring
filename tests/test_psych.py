"""Tests for task scoring and psychometric indices.

Reference values are taken from the source papers' definitions and from standard
psychometric worked examples, so these check against the literature rather than
against the implementation.
"""

from __future__ import annotations

import pytest

from glassbox.psych.reliability import (
    cronbach_alpha,
    interpret_reliability,
    max_validity,
    percentile_rank,
    spearman_brown,
    split_half_reliability,
    standard_error_of_measurement,
    z_score,
)
from glassbox.psych.tasks import (
    BartTrial,
    bart_score,
    digit_span_score,
    flanker_score,
    stop_signal_rt,
    tower_of_london_score,
    trust_game_score,
)


class TestBart:
    def test_adjusted_pumps_excludes_exploded(self):
        """The defining feature of the standard measure."""
        trials = [
            BartTrial(pumps=10, exploded=False),
            BartTrial(pumps=20, exploded=False),
            BartTrial(pumps=5, exploded=True),  # must not drag the mean down
        ]
        assert bart_score(trials)["adjusted_pumps"] == pytest.approx(15.0)

    def test_total_pumps_includes_everything(self):
        trials = [BartTrial(10, False), BartTrial(20, False), BartTrial(5, True)]
        assert bart_score(trials)["total_pumps"] == pytest.approx(35.0)

    def test_explosion_rate(self):
        trials = [BartTrial(10, False), BartTrial(5, True)]
        assert bart_score(trials)["explosion_rate"] == pytest.approx(0.5)

    def test_none_when_all_exploded(self):
        """Cannot compute intended behaviour when every balloon was truncated."""
        assert bart_score([BartTrial(5, True), BartTrial(6, True)])["adjusted_pumps"] is None

    def test_learning_slope_positive_when_escalating(self):
        trials = [BartTrial(pumps=5 + i * 3, exploded=False) for i in range(6)]
        assert bart_score(trials)["learning_slope"] == pytest.approx(3.0)

    def test_learning_slope_none_with_too_few_trials(self):
        trials = [BartTrial(10, False), BartTrial(12, False)]
        assert bart_score(trials)["learning_slope"] is None

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="no trials"):
            bart_score([])


class TestDigitSpan:
    def test_max_span(self):
        results = [(3, True), (3, True), (4, True), (4, False), (5, False), (5, False)]
        assert digit_span_score(results)["max_span"] == 4.0

    def test_reliable_span_ignores_lucky_single_trial(self):
        """max_span rewards one lucky trial; reliable_span requires 2/3 correct."""
        results = [(3, True), (3, True), (4, True), (4, False), (4, False)]
        scores = digit_span_score(results)
        assert scores["max_span"] == 4.0
        assert scores["reliable_span"] == 3.0

    def test_accuracy(self):
        assert digit_span_score([(3, True), (3, False)])["accuracy"] == pytest.approx(0.5)

    def test_all_wrong_gives_zero_span(self):
        assert digit_span_score([(3, False), (4, False)])["max_span"] == 0.0

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="no results"):
            digit_span_score([])


class TestFlanker:
    def test_conflict_effect_is_the_difference(self):
        result = flanker_score([400.0, 420.0], [500.0, 520.0])
        assert result["conflict_effect"] == pytest.approx(100.0)

    def test_no_conflict_when_conditions_match(self):
        result = flanker_score([450.0, 450.0], [450.0, 450.0])
        assert result["conflict_effect"] == pytest.approx(0.0)

    def test_accuracy_when_counts_given(self):
        result = flanker_score(
            [400.0, 420.0], [500.0, 520.0],
            congruent_correct=2, incongruent_correct=1,
        )
        assert result["accuracy"] == pytest.approx(0.75)

    def test_rejects_empty_condition(self):
        with pytest.raises(ValueError, match="both conditions"):
            flanker_score([], [500.0])


class TestStopSignalRt:
    def test_integration_method(self):
        """Go RTs 100..1000 by 100, 50% inhibition, mean SSD 200.

        p(respond) = 0.5 -> nearest-rank index 4 (0-based) -> 500ms; 500 - 200 = 300.
        """
        go_rts = [float(i) for i in range(100, 1001, 100)]
        assert stop_signal_rt(go_rts, [200.0], 0.5) == pytest.approx(300.0)

    def test_none_when_success_rate_unreliable(self):
        """Outside [0.1, 0.9] SSRT estimates are not trustworthy; return None."""
        go_rts = [float(i) for i in range(100, 1001, 100)]
        assert stop_signal_rt(go_rts, [200.0], 0.95) is None
        assert stop_signal_rt(go_rts, [200.0], 0.05) is None

    def test_rejects_out_of_range_rate(self):
        with pytest.raises(ValueError, match="must be in"):
            stop_signal_rt([400.0], [200.0], 1.5)

    def test_rejects_empty_go_trials(self):
        with pytest.raises(ValueError, match="no go trials"):
            stop_signal_rt([], [200.0], 0.5)


class TestTowerOfLondon:
    def test_optimal_solutions(self):
        problems = [(3, 3, 1000.0), (4, 4, 1200.0), (6, 4, 800.0)]
        assert tower_of_london_score(problems)["solved_optimally"] == pytest.approx(2 / 3)

    def test_excess_moves(self):
        problems = [(3, 3, 1000.0), (6, 4, 800.0)]
        assert tower_of_london_score(problems)["excess_moves"] == pytest.approx(1.0)

    def test_planning_efficiency_negative_when_thinking_helps(self):
        """Longer first-move latency associated with fewer excess moves."""
        problems = [(8, 4, 200.0), (6, 4, 600.0), (4, 4, 1500.0)]
        efficiency = tower_of_london_score(problems)["planning_efficiency"]
        assert efficiency is not None and efficiency < -0.9

    def test_efficiency_none_with_too_few_problems(self):
        assert tower_of_london_score([(3, 3, 100.0)])["planning_efficiency"] is None

    def test_rejects_invalid_minimum(self):
        with pytest.raises(ValueError, match="at least 1"):
            tower_of_london_score([(3, 0, 100.0)])


class TestTrustGame:
    def test_trust_is_send_fraction(self):
        assert trust_game_score(sent=5.0, endowment=10.0)["trust"] == pytest.approx(0.5)

    def test_multiplier_applied(self):
        assert trust_game_score(5.0, 10.0)["amount_received"] == pytest.approx(15.0)

    def test_reciprocity(self):
        result = trust_game_score(5.0, 10.0, returned=6.0)
        assert result["reciprocity"] == pytest.approx(0.4)

    def test_reciprocity_none_without_return(self):
        assert trust_game_score(5.0, 10.0)["reciprocity"] is None

    def test_investor_payoff(self):
        assert trust_game_score(5.0, 10.0, returned=9.0)["investor_payoff"] == pytest.approx(14.0)

    def test_rejects_overspend(self):
        with pytest.raises(ValueError, match="must be in"):
            trust_game_score(sent=15.0, endowment=10.0)


class TestCronbachAlpha:
    def test_high_alpha_for_consistent_items(self):
        # Respondents differ; items agree within respondent.
        scores = [[5, 5, 5], [4, 4, 4], [3, 3, 3], [2, 2, 2], [1, 1, 1]]
        alpha = cronbach_alpha(scores)
        assert alpha is not None and alpha > 0.95

    def test_low_alpha_for_inconsistent_items(self):
        scores = [[5, 1, 3], [1, 5, 2], [3, 2, 5], [2, 4, 1], [4, 3, 4]]
        alpha = cronbach_alpha(scores)
        assert alpha is not None and alpha < 0.5

    def test_none_with_too_few_items(self):
        assert cronbach_alpha([[1], [2], [3]]) is None

    def test_none_with_zero_total_variance(self):
        assert cronbach_alpha([[3, 3], [3, 3], [3, 3]]) is None

    def test_rejects_ragged_rows(self):
        with pytest.raises(ValueError, match="same number of items"):
            cronbach_alpha([[1, 2, 3], [1, 2]])


class TestSpearmanBrown:
    def test_doubling_raises_reliability(self):
        """r=0.5 doubled -> 2(0.5)/(1+0.5) = 0.667."""
        assert spearman_brown(0.5, 2.0) == pytest.approx(2 / 3)

    def test_halving_lowers_reliability(self):
        assert spearman_brown(0.8, 0.5) < 0.8

    def test_perfect_reliability_unchanged(self):
        assert spearman_brown(1.0, 2.0) == pytest.approx(1.0)

    def test_rejects_nonpositive_factor(self):
        with pytest.raises(ValueError, match="must be positive"):
            spearman_brown(0.5, 0.0)


class TestSplitHalf:
    def test_corrected_upward_from_half_length(self):
        first = [1.0, 2.0, 3.0, 4.0, 5.0]
        second = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert split_half_reliability(first, second) == pytest.approx(1.0)

    def test_rejects_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same respondents"):
            split_half_reliability([1.0, 2.0], [1.0])


class TestStandardError:
    def test_known_value(self):
        """SD 15, reliability 0.80 -> 15 * sqrt(0.2) = 6.708."""
        assert standard_error_of_measurement(15.0, 0.80) == pytest.approx(6.7082, abs=1e-4)

    def test_perfect_reliability_gives_zero_error(self):
        assert standard_error_of_measurement(15.0, 1.0) == pytest.approx(0.0)

    def test_rejects_invalid_reliability(self):
        with pytest.raises(ValueError, match="must be in"):
            standard_error_of_measurement(15.0, 1.5)


class TestMaxValidity:
    def test_ceiling_from_test_reliability(self):
        """Reliability 0.60 caps validity at sqrt(0.60) = 0.7746."""
        assert max_validity(0.60) == pytest.approx(0.7746, abs=1e-4)

    def test_imperfect_criterion_lowers_ceiling_sharply(self):
        """The number vendors omit: a noisy criterion caps validity hard."""
        assert max_validity(0.80, 0.52) == pytest.approx(0.6450, abs=1e-4)

    def test_perfect_reliabilities_allow_perfect_validity(self):
        assert max_validity(1.0, 1.0) == pytest.approx(1.0)

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError, match="must be in"):
            max_validity(1.2)


class TestNorming:
    def test_percentile_rank_midpoint(self):
        assert percentile_rank(3.0, [1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(50.0)

    def test_percentile_rank_handles_ties(self):
        assert percentile_rank(2.0, [1.0, 2.0, 2.0, 3.0]) == pytest.approx(50.0)

    def test_percentile_bounds(self):
        norms = [1.0, 2.0, 3.0]
        assert percentile_rank(0.0, norms) == 0.0
        assert percentile_rank(10.0, norms) == 100.0

    def test_z_score(self):
        assert z_score(3.0, [1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(0.0)

    def test_z_score_none_for_zero_variance(self):
        assert z_score(3.0, [3.0, 3.0, 3.0]) is None

    def test_rejects_empty_norms(self):
        with pytest.raises(ValueError, match="norm sample is empty"):
            percentile_rank(1.0, [])


class TestInterpretReliability:
    def test_selection_standard_is_stricter_than_research(self):
        """0.85 is 'good' for research but only marginal for individual decisions."""
        assert "Good" in interpret_reliability(0.85, use="research")
        assert "Marginal" in interpret_reliability(0.85, use="selection")

    def test_high_reliability_adequate_for_selection(self):
        assert "Adequate" in interpret_reliability(0.92, use="selection")

    def test_low_reliability_called_out(self):
        assert "measurement error" in interpret_reliability(0.40)

    def test_rejects_unknown_use(self):
        with pytest.raises(ValueError, match="must be"):
            interpret_reliability(0.8, use="clinical")
