"""Tests for counterfactual perturbation auditing.

The key tests use *deliberately biased* scorers with a known, planted effect size, so
the harness is checked against ground truth rather than against itself.
"""

from __future__ import annotations

import pytest

from glassbox.audit.perturb import (
    NAME_SETS,
    Perturbation,
    affiliation_swap,
    employment_gap,
    name_swap,
    pronoun_swap,
    run_perturbation_audit,
)

RESUME = """Jane Doe
jane@example.com

EXPERIENCE
Senior Engineer, Acme Corp (2020-2024)
He led the migration of his team's services. His work reduced latency 40%.

EDUCATION
Wellesley College, BS Computer Science
"""


class TestNameSwap:
    def test_replaces_first_nonempty_line(self):
        assert name_swap("Alan Turing")(RESUME).split("\n")[0] == "Alan Turing"

    def test_leaves_body_untouched(self):
        result = name_swap("Alan Turing")(RESUME)
        assert "Senior Engineer, Acme Corp" in result
        assert "Wellesley College" in result

    def test_handles_leading_blank_lines(self):
        assert name_swap("X")("\n\n\nJane Doe\nrest").split("\n")[3] == "X"

    def test_regex_targeting(self):
        result = name_swap("Alan Turing", original_pattern=r"Jane Doe")(RESUME)
        assert result.startswith("Alan Turing")

    def test_empty_text_is_safe(self):
        assert name_swap("X")("") == ""


class TestPronounSwap:
    def test_he_to_she(self):
        result = pronoun_swap("she")(RESUME)
        assert "She led the migration of her team's services." in result
        assert "Her work reduced latency" in result

    def test_he_to_they(self):
        result = pronoun_swap("they")(RESUME)
        assert "They led the migration of their team's services." in result

    def test_preserves_capitalisation(self):
        assert pronoun_swap("she")("He works. his work.") == "She works. her work."

    def test_preserves_all_caps(self):
        assert "HER" in pronoun_swap("she")("HIS RESUME")

    def test_word_boundaries_respected(self):
        """'his' inside 'history' must not be rewritten."""
        text = "Studied history and this thesis."
        assert pronoun_swap("she")(text) == text

    def test_idempotent_across_source_pronouns(self):
        """Swapping to 'they' works whether the source used he/him or she/her."""
        from_he = pronoun_swap("they")("He said his piece.")
        from_she = pronoun_swap("they")("She said her piece.")
        assert from_he == from_she == "They said their piece."

    def test_rejects_unknown_target(self):
        with pytest.raises(ValueError, match="must be one of"):
            pronoun_swap("xe")


class TestAffiliationSwap:
    def test_replaces_institution(self):
        result = affiliation_swap("Wellesley College", "Amherst College")(RESUME)
        assert "Amherst College" in result
        assert "Wellesley" not in result

    def test_case_insensitive(self):
        assert "Amherst" in affiliation_swap("wellesley college", "Amherst")(RESUME)

    def test_leaves_other_text_alone(self):
        result = affiliation_swap("Wellesley College", "Amherst College")(RESUME)
        assert "Acme Corp" in result


class TestEmploymentGap:
    def test_appends_gap(self):
        result = employment_gap(2)(RESUME)
        assert "Career break (2 years)" in result
        assert len(result) > len(RESUME)

    def test_singular_year(self):
        assert "1 year)" in employment_gap(1)(RESUME)

    def test_custom_text(self):
        assert "medical leave" in employment_gap(gap_text="medical leave")(RESUME)

    def test_preserves_original_content(self):
        assert "Wellesley College" in employment_gap()(RESUME)


