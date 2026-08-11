"""Dataset loading and chemistry-audit artifact generation."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from cypshift.chemistry import STANDARDIZATION_VERSION, audit_molecules
from cypshift.schema import (
    MeasurementRecord,
    MoleculeInput,
    MoleculeRecord,
    MoleculeStatus,
)

AUDIT_SCHEMA_VERSION = "cypshift.audit.v1"
MOLECULE_SCHEMA_VERSION = "cypshift.molecules.v1"
MEASUREMENT_SCHEMA_VERSION = "cypshift.measurements.v1"

MOLECULE_INPUT_COLUMNS = (
    "molecule_id",
    "structure",
    "structure_format",
    "source",
    "provenance",
)
MEASUREMENT_COLUMNS = (
    "measurement_id",
    "molecule_id",
    "endpoint",
    "isoform",
    "nadph_condition",
    "probe",
    "readout",
    "value",
    "lower_bound",
    "upper_bound",
    "censoring",
    "unit",
    "quality",
    "source",
    "provenance",
)
MOLECULE_OUTPUT_COLUMNS = (
    "molecule_id",
    "raw_structure",
    "structure_format",
    "standardized_structure",
    "standardized_structure_hash",
    "status",
    "stereochemistry_status",
    "input_fragments",
    "standardization_changed",
    "duplicate_of",
    "warnings",
    "standardization_version",
    "source",
    "provenance",
)


class AuditError(ValueError):
    """Raised when the audit cannot safely produce canonical artifacts."""


@dataclass(frozen=True, slots=True)
class AuditResult:
    """In-memory result and paths from one completed audit."""

    report: dict[str, Any]
    molecules: tuple[MoleculeRecord, ...]
    measurements: tuple[MeasurementRecord, ...]
    output_directory: Path


def run_audit(
    molecules_path: Path, measurements_path: Path, output_directory: Path
) -> AuditResult:
    """Validate inputs and write a new, non-overwriting canonical audit."""

    if output_directory.exists():
        raise AuditError(
            f"output path already exists: {output_directory}. "
            "Choose a new directory; cypshift never overwrites run artifacts."
        )

    molecule_inputs = _load_molecules(molecules_path)
    measurements = _load_measurements(measurements_path)
    _validate_unique_ids(
        (molecule.molecule_id for molecule in molecule_inputs), "molecule_id"
    )
    _validate_unique_ids(
        (measurement.measurement_id for measurement in measurements),
        "measurement_id",
    )
    molecule_ids = {molecule.molecule_id for molecule in molecule_inputs}
    unknown_ids = sorted(
        {
            measurement.molecule_id
            for measurement in measurements
            if measurement.molecule_id not in molecule_ids
        }
    )
    if unknown_ids:
        raise AuditError(
            "measurements reference unknown molecule_id values: "
            + ", ".join(unknown_ids)
        )

    molecules = audit_molecules(sorted(molecule_inputs, key=lambda row: row.molecule_id))
    measurements = sorted(measurements, key=lambda row: row.measurement_id)
    report = _build_report(
        molecules_path=molecules_path,
        measurements_path=measurements_path,
        molecules=molecules,
        measurements=measurements,
    )

    output_directory.mkdir(parents=True)
    _write_molecules(output_directory / "molecules.csv", molecules)
    _write_measurements(output_directory / "measurements.csv", measurements)
    _write_json(output_directory / "audit.json", report)
    return AuditResult(
        report=report,
        molecules=tuple(molecules),
        measurements=tuple(measurements),
        output_directory=output_directory,
    )


def _load_molecules(path: Path) -> list[MoleculeInput]:
    return [
        MoleculeInput.from_mapping(row)
        for row in _read_csv(path, MOLECULE_INPUT_COLUMNS)
    ]


def _load_measurements(path: Path) -> list[MeasurementRecord]:
    return [
        MeasurementRecord.from_mapping(row)
        for row in _read_csv(path, MEASUREMENT_COLUMNS)
    ]


def _read_csv(path: Path, expected_columns: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            actual_columns = tuple(reader.fieldnames or ())
            if actual_columns != tuple(expected_columns):
                raise AuditError(
                    f"{path.name} columns do not match the current adapter. "
                    f"Expected {list(expected_columns)!r}; got {list(actual_columns)!r}."
                )
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise AuditError(
                        f"{path.name} row {reader.line_num} has the wrong "
                        "number of fields"
                    )
                rows.append(
                    {
                        column: cast(str, row[column])
                        for column in expected_columns
                    }
                )
    except OSError as exc:
        raise AuditError(f"cannot read {path}: {exc}") from exc
    if not rows:
        raise AuditError(f"{path.name} contains no data rows")
    return rows


def _validate_unique_ids(values: Iterable[str], field: str) -> None:
    counts = Counter(values)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        raise AuditError(f"duplicate {field} values: {', '.join(duplicates)}")


def _build_report(
    *,
    molecules_path: Path,
    measurements_path: Path,
    molecules: Sequence[MoleculeRecord],
    measurements: Sequence[MeasurementRecord],
) -> dict[str, Any]:
    warning_counts = Counter(
        warning for molecule in molecules for warning in molecule.warnings
    )
    quarantined_ids = {
        molecule.molecule_id
        for molecule in molecules
        if molecule.status is MoleculeStatus.QUARANTINED
    }
    assay_counts = Counter(
        (
            measurement.endpoint,
            measurement.isoform,
            measurement.nadph_condition,
            measurement.probe,
            measurement.readout,
        )
        for measurement in measurements
    )
    issues = [
        {
            "molecule_id": molecule.molecule_id,
            "status": molecule.status.value,
            "warnings": list(molecule.warnings),
        }
        for molecule in molecules
        if molecule.warnings
    ]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "canonical_schema_versions": {
            "molecules": MOLECULE_SCHEMA_VERSION,
            "measurements": MEASUREMENT_SCHEMA_VERSION,
        },
        "standardization_version": STANDARDIZATION_VERSION,
        "inputs": {
            "molecules": {
                "name": molecules_path.name,
                "sha256": _file_hash(molecules_path),
            },
            "measurements": {
                "name": measurements_path.name,
                "sha256": _file_hash(measurements_path),
            },
        },
        "summary": {
            "molecules_total": len(molecules),
            "molecules_accepted": sum(
                molecule.status is MoleculeStatus.ACCEPTED
                for molecule in molecules
            ),
            "molecules_quarantined": len(quarantined_ids),
            "standardization_changes": sum(
                molecule.standardization_changed for molecule in molecules
            ),
            "standardized_duplicates": sum(
                molecule.duplicate_of is not None for molecule in molecules
            ),
            "measurements_total": len(measurements),
            "measurements_linked_to_quarantined_molecules": sum(
                measurement.molecule_id in quarantined_ids
                for measurement in measurements
            ),
            "warning_counts": dict(sorted(warning_counts.items())),
        },
        "assay_context_counts": [
            {
                "endpoint": context[0],
                "isoform": context[1],
                "nadph_condition": context[2],
                "probe": context[3],
                "readout": context[4],
                "count": count,
            }
            for context, count in sorted(assay_counts.items())
        ],
        "issues": issues,
    }


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise AuditError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _write_molecules(path: Path, molecules: Sequence[MoleculeRecord]) -> None:
    rows: list[dict[str, str]] = []
    for molecule in molecules:
        record = molecule.to_dict()
        rows.append(
            {
                column: _csv_value(record[column])
                for column in MOLECULE_OUTPUT_COLUMNS
            }
        )
    _write_csv(path, MOLECULE_OUTPUT_COLUMNS, rows)


def _write_measurements(
    path: Path, measurements: Sequence[MeasurementRecord]
) -> None:
    rows = [
        {column: _csv_value(measurement.to_dict()[column]) for column in MEASUREMENT_COLUMNS}
        for measurement in measurements
    ]
    _write_csv(path, MEASUREMENT_COLUMNS, rows)


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


__all__ = ["AuditError", "AuditResult", "run_audit"]
