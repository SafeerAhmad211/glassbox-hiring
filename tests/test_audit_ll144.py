"""Tests for LL144 bias-audit report generation."""

from __future__ import annotations

from datetime import date

import pytest

from glassbox.audit.ll144 import build_bias_audit, render_markdown

BASE = {
    "tool_name": "ScreenBot",
    "tool_version": "2.1.0",
    "auditor": "Independent Audit Co.",
    "data_source": "Historical applicant data, 2025 hiring cycle",
    "data_explanation": "All applicants scored by the tool during 2025.",
}


class TestBuildBiasAudit:
    def test_builds_all_three_categories(self):
        audit = build_bias_audit(
            **BASE,
            sex_outcomes={"Male": (500, 1000), "Female": (450, 1000)},
            race_outcomes={"White": (400, 800), "Black or African American": (150, 400)},
            intersectional_outcomes={
                "Male / White": (250, 400),
                "Female / White": (150, 400),
            },
        )
        assert audit.sex is not None
        assert audit.race is not None
        assert audit.intersectional is not None
        assert len(audit.reports) == 3

    def test_defaults_audit_date_to_today(self):
        audit = build_bias_audit(**BASE, sex_outcomes={"Male": (5, 10), "Female": (5, 10)})
        assert audit.audit_date == date.today()

    def test_requires_some_data(self):
        with pytest.raises(ValueError, match="at least one of"):
            build_bias_audit(**BASE)

    def test_two_percent_exclusion_applied_by_default(self):
        audit = build_bias_audit(
            **BASE,
            race_outcomes={
                "White": (400, 800),
                "Black or African American": (150, 400),
                "Native American or Alaska Native": (1, 5),
            },
        )
        assert any(
            name == "Native American or Alaska Native" for name, _ in audit.race.excluded
        )

    def test_exclusion_can_be_disabled(self):
        audit = build_bias_audit(
            **BASE,
            race_outcomes={
                "White": (400, 800),
                "Black or African American": (150, 400),
                "Native American or Alaska Native": (1, 5),
            },
            apply_two_percent_exclusion=False,
        )
        assert "Native American or Alaska Native" in [g.name for g in audit.race.groups]


class TestIntersectionalDetection:
    """The case LL144's intersectional requirement exists to catch."""

    @pytest.fixture
    def audit(self):
        # Marginals are balanced: each sex ~50%, each race ~50%.
        # But Female/Black is selected at 20% while Male/White is at 80%.
        return build_bias_audit(
            **BASE,
            sex_outcomes={"Male": (500, 1000), "Female": (500, 1000)},
            race_outcomes={
                "White": (500, 1000),
                "Black or African American": (500, 1000),
            },
            intersectional_outcomes={
                "Male / White": (400, 500),
                "Male / Black or African American": (100, 500),
                "Female / White": (400, 500),
                "Female / Black or African American": (100, 500),
            },
        )

    def test_marginals_pass(self, audit):
        assert audit.sex.passes_four_fifths
        assert audit.race.passes_four_fifths

    def test_intersection_fails(self, audit):
        assert not audit.intersectional.passes_four_fifths
        assert audit.intersectional.min_impact_ratio == pytest.approx(0.25)

    def test_overall_audit_reflects_intersectional_failure(self, audit):
        assert not audit.all_pass
        assert audit.failing_categories == ["sex x race/ethnicity"]


class TestRenderMarkdown:
    @pytest.fixture
    def markdown(self):
        audit = build_bias_audit(
            **BASE,
            sex_outcomes={"Male": (500, 1000), "Female": (300, 1000)},
            unknown_count=42,
            selection_threshold="score >= 70th percentile",
            audit_date=date(2026, 3, 15),
            distribution_date=date(2025, 1, 10),
        )
        return render_markdown(audit)

    def test_includes_required_ll144_fields(self, markdown):
        for required in [
            "2026-03-15",           # date of most recent bias audit
            "2025-01-10",           # distribution date
            "Independent Audit Co.",  # auditor
            "42",                    # unknown category count
            "Historical applicant data",  # data source
            "score >= 70th percentile",   # selection criterion
        ]:
            assert required in markdown

    def test_reports_impact_ratio(self, markdown):
        assert "0.600" in markdown

    def test_flags_failure_prominently(self, markdown):
        assert "⚠️" in markdown
        assert "**YES**" in markdown

    def test_states_that_passing_is_not_clearance(self, markdown):
        assert "does **not** establish" in markdown

    def test_warns_about_threshold_dependence(self, markdown):
        assert "depend on the selection threshold" in markdown

    def test_disclaims_independence_and_legal_advice(self, markdown):
        assert "does not make an audit independent" in markdown
        assert "not legal advice" in markdown

    def test_passing_audit_says_so(self):
        audit = build_bias_audit(
            **BASE, sex_outcomes={"Male": (500, 1000), "Female": (480, 1000)}
        )
        markdown = render_markdown(audit)
        assert "All computed impact ratios are at or above 0.80" in markdown
        assert "⚠️" not in markdown

    def test_lists_excluded_categories_rather_than_hiding_them(self):
        audit = build_bias_audit(
            **BASE,
            race_outcomes={
                "White": (400, 800),
                "Black or African American": (150, 400),
                "Two or More Races": (1, 5),
            },
        )
        markdown = render_markdown(audit)
        assert "Excluded from impact-ratio calculations" in markdown
        assert "Two or More Races" in markdown

    def test_renders_all_categories(self):
        audit = build_bias_audit(
            **BASE,
            sex_outcomes={"Male": (5, 10), "Female": (4, 10)},
            race_outcomes={"White": (5, 10), "Asian": (4, 10)},
            intersectional_outcomes={"Male / White": (5, 10), "Female / Asian": (4, 10)},
        )
        markdown = render_markdown(audit)
        assert "### Sex" in markdown
        assert "### Race/Ethnicity" in markdown
        assert "### Sex X Race/Ethnicity" in markdown