class TestPerturbationAudit:
    def test_fair_scorer_is_invariant(self):
        """A scorer keying only on job-relevant content must show zero delta."""
        def fair_scorer(text: str) -> float:
            return 1.0 if "Senior Engineer" in text else 0.0

        report = run_perturbation_audit([RESUME], fair_scorer)
        assert report.is_invariant
        assert report.violations == []
        assert all(r.mean_delta == 0.0 for r in report.results)

    def test_detects_planted_name_bias(self):
        """A scorer penalising specific names must be caught, with the right sign."""
        penalised = NAME_SETS["black_associated_female"][0]

        def biased_scorer(text: str) -> float:
            return 0.3 if text.startswith(penalised) else 0.9

        report = run_perturbation_audit([RESUME], biased_scorer)
        assert not report.is_invariant

        violation = next(
            r for r in report.violations
            if r.perturbation == "name:black_associated_female"
        )
        assert violation.mean_delta == pytest.approx(-0.6)

    def test_dimension_spread_quantifies_name_sensitivity(self):
        """The headline number: best- minus worst-treated variant within a dimension."""
        penalised = NAME_SETS["black_associated_male"][0]

        def biased_scorer(text: str) -> float:
            return 0.2 if text.startswith(penalised) else 0.8

        spread = run_perturbation_audit([RESUME], biased_scorer).dimension_spread()
        assert spread["name"] == pytest.approx(0.6)
        assert spread["pronoun"] == pytest.approx(0.0)

    def test_detects_pronoun_bias(self):
        import re

        def gendered_scorer(text: str) -> float:
            # Word-boundary match: the swapped pronoun may begin a line.
            return 0.4 if re.search(r"\bshe\b", text, re.IGNORECASE) else 0.8

        report = run_perturbation_audit([RESUME], gendered_scorer)
        assert report.dimension_spread()["pronoun"] > 0.3

    def test_max_abs_delta_catches_offsetting_effects(self):
        """A mean near zero can hide large swings in opposite directions."""
        resumes = ["Alice\nengineer", "Bob\nengineer"]

        def erratic_scorer(text: str) -> float:
            # Raises one resume and lowers the other by the same amount.
            return 1.0 if text.startswith(NAME_SETS["asian_associated"][0]) else (
                0.5 if text.startswith("Alice") else 0.0
            )

        probe = Perturbation(
            name="name:asian_associated",
            dimension="name",
            apply=name_swap(NAME_SETS["asian_associated"][0]),
        )
        report = run_perturbation_audit(resumes, erratic_scorer, perturbations=[probe])
        result = report.results[0]
        assert result.max_abs_delta > 0
        assert result.n_changed == 2

    def test_tolerance_absorbs_scorer_noise(self):
        counter = {"n": 0}

        def noisy_scorer(text: str) -> float:
            counter["n"] += 1
            return 0.5 + (counter["n"] % 2) * 1e-6

        strict = run_perturbation_audit([RESUME], noisy_scorer, invariance_tolerance=0.0)
        assert not strict.is_invariant

        counter["n"] = 0
        lenient = run_perturbation_audit(
            [RESUME], noisy_scorer, invariance_tolerance=1e-3
        )
        assert lenient.is_invariant

    def test_aggregates_across_multiple_resumes(self):
        resumes = [RESUME, RESUME.replace("Jane Doe", "John Smith")]
        report = run_perturbation_audit(resumes, lambda t: float(len(t)))
        assert report.n_resumes == 2
        assert all(r.n_resumes == 2 for r in report.results)
        assert all(len(r.deltas) == 2 for r in report.results)

    def test_custom_perturbations(self):
        probe = Perturbation(
            name="gap:2y",
            dimension="career_gap",
            apply=employment_gap(2),
            note="two-year caregiving break",
        )

        def gap_penalising_scorer(text: str) -> float:
            return 0.2 if "Career break" in text else 0.9

        report = run_perturbation_audit([RESUME], gap_penalising_scorer, perturbations=[probe])
        assert report.results[0].mean_delta == pytest.approx(-0.7)

    def test_stdev_none_for_single_resume(self):
        report = run_perturbation_audit([RESUME], lambda t: 1.0)
        assert report.results[0].stdev_delta is None

    def test_rejects_empty_corpus(self):
        with pytest.raises(ValueError, match="no resumes"):
            run_perturbation_audit([], lambda t: 1.0)

    def test_rejects_negative_tolerance(self):
        with pytest.raises(ValueError, match="non-negative"):
            run_perturbation_audit([RESUME], lambda t: 1.0, invariance_tolerance=-1.0)
