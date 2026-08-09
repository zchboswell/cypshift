"""Concrete public-benchmark adapters used by Phase 0.5 research scripts."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from cypshift.audit import MEASUREMENT_COLUMNS, MOLECULE_INPUT_COLUMNS
from cypshift.schema import MeasurementRecord, MoleculeInput, RecordError

OCTANT_ADAPTER_SCHEMA_VERSION = "cypshift.octant_inhibition_adapter.v1"
OCTANT_DATASET_ID = (
    "openadmet/Octant_CYP_inhibition_reactivity_blog_release"
)
OCTANT_ENDPOINT = "inhibition_pIC50_active_enzyme_preincubation"
OCTANT_NADPH_CONDITION = "not_reported_active_enzyme_preincubation_30min"
OCTANT_ASSAY_WARNING = (
    "Active-enzyme preincubation may combine reversible inhibition with "
    "metabolism-dependent effects; this is not the challenge minus-NADPH "
    "direct-inhibition endpoint."
)
OCTANT_INHIBITION_COLUMNS = (
    "ocnt_batch",
    "CYP3A4_pIC50",
    "CYP3A4_pIC50_se",
    "CYP3A4_pIC50_ci_lower",
    "CYP3A4_pIC50_ci_upper",
    "slope_log2",
    "emax_log2fc",
    "activity_status",
    "rollover_status",
    "saturation_status",
    "direction",
    "drc_qc_status",
    "drc_qc_flag",
    "qc_flag_primary",
    "plate_qc_status",
    "standardized_smiles",
)


class BenchmarkDataError(ValueError):
    """Raised when public benchmark data cannot be ingested without ambiguity."""


@dataclass(frozen=True, slots=True)
class OctantAdapterResult:
    """Deterministic adapter artifacts ready for the canonical chemistry audit."""

    molecules_path: Path
    measurements_path: Path
    manifest_path: Path
    source_sha256: str
    row_count: int


def prepare_octant_inhibition(
    source_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
    expected_sha256: str,
) -> OctantAdapterResult:
    """Map the frozen Octant compound-level inhibition TSV into audit inputs."""

    if output_directory.exists():
        raise BenchmarkDataError(
            f"output path already exists: {output_directory}. "
            "Choose a new directory; benchmark adapters never overwrite artifacts."
        )
    source_revision = source_revision.strip()
    if not source_revision:
        raise BenchmarkDataError("source_revision must not be empty")
    expected_sha256 = expected_sha256.strip().lower()
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise BenchmarkDataError("expected_sha256 must be a lowercase SHA-256 digest")

    source_sha256 = _file_hash(source_path)
    if source_sha256 != expected_sha256:
        raise BenchmarkDataError(
            f"source hash mismatch for {source_path.name}: "
            f"expected {expected_sha256}, got {source_sha256}"
        )
    source_rows = _read_octant_tsv(source_path)
    _require_unique_ids(source_rows)

    molecule_rows: list[dict[str, str]] = []
    measurement_rows: list[dict[str, str]] = []
    missing_measurement_count = 0
    for source_row_number, row in enumerate(source_rows, start=2):
        molecule_id = _required_source_text(row, "ocnt_batch", source_row_number)
        raw_structure = _required_source_raw_text(
            row, "standardized_smiles", source_row_number
        )
        source_values = {
            column: row[column]
            for column in OCTANT_INHIBITION_COLUMNS
            if column not in {"ocnt_batch", "standardized_smiles"}
        }
        has_measurement = bool(row["CYP3A4_pIC50"].strip())
        if not has_measurement and any(
            row[field].strip()
            for field in (
                "CYP3A4_pIC50_se",
                "CYP3A4_pIC50_ci_lower",
                "CYP3A4_pIC50_ci_upper",
            )
        ):
            raise BenchmarkDataError(
                f"Octant inhibition row {source_row_number} has uncertainty "
                "values but no CYP3A4_pIC50"
            )
        provenance_base = {
            "dataset_id": OCTANT_DATASET_ID,
            "revision": source_revision,
            "source_file": source_path.name,
            "source_row": source_row_number,
            "source_sha256": source_sha256,
        }
        molecule = MoleculeInput.from_mapping(
            {
                "molecule_id": molecule_id,
                "structure": raw_structure,
                "structure_format": "smiles",
                "source": OCTANT_DATASET_ID,
                "provenance": _compact_json(
                    {
                        **provenance_base,
                        "measurement_status": (
                            "present" if has_measurement else "missing_source_pIC50"
                        ),
                        "source_values": source_values,
                        "source_structure_field": "standardized_smiles",
                    }
                ),
            }
        )
        molecule_rows.append(
            {
                "molecule_id": molecule.molecule_id,
                "structure": molecule.structure,
                "structure_format": molecule.structure_format,
                "source": molecule.source,
                "provenance": molecule.provenance,
            }
        )

        if not has_measurement:
            missing_measurement_count += 1
            continue

        quality = ";".join(
            f"{field}={_required_source_text(row, field, source_row_number)}"
            for field in (
                "drc_qc_status",
                "drc_qc_flag",
                "qc_flag_primary",
                "plate_qc_status",
            )
        )
        measurement_mapping = {
            "measurement_id": f"octant_cyp3a4_inhibition:{molecule_id}",
            "molecule_id": molecule_id,
            "endpoint": OCTANT_ENDPOINT,
            "isoform": "CYP3A4",
            "nadph_condition": OCTANT_NADPH_CONDITION,
            "probe": "DBOMF",
            "readout": "fluorescence",
            "value": _required_source_text(
                row, "CYP3A4_pIC50", source_row_number
            ),
            "lower_bound": _required_source_text(
                row, "CYP3A4_pIC50_ci_lower", source_row_number
            ),
            "upper_bound": _required_source_text(
                row, "CYP3A4_pIC50_ci_upper", source_row_number
            ),
            "censoring": "none",
            "unit": "pIC50",
            "quality": quality,
            "source": OCTANT_DATASET_ID,
            "provenance": _compact_json(
                {
                    **provenance_base,
                    "assay_warning": OCTANT_ASSAY_WARNING,
                    "source_values": source_values,
                }
            ),
        }
        try:
            measurement = MeasurementRecord.from_mapping(measurement_mapping)
        except RecordError as exc:
            raise BenchmarkDataError(
                f"invalid Octant inhibition row {source_row_number}: {exc}"
            ) from exc
        measurement_rows.append(
            {
                column: _csv_value(measurement.to_dict()[column])
                for column in MEASUREMENT_COLUMNS
            }
        )

    molecule_bytes = _csv_bytes(MOLECULE_INPUT_COLUMNS, molecule_rows)
    measurement_bytes = _csv_bytes(MEASUREMENT_COLUMNS, measurement_rows)
    manifest = {
        "schema_version": OCTANT_ADAPTER_SCHEMA_VERSION,
        "dataset_id": OCTANT_DATASET_ID,
        "source_revision": source_revision,
        "source_file": source_path.name,
        "source_sha256": source_sha256,
        "source_rows": len(source_rows),
        "molecule_rows": len(molecule_rows),
        "measurement_rows": len(measurement_rows),
        "measurement_omissions": {
            "missing_source_CYP3A4_pIC50": missing_measurement_count,
        },
        "assay_context": {
            "endpoint": OCTANT_ENDPOINT,
            "isoform": "CYP3A4",
            "nadph_condition": OCTANT_NADPH_CONDITION,
            "preincubation": "30 minutes with active CYP3A4",
            "probe": "DBOMF",
            "readout": "fluorescence",
            "warning": OCTANT_ASSAY_WARNING,
        },
        "outputs": {
            "molecules_input.csv": sha256(molecule_bytes).hexdigest(),
            "measurements_input.csv": sha256(measurement_bytes).hexdigest(),
        },
        "deterministic": True,
    }
    manifest_bytes = _json_bytes(manifest)

    output_directory.mkdir(parents=True)
    molecules_path = output_directory / "molecules_input.csv"
    measurements_path = output_directory / "measurements_input.csv"
    manifest_path = output_directory / "adapter_manifest.json"
    _write_new(molecules_path, molecule_bytes)
    _write_new(measurements_path, measurement_bytes)
    _write_new(manifest_path, manifest_bytes)
    return OctantAdapterResult(
        molecules_path=molecules_path,
        measurements_path=measurements_path,
        manifest_path=manifest_path,
        source_sha256=source_sha256,
        row_count=len(source_rows),
    )


def _read_octant_tsv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            actual_columns = tuple(reader.fieldnames or ())
            if actual_columns != OCTANT_INHIBITION_COLUMNS:
                raise BenchmarkDataError(
                    f"{path.name} columns do not match the frozen Octant adapter. "
                    f"Expected {list(OCTANT_INHIBITION_COLUMNS)!r}; "
                    f"got {list(actual_columns)!r}."
                )
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise BenchmarkDataError(
                        f"{path.name} row {reader.line_num} has the wrong "
                        "number of fields"
                    )
                rows.append(
                    {
                        column: cast(str, row[column])
                        for column in OCTANT_INHIBITION_COLUMNS
                    }
                )
    except OSError as exc:
        raise BenchmarkDataError(f"cannot read {path}: {exc}") from exc
    if not rows:
        raise BenchmarkDataError(f"{path.name} contains no data rows")
    return rows


def _require_unique_ids(rows: Sequence[Mapping[str, str]]) -> None:
    counts = Counter(row["ocnt_batch"].strip() for row in rows)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        raise BenchmarkDataError(
            "duplicate Octant ocnt_batch values: " + ", ".join(duplicates)
        )


def _required_source_text(
    row: Mapping[str, str], field: str, source_row_number: int
) -> str:
    value = row[field].strip()
    if not value:
        raise BenchmarkDataError(
            f"Octant inhibition row {source_row_number} has empty {field}"
        )
    return value


def _required_source_raw_text(
    row: Mapping[str, str], field: str, source_row_number: int
) -> str:
    value = row[field]
    if not value or not value.strip():
        raise BenchmarkDataError(
            f"Octant inhibition row {source_row_number} has empty {field}"
        )
    return value


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BenchmarkDataError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _csv_bytes(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise BenchmarkDataError(f"refusing to overwrite {path}") from exc


__all__ = [
    "BenchmarkDataError",
    "OCTANT_ADAPTER_SCHEMA_VERSION",
    "OCTANT_ASSAY_WARNING",
    "OCTANT_DATASET_ID",
    "OCTANT_ENDPOINT",
    "OCTANT_INHIBITION_COLUMNS",
    "OCTANT_NADPH_CONDITION",
    "OctantAdapterResult",
    "prepare_octant_inhibition",
]
