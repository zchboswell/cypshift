"""Strict local upload checks for the released CYP 2026 direct and TDI tracks.

The Space permits reordered/extra columns; this release validator deliberately
requires canonical serialization and exact blinded-test identities as well.
It performs no network calls, prediction modifications, or portal operations.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import statistics
from dataclasses import dataclass
from typing import Literal

Track = Literal["direct", "tdi"]
SPACE_REVISION = "453a39a27c9671aa6790bbc2d618606a9cc556c3"
IDENTIFIERS = ("SMILES", "Molecule_Name")
DIRECT_COLUMNS = tuple(
    f"{endpoint}_pIC50_direct_inhibition"
    for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
)
TDI_COLUMNS = ("CYP2D6_is_TDI", "CYP3A4_is_TDI")


@dataclass(frozen=True)
class SubmissionReceipt:
    track: Track
    rows: int
    predictions: int
    test_sha256: str
    submission_sha256: str
    standard_deviations: dict[str, float]
    positive_counts: dict[str, int]
    space_revision: str = SPACE_REVISION


def _read(raw: bytes) -> tuple[list[str], list[list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8")), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Invalid UTF-8 CSV") from exc
    if not rows or len(set(rows[0])) != len(rows[0]):
        raise ValueError("Empty CSV or duplicate columns")
    if any(len(row) != len(rows[0]) for row in rows[1:]):
        raise ValueError("Malformed CSV row")
    return rows[0], rows[1:]


def validate_submission(
    test_raw: bytes,
    submission_raw: bytes,
    track: Track,
    *,
    expected_test_sha256: str,
    expected_rows: int = 750,
) -> SubmissionReceipt:
    """Fail closed on identity, schema, missingness, and current variation rules."""
    test_sha = hashlib.sha256(test_raw).hexdigest()
    if test_sha != expected_test_sha256:
        raise ValueError("Blinded-test receipt differs")
    test_columns, test = _read(test_raw)
    columns, submitted = _read(submission_raw)
    if track not in ("direct", "tdi"):
        raise ValueError("Unknown track")
    endpoints = DIRECT_COLUMNS if track == "direct" else TDI_COLUMNS
    if set(test_columns) != set(IDENTIFIERS):
        raise ValueError("Unexpected blinded-test columns")
    if tuple(columns) != IDENTIFIERS + endpoints:
        raise ValueError("Submission columns or order differ")
    if (
        expected_rows < 2
        or len(test) != expected_rows
        or len(submitted) != expected_rows
    ):
        raise ValueError("Submission row count differs")
    identities = [
        tuple(row[test_columns.index(c)] for c in IDENTIFIERS) for row in test
    ]
    if any(not value or value != value.strip() for row in identities for value in row):
        raise ValueError("Empty or padded identity")
    if len({row[1] for row in identities}) != expected_rows:
        raise ValueError("Duplicate molecule identity")
    if [tuple(row[:2]) for row in submitted] != identities:
        raise ValueError("Submission identity or row order differs")
    deviations: dict[str, float] = {}
    positives: dict[str, int] = {}
    for index, endpoint in enumerate(endpoints, 2):
        values: list[float] = []
        for row in submitted:
            cell = row[index]
            if not cell or cell != cell.strip():
                raise ValueError(f"Missing or padded prediction: {endpoint}")
            # Canonical numeric 0/1 avoids ambiguous mixed CSV boolean inference.
            if track == "tdi" and cell not in ("0", "1"):
                raise ValueError(f"TDI requires canonical 0/1: {endpoint}")
            try:
                value = float(cell)
            except ValueError as exc:
                raise ValueError(f"Nonnumeric prediction: {endpoint}") from exc
            if not math.isfinite(value):
                raise ValueError(f"Nonfinite prediction: {endpoint}")
            values.append(value)
        if len(set(values)) < 2:
            raise ValueError(f"Constant predictions: {endpoint}")
        if track == "direct":
            deviation = statistics.stdev(values)  # pandas std uses ddof=1.
            if not math.isfinite(deviation) or deviation < 0.01:
                raise ValueError(f"Prediction sample STD below 0.01: {endpoint}")
            deviations[endpoint] = deviation
        else:
            positives[endpoint] = int(sum(values))
    return SubmissionReceipt(
        track,
        expected_rows,
        expected_rows * len(endpoints),
        test_sha,
        hashlib.sha256(submission_raw).hexdigest(),
        deviations,
        positives,
    )
