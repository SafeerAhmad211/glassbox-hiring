"""Typed tool surface for agents driving glassbox.

Designed against the action-space rules in `agent-harness-construction`: stable names,
narrow schema-first inputs, deterministic output shapes, and error paths that carry a
root-cause hint plus a safe next step rather than a bare exception.

Every tool returns an :class:`Observation` with the same four fields, so an agent never
has to pattern-match on tool-specific success shapes:

- ``status``   — ``success`` | ``warning`` | ``error``
- ``summary``  — one line, the result stated plainly
- ``data``     — the structured payload
- ``next_actions`` — concrete follow-ups, named as tools where applicable

``warning`` is a distinct status on purpose. An audit finding adverse impact is not a
failed tool call -- the tool worked perfectly and the answer is bad news. Collapsing
those two into ``error`` teaches an agent to retry when it should be reporting.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ..audit.impact import adverse_impact, impact_ratio_curve
from ..audit.ll144 import build_bias_audit, render_markdown
from ..audit.perturb import run_perturbation_audit
from ..parse.diagnostics import diagnose
from ..parse.layout import TextBlock, column_aware_reading_order
from ..score.rubric import Rubric, score_resume

__all__ = ["TOOLS", "Observation", "call", "tool_schemas"]

Status = Literal["success", "warning", "error"]


@dataclass
class Observation:
    """Uniform tool result.

    Attributes:
        status: Outcome class. ``warning`` means the tool succeeded and the *finding*
            warrants attention -- not that the call failed.
        summary: One-line result.
        data: Structured payload.
        next_actions: Concrete follow-ups.
        artifacts: Paths or identifiers of anything written.
    """

    status: Status
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialise to JSON for transport to an agent."""
        return json.dumps(asdict(self), indent=2, default=str)


def _error(summary: str, hint: str, retry: str) -> Observation:
    """Build an error observation carrying a cause and a safe next step."""
    return Observation(
        status="error",
        summary=summary,
        data={"hint": hint},
        next_actions=[retry],
    )


def audit_selection_rates(
    outcomes: dict[str, list[int]],
    category: str = "unspecified",
    min_share: float = 0.0,
) -> Observation:
    """Run a four-fifths adverse-impact analysis on selection counts.

    Args:
        outcomes: ``{group_name: [selected, total]}``.
        category: Category label, e.g. ``"race/ethnicity"``.
        min_share: Exclude groups below this share of data. Use 0.02 for NYC LL144.
    """
    try:
        parsed = {name: (int(v[0]), int(v[1])) for name, v in outcomes.items()}
    except (TypeError, ValueError, IndexError):
        return _error(
            "Could not parse outcomes.",
            "Each value must be a two-element list [selected, total] of integers.",
            'Retry as {"Group A": [40, 100], "Group B": [50, 100]}.',
        )

    try:
        report = adverse_impact(parsed, category=category, min_share=min_share)
    except ValueError as exc:
        return _error(
            f"Analysis could not run: {exc}",
            "At least two groups with observations are required.",
            "Supply counts for two or more groups, or lower min_share.",
        )

    groups = [
        {
            "name": g.name,
            "selected": g.selected,
            "total": g.total,
            "selection_rate": round(g.selection_rate, 4),
            "impact_ratio": None if g.impact_ratio is None else round(g.impact_ratio, 4),
            "flagged": g.flagged,
            "shortfall": g.shortfall,
            "p_value": None if g.significance is None else round(g.significance.p_value, 6),
        }
        for g in report.groups
    ]

    data = {
        "category": report.category,
        "reference_group": report.reference_group,
        "min_impact_ratio": report.min_impact_ratio,
        "groups": groups,
        "excluded": [{"group": n, "reason": r} for n, r in report.excluded],
        "notes": report.notes,
    }

    if report.passes_four_fifths:
        return Observation(
            status="success",
            summary=(
                f"All impact ratios at or above 0.80 "
                f"(minimum {report.min_impact_ratio:.3f})."
                if report.min_impact_ratio is not None
                else "No selections in any group; impact ratios undefined."
            ),
            data=data,
            next_actions=[
                "Clearing 0.80 is not clearance -- check `notes` for significant "
                "differences that still passed.",
                "Call sweep_thresholds to check whether a nearby cut score fails.",
            ],
        )

    worst = report.flagged_groups[0]
    return Observation(
        status="warning",
        summary=(
            f"Adverse impact indicated: {worst.name} at impact ratio "
            f"{worst.impact_ratio:.3f} (below 0.80)."
        ),
        data=data,
        next_actions=[
            f"{worst.name} would need {worst.shortfall} additional selections to reach 0.80.",
            "Call sweep_thresholds to see whether a different cut score avoids this.",
            "Call generate_ll144_report to produce a publishable audit.",
            "Under 29 CFR 1607.14, a procedure with adverse impact requires validity evidence.",
        ],
    )


