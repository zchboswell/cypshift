"""Command-line entry point for cypshift."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cypshift import __version__
from cypshift.audit import AuditError, run_audit
from cypshift.schema import RecordError


def build_parser() -> argparse.ArgumentParser:
    """Build the current public command parser."""

    parser = argparse.ArgumentParser(
        prog="cypshift",
        description="Auditable CYP inhibition prediction",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    audit_parser = commands.add_parser(
        "audit", help="validate chemistry and measurement inputs"
    )
    audit_parser.add_argument("molecules", type=Path, help="input molecule CSV")
    audit_parser.add_argument(
        "--measurements",
        required=True,
        type=Path,
        help="input measurement CSV",
    )
    audit_parser.add_argument(
        "--out", required=True, type=Path, help="new output directory"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit status."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = run_audit(args.molecules, args.measurements, args.out)
            summary = result.report["summary"]
            warning_total = sum(summary["warning_counts"].values())
            print(
                "Audit complete: "
                f"{summary['molecules_accepted']} accepted, "
                f"{summary['molecules_quarantined']} quarantined, "
                f"{warning_total} warnings. "
                f"Outputs: {result.output_directory}"
            )
            return 0
    except (AuditError, OSError, RecordError) as exc:
        parser.error(str(exc))
    return 2
