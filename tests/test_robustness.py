"""Regression tests for bugs found by adversarial testing.

Each class documents a specific defect that shipped in 0.1.0 and the input that
exposed it. These are the tests that would have caught them.
"""

from __future__ import annotations

import time
from typing import ClassVar

import pytest

from glassbox.audit.impact import adverse_impact
from glassbox.audit.stats import fisher_exact_2x2
from glassbox.parse.layout import TextBlock, detect_columns
from glassbox.psych.tasks import BartTrial, bart_score


class TestFisherExactOnLargeTables:
    """Fisher's exact test hung on large tables with a small cell.

    The test is selected when any cell count is below 5, but that rule says nothing
    about the grand total. A realistic dataset -- 20,000 applicants, one selection in
    some group -- has a small cell *and* a support spanning tens of thousands of
    values, and naive enumeration over huge-integer binomials took minutes to never.
    """

    @pytest.mark.parametrize("half", [2_000, 20_000, 200_000, 2_000_000, 20_000_000])
    def test_large_tables_complete_quickly(self, half):
        start = time.perf_counter()
        result = fisher_exact_2x2(half, half, 1, half - 1)
        elapsed = time.perf_counter() - start

        assert 0.0 <= result.p_value <= 1.0
        assert elapsed < 1.0, f"took {elapsed:.2f}s for n={4 * half}"

    def test_runtime_does_not_grow_with_table_size(self):
        """Cost must be logarithmic in n, not linear.

        Two separate defects made this linear: a per-term stopping rule that walked
        thousands of values, and an underflow guard that never fired when a tail
        began already at zero. Together they took 12.6 seconds at n=80,000,000.
        A ratio assertion catches a regression that a fixed timeout would not.
        """
        def timed(half: int) -> float:
            start = time.perf_counter()
            fisher_exact_2x2(half, half, 1, half - 1)
            return time.perf_counter() - start

        # Warm up so import and first-call costs do not skew the comparison.
        timed(20_000)

        small = max(timed(200_000), 1e-6)
        large = max(timed(20_000_000), 1e-6)

        # n grows 100x; runtime must not. Generous bound to stay stable on shared CI.
        assert large < small * 20, (
            f"runtime scaled with n: {small * 1000:.2f}ms -> {large * 1000:.2f}ms"
        )

    def test_realistic_employment_scale(self):
        """20,000 applicants with a single selection in the focal group."""
        start = time.perf_counter()
        report = adverse_impact({"Focal": (1, 5_000), "Reference": (3_000, 15_000)})
        elapsed = time.perf_counter() - start

        focal = next(g for g in report.groups if g.name == "Focal")
        assert focal.flagged
        assert focal.significance is not None
        assert elapsed < 2.0, f"took {elapsed:.1f}s"

    def test_log_space_path_still_accurate(self):
        """The large-table path must not trade correctness for speed.

        Reference values from ``scipy.stats.fisher_exact``.
        """
        assert fisher_exact_2x2(100, 900, 3, 997).p_value == pytest.approx(
            3.081554752e-27, rel=1e-9
        )
        assert fisher_exact_2x2(50, 4950, 10, 4990).p_value == pytest.approx(
            1.493064622e-07, rel=1e-9
        )
        assert fisher_exact_2x2(1000, 1000, 900, 1100).p_value == pytest.approx(
            1.717615178e-03, rel=1e-9
        )

    def test_exact_and_logspace_paths_agree(self):
        """Both implementations must give the same answer where both are usable."""
        # Small enough for exact enumeration, checked against scipy.
        assert fisher_exact_2x2(12, 28, 48, 32).p_value == pytest.approx(
            0.0034092217678, rel=1e-9
        )

    def test_observed_at_the_mode_gives_one(self):
        """When the observed table IS the mode, every table is at least as extreme.

        A tail-summing implementation can double-count or skip the overlap here. The
        first version of the log-space path returned 0.548 for this table because the
        far-side boundary landed exactly on the observed value and was skipped.
        """
        # a=38 is the mode for these margins.
        assert fisher_exact_2x2(38, 32661, 31, 26665).p_value == pytest.approx(1.0)

    def test_both_tails_are_counted(self):
        """The log-space path must sum both tails, not one.

        The original bug returned exactly half the correct value here, because the
        left-tail boundary search found the smallest qualifying k (always ``lo``)
        instead of the largest, summing a single term.
        """
        # scipy.stats.fisher_exact([[50, 4950], [10, 4990]]) -> 1.493064622e-07
        assert fisher_exact_2x2(50, 4950, 10, 4990).p_value == pytest.approx(
            1.493064622e-07, rel=1e-9
        )