def sweep_thresholds(
    scores_by_group: dict[str, list[float]],
    percentiles: list[float] | None = None,
) -> Observation:
    """Compute the impact ratio across a range of cut scores.

    Args:
        scores_by_group: ``{group_name: [score, ...]}``.
        percentiles: Percentiles to test. Defaults to 10..90 by 10.
    """
    try:
        curve = impact_ratio_curve(
            {k: [float(s) for s in v] for k, v in scores_by_group.items()},
            percentiles=tuple(percentiles) if percentiles else (10, 20, 30, 40, 50, 60, 70, 80, 90),
        )
    except (ValueError, TypeError) as exc:
        return _error(
            f"Sweep could not run: {exc}",
            "Needs at least two groups with numeric scores.",
            'Retry as {"Group A": [0.1, 0.4, ...], "Group B": [...]}.',
        )

    points = [
        {
            "percentile": p.percentile,
            "threshold": round(p.threshold, 6),
            "min_impact_ratio": None if p.min_impact_ratio is None else round(p.min_impact_ratio, 4),
            "selection_rate": round(p.overall_selection_rate, 4),
            "passes": p.passes,
            "worst_group": p.worst_group,
        }
        for p in curve
    ]
    failing = [p for p in points if not p["passes"]]

    if not failing:
        return Observation(
            status="success",
            summary=f"Passes four-fifths at all {len(points)} thresholds tested.",
            data={"curve": points},
            next_actions=["Record the tested range in the audit; it strengthens the finding."],
        )

    return Observation(
        status="warning",
        summary=(
            f"Fails four-fifths at {len(failing)} of {len(points)} thresholds "
            f"(percentiles: {', '.join(str(p['percentile']) for p in failing)})."
        ),
        data={"curve": points, "failing_thresholds": failing},
        next_actions=[
            "An impact ratio is only meaningful with its threshold stated. Publish both.",
            "If the deployed cut score sits near a failing threshold, the configuration is fragile.",
        ],
    )


