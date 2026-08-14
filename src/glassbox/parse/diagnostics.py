"""Parseability diagnostics: what a screener loses from a document.

Every finding here is deterministic geometry or text analysis. There is no model, no
scoring heuristic, and nothing probabilistic -- which means a candidate can be told
exactly *why* something will be lost and can verify the claim themselves.

This is the honest core of a candidate-facing tool. Most published "ATS score"
products invent a number; the checkable fact is narrower and far more useful: your
contact block is in a PDF header and a large share of parsers never read those.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .layout import (
    TextBlock,
    column_aware_reading_order,
    detect_columns,
    naive_reading_order,
)

__all__ = [
    "Finding",
    "ParseabilityReport",
    "Severity",
    "diagnose",
]


class Severity(str, Enum):
    """How much a finding is likely to cost the candidate."""

    CRITICAL = "critical"
    """Information is likely lost entirely -- e.g. contact details a parser never reads."""

    HIGH = "high"
    """Content is likely reordered or corrupted -- e.g. interleaved columns."""

    MEDIUM = "medium"
    """Content is readable but may be mis-attributed -- e.g. unrecognised section names."""

    LOW = "low"
    """Cosmetic or stylistic; unlikely to change an outcome on its own."""


@dataclass(frozen=True)
class Finding:
    """One parseability issue.

    Attributes:
        code: Stable machine-readable identifier.
        severity: How costly the issue is likely to be.
        summary: One-line statement of the problem.
        detail: Why it happens, in terms a non-engineer can act on.
        evidence: Concrete excerpt or measurement supporting the finding.
        fix: The specific change that resolves it.
    """

    code: str
    severity: Severity
    summary: str
    detail: str
    evidence: str = ""
    fix: str = ""


@dataclass
class ParseabilityReport:
    """Findings for one document."""

    findings: list[Finding] = field(default_factory=list)
    naive_text: str = ""
    reading_order_text: str = ""
    n_blocks: int = 0
    n_columns: int = 1
    n_pages: int = 1

    @property
    def critical(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.CRITICAL]

    @property
    def is_clean(self) -> bool:
        """True when nothing above LOW severity was found."""
        return not any(f.severity is not Severity.LOW for f in self.findings)

    @property
    def reading_order_differs(self) -> bool:
        """Whether geometry-aware and geometry-naive extraction disagree.

        When these differ, candidates are not being read as written -- and which
        version a given screener sees depends on a parser implementation detail the
        candidate cannot observe.
        """
        return _normalise(self.naive_text) != _normalise(self.reading_order_text)

    def by_severity(self) -> list[Finding]:
        """Findings ordered most severe first."""
        rank = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        return sorted(self.findings, key=lambda f: rank[f.severity])


def _normalise(text: str) -> str:
    """Collapse whitespace so ordering differences are not masked by spacing."""
    return re.sub(r"\s+", " ", text).strip()


#: Section headings a parser is likely to recognise. Screeners key on a small
#: vocabulary; a heading outside it may not be recognised as a section boundary.
CONVENTIONAL_SECTIONS = {
    "experience", "work experience", "professional experience", "employment",
    "employment history", "work history", "education", "skills", "technical skills",
    "core competencies", "projects", "certifications", "licenses", "publications",
    "awards", "summary", "professional summary", "objective", "profile",
    "volunteer experience", "languages", "interests", "references",
}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_DATE_RANGE = re.compile(
    # The en dash and em dash here are intentional: word processors autocorrect
    # "2020-2024" into "2020–2024", so a hyphen-only pattern misses a large share of
    # real resumes and reports their experience as zero.
    r"\b(19|20)\d{2}\s*[-–—]\s*((19|20)\d{2}|present|current)\b",
    re.IGNORECASE,
)


def diagnose(
    blocks: list[TextBlock],
    *,
    header_blocks: list[TextBlock] | None = None,
    footer_blocks: list[TextBlock] | None = None,
    has_images: bool = False,
    has_tables: bool = False,
    is_scanned: bool = False,
    naive_text: str | None = None,
) -> ParseabilityReport:
    """Analyse a document's parseability.

    Args:
        blocks: Body text blocks with positions.
        header_blocks: Blocks in the page header region, if the extractor can
            distinguish them. Content here is frequently not extracted at all.
        footer_blocks: Blocks in the page footer region.
        has_images: Whether the document contains images.
        has_tables: Whether the document contains table structures.
        is_scanned: Whether the document appears to be a scan with no text layer.
        naive_text: Output of a real geometry-blind extractor, when available.
            :func:`glassbox.parse.pdf.extract_pdf_blocks` supplies pypdf's
            ``extract_text()`` here. Passing it makes the reading-order finding a
            comparison between two independent real extractors rather than between
            two of our own functions, which is far stronger evidence.

    Returns:
        A :class:`ParseabilityReport`.
    """
    findings: list[Finding] = []
    header_blocks = header_blocks or []
    footer_blocks = footer_blocks or []

    naive = naive_text if naive_text is not None else naive_reading_order(blocks)
    ordered = column_aware_reading_order(blocks)
    body_text = ordered or naive

    pages = sorted({b.page for b in blocks}) or [0]
    columns_per_page = {
        page: len(detect_columns([b for b in blocks if b.page == page]))
        for page in pages
    }
    max_columns = max(columns_per_page.values(), default=1)

    # --- Scanned document: nothing else matters if there is no text layer ---
    if is_scanned or (not blocks and not header_blocks):
        findings.append(
            Finding(
                code="no_text_layer",
                severity=Severity.CRITICAL,
                summary="Document has no extractable text layer",
                detail=(
                    "The file appears to be an image or scan. Screeners extract text, "
                    "not pixels; without OCR this document yields nothing at all, and "
                    "many pipelines do not run OCR."
                ),
                evidence=f"{len(blocks)} text blocks extracted",
                fix="Export a text-based PDF from the original document rather than scanning or exporting as an image.",
            )
        )
        return ParseabilityReport(
            findings=findings,
            naive_text=naive,
            reading_order_text=ordered,
            n_blocks=len(blocks),
            n_columns=max_columns,
            n_pages=len(pages),
        )

    # --- Contact information stranded in header/footer ---
    header_footer_text = " ".join(b.text for b in header_blocks + footer_blocks)
    if header_footer_text:
        found_email = _EMAIL.search(header_footer_text)
        found_phone = _PHONE.search(header_footer_text)
        body_has_email = bool(_EMAIL.search(body_text))
        body_has_phone = bool(_PHONE.search(body_text))

        if (found_email and not body_has_email) or (found_phone and not body_has_phone):
            missing = []
            if found_email and not body_has_email:
                missing.append("email address")
            if found_phone and not body_has_phone:
                missing.append("phone number")
            findings.append(
                Finding(
                    code="contact_in_header",
                    severity=Severity.CRITICAL,
                    summary=f"Contact details ({', '.join(missing)}) are in the page header/footer",
                    detail=(
                        "Many parsers never read PDF header and footer regions. If your "
                        "only contact information is there, a recruiter who wants to "
                        "reach you may have no way to do so -- and this fails silently, "
                        "with no error shown to anyone."
                    ),
                    evidence=header_footer_text[:120],
                    fix="Move your name, email, and phone into the main body of the first page.",
                )
            )

    # --- Multi-column layout ---
    if max_columns > 1:
        multi_column_pages = [p for p, n in columns_per_page.items() if n > 1]
        findings.append(
            Finding(
                code="multi_column_layout",
                severity=Severity.HIGH,
                summary=f"Multi-column layout detected ({max_columns} columns)",
                detail=(
                    "A parser that does not reconstruct columns reads straight across "
                    "the page, interleaving text from both columns into alternating "
                    "fragments. Job titles separate from employers, and skills land "
                    "inside dates. Behaviour is vendor-specific and you cannot tell "
                    "which parser will receive your file."
                ),
                evidence=f"page(s) {', '.join(str(p + 1) for p in multi_column_pages)}",
                fix="Use a single-column layout.",
            )
        )

    # --- Reading order actually changes ---
    if _normalise(naive) != _normalise(ordered):
        findings.append(
            Finding(
                code="reading_order_ambiguous",
                severity=Severity.HIGH,
                summary="Text extracts in a different order depending on the parser",
                detail=(
                    "Geometry-aware and geometry-naive extraction produce different "
                    "text from this file. Which one a given screener uses is an "
                    "implementation detail you cannot observe, so your resume may be "
                    "read correctly by one employer and scrambled by another."
                ),
                evidence=f"naive: {_normalise(naive)[:80]!r} vs ordered: {_normalise(ordered)[:80]!r}",
                fix="Simplify the layout until both orders agree -- single column, no side-by-side blocks.",
            )
        )

    # --- Tables ---
    if has_tables:
        findings.append(
            Finding(
                code="table_layout",
                severity=Severity.HIGH,
                summary="Document uses tables",
                detail=(
                    "Table handling is the least consistent part of resume parsing. "
                    "Reported behaviour differs by vendor: some merge all cells in a "
                    "row into one string, others emit cells in unpredictable order."
                ),
                fix="Replace tables with plain paragraphs and simple bullet lists.",
            )
        )

    # --- Section headings ---
    recognised = _find_recognised_sections(body_text)
    if not recognised:
        findings.append(
            Finding(
                code="no_recognised_sections",
                severity=Severity.MEDIUM,
                summary="No conventional section headings found",
                detail=(
                    "Parsers segment a resume by matching headings against a small "
                    "known vocabulary. Creative headings ('Where I've Made an Impact') "
                    "may not register as boundaries, so the content beneath them may "
                    "not be attributed to experience or education at all."
                ),
                fix="Include standard headings: Experience, Education, Skills.",
            )
        )
    elif len(recognised) < 2:
        findings.append(
            Finding(
                code="few_recognised_sections",
                severity=Severity.MEDIUM,
                summary=f"Only one conventional section heading found: {recognised[0]!r}",
                detail=(
                    "With only one recognisable boundary, a parser may fold most of "
                    "the document into a single undifferentiated block."
                ),
                fix="Use standard headings for each major section.",
            )
        )

    # --- Contact information missing entirely ---
    all_text = f"{body_text} {header_footer_text}"
    if not _EMAIL.search(all_text):
        findings.append(
            Finding(
                code="no_email",
                severity=Severity.CRITICAL,
                summary="No email address found anywhere in the document",
                detail=(
                    "Most systems key candidate records on email. Without one, a record "
                    "may fail to create at all, or duplicate on every application."
                ),
                fix="Add a plain-text email address in the body of the first page.",
            )
        )

    # --- Dates ---
    if not _DATE_RANGE.search(body_text):
        findings.append(
            Finding(
                code="no_date_ranges",
                severity=Severity.MEDIUM,
                summary="No recognisable employment date ranges found",
                detail=(
                    "Tenure and recency are computed from date ranges like "
                    "'2020 - 2024' or '2021 - Present'. Without a recognisable format, "
                    "experience may be computed as zero."
                ),
                fix="Write date ranges as '2020 - 2024' or 'Jan 2020 - Present'.",
            )
        )

    # --- Images ---
    if has_images:
        findings.append(
            Finding(
                code="images_present",
                severity=Severity.LOW,
                summary="Document contains images",
                detail=(
                    "Images are not read. Harmless if decorative, but any text that "
                    "exists only inside an image -- a skills chart, a logo with your "
                    "name -- is invisible to the screener."
                ),
                fix="Ensure no substantive information appears only inside an image.",
            )
        )

    return ParseabilityReport(
        findings=findings,
        naive_text=naive,
        reading_order_text=ordered,
        n_blocks=len(blocks),
        n_columns=max_columns,
        n_pages=len(pages),
    )


def _find_recognised_sections(text: str) -> list[str]:
    """Return conventional section headings appearing as their own line."""
    found = []
    for raw_line in text.split("\n"):
        cleaned = raw_line.strip().strip(":").lower()
        # A heading is short and stands alone; this avoids matching the word
        # "experience" inside a sentence of prose.
        if cleaned in CONVENTIONAL_SECTIONS and len(raw_line.strip()) <= 40:
            found.append(raw_line.strip())
    return found
