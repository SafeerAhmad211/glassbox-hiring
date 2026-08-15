"""Tests for the shipped examples.

README examples rot. These run the real script and assert on the specific numbers the
README quotes, so a change that alters documented output fails the build instead of
leaving the front page quietly wrong.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
sys.path.insert(0, str(EXAMPLES))

from end_to_end import COHORT_A, COHORT_B, RUBRIC, screen  # noqa: E402

from glassbox.audit.impact import adverse_impact, impact_ratio_curve  # noqa: E402
from glassbox.audit.perturb import run_perturbation_audit  # noqa: E402
from glassbox.score.rubric import score_resume  # noqa: E402


class TestEndToEndExampleRuns:
    def test_script_runs_cleanly(self):
        """The exact command the README tells people to type."""
        result = subprocess.run(
            [sys.executable, str(EXAMPLES / "end_to_end.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr

    def test_output_contains_each_documented_stage(self):
        result = subprocess.run(
            [sys.executable, str(EXAMPLES / "end_to_end.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        for stage in ("1. SCORE", "2. PERTURB", "3. ADVERSE IMPACT", "4. SWEEP"):
            assert stage in result.stdout


class TestReadmeNumbersAreCurrent:
    """Each assertion pins a number quoted in the README."""

    def test_first_candidate_scores_one(self):
        # README: "Match score: 1.000"
        assert score_resume(COHORT_A[0], RUBRIC).score == pytest.approx(1.0)

    def test_score_attribution_matches_documented_weights(self):
        # README shows +0.375 Python, +0.250 PostgreSQL, +0.250 Kubernetes, +0.125 Docker
        result = score_resume(COHORT_A[0], RUBRIC)
        points = {r.requirement.name: r.points for r in result.matched}
        assert points["Python"] == pytest.approx(0.375)
        assert points["PostgreSQL"] == pytest.approx(0.250)
        assert points["Kubernetes"] == pytest.approx(0.250)
        assert points["Docker"] == pytest.approx(0.125)

    def test_scorer_is_counterfactually_invariant(self):
        # README: "is_invariant -> True", spread {'name': 0.0, 'pronoun': 0.0}
        report = run_perturbation_audit(COHORT_A + COHORT_B, screen)
        assert report.is_invariant
        assert all(spread == 0.0 for spread in report.dimension_spread().values())

    def test_cohort_selection_counts(self):
        # README: Cohort A 5/6, Cohort B 1/6 at a 0.75 cut
        selected = {
            "Cohort A": sum(1 for r in COHORT_A if screen(r) >= 0.75),
            "Cohort B": sum(1 for r in COHORT_B if screen(r) >= 0.75),
        }
        assert selected == {"Cohort A": 5, "Cohort B": 1}

    def test_impact_ratio_and_shortfall(self):
        # README: IR=0.200, "needs 3 more selection(s)"
        report = adverse_impact({"Cohort A": (5, 6), "Cohort B": (1, 6)})
        cohort_b = next(g for g in report.groups if g.name == "Cohort B")
        assert cohort_b.impact_ratio == pytest.approx(0.2)
        assert cohort_b.shortfall == 3
        assert not report.passes_four_fifths

    def test_both_honesty_notes_are_emitted(self):
        """The README quotes both caveats; they must still fire."""
        report = adverse_impact({"Cohort A": (5, 6), "Cohort B": (1, 6)})
        notes = " ".join(report.notes)
        assert "Small samples" in notes
        assert "not significant" in notes

    def test_sweep_flips_verdict_across_thresholds(self):
        """README: PASS at the 10th percentile, FAIL at 25/50/75."""
        scores = {
            "Cohort A": [screen(r) for r in COHORT_A],
            "Cohort B": [screen(r) for r in COHORT_B],
        }
        curve = impact_ratio_curve(scores, percentiles=(10, 25, 50, 75))
        verdicts = {p.percentile: p.passes for p in curve}

        assert verdicts[10] is True
        assert verdicts[25] is False
        assert verdicts[50] is False
        assert verdicts[75] is False

    def test_documented_sweep_ratios(self):
        scores = {
            "Cohort A": [screen(r) for r in COHORT_A],
            "Cohort B": [screen(r) for r in COHORT_B],
        }
        ratios = {
            p.percentile: p.min_impact_ratio
            for p in impact_ratio_curve(scores, percentiles=(10, 25, 50, 75))
        }
        assert ratios[10] == pytest.approx(1.000)
        assert ratios[25] == pytest.approx(0.667, abs=1e-3)
        assert ratios[50] == pytest.approx(0.333, abs=1e-3)


class TestPdfFixtureGenerator:
    def test_make_test_pdf_runs(self, tmp_path):
        """The other shipped example; used by the parsing tests."""
        result = subprocess.run(
            [sys.executable, str(EXAMPLES / "make_test_pdf.py")],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
