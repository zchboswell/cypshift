"""Concrete adapter for the frozen TDC CYP ADMET benchmark archive."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from cypshift.audit import MEASUREMENT_COLUMNS, MOLECULE_INPUT_COLUMNS
from cypshift.schema import MeasurementRecord, MoleculeInput, RecordError

TDC_ADAPTER_SCHEMA_VERSION = "cypshift.tdc_admet_adapter.v1"
TDC_DATASET_ID = "TDC/ADMET_Group"
TDC_ENDPOINT = "binary_inhibition_veith"
TDC_MEMBER_COLUMNS = ("Drug_ID", "Drug", "Y")
TDC_TASKS = {
    "cyp2c9_veith": "CYP2C9",
    "cyp2d6_veith": "CYP2D6",
    "cyp3a4_veith": "CYP3A4",
}
TDC_PARTITIONS = ("train_val", "test")
TDC_SPLIT_COLUMNS = ("molecule_id", "task", "partition", "source_row")


class TdcDataError(ValueError):
    """Raised when the frozen TDC archive violates its source contract."""


@dataclass(frozen=True, slots=True)
class TdcAdapterResult:
    """Deterministic TDC adapter artifacts ready for the chemistry audit."""

    molecules_path: Path
    measurements_path: Path
    split_path: Path
    manifest_path: Path
    source_sha256: str
    row_count: int


def prepare_tdc_admet(
    archive_path: Path,
    output_directory: Path,
    *,
    expected_archive_sha256: str,
    task_contracts: Mapping[str, Any],
) -> TdcAdapterResult:
    """Map three frozen TDC CYP tasks while preserving official partitions."""

    if output_directory.exists():
        raise TdcDataError(
            f"output path already exists: {output_directory}. "
            "Choose a new directory; benchmark adapters never overwrite artifacts."
        )
    expected_archive_sha256 = _digest(expected_archive_sha256, "archive")
    source_sha256 = _file_hash(archive_path)
    if source_sha256 != expected_archive_sha256:
        raise TdcDataError(
            f"source hash mismatch for {archive_path.name}: "
            f"expected {expected_archive_sha256}, got {source_sha256}"
        )

    molecule_rows: list[dict[str, str]] = []
    measurement_rows: list[dict[str, str]] = []
    split_rows: list[dict[str, str]] = []
    observed_contract: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for task, isoform in TDC_TASKS.items():
                task_contract = _mapping(task_contracts, task)
                observed_contract[task] = {}
                for partition in TDC_PARTITIONS:
                    partition_contract = _mapping(task_contract, partition)
                    member_path = _text(partition_contract, "path")
                    expected_member_hash = _digest(
                        _text(partition_contract, "sha256"), member_path
                    )
                    try:
                        member_bytes = archive.read(member_path)
                    except KeyError as exc:
                        raise TdcDataError(
                            f"TDC archive has no contracted member {member_path}"
                        ) from exc
                    member_hash = sha256(member_bytes).hexdigest()
                    if member_hash != expected_member_hash:
                        raise TdcDataError(
                            f"member hash mismatch for {member_path}: expected "
                            f"{expected_member_hash}, got {member_hash}"
                        )
                    rows = _read_member(member_path, member_bytes)
                    _validate_partition(rows, partition_contract, member_path)
                    counts = _append_partition(
                        rows,
                        task=task,
                        isoform=isoform,
                        partition=partition,
                        member_path=member_path,
                        member_hash=member_hash,
                        archive_hash=source_sha256,
                        molecule_rows=molecule_rows,
                        measurement_rows=measurement_rows,
                        split_rows=split_rows,
                    )
                    observed_contract[task][partition] = {
                        "path": member_path,
                        "sha256": member_hash,
                        **counts,
                    }
    except (OSError, zipfile.BadZipFile) as exc:
        raise TdcDataError(f"cannot read TDC archive {archive_path}: {exc}") from exc

    molecule_bytes = _csv_bytes(MOLECULE_INPUT_COLUMNS, molecule_rows)
    measurement_bytes = _csv_bytes(MEASUREMENT_COLUMNS, measurement_rows)
    split_bytes = _csv_bytes(TDC_SPLIT_COLUMNS, split_rows)
    manifest = {
        "schema_version": TDC_ADAPTER_SCHEMA_VERSION,
        "dataset_id": TDC_DATASET_ID,
        "source_file": archive_path.name,
        "source_sha256": source_sha256,
        "task_order": list(TDC_TASKS),
        "partition_order": list(TDC_PARTITIONS),
        "tasks": observed_contract,
        "molecule_rows": len(molecule_rows),
        "measurement_rows": len(measurement_rows),
        "split_rows": len(split_rows),
        "assay_context": {
            "endpoint": TDC_ENDPOINT,
            "nadph_condition": "not_reported",
            "probe": "not_reported",
            "readout": "binary_label",
            "warning": (
                "The benchmark archive does not encode assay condition, probe, "
                "or readout fields; do not infer equivalence to another assay."
            ),
        },
        "selection_policy": (
            "Candidate selection is restricted to train_val. Public test labels "
            "are ingested for alignment but are not scored by this adapter."
        ),
        "outputs": {
            "molecules_input.csv": sha256(molecule_bytes).hexdigest(),
            "measurements_input.csv": sha256(measurement_bytes).hexdigest(),
            "official_split.csv": sha256(split_bytes).hexdigest(),
        },
        "deterministic": True,
    }
    manifest_bytes = _json_bytes(manifest)

    output_directory.mkdir(parents=True)
    molecules_path = output_directory / "molecules_input.csv"
    measurements_path = output_directory / "measurements_input.csv"
    split_path = output_directory / "official_split.csv"
    manifest_path = output_directory / "adapter_manifest.json"
    _write_new(molecules_path, molecule_bytes)
    _write_new(measurements_path, measurement_bytes)
    _write_new(split_path, split_bytes)
    _write_new(manifest_path, manifest_bytes)
    return TdcAdapterResult(
        molecules_path=molecules_path,
        measurements_path=measurements_path,
        split_path=split_path,
        manifest_path=manifest_path,
        source_sha256=source_sha256,
        row_count=len(molecule_rows),
    )


def _append_partition(
    rows: Sequence[Mapping[str, str]],
    *,
    task: str,
    isoform: str,
    partition: str,
    member_path: str,
    member_hash: str,
    archive_hash: str,
    molecule_rows: list[dict[str, str]],
    measurement_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
) -> dict[str, int]:
    negative = 0
    positive = 0
    for source_row, row in enumerate(rows, start=2):
        source_id = _required_row_text(row, "Drug_ID", member_path, source_row)
        raw_structure = _required_row_raw_text(row, "Drug", member_path, source_row)
        label = _required_row_text(row, "Y", member_path, source_row)
        if label not in {"0", "1"}:
            raise TdcDataError(
                f"{member_path} row {source_row} has non-binary Y {label!r}"
            )
        negative += label == "0"
        positive += label == "1"
        molecule_id = f"tdc:{task}:{partition}:{source_row - 1:05d}"
        provenance = _compact_json(
            {
                "archive_sha256": archive_hash,
                "dataset_id": TDC_DATASET_ID,
                "member_path": member_path,
                "member_sha256": member_hash,
                "official_partition": partition,
                "source_drug_id": source_id,
                "source_drug_id_raw": row["Drug_ID"],
                "source_label_raw": row["Y"],
                "source_row": source_row,
                "task": task,
            }
        )
        molecule = MoleculeInput.from_mapping(
            {
                "molecule_id": molecule_id,
                "structure": raw_structure,
                "structure_format": "smiles",
                "source": f"{TDC_DATASET_ID}/{task}",
                "provenance": provenance,
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
        try:
            measurement = MeasurementRecord.from_mapping(
                {
                    "measurement_id": f"{molecule_id}:label",
                    "molecule_id": molecule_id,
                    "endpoint": TDC_ENDPOINT,
                    "isoform": isoform,
                    "nadph_condition": "not_reported",
                    "probe": "not_reported",
                    "readout": "binary_label",
                    "value": label,
                    "lower_bound": "",
                    "upper_bound": "",
                    "censoring": "none",
                    "unit": "binary_label",
                    "quality": "official_source_label",
                    "source": f"{TDC_DATASET_ID}/{task}",
                    "provenance": provenance,
                }
            )
        except RecordError as exc:
            raise TdcDataError(
                f"invalid TDC row {member_path}:{source_row}: {exc}"
            ) from exc
        measurement_rows.append(
            {
                column: _csv_value(measurement.to_dict()[column])
                for column in MEASUREMENT_COLUMNS
            }
        )
        split_rows.append(
            {
                "molecule_id": molecule_id,
                "task": task,
                "partition": partition,
                "source_row": str(source_row),
            }
        )
    return {"rows": len(rows), "negative": negative, "positive": positive}


def _read_member(path: str, content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TdcDataError(f"{path} is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    actual_columns = tuple(reader.fieldnames or ())
    if actual_columns != TDC_MEMBER_COLUMNS:
        raise TdcDataError(
            f"{path} columns do not match the frozen TDC adapter. Expected "
            f"{list(TDC_MEMBER_COLUMNS)!r}; got {list(actual_columns)!r}."
        )
    rows = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise TdcDataError(
                f"{path} row {reader.line_num} has the wrong number of fields"
            )
        rows.append(
            {column: cast(str, row[column]) for column in TDC_MEMBER_COLUMNS}
        )
    if not rows:
        raise TdcDataError(f"{path} contains no data rows")
    return rows


def _validate_partition(
    rows: Sequence[Mapping[str, str]], contract: Mapping[str, Any], path: str
) -> None:
    expected_rows = _integer(contract, "rows")
    expected_negative = _integer(contract, "negative")
    expected_positive = _integer(contract, "positive")
    invalid_labels = sorted(
        {row["Y"] for row in rows if row["Y"].strip() not in {"0", "1"}}
    )
    if invalid_labels:
        raise TdcDataError(
            f"{path} has non-binary Y values: {', '.join(invalid_labels)}"
        )
    observed_negative = sum(row["Y"].strip() == "0" for row in rows)
    observed_positive = sum(row["Y"].strip() == "1" for row in rows)
    if len(rows) != expected_rows:
        raise TdcDataError(
            f"row-count mismatch for {path}: expected {expected_rows}, got {len(rows)}"
        )
    if (observed_negative, observed_positive) != (
        expected_negative,
        expected_positive,
    ):
        raise TdcDataError(
            f"label-count mismatch for {path}: expected "
            f"({expected_negative}, {expected_positive}), got "
            f"({observed_negative}, {observed_positive})"
        )


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise TdcDataError(f"TDC source contract {key!r} must be an object")
    return item


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise TdcDataError(f"TDC source contract {key!r} must be nonempty text")
    return item.strip()


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool) or item < 0:
        raise TdcDataError(
            f"TDC source contract {key!r} must be a nonnegative integer"
        )
    return item


def _required_row_text(
    row: Mapping[str, str], field: str, path: str, source_row: int
) -> str:
    value = row[field].strip()
    if not value:
        raise TdcDataError(f"{path} row {source_row} has empty {field}")
    return value


def _required_row_raw_text(
    row: Mapping[str, str], field: str, path: str, source_row: int
) -> str:
    value = row[field]
    if not value or not value.strip():
        raise TdcDataError(f"{path} row {source_row} has empty {field}")
    return value


def _digest(value: str, label: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise TdcDataError(f"{label} SHA-256 must be a lowercase digest")
    return digest


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise TdcDataError(f"cannot hash {path}: {exc}") from exc
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
        raise TdcDataError(f"refusing to overwrite {path}") from exc


__all__ = [
    "TDC_ADAPTER_SCHEMA_VERSION",
    "TDC_DATASET_ID",
    "TDC_ENDPOINT",
    "TDC_MEMBER_COLUMNS",
    "TDC_PARTITIONS",
    "TDC_SPLIT_COLUMNS",
    "TDC_TASKS",
    "TdcAdapterResult",
    "TdcDataError",
    "prepare_tdc_admet",
]
