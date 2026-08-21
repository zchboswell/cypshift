"""Authenticated private inputs and publication for the R5C outer freezer."""

from __future__ import annotations

import csv
import importlib.metadata
import io
import json
import math
import os
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, cast

from cypshift.openadmet_oracle_freezer_g0 import (
    G0_SOURCE_FILES,
    G0Input,
    LoadedG0,
    OracleOuterG0Error,
)
from cypshift.openadmet_oracle_freezer_g0 import (
    load_g0_roots as _load_g0_roots,
)
from cypshift.openadmet_oracle_inner_io import (
    D070_RUNNER_SOURCE_FILES,
    EXPECTED_RUNTIME,
)
from cypshift.openadmet_oracle_pair_cell import (
    FRAGMENT_COLUMNS,
    candidate_id,
    cell_id,
    fragment_id,
)
from cypshift.openadmet_oracle_pair_cell_io import (
    ACCOUNTING_FIELDS,
    SelectionToken,
    load_selection_token,
)
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    open_directory_no_symlinks,
    read_exact_root,
    read_regular_at,
    read_stable_file,
    validate_output_root,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY, SOURCE_PARENT_FILES
from cypshift.openadmet_oracle_sealed import (
    ELIGIBILITY_COLUMNS,
    RESOLVED_CONTRACT_SHA256,
    SEALED_FILES,
    SEALED_SCHEMA_VERSION,
    SEALED_STATUS,
    V2_CONTRACT_SHA256,
    VALID_TRUE_STATUSES,
)
from cypshift.openadmet_oracle_validation import CLIFF_COLUMNS, TRUTH_COLUMNS
from cypshift.openadmet_transformation_io import strict_json_object

ROOT: Final = Path(__file__).resolve().parents[2]
SYSTEMS: Final = (
    "G0",
    "C0",
    "C1",
    "C2",
    "C3",
    "T0",
    "F0",
    "F1",
    "F2",
    "A0",
    "A1",
    "A2",
)
PAIR_SYSTEMS: Final = SYSTEMS[1:]
TOKEN_SYSTEMS: Final = ("C2", "C3", "T0", "A0", "A1", "A2")
PAIR_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_private_prediction_fragment.v1"
PAIR_STATUS: Final = "R5_ORACLE_PAIR_CELL_COMPLETE"
FREEZE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_outer_prediction_freeze.v1"
FREEZE_STATUS: Final = "R5_ORACLE_OUTER_PREDICTIONS_FROZEN"
FREEZER_SOURCE_FILES: Final = tuple(
    sorted(
        {
            *D070_RUNNER_SOURCE_FILES,
            *G0_SOURCE_FILES,
            "src/cypshift/openadmet_oracle_freezer.py",
            "src/cypshift/openadmet_oracle_freezer_g0.py",
            "src/cypshift/openadmet_oracle_freezer_io.py",
            "src/cypshift/openadmet_oracle_freezer_publish.py",
            "src/cypshift/openadmet_oracle_inner_io.py",
            "src/cypshift/openadmet_oracle_private_io.py",
            "src/cypshift/openadmet_oracle_sealed.py",
        }
    )
)


class OracleOuterFreezerIOError(ValueError):
    """An outer-freezer source, capability, or publication differs."""


@dataclass(frozen=True, slots=True)
class TokenInput:
    """One independently promoted outer selection-token capability."""

    system_id: str
    repeat: int
    outer_fold: int
    alpha: float | None
    lambda_value: float | None
    root: Path
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class FragmentInput:
    """One independently receipt-bound outer pair-system fragment."""

    system_id: str
    repeat: int
    outer_fold: int
    root: Path
    expected_manifest_sha256: str
    expected_operation_accounting: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected_operation_accounting",
            MappingProxyType(dict(self.expected_operation_accounting)),
        )


@dataclass(frozen=True, slots=True)
class EligibilityInput:
    """One v3 outer sealed root exposed only through eligibility transport."""

    repeat: int
    outer_fold: int
    root: Path
    expected_manifest_sha256: str
    expected_operation_accounting: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected_operation_accounting",
            MappingProxyType(dict(self.expected_operation_accounting)),
        )


@dataclass(frozen=True, slots=True)
class LoadedFragment:
    source: FragmentInput
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, str], ...]
    fragment: bytes


