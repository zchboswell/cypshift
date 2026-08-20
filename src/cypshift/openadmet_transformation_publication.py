"""Atomic terminal publication for accepted R4 transformation coverage bytes."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from cypshift.openadmet_transformation_compiler import (
    PAIR_COLUMNS,
    TransformationGeometry,
    _pair_csv,
)
from cypshift.openadmet_transformation_coverage import (
    OpenADMETTransformationCoverageError,
    ProjectionBundle,
)
from cypshift.openadmet_transformation_io import (
    NO_TARGET_ACCOUNTING,
    canonical_csv_bytes,
    canonical_json_bytes,
    strict_json_object,
)
from cypshift.openadmet_transformation_projection import (
    _check_destination,
    _cleanup_stage,
    _readonly_tree,
    _rename_noreplace,
    _safe_output_parent,
    _write_new,
)
from cypshift.openadmet_transformation_serialization import (
    CONTRACT_SHA256,
    EPISODE_COLUMNS,
    serialize_transformation_results,
)
from cypshift.openadmet_transformation_support import (
    TransformationSupport,
    compile_transformation_support,
)

MANIFEST_SCHEMA_VERSION: Final[str] = (
    "cypshift.openadmet_cyp_2026.transformation_coverage_manifest.v5"
)
FAILURE_SCHEMA_VERSION: Final[str] = (
    "cypshift.openadmet_cyp_2026.transformation_coverage_failure.v5"
)
SUCCESS_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED",
        "R4_TRANSFORMATION_COVERAGE_SUPPORTED",
    }
)
TERMINAL_CODES: Final[frozenset[str]] = frozenset(
    {"C1", "C5", "P1", "P2", "P5", "P6", "V1", "V2", "V4"}
)
SUCCESS_FILES: Final[tuple[str, ...]] = (
    "transformation_pairs.csv",
    "episode_transformations.csv",
    "transformation_coverage.json",
    "manifest.json",
)
_RUNTIME_KEYS: Final[frozenset[str]] = frozenset(
    {"python_version", "rdkit_version", "platform", "device", "seed", "code_commit"}
)
_AUTHORITY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "geometry_coverage",
        "oracle_contract_freeze",
        "model_fits",
        "predictions",
        "metrics",
        "official_st_rae",
        "test_access",
        "tdi",
        "submissions",
        "transduction",
    }
)
_COVERAGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "contract_sha256",
        "status",
        "counts",
        "status_partition",
        "fractions",
        "frequency_units",
        "exact_transformation_frequency",
        "transformation_class_frequency",
        "independent_group_support",
        "valid_changed_heavy_atom_fraction_distribution",
        "cross_cyp_valid_transformation_sharing",
        "test_query_coverage",
        "selected_anchor_structural_coverage",
        "local_cyp3a4_state",
        "accounting",
        "authority",
    }
)


@dataclass(frozen=True, slots=True)
class TransformationPublicationResult:
    """One atomically published terminal directory."""

    output_directory: Path
    status: str
    manifest_path: Path


def publish_transformation_coverage(
    *,
    destination: Path,
    bundle: ProjectionBundle,
    geometry: TransformationGeometry,
    support: TransformationSupport,
    runtime: Mapping[str, Any],
    expected_episode_rows: int = 1818,
) -> TransformationPublicationResult:
    """Validate, receipt, and atomically publish one success terminal."""

    _check_destination(destination)
    runtime_value = _runtime(runtime)
    ordered_pairs = tuple(
        sorted(geometry.pairs, key=lambda item: item.result.transformation_pair_id)
    )
    pair_ids = [item.result.transformation_pair_id for item in ordered_pairs]
    if len(pair_ids) != len(set(pair_ids)):
        raise OpenADMETTransformationCoverageError("duplicate transformation pair")
    if support != compile_transformation_support(bundle, geometry):
        raise OpenADMETTransformationCoverageError("support facts differ")
    serialization = serialize_transformation_results(geometry, support)
    payloads = {
        "transformation_pairs.csv": _pair_csv(ordered_pairs),
        "episode_transformations.csv": serialization.episode_transformations_csv,
        "transformation_coverage.json": serialization.transformation_coverage_json,
    }
    coverage = _coverage(payloads["transformation_coverage.json"])
    _csv_rows(payloads["transformation_pairs.csv"], PAIR_COLUMNS, "pairs")
    episode_rows = _csv_rows(
        payloads["episode_transformations.csv"], EPISODE_COLUMNS, "episodes"
    )
    if episode_rows != expected_episode_rows:
        raise OpenADMETTransformationCoverageError("episode output rows differ")
    parent = _safe_output_parent(destination)
    stage: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=".r4-coverage-", dir=parent))
        for name, data in payloads.items():
            _write_new(stage / name, data)
        receipts = _reopen_payloads(stage, payloads, expected_episode_rows)
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "status": coverage["status"],
            "contract_sha256": CONTRACT_SHA256,
            "input_receipts": _input_receipts(bundle),
            "source_receipts": _source_receipts(bundle),
            "output_receipts": receipts,
            "runtime": runtime_value,
            "accounting": dict(NO_TARGET_ACCOUNTING),
            "authority": coverage["authority"],
        }
        _write_new(stage / "manifest.json", canonical_json_bytes(manifest))
        _validate_success_stage(stage, manifest, payloads, expected_episode_rows)
        _readonly_tree(stage)
        _check_destination(destination)
        _rename_noreplace(stage, destination)
        stage = None
    except Exception:
        _cleanup_stage(stage)
        raise
    return TransformationPublicationResult(
        destination, coverage["status"], destination / "manifest.json"
    )


def publish_transformation_failure(
    *,
    destination: Path,
    terminal_codes: Sequence[str],
    runtime: Mapping[str, Any],
) -> TransformationPublicationResult:
    """Atomically publish the exact one-file post-gate failure terminal."""

    _check_destination(destination)
    runtime_value = _runtime(runtime)
    codes = sorted(set(terminal_codes))
    if not codes or any(code not in TERMINAL_CODES for code in codes):
        raise OpenADMETTransformationCoverageError("invalid terminal failure codes")
    authority = _failed_authority()
    receipt = {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "contract_sha256": CONTRACT_SHA256,
        "status": "R4_TRANSFORMATION_COVERAGE_FAILED",
        "terminal_integrity_failure_codes": codes,
        "accounting": dict(NO_TARGET_ACCOUNTING),
        "runtime": runtime_value,
        "authority": authority,
    }
    data = canonical_json_bytes(receipt)
    parent = _safe_output_parent(destination)
    stage: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=".r4-coverage-failure-", dir=parent))
        _write_new(stage / "failure_receipt.json", data)
        if {path.name for path in stage.iterdir()} != {"failure_receipt.json"}:
            raise OpenADMETTransformationCoverageError("failure file set differs")
        path = stage / "failure_receipt.json"
        if path.is_symlink() or not path.is_file():
            raise OpenADMETTransformationCoverageError("failure receipt is not regular")
        if path.read_bytes() != data:
            raise OpenADMETTransformationCoverageError("failure receipt differs")
        if strict_json_object(data, "failure receipt") != receipt:
            raise OpenADMETTransformationCoverageError("failure receipt schema differs")
        _readonly_tree(stage)
        _check_destination(destination)
        _rename_noreplace(stage, destination)
        stage = None
    except Exception:
        _cleanup_stage(stage)
        raise
    return TransformationPublicationResult(
        destination,
        "R4_TRANSFORMATION_COVERAGE_FAILED",
        destination / "failure_receipt.json",
    )


def _coverage(data: bytes) -> dict[str, Any]:
    value = strict_json_object(data, "transformation coverage")
    if canonical_json_bytes(value) != data:
        raise OpenADMETTransformationCoverageError("coverage JSON is not canonical")
    if set(value) != _COVERAGE_KEYS:
        raise OpenADMETTransformationCoverageError("coverage schema differs")
    if value.get("contract_sha256") != CONTRACT_SHA256:
        raise OpenADMETTransformationCoverageError("coverage contract differs")
    status = value.get("status")
    if status not in SUCCESS_STATUSES:
        raise OpenADMETTransformationCoverageError("coverage status differs")
    if not _exact_typed_zero_map(value.get("accounting")):
        raise OpenADMETTransformationCoverageError("coverage accounting differs")
    expected_authority = _success_authority(status)
    if not _exact_typed_map(value.get("authority"), expected_authority):
        raise OpenADMETTransformationCoverageError("coverage authority differs")
    return value


def _runtime(value: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    if set(output) != _RUNTIME_KEYS:
        raise OpenADMETTransformationCoverageError("runtime schema differs")
    expected = {
        "python_version": "3.12.3",
        "rdkit_version": "2026.03.5",
        "platform": "Linux x86_64 CPU",
        "device": "CPU",
        "seed": 0,
    }
    if any(
        type(output[key]) is not type(item) or output[key] != item
        for key, item in expected.items()
    ):
        raise OpenADMETTransformationCoverageError("runtime value differs")
    commit = output["code_commit"]
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise OpenADMETTransformationCoverageError("runtime commit differs")
    return output


def _input_receipts(bundle: ProjectionBundle) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in sorted(bundle.input_receipts, key=lambda row: row.name):
        if item.name in output:
            raise OpenADMETTransformationCoverageError("duplicate input receipt")
        if not _positive_int(item.bytes) or not _sha256(item.sha256):
            raise OpenADMETTransformationCoverageError("input receipt value differs")
        if item.name == "manifest.json":
            if item.rows is not None or item.columns:
                raise OpenADMETTransformationCoverageError("manifest receipt differs")
            output[item.name] = {"bytes": item.bytes, "sha256": item.sha256}
        else:
            expected_columns = _projection_columns().get(item.name)
            if (
                not _nonnegative_int(item.rows)
                or expected_columns is None
                or item.columns != expected_columns
            ):
                raise OpenADMETTransformationCoverageError("input receipt differs")
            output[item.name] = {
                "bytes": item.bytes,
                "columns": list(item.columns),
                "rows": item.rows,
                "sha256": item.sha256,
            }
    expected = {
        "direct_projection.csv",
        "fold_projection.csv",
        "manifest.json",
        "mask_projection.csv",
        "public_projection.csv",
        "structure_projection.csv",
    }
    if set(output) != expected:
        raise OpenADMETTransformationCoverageError("input receipt set differs")
    return output


def _source_receipts(bundle: ProjectionBundle) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in bundle.source_receipts:
        if (
            item.name in output
            or not _positive_int(item.bytes)
            or not _nonnegative_int(item.rows)
            or not _sha256(item.sha256)
        ):
            raise OpenADMETTransformationCoverageError("source receipt value differs")
        output[item.name] = {
            "bytes": item.bytes,
            "rows": item.rows,
            "sha256": item.sha256,
        }
    expected = {
        "direct_observations.csv",
        "group_folds.csv",
        "masks.csv",
        "public_episodes.csv",
        "structure.csv",
    }
    if len(output) != len(bundle.source_receipts) or set(output) != expected:
        raise OpenADMETTransformationCoverageError("source receipt set differs")
    return output


def _reopen_payloads(
    stage: Path, expected: Mapping[str, bytes], episode_rows: int
) -> dict[str, dict[str, Any]]:
    observed = {name: (stage / name).read_bytes() for name in expected}
    if observed != expected:
        raise OpenADMETTransformationCoverageError("staged payload differs")
    pair_rows = _csv_rows(observed["transformation_pairs.csv"], PAIR_COLUMNS, "pairs")
    actual_episode_rows = _csv_rows(
        observed["episode_transformations.csv"], EPISODE_COLUMNS, "episodes"
    )
    if actual_episode_rows != episode_rows:
        raise OpenADMETTransformationCoverageError("staged episode rows differ")
    _coverage(observed["transformation_coverage.json"])
    return {
        "transformation_pairs.csv": _csv_receipt(
            observed["transformation_pairs.csv"], PAIR_COLUMNS, pair_rows
        ),
        "episode_transformations.csv": _csv_receipt(
            observed["episode_transformations.csv"],
            EPISODE_COLUMNS,
            actual_episode_rows,
        ),
        "transformation_coverage.json": _json_receipt(
            observed["transformation_coverage.json"]
        ),
    }


def _validate_success_stage(
    stage: Path,
    manifest: Mapping[str, Any],
    expected_payloads: Mapping[str, bytes],
    episode_rows: int,
) -> None:
    if {path.name for path in stage.iterdir()} != set(SUCCESS_FILES):
        raise OpenADMETTransformationCoverageError("terminal file set differs")
    manifest_data = (stage / "manifest.json").read_bytes()
    if canonical_json_bytes(manifest) != manifest_data:
        raise OpenADMETTransformationCoverageError("terminal manifest differs")
    parsed = strict_json_object(manifest_data, "coverage manifest")
    if parsed != manifest:
        raise OpenADMETTransformationCoverageError("terminal manifest schema differs")
    receipts = _reopen_payloads(stage, expected_payloads, episode_rows)
    if receipts != manifest["output_receipts"]:
        raise OpenADMETTransformationCoverageError("terminal output receipt differs")


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> int:
    try:
        reader = csv.DictReader(
            io.StringIO(data.decode("utf-8"), newline=""), strict=True
        )
        if reader.fieldnames != list(columns):
            raise OpenADMETTransformationCoverageError(f"{label} columns differ")
        rows: list[dict[str, str]] = []
        for raw in reader:
            if set(raw) != set(columns) or any(value is None for value in raw.values()):
                raise OpenADMETTransformationCoverageError(f"{label} row width differs")
            rows.append({column: raw[column] for column in columns})
    except (UnicodeDecodeError, csv.Error) as exc:
        raise OpenADMETTransformationCoverageError(f"invalid {label} CSV") from exc
    if canonical_csv_bytes(columns, rows) != data:
        raise OpenADMETTransformationCoverageError(f"{label} CSV is not canonical")
    return len(rows)


def _csv_receipt(data: bytes, columns: Sequence[str], rows: int) -> dict[str, Any]:
    return {
        "bytes": len(data),
        "columns": list(columns),
        "rows": rows,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _json_receipt(data: bytes) -> dict[str, Any]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _success_authority(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "geometry_coverage": True,
        "oracle_contract_freeze": status == "R4_TRANSFORMATION_COVERAGE_SUPPORTED",
        "model_fits": False,
        "predictions": False,
        "metrics": False,
        "official_st_rae": False,
        "test_access": False,
        "tdi": False,
        "submissions": False,
        "transduction": False,
    }


def _failed_authority() -> dict[str, Any]:
    output = {key: False for key in _AUTHORITY_KEYS if key != "status"}
    return {"status": "R4_TRANSFORMATION_COVERAGE_FAILED", **output}


def _exact_typed_zero_map(value: Any) -> bool:
    return _exact_typed_map(value, NO_TARGET_ACCOUNTING)


def _exact_typed_map(value: Any, expected: Mapping[str, Any]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(expected)
        and all(
            type(value[key]) is type(item) and value[key] == item
            for key, item in expected.items()
        )
    )


def _projection_columns() -> dict[str, tuple[str, ...]]:
    from cypshift.openadmet_transformation_coverage import CSV_COLUMNS

    return CSV_COLUMNS


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


__all__ = [
    "FAILURE_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "SUCCESS_FILES",
    "TERMINAL_CODES",
    "TransformationPublicationResult",
    "publish_transformation_coverage",
    "publish_transformation_failure",
]