def audit_scorer_invariance(
    resumes: list[str],
    scorer: Callable[[str], float],
    tolerance: float = 1e-9,
) -> Observation:
    """Test whether a scorer is counterfactually invariant to names and pronouns.

    Args:
        resumes: Resume texts.
        scorer: Callable mapping resume text to a score.
        tolerance: Score change treated as noise.
    """
    try:
        report = run_perturbation_audit(
            resumes, scorer, invariance_tolerance=tolerance
        )
    except ValueError as exc:
        return _error(
            f"Perturbation audit could not run: {exc}",
            "Needs a non-empty resume list and a non-negative tolerance.",
            "Supply at least one resume.",
        )
    except Exception as exc:
        # `scorer` is arbitrary caller code -- typically an HTTP call to a model
        # endpoint. Its failure is an ordinary operational event, not a bug in this
        # tool, and an agent must receive it as a recoverable observation rather
        # than a traceback.
        return _error(
            f"The supplied scorer raised {type(exc).__name__}: {exc}",
            "The failure came from the scorer callable, not from the audit itself.",
            "Verify the scorer runs standalone on one resume, then retry.",
        )

    spread = {k: round(v, 6) for k, v in report.dimension_spread().items()}

    if report.is_invariant:
        return Observation(
            status="success",
            summary=f"Scorer is invariant to all probes across {report.n_resumes} resume(s).",
            data={"dimension_spread": spread, "n_resumes": report.n_resumes},
            next_actions=[
                "Invariance is necessary but not sufficient -- run audit_selection_rates "
                "on real outcomes, since correlated legitimate features can still "
                "produce disparate impact."
            ],
        )

    violations = [
        {
            "perturbation": v.perturbation,
            "dimension": v.dimension,
            "mean_delta": round(v.mean_delta, 6),
            "max_abs_delta": round(v.max_abs_delta, 6),
            "n_changed": v.n_changed,
        }
        for v in report.violations
    ]
    worst = violations[0]

    return Observation(
        status="warning",
        summary=(
            f"Scorer is NOT invariant: {worst['perturbation']} moved the mean score by "
            f"{worst['mean_delta']:+.4f}."
        ),
        data={"violations": violations, "dimension_spread": spread},
        next_actions=[
            "Identify which feature carries the signal and whether it is job-related.",
            "Re-test after removing it; the HireVue patent's iterative feature ablation "
            "is the same move.",
        ],
    )


def check_resume_parseability(
    blocks: list[dict[str, Any]],
    has_tables: bool = False,
    has_images: bool = False,
    naive_text: str | None = None,
) -> Observation:
    """Diagnose what a screener will lose from a document.

    Args:
        blocks: ``[{"text": ..., "x": ..., "y": ..., "size": ..., "page": ...}, ...]``.
        has_tables: Whether the document contains tables.
        has_images: Whether the document contains images.
        naive_text: Output of a geometry-blind extractor, if available.
    """
    try:
        parsed = [
            TextBlock(
                text=b["text"],
                x=float(b["x"]),
                y=float(b["y"]),
                size=float(b.get("size", 11.0)),
                page=int(b.get("page", 0)),
                emit_index=int(b.get("emit_index", i)),
            )
            for i, b in enumerate(blocks)
        ]
    except (KeyError, TypeError, ValueError) as exc:
        return _error(
            f"Could not parse blocks: {exc}",
            "Each block needs at least text, x, and y.",
            'Retry with [{"text": "Jane Doe", "x": 50, "y": 700}].',
        )

    report = diagnose(
        parsed, has_tables=has_tables, has_images=has_images, naive_text=naive_text
    )
    findings = [
        {
            "code": f.code,
            "severity": f.severity.value,
            "summary": f.summary,
            "fix": f.fix,
        }
        for f in report.by_severity()
    ]
    data = {
        "findings": findings,
        "n_columns": report.n_columns,
        "n_pages": report.n_pages,
        "reading_order_differs": report.reading_order_differs,
        "extracted_text": column_aware_reading_order(parsed),
    }

    if report.is_clean:
        return Observation(
            status="success",
            summary="Document is cleanly parseable; no issues above LOW severity.",
            data=data,
            next_actions=["Call match_resume_to_rubric to assess content fit."],
        )

    critical = report.critical
    return Observation(
        status="warning",
        summary=(
            f"{len(findings)} parseability issue(s), {len(critical)} critical: "
            f"{findings[0]['summary']}"
        ),
        data=data,
        next_actions=[f["fix"] for f in findings[:3]],
    )


