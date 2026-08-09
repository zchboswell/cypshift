"""Deterministic Phase 0 split, median baseline, and prediction artifacts."""

from __future__ import annotations

import csv
import json
import platform
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Any, cast

from rdkit import rdBase

from cypshift import __release_tag__, __version__
from cypshift.audit import (
    AUDIT_SCHEMA_VERSION,
    MEASUREMENT_COLUMNS,
    MOLECULE_OUTPUT_COLUMNS,
)
from cypshift.schema import (
    Censoring,
    MeasurementRecord,
    MoleculeRecord,
    MoleculeStatus,
    RecordError,
)

DEFAULT_SEED = 20260809
DEFAULT_VALIDATION_FRACTION = 0.25
MODEL_SCHEMA_VERSION = "cypshift.endpoint_context_median.v1"
SPLIT_SCHEMA_VERSION = "cypshift.fixture_split.v1"
PREDICTION_SCHEMA_VERSION = "cypshift.predictions.v1"
PREDICTION_CARD_SCHEMA_VERSION = "cypshift.prediction_card.v1"
RUN_MANIFEST_SCHEMA_VERSION = "cypshift.run_manifest.v1"

SPLIT_COLUMNS = (
    "molecule_id",
    "standardized_structure_hash",
    "partition",
    "split_schema_version",
    "seed",
)
PREDICTION_COLUMNS = (
    "molecule_id",
    "endpoint",
    "isoform",
    "nadph_condition",
    "probe",
    "readout",
    "unit",
    "partition",
    "model",
    "prediction",
    "training_measurement_count",
    "data_version",
    "model_version",
)
CONTEXT_FIELDS = (
    "endpoint",
    "isoform",
    "nadph_condition",
    "probe",
    "readout",
    "unit",
)

AssayContext = tuple[str, str, str, str, str, str]


class BaselineError(ValueError):
    """Raised when deterministic baseline artifacts cannot be produced."""


