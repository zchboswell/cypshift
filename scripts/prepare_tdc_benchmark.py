"""Reproduce the frozen TDC CYP ingestion and canonical chemistry audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from cypshift.audit import run_audit
from cypshift.tdc import prepare_tdc_admet

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "public_sources.json"
)


def main() -> None:
    """Prepare adapter and canonical artifacts from the frozen TDC archive."""

    parser = argparse.ArgumentParser(
        description=(
            "Verify and ingest the frozen TDC ADMET_Group CYP benchmark archive."
        )
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    source_contract = _load_tdc_contract(args.manifest)
    archive_contract = _mapping(source_contract, "archive")
    task_contracts = _mapping(source_contract, "tasks")
    result = prepare_tdc_admet(
        args.archive,
        args.out / "adapter",
        expected_archive_sha256=_text(archive_contract, "sha256"),
        task_contracts=task_contracts,
    )
    audit = run_audit(
        result.molecules_path,
        result.measurements_path,
        args.out / "canonical",
    )
    summary = audit.report["summary"]
    print(
        "TDC ingestion complete: "
        f"{result.row_count} source rows, "
        f"{summary['molecules_accepted']} accepted molecules, "
        f"{summary['molecules_quarantined']} quarantined. "
        f"Outputs: {args.out}"
    )


def _load_tdc_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read public source manifest {path}: {exc}") from exc
    if value.get("schema_version") != "cypshift.public_sources.v2":
        raise SystemExit("unsupported public source manifest schema")
    try:
        source = value["sources"]["tdc_admet"]
    except (KeyError, TypeError) as exc:
        raise SystemExit("public source manifest has no TDC contract") from exc
    if not isinstance(source, dict):
        raise SystemExit("TDC source contract must be an object")
    return cast(dict[str, Any], source)


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise SystemExit(f"TDC source contract {key!r} must be an object")
    return cast(dict[str, Any], item)


def _text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise SystemExit(f"TDC source contract {key!r} must be nonempty text")
    return item.strip()


if __name__ == "__main__":
    main()
