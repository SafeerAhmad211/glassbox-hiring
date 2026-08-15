"""End-to-end example: score candidates, then audit the scorer that did it.

Runnable as-is, with no data files and no network:

    python examples/end_to_end.py

The point of the walkthrough is that the two audits answer different questions and
can disagree. A scorer can be perfectly blind to names and still select groups at
different rates, because the features it *does* use are correlated with group
membership. That is not a bug in the scorer; it is the thing adverse-impact law is
about, and you only see it by running both checks.
"""

from __future__ import annotations

import contextlib
import sys

from glassbox.audit.impact import adverse_impact, impact_ratio_curve
from glassbox.audit.perturb import run_perturbation_audit
from glassbox.score.rubric import Requirement, Rubric, score_resume

# `MatchResult.explain()` marks matched requirements with ✓, and the reports use en
# dashes. The default Windows console codepage (cp1252) cannot encode either, so
# printing them raises UnicodeEncodeError. Any script that prints glassbox output on
# Windows needs this; the `glassbox` CLI does the same thing internally.
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(ValueError, OSError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 1. the screener

RUBRIC = Rubric(
    [
        Requirement("Python", ("python",), weight=3.0, required=True),
        Requirement("PostgreSQL", ("postgres", "postgresql"), weight=2.0),
        Requirement("Kubernetes", ("kubernetes", "k8s"), weight=2.0),
        Requirement("Docker", ("docker",), weight=1.0),
    ],
    name="Backend Engineer",
)


def screen(resume_text: str) -> float:
    """The scorer under audit. Any callable taking text and returning a float works."""
    return score_resume(resume_text, RUBRIC).score


# ---------------------------------------------------------------- 2. the candidates


def resume(name: str, skills: str) -> str:
    return f"{name}\n{name.split()[0].lower()}@example.com\n\nEXPERIENCE\nEngineer, Acme Corp\n2020 - 2024\n{skills}\n"


# Two cohorts. Cohort B lists the infrastructure tooling less often -- a difference in
# the resumes themselves, not in how the scorer treats the names. Overlapping but
# unequal distributions are what real applicant pools look like.
COHORT_A = [
    resume("Alice Nguyen", "Built services in Python with PostgreSQL, Kubernetes and Docker."),
    resume("Ben Carter", "Python and PostgreSQL services, deployed on Kubernetes."),
    resume("Chidi Okafor", "Python and Docker, some PostgreSQL."),
    resume("Dana Levin", "Python services with Kubernetes and Docker."),
    resume("Eli Brandt", "Python and PostgreSQL reporting tools."),
    resume("Farah Aziz", "Python, Kubernetes and PostgreSQL platform work."),
]
COHORT_B = [
    resume("Grace Mbeki", "Python services with PostgreSQL and Kubernetes."),
    resume("Hana Sato", "Python and PostgreSQL data pipelines."),
    resume("Idris Bello", "Python scripting and some Docker."),
    resume("Julia Roth", "Python data pipelines."),
    resume("Kofi Mensah", "Python and Docker."),
    resume("Lena Fischer", "Python automation work."),
]


def main() -> None:
    print("=" * 72)
    print("1. SCORE — every point traces to a requirement and a line")
    print("=" * 72)
    result = score_resume(COHORT_A[0], RUBRIC)
    print(result.explain())

    print()
    print("=" * 72)
    print("2. PERTURB — is the scorer sensitive to names and pronouns?")
    print("=" * 72)
    perturbation = run_perturbation_audit(COHORT_A + COHORT_B, screen)
    print(f"counterfactually invariant : {perturbation.is_invariant}")
    print(f"score movement by dimension: {perturbation.dimension_spread()}")
    print()
    print("A rubric keys only on named job-relevant terms, so swapping a candidate's")
    print("name cannot move the score. Invariance is necessary -- but not sufficient.")

    print()
    print("=" * 72)
    print("3. ADVERSE IMPACT — do the outcomes differ anyway?")
    print("=" * 72)
    threshold = 0.75
    scores = {
        "Cohort A": [screen(r) for r in COHORT_A],
        "Cohort B": [screen(r) for r in COHORT_B],
    }
    outcomes = {
        name: (sum(1 for s in group if s >= threshold), len(group))
        for name, group in scores.items()
    }
    report = adverse_impact(
        outcomes,
        category="cohort",
        threshold=threshold,
        threshold_label=f"score >= {threshold}",
    )

    print(f"reference group: {report.reference_group}\n")
    for group in sorted(report.groups, key=lambda g: g.name):
        ratio = "reference" if group.is_reference else f"{group.impact_ratio:.3f}"
        flag = "  <-- below 0.80" if group.flagged else ""
        print(
            f"  {group.name:<10} {group.selected}/{group.total} selected"
            f"  rate={group.selection_rate:.3f}  IR={ratio}{flag}"
        )
        if group.shortfall:
            print(f"{'':<14}needs {group.shortfall} more selection(s) to reach 0.80")

    print()
    print(f"passes four-fifths: {report.passes_four_fifths}")
    for note in report.notes:
        print(f"  note: {note}")

    print()
    print("Same scorer, no name sensitivity at all -- yet the selection rates differ,")
    print("because the skills it rewards are distributed differently across cohorts.")
    print("Whether that is lawful turns on job-relatedness (29 CFR 1607.14), which is")
    print("a validity question this library does not answer for you.")

    print()
    print("=" * 72)
    print("4. SWEEP — the impact ratio depends on where you cut")
    print("=" * 72)
    print(f"{'percentile':>11} {'threshold':>10} {'min IR':>8} {'sel rate':>9}  verdict")
    for point in impact_ratio_curve(scores, percentiles=(10, 25, 50, 75)):
        ratio = "—" if point.min_impact_ratio is None else f"{point.min_impact_ratio:.3f}"
        print(
            f"{point.percentile:>11g} {point.threshold:>10.3f} {ratio:>8} "
            f"{point.overall_selection_rate:>9.3f}  "
            f"{'PASS' if point.passes else 'FAIL'}"
        )
    print()
    print("Reporting one ratio without naming its cut score is not reproducible.")


if __name__ == "__main__":
    main()
