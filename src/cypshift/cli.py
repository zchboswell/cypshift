"""Command-line entry point for cypshift."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cypshift import __version__
from cypshift.audit import AuditError, run_audit
from cypshift.baseline import (
    DEFAULT_SEED,
    DEFAULT_VALIDATION_FRACTION,
    BaselineError,
    predict_baseline,
    train_baseline,
)
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

    train_parser = commands.add_parser(
        "train", help="fit the Phase 0 endpoint-context median"
    )
    train_parser.add_argument(
        "--data", required=True, type=Path, help="audited data directory"
    )
    train_parser.add_argument(
        "--out", required=True, type=Path, help="output directory"
    )
    train_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    train_parser.add_argument(
        "--validation-fraction",
        type=float,
        default=DEFAULT_VALIDATION_FRACTION,
    )

    predict_parser = commands.add_parser(
        "predict", help="generate Phase 0 median predictions"
    )
    predict_parser.add_argument(
        "--data", required=True, type=Path, help="audited data directory"
    )
    predict_parser.add_argument(
        "--model", required=True, type=Path, help="model JSON"
    )
    predict_parser.add_argument(
        "--split",
        type=Path,
        help="split CSV (defaults to split.csv beside the model)",
    )
    predict_parser.add_argument(
        "--out", required=True, type=Path, help="output directory"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit status."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            audit_result = run_audit(
                args.molecules, args.measurements, args.out
            )
            summary = audit_result.report["summary"]
            warning_total = sum(summary["warning_counts"].values())
            print(
                "Audit complete: "
                f"{summary['molecules_accepted']} accepted, "
                f"{summary['molecules_quarantined']} quarantined, "
                f"{warning_total} warnings. "
                f"Outputs: {audit_result.output_directory}"
            )
            return 0
        if args.command == "train":
            training_result = train_baseline(
                args.data,
                args.out,
                seed=args.seed,
                validation_fraction=args.validation_fraction,
            )
            context_count = training_result.model["fit_summary"]["contexts"]
            print(
                f"Training complete: {context_count} endpoint contexts. "
                f"Model: {training_result.model_path}; "
                f"split: {training_result.split_path}"
            )
            return 0
        if args.command == "predict":
            split_path = args.split or args.model.with_name("split.csv")
            prediction_result = predict_baseline(
                args.data, args.model, split_path, args.out
            )
            print(
                "Prediction complete: "
                f"{prediction_result.prediction_count} predictions. "
                f"Outputs: {prediction_result.predictions_path.parent}"
            )
            return 0
    except (AuditError, BaselineError, OSError, RecordError) as exc:
        parser.error(str(exc))
    return 2
