"""Frozen public-benchmark split construction and leakage audits."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from rdkit import Chem, rdBase

from cypshift.baseline import BaselineError, load_audited_dataset
from cypshift.metrics import AUPRC_DIRECTION
from cypshift.schema import MoleculeRecord, MoleculeStatus
from cypshift.tdc import TDC_SPLIT_COLUMNS, TDC_TASKS

OCTANT_GROUPED_SPLIT_SCHEMA_VERSION = "cypshift.octant_grouped_split.v1"
TDC_SPLIT_AUDIT_SCHEMA_VERSION = "cypshift.tdc_split_audit.v1"
OCTANT_SPLIT_COLUMNS = (
    "molecule_id",
    "standardized_structure_hash",
    "group_type",
    "group_hash",
    "outer_fold",
    "outer_partition",
    "inner_fold",
    "has_measurement",
)
TDC_EXCLUSION_COLUMNS = (
    "task",
    "molecule_id",
    "standardized_structure_hash",
    "reason",
)


class ValidationDataError(ValueError):
    """Raised when a benchmark split cannot be frozen without ambiguity."""


@dataclass(frozen=True, slots=True)
class OctantSplitResult:
    """Paths and counts for the deterministic grouped Octant split."""

    split_path: Path
    manifest_path: Path
    row_count: int
    group_count: int


@dataclass(frozen=True, slots=True)
class TdcSplitAuditResult:
    """Paths for official and strict TDC split-integrity evidence."""

    report_path: Path
    exclusions_path: Path
    exclusion_count: int


def freeze_octant_grouped_split(
    canonical_directory: Path,
    output_directory: Path,
    *,
    seed: int = 20260809,
) -> OctantSplitResult:
    """Freeze one scaffold-grouped outer fold and four grouped inner folds."""

    if output_directory.exists():
        raise ValidationDataError(
            f"output path already exists: {output_directory}. "
            "Validation artifacts are immutable."
        )
    dataset = _load_dataset(canonical_directory)
    measurement_counts = Counter(
        measurement.molecule_id for measurement in dataset.measurements
    )
    repeated_measurements = sorted(
        molecule_id
        for molecule_id, count in measurement_counts.items()
        if count > 1
    )
    if repeated_measurements:
        raise ValidationDataError(
            "Octant grouped split expects at most one measurement per molecule: "
            + ", ".join(repeated_measurements)
        )

    group_details: dict[str, tuple[str, str]] = {}
    members_by_group: dict[str, list[str]] = defaultdict(list)
    molecules_by_id: dict[str, MoleculeRecord] = {}
    for molecule in dataset.molecules:
        if molecule.status is not MoleculeStatus.ACCEPTED:
            raise ValidationDataError(
                "Octant grouped split requires all input molecules to be accepted"
            )
        if (
            molecule.standardized_structure is None
            or molecule.standardized_structure_hash is None
        ):
            raise ValidationDataError(
                f"accepted molecule {molecule.molecule_id} lacks standardized data"
            )
        group_type, group_hash = _scaffold_group(molecule)
        group_details[molecule.molecule_id] = (group_type, group_hash)
        members_by_group[group_hash].append(molecule.molecule_id)
        molecules_by_id[molecule.molecule_id] = molecule
    if len(members_by_group) < 5:
        raise ValidationDataError(
            "Octant grouped split requires at least five distinct chemistry groups"
        )

    fold_by_group = _balanced_group_folds(members_by_group, seed, fold_count=5)
    rows = []
    for molecule_id in sorted(molecules_by_id):
        molecule = molecules_by_id[molecule_id]
        group_type, group_hash = group_details[molecule_id]
        outer_fold = fold_by_group[group_hash]
        rows.append(
            {
                "molecule_id": molecule_id,
                "standardized_structure_hash": cast(
                    str, molecule.standardized_structure_hash
                ),
                "group_type": group_type,
                "group_hash": group_hash,
                "outer_fold": str(outer_fold),
                "outer_partition": (
                    "validation" if outer_fold == 0 else "train"
                ),
                "inner_fold": "" if outer_fold == 0 else str(outer_fold - 1),
                "has_measurement": str(molecule_id in measurement_counts).lower(),
            }
        )
    split_bytes = _csv_bytes(OCTANT_SPLIT_COLUMNS, rows)
    fold_counts = []
    for fold in range(5):
        fold_rows = [row for row in rows if int(row["outer_fold"]) == fold]
        fold_counts.append(
            {
                "fold": fold,
                "rows": len(fold_rows),
                "measured_rows": sum(
                    row["has_measurement"] == "true" for row in fold_rows
                ),
                "groups": len({row["group_hash"] for row in fold_rows}),
            }
        )
    manifest = {
        "schema_version": OCTANT_GROUPED_SPLIT_SCHEMA_VERSION,
        "seed": seed,
        "group_policy": (
            "Bemis-Murcko scaffold without chirality; acyclic molecules fall "
            "back to exact standardized structure"
        ),
        "assignment_policy": (
            "Largest groups first into the smallest of five folds; seeded "
            "SHA-256 breaks size ties. Fold 0 is outer validation and folds "
            "1-4 are training plus four inner folds."
        ),
        "selection_policy": (
            "Outer validation is never used to fit or select candidates. "
            "Candidate selection uses only the four grouped inner folds."
        ),
        "input_hashes": dict(dataset.hashes),
        "rows": len(rows),
        "measured_rows": len(measurement_counts),
        "unmeasured_rows": len(rows) - len(measurement_counts),
        "groups": len(members_by_group),
        "group_type_counts": dict(
            sorted(Counter(value[0] for value in group_details.values()).items())
        ),
        "outer_fold_counts": fold_counts,
        "output": {
            "path": "octant_grouped_split.csv",
            "sha256": sha256(split_bytes).hexdigest(),
        },
        "deterministic": True,
    }
    manifest_bytes = _json_bytes(manifest)
    output_directory.mkdir(parents=True)
    split_path = output_directory / "octant_grouped_split.csv"
    manifest_path = output_directory / "split_manifest.json"
    _write_new(split_path, split_bytes)
    _write_new(manifest_path, manifest_bytes)
    return OctantSplitResult(
        split_path=split_path,
        manifest_path=manifest_path,
        row_count=len(rows),
        group_count=len(members_by_group),
    )


def audit_tdc_official_splits(
    canonical_directory: Path,
    official_split_path: Path,
    output_directory: Path,
) -> TdcSplitAuditResult:
    """Audit exact and standardized leakage without changing official splits."""

    if output_directory.exists():
        raise ValidationDataError(
            f"output path already exists: {output_directory}. "
            "Validation artifacts are immutable."
        )
    dataset = _load_dataset(canonical_directory)
    split_rows = _read_csv(official_split_path, TDC_SPLIT_COLUMNS)
    molecule_by_id = {molecule.molecule_id: molecule for molecule in dataset.molecules}
    if len(molecule_by_id) != len(dataset.molecules):
        raise ValidationDataError("canonical TDC molecule IDs are not unique")
    split_counts = Counter(row["molecule_id"] for row in split_rows)
    duplicate_split_ids = sorted(
        molecule_id for molecule_id, count in split_counts.items() if count > 1
    )
    if duplicate_split_ids:
        raise ValidationDataError(
            "official split repeats molecule IDs: " + ", ".join(duplicate_split_ids)
        )
    if set(split_counts) != set(molecule_by_id):
        raise ValidationDataError(
            "official split molecule IDs do not exactly match canonical molecules"
        )
    measurement_by_id = {}
    for measurement in dataset.measurements:
        if measurement.molecule_id in measurement_by_id:
            raise ValidationDataError(
                "TDC split audit expects one label per canonical molecule"
            )
        if measurement.value not in {0.0, 1.0}:
            raise ValidationDataError("TDC split audit requires binary labels")
        measurement_by_id[measurement.molecule_id] = measurement
    if set(measurement_by_id) != set(molecule_by_id):
        raise ValidationDataError(
            "TDC split audit requires one label for every canonical molecule"
        )

    tasks: dict[str, Any] = {}
    exclusion_rows: list[dict[str, str]] = []
    for task in TDC_TASKS:
        task_rows = [row for row in split_rows if row["task"] == task]
        unexpected_partitions = sorted(
            {row["partition"] for row in task_rows} - {"train_val", "test"}
        )
        if unexpected_partitions:
            raise ValidationDataError(
                f"{task} has unexpected partitions: {', '.join(unexpected_partitions)}"
            )
        rows_by_partition = {
            partition: [
                row for row in task_rows if row["partition"] == partition
            ]
            for partition in ("train_val", "test")
        }
        if any(not rows for rows in rows_by_partition.values()):
            raise ValidationDataError(f"{task} is missing an official partition")
        molecules_by_partition = {
            partition: [
                molecule_by_id[row["molecule_id"]] for row in rows
            ]
            for partition, rows in rows_by_partition.items()
        }
        raw_overlap = {
            molecule.raw_structure
            for molecule in molecules_by_partition["train_val"]
        } & {
            molecule.raw_structure for molecule in molecules_by_partition["test"]
        }
        standardized_overlap = {
            _structure_hash(molecule)
            for molecule in molecules_by_partition["train_val"]
        } & {
            _structure_hash(molecule)
            for molecule in molecules_by_partition["test"]
        }
        labels_by_overlap: dict[str, set[float]] = defaultdict(set)
        for partition_molecules in molecules_by_partition.values():
            for molecule in partition_molecules:
                structure_hash = _structure_hash(molecule)
                if structure_hash in standardized_overlap:
                    value = measurement_by_id[molecule.molecule_id].value
                    if value is None:
                        raise ValidationDataError("TDC label unexpectedly missing")
                    labels_by_overlap[structure_hash].add(value)
        for molecule in molecules_by_partition["test"]:
            structure_hash = _structure_hash(molecule)
            if structure_hash in standardized_overlap:
                exclusion_rows.append(
                    {
                        "task": task,
                        "molecule_id": molecule.molecule_id,
                        "standardized_structure_hash": structure_hash,
                        "reason": "standardized_structure_in_train_val",
                    }
                )
        partition_summary = {}
        for partition, molecules in molecules_by_partition.items():
            positives = sum(
                measurement_by_id[molecule.molecule_id].value == 1.0
                for molecule in molecules
            )
            partition_summary[partition] = {
                "rows": len(molecules),
                "positive": positives,
                "negative": len(molecules) - positives,
                "prevalence": positives / len(molecules),
            }
        tasks[task] = {
            "partitions": partition_summary,
            "raw_structure_overlap": {
                "structures": len(raw_overlap),
                "train_val_rows": sum(
                    molecule.raw_structure in raw_overlap
                    for molecule in molecules_by_partition["train_val"]
                ),
                "test_rows": sum(
                    molecule.raw_structure in raw_overlap
                    for molecule in molecules_by_partition["test"]
                ),
            },
            "standardized_structure_overlap": {
                "structures": len(standardized_overlap),
                "train_val_rows": sum(
                    _structure_hash(molecule) in standardized_overlap
                    for molecule in molecules_by_partition["train_val"]
                ),
                "test_rows": sum(
                    _structure_hash(molecule) in standardized_overlap
                    for molecule in molecules_by_partition["test"]
                ),
                "conflicting_label_structures": sum(
                    len(labels) > 1 for labels in labels_by_overlap.values()
                ),
            },
        }
    unexpected_tasks = sorted({row["task"] for row in split_rows} - set(TDC_TASKS))
    if unexpected_tasks:
        raise ValidationDataError(
            "official split has unexpected tasks: " + ", ".join(unexpected_tasks)
        )

    exclusion_rows.sort(key=lambda row: (row["task"], row["molecule_id"]))
    exclusion_bytes = _csv_bytes(TDC_EXCLUSION_COLUMNS, exclusion_rows)
    report = {
        "schema_version": TDC_SPLIT_AUDIT_SCHEMA_VERSION,
        "input_hashes": {
            **dict(dataset.hashes),
            "official_split.csv": _file_hash(official_split_path),
        },
        "official_policy": (
            "Preserve and report the official test population unchanged. "
            "Never select candidates on public test labels."
        ),
        "strict_policy": (
            "Report a separate companion score excluding test molecules whose "
            "standardized structure occurs in train_val."
        ),
        "metric": {"name": "AUPRC", "direction": AUPRC_DIRECTION},
        "public_test_evaluations": 0,
        "tasks": tasks,
        "strict_test_exclusions": {
            "rows": len(exclusion_rows),
            "path": "strict_test_exclusions.csv",
            "sha256": sha256(exclusion_bytes).hexdigest(),
        },
        "deterministic": True,
    }
    report_bytes = _json_bytes(report)
    output_directory.mkdir(parents=True)
    report_path = output_directory / "tdc_split_audit.json"
    exclusions_path = output_directory / "strict_test_exclusions.csv"
    _write_new(report_path, report_bytes)
    _write_new(exclusions_path, exclusion_bytes)
    return TdcSplitAuditResult(
        report_path=report_path,
        exclusions_path=exclusions_path,
        exclusion_count=len(exclusion_rows),
    )


def _load_dataset(canonical_directory: Path) -> Any:
    try:
        return load_audited_dataset(canonical_directory)
    except BaselineError as exc:
        raise ValidationDataError(str(exc)) from exc


def _scaffold_group(molecule: MoleculeRecord) -> tuple[str, str]:
    structure = cast(str, molecule.standardized_structure)
    with rdBase.BlockLogs():
        parsed = Chem.MolFromSmiles(structure)
    if parsed is None:
        raise ValidationDataError(
            f"cannot parse canonical structure for {molecule.molecule_id}"
        )
    murcko_module = import_module("rdkit.Chem.Scaffolds.MurckoScaffold")
    scaffold_value = murcko_module.MurckoScaffoldSmiles(
        mol=parsed, includeChirality=False
    )
    if not isinstance(scaffold_value, str):
        raise ValidationDataError("RDKit returned a non-text scaffold")
    scaffold = scaffold_value
    if scaffold:
        group_type = "bemis_murcko_scaffold"
        material = scaffold
    else:
        group_type = "acyclic_exact_structure"
        material = structure
    group_hash = sha256(f"{group_type}:{material}".encode()).hexdigest()
    return group_type, group_hash


def _balanced_group_folds(
    members_by_group: Mapping[str, Sequence[str]], seed: int, *, fold_count: int
) -> dict[str, int]:
    ordered_groups = sorted(
        members_by_group,
        key=lambda group_hash: (
            -len(members_by_group[group_hash]),
            sha256(f"{seed}:{group_hash}".encode()).hexdigest(),
        ),
    )
    row_counts = [0] * fold_count
    assignment = {}
    for group_hash in ordered_groups:
        fold = min(range(fold_count), key=lambda value: (row_counts[value], value))
        assignment[group_hash] = fold
        row_counts[fold] += len(members_by_group[group_hash])
    return assignment


def _structure_hash(molecule: MoleculeRecord) -> str:
    if (
        molecule.status is not MoleculeStatus.ACCEPTED
        or molecule.standardized_structure_hash is None
    ):
        raise ValidationDataError(
            f"TDC split molecule {molecule.molecule_id} is not accepted"
        )
    return molecule.standardized_structure_hash


def _read_csv(path: Path, expected_columns: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != tuple(expected_columns):
                raise ValidationDataError(
                    f"{path.name} columns do not match its frozen schema"
                )
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValidationDataError(
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
        raise ValidationDataError(f"cannot read {path}: {exc}") from exc
    return rows


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ValidationDataError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _csv_bytes(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except OSError as exc:
        raise ValidationDataError(f"cannot write {path}: {exc}") from exc


__all__ = [
    "OCTANT_GROUPED_SPLIT_SCHEMA_VERSION",
    "OCTANT_SPLIT_COLUMNS",
    "TDC_EXCLUSION_COLUMNS",
    "TDC_SPLIT_AUDIT_SCHEMA_VERSION",
    "OctantSplitResult",
    "TdcSplitAuditResult",
    "ValidationDataError",
    "audit_tdc_official_splits",
    "freeze_octant_grouped_split",
]
