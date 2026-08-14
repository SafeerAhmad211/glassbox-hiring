"""Integration tests for PDF extraction.

These are the tests that catch extractor-level regressions. The library previously used
pypdf's text visitor, which does not reliably report the horizontal component of the
text matrix -- every block came back at the same x, so column detection silently
reported every two-column resume as clean. That failure was invisible to unit tests of
the layout logic, because the layout logic was correct; only an end-to-end test against
a real PDF with known geometry exposes it.

``test_columns_have_distinct_x`` is the direct regression guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from make_test_pdf import single_column_resume, two_column_resume

from glassbox.parse.diagnostics import diagnose
from glassbox.parse.layout import (
    column_aware_reading_order,
    detect_columns,
)
from glassbox.parse.pdf import extract_blocks, extract_pdf_blocks

pytest.importorskip("pdfminer", reason="needs the [parse] extra")


@pytest.fixture(scope="module")
def two_column_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdfs") / "two_column.pdf"
    path.write_bytes(two_column_resume())
    return path


@pytest.fixture(scope="module")
def single_column_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdfs") / "single_column.pdf"
    path.write_bytes(single_column_resume())
    return path


class TestExtraction:
    def test_extracts_blocks(self, two_column_pdf):
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        assert len(blocks) >= 12

    def test_recovers_text_content(self, two_column_pdf):
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        texts = {b.text for b in blocks}
        assert "EXPERIENCE" in texts
        assert "SKILLS" in texts

    def test_columns_have_distinct_x(self, two_column_pdf):
        """Regression guard for the pypdf text-matrix bug.

        The left column is placed at x=50 and the right at x=350. An extractor that
        loses horizontal position reports both at 50, and every downstream column
        diagnostic silently passes.
        """
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        x_positions = {round(b.x) for b in blocks}
        assert 50 in x_positions
        assert 350 in x_positions

    def test_reports_measured_width(self, two_column_pdf):
        """pdfminer supplies real glyph bounding boxes, not a character-count guess."""
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        assert all(b.width is not None and b.width > 0 for b in blocks)

    def test_font_sizes_recovered(self, two_column_pdf):
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        name = next(b for b in blocks if b.text == "Jane Doe")
        assert name.size == pytest.approx(16.0, abs=0.5)

    def test_flags_include_naive_text(self, two_column_pdf):
        _, flags = extract_pdf_blocks(two_column_pdf)
        assert flags["naive_text"] is not None
        assert "EXPERIENCE" in flags["naive_text"]

    def test_page_count(self, two_column_pdf):
        _, flags = extract_pdf_blocks(two_column_pdf)
        assert flags["n_pages"] == 1

    def test_dispatch_by_extension(self, two_column_pdf):
        blocks, _ = extract_blocks(two_column_pdf)
        assert blocks

    def test_rejects_unsupported_extension(self, tmp_path):
        bad = tmp_path / "resume.txt"
        bad.write_text("hello", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_blocks(bad)


class TestEndToEndDiagnosis:
    def test_two_column_pdf_is_flagged(self, two_column_pdf):
        blocks, flags = extract_pdf_blocks(two_column_pdf)
        report = diagnose(blocks, naive_text=flags["naive_text"], **_doc_flags(flags))
        codes = {f.code for f in report.findings}
        assert "multi_column_layout" in codes

    def test_two_column_pdf_detects_two_columns(self, two_column_pdf):
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        assert len(detect_columns(blocks)) == 2

    def test_reading_order_recovers_column_contiguity(self, two_column_pdf):
        """The employer must stay with its dates, not with the skills list."""
        blocks, _ = extract_pdf_blocks(two_column_pdf)
        text = column_aware_reading_order(blocks)
        before_skills = text.split("SKILLS")[0]
        assert "Senior Engineer, Acme Corp" in before_skills
        assert "2020 - 2024" in before_skills
        assert "Python" not in before_skills

    def test_single_column_pdf_is_clean(self, single_column_pdf):
        blocks, flags = extract_pdf_blocks(single_column_pdf)
        report = diagnose(blocks, naive_text=flags["naive_text"], **_doc_flags(flags))
        assert report.is_clean, [f.code for f in report.findings]

    def test_single_column_finds_email_and_dates(self, single_column_pdf):
        blocks, _ = extract_pdf_blocks(single_column_pdf)
        text = column_aware_reading_order(blocks)
        assert "jane@example.com" in text
        assert "2020 - 2024" in text

    def test_single_column_detects_one_column(self, single_column_pdf):
        blocks, _ = extract_pdf_blocks(single_column_pdf)
        assert len(detect_columns(blocks)) == 1


def _doc_flags(flags: dict) -> dict:
    """Pass only the document-feature flags diagnose() accepts."""
    return {
        "has_images": flags.get("has_images", False),
        "has_tables": flags.get("has_tables", False),
    }
