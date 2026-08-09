"""Prepare the stripped, label-free input for the CheMeleon reference."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from typing import Any

CHEMELEON_INPUT_SCHEMA_VERSION = "cypshift.chemeleon_inference_input.v1"
CHEMELEON_INPUT_COLUMNS = (
    "benchmark",
    "task",
    "molecule_id",
    "standardized_structure",
    "standardized_structure_hash",
)
KEY_COLUMNS = ("benchmark", "task", "molecule_id")
AGGREGATE_RECIPE = (
    "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined with newline "
    "characters, without a trailing newline"
)
KEY_RECIPE = (
    "SHA-256 of benchmark|task|molecule_id lines in canonical CSV order, "
    "joined with newline characters without a trailing newline"
)


class CheMeleonInputError(ValueError):
    """Raised when the external-model input firewall is invalid."""


def prepare_chemeleon_inference_input(
    prediction_input_root: Path,
    retained_mean_prediction_root: Path,
    contract_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> Path:
    """Project exact held-out keys onto identity and structure fields only."""

    if output_directory.exists():
        raise CheMeleonInputError(f"output path already exists: {output_directory}")
    contract = _read_json(contract_path)
    benchmark_input = _mapping(contract, "benchmark_input", contract_path)
    _require_hash(
        prediction_input_root / "prediction_input_manifest.json",
        _text(benchmark_input, "prediction_input_manifest_sha256", contract_path),
    )
    prediction_manifest = _verify_manifest_receipt(
        prediction_input_root / "prediction_input_manifest.json"
    )
    expected_input_aggregate = _text(
        benchmark_input, "prediction_input_aggregate_sha256", contract_path
    )
    if prediction_manifest.get("aggregate_sha256") != expected_input_aggregate:
        raise CheMeleonInputError("prediction-input aggregate does not match contract")
    prediction_outputs = _mapping(
        prediction_manifest,
        "outputs",
        prediction_input_root / "prediction_input_manifest.json",
    )
    for name in ("octant/molecules.csv", "tdc/molecules.csv"):
        _require_hash(
            prediction_input_root / name,
            _text(
                prediction_outputs,
                name,
                prediction_input_root / "prediction_input_manifest.json",
            ),
        )

    population = _mapping(contract, "population_key_source", contract_path)
    retained_manifest_path = (
        retained_mean_prediction_root / "retained_mean_prediction_manifest.json"
    )
    _require_hash(
        retained_manifest_path,
        _text(population, "manifest_sha256", contract_path),
    )
    retained_manifest = _verify_manifest(
        retained_manifest_path, retained_mean_prediction_root
    )
    if retained_manifest.get("aggregate_sha256") != _text(
        population, "aggregate_sha256", contract_path
    ):
        raise CheMeleonInputError("population-key aggregate does not match contract")
    prediction_path = (
        retained_mean_prediction_root / "retained_mean_heldout_predictions.csv"
    )
    _require_hash(
        prediction_path,
        _text(population, "prediction_csv_sha256", contract_path),
    )

    key_rows = _read_csv(
        prediction_path,
        required=("benchmark", "task", "molecule_id"),
        exact=False,
    )
    keys: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in key_rows:
        key = tuple(_required(row, field, prediction_path) for field in KEY_COLUMNS)
        typed_key = (key[0], key[1], key[2])
        if typed_key in seen:
            raise CheMeleonInputError(f"duplicate population key: {typed_key}")
        seen.add(typed_key)
        keys.append(typed_key)
    keys.sort()

    molecules = {
        "octant_cyp": _molecule_index(
            prediction_input_root / "octant" / "molecules.csv"
        ),
        "tdc_admet_group": _molecule_index(
            prediction_input_root / "tdc" / "molecules.csv"
        ),
    }
    projected: list[dict[str, str]] = []
    for benchmark, task, molecule_id in keys:
        if benchmark not in molecules:
            raise CheMeleonInputError(f"unsupported benchmark in population: {benchmark}")
        molecule = molecules[benchmark].get(molecule_id)
        if molecule is None:
            raise CheMeleonInputError(f"population molecule is missing: {molecule_id}")
        projected.append(
            {
                "benchmark": benchmark,
                "task": task,
                "molecule_id": molecule_id,
                "standardized_structure": molecule[0],
                "standardized_structure_hash": molecule[1],
            }
        )

    expected_counts = _string_int_mapping(
        _mapping(contract, "expected_task_counts", contract_path), contract_path
    )
    actual_counts = Counter(row["task"] for row in projected)
    if dict(sorted(actual_counts.items())) != dict(sorted(expected_counts.items())):
        raise CheMeleonInputError("projected task counts do not match contract")

    output_directory.mkdir(parents=True)
    input_path = output_directory / "chemeleon_inference_input.csv"
    _write_csv(input_path, CHEMELEON_INPUT_COLUMNS, projected)
    validation = validate_chemeleon_inference_input(
        input_path,
        expected_rows=len(projected),
        expected_task_counts=expected_counts,
    )
    outputs = {input_path.name: _file_hash(input_path)}
    projection_contract = _mapping(
        contract, "model_facing_projection", contract_path
    )
    expected_output = _text(
        projection_contract, "expected_output_sha256", contract_path
    )
    expected_key = _text(
        projection_contract, "expected_population_key_sha256", contract_path
    )
    expected_aggregate = _text(
        projection_contract, "expected_aggregate_sha256", contract_path
    )
    if outputs[input_path.name] != expected_output:
        raise CheMeleonInputError("projected output hash does not match contract")
    if validation["population_key_sha256"] != expected_key:
        raise CheMeleonInputError("projected population-key hash does not match contract")
    if _hash_mapping(outputs) != expected_aggregate:
        raise CheMeleonInputError("projected aggregate does not match contract")
    manifest_path = output_directory / "chemeleon_input_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": CHEMELEON_INPUT_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "contract_sha256": _file_hash(contract_path),
            "prediction_input_manifest_sha256": _file_hash(
                prediction_input_root / "prediction_input_manifest.json"
            ),
            "prediction_input_aggregate_sha256": expected_input_aggregate,
            "population_key_manifest_sha256": _file_hash(retained_manifest_path),
            "population_key_aggregate_sha256": retained_manifest[
                "aggregate_sha256"
            ],
            "population_key_csv_sha256": _file_hash(prediction_path),
            "population_key_recipe": KEY_RECIPE,
            "population_key_sha256": validation["population_key_sha256"],
            "columns": list(CHEMELEON_INPUT_COLUMNS),
            "rows": len(projected),
            "task_counts": dict(sorted(actual_counts.items())),
            "source_molecule_tables_opened": 2,
            "source_provenance_values_parsed": 0,
            "source_measurement_tables_opened": 0,
            "heldout_labels_parsed": 0,
            "native_prediction_values_consumed": 0,
            "model_facing_input_files": [input_path.name],
            "model_mount_policy": (
                "Mount only this stripped CSV read-only. Do not mount the broader "
                "prediction-input or retained-mean roots."
            ),
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
        },
    )
    return manifest_path


def validate_chemeleon_inference_input(
    input_path: Path,
    *,
    expected_rows: int,
    expected_task_counts: Mapping[str, int],
    expected_file_sha256: str | None = None,
    expected_key_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the only file that the external container may read."""

    if expected_file_sha256 is not None:
        _require_hash(input_path, expected_file_sha256)
    rows = _read_csv(input_path, required=CHEMELEON_INPUT_COLUMNS, exact=True)
    if len(rows) != expected_rows:
        raise CheMeleonInputError("external-model input row count mismatch")
    counts: Counter[str] = Counter()
    key_lines: list[str] = []
    previous: tuple[str, str, str] | None = None
    for row in rows:
        key = tuple(_required(row, field, input_path) for field in KEY_COLUMNS)
        typed_key = (key[0], key[1], key[2])
        if previous is not None and typed_key <= previous:
            raise CheMeleonInputError(
                "external-model input keys must be unique and sorted"
            )
        previous = typed_key
        structure = _required(row, "standardized_structure", input_path)
        structure_hash = _required(
            row, "standardized_structure_hash", input_path
        )
        if sha256(structure.encode()).hexdigest() != structure_hash:
            raise CheMeleonInputError("standardized structure hash mismatch")
        counts[typed_key[1]] += 1
        key_lines.append("|".join(typed_key))
    if dict(sorted(counts.items())) != dict(sorted(expected_task_counts.items())):
        raise CheMeleonInputError("external-model input task counts mismatch")
    key_hash = sha256("\n".join(key_lines).encode()).hexdigest()
    if expected_key_sha256 is not None and key_hash != expected_key_sha256:
        raise CheMeleonInputError("external-model population-key hash mismatch")
    return {
        "rows": len(rows),
        "task_counts": dict(sorted(counts.items())),
        "population_key_sha256": key_hash,
        "file_sha256": _file_hash(input_path),
    }


