"""Execution and candidate authority boundary for the private R5C inner scorer."""

from __future__ import annotations

import csv
import importlib.metadata
import io
import json
import math
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast

from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    candidate_id,
    cell_id,
    fragment_id,
)
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    read_exact_root,
    read_stable_file,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY, SOURCE_PARENT_FILES
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
ROOT_LOCK: Final = ROOT / "uv.lock"
ROOT_LOCK_SHA256: Final = (
    "33d9382256de7992ce9ff7a7edc125d4771546a25ef3be5f1160627846d2c9b6"
)
LEARNED_SYSTEMS: Final = ("C2", "C3", "T0", "A0", "A1", "A2")
PAIR_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_private_prediction_fragment.v1"
PAIR_STATUS: Final = "R5_ORACLE_PAIR_CELL_COMPLETE"
D070_RUNNER_SOURCE_FILES: Final = (
    "research/maplight-fixed/run_r5_oracle_pair_cell.py",
    "src/cypshift/audit.py",
    "src/cypshift/chemistry.py",
    "src/cypshift/openadmet_cyp.py",
    "src/cypshift/openadmet_oracle_cell_io.py",
    "src/cypshift/openadmet_oracle_cell_validation.py",
    "src/cypshift/openadmet_oracle_controls.py",
    "src/cypshift/openadmet_oracle_geometry_validation.py",
    "src/cypshift/openadmet_oracle_models.py",
    "src/cypshift/openadmet_oracle_pair_cell.py",
    "src/cypshift/openadmet_oracle_pair_cell_io.py",
    "src/cypshift/openadmet_oracle_projection.py",
    "src/cypshift/openadmet_oracle_validation.py",
    "src/cypshift/openadmet_topology.py",
    "src/cypshift/openadmet_transformation_compiler.py",
    "src/cypshift/openadmet_transformation_coverage.py",
    "src/cypshift/openadmet_transformation_io.py",
    "src/cypshift/openadmet_transformations.py",
    "src/cypshift/openadmet_transformation_mmp.py",
    "src/cypshift/openadmet_transformation_projection.py",
    "src/cypshift/openadmet_transformation_serialization.py",
    "src/cypshift/openadmet_transformation_stereo.py",
    "src/cypshift/openadmet_transformation_support.py",
    "src/cypshift/openadmet_transformation_types.py",
    "src/cypshift/openadmet_validation.py",
    "src/cypshift/openadmet_validation_contract.py",
    "src/cypshift/schema.py",
)
SCORER_SOURCE_FILES: Final = tuple(
    sorted(
        {
            *D070_RUNNER_SOURCE_FILES,
            "src/cypshift/openadmet_oracle_inner.py",
            "src/cypshift/openadmet_oracle_inner_io.py",
            "src/cypshift/openadmet_oracle_private_io.py",
            "src/cypshift/openadmet_oracle_scoring.py",
            "src/cypshift/openadmet_oracle_sealed.py",
            "src/cypshift/openadmet_oracle_statistics.py",
        }
    )
)
EXPECTED_RUNTIME: Final = {
    "platform": "Linux x86_64 CPU",
    "python_version": "3.12.3",
    "numpy_version": "2.5.2",
    "sklearn_version": "1.9.0",
    "rdkit_version": "2026.3.5",
    "uv_lock_sha256": ROOT_LOCK_SHA256,
}


class OracleInnerIOError(ValueError):
    """The scorer execution or one accepted D-070 candidate differs."""


@dataclass(frozen=True, slots=True)
class CandidateFragmentInput:
    """One independently receipt-bound D-070 inner candidate fragment root."""

    system_id: str
    repeat: int
    outer_fold: int
    inner_fold: int
    alpha: float | None
    lambda_value: float | None
    root: Path
    expected_manifest_sha256: str
    expected_operation_accounting: Mapping[str, int]

    def __post_init__(self) -> None:
        """Snapshot coordinator counts so callers cannot mutate them in flight."""

        object.__setattr__(
            self,
            "expected_operation_accounting",
            MappingProxyType(dict(self.expected_operation_accounting)),
        )


@dataclass(frozen=True, slots=True)
class LoadedCandidate:
    """One authenticated immutable D-070 prediction fragment."""

    source: CandidateFragmentInput
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, str], ...]
    fragment: bytes


def scorer_source_bundle_sha256() -> str:
    """Hash the complete reviewed scorer execution source set."""

    return _source_bundle_sha256(SCORER_SOURCE_FILES)


def candidate_runner_source_bundle_sha256() -> str:
    """Recompute the exact accepted 27-file D-070 runner source bundle."""

    return _source_bundle_sha256(D070_RUNNER_SOURCE_FILES)


