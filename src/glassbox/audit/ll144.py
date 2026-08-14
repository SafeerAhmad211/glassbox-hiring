"""NYC Local Law 144 bias-audit report generation.

Local Law 144 of 2021 requires an employer using an Automated Employment Decision Tool
on NYC candidates to commission an **independent** annual bias audit and publish a
summary of results. This module produces that summary.

What the published audit must contain, per the DCWP rules (6 RCNY 5-301 et seq.):

- the date of the most recent bias audit,
- the source and explanation of the data used,
- the number of individuals assessed who fall into an *unknown* demographic category,
- selection rates **and** impact ratios for sex categories, for race/ethnicity
  categories, and for **intersectional** sex x race/ethnicity categories,
- the distribution date of the tool.

The intersectional breakdown is the requirement most often missed. It is also where
disparity most often appears: a tool can clear four-fifths on sex alone and on
race/ethnicity alone while failing badly for a specific intersection.

.. warning::
   Running this module does not make an audit independent. LL144 requires an auditor
   who is not involved in using, developing, or distributing the tool, and who has no
   financial interest in the employer or vendor. This is a calculation and reporting
   instrument for that auditor -- it is not a substitute for one, and it is not legal
   advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .impact import (
    FOUR_FIFTHS,
    LL144_MIN_SHARE,
    GroupOutcome,
    ImpactReport,
    adverse_impact,
)

__all__ = [
    "EEOC_RACE_CATEGORIES",
    "EEOC_SEX_CATEGORIES",
    "BiasAudit",
    "build_bias_audit",
    "render_markdown",
]

#: EEOC sex categories used for adverse-impact testing.
EEOC_SEX_CATEGORIES = ("Male", "Female")

#: EEOC race/ethnicity categories (EEO-1 component 1 taxonomy).
EEOC_RACE_CATEGORIES = (
    "Hispanic or Latino",
    "White",
    "Black or African American",
    "Native Hawaiian or Pacific Islander",
    "Asian",
    "Native American or Alaska Native",
    "Two or More Races",
)


@dataclass
class BiasAudit:
    """A complete LL144 bias audit.

    Attributes:
        tool_name: Name of the AEDT audited.
        tool_version: Version or model identifier.
        audit_date: Date the audit was performed.
        distribution_date: Date the tool was distributed/put into use.
        data_source: Where the data came from, and whether historical or test data.
        data_explanation: Narrative explanation of the dataset.
        auditor: Name of the independent auditor.
        sex: Impact report across sex categories.
        race: Impact report across race/ethnicity categories.
        intersectional: Impact report across sex x race/ethnicity categories.
        unknown_count: Individuals assessed whose demographic category is unknown.
        selection_threshold: Description of what counts as "selected".
        notes: Additional auditor notes.
    """

    tool_name: str
    tool_version: str
    audit_date: date
    distribution_date: date | None
    data_source: str
    data_explanation: str
    auditor: str
    sex: ImpactReport | None = None
    race: ImpactReport | None = None
    intersectional: ImpactReport | None = None
    unknown_count: int = 0
    selection_threshold: str = "not specified"
    notes: list[str] = field(default_factory=list)

    @property
    def reports(self) -> list[ImpactReport]:
        """All populated category reports."""
        return [r for r in (self.sex, self.race, self.intersectional) if r is not None]

    @property
    def all_pass(self) -> bool:
        """Whether every category clears four-fifths.

        Not a compliance verdict. LL144 requires *publication* of results, not a
        passing result -- an employer may lawfully publish an audit showing disparity.
        Clearing four-fifths also does not establish validity under 29 CFR 1607.
        """
        return all(r.passes_four_fifths for r in self.reports)

    @property
    def failing_categories(self) -> list[str]:
        """Categories containing at least one group below four-fifths."""
        return [r.category for r in self.reports if not r.passes_four_fifths]


def build_bias_audit(
    *,
    tool_name: str,
    tool_version: str,
    auditor: str,
    data_source: str,
    data_explanation: str,
    sex_outcomes: dict[str, tuple[int, int]] | None = None,
    race_outcomes: dict[str, tuple[int, int]] | None = None,
    intersectional_outcomes: dict[str, tuple[int, int]] | None = None,
    unknown_count: int = 0,
    audit_date: date | None = None,
    distribution_date: date | None = None,
    selection_threshold: str = "not specified",
    apply_two_percent_exclusion: bool = True,
) -> BiasAudit:
    """Assemble a bias audit from selection counts.

    Args:
        tool_name: Name of the AEDT.
        tool_version: Version or model identifier.
        auditor: Independent auditor's name.
        data_source: Provenance of the data, and whether historical or test data.
        data_explanation: Narrative explanation of the dataset.
        sex_outcomes: ``{category: (selected, total)}`` across sex categories.
        race_outcomes: ``{category: (selected, total)}`` across race/ethnicity.
        intersectional_outcomes: ``{"Female / Asian": (selected, total), ...}``.
        unknown_count: Individuals assessed whose category is unknown.
        audit_date: Defaults to today.
        distribution_date: Date the tool was put into use.
        selection_threshold: Description of the selection criterion, e.g.
            ``"score >= 70th percentile"``. Recorded because an impact ratio is
            meaningless without it.
        apply_two_percent_exclusion: Apply the LL144 <2% category exclusion. Excluded
            categories are still listed in the report with their reason, never dropped
            silently.

    Returns:
        A :class:`BiasAudit`.

    Raises:
        ValueError: If no outcome data is supplied at all.
    """
    if not any((sex_outcomes, race_outcomes, intersectional_outcomes)):
        raise ValueError(
            "supply at least one of sex_outcomes, race_outcomes, "
            "intersectional_outcomes"
        )

    min_share = LL144_MIN_SHARE if apply_two_percent_exclusion else 0.0

    def build(
        outcomes: dict[str, tuple[int, int]] | None, category: str
    ) -> ImpactReport | None:
        if not outcomes:
            return None
        groups = [GroupOutcome(name, s, t) for name, (s, t) in outcomes.items()]
        return adverse_impact(
            groups,
            category=category,
            min_share=min_share,
            threshold_label=selection_threshold,
        )

    return BiasAudit(
        tool_name=tool_name,
        tool_version=tool_version,
        audit_date=audit_date or date.today(),
        distribution_date=distribution_date,
        data_source=data_source,
        data_explanation=data_explanation,
        auditor=auditor,
        sex=build(sex_outcomes, "sex"),
        race=build(race_outcomes, "race/ethnicity"),
        intersectional=build(intersectional_outcomes, "sex x race/ethnicity"),
        unknown_count=unknown_count,
        selection_threshold=selection_threshold,
    )


def _format_ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _render_table(report: ImpactReport) -> list[str]:
    """Render one category's results as a markdown table."""
    lines = [
        "",
        f"### {report.category.title()}",
        "",
        f"Reference group (highest selection rate): **{report.reference_group}**",
        "",
        "| Category | Selected | Total | Selection rate | Impact ratio | Below 4/5? | Significance |",
        "|---|---:|---:|---:|---:|:---:|---|",
    ]

    for group in sorted(report.groups, key=lambda g: g.name):
        if group.is_reference:
            flag, ratio = "reference", "—"
        else:
            flag = "**YES**" if group.flagged else "no"
            ratio = _format_ratio(group.impact_ratio)

        if group.significance is None:
            significance = "—"
        else:
            marker = "*" if group.significance.significant_at_05 else ""
            significance = f"p={group.significance.p_value:.4f}{marker}"

        lines.append(
            f"| {group.name} | {group.selected} | {group.total} "
            f"| {group.selection_rate:.3f} | {ratio} | {flag} | {significance} |"
        )

    lines.append("")
    minimum = report.min_impact_ratio
    if minimum is not None:
        verdict = "at or above" if minimum >= FOUR_FIFTHS else "**below**"
        lines.append(
            f"Minimum impact ratio: **{minimum:.3f}** — {verdict} the 0.80 threshold."
        )
    else:
        lines.append("Minimum impact ratio: not computable (no group had selections).")

    if report.excluded:
        lines.extend(["", "**Excluded from impact-ratio calculations:**", ""])
        lines.extend(f"- {name} — {reason}" for name, reason in report.excluded)

    if report.notes:
        lines.extend(["", "**Auditor notes:**", ""])
        lines.extend(f"- {note}" for note in report.notes)

    return lines


