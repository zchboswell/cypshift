"""Reproduce the frozen Octant compound-level ingestion and chemistry audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from cypshift.audit import run_audit
from cypshift.benchmark import prepare_octant_inhibition

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "public_sources.json"
)


def main() -> None:
    """Prepare adapter and canonical artifacts from one frozen source file."""

    parser = argparse.ArgumentParser(
        description=(
            "Verify and ingest the frozen OpenADMET Octant compound-level "
            "CYP3A4 inhibition table."
        )
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    source_contract = _load_octant_contract(args.manifest)
    inhibition_contract = next(
        (
            entry
            for entry in source_contract["files"]
            if entry.get("path") == "inhibition.tsv"
        ),
        None,
    )
    if inhibition_contract is None:
        parser.error("public source manifest has no Octant inhibition.tsv entry")

    adapter_result = prepare_octant_inhibition(
        args.source,
        args.out / "adapter",
        source_revision=cast(str, source_contract["revision"]),
        expected_sha256=cast(str, inhibition_contract["sha256"]),
    )
    audit_result = run_audit(
        adapter_result.molecules_path,
        adapter_result.measurements_path,
        args.out / "canonical",
    )
    summary = audit_result.report["summary"]
    print(
        "Octant ingestion complete: "
        f"{adapter_result.row_count} source rows, "
        f"{summary['molecules_accepted']} accepted molecules, "
        f"{summary['molecules_quarantined']} quarantined. "
        f"Outputs: {args.out}"
    )


def _load_octant_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read public source manifest {path}: {exc}") from exc
    if value.get("schema_version") != "cypshift.public_sources.v1":
        raise SystemExit("unsupported public source manifest schema")
    try:
        source = value["sources"]["octant_cyp"]
    except (KeyError, TypeError) as exc:
        raise SystemExit("public source manifest has no Octant contract") from exc
    if not isinstance(source, dict):
        raise SystemExit("Octant source contract must be an object")
    return cast(dict[str, Any], source)


if __name__ == "__main__":
    main()
