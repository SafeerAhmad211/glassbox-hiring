"""Tests for reading-order reconstruction.

The two-column fixture is the central case: it encodes a resume whose PDF emits text
column-interleaved, which is exactly how the classic scrambled-resume failure occurs.
"""

from __future__ import annotations

from glassbox.parse.layout import (
    TextBlock,
    column_aware_reading_order,
    detect_columns,
    group_into_lines,
    naive_reading_order,
)


def two_column_blocks() -> list[TextBlock]:
    """A two-column resume whose producer emitted rows across both columns.

    Left column at x=50 (EXPERIENCE), right column at x=350 (SKILLS). The emit order
    alternates, which is what a geometry-blind reader will replay.
    """
    rows = [
        ("EXPERIENCE", "SKILLS"),
        ("Acme Corp", "Python"),
        ("2020-2024", "Postgres"),
        ("Built the thing", "Docker"),
    ]
    blocks = []
    emit = 0
    for row, (left, right) in enumerate(rows):
        y = 700.0 - row * 20.0
        blocks.append(TextBlock(left, x=50.0, y=y, size=11.0, emit_index=emit))
        emit += 1
        blocks.append(TextBlock(right, x=350.0, y=y, size=11.0, emit_index=emit))
        emit += 1
    return blocks


def single_column_blocks() -> list[TextBlock]:
    lines = ["Jane Doe", "jane@example.com", "EXPERIENCE", "Acme Corp", "2020-2024"]
    return [
        TextBlock(text, x=50.0, y=700.0 - i * 20.0, size=11.0, emit_index=i)
        for i, text in enumerate(lines)
    ]


class TestGroupIntoLines:
    def test_groups_by_baseline(self):
        lines = group_into_lines(two_column_blocks())
        assert len(lines) == 4
        assert [b.text for b in lines[0]] == ["EXPERIENCE", "SKILLS"]

    def test_orders_left_to_right_within_line(self):
        blocks = [
            TextBlock("right", x=300.0, y=700.0, emit_index=0),
            TextBlock("left", x=50.0, y=700.0, emit_index=1),
        ]
        assert [b.text for b in group_into_lines(blocks)[0]] == ["left", "right"]

    def test_orders_top_to_bottom(self):
        lines = group_into_lines(single_column_blocks())
        assert next(line[0].text for line in lines) == "Jane Doe"

    def test_tolerates_subpoint_baseline_drift(self):
        blocks = [
            TextBlock("a", x=50.0, y=700.0),
            TextBlock("b", x=100.0, y=701.5),  # within default 2.0pt tolerance
        ]
        assert len(group_into_lines(blocks)) == 1

    def test_separates_beyond_tolerance(self):
        blocks = [
            TextBlock("a", x=50.0, y=700.0),
            TextBlock("b", x=100.0, y=690.0),
        ]
        assert len(group_into_lines(blocks)) == 2

    def test_does_not_merge_across_pages(self):
        blocks = [
            TextBlock("p1", x=50.0, y=700.0, page=0),
            TextBlock("p2", x=50.0, y=700.0, page=1),
        ]
        assert len(group_into_lines(blocks)) == 2

    def test_empty_input(self):
        assert group_into_lines([]) == []


class TestDetectColumns:
    def test_detects_two_columns(self):
        columns = detect_columns(two_column_blocks())
        assert len(columns) == 2
        assert columns[0].centre < columns[1].centre

    def test_assigns_blocks_to_correct_column(self):
        left, right = detect_columns(two_column_blocks())
        assert "EXPERIENCE" in [b.text for b in left.blocks]
        assert "SKILLS" in [b.text for b in right.blocks]

    def test_single_column_returns_one(self):
        assert len(detect_columns(single_column_blocks())) == 1

    def test_narrow_gap_is_not_a_column(self):
        """Word spacing must not be read as a column boundary."""
        blocks = [
            TextBlock("word", x=50.0, y=700.0, size=11.0),
            TextBlock("next", x=85.0, y=700.0, size=11.0),
        ]
        assert len(detect_columns(blocks, min_gap=20.0)) == 1

    def test_sparse_region_is_not_a_column(self):
        """A single indented block far right is not a column."""
        blocks = [
            TextBlock(f"line {i}", x=50.0, y=700.0 - i * 15.0, size=11.0)
            for i in range(20)
        ]
        blocks.append(TextBlock("*", x=500.0, y=700.0, size=11.0))
        assert len(detect_columns(blocks)) == 1

    def test_empty_input(self):
        assert detect_columns([]) == []


class TestNaiveReadingOrder:
    def test_reproduces_the_interleaving_failure(self):
        """The classic scrambled resume, reproduced exactly."""
        text = naive_reading_order(two_column_blocks())
        assert text.split("\n") == [
            "EXPERIENCE", "SKILLS",
            "Acme Corp", "Python",
            "2020-2024", "Postgres",
            "Built the thing", "Docker",
        ]

    def test_single_column_is_already_correct(self):
        text = naive_reading_order(single_column_blocks())
        assert text.startswith("Jane Doe\njane@example.com")


class TestColumnAwareReadingOrder:
    def test_recovers_column_order(self):
        """Left column fully, then right column -- as a human reads it."""
        lines = column_aware_reading_order(two_column_blocks()).split("\n")
        assert lines == [
            "EXPERIENCE", "Acme Corp", "2020-2024", "Built the thing",
            "SKILLS", "Python", "Postgres", "Docker",
        ]

    def test_keeps_experience_contiguous(self):
        """The point of the exercise: the employer stays with its dates."""
        text = column_aware_reading_order(two_column_blocks())
        experience_section = text.split("SKILLS")[0]
        assert "Acme Corp" in experience_section
        assert "2020-2024" in experience_section
        assert "Python" not in experience_section

    def test_matches_naive_for_single_column(self):
        blocks = single_column_blocks()
        assert column_aware_reading_order(blocks) == naive_reading_order(blocks)

    def test_handles_multiple_pages_in_order(self):
        blocks = [
            TextBlock("page one", x=50.0, y=700.0, page=0, emit_index=0),
            TextBlock("page two", x=50.0, y=700.0, page=1, emit_index=1),
        ]
        assert column_aware_reading_order(blocks) == "page one\npage two"

    def test_empty_input(self):
        assert column_aware_reading_order([]) == ""
