"""Tests for rubric scoring.

``TestCounterfactualInvariance`` is the load-bearing one: it wires the scorer into the
perturbation harness and asserts the property the whole design exists to guarantee.
"""

from __future__ import annotations

import pytest

from glassbox.audit.perturb import run_perturbation_audit
from glassbox.score.rubric import Requirement, Rubric, score_resume

RESUME = """Jane Doe
jane@example.com

EXPERIENCE
Senior Engineer, Acme Corp (2020-2024)
Built distributed services in Python and Go.
Managed PostgreSQL clusters and Docker deployments.

EDUCATION
BS Computer Science, State University
"""


@pytest.fixture
def rubric():
    return Rubric(
        [
            Requirement("Python", ("python",), weight=3.0, required=True),
            Requirement("PostgreSQL", ("postgres", "postgresql"), weight=2.0),
            Requirement("Kubernetes", ("kubernetes", "k8s"), weight=2.0, required=True),
            Requirement("Docker", ("docker",), weight=1.0),
        ],
        name="Backend Engineer",
    )


class TestRequirement:
    def test_rejects_empty_patterns(self):
        with pytest.raises(ValueError, match="at least one pattern"):
            Requirement("X", ())

    def test_rejects_nonpositive_weight(self):
        with pytest.raises(ValueError, match="weight must be positive"):
            Requirement("X", ("x",), weight=0.0)


class TestRubric:
    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="at least one requirement"):
            Rubric([])

    def test_rejects_duplicate_names(self):
        with pytest.raises(ValueError, match="duplicate requirement names"):
            Rubric([Requirement("X", ("a",)), Requirement("X", ("b",))])

    def test_from_skills(self):
        built = Rubric.from_skills(required=["Python"], preferred=["Docker"])
        assert len(built.requirements) == 2
        assert built.requirements[0].required
        assert not built.requirements[1].required

    def test_from_skills_rejects_empty(self):
        with pytest.raises(ValueError, match="at least one required or preferred"):
            Rubric.from_skills()


class TestScoring:
    def test_score_is_sum_of_matched_weight_shares(self, rubric):
        """Python(3) + Postgres(2) + Docker(1) matched, Kubernetes(2) not. 6/8 = 0.75."""
        assert score_resume(RESUME, rubric).score == pytest.approx(0.75)

    def test_score_in_unit_interval(self, rubric):
        assert 0.0 <= score_resume(RESUME, rubric).score <= 1.0

    def test_perfect_match_scores_one(self):
        simple = Rubric([Requirement("Python", ("python",))])
        assert score_resume("I use Python", simple).score == pytest.approx(1.0)

    def test_no_match_scores_zero(self):
        simple = Rubric([Requirement("Rust", ("rust",))])
        assert score_resume(RESUME, simple).score == 0.0

    def test_breakdown_sums_exactly_to_score(self, rubric):
        """Full attribution: nothing contributes that is not itemised."""
        result = score_resume(RESUME, rubric)
        assert sum(r.points for r in result.requirement_scores) == pytest.approx(result.score)

    def test_synonym_matching(self, rubric):
        result = score_resume(RESUME, rubric)
        postgres = next(r for r in result.requirement_scores if r.requirement.name == "PostgreSQL")
        assert postgres.matched
        assert postgres.evidence[0].pattern == "postgresql"

    def test_identifies_missing_required(self, rubric):
        result = score_resume(RESUME, rubric)
        assert [r.requirement.name for r in result.missing_required] == ["Kubernetes"]

    def test_gaps_ordered_by_cost(self):
        rubric = Rubric(
            [
                Requirement("Big", ("bigthing",), weight=5.0),
                Requirement("Small", ("smallthing",), weight=1.0),
            ]
        )
        assert [r.requirement.name for r in score_resume("nothing", rubric).gaps] == [
            "Big",
            "Small",
        ]


class TestEvidence:
    def test_records_line_number_and_text(self, rubric):
        result = score_resume(RESUME, rubric)
        python = next(r for r in result.requirement_scores if r.requirement.name == "Python")
        evidence = python.evidence[0]
        assert "Python" in evidence.line
        assert RESUME.split("\n")[evidence.line_number - 1] == evidence.line

    def test_every_matched_requirement_has_evidence(self, rubric):
        result = score_resume(RESUME, rubric)
        assert all(r.evidence for r in result.matched)

    def test_case_insensitive(self):
        simple = Rubric([Requirement("Python", ("PYTHON",))])
        assert score_resume("i know python", simple).score == pytest.approx(1.0)

    def test_accent_insensitive(self):
        simple = Rubric([Requirement("Martinez", ("martinez",))])
        assert score_resume("Zoë Martínez", simple).score == pytest.approx(1.0)

    def test_whole_word_matching_avoids_substrings(self):
        """'go' must not match inside 'algorithms' or 'Django'."""
        simple = Rubric([Requirement("Go", ("go",))])
        assert score_resume("Built algorithms with Django", simple).score == 0.0

    def test_matches_go_as_a_word(self):
        simple = Rubric([Requirement("Go", ("go",))])
        assert score_resume("Wrote services in Go.", simple).score == pytest.approx(1.0)

    def test_handles_regex_metacharacters_in_patterns(self):
        """'C++' and '.NET' contain regex metacharacters and must still match."""
        simple = Rubric(
            [Requirement("C++", ("c++",)), Requirement(".NET", (".net",))]
        )
        assert score_resume("Experience with C++ and .NET", simple).score == pytest.approx(1.0)


class TestExplain:
    def test_reports_score(self, rubric):
        assert "0.750" in score_resume(RESUME, rubric).explain()

    def test_lists_matched_with_points_and_line(self, rubric):
        text = score_resume(RESUME, rubric).explain()
        assert "Python" in text
        assert "+0.375" in text  # 3/8

    def test_flags_missing_required_prominently(self, rubric):
        text = score_resume(RESUME, rubric).explain()
        assert "MISSING REQUIRED" in text
        assert "Kubernetes" in text

    def test_shows_what_each_gap_would_add(self, rubric):
        assert "would add" in score_resume(RESUME, rubric).explain()

    def test_handles_zero_matches(self):
        simple = Rubric([Requirement("Rust", ("rust",))])
        assert "(none)" in score_resume("nothing here", simple).explain()


class TestCounterfactualInvariance:
    """The property the transparent design exists to provide.

    A rubric scorer keys only on named job-relevant terms, so swapping a candidate's
    name or pronouns cannot move the score. This wires the real scorer into the real
    perturbation harness rather than asserting it by inspection.
    """

    def test_invariant_to_name_and_pronoun_swaps(self, rubric):
        report = run_perturbation_audit(
            [RESUME], lambda text: score_resume(text, rubric).score
        )
        assert report.is_invariant
        assert report.violations == []

    def test_dimension_spread_is_zero(self, rubric):
        report = run_perturbation_audit(
            [RESUME], lambda text: score_resume(text, rubric).score
        )
        assert all(spread == 0.0 for spread in report.dimension_spread().values())

    def test_harness_would_catch_a_biased_rubric(self):
        """Control: a rubric keying on a name IS caught, so the test above has teeth."""
        biased = Rubric([Requirement("Name", ("todd wilson",))])
        report = run_perturbation_audit(
            [RESUME], lambda text: score_resume(text, biased).score
        )
        assert not report.is_invariant