@dataclass(frozen=True, slots=True)
class AuditedDataset:
    """Canonical records and hashes loaded from one completed audit."""

    molecules: tuple[MoleculeRecord, ...]
    measurements: tuple[MeasurementRecord, ...]
    hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Paths and resolved configuration from one baseline fit."""

    model_path: Path
    split_path: Path
    model: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class PredictionResult:
    """Paths from one completed deterministic prediction run."""

    predictions_path: Path
    prediction_cards_path: Path
    manifest_path: Path
    prediction_count: int
    supported_context_count: int
    unsupported_context_count: int


def train_baseline(
    data_directory: Path,
    output_directory: Path,
    *,
    seed: int = DEFAULT_SEED,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
) -> TrainingResult:
    """Fit an endpoint-context median using a fixture-only grouped split."""

    if not 0.0 < validation_fraction < 1.0:
        raise BaselineError("validation_fraction must be between 0 and 1")
    dataset = load_audited_dataset(data_directory)
    model_path = output_directory / "model.json"
    split_path = output_directory / "split.csv"
    _require_absent((model_path, split_path))

    split_rows = _make_split(dataset.molecules, seed, validation_fraction)
    partition_by_molecule = {
        row["molecule_id"]: row["partition"] for row in split_rows
    }
    values_by_context: dict[AssayContext, list[float]] = defaultdict(list)
    observed_counts: dict[AssayContext, int] = defaultdict(int)
    training_counts: dict[AssayContext, int] = defaultdict(int)
    used_measurements = 0
    for measurement in dataset.measurements:
        context = _context(measurement)
        observed_counts[context] += 1
        if partition_by_molecule[measurement.molecule_id] == "train":
            training_counts[context] += 1
        if (
            partition_by_molecule[measurement.molecule_id] == "train"
            and measurement.censoring is Censoring.NONE
            and measurement.value is not None
        ):
            values_by_context[context].append(measurement.value)
            used_measurements += 1
    if not values_by_context:
        raise BaselineError(
            "the training partition has no uncensored numeric measurements"
        )

    split_bytes = _csv_bytes(SPLIT_COLUMNS, split_rows)
    contexts = []
    for context, values in sorted(values_by_context.items()):
        context_record: dict[str, Any] = dict(
            zip(CONTEXT_FIELDS, context, strict=True)
        )
        context_record.update(
            {
                "prediction": median(values),
                "training_measurement_count": len(values),
            }
        )
        contexts.append(context_record)
    unsupported_contexts = []
    for context in sorted(set(observed_counts) - set(values_by_context)):
        context_record = dict(zip(CONTEXT_FIELDS, context, strict=True))
        context_record.update(
            {
                "reason": (
                    "no_training_partition_measurement"
                    if training_counts[context] == 0
                    else "no_uncensored_numeric_training_measurement"
                ),
                "observed_measurement_count": observed_counts[context],
                "training_measurement_count": training_counts[context],
            }
        )
        unsupported_contexts.append(context_record)
    model: dict[str, Any] = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "method": "endpoint_context_median",
        "resolved_configuration": {
            "seed": seed,
            "validation_fraction": validation_fraction,
            "split_schema_version": SPLIT_SCHEMA_VERSION,
            "split_scope": "synthetic_fixture_pipeline_test_only",
        },
        "training_data_hashes": dict(dataset.hashes),
        "split_sha256": sha256(split_bytes).hexdigest(),
        "fit_summary": {
            "contexts_observed": len(observed_counts),
            "contexts_supported": len(contexts),
            "contexts_unsupported": len(unsupported_contexts),
            "measurements_used": used_measurements,
            "measurements_not_used": len(dataset.measurements) - used_measurements,
        },
        "contexts": contexts,
        "unsupported_contexts": unsupported_contexts,
    }
    model_bytes = _json_bytes(model)

    output_directory.mkdir(parents=True, exist_ok=True)
    _write_new(split_path, split_bytes)
    _write_new(model_path, model_bytes)
    return TrainingResult(model_path=model_path, split_path=split_path, model=model)


def predict_baseline(
    data_directory: Path,
    model_path: Path,
    split_path: Path,
    output_directory: Path,
) -> PredictionResult:
    """Generate deterministic baseline predictions, cards, and a run manifest."""

    dataset = load_audited_dataset(data_directory)
    model = _read_json(model_path)
    if model.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise BaselineError(
            f"unsupported model schema: {model.get('schema_version')!r}"
        )
    split_rows = _read_csv(split_path, SPLIT_COLUMNS)
    expected_split_hash = model.get("split_sha256")
    actual_split_hash = _file_hash(split_path)
    if actual_split_hash != expected_split_hash:
        raise BaselineError("split.csv hash does not match model.json")

    predictions_path = output_directory / "predictions.csv"
    cards_path = output_directory / "prediction_cards.jsonl"
    manifest_path = output_directory / "run_manifest.json"
    _require_absent((predictions_path, cards_path, manifest_path))

    partition_by_molecule = {
        row["molecule_id"]: row["partition"] for row in split_rows
    }
    model_version = _file_hash(model_path)
    data_version = _combined_hash(dataset.hashes)
    prediction_rows: list[dict[str, str]] = []
    cards: list[dict[str, Any]] = []
    contexts = model.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise BaselineError("model contains no endpoint contexts")
    unsupported_contexts = model.get("unsupported_contexts")
    if not isinstance(unsupported_contexts, list):
        raise BaselineError("model unsupported_contexts must be an array")

    for molecule in dataset.molecules:
        if molecule.status is MoleculeStatus.QUARANTINED:
            continue
        for context in contexts:
            if not isinstance(context, dict):
                raise BaselineError("model context is not an object")
            prediction = _required_model_number(context, "prediction")
            training_count = _required_model_int(
                context, "training_measurement_count"
            )
            partition = partition_by_molecule.get(molecule.molecule_id, "prediction")
            row = {
                "molecule_id": molecule.molecule_id,
                **{
                    field: _required_model_text(context, field)
                    for field in CONTEXT_FIELDS
                },
                "partition": partition,
                "model": "endpoint_context_median",
                "prediction": str(prediction),
                "training_measurement_count": str(training_count),
                "data_version": data_version,
                "model_version": model_version,
            }
            prediction_rows.append(row)
            cards.append(
                {
                    "schema_version": PREDICTION_CARD_SCHEMA_VERSION,
                    "molecule_id": molecule.molecule_id,
                    "context": {field: row[field] for field in CONTEXT_FIELDS},
                    "prediction": prediction,
                    "model": "endpoint_context_median",
                    "training_measurement_count": training_count,
                    "partition": partition,
                    "chemistry_warnings": list(molecule.warnings),
                    "llm_adjudication": "not_used",
                    "data_version": data_version,
                    "model_version": model_version,
                }
            )

    prediction_rows.sort(
        key=lambda row: (
            row["molecule_id"],
            *(row[field] for field in CONTEXT_FIELDS),
        )
    )
    cards.sort(
        key=lambda card: (
            card["molecule_id"],
            *(card["context"][field] for field in CONTEXT_FIELDS),
        )
    )
    prediction_bytes = _csv_bytes(PREDICTION_COLUMNS, prediction_rows)
    cards_bytes = b"".join(_compact_json_line(card) for card in cards)
    manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "prediction_schema_version": PREDICTION_SCHEMA_VERSION,
        "resolved_configuration": {
            "method": model["method"],
            **model["resolved_configuration"],
            "llm_adjudication_used": False,
        },
        "software": {
            "cypshift": __version__,
            "source_revision": __release_tag__,
            "python": platform.python_version(),
            "rdkit": rdBase.rdkitVersion,
        },
        "input_hashes": {
            **dict(dataset.hashes),
            "model.json": model_version,
            "split.csv": actual_split_hash,
        },
        "output_hashes": {
            "predictions.csv": sha256(prediction_bytes).hexdigest(),
            "prediction_cards.jsonl": sha256(cards_bytes).hexdigest(),
        },
        "summary": {
            "predictions": len(prediction_rows),
            "molecules": len(
                {
                    row["molecule_id"] for row in prediction_rows
                }
            ),
            "contexts_supported": len(contexts),
            "contexts_unsupported": len(unsupported_contexts),
            "quarantined_molecules_excluded": sum(
                molecule.status is MoleculeStatus.QUARANTINED
                for molecule in dataset.molecules
            ),
        },
        "deterministic": True,
    }
    manifest_bytes = _json_bytes(manifest)

    output_directory.mkdir(parents=True, exist_ok=True)
    _write_new(predictions_path, prediction_bytes)
    _write_new(cards_path, cards_bytes)
    _write_new(manifest_path, manifest_bytes)
    return PredictionResult(
        predictions_path=predictions_path,
        prediction_cards_path=cards_path,
        manifest_path=manifest_path,
        prediction_count=len(prediction_rows),
        supported_context_count=len(contexts),
        unsupported_context_count=len(unsupported_contexts),
    )


def load_audited_dataset(data_directory: Path) -> AuditedDataset:
    """Load and validate the three canonical artifacts produced by audit."""

    audit_path = data_directory / "audit.json"
    molecules_path = data_directory / "molecules.csv"
    measurements_path = data_directory / "measurements.csv"
    audit_report = _read_json(audit_path)
    if audit_report.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise BaselineError(
            f"unsupported audit schema: {audit_report.get('schema_version')!r}"
        )
    molecule_rows = _read_csv(molecules_path, MOLECULE_OUTPUT_COLUMNS)
    measurement_rows = _read_csv(measurements_path, MEASUREMENT_COLUMNS)
    try:
        molecules = tuple(
            MoleculeRecord.from_mapping(row) for row in molecule_rows
        )
        measurements = tuple(
            MeasurementRecord.from_mapping(row) for row in measurement_rows
        )
    except RecordError as exc:
        raise BaselineError(f"invalid audited data: {exc}") from exc

    molecule_ids = {molecule.molecule_id for molecule in molecules}
    unknown_ids = sorted(
        {
            measurement.molecule_id
            for measurement in measurements
            if measurement.molecule_id not in molecule_ids
        }
    )
    if unknown_ids:
        raise BaselineError(
            "canonical measurements reference unknown molecules: "
            + ", ".join(unknown_ids)
        )
    return AuditedDataset(
        molecules=molecules,
        measurements=measurements,
        hashes={
            "audit.json": _file_hash(audit_path),
            "molecules.csv": _file_hash(molecules_path),
            "measurements.csv": _file_hash(measurements_path),
        },
    )


def _make_split(
    molecules: Sequence[MoleculeRecord], seed: int, validation_fraction: float
) -> list[dict[str, str]]:
    accepted_hashes = sorted(
        {
            molecule.standardized_structure_hash
            for molecule in molecules
            if molecule.status is MoleculeStatus.ACCEPTED
            and molecule.standardized_structure_hash is not None
        }
    )
    if len(accepted_hashes) < 2:
        raise BaselineError(
            "at least two distinct accepted standardized structures are required"
        )
    ranked_hashes = sorted(
        accepted_hashes,
        key=lambda value: sha256(f"{seed}:{value}".encode()).hexdigest(),
    )
    validation_count = min(
        len(ranked_hashes) - 1,
        max(1, int(len(ranked_hashes) * validation_fraction + 0.5)),
    )
    validation_hashes = set(ranked_hashes[:validation_count])
    rows = []
    for molecule in sorted(molecules, key=lambda item: item.molecule_id):
        structure_hash = molecule.standardized_structure_hash
        if molecule.status is MoleculeStatus.QUARANTINED:
            partition = "excluded"
        elif structure_hash in validation_hashes:
            partition = "validation"
        else:
            partition = "train"
        rows.append(
            {
                "molecule_id": molecule.molecule_id,
                "standardized_structure_hash": structure_hash or "",
                "partition": partition,
                "split_schema_version": SPLIT_SCHEMA_VERSION,
                "seed": str(seed),
            }
        )
    return rows


def _context(measurement: MeasurementRecord) -> AssayContext:
    return (
        measurement.endpoint,
        measurement.isoform,
        measurement.nadph_condition,
        measurement.probe,
        measurement.readout,
        measurement.unit,
    )


def _read_csv(path: Path, expected_columns: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = tuple(reader.fieldnames or ())
            if columns != tuple(expected_columns):
                raise BaselineError(
                    f"{path.name} columns do not match its canonical schema"
                )
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise BaselineError(
                        f"{path.name} row {reader.line_num} has the wrong "
                        "number of fields"
                    )
                rows.append(
                    {
                        column: cast(str, row[column])
                        for column in expected_columns
                    }
                )
            return rows
    except OSError as exc:
        raise BaselineError(f"cannot read {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BaselineError(f"{path.name} must contain a JSON object")
    return value


def _file_hash(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BaselineError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _combined_hash(hashes: Mapping[str, str]) -> str:
    canonical = "\n".join(f"{key}={hashes[key]}" for key in sorted(hashes))
    return sha256(canonical.encode()).hexdigest()


def _require_absent(paths: Iterable[Path]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise BaselineError(
            "refusing to overwrite existing artifacts: " + ", ".join(existing)
        )


def _csv_bytes(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> bytes:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact_json_line(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except OSError as exc:
        raise BaselineError(f"cannot write {path}: {exc}") from exc


def _required_model_text(context: Mapping[str, Any], field: str) -> str:
    value = context.get(field)
    if not isinstance(value, str) or not value:
        raise BaselineError(f"model context requires text field {field!r}")
    return value


def _required_model_number(context: Mapping[str, Any], field: str) -> float:
    value = context.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BaselineError(f"model context requires numeric field {field!r}")
    return float(value)


def _required_model_int(context: Mapping[str, Any], field: str) -> int:
    value = context.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BaselineError(f"model context requires positive integer {field!r}")
    return value