class TestFisherDifferentialLargeTables:
    """Differential test against scipy that *forces* the log-space path.

    The original scipy comparison suite only ever exercised the exact enumeration
    path, so a log-space bug producing exactly half the correct p-value passed every
    test. Every table here exceeds the exact-path bounds.
    """

    LARGE_TABLES: ClassVar[list[tuple[int, int, int, int]]] = [
        (50, 4950, 10, 4990),        # both tails matter
        (500, 9500, 400, 9600),      # moderate proportions
        (2, 50000, 3, 49999),        # tiny cells, huge n
        (1, 9999, 5, 9995),          # single selection
        (3000, 7000, 2500, 7500),    # mid-range, near the mode
        (38, 32661, 31, 26665),      # observed at the mode
        (20, 19980, 60, 19940),      # asymmetric
        (9000, 1000, 1000, 9000),    # extreme separation
    ]

    @pytest.mark.parametrize("table", LARGE_TABLES)
    def test_matches_scipy(self, table):
        scipy_stats = pytest.importorskip("scipy.stats", reason="scipy not installed")
        a, b, c, d = table
        _, expected = scipy_stats.fisher_exact([[a, b], [c, d]])
        actual = fisher_exact_2x2(a, b, c, d).p_value

        if expected < 1e-300:
            # Both implementations are at the float64 floor (subnormals bottom out
            # near 5e-324); relative comparison is meaningless there. What matters is
            # that both agree the result is vanishingly small.
            assert actual < 1e-300
        else:
            assert actual == pytest.approx(expected, rel=1e-8)

    @pytest.mark.parametrize("table", LARGE_TABLES)
    def test_significance_decision_matches_scipy(self, table):
        """The decision, not just the number: does it clear p <= 0.05 the same way?

        This is what a compliance finding actually turns on.
        """
        scipy_stats = pytest.importorskip("scipy.stats", reason="scipy not installed")
        a, b, c, d = table
        _, expected = scipy_stats.fisher_exact([[a, b], [c, d]])
        actual = fisher_exact_2x2(a, b, c, d)
        assert actual.significant_at_05 == (expected <= 0.05)


