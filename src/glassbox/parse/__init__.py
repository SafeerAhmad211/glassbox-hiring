"""Document parsing and parseability diagnostics."""

from .diagnostics import Finding, ParseabilityReport, Severity, diagnose
from .layout import (
    Column,
    TextBlock,
    column_aware_reading_order,
    detect_columns,
    group_into_lines,
    naive_reading_order,
)

__all__ = [
    "Column",
    "Finding",
    "ParseabilityReport",
    "Severity",
    "TextBlock",
    "column_aware_reading_order",
    "detect_columns",
    "diagnose",
    "group_into_lines",
    "naive_reading_order",
]
