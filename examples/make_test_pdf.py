"""Generate small PDFs with text at known positions, for testing and demos.

Writes raw PDF rather than depending on a rendering library: the fixtures need exact
control over glyph position *and* content-stream emission order, which is precisely
what the layout diagnostics analyse. A generator that hid emission order would make
the fixtures unable to exercise the thing under test.

Usage::

    python examples/make_test_pdf.py
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["build_pdf", "single_column_resume", "two_column_resume"]


def build_pdf(items: list[tuple[str, float, float, float]]) -> bytes:
    """Build a one-page PDF placing each string at an absolute position.

    Args:
        items: ``(text, x, y, font_size)`` in content-stream order. That order is
            preserved in the output and is what a geometry-blind extractor replays.

    Returns:
        The PDF file as bytes.
    """
    parts = ["BT", "/F1 11 Tf"]
    for text, x, y, size in items:
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        parts.append(f"/F1 {size:g} Tf")
        parts.append(f"1 0 0 1 {x:g} {y:g} Tm")
        parts.append(f"({escaped}) Tj")
    parts.append("ET")
    stream = "\n".join(parts).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode()

    return bytes(out)


def two_column_resume() -> bytes:
    """A two-column resume emitted row-by-row across both columns.

    This is the failure case: a geometry-blind reader interleaves the columns.
    """
    rows = [
        ("EXPERIENCE", "SKILLS"),
        ("Senior Engineer, Acme Corp", "Python"),
        ("2020 - 2024", "PostgreSQL"),
        ("Built distributed services.", "Docker"),
        ("EDUCATION", "Kubernetes"),
        ("BS Computer Science", "Go"),
    ]
    items = [("Jane Doe", 50.0, 730.0, 16.0), ("jane@example.com", 50.0, 712.0, 10.0)]
    for index, (left, right) in enumerate(rows):
        y = 680.0 - index * 22.0
        items.append((left, 50.0, y, 11.0))
        items.append((right, 350.0, y, 11.0))
    return build_pdf(items)


def single_column_resume() -> bytes:
    """A clean single-column resume that parses correctly everywhere."""
    lines = [
        ("Jane Doe", 16.0),
        ("jane@example.com | 555-123-4567", 10.0),
        ("", 11.0),
        ("EXPERIENCE", 12.0),
        ("Senior Engineer, Acme Corp", 11.0),
        ("2020 - 2024", 11.0),
        ("Built distributed services in Python and Go.", 11.0),
        ("Managed PostgreSQL clusters and Docker deployments.", 11.0),
        ("", 11.0),
        ("EDUCATION", 12.0),
        ("BS Computer Science, State University", 11.0),
        ("", 11.0),
        ("SKILLS", 12.0),
        ("Python, Go, PostgreSQL, Docker", 11.0),
    ]
    items = [
        (text, 50.0, 730.0 - index * 20.0, size)
        for index, (text, size) in enumerate(lines)
        if text
    ]
    return build_pdf(items)


if __name__ == "__main__":
    here = Path(__file__).parent
    (here / "resume_two_column.pdf").write_bytes(two_column_resume())
    (here / "resume_single_column.pdf").write_bytes(single_column_resume())
    print(f"Wrote resume_two_column.pdf and resume_single_column.pdf to {here}")