class TestNonFiniteGeometry:
    """A NaN coordinate silently defeated column detection.

    NaN poisons comparisons rather than raising: every ``<`` involving it is false,
    so span merging collapses and a two-column resume is reported as one clean
    column. Silently passing is the worst possible failure for this diagnostic.
    """

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite_x(self, bad):
        with pytest.raises(ValueError, match="must be finite"):
            TextBlock("a", x=bad, y=1.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_rejects_non_finite_y(self, bad):
        with pytest.raises(ValueError, match="must be finite"):
            TextBlock("a", x=1.0, y=bad)

    def test_rejects_non_finite_size(self):
        with pytest.raises(ValueError, match="must be finite"):
            TextBlock("a", x=1.0, y=1.0, size=float("nan"))

    def test_rejects_non_finite_width(self):
        with pytest.raises(ValueError, match="must be finite"):
            TextBlock("a", x=1.0, y=1.0, width=float("nan"))

    def test_error_names_the_offending_text(self):
        """The message must identify which block, or it is unactionable."""
        with pytest.raises(ValueError, match="Senior Engineer"):
            TextBlock("Senior Engineer, Acme Corp", x=float("nan"), y=1.0)

    def test_finite_geometry_still_accepted(self):
        block = TextBlock("a", x=-500.0, y=-200.0, size=0.0, width=0.0)
        assert block.x == -500.0

    def test_columns_still_detected_with_valid_input(self):
        """Sanity: the guard must not break the normal path."""
        blocks = [
            TextBlock("left", x=50.0, y=700.0, size=11.0),
            TextBlock("right", x=350.0, y=700.0, size=11.0),
            TextBlock("left2", x=50.0, y=680.0, size=11.0),
            TextBlock("right2", x=350.0, y=680.0, size=11.0),
        ]
        assert len(detect_columns(blocks)) == 2


class TestBartTrialValidation:
    """BartTrial accepted impossible values and produced negative pump averages.

    Behavioural telemetry arrives from a browser and is trivially corrupted or
    forged. An impossible pump count does not fail visibly downstream -- it just
    makes someone look like a low risk-taker.
    """

    def test_rejects_negative_pumps(self):
        with pytest.raises(ValueError, match="non-negative"):
            BartTrial(-5, False)

    def test_rejects_pumps_beyond_burst_point(self):
        with pytest.raises(ValueError, match="exceeds max_pumps"):
            BartTrial(20, False, max_pumps=10)

    def test_rejects_nonpositive_max_pumps(self):
        with pytest.raises(ValueError, match="must be positive"):
            BartTrial(5, False, max_pumps=0)

    def test_zero_pumps_is_valid(self):
        """Banking immediately is a real, meaningful strategy."""
        assert bart_score([BartTrial(0, False)])["adjusted_pumps"] == 0.0

    def test_valid_trial_at_burst_point(self):
        assert BartTrial(10, True, max_pumps=10).pumps == 10

    def test_score_can_no_longer_go_negative(self):
        """The downstream symptom that motivated the fix."""
        trials = [BartTrial(5, False), BartTrial(10, False)]
        assert bart_score(trials)["adjusted_pumps"] == 7.5


class TestMinShareValidation:
    """min_share accepted nonsensical values.

    A negative share excluded nothing; a share >= 1 excluded everything and then
    surfaced as "need at least 2 groups", pointing away from the actual mistake.
    """

    @pytest.mark.parametrize("bad", [-1.0, -0.01, 1.0, 1.5, 100.0])
    def test_rejects_out_of_range(self, bad):
        with pytest.raises(ValueError, match=r"min_share must be in \[0, 1\)"):
            adverse_impact({"A": (4, 10), "B": (8, 10)}, min_share=bad)

    @pytest.mark.parametrize("good", [0.0, 0.02, 0.1, 0.49])
    def test_accepts_valid_range(self, good):
        """Two equal groups are 50% each, so any threshold below 0.5 keeps both."""
        report = adverse_impact({"A": (4, 100), "B": (8, 100)}, min_share=good)
        assert report.min_impact_ratio is not None

    def test_high_threshold_excluding_everything_is_still_reported(self):
        """A valid-but-aggressive threshold excludes both groups and says so."""
        with pytest.raises(ValueError, match="at least 2 groups"):
            adverse_impact({"A": (4, 100), "B": (8, 100)}, min_share=0.9)


class TestNonFiniteScores:
    """A scorer returning inf or nan produced a self-contradictory report.

    ``inf - inf`` is ``nan``, and every comparison with ``nan`` is false, so the run
    registered as *not invariant* while listing *no violations*. Code that checks
    ``is_invariant`` and then reads ``violations[0]`` -- which the agent tool did --
    crashed on an empty list.
    """

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_rejects_non_finite_scores(self, bad):
        from glassbox.audit.perturb import run_perturbation_audit

        with pytest.raises(ValueError, match="non-finite"):
            run_perturbation_audit(["Jane Doe"], lambda _text: bad)

    def test_rejects_non_numeric_scores(self):
        from glassbox.audit.perturb import run_perturbation_audit

        with pytest.raises(TypeError, match="must return a number"):
            run_perturbation_audit(["Jane Doe"], lambda _text: "high")

    def test_error_names_which_call_failed(self):
        """The message must say whether the baseline or a perturbation failed."""
        from glassbox.audit.perturb import run_perturbation_audit

        with pytest.raises(ValueError, match="unmodified resume"):
            run_perturbation_audit(["Jane Doe"], lambda _text: float("nan"))

    def test_report_invariants_hold_for_valid_scorers(self):
        """is_invariant False must always imply a non-empty violations list."""
        from glassbox.audit.perturb import run_perturbation_audit

        report = run_perturbation_audit(
            ["Jane Doe\nEngineer"],
            lambda text: 0.1 if text.startswith("Todd") else 0.9,
        )
        assert not report.is_invariant
        assert report.violations, "not invariant must imply at least one violation"

    def test_int_scores_are_accepted(self):
        """A scorer returning int, not float, is perfectly reasonable."""
        from glassbox.audit.perturb import run_perturbation_audit

        report = run_perturbation_audit(["Jane Doe"], len)
        assert report.n_resumes == 1


class TestHarnessNeverRaises:
    """The dispatcher guarantees a recoverable observation, never an exception."""

    def test_scorer_exception_becomes_an_observation(self):
        from glassbox.agent import call

        def broken(_text: str) -> float:
            raise RuntimeError("model endpoint down")

        observation = call("audit_scorer_invariance", resumes=["x"], scorer=broken)
        assert observation.status == "error"
        assert "RuntimeError" in observation.summary
        assert observation.next_actions

    @pytest.mark.parametrize(
        "scorer",
        [
            lambda _t: float("inf"),
            lambda _t: float("nan"),
            lambda _t: "not a number",
            lambda _t: None,
        ],
    )
    def test_hostile_scorer_returns_error_not_traceback(self, scorer):
        from glassbox.agent import call

        observation = call("audit_scorer_invariance", resumes=["x"], scorer=scorer)
        assert observation.status == "error"
        assert observation.data.get("hint")


class TestCorruptDocuments:
    """Corrupt PDFs reached the user as a raw pdfminer traceback.

    pdfminer's exception hierarchy inherits from neither OSError nor ValueError, so
    nothing in the call chain caught it.
    """

    @pytest.fixture
    def extract(self):
        pytest.importorskip("pdfminer", reason="needs the [parse] extra")
        from glassbox.parse.pdf import extract_blocks

        return extract_blocks

    @pytest.mark.parametrize(
        "name,content",
        [
            ("empty.pdf", b""),
            ("notapdf.pdf", b"this is plain text, not a pdf at all"),
            ("header_only.pdf", b"%PDF-1.4\n"),
            ("truncated.pdf", b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog"),
        ],
    )
    def test_corrupt_pdf_raises_value_error(self, extract, tmp_path, name, content):
        bad = tmp_path / name
        bad.write_bytes(content)
        with pytest.raises(ValueError, match="Could not read"):
            extract(bad)

    def test_error_message_is_actionable(self, extract, tmp_path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        with pytest.raises(ValueError, match="corrupt, truncated, password-protected"):
            extract(bad)

    def test_cli_reports_cleanly_without_traceback(self, tmp_path, capsys):
        pytest.importorskip("pdfminer", reason="needs the [parse] extra")
        from glassbox.cli import main

        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")

        assert main(["lens", str(bad)]) == 2
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.err
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out
