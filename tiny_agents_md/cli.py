from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from . import __version__
from .doctor import DoctorReport, run_doctor
from .generator import render_agents_md
from .scanner import scan_repo


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _run_init(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "loop":
        return _run_loop(args)

    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiny-agents-md",
        description="Generate a minimal AGENTS.md from repository facts.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser("init", help="Generate AGENTS.md")
    init_parser.add_argument("path", nargs="?", default=".")
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a unified diff instead of writing AGENTS.md.",
    )
    init_parser.add_argument(
        "--write",
        action="store_true",
        help="Write AGENTS.md. This is the default unless --dry-run is used.",
    )
    init_parser.add_argument(
        "--format",
        choices=("md",),
        default="md",
        help="Output format. Only md is supported in v0.1.",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Check AGENTS.md health")
    doctor_parser.add_argument("path", nargs="?", default=".")
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON report.",
    )
    doctor_parser.add_argument(
        "--file",
        default="AGENTS.md",
        help="Instruction file to check, relative to the repository root.",
    )
    doctor_parser.add_argument(
        "--min-score",
        type=int,
        default=75,
        help="Minimum doctor score required for a zero exit code.",
    )
    doctor_parser.add_argument(
        "--explain",
        action="store_true",
        help="Include detected command and path evidence in the report.",
    )

    loop_parser = subparsers.add_parser(
        "loop",
        help="Regenerate AGENTS.md and run doctor until stable.",
    )
    loop_parser.add_argument("path", nargs="?", default=".")
    loop_parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum regeneration/check iterations.",
    )
    loop_parser.add_argument(
        "--min-score",
        type=int,
        default=90,
        help="Minimum doctor score required for success.",
    )
    return parser


def _run_init(args: argparse.Namespace) -> int:
    if args.dry_run and args.write:
        print("error: choose either --dry-run or --write, not both", file=sys.stderr)
        return 2

    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    facts = scan_repo(root)
    content = render_agents_md(facts)

    for warning in facts.warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    target = root / "AGENTS.md"
    if args.dry_run:
        _print_diff(target, content)
        return 0

    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    if args.min_score < 0 or args.min_score > 100:
        print("error: --min-score must be between 0 and 100", file=sys.stderr)
        return 2

    report = run_doctor(root, args.file)
    if args.json:
        print(json.dumps(report.to_dict(include_explain=args.explain), indent=2))
    else:
        _print_doctor_report(report, explain=args.explain)
    return 0 if report.score >= args.min_score else 1


def _print_doctor_report(report: DoctorReport, explain: bool = False) -> None:
    print("AGENTS.md Health Report")
    print()
    print(f"File: {report.file}")
    print(f"Score: {report.score}/100")
    print(f"Rating: {report.rating}")
    print()

    if not report.issues:
        print("Issues: none")
    else:
        print("Issues:")
        for issue in report.issues:
            print(f"- {issue.message}")

        suggestions = [issue.suggestion for issue in report.issues if issue.suggestion]
        if suggestions:
            print()
            print("Suggestions:")
            for suggestion in dict.fromkeys(suggestions):
                print(f"- {suggestion}")

    if explain:
        _print_doctor_explain(report)


def _print_doctor_explain(report: DoctorReport) -> None:
    print()
    print("Valid Commands:")
    if report.valid_commands:
        for command in report.valid_commands:
            sources = ", ".join(command.sources)
            print(f"- `{command.command}` from {sources}")
    else:
        print("- none detected")

    print()
    print("Valid Paths:")
    if report.valid_paths:
        for path in report.valid_paths:
            print(f"- `{path.path}` ({path.kind})")
    else:
        print("- none detected")


def _run_loop(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    if args.max_iterations < 1:
        print("error: --max-iterations must be at least 1", file=sys.stderr)
        return 2
    if args.min_score < 0 or args.min_score > 100:
        print("error: --min-score must be between 0 and 100", file=sys.stderr)
        return 2

    target = root / "AGENTS.md"

    for iteration in range(1, args.max_iterations + 1):
        generated = render_agents_md(scan_repo(root))
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        changed = current != generated

        if changed:
            target.write_text(generated, encoding="utf-8")
            print(f"Iteration {iteration}: wrote {target}")
        else:
            print(f"Iteration {iteration}: AGENTS.md unchanged")

        report = run_doctor(root)
        print(f"Iteration {iteration}: doctor score {report.score}/100 ({report.rating})")

        stable = _agents_md_is_stable(root, target)
        if stable and report.score >= args.min_score:
            print("Loop converged.")
            return 0

        if stable and report.score < args.min_score:
            print()
            _print_doctor_report(report)
            return 1

    print("error: loop did not converge", file=sys.stderr)
    return 1


def _agents_md_is_stable(root: Path, target: Path) -> bool:
    if not target.exists():
        return False
    generated = render_agents_md(scan_repo(root))
    current = target.read_text(encoding="utf-8")
    return current == generated


def _print_diff(target: Path, generated: str) -> None:
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=str(target),
        tofile=f"{target} (generated)",
    )
    output = "".join(diff)
    if output:
        print(output, end="")
    else:
        print("AGENTS.md is up to date.")
