#!/usr/bin/env python3
"""Validate one direct-track CSV against the pinned blinded-test identity order."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "benchmarks/openadmet_cyp_2026/direct_maplight_deployment_contract.json"
)
VALIDATOR = Path(__file__).resolve()
SCHEMA = "cypshift.openadmet_cyp_2026.direct_maplight_deployment.v1"


class DirectSubmissionError(ValueError):
    """The deployment contract or submitted CSV is invalid."""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Exact direct-submission validation counts and receipt."""

    rows: int
    finite_predictions: int
    submission_sha256: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular_bytes(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise DirectSubmissionError(f"{label} must be a regular non-symlink file")
    for parent in path.absolute().parents:
        if parent == parent.parent:
            break
        if parent.is_symlink():
            raise DirectSubmissionError(f"{label} has a symlinked ancestor")
    return path.read_bytes()


def _load_json(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise DirectSubmissionError(f"{label} has a duplicate JSON key")
            value[key] = item
        return value

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DirectSubmissionError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise DirectSubmissionError(f"{label} root must be an object")
    return value


def load_frozen_contract(expected_sha256: str) -> tuple[dict[str, Any], str]:
    """Load exact reviewed contract bytes and bind this validator source."""

    raw = _regular_bytes(CONTRACT, "deployment contract")
    observed = _sha256(raw)
    if observed != expected_sha256:
        raise DirectSubmissionError("deployment contract SHA-256 differs")
    contract = _load_json(raw, "deployment contract")
    implementation = contract.get("implementation")
    if (
        contract.get("schema_version") != SCHEMA
        or not isinstance(implementation, Mapping)
        or implementation.get("validator_path")
        != "scripts/validate_openadmet_direct_submission.py"
        or implementation.get("validator_sha256")
        != _sha256(_regular_bytes(VALIDATOR, "validator source"))
    ):
        raise DirectSubmissionError("deployment contract or validator receipt differs")
    return contract, observed


def _csv_rows(raw: bytes, columns: Sequence[str], label: str) -> list[list[str]]:
    try:
        records = list(
            csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
        )
    except (UnicodeError, csv.Error) as exc:
        raise DirectSubmissionError(f"{label} is not valid UTF-8 RFC4180 CSV") from exc
    if not records or records[0] != list(columns):
        raise DirectSubmissionError(f"{label} columns or order differ")
    rows = records[1:]
    if any(len(row) != len(columns) for row in rows):
        raise DirectSubmissionError(f"{label} has a malformed row")
    return rows


def validate_submission_bytes(
    test_raw: bytes,
    submission_raw: bytes,
    contract: Mapping[str, Any],
    *,
    verify_test_receipt: bool = True,
) -> ValidationResult:
    """Validate exact schema, identity order, and all finite predictions."""

    test = contract["test"]
    submission = contract["submission"]
    test_columns = tuple(test["columns"])
    output_columns = tuple(submission["columns"])
    if verify_test_receipt and _sha256(test_raw) != test["source_sha256"]:
        raise DirectSubmissionError("blinded-test CSV receipt differs")
    test_rows = _csv_rows(test_raw, test_columns, "blinded-test CSV")
    output_rows = _csv_rows(submission_raw, output_columns, "submission CSV")
    expected_rows = int(submission["rows"])
    if len(test_rows) != expected_rows or len(output_rows) != expected_rows:
        raise DirectSubmissionError("direct submission must contain exactly 750 rows")
    test_index = {name: index for index, name in enumerate(test_columns)}
    output_index = {name: index for index, name in enumerate(output_columns)}
    identities = [
        (row[test_index["SMILES"]], row[test_index["Molecule_Name"]])
        for row in test_rows
    ]
    if len({name for _, name in identities}) != expected_rows:
        raise DirectSubmissionError("blinded-test Molecule_Name values are not unique")
    observed_identities = [
        (row[output_index["SMILES"]], row[output_index["Molecule_Name"]])
        for row in output_rows
    ]
    if observed_identities != identities:
        raise DirectSubmissionError("submission identity or row order differs")
    prediction_columns = output_columns[2:]
    finite = 0
    for row in output_rows:
        for name in prediction_columns:
            text = row[output_index[name]]
            try:
                value = float(text)
            except ValueError as exc:
                raise DirectSubmissionError(
                    f"{name} contains a nonnumeric value"
                ) from exc
            if text == "" or text != text.strip() or not math.isfinite(value):
                raise DirectSubmissionError(f"{name} contains a nonfinite value")
            finite += 1
    if finite != int(submission["finite_predictions"]):
        raise DirectSubmissionError("submission must contain 3000 finite predictions")
    return ValidationResult(expected_rows, finite, _sha256(submission_raw))


def validate_submission(
    test_path: Path, submission_path: Path, expected_contract_sha256: str
) -> ValidationResult:
    """Validate two regular files using the exact frozen production contract."""

    contract, _ = load_frozen_contract(expected_contract_sha256)
    return validate_submission_bytes(
        _regular_bytes(test_path, "blinded-test CSV"),
        _regular_bytes(submission_path, "submission CSV"),
        contract,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-csv", type=Path, required=True)
    parser.add_argument("--submission-csv", type=Path, required=True)
    parser.add_argument("--expected-contract-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = validate_submission(
            args.test_csv, args.submission_csv, args.expected_contract_sha256
        )
    except DirectSubmissionError as exc:
        print(f"direct submission validation failed: {exc}")
        return 1
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