def validate_execution(
    *, expected_scorer_source_sha256: str, expected_candidate_source_sha256: str
) -> tuple[str, str, Mapping[str, str]]:
    """Fail before private input open on scorer source/runtime drift."""

    _digest(expected_scorer_source_sha256, "scorer source")
    _digest(expected_candidate_source_sha256, "D-070 source")
    receipts = _source_receipts(SCORER_SOURCE_FILES)
    observed_source = _bundle_sha256(SCORER_SOURCE_FILES, receipts)
    if observed_source != expected_scorer_source_sha256:
        raise OracleInnerIOError("scorer source bundle differs")
    observed_candidate_source = _bundle_sha256(D070_RUNNER_SOURCE_FILES, receipts)
    if observed_candidate_source != expected_candidate_source_sha256:
        raise OracleInnerIOError("D-070 source bundle differs")
    runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(read_stable_file(ROOT_LOCK)).hexdigest(),
    }
    if runtime != EXPECTED_RUNTIME:
        raise OracleInnerIOError("scorer runtime differs")
    return observed_source, observed_candidate_source, runtime


def load_candidate(
    source: CandidateFragmentInput, *, expected_runner_source_sha256: str
) -> LoadedCandidate:
    """Authenticate one exact accepted D-070 candidate root and semantics."""

    observed_runner_source = candidate_runner_source_bundle_sha256()
    if observed_runner_source != expected_runner_source_sha256:
        raise OracleInnerIOError("D-070 source bundle differs")
    return _load_candidate_after_source_gate(source, observed_runner_source)


def _load_candidate_after_source_gate(
    source: CandidateFragmentInput, expected_runner_source_sha256: str
) -> LoadedCandidate:
    """Open one candidate after the enclosing scorer authenticated D-070 source."""

    _digest(source.expected_manifest_sha256, "candidate manifest")
    validate_expected_accounting(source.expected_operation_accounting, source.system_id)
    try:
        data = read_exact_root(
            source.root, ("manifest.json", "prediction_fragment.csv")
        )
    except OraclePrivateIOError as exc:
        raise OracleInnerIOError(str(exc)) from exc
    manifest_data = data["manifest.json"]
    if sha256(manifest_data).hexdigest() != source.expected_manifest_sha256:
        raise OracleInnerIOError("candidate manifest receipt differs")
    manifest = _canonical_object(manifest_data, "candidate manifest")
    expected_fields = {
        "schema_version",
        "status",
        "contract_sha256",
        "runner_source_sha256",
        "scope",
        "system_id",
        "candidate_id",
        "cell_id",
        "fragment_id",
        "capability_binding",
        "g0_bindings",
        "runtime",
        "operation_accounting",
        "prediction_fragment",
        "authority",
    }
    alpha, lambda_value = source.alpha, source.lambda_value
    expected_candidate = candidate_id(source.system_id, alpha, lambda_value)
    expected_cell = cell_id(
        "inner",
        source.repeat,
        source.outer_fold,
        source.inner_fold,
        source.system_id,
        expected_candidate,
        "all",
        alpha=alpha,
        lambda_=lambda_value,
    )
    expected_fragment = fragment_id(
        "inner",
        source.repeat,
        source.outer_fold,
        source.inner_fold,
        source.system_id,
        expected_candidate,
        "all",
        expected_cell,
    )
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != PAIR_SCHEMA
        or manifest.get("status") != PAIR_STATUS
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("runner_source_sha256") != expected_runner_source_sha256
        or manifest.get("runtime") != EXPECTED_RUNTIME
        or manifest.get("authority") != DENIED_AUTHORITY
        or manifest.get("scope")
        != {
            "stage": "inner",
            "repeat": source.repeat,
            "outer_fold": source.outer_fold,
            "inner_fold": source.inner_fold,
        }
        or manifest.get("system_id") != source.system_id
        or manifest.get("candidate_id") != expected_candidate
        or manifest.get("cell_id") != expected_cell
        or manifest.get("fragment_id") != expected_fragment
    ):
        raise OracleInnerIOError("candidate D-070 binding differs")
    _validate_capability(manifest.get("capability_binding"), source.system_id)
    _validate_g0_bindings(
        manifest.get("g0_bindings"),
        _object(manifest.get("capability_binding"), "candidate capability").get(
            "g0_manifest_sha256"
        ),
    )
    _validate_accounting(
        manifest.get("operation_accounting"),
        source.expected_operation_accounting,
        source.system_id,
    )
    fragment = data["prediction_fragment.csv"]
    expected_receipt = {
        "path": "prediction_fragment.csv",
        "sha256": sha256(fragment).hexdigest(),
        "bytes": len(fragment),
        "rows": fragment.count(b"\n") - 1,
        "columns": list(FRAGMENT_COLUMNS),
    }
    if (
        _object(manifest.get("prediction_fragment"), "candidate fragment")
        != expected_receipt
    ):
        raise OracleInnerIOError("candidate fragment receipt differs")
    rows = tuple(_csv_rows(fragment, FRAGMENT_COLUMNS, "candidate fragment"))
    _validate_rows(rows, source, expected_candidate)
    return LoadedCandidate(source, manifest, rows, fragment)


