"""Concrete prediction and overlap receipts for the CheMeleon reference."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from typing import Any

from cypshift.chemeleon import (
    AGGREGATE_RECIPE,
    CHEMELEON_INPUT_COLUMNS,
    CheMeleonInputError,
    validate_chemeleon_inference_input,
)
from cypshift.chemistry import STANDARDIZATION_VERSION, standardize_molecule
from cypshift.schema import MoleculeInput, MoleculeStatus

OVERLAP_SCHEMA_VERSION = "cypshift.chemeleon_overlap.v1"
PREDICTION_SCHEMA_VERSION = "cypshift.chemeleon_prediction.v1"
OVERLAP_COLUMNS = (
    "benchmark",
    "task",
    "molecule_id",
    "standardized_structure_hash",
    "exact_training_structure_overlap",
)
PREDICTION_COLUMNS = (
    "benchmark",
    "task",
    "molecule_id",
    "prediction",
    "standardized_structure_hash",
    "exact_training_structure_overlap",
)


def verify_model_files(model_root: Path, contract_path: Path) -> dict[str, str]:
    """Verify every frozen model file and return its relative-path digest."""

    contract = _read_json(contract_path)
    required = _mapping(_mapping(contract, "model"), "required_files")
    verified: dict[str, str] = {}
    for name, expected in sorted(required.items()):
        if not isinstance(name, str) or not isinstance(expected, str):
            raise CheMeleonInputError("invalid required model file entry")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise CheMeleonInputError(f"unsafe model file path: {name}")
        actual = _file_hash(model_root / relative)
        if actual != expected:
            raise CheMeleonInputError(f"model file hash mismatch: {name}")
        verified[name] = actual
    return verified


def validate_task_mapping(input_path: Path, contract_path: Path) -> None:
    """Require the contract keys to equal the exact model-facing task values."""

    contract = _read_json(contract_path)
    _validate_input(input_path, contract)
    rows = _read_csv(input_path, required=CHEMELEON_INPUT_COLUMNS, exact=True)
    validate_task_mapping_values({row["task"] for row in rows}, contract_path)


def validate_task_mapping_values(
    input_tasks: set[str], contract_path: Path
) -> None:
    """Validate known task values without requiring an untracked real artifact."""

    contract = _read_json(contract_path)
    task_mapping = _mapping(contract, "task_mapping")
    if input_tasks != set(task_mapping):
        raise CheMeleonInputError(
            "contract task mapping does not match model-facing input tasks"
        )
    for task in sorted(input_tasks):
        _text(_mapping(task_mapping, task), "model_output")


def audit_training_overlap(
    input_path: Path,
    model_root: Path,
    contract_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> Path:
    """Standardize published training structures and flag exact input overlap."""

    _require_new(output_directory)
    contract = _read_json(contract_path)
    input_validation = _validate_input(input_path, contract)
    verify_model_files(model_root, contract_path)
    model = _mapping(contract, "model")
    training_column = _text(model, "training_structure_column")
    training_path = model_root / "anvil_training" / "data" / "X_train.csv"
    training_rows = _read_csv(training_path, required=(training_column,), exact=False)
    expected_training_rows = _integer(model, "training_rows")
    if len(training_rows) != expected_training_rows:
        raise CheMeleonInputError("CheMeleon training row count mismatch")

    training_hashes: set[str] = set()
    invalid = 0
    for index, row in enumerate(training_rows, start=1):
        structure = _required(row, training_column, training_path)
        record = standardize_molecule(
            MoleculeInput(
                molecule_id=f"chemeleon-train-{index:05d}",
                structure=structure,
                structure_format="smiles",
                source="openadmet/chemeleon-cyp-v1",
                provenance="published X_train.csv structure only",
            )
        )
        if record.status is MoleculeStatus.QUARANTINED:
            invalid += 1
            continue
        if record.standardized_structure_hash is None:
            raise CheMeleonInputError("accepted training structure has no hash")
        training_hashes.add(record.standardized_structure_hash)

    input_rows = _read_csv(
        input_path, required=CHEMELEON_INPUT_COLUMNS, exact=True
    )
    overlap_rows: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for row in input_rows:
        task = _required(row, "task", input_path)
        overlap = row["standardized_structure_hash"] in training_hashes
        if overlap:
            counts[task] += 1
        overlap_rows.append(
            {
                "benchmark": row["benchmark"],
                "task": task,
                "molecule_id": row["molecule_id"],
                "standardized_structure_hash": row[
                    "standardized_structure_hash"
                ],
                "exact_training_structure_overlap": str(overlap).lower(),
            }
        )

    output_directory.mkdir(parents=True)
    overlap_path = output_directory / "chemeleon_training_overlap.csv"
    _write_csv(overlap_path, OVERLAP_COLUMNS, overlap_rows)
    outputs = {overlap_path.name: _file_hash(overlap_path)}
    manifest_path = output_directory / "chemeleon_overlap_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": OVERLAP_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "contract_sha256": _file_hash(contract_path),
            "input_sha256": input_validation["file_sha256"],
            "population_key_sha256": input_validation[
                "population_key_sha256"
            ],
            "training_structure_file_sha256": _file_hash(training_path),
            "training_rows": len(training_rows),
            "accepted_training_rows": len(training_rows) - invalid,
            "invalid_training_rows": invalid,
            "unique_training_structure_hashes": len(training_hashes),
            "standardization_version": STANDARDIZATION_VERSION,
            "overlap_counts": dict(sorted(counts.items())),
            "rows": len(overlap_rows),
            "heldout_labels_parsed": 0,
            "model_fits": 0,
            "model_evaluations": 0,
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
        },
    )
    return manifest_path


def canonicalize_predictions(
    input_path: Path,
    raw_prediction_path: Path,
    overlap_root: Path,
    contract_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
    runtime_seconds: float,
) -> Path:
    """Align upstream multitask predictions to the exact frozen task rows."""

    _require_new(output_directory)
    contract = _read_json(contract_path)
    input_validation = _validate_input(input_path, contract)
    input_rows = _read_csv(
        input_path, required=CHEMELEON_INPUT_COLUMNS, exact=True
    )
    raw_rows = _read_csv(
        raw_prediction_path, required=CHEMELEON_INPUT_COLUMNS, exact=False
    )
    if len(raw_rows) != len(input_rows):
        raise CheMeleonInputError("raw prediction row count mismatch")
    overlap_manifest = _verify_manifest(
        overlap_root / "chemeleon_overlap_manifest.json", overlap_root
    )
    overlap_rows = _read_csv(
        overlap_root / "chemeleon_training_overlap.csv",
        required=OVERLAP_COLUMNS,
        exact=True,
    )
    if len(overlap_rows) != len(input_rows):
        raise CheMeleonInputError("overlap row count mismatch")

    task_mapping = _mapping(contract, "task_mapping")
    canonical: list[dict[str, str]] = []
    resolved_columns: dict[str, str] = {}
    for input_row, raw_row, overlap_row in zip(
        input_rows, raw_rows, overlap_rows, strict=True
    ):
        for field in CHEMELEON_INPUT_COLUMNS:
            if raw_row.get(field) != input_row[field]:
                raise CheMeleonInputError(f"raw prediction alignment mismatch: {field}")
        for field in OVERLAP_COLUMNS[:4]:
            if overlap_row[field] != input_row[field]:
                raise CheMeleonInputError(f"overlap alignment mismatch: {field}")
        task = input_row["task"]
        mapping = _mapping(task_mapping, task)
        model_output = _text(mapping, "model_output")
        prediction_column = resolve_prediction_column(raw_row, model_output)
        prior_column = resolved_columns.setdefault(task, prediction_column)
        if prior_column != prediction_column:
            raise CheMeleonInputError("prediction column changed within a task")
        prediction_text = _required(raw_row, prediction_column, raw_prediction_path)
        try:
            prediction = float(prediction_text)
        except ValueError as exc:
            raise CheMeleonInputError("CheMeleon prediction is not numeric") from exc
        if not math.isfinite(prediction):
            raise CheMeleonInputError("CheMeleon prediction is not finite")
        canonical.append(
            {
                "benchmark": input_row["benchmark"],
                "task": task,
                "molecule_id": input_row["molecule_id"],
                "prediction": format(prediction, ".17g"),
                "standardized_structure_hash": input_row[
                    "standardized_structure_hash"
                ],
                "exact_training_structure_overlap": overlap_row[
                    "exact_training_structure_overlap"
                ],
            }
        )

    output_directory.mkdir(parents=True)
    predictions_path = output_directory / "chemeleon_predictions.csv"
    _write_csv(predictions_path, PREDICTION_COLUMNS, canonical)
    outputs = {predictions_path.name: _file_hash(predictions_path)}
    manifest_path = output_directory / "chemeleon_prediction_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": PREDICTION_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "contract_sha256": _file_hash(contract_path),
            "input_sha256": input_validation["file_sha256"],
            "population_key_sha256": input_validation[
                "population_key_sha256"
            ],
            "raw_prediction_sha256": _file_hash(raw_prediction_path),
            "overlap_manifest_sha256": _file_hash(
                overlap_root / "chemeleon_overlap_manifest.json"
            ),
            "overlap_aggregate_sha256": overlap_manifest["aggregate_sha256"],
            "rows": len(canonical),
            "resolved_prediction_columns": dict(sorted(resolved_columns.items())),
            "runtime_seconds": runtime_seconds,
            "heldout_labels_parsed": 0,
            "model_fits": 0,
            "model_evaluations": 0,
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
        },
    )
    return manifest_path


def docker_prediction_command(
    *,
    image: str,
    input_path: Path,
    model_directory: Path,
    output_directory: Path,
    output_name: str,
) -> list[str]:
    """Build the fixed container command with only safe read-only inputs."""

    return [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--user=root",
        "-e",
        "TABPFN_TELEMETRY_OPTOUT=1",
        "-e",
        "OADMET_NO_RICH_LOGGING=1",
        "-v",
        f"{input_path.resolve()}:/input.csv:ro",
        "-v",
        f"{model_directory.resolve()}:/model:ro",
        "-v",
        f"{output_directory.resolve()}:/output:rw",
        image,
        "openadmet",
        "predict",
        "--input-path",
        "/input.csv",
        "--input-col",
        "standardized_structure",
        "--model-dir",
        "/model",
        "--output-csv",
        f"/output/{output_name}",
        "--accelerator",
        "cpu",
    ]


def resolve_prediction_column(row: Mapping[str, str], model_output: str) -> str:
    """Resolve the sole upstream prediction field for one frozen model output."""

    suffix = f"_{model_output}"
    candidates = sorted(
        name
        for name in row
        if name.startswith("OADMET_PRED_") and name.endswith(suffix)
    )
    if len(candidates) != 1:
        raise CheMeleonInputError(
            f"expected one prediction column for {model_output}, got {candidates}"
        )
    return candidates[0]


def require_docker_ready() -> None:
    """Fail before the attempt if the local Docker service is unavailable."""

    result = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CheMeleonInputError("Docker service is not ready")


def require_identical_predictions(first: Path, second: Path) -> None:
    """Require exact repeat bytes before any label can be opened."""

    if first.read_bytes() != second.read_bytes():
        raise CheMeleonInputError("full canonical predictions are not identical")


def _validate_input(input_path: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    projection = _mapping(contract, "model_facing_projection")
    counts = {
        key: _integer_value(value, "expected task count")
        for key, value in _mapping(contract, "expected_task_counts").items()
    }
    return validate_chemeleon_inference_input(
        input_path,
        expected_rows=sum(counts.values()),
        expected_task_counts=counts,
        expected_file_sha256=_text(projection, "expected_output_sha256"),
        expected_key_sha256=_text(
            projection, "expected_population_key_sha256"
        ),
    )


def _verify_manifest(manifest_path: Path, root: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    outputs = _mapping(manifest, "outputs")
    normalized: dict[str, str] = {}
    for name, expected in outputs.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise CheMeleonInputError("invalid manifest output")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise CheMeleonInputError("unsafe manifest output")
        if _file_hash(root / relative) != expected:
            raise CheMeleonInputError(f"manifest output hash mismatch: {name}")
        normalized[name] = expected
    if manifest.get("aggregate_sha256") != _hash_mapping(normalized):
        raise CheMeleonInputError("manifest aggregate mismatch")
    return manifest


def _require_new(path: Path) -> None:
    if path.exists():
        raise CheMeleonInputError(f"output path already exists: {path}")


def _read_csv(
    path: Path, *, required: Sequence[str], exact: bool
) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            if exact and fields != tuple(required):
                raise CheMeleonInputError(f"unexpected columns in {path}")
            missing = [field for field in required if field not in fields]
            if missing:
                raise CheMeleonInputError(f"missing columns in {path}: {missing}")
            rows = list(reader)
    except OSError as exc:
        raise CheMeleonInputError(f"cannot read {path}: {exc}") from exc
    if any(
        None in row or any(value is None for value in row.values()) for row in rows
    ):
        raise CheMeleonInputError(f"malformed row width in {path}")
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheMeleonInputError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CheMeleonInputError(f"{path} must contain a JSON object")
    return value


def _mapping(value: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    result = value.get(field)
    if not isinstance(result, dict):
        raise CheMeleonInputError(f"contract requires object field {field!r}")
    return result


def _text(value: Mapping[str, Any], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise CheMeleonInputError(f"contract requires text field {field!r}")
    return result


def _integer(value: Mapping[str, Any], field: str) -> int:
    return _integer_value(value.get(field), field)


def _integer_value(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CheMeleonInputError(f"contract requires integer field {field!r}")
    return value


def _required(row: Mapping[str, str], field: str, path: Path) -> str:
    value = row.get(field)
    if not value:
        raise CheMeleonInputError(f"{path} requires nonempty field {field!r}")
    return value


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


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise CheMeleonInputError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def _hash_mapping(values: Mapping[str, str]) -> str:
    material = "\n".join(f"{name}={values[name]}" for name in sorted(values))
    return sha256(material.encode()).hexdigest()


__all__ = [
    "OVERLAP_COLUMNS",
    "OVERLAP_SCHEMA_VERSION",
    "PREDICTION_COLUMNS",
    "PREDICTION_SCHEMA_VERSION",
    "audit_training_overlap",
    "canonicalize_predictions",
    "docker_prediction_command",
    "require_docker_ready",
    "require_identical_predictions",
    "resolve_prediction_column",
    "validate_task_mapping",
    "validate_task_mapping_values",
    "verify_model_files",
]