def match_resume_to_rubric(
    resume_text: str,
    required_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
) -> Observation:
    """Score a resume against a transparent skills rubric.

    Args:
        resume_text: Plain text of the resume.
        required_skills: Must-have skills.
        preferred_skills: Nice-to-have skills.
    """
    try:
        rubric = Rubric.from_skills(required_skills, preferred_skills)
    except ValueError as exc:
        return _error(
            f"Rubric invalid: {exc}",
            "At least one required or preferred skill is needed.",
            'Retry with required_skills=["Python"].',
        )

    result = score_resume(resume_text, rubric)
    data = {
        "score": round(result.score, 4),
        "matched": [
            {
                "requirement": r.requirement.name,
                "points": round(r.points, 4),
                "line_number": r.evidence[0].line_number,
                "evidence": r.evidence[0].line.strip()[:120],
            }
            for r in result.matched
        ],
        "gaps": [
            {"requirement": r.requirement.name, "would_add": round(r.weight_share, 4)}
            for r in result.gaps
        ],
        "missing_required": [r.requirement.name for r in result.missing_required],
        "explanation": result.explain(),
    }

    if result.missing_required:
        return Observation(
            status="warning",
            summary=(
                f"Score {result.score:.3f}; missing required: "
                f"{', '.join(r.requirement.name for r in result.missing_required)}."
            ),
            data=data,
            next_actions=[
                "Every point is attributed in `explanation` -- nothing is hidden.",
                "Call audit_scorer_invariance to confirm this rubric is name-blind.",
            ],
        )

    return Observation(
        status="success",
        summary=f"Score {result.score:.3f}; all required skills evidenced.",
        data=data,
        next_actions=["Review `explanation` for the full attribution."],
    )


def generate_ll144_report(
    tool_name: str,
    tool_version: str,
    auditor: str,
    data_source: str,
    data_explanation: str,
    sex_outcomes: dict[str, list[int]] | None = None,
    race_outcomes: dict[str, list[int]] | None = None,
    intersectional_outcomes: dict[str, list[int]] | None = None,
    unknown_count: int = 0,
    selection_threshold: str = "not specified",
    output_path: str | None = None,
) -> Observation:
    """Produce a NYC Local Law 144 bias-audit summary.

    Args:
        tool_name: Name of the AEDT.
        tool_version: Version identifier.
        auditor: Independent auditor's name.
        data_source: Provenance of the data.
        data_explanation: Narrative explanation of the dataset.
        sex_outcomes: ``{category: [selected, total]}``.
        race_outcomes: ``{category: [selected, total]}``.
        intersectional_outcomes: ``{"Female / Asian": [selected, total], ...}``.
        unknown_count: Individuals in an unknown demographic category.
        selection_threshold: Description of the selection criterion.
        output_path: If given, write the markdown here.
    """
    def convert(d: dict[str, list[int]] | None) -> dict[str, tuple[int, int]] | None:
        return None if not d else {k: (int(v[0]), int(v[1])) for k, v in d.items()}

    try:
        audit = build_bias_audit(
            tool_name=tool_name,
            tool_version=tool_version,
            auditor=auditor,
            data_source=data_source,
            data_explanation=data_explanation,
            sex_outcomes=convert(sex_outcomes),
            race_outcomes=convert(race_outcomes),
            intersectional_outcomes=convert(intersectional_outcomes),
            unknown_count=unknown_count,
            selection_threshold=selection_threshold,
        )
    except (ValueError, TypeError, IndexError) as exc:
        return _error(
            f"Could not build audit: {exc}",
            "Supply at least one outcome mapping of {category: [selected, total]}.",
            'Retry with sex_outcomes={"Male": [50, 100], "Female": [40, 100]}.',
        )

    markdown = render_markdown(audit)
    artifacts = []
    if output_path:
        try:
            # Explicit UTF-8: the report contains typographic characters that the
            # Windows default codepage cannot encode.
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(markdown)
            artifacts.append(output_path)
        except OSError as exc:
            return _error(
                f"Report generated but could not be written: {exc}",
                "The output directory may not exist or may not be writable.",
                "Retry with a valid output_path, or omit it to receive the markdown inline.",
            )

    data = {
        "markdown": markdown,
        "all_pass": audit.all_pass,
        "failing_categories": audit.failing_categories,
        "categories_reported": [r.category for r in audit.reports],
    }

    if audit.all_pass:
        return Observation(
            status="success",
            summary="Bias audit generated; all impact ratios at or above 0.80.",
            data=data,
            artifacts=artifacts,
            next_actions=[
                "LL144 requires an auditor independent of the tool's users, developers, "
                "and distributors. Generating this document does not satisfy that."
            ],
        )

    return Observation(
        status="warning",
        summary=(
            f"Bias audit generated; impact ratios below 0.80 in: "
            f"{', '.join(audit.failing_categories)}."
        ),
        data=data,
        artifacts=artifacts,
        next_actions=[
            "LL144 requires publication of results, including unfavourable ones.",
            "Under 29 CFR 1607.14, adverse impact triggers a validity-evidence obligation.",
        ],
    )


