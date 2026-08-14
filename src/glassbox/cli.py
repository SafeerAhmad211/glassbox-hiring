"""Command-line interface for glassbox.

Subcommands mirror the four surfaces: ``audit``, ``sweep``, ``ll144``, ``lens``,
``atlas``, and ``tools``.

All output is written as UTF-8 explicitly. The reports contain typographic characters
(en dashes, ✓/✗, ⚠) that the Windows console codepage cannot encode, and a compliance
tool that crashes when redirected to a file on one platform is not a usable tool.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .agent.tools import call, tool_schemas
from .atlas import load_atlas

__all__ = ["main"]


def _configure_stdout() -> None:
    """Force UTF-8 on stdout where the platform default cannot encode our output."""
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(ValueError, OSError):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load_counts(path: Path) -> dict[str, list[int]]:
    """Load ``{group: [selected, total]}`` from CSV or JSON.

    CSV is expected with columns ``group``, ``selected``, ``total``.

    Raises:
        ValueError: If the file cannot be interpreted.
    """
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".json":
        data = json.loads(text)
        return {k: [int(v[0]), int(v[1])] for k, v in data.items()}

    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        raise ValueError(f"{path}: no rows found")

    missing = {"group", "selected", "total"} - set(rows[0].keys() or ())
    if missing:
        raise ValueError(
            f"{path}: CSV needs columns group, selected, total (missing: {sorted(missing)})"
        )
    return {r["group"]: [int(r["selected"]), int(r["total"])] for r in rows}


def _load_scores(path: Path) -> dict[str, list[float]]:
    """Load ``{group: [score, ...]}`` from CSV (columns ``group``, ``score``) or JSON."""
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".json":
        return {k: [float(s) for s in v] for k, v in json.loads(text).items()}

    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        raise ValueError(f"{path}: no rows found")

    missing = {"group", "score"} - set(rows[0].keys() or ())
    if missing:
        raise ValueError(f"{path}: CSV needs columns group, score (missing: {sorted(missing)})")

    scores: dict[str, list[float]] = {}
    for row in rows:
        scores.setdefault(row["group"], []).append(float(row["score"]))
    return scores


def _emit(observation: Any, as_json: bool) -> int:
    """Print an observation and map its status to an exit code.

    Exit codes are meaningful for CI: 0 success, 1 finding, 2 error. A bias audit that
    finds adverse impact should be able to fail a pipeline.
    """
    if as_json:
        print(observation.to_json())
    else:
        marker = {"success": "OK", "warning": "FINDING", "error": "ERROR"}[observation.status]
        print(f"[{marker}] {observation.summary}")
        if observation.next_actions:
            print()
            for action in observation.next_actions:
                print(f"  → {action}")
        if observation.artifacts:
            print()
            for artifact in observation.artifacts:
                print(f"  wrote: {artifact}")

    return {"success": 0, "warning": 1, "error": 2}[observation.status]


def _cmd_audit(args: argparse.Namespace) -> int:
    outcomes = _load_counts(Path(args.counts))
    return _emit(
        call(
            "audit_selection_rates",
            outcomes=outcomes,
            category=args.category,
            min_share=args.min_share,
        ),
        args.json,
    )


def _cmd_sweep(args: argparse.Namespace) -> int:
    scores = _load_scores(Path(args.scores))
    observation = call("sweep_thresholds", scores_by_group=scores)

    if not args.json and observation.status != "error":
        print(f"{'pct':>5} {'threshold':>12} {'min IR':>8} {'sel rate':>9}  {'':<6} worst")
        print("-" * 58)
        for point in observation.data["curve"]:
            ratio = point["min_impact_ratio"]
            print(
                f"{point['percentile']:>5g} {point['threshold']:>12.4f} "
                f"{'—' if ratio is None else f'{ratio:>8.3f}'} "
                f"{point['selection_rate']:>9.3f}  "
                f"{'PASS' if point['passes'] else 'FAIL':<6} {point['worst_group'] or ''}"
            )
        print()

    return _emit(observation, args.json)


def _cmd_ll144(args: argparse.Namespace) -> int:
    kwargs: dict[str, Any] = {
        "tool_name": args.tool_name,
        "tool_version": args.tool_version,
        "auditor": args.auditor,
        "data_source": args.data_source,
        "data_explanation": args.data_explanation,
        "unknown_count": args.unknown_count,
        "selection_threshold": args.selection_threshold,
        "output_path": args.out,
    }
    for key, path in (
        ("sex_outcomes", args.sex),
        ("race_outcomes", args.race),
        ("intersectional_outcomes", args.intersectional),
    ):
        if path:
            kwargs[key] = _load_counts(Path(path))

    observation = call("generate_ll144_report", **kwargs)
    if not args.out and observation.status != "error" and not args.json:
        print(observation.data["markdown"])
        return {"success": 0, "warning": 1, "error": 2}[observation.status]
    return _emit(observation, args.json)


def _cmd_lens(args: argparse.Namespace) -> int:
    from .parse.pdf import extract_blocks

    try:
        blocks, flags = extract_blocks(Path(args.resume))
    except ImportError:
        print(
            "[ERROR] PDF support needs the parse extra: pip install 'glassbox-hiring[parse]'",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Could not read {args.resume}: {exc}", file=sys.stderr)
        return 2

    observation = call(
        "check_resume_parseability",
        blocks=[
            {
                "text": b.text, "x": b.x, "y": b.y, "size": b.size,
                "page": b.page, "emit_index": b.emit_index,
            }
            for b in blocks
        ],
        has_images=flags.get("has_images", False),
        has_tables=flags.get("has_tables", False),
        naive_text=flags.get("naive_text"),
    )

    if not args.json and observation.status != "error":
        print(f"Parseability report — {args.resume}\n")
        for finding in observation.data["findings"]:
            print(f"  [{finding['severity'].upper():<8}] {finding['summary']}")
            print(f"             fix: {finding['fix']}\n")
        if args.show_text:
            print("--- text as a screener would extract it ---")
            print(observation.data["extracted_text"])
            print()

    if args.skills:
        skills = [s.strip() for s in args.skills.split(",") if s.strip()]
        match = call(
            "match_resume_to_rubric",
            resume_text=observation.data.get("extracted_text", ""),
            required_skills=skills,
        )
        if not args.json:
            print(match.data.get("explanation", ""))
            print()

    return _emit(observation, args.json)


def _cmd_atlas(args: argparse.Namespace) -> int:
    atlas = load_atlas()

    if args.regulations:
        for regulation in atlas["regulations"]:
            print(f"{regulation['name']}")
            print(f"  jurisdiction: {regulation['jurisdiction']}")
            print(f"  status: {regulation['status']}")
            if "warning" in regulation:
                print(f"  ⚠ {regulation['warning']}")
            print()
        return 0

    vendors = atlas["vendors"]
    if args.category:
        vendors = [v for v in vendors if v["category"] == args.category]

    if args.json:
        print(json.dumps(vendors, indent=2))
        return 0

    print(f"{'id':<22} {'category':<12} {'tier':<18} name")
    print("-" * 78)
    for vendor in vendors:
        print(f"{vendor['id']:<22} {vendor['category']:<12} {vendor['tier']:<18} {vendor['name']}")
    print(f"\n{len(vendors)} vendor(s). Evidence levels are per-field; see data/vendors.json.")
    return 0


def _cmd_tools(args: argparse.Namespace) -> int:
    schemas = tool_schemas()
    if args.json:
        print(json.dumps(schemas, indent=2))
        return 0

    for name, schema in sorted(schemas.items()):
        print(f"{name}")
        print(f"  {schema['description']}")
        required = [p for p, s in schema["parameters"].items() if s["required"]]
        optional = [p for p, s in schema["parameters"].items() if not s["required"]]
        if required:
            print(f"  required: {', '.join(required)}")
        if optional:
            print(f"  optional: {', '.join(optional)}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="glassbox",
        description="Audit and inspect algorithmic hiring systems.",
        epilog="Exit codes: 0 = clean, 1 = finding, 2 = error.",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="four-fifths adverse-impact analysis")
    audit.add_argument("counts", help="CSV (group,selected,total) or JSON")
    audit.add_argument("--category", default="unspecified")
    audit.add_argument(
        "--min-share", type=float, default=0.0,
        help="exclude groups below this share of data (0.02 for NYC LL144)",
    )
    audit.set_defaults(func=_cmd_audit)

    sweep = subparsers.add_parser("sweep", help="impact ratio across cut scores")
    sweep.add_argument("scores", help="CSV (group,score) or JSON")
    sweep.set_defaults(func=_cmd_sweep)

    ll144 = subparsers.add_parser("ll144", help="generate an NYC LL144 bias audit")
    ll144.add_argument("--tool-name", required=True)
    ll144.add_argument("--tool-version", default="unspecified")
    ll144.add_argument("--auditor", required=True)
    ll144.add_argument("--data-source", required=True)
    ll144.add_argument("--data-explanation", default="")
    ll144.add_argument("--sex", help="counts file for sex categories")
    ll144.add_argument("--race", help="counts file for race/ethnicity categories")
    ll144.add_argument("--intersectional", help="counts file for intersectional categories")
    ll144.add_argument("--unknown-count", type=int, default=0)
    ll144.add_argument("--selection-threshold", default="not specified")
    ll144.add_argument("--out", help="write markdown here instead of stdout")
    ll144.set_defaults(func=_cmd_ll144)

    lens = subparsers.add_parser("lens", help="what a screener loses from a resume")
    lens.add_argument("resume", help="path to a PDF or DOCX")
    lens.add_argument("--skills", help="comma-separated skills to match against")
    lens.add_argument("--show-text", action="store_true", help="print extracted text")
    lens.set_defaults(func=_cmd_lens)

    atlas = subparsers.add_parser("atlas", help="browse the vendor/regulation atlas")
    atlas.add_argument("--category", choices=["ats", "assessment"])
    atlas.add_argument("--regulations", action="store_true", help="list regulations instead")
    atlas.set_defaults(func=_cmd_atlas)

    tools = subparsers.add_parser("tools", help="list the agent tool surface")
    tools.set_defaults(func=_cmd_tools)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point.

    Returns:
        0 clean, 1 finding, 2 error.
    """
    _configure_stdout()
    args = build_parser().parse_args(argv)

    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(f"[ERROR] File not found: {exc.filename}", file=sys.stderr)
        return 2
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