def render_markdown(audit: BiasAudit) -> str:
    """Render a bias audit as a publishable markdown summary.

    Structured to cover each element the DCWP rules require, in a form an employer can
    post publicly and a regulator can read without a data-science background.

    Args:
        audit: The audit to render.

    Returns:
        Markdown source.
    """
    distribution = (
        audit.distribution_date.isoformat() if audit.distribution_date else "not stated"
    )

    lines = [
        f"# Bias Audit — {audit.tool_name}",
        "",
        "Prepared under New York City Local Law 144 of 2021 "
        "(Automated Employment Decision Tools).",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Tool | {audit.tool_name} |",
        f"| Version | {audit.tool_version} |",
        f"| Date of most recent bias audit | {audit.audit_date.isoformat()} |",
        f"| Distribution date of tool | {distribution} |",
        f"| Independent auditor | {audit.auditor} |",
        f"| Selection criterion | {audit.selection_threshold} |",
        f"| Individuals in unknown category | {audit.unknown_count} |",
        "",
        "## Data used",
        "",
        f"**Source:** {audit.data_source}",
        "",
        audit.data_explanation,
        "",
        "## Summary of results",
        "",
    ]

    if audit.failing_categories:
        lines.append(
            f"⚠️ Impact ratios below 0.80 were found in: "
            f"**{', '.join(audit.failing_categories)}**."
        )
    else:
        lines.append("All computed impact ratios are at or above 0.80.")

    lines.extend(
        [
            "",
            "Impact ratio is the selection rate of a category divided by the selection "
            "rate of the highest-selecting category. Under the EEOC Uniform Guidelines "
            "(29 CFR 1607.4(D)) a ratio below four-fifths (0.80) is generally regarded "
            "as evidence of adverse impact.",
            "",
            "`*` marks a difference statistically significant at p ≤ 0.05.",
            "",
        ]
    )

    for report in audit.reports:
        lines.extend(_render_table(report))

    lines.extend(
        [
            "",
            "## Interpretation and limits",
            "",
            "- An impact ratio at or above 0.80 does **not** establish that a selection "
            "procedure is lawful or job-related. 29 CFR 1607.4(D) provides that smaller "
            "differences may still constitute adverse impact where significant in both "
            "statistical and practical terms.",
            "- An impact ratio below 0.80 based on small numbers, without statistical "
            "significance, may **not** constitute adverse impact under the same section.",
            "- **Impact ratios depend on the selection threshold.** The criterion used "
            f"here was: {audit.selection_threshold}. A different cut score can produce "
            "materially different ratios from the same tool and the same data.",
            "- This audit reports outcomes. It does not assess the tool's validity, "
            "job-relatedness, or business necessity, which are separate obligations "
            "under 29 CFR 1607.14.",
            "",
        ]
    )

    if audit.notes:
        lines.extend(["## Additional auditor notes", ""])
        lines.extend(f"- {note}" for note in audit.notes)
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            f"Generated with [glassbox-hiring](https://github.com/SafeerAhmad211/glassbox-hiring) "
            f"on {date.today().isoformat()}. Generating this document does not make an "
            "audit independent within the meaning of Local Law 144, and it is not legal "
            "advice.",
        ]
    )

    return "\n".join(lines)