def _validate_capability(value: Any, system_id: str) -> None:
    capability = _object(value, "candidate capability")
    if set(capability) != {
        "model_public_manifest_sha256",
        "target_manifest_sha256",
        "target_kind",
        "g0_manifest_sha256",
        "system_id",
        "source_bundle_binding",
        "selection_token",
    }:
        raise OracleInnerIOError("candidate capability fields differ")
    target_kind = "c3-target" if system_id == "C3" else "cell-target"
    if (
        capability.get("system_id") != system_id
        or capability.get("target_kind") != target_kind
        or capability.get("selection_token") is not None
    ):
        raise OracleInnerIOError("candidate capability system differs")
    for name in ("model_public_manifest_sha256", "target_manifest_sha256"):
        _digest(capability.get(name), f"candidate capability {name}")
    g0 = capability.get("g0_manifest_sha256")
    receipts = g0 if isinstance(g0, list) else [g0]
    if not receipts:
        raise OracleInnerIOError("candidate G0 capability is empty")
    for receipt in receipts:
        _digest(receipt, "candidate G0 manifest")
    binding = _object(capability.get("source_bundle_binding"), "source binding")
    if set(binding) != {
        "manifest_receipt",
        "schema_version",
        "contract_sha256",
        "parent_receipts",
        "input_receipts",
        "source_receipts",
    } or (
        binding.get("schema_version")
        != "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
        or binding.get("contract_sha256")
        != "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
    ):
        raise OracleInnerIOError("candidate source binding differs")
    manifest_receipt = _object(binding.get("manifest_receipt"), "source manifest")
    if set(manifest_receipt) != {"sha256", "bytes"}:
        raise OracleInnerIOError("candidate source manifest differs")
    _digest(manifest_receipt.get("sha256"), "candidate source manifest")
    if type(manifest_receipt.get("bytes")) is not int or manifest_receipt["bytes"] < 0:
        raise OracleInnerIOError("candidate source manifest differs")
    parents = _object(binding.get("parent_receipts"), "source parents")
    inputs = _object(binding.get("input_receipts"), "source inputs")
    sources = _object(binding.get("source_receipts"), "source receipts")
    if (
        set(parents) != set(SOURCE_PARENT_FILES)
        or set(inputs) != set(parents)
        or inputs != sources
    ):
        raise OracleInnerIOError("candidate source receipts differ")
    for name in SOURCE_PARENT_FILES:
        _digest(parents[name], f"candidate source parent: {name}")
        record = _object(inputs[name], f"candidate source input: {name}")
        if (
            set(record) != {"sha256", "bytes"}
            or record.get("sha256") != parents[name]
            or type(record.get("bytes")) is not int
            or record["bytes"] < 0
        ):
            raise OracleInnerIOError("candidate source input differs")


def _validate_accounting(
    value: Any, expected_value: Mapping[str, int], system_id: str
) -> None:
    accounting = _object(value, "candidate accounting")
    expected = dict(expected_value)
    if (
        set(accounting) != set(ACCOUNTING_FIELDS)
        or set(expected) != set(ACCOUNTING_FIELDS)
        or any(
            type(item) is not int or item < 0
            for item in (*accounting.values(), *expected.values())
        )
        or accounting != expected
    ):
        raise OracleInnerIOError("candidate accounting fields differ")
    expected_fits = {
        "C2": (1, 0),
        "C3": (1, 1),
        "T0": (1, 1),
        "A0": (0, 1),
        "A1": (0, 1),
        "A2": (1, 0),
    }[system_id]
    if (
        accounting["ridge_model_fits"] != expected_fits[0]
        or accounting["hierarchy_fits"] != expected_fits[1]
        or accounting["maplight_model_fits"] != 0
        or accounting["predictions_frozen"] != 0
        or accounting["query_truth_values_opened_by_scorers"] != 0
        or accounting["internal_absolute_error_evaluations"] != 0
        or any(accounting[name] for name in ACCOUNTING_FIELDS[8:])
        or accounting["direct_target_values_parsed"] <= 0
        or (system_id == "C3" and accounting["anchor_labels_exposed_to_models"] != 0)
        or (
            system_id != "C3"
            and accounting["anchor_labels_exposed_to_models"]
            > accounting["direct_target_values_parsed"]
        )
    ):
        raise OracleInnerIOError("candidate per-system accounting differs")