def _molecule_index(path: Path) -> dict[str, tuple[str, str]]:
    rows = _read_csv(
        path,
        required=(
            "molecule_id",
            "standardized_structure",
            "standardized_structure_hash",
        ),
        exact=False,
    )
    result: dict[str, tuple[str, str]] = {}
    for row in rows:
        molecule_id = _required(row, "molecule_id", path)
        if molecule_id in result:
            raise CheMeleonInputError(f"duplicate molecule id: {molecule_id}")
        structure = _required(row, "standardized_structure", path)
        structure_hash = _required(row, "standardized_structure_hash", path)
        if sha256(structure.encode()).hexdigest() != structure_hash:
            raise CheMeleonInputError(f"structure hash mismatch: {molecule_id}")
        result[molecule_id] = (structure, structure_hash)
    return result


def _verify_manifest(manifest_path: Path, root: Path) -> dict[str, Any]:
    manifest = _verify_manifest_receipt(manifest_path)
    outputs = _mapping(manifest, "outputs", manifest_path)
    for name, expected in outputs.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise CheMeleonInputError(f"invalid manifest output: {manifest_path}")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise CheMeleonInputError(f"unsafe manifest output: {name}")
        _require_hash(root / relative, expected)
    return manifest


def _verify_manifest_receipt(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    outputs = _mapping(manifest, "outputs", manifest_path)
    normalized: dict[str, str] = {}
    for name, expected in outputs.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise CheMeleonInputError(f"invalid manifest output: {manifest_path}")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise CheMeleonInputError(f"unsafe manifest output: {name}")
        normalized[name] = expected
    if manifest.get("aggregate_sha256") != _hash_mapping(normalized):
        raise CheMeleonInputError(f"manifest aggregate mismatch: {manifest_path}")
    return manifest


def _read_csv(
    path: Path, *, required: Sequence[str], exact: bool
) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            if exact and fields != tuple(required):
                raise CheMeleonInputError(f"unexpected columns in {path}: {fields}")
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


def _mapping(
    value: Mapping[str, Any], field: str, path: Path
) -> Mapping[str, Any]:
    result = value.get(field)
    if not isinstance(result, dict):
        raise CheMeleonInputError(f"{path} requires object field {field!r}")
    return result


def _text(value: Mapping[str, Any], field: str, path: Path) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise CheMeleonInputError(f"{path} requires text field {field!r}")
    return result


def _required(row: Mapping[str, str], field: str, path: Path) -> str:
    result = row.get(field)
    if not result:
        raise CheMeleonInputError(f"{path} requires nonempty field {field!r}")
    return result


def _string_int_mapping(
    value: Mapping[str, Any], path: Path
) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key or not isinstance(count, int):
            raise CheMeleonInputError(f"{path} contains invalid task counts")
        result[key] = count
    return result


def _require_hash(path: Path, expected: str) -> None:
    if _file_hash(path) != expected:
        raise CheMeleonInputError(f"file hash mismatch: {path}")


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
    "CHEMELEON_INPUT_COLUMNS",
    "CHEMELEON_INPUT_SCHEMA_VERSION",
    "CheMeleonInputError",
    "prepare_chemeleon_inference_input",
    "validate_chemeleon_inference_input",
]