@dataclass(frozen=True, slots=True)
class LoadedEligibility:
    source: EligibilityInput
    manifest: Mapping[str, Any]
    rows: tuple[Mapping[str, str], ...]
    data: bytes


def source_bundle_sha256(paths: Sequence[str]) -> str:
    """Hash one declared source closure through no-follow stable reads."""

    receipts = {
        name: sha256(read_stable_file(ROOT / name)).hexdigest() for name in paths
    }
    material = "".join(f"{name}|{receipts[name]}\n" for name in sorted(paths))
    return sha256(material.encode()).hexdigest()


def freezer_source_bundle_sha256() -> str:
    return source_bundle_sha256(FREEZER_SOURCE_FILES)


def pair_runner_source_bundle_sha256() -> str:
    return source_bundle_sha256(D070_RUNNER_SOURCE_FILES)


def g0_source_bundle_sha256() -> str:
    return source_bundle_sha256(G0_SOURCE_FILES)


def validate_execution(
    *,
    expected_freezer_source_sha256: str,
    expected_pair_runner_source_sha256: str,
    expected_g0_source_sha256: str,
) -> tuple[str, str, str, Mapping[str, str]]:
    """Authenticate complete source and root runtime before private inputs open."""

    for value, label in (
        (expected_freezer_source_sha256, "freezer source"),
        (expected_pair_runner_source_sha256, "pair runner source"),
        (expected_g0_source_sha256, "G0 source"),
    ):
        _digest(value, label)
    receipts = {
        name: sha256(read_stable_file(ROOT / name)).hexdigest()
        for name in FREEZER_SOURCE_FILES
    }
    observed_freezer = _bundle(FREEZER_SOURCE_FILES, receipts)
    observed_pair = _bundle(D070_RUNNER_SOURCE_FILES, receipts)
    observed_g0 = _bundle(G0_SOURCE_FILES, receipts)
    if observed_freezer != expected_freezer_source_sha256:
        raise OracleOuterFreezerIOError("freezer source bundle differs")
    if observed_pair != expected_pair_runner_source_sha256:
        raise OracleOuterFreezerIOError("pair runner source bundle differs")
    if observed_g0 != expected_g0_source_sha256:
        raise OracleOuterFreezerIOError("G0 source bundle differs")
    runtime = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "sklearn_version": importlib.metadata.version("scikit-learn"),
        "rdkit_version": importlib.metadata.version("rdkit"),
        "uv_lock_sha256": sha256(read_stable_file(ROOT / "uv.lock")).hexdigest(),
    }
    if runtime != EXPECTED_RUNTIME:
        raise OracleOuterFreezerIOError("freezer runtime differs")
    return observed_freezer, observed_pair, observed_g0, runtime


def load_token(source: TokenInput) -> SelectionToken:
    try:
        return load_selection_token(
            source.root,
            expected_sha256=source.expected_sha256,
            requested_system_id=source.system_id,
            repeat=source.repeat,
            outer_fold=source.outer_fold,
            alpha=source.alpha,
            lambda_=source.lambda_value,
        )
    except ValueError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc


def load_fragment(
    source: FragmentInput,
    *,
    token: SelectionToken | None,
    expected_pair_source_sha256: str,
    expected_g0_manifest_sha256: Sequence[str],
    t0_fragment_sha256: str | None = None,
) -> LoadedFragment:
    """Authenticate one exact outer D-070 fragment without target access."""

    if source.system_id not in PAIR_SYSTEMS:
        raise OracleOuterFreezerIOError("outer fragment system differs")
    _validate_accounting(
        source.expected_operation_accounting,
        source.expected_operation_accounting,
        source.system_id,
    )
    _digest(source.expected_manifest_sha256, "outer fragment manifest")
    try:
        data = read_exact_root(
            source.root, ("manifest.json", "prediction_fragment.csv")
        )
    except OraclePrivateIOError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc
    manifest_data = data["manifest.json"]
    if sha256(manifest_data).hexdigest() != source.expected_manifest_sha256:
        raise OracleOuterFreezerIOError("outer fragment manifest receipt differs")
    manifest = _canonical_object(manifest_data, "outer fragment manifest")
    _validate_pair_manifest(
        manifest,
        source,
        token=token,
        expected_pair_source_sha256=expected_pair_source_sha256,
        expected_g0_manifest_sha256=expected_g0_manifest_sha256,
        t0_fragment_sha256=t0_fragment_sha256,
    )
    fragment = data["prediction_fragment.csv"]
    receipt = {
        "path": "prediction_fragment.csv",
        "sha256": sha256(fragment).hexdigest(),
        "bytes": len(fragment),
        "rows": fragment.count(b"\n") - 1,
        "columns": list(FRAGMENT_COLUMNS),
    }
    if _object(manifest.get("prediction_fragment"), "outer fragment") != receipt:
        raise OracleOuterFreezerIOError("outer fragment receipt differs")
    rows = tuple(_csv_rows(fragment, FRAGMENT_COLUMNS, "outer fragment"))
    _validate_fragment_rows(rows, source, cast(str, manifest["candidate_id"]))
    return LoadedFragment(source, manifest, rows, fragment)