def validate_expected_accounting(value: Mapping[str, int], system_id: str) -> None:
    """Validate a trusted replay's exact expected per-candidate accounting."""

    if system_id not in LEARNED_SYSTEMS:
        raise OracleInnerIOError("candidate accounting system differs")
    _validate_accounting(dict(value), value, system_id)


def _source_receipts(paths: Sequence[str]) -> dict[str, str]:
    return {name: sha256(read_stable_file(ROOT / name)).hexdigest() for name in paths}


def _bundle_sha256(paths: Sequence[str], receipts: Mapping[str, str]) -> str:
    material = "".join(f"{name}|{receipts[name]}\n" for name in sorted(paths))
    return sha256(material.encode()).hexdigest()


def _source_bundle_sha256(paths: Sequence[str]) -> str:
    return _bundle_sha256(paths, _source_receipts(paths))


def _validate_g0_bindings(value: Any, capability_receipts: Any) -> None:
    if not isinstance(value, list) or not value:
        raise OracleInnerIOError("candidate G0 bindings differ")
    expected_fields = {
        "binding_sha256",
        "g0_manifest_sha256",
        "g0_prediction_fragment_sha256",
        "episode_id",
        "episode_target_manifest_sha256",
        "r3c_parameter_record_sha256",
        "g0_source_bundle_sha256",
    }
    observed_receipts: list[str] = []
    episodes: set[str] = set()
    for item in value:
        record = _object(item, "candidate G0 binding")
        if set(record) != expected_fields:
            raise OracleInnerIOError("candidate G0 binding fields differ")
        for name in expected_fields - {"episode_id"}:
            _digest(record[name], f"candidate G0 binding: {name}")
        episode = record["episode_id"]
        if not isinstance(episode, str) or not episode or episode in episodes:
            raise OracleInnerIOError("candidate G0 episode binding differs")
        episodes.add(episode)
        observed_receipts.append(record["g0_manifest_sha256"])
    expected = (
        capability_receipts
        if isinstance(capability_receipts, list)
        else [capability_receipts]
    )
    if observed_receipts != expected:
        raise OracleInnerIOError("candidate G0 capability receipts differ")


def _validate_rows(
    rows: Sequence[Mapping[str, str]],
    source: CandidateFragmentInput,
    expected_candidate: str,
) -> None:
    if not rows:
        raise OracleInnerIOError("candidate fragment is empty")
    keys: set[tuple[str, str, str]] = set()
    for row in rows:
        key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
        if (
            key in keys
            or row["system_id"] != source.system_id
            or row["candidate_id"] != expected_candidate
            or row["repeat"] != str(source.repeat)
            or row["outer_fold"] != str(source.outer_fold)
            or row["inner_fold"] != str(source.inner_fold)
            or row["episode_policy_id"] != "selected_anchor"
        ):
            raise OracleInnerIOError("candidate fragment row binding differs")
        keys.add(key)
        _finite(row["prediction"], "candidate prediction", canonical=True)
    observed = [(row["episode_id"], int(row["query_rank"])) for row in rows]
    if observed != sorted(observed):
        raise OracleInnerIOError("candidate fragment row order differs")


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OracleInnerIOError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OracleInnerIOError(f"{label} columns differ")
        return [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise OracleInnerIOError(f"{label} is invalid") from exc


def _canonical_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleInnerIOError(str(exc)) from exc
    expected = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    if expected != data:
        raise OracleInnerIOError(f"{label} is not canonical")
    return value


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OracleInnerIOError(f"{label} is not an object")
    return cast(dict[str, Any], value)


def _finite(value: str, label: str, *, canonical: bool = False) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleInnerIOError(f"{label} is not finite") from exc
    if not math.isfinite(result) or (canonical and format(result, ".17g") != value):
        raise OracleInnerIOError(f"{label} is not finite")
    return result


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleInnerIOError(f"{label} is not SHA-256")
    return value


__all__ = [
    "D070_RUNNER_SOURCE_FILES",
    "EXPECTED_RUNTIME",
    "LEARNED_SYSTEMS",
    "SCORER_SOURCE_FILES",
    "CandidateFragmentInput",
    "LoadedCandidate",
    "OracleInnerIOError",
    "candidate_runner_source_bundle_sha256",
    "load_candidate",
    "scorer_source_bundle_sha256",
    "validate_execution",
    "validate_expected_accounting",
]