#: The agent-callable action space. Names are stable API.
TOOLS: dict[str, Callable[..., Observation]] = {
    "audit_selection_rates": audit_selection_rates,
    "sweep_thresholds": sweep_thresholds,
    "audit_scorer_invariance": audit_scorer_invariance,
    "check_resume_parseability": check_resume_parseability,
    "match_resume_to_rubric": match_resume_to_rubric,
    "generate_ll144_report": generate_ll144_report,
}


def call(tool_name: str, /, **kwargs: Any) -> Observation:
    """Dispatch a tool by name.

    ``tool_name`` is positional-only. Several tools take a ``tool_name`` argument of
    their own -- ``generate_ll144_report`` names the AEDT being audited -- and without
    the ``/`` those tools are simply uncallable through this dispatcher, failing with
    "got multiple values for argument".

    Args:
        tool_name: One of the keys of :data:`TOOLS`. Positional-only.
        **kwargs: Tool arguments.

    Returns:
        An :class:`Observation`. An unknown name or bad argument returns an ``error``
        observation naming the valid options rather than raising -- an agent recovers
        from a message far more reliably than from a traceback.
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        return _error(
            f"Unknown tool: {tool_name!r}",
            f"Valid tools are: {', '.join(sorted(TOOLS))}.",
            "Retry with one of the listed tool names.",
        )

    try:
        return tool(**kwargs)
    except TypeError as exc:
        return _error(
            f"Invalid arguments for {tool_name}: {exc}",
            "An argument is missing, misspelled, or of the wrong type.",
            f"Check the signature via tool_schemas()[{tool_name!r}] and retry.",
        )
    except Exception as exc:
        # Last-resort net. The harness guarantees that no dispatched call raises:
        # an agent recovers from a message far more reliably than from a traceback,
        # and a tool that escapes this contract can strand an autonomous loop. Tools
        # should still handle their own expected failures with specific guidance --
        # this only catches what they missed.
        return _error(
            f"{tool_name} failed unexpectedly with {type(exc).__name__}: {exc}",
            "This is an unhandled error inside the tool, not a problem with the "
            "inputs as such.",
            "Retry with simpler inputs to isolate the cause, and report it as a bug "
            "if it persists.",
        )


def tool_schemas() -> dict[str, dict[str, Any]]:
    """Return name, description, and parameter names for each tool.

    Enough for an agent to construct a call without reading the source.
    """
    import inspect

    schemas = {}
    for name, fn in TOOLS.items():
        signature = inspect.signature(fn)
        doc = (fn.__doc__ or "").strip().split("\n")[0]
        schemas[name] = {
            "description": doc,
            "parameters": {
                param_name: {
                    "required": param.default is inspect.Parameter.empty,
                    "default": None
                    if param.default is inspect.Parameter.empty
                    else param.default,
                }
                for param_name, param in signature.parameters.items()
            },
        }
    return schemas