def load_g0_roots(
    source: G0Input,
    *,
    expected_g0_source_sha256: str,
    public_rows: Sequence[Mapping[str, str]],
) -> tuple[LoadedG0, ...]:
    """Translate the cohesive locked-G0 boundary into freezer errors."""

    try:
        return _load_g0_roots(
            source,
            expected_g0_source_sha256=expected_g0_source_sha256,
            public_rows=public_rows,
        )
    except OracleOuterG0Error as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc


def load_eligibility(source: EligibilityInput) -> LoadedEligibility:
    """Read only manifest and eligibility bytes from one exact v3 sealed root."""

    _digest(source.expected_manifest_sha256, "eligibility manifest")
    root_fd = open_directory_no_symlinks(source.root)
    try:
        if os.fstat(root_fd).st_mode & 0o222:
            raise OracleOuterFreezerIOError("eligibility root is writable")
        if set(os.listdir(root_fd)) != set(SEALED_FILES):
            raise OracleOuterFreezerIOError("eligibility root file set differs")
        manifest_data = read_regular_at(root_fd, "manifest.json")
        eligibility = read_regular_at(root_fd, "sealed_episode_eligibility.csv")
    except OraclePrivateIOError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc
    finally:
        os.close(root_fd)
    if sha256(manifest_data).hexdigest() != source.expected_manifest_sha256:
        raise OracleOuterFreezerIOError("eligibility manifest receipt differs")
    manifest = _canonical_object(manifest_data, "eligibility manifest")
    _validate_eligibility_manifest(manifest, source, eligibility)
    rows = tuple(_csv_rows(eligibility, ELIGIBILITY_COLUMNS, "eligibility"))
    _validate_eligibility_rows(rows)
    return LoadedEligibility(source, manifest, rows, eligibility)


def validate_freeze_output(output_root: Path) -> None:
    try:
        validate_output_root(output_root)
    except OraclePrivateIOError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc


def _validate_pair_manifest(
    manifest: Mapping[str, Any],
    source: FragmentInput,
    *,
    token: SelectionToken | None,
    expected_pair_source_sha256: str,
    expected_g0_manifest_sha256: Sequence[str],
    t0_fragment_sha256: str | None,
) -> None:
    fields = {
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
    if (
        set(manifest) != fields
        or manifest.get("schema_version") != PAIR_SCHEMA
        or manifest.get("status") != PAIR_STATUS
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("runner_source_sha256") != expected_pair_source_sha256
        or manifest.get("runtime") != EXPECTED_RUNTIME
        or manifest.get("authority") != DENIED_AUTHORITY
        or manifest.get("scope")
        != {
            "stage": "outer",
            "repeat": source.repeat,
            "outer_fold": source.outer_fold,
            "inner_fold": "",
        }
        or manifest.get("system_id") != source.system_id
    ):
        raise OracleOuterFreezerIOError("outer fragment binding differs")
    capability = _object(manifest.get("capability_binding"), "outer capability")
    _validate_capability(
        capability,
        source.system_id,
        token,
        expected_g0_manifest_sha256,
    )
    alpha: float | None = None
    lambda_value: float | None = None
    if source.system_id in {"C2", "C3", "T0", "F2", "A0", "A1", "A2"}:
        if token is None:
            raise OracleOuterFreezerIOError("outer learned token is missing")
        alpha = token.alpha
        lambda_value = token.lambda_
    token_sha = (
        token.sha256
        if token is not None and source.system_id in {"F0", "F1", "F2"}
        else None
    )
    upstream = t0_fragment_sha256 if source.system_id in {"F0", "F1"} else None
    expected_candidate = candidate_id(
        source.system_id,
        alpha,
        lambda_value,
        selection_token_sha256=token_sha,
        upstream_candidate_receipt_sha256=upstream,
    )
    expected_cell = cell_id(
        "outer",
        source.repeat,
        source.outer_fold,
        None,
        source.system_id,
        expected_candidate,
        "all",
        alpha=alpha,
        lambda_=lambda_value,
        selection_token_sha256=token_sha,
        upstream_candidate_receipt_sha256=upstream,
    )
    expected_fragment = fragment_id(
        "outer",
        source.repeat,
        source.outer_fold,
        None,
        source.system_id,
        expected_candidate,
        "all",
        expected_cell,
        selection_token_sha256=token_sha,
        upstream_candidate_receipt_sha256=upstream,
    )
    if (
        manifest.get("candidate_id") != expected_candidate
        or manifest.get("cell_id") != expected_cell
        or manifest.get("fragment_id") != expected_fragment
    ):
        raise OracleOuterFreezerIOError("outer fragment identity differs")
    _validate_accounting(
        manifest.get("operation_accounting"),
        source.expected_operation_accounting,
        source.system_id,
    )


def _validate_capability(
    capability: Mapping[str, Any],
    system: str,
    token: SelectionToken | None,
    g0_receipts: Sequence[str],
) -> None:
    if set(capability) != {
        "model_public_manifest_sha256",
        "target_manifest_sha256",
        "target_kind",
        "g0_manifest_sha256",
        "system_id",
        "source_bundle_binding",
        "selection_token",
    }:
        raise OracleOuterFreezerIOError("outer capability fields differ")
    for name in ("model_public_manifest_sha256", "target_manifest_sha256"):
        _digest(capability.get(name), f"outer capability {name}")
    expected_kind = "c3-target" if system == "C3" else "cell-target"
    expected_g0: str | list[str] = (
        g0_receipts[0] if len(g0_receipts) == 1 else list(g0_receipts)
    )
    if (
        capability.get("system_id") != system
        or capability.get("target_kind") != expected_kind
        or capability.get("g0_manifest_sha256") != expected_g0
    ):
        raise OracleOuterFreezerIOError("outer capability binding differs")
    _validate_source_binding(
        _object(capability.get("source_bundle_binding"), "outer source binding")
    )
    binding = capability.get("selection_token")
    if token is None:
        if binding is not None:
            raise OracleOuterFreezerIOError("outer token binding differs")
        return
    token_binding = _object(binding, "outer token binding")
    if token_binding != {
        "sha256": token.sha256,
        "system_id": token.system_id,
        "candidate_id": token.candidate_id,
        "candidate_receipt_sha256": token.candidate_receipt_sha256,
        "scorer_receipt_sha256": token.scorer_receipt_sha256,
    }:
        raise OracleOuterFreezerIOError("outer token binding differs")


def _validate_accounting(
    value: Any, expected_value: Mapping[str, int], system: str
) -> None:
    accounting = _object(value, "outer accounting")
    expected = dict(expected_value)
    if (
        set(accounting) != set(ACCOUNTING_FIELDS)
        or set(expected) != set(ACCOUNTING_FIELDS)
        or any(
            type(item) is not int or item < 0
            for item in (*accounting.values(), *expected.values())
        )
        or accounting != expected
        or accounting["predictions_frozen"] != 0
        or accounting["query_truth_values_opened_by_scorers"] != 0
        or accounting["internal_absolute_error_evaluations"] != 0
        or any(accounting[name] for name in ACCOUNTING_FIELDS[8:])
    ):
        raise OracleOuterFreezerIOError("outer accounting differs")
    fits = {
        "C0": (0, 0),
        "C1": (0, 0),
        "C2": (1, 0),
        "C3": (1, 1),
        "T0": (1, 1),
        "F0": (0, 0),
        "F1": (0, 0),
        "F2": (1, 1),
        "A0": (0, 1),
        "A1": (0, 1),
        "A2": (1, 0),
    }[system]
    if (
        accounting["ridge_model_fits"] != fits[0]
        or accounting["hierarchy_fits"] != fits[1]
        or accounting["maplight_model_fits"] != 0
    ):
        raise OracleOuterFreezerIOError("outer per-system accounting differs")


def _validate_fragment_rows(
    rows: Sequence[Mapping[str, str]], source: FragmentInput, candidate: str
) -> None:
    if not rows:
        raise OracleOuterFreezerIOError("outer fragment is empty")
    keys: set[tuple[str, str, str]] = set()
    policies: set[str] = set()
    order: list[tuple[str, int]] = []
    for row in rows:
        key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
        if (
            key in keys
            or row["system_id"] != source.system_id
            or row["candidate_id"] != candidate
            or row["repeat"] != str(source.repeat)
            or row["outer_fold"] != str(source.outer_fold)
            or row["inner_fold"] != ""
            or row["episode_policy_id"]
            not in {"selected_anchor", "deterministic_random_anchor_stress"}
        ):
            raise OracleOuterFreezerIOError("outer fragment row binding differs")
        keys.add(key)
        policies.add(row["episode_policy_id"])
        rank = _canonical_int(row["query_rank"], "outer query rank", minimum=1)
        order.append((row["episode_id"], rank))
        _digest(row["episode_id"], "outer episode")
        _digest(row["component_id"], "outer component")
        value = _finite(row["prediction"], "outer prediction")
        if format(value, ".17g") != row["prediction"]:
            raise OracleOuterFreezerIOError("outer prediction serialization differs")
        if row["local_available"] not in {"true", "false"}:
            raise OracleOuterFreezerIOError("outer local availability differs")
        source_token = row["prediction_source"]
        expected_local_source = (
            source.system_id
            if source.system_id in {"C0", "C1", "F0", "F1"}
            else "LOCAL"
        )
        if source_token not in {"G0", expected_local_source}:
            raise OracleOuterFreezerIOError("outer prediction source differs")
        if (row["local_available"] == "false") != (source_token == "G0"):
            raise OracleOuterFreezerIOError("outer fallback equality differs")
        if row["local_available"] == "true" and source_token != expected_local_source:
            raise OracleOuterFreezerIOError("outer local source differs")
        for name in ("exact_support_components", "class_support_components"):
            _canonical_int(row[name], f"outer {name}")
        if row["similarity"]:
            similarity = _finite(row["similarity"], "outer similarity")
            if format(similarity, ".17g") != row["similarity"]:
                raise OracleOuterFreezerIOError(
                    "outer similarity serialization differs"
                )
    if order != sorted(order) or policies != {
        "selected_anchor",
        "deterministic_random_anchor_stress",
    }:
        raise OracleOuterFreezerIOError("outer fixed superset differs")


def _validate_eligibility_manifest(
    manifest: Mapping[str, Any], source: EligibilityInput, eligibility: bytes
) -> None:
    fields = {
        "schema_version",
        "status",
        "contract_sha256",
        "parent_contract_sha256",
        "root",
        "current_cell_scope",
        "parent_receipts",
        "input_receipts",
        "output_receipts",
        "source_bundle_binding",
        "operation_accounting",
        "authority",
    }
    scope = {
        "stage": "outer",
        "repeat": source.repeat,
        "outer_fold": source.outer_fold,
        "inner_fold": "",
    }
    if (
        set(manifest) != fields
        or manifest.get("schema_version") != SEALED_SCHEMA_VERSION
        or manifest.get("status") != SEALED_STATUS
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("parent_contract_sha256") != V2_CONTRACT_SHA256
        or manifest.get("root") != "sealed-scorer"
        or manifest.get("current_cell_scope") != scope
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleOuterFreezerIOError("eligibility manifest binding differs")
    parents = _object(manifest.get("parent_receipts"), "eligibility parents")
    inputs = _object(manifest.get("input_receipts"), "eligibility inputs")
    if set(parents) != {
        "v2_sealed_manifest_sha256",
        "v2_source_manifest_sha256",
    } or set(inputs) != {
        "v2_sealed_manifest.json",
        "v2_source_manifest.json",
        "episode_truth.csv",
        "activity_cliffs.csv",
    }:
        raise OracleOuterFreezerIOError("eligibility parent/input fields differ")
    for name in parents:
        _digest(parents[name], f"eligibility parent: {name}")
    for name, parent_name in (
        ("v2_sealed_manifest.json", "v2_sealed_manifest_sha256"),
        ("v2_source_manifest.json", "v2_source_manifest_sha256"),
    ):
        record = _object(inputs[name], f"eligibility input: {name}")
        if (
            set(record) != {"sha256", "bytes"}
            or record.get("sha256") != parents[parent_name]
            or type(record.get("bytes")) is not int
            or record["bytes"] < 1
        ):
            raise OracleOuterFreezerIOError("eligibility parent input differs")
    receipts = _object(manifest.get("output_receipts"), "eligibility outputs")
    if set(receipts) != set(SEALED_FILES) - {"manifest.json"}:
        raise OracleOuterFreezerIOError("eligibility output receipt set differs")
    for name, columns in (
        ("episode_truth.csv", TRUTH_COLUMNS),
        ("activity_cliffs.csv", CLIFF_COLUMNS),
    ):
        record = _object(receipts.get(name), f"eligibility receipt: {name}")
        if not _valid_unopened_csv_receipt(record, name, columns):
            raise OracleOuterFreezerIOError("eligibility unopened receipt differs")
        if _object(inputs[name], f"eligibility copied input: {name}") != record:
            raise OracleOuterFreezerIOError("eligibility copied input differs")
    record = _object(
        receipts.get("sealed_episode_eligibility.csv"), "eligibility receipt"
    )
    if record != {
        "relative_path": "sealed_episode_eligibility.csv",
        "sha256": sha256(eligibility).hexdigest(),
        "bytes": len(eligibility),
        "rows": eligibility.count(b"\n") - 1,
        "columns": list(ELIGIBILITY_COLUMNS),
        "scope": scope,
    }:
        raise OracleOuterFreezerIOError("eligibility receipt differs")
    accounting = _object(manifest.get("operation_accounting"), "eligibility accounting")
    expected_accounting = dict(source.expected_operation_accounting)
    expected_shape = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    if set(expected_accounting) == set(ACCOUNTING_FIELDS):
        expected_shape["query_truth_values_opened_by_scorers"] = expected_accounting[
            "query_truth_values_opened_by_scorers"
        ]
    if accounting != expected_accounting or expected_accounting != expected_shape:
        raise OracleOuterFreezerIOError("eligibility accounting differs")
    source_binding = _object(
        manifest.get("source_bundle_binding"), "eligibility source binding"
    )
    _validate_source_binding(source_binding)
    source_manifest = _object(
        source_binding.get("manifest_receipt"), "eligibility source manifest"
    )
    if source_manifest.get("sha256") != parents["v2_source_manifest_sha256"]:
        raise OracleOuterFreezerIOError("eligibility source parent differs")


def _valid_unopened_csv_receipt(
    record: Mapping[str, Any], name: str, columns: Sequence[str]
) -> bool:
    return (
        set(record) == {"sha256", "bytes", "rows", "columns"}
        and record.get("columns") == list(columns)
        and isinstance(record.get("sha256"), str)
        and len(cast(str, record["sha256"])) == 64
        and all(char in "0123456789abcdef" for char in cast(str, record["sha256"]))
        and type(record.get("bytes")) is int
        and record["bytes"] >= 1
        and type(record.get("rows")) is int
        and record["rows"] >= 0
        and name in {"episode_truth.csv", "activity_cliffs.csv"}
    )


def _validate_eligibility_rows(rows: Sequence[Mapping[str, str]]) -> None:
    if not rows:
        raise OracleOuterFreezerIOError("eligibility is empty")
    keys: set[tuple[str, str, str]] = set()
    order: list[tuple[str, int]] = []
    for row in rows:
        key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
        rank = _canonical_int(row["query_rank"], "eligibility query rank", minimum=1)
        if (
            key in keys
            or row["complete_anchor"] not in {"true", "false"}
            or row["valid_true_transformation"] not in {"true", "false"}
            or not row["true_extraction_status"]
            or (row["valid_true_transformation"] == "true")
            != (row["true_extraction_status"] in VALID_TRUE_STATUSES)
        ):
            raise OracleOuterFreezerIOError("eligibility row differs")
        keys.add(key)
        order.append((row["episode_id"], rank))
    if order != sorted(order):
        raise OracleOuterFreezerIOError("eligibility row order differs")


def _validate_source_binding(binding: Mapping[str, Any]) -> None:
    if (
        set(binding)
        != {
            "manifest_receipt",
            "schema_version",
            "contract_sha256",
            "parent_receipts",
            "input_receipts",
            "source_receipts",
        }
        or binding.get("schema_version")
        != "cypshift.openadmet_cyp_2026.oracle_source_bundle.v1"
        or binding.get("contract_sha256")
        != "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
    ):
        raise OracleOuterFreezerIOError("source binding fields differ")
    manifest = _object(binding.get("manifest_receipt"), "source manifest")
    if set(manifest) != {"sha256", "bytes"}:
        raise OracleOuterFreezerIOError("source manifest receipt differs")
    _digest(manifest.get("sha256"), "source manifest")
    if type(manifest.get("bytes")) is not int or manifest["bytes"] < 0:
        raise OracleOuterFreezerIOError("source manifest receipt differs")
    parents = _object(binding.get("parent_receipts"), "source parents")
    inputs = _object(binding.get("input_receipts"), "source inputs")
    sources = _object(binding.get("source_receipts"), "source receipts")
    if (
        set(parents) != set(SOURCE_PARENT_FILES)
        or set(inputs) != set(parents)
        or inputs != sources
    ):
        raise OracleOuterFreezerIOError("source binding receipts differ")
    for name in SOURCE_PARENT_FILES:
        _digest(parents[name], f"source parent: {name}")
        record = _object(inputs[name], f"source input: {name}")
        if (
            set(record) != {"sha256", "bytes"}
            or record.get("sha256") != parents[name]
            or type(record.get("bytes")) is not int
            or record["bytes"] < 0
        ):
            raise OracleOuterFreezerIOError("source input receipt differs")


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OracleOuterFreezerIOError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OracleOuterFreezerIOError(f"{label} columns differ")
        return [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise OracleOuterFreezerIOError(f"{label} is invalid") from exc


def _canonical_object(
    data: bytes, label: str, *, compact: bool = True
) -> dict[str, Any]:
    try:
        value = cast(dict[str, Any], strict_json_object(data, label))
    except ValueError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc
    expected = _compact_json(value) if compact else _pretty_json(value)
    if data != expected:
        raise OracleOuterFreezerIOError(f"{label} is not canonical")
    return value


def _compact_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()


def _bundle(paths: Sequence[str], receipts: Mapping[str, str]) -> str:
    material = "".join(f"{name}|{receipts[name]}\n" for name in sorted(paths))
    return sha256(material.encode()).hexdigest()


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleOuterFreezerIOError(f"{label} is not an object")
    return dict(cast(Mapping[str, Any], value))


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleOuterFreezerIOError(f"{label} is not SHA-256")
    return value


def _canonical_int(value: str, label: str, *, minimum: int = 0) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise OracleOuterFreezerIOError(f"{label} differs") from exc
    if str(result) != value or result < minimum:
        raise OracleOuterFreezerIOError(f"{label} differs")
    return result


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleOuterFreezerIOError(f"{label} is not finite") from exc
    if not math.isfinite(result):
        raise OracleOuterFreezerIOError(f"{label} is not finite")
    return result


__all__ = [
    "FREEZE_SCHEMA",
    "FREEZE_STATUS",
    "FREEZER_SOURCE_FILES",
    "G0_SOURCE_FILES",
    "PAIR_SYSTEMS",
    "SYSTEMS",
    "TOKEN_SYSTEMS",
    "EligibilityInput",
    "FragmentInput",
    "G0Input",
    "LoadedEligibility",
    "LoadedFragment",
    "LoadedG0",
    "OracleOuterFreezerIOError",
    "TokenInput",
    "freezer_source_bundle_sha256",
    "g0_source_bundle_sha256",
    "load_eligibility",
    "load_fragment",
    "load_g0_roots",
    "load_token",
    "pair_runner_source_bundle_sha256",
    "validate_execution",
    "validate_freeze_output",
]
