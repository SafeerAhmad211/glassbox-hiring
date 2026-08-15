"""Reading-order reconstruction from positioned text.

A PDF does not store paragraphs. It stores instructions to draw glyph runs at
coordinates, in whatever order the producing application emitted them. Recovering
"what a human reads" from that is a geometry problem, and it is where resume parsing
actually fails: a two-column layout whose runs are emitted column-interleaved will
serialise into alternating fragments from both columns unless the reader detects the
columns first.

This module is deliberately independent of any PDF or DOCX library. It consumes
:class:`TextBlock` objects -- x, y, text -- from any source, which makes the layout
logic testable without binary fixtures and reusable across extractors.

Coordinates use the PDF convention: origin at bottom-left, y increasing upward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "Column",
    "TextBlock",
    "column_aware_reading_order",
    "detect_columns",
    "group_into_lines",
    "naive_reading_order",
]


@dataclass(frozen=True)
class TextBlock:
    """A positioned run of text.

    Args:
        text: The literal text.
        x: Left edge, in points from the left of the page.
        y: Baseline, in points from the bottom of the page.
        size: Font size in points, when known.
        page: Zero-based page index.
        emit_index: Position in the producer's emission order. This is what a
            geometry-naive extractor sorts by, so keeping it lets us reproduce
            exactly what such an extractor would see.
    """

    text: str
    x: float
    y: float
    size: float = 0.0
    page: int = 0
    emit_index: int = 0
    width: float | None = None

    def __post_init__(self) -> None:
        """Reject non-finite geometry.

        NaN coordinates do not fail loudly -- they poison comparisons silently. A
        single NaN x makes every ``<`` comparison false, so span merging collapses,
        column detection reports one column, and a two-column resume is declared
        clean. That is the exact failure this module exists to catch, so a malformed
        coordinate must raise rather than quietly produce a passing result.

        Raises:
            ValueError: If any coordinate is NaN or infinite.
        """
        for field_name, value in (("x", self.x), ("y", self.y), ("size", self.size)):
            if not math.isfinite(value):
                raise ValueError(
                    f"TextBlock {field_name} must be finite, got {value!r} "
                    f"(text={self.text[:30]!r})"
                )
        if self.width is not None and not math.isfinite(self.width):
            raise ValueError(f"TextBlock width must be finite, got {self.width!r}")

    @property
    def width_estimate(self) -> float:
        """Rendered width in points.

        Uses the measured ``width`` when the extractor supplied one (pdfminer reports
        real glyph bounding boxes). Otherwise falls back to a rough estimate: average
        glyph advance in common resume faces runs near 0.5 em. The estimate only needs
        to be good enough to tell whether two blocks could overlap horizontally.
        """
        if self.width is not None:
            return self.width
        return len(self.text) * self.size * 0.5 if self.size else len(self.text) * 5.0


@dataclass
class Column:
    """A detected vertical text column."""

    left: float
    right: float
    blocks: list[TextBlock] = field(default_factory=list)

    @property
    def centre(self) -> float:
        return (self.left + self.right) / 2.0


def group_into_lines(
    blocks: list[TextBlock], *, y_tolerance: float = 2.0
) -> list[list[TextBlock]]:
    """Group blocks sharing a baseline into lines, each ordered left to right.

    Args:
        blocks: Blocks to group.
        y_tolerance: Baseline difference in points still treated as the same line.
            Guards against sub-point rounding and superscript drift.

    Returns:
        Lines ordered top to bottom; within each line, blocks ordered left to right.
    """
    if not blocks:
        return []

    lines: list[list[TextBlock]] = []
    for block in sorted(blocks, key=lambda b: (b.page, -b.y, b.x)):
        placed = False
        for line in reversed(lines):
            reference = line[0]
            if reference.page == block.page and abs(reference.y - block.y) <= y_tolerance:
                line.append(block)
                placed = True
                break
        if not placed:
            lines.append([block])

    for line in lines:
        line.sort(key=lambda b: b.x)
    return lines


def detect_columns(
    blocks: list[TextBlock],
    *,
    min_gap: float = 20.0,
    min_column_share: float = 0.15,
) -> list[Column]:
    """Detect vertical columns by finding sustained horizontal gaps.

    Projects every block onto the x axis, then looks for gutters -- x ranges no block
    occupies -- that are wide enough to be a real column separator rather than word
    spacing. A gutter splits the page only if both sides carry enough text to be a
    genuine column, which prevents a single indented bullet from being read as one.

    Args:
        blocks: Blocks from a single page.
        min_gap: Minimum gutter width in points. Below roughly 20pt a gap is more
            likely inter-word or inter-cell spacing than a column boundary.
        min_column_share: Minimum fraction of blocks a region must hold to count as a
            column.

    Returns:
        Columns ordered left to right. A single-column page returns one column.
    """
    if not blocks:
        return []

    spans = sorted((b.x, b.x + b.width_estimate) for b in blocks)

    # Merge overlapping spans into occupied regions; the holes between them are gutters.
    occupied: list[list[float]] = [list(spans[0])]
    for left, right in spans[1:]:
        if left <= occupied[-1][1]:
            occupied[-1][1] = max(occupied[-1][1], right)
        else:
            occupied.append([left, right])

    if len(occupied) == 1:
        region = occupied[0]
        return [Column(region[0], region[1], list(blocks))]

    # Build candidate boundaries at gutters wide enough to matter.
    boundaries = [
        (occupied[i][1] + occupied[i + 1][0]) / 2.0
        for i in range(len(occupied) - 1)
        if occupied[i + 1][0] - occupied[i][1] >= min_gap
    ]

    if not boundaries:
        return [Column(occupied[0][0], occupied[-1][1], list(blocks))]

    edges = [occupied[0][0], *boundaries, occupied[-1][1]]
    candidates = [
        Column(
            edges[i],
            edges[i + 1],
            [b for b in blocks if edges[i] <= b.x < edges[i + 1]],
        )
        for i in range(len(edges) - 1)
    ]
    # The rightmost column is half-open above; recapture blocks on the final edge.
    candidates[-1].blocks = [b for b in blocks if b.x >= edges[-2]]

    threshold = len(blocks) * min_column_share
    real = [c for c in candidates if len(c.blocks) >= threshold]

    if len(real) < 2:
        return [Column(occupied[0][0], occupied[-1][1], list(blocks))]
    return real


def naive_reading_order(blocks: list[TextBlock]) -> str:
    """Serialise in the producer's emission order -- what a geometry-blind reader sees.

    This is not a strawman. It is the behaviour that produces the classic interleaved
    two-column resume, and reproducing it faithfully is what lets
    :mod:`glassbox.parse.diagnostics` show a candidate the difference between what
    they designed and what a screener receives.

    Args:
        blocks: Blocks to serialise.

    Returns:
        Text in emission order, one block per line.
    """
    return "\n".join(b.text for b in sorted(blocks, key=lambda b: (b.page, b.emit_index)))


def column_aware_reading_order(
    blocks: list[TextBlock],
    *,
    min_gap: float = 20.0,
    y_tolerance: float = 2.0,
) -> str:
    """Serialise in human reading order: each column top-to-bottom, left to right.

    Args:
        blocks: Blocks to serialise. May span multiple pages.
        min_gap: Passed to :func:`detect_columns`.
        y_tolerance: Passed to :func:`group_into_lines`.

    Returns:
        Text in reading order.
    """
    if not blocks:
        return ""

    output: list[str] = []
    for page in sorted({b.page for b in blocks}):
        page_blocks = [b for b in blocks if b.page == page]
        for column in detect_columns(page_blocks, min_gap=min_gap):
            for line in group_into_lines(column.blocks, y_tolerance=y_tolerance):
                output.append(" ".join(b.text for b in line))

    return "\n".join(output)
