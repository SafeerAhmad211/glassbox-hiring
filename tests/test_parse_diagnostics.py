"""Tests for parseability diagnostics."""

from __future__ import annotations

import pytest

from glassbox.parse.diagnostics import Severity, diagnose
from glassbox.parse.layout import TextBlock

from .test_parse_layout import two_column_blocks


def good_resume_blocks() -> list[TextBlock]:
    """A clean, single-column, fully parseable resume."""
    lines = [
        "Jane Doe",
        "jane@example.com | 555-123-4567",
        "EXPERIENCE",
        "Senior Engineer, Acme Corp",
        "2020 - 2024",
        "Built distributed systems.",
        "EDUCATION",
        "BS Computer Science, State University",
        "SKILLS",
        "Python, Postgres, Docker",
    ]
    return [
        TextBlock(text, x=50.0, y=700.0 - i * 20.0, size=11.0, emit_index=i)
        for i, text in enumerate(lines)
    ]


def codes(report) -> set[str]:
    return {f.code for f in report.findings}


class TestCleanDocument:
    def test_clean_resume_has_no_serious_findings(self):
        report = diagnose(good_resume_blocks())
        assert report.is_clean, [f.code for f in report.findings]

    def test_reading_order_agrees_for_single_column(self):
        assert not diagnose(good_resume_blocks()).reading_order_differs

    def test_reports_structure(self):
        report = diagnose(good_resume_blocks())
        assert report.n_columns == 1
        assert report.n_pages == 1
        assert report.n_blocks == 10


class TestMultiColumn:
    def test_flags_multi_column_layout(self):
        assert "multi_column_layout" in codes(diagnose(two_column_blocks()))

    def test_flags_ambiguous_reading_order(self):
        assert "reading_order_ambiguous" in codes(diagnose(two_column_blocks()))

    def test_reading_order_differs(self):
        assert diagnose(two_column_blocks()).reading_order_differs

    def test_multi_column_is_high_severity(self):
        report = diagnose(two_column_blocks())
        finding = next(f for f in report.findings if f.code == "multi_column_layout")
        assert finding.severity is Severity.HIGH

    def test_evidence_names_the_page(self):
        report = diagnose(two_column_blocks())
        finding = next(f for f in report.findings if f.code == "multi_column_layout")
        assert "1" in finding.evidence


class TestContactInHeader:
    def test_flags_email_only_in_header(self):
        body = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0, emit_index=0),
            TextBlock("EXPERIENCE", x=50.0, y=680.0, size=11.0, emit_index=1),
            TextBlock("Acme Corp 2020 - 2024", x=50.0, y=660.0, size=11.0, emit_index=2),
            TextBlock("EDUCATION", x=50.0, y=640.0, size=11.0, emit_index=3),
        ]
        header = [TextBlock("jane@example.com", x=50.0, y=780.0, size=9.0)]
        report = diagnose(body, header_blocks=header)
        assert "contact_in_header" in codes(report)

    def test_contact_in_header_is_critical(self):
        body = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0),
            TextBlock("EXPERIENCE", x=50.0, y=680.0, size=11.0),
            TextBlock("Acme 2020 - 2024", x=50.0, y=660.0, size=11.0),
            TextBlock("EDUCATION", x=50.0, y=640.0, size=11.0),
        ]
        header = [TextBlock("jane@example.com", x=50.0, y=780.0, size=9.0)]
        finding = next(
            f for f in diagnose(body, header_blocks=header).findings
            if f.code == "contact_in_header"
        )
        assert finding.severity is Severity.CRITICAL
        assert "header" in finding.fix.lower() or "body" in finding.fix.lower()

    def test_no_flag_when_contact_also_in_body(self):
        blocks = good_resume_blocks()
        header = [TextBlock("jane@example.com", x=50.0, y=780.0, size=9.0)]
        assert "contact_in_header" not in codes(diagnose(blocks, header_blocks=header))


class TestMissingInformation:
    def test_flags_missing_email(self):
        blocks = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0),
            TextBlock("EXPERIENCE", x=50.0, y=680.0, size=11.0),
            TextBlock("Acme Corp 2020 - 2024", x=50.0, y=660.0, size=11.0),
            TextBlock("EDUCATION", x=50.0, y=640.0, size=11.0),
        ]
        report = diagnose(blocks)
        assert "no_email" in codes(report)
        assert report.critical

    def test_flags_missing_date_ranges(self):
        blocks = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0),
            TextBlock("jane@example.com", x=50.0, y=690.0, size=11.0),
            TextBlock("EXPERIENCE", x=50.0, y=680.0, size=11.0),
            TextBlock("Acme Corp, Senior Engineer", x=50.0, y=660.0, size=11.0),
            TextBlock("EDUCATION", x=50.0, y=640.0, size=11.0),
        ]
        assert "no_date_ranges" in codes(diagnose(blocks))

    @pytest.mark.parametrize(
        "date_text",
        # The en dash case is the point: word processors autocorrect hyphens into
        # en dashes, so a parser matching only "-" misses these silently.
        ["2020 - 2024", "2020-2024", "2021 - Present", "2019 – current"],
    )
    def test_recognises_common_date_formats(self, date_text):
        blocks = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0),
            TextBlock("jane@example.com", x=50.0, y=690.0, size=11.0),
            TextBlock("EXPERIENCE", x=50.0, y=680.0, size=11.0),
            TextBlock(f"Acme Corp {date_text}", x=50.0, y=660.0, size=11.0),
            TextBlock("EDUCATION", x=50.0, y=640.0, size=11.0),
        ]
        assert "no_date_ranges" not in codes(diagnose(blocks))


class TestSectionHeadings:
    def test_flags_no_conventional_sections(self):
        blocks = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0),
            TextBlock("jane@example.com", x=50.0, y=690.0, size=11.0),
            TextBlock("Where I Made an Impact", x=50.0, y=670.0, size=11.0),
            TextBlock("Acme Corp 2020 - 2024", x=50.0, y=650.0, size=11.0),
        ]
        assert "no_recognised_sections" in codes(diagnose(blocks))

    def test_accepts_conventional_headings(self):
        assert "no_recognised_sections" not in codes(diagnose(good_resume_blocks()))

    def test_prose_mentioning_experience_is_not_a_heading(self):
        """The word 'experience' inside a sentence must not count as a section."""
        blocks = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0),
            TextBlock("jane@example.com", x=50.0, y=690.0, size=11.0),
            TextBlock(
                "I have extensive experience building systems since 2020 - 2024.",
                x=50.0, y=670.0, size=11.0,
            ),
        ]
        assert "no_recognised_sections" in codes(diagnose(blocks))


class TestDocumentFeatures:
    def test_flags_tables(self):
        report = diagnose(good_resume_blocks(), has_tables=True)
        assert "table_layout" in codes(report)

    def test_flags_images_as_low_severity(self):
        report = diagnose(good_resume_blocks(), has_images=True)
        finding = next(f for f in report.findings if f.code == "images_present")
        assert finding.severity is Severity.LOW

    def test_images_alone_still_counts_as_clean(self):
        """LOW findings do not make a document unclean."""
        assert diagnose(good_resume_blocks(), has_images=True).is_clean


class TestScannedDocument:
    def test_flags_no_text_layer(self):
        report = diagnose([], is_scanned=True)
        assert "no_text_layer" in codes(report)
        assert report.critical

    def test_short_circuits_other_findings(self):
        """With no text layer, downstream findings are noise."""
        report = diagnose([], is_scanned=True)
        assert len(report.findings) == 1

    def test_empty_document_treated_as_no_text(self):
        assert "no_text_layer" in codes(diagnose([]))


class TestReportOrdering:
    def test_by_severity_puts_critical_first(self):
        blocks = [
            TextBlock("Jane Doe", x=50.0, y=700.0, size=11.0, emit_index=0),
            TextBlock("Skills", x=350.0, y=700.0, size=11.0, emit_index=1),
            TextBlock("Acme", x=50.0, y=680.0, size=11.0, emit_index=2),
            TextBlock("Python", x=350.0, y=680.0, size=11.0, emit_index=3),
        ]
        ordered = diagnose(blocks, has_images=True).by_severity()
        assert ordered[0].severity is Severity.CRITICAL
        assert ordered[-1].severity is Severity.LOW

    def test_every_finding_has_an_actionable_fix(self):
        report = diagnose(two_column_blocks())
        assert all(f.fix for f in report.findings)

    def test_every_finding_has_detail(self):
        report = diagnose(two_column_blocks())
        assert all(len(f.detail) > 40 for f in report.findings)
