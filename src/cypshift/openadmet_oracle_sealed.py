"""V3 sealed-scorer capability migration for the R5C oracle experiment."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Literal, cast

from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
    read_exact_root,
)
from cypshift.openadmet_oracle_projection import (
    ACCOUNTING_FIELDS,
    DENIED_AUTHORITY,
    SOURCE_FILES,
    SOURCE_MANIFEST_SCHEMA,
)
from cypshift.openadmet_oracle_projection import (
    SCHEMA_VERSION as V2_SCHEMA_VERSION,
)
from cypshift.openadmet_oracle_validation import (
    ANCHOR_CONTEXT_COLUMNS,
    CLIFF_COLUMNS,
    PUBLIC_QUERY_COLUMNS,
    SCOPE_COLUMNS,
    TRUTH_COLUMNS,
    csv_rows,
)
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    canonical_json_bytes,
    strict_json_object,
)
from cypshift.openadmet_transformation_serialization import EPISODE_COLUMNS

RESOLVED_CONTRACT_SHA256: Final = (
    "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
)
V2_CONTRACT_SHA256: Final = (
    "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
)
SEALED_SCHEMA_VERSION: Final = (
    "cypshift.openadmet_cyp_2026.r5c_sealed_scorer_capability.v1"
)
SEALED_STATUS: Final = "R5_ORACLE_V3_SEALED_SCORER_COMPLETE"
ELIGIBILITY_COLUMNS: Final = (
    "episode_id",
    "query_molecule_id",
    "query_rank",
    "complete_anchor",
    "valid_true_transformation",
    "true_extraction_status",
)
V2_FILES: Final = ("manifest.json", "episode_truth.csv", "activity_cliffs.csv")
SEALED_FILES: Final = (*V2_FILES, "sealed_episode_eligibility.csv")
VALID_TRUE_STATUSES: Final = frozenset({"VALID_SINGLE", "VALID_DOUBLE"})
Scope = tuple[Literal["inner", "outer"], int, int, int | None]


class OracleSealedCapabilityError(ValueError):
    """A sealed capability receipt, population, or publication invariant failed."""


@dataclass(frozen=True, slots=True)
class SealedScorerCapability:
    """One authenticated V3 sealed-scorer cell."""

    root: Path
    manifest_sha256: str
    scope: Scope
    manifest: Mapping[str, Any]
    truth_rows: tuple[Mapping[str, str], ...]
    cliff_rows: tuple[Mapping[str, str], ...]
    eligibility_rows: tuple[Mapping[str, str], ...]
    query_points: tuple[tuple[str, str, float | None], ...]


def migrate_v3_sealed_scorer(
    v2_root: Path,
    source_root: Path,
    output_root: Path,
    *,
    expected_v2_manifest_sha256: str,
    expected_source_manifest_sha256: str,
    expected_scope: Scope,
) -> Path:
    """Add trusted eligibility to one immutable V2 sealed root and republish V3."""

    _validate_scope(expected_scope)
    v2_manifest, truth, cliffs = _load_v2_root(
        v2_root,
        expected_manifest_sha256=expected_v2_manifest_sha256,
        expected_scope=expected_scope,
    )
    source_manifest, public, contexts, geometry = _load_source_material(
        source_root, expected_source_manifest_sha256
    )
    source_binding = _object(v2_manifest.get("source_bundle_binding"), "source binding")
    bound_manifest = _object(source_binding.get("manifest_receipt"), "source manifest")
    if bound_manifest.get("sha256") != expected_source_manifest_sha256:
        raise OracleSealedCapabilityError("V2/source parent receipt differs")
    eligibility = _derive_eligibility(expected_scope, truth, public, contexts, geometry)
    scorer_accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    scorer_accounting["query_truth_values_opened_by_scorers"] = sum(
        row["query_point_available"] == "true" for row in truth[0]
    )
    scope_object = _scope_object(expected_scope)
    eligibility_bytes = canonical_csv_bytes(ELIGIBILITY_COLUMNS, eligibility)
    data = {
        "episode_truth.csv": truth[1],
        "activity_cliffs.csv": cliffs[1],
        "sealed_episode_eligibility.csv": eligibility_bytes,
    }
    output_receipts = {
        "episode_truth.csv": _csv_receipt("episode_truth.csv", truth[1], TRUTH_COLUMNS),
        "activity_cliffs.csv": _csv_receipt(
            "activity_cliffs.csv", cliffs[1], CLIFF_COLUMNS
        ),
        "sealed_episode_eligibility.csv": {
            **_csv_receipt(
                "sealed_episode_eligibility.csv",
                eligibility_bytes,
                ELIGIBILITY_COLUMNS,
            ),
            "relative_path": "sealed_episode_eligibility.csv",
            "scope": scope_object,
        },
    }
    v2_data = canonical_json_bytes(v2_manifest)
    source_data = canonical_json_bytes(source_manifest)
    manifest = {
        "schema_version": SEALED_SCHEMA_VERSION,
        "status": SEALED_STATUS,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "parent_contract_sha256": V2_CONTRACT_SHA256,
        "root": "sealed-scorer",
        "current_cell_scope": scope_object,
        "parent_receipts": {
            "v2_sealed_manifest_sha256": expected_v2_manifest_sha256,
            "v2_source_manifest_sha256": expected_source_manifest_sha256,
        },
        "input_receipts": {
            "v2_sealed_manifest.json": {
                "sha256": expected_v2_manifest_sha256,
                "bytes": len(v2_data),
            },
            "v2_source_manifest.json": {
                "sha256": expected_source_manifest_sha256,
                "bytes": len(source_data),
            },
            "episode_truth.csv": _csv_receipt(
                "episode_truth.csv", truth[1], TRUTH_COLUMNS
            ),
            "activity_cliffs.csv": _csv_receipt(
                "activity_cliffs.csv", cliffs[1], CLIFF_COLUMNS
            ),
        },
        "output_receipts": output_receipts,
        "source_bundle_binding": source_binding,
        "operation_accounting": scorer_accounting,
        "authority": dict(DENIED_AUTHORITY),
    }
    payloads = {**data, "manifest.json": _compact_json_bytes(manifest)}
    _publish_tree(output_root, payloads, expected_scope)
    return output_root


def load_v3_sealed_scorer(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_scope: Scope,
) -> SealedScorerCapability:
    """Authenticate one V3 sealed root from an independent manifest receipt."""

    _digest(expected_manifest_sha256, "sealed manifest")
    _validate_scope(expected_scope)
    data = _read_exact_root(root, SEALED_FILES)
    manifest_bytes = data["manifest.json"]
    if sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise OracleSealedCapabilityError("sealed manifest receipt differs")
    manifest = _canonical_object(manifest_bytes, "sealed manifest", compact=True)
    expected_fields = {
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
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != SEALED_SCHEMA_VERSION
        or manifest.get("status") != SEALED_STATUS
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("parent_contract_sha256") != V2_CONTRACT_SHA256
        or manifest.get("root") != "sealed-scorer"
        or manifest.get("current_cell_scope") != _scope_object(expected_scope)
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleSealedCapabilityError("sealed manifest fields differ")
    parents = _object(manifest.get("parent_receipts"), "sealed parents")
    inputs = _object(manifest.get("input_receipts"), "sealed inputs")
    if set(parents) != {
        "v2_sealed_manifest_sha256",
        "v2_source_manifest_sha256",
    } or set(inputs) != {
        "v2_sealed_manifest.json",
        "v2_source_manifest.json",
        "episode_truth.csv",
        "activity_cliffs.csv",
    }:
        raise OracleSealedCapabilityError("sealed parent/input fields differ")
    for key in parents:
        _digest(parents[key], f"sealed parent: {key}")
    if (
        _object(inputs["v2_sealed_manifest.json"], "V2 sealed input").get("sha256")
        != parents["v2_sealed_manifest_sha256"]
        or _object(inputs["v2_source_manifest.json"], "V2 source input").get("sha256")
        != parents["v2_source_manifest_sha256"]
    ):
        raise OracleSealedCapabilityError("sealed parent/input receipt differs")
    for name in ("v2_sealed_manifest.json", "v2_source_manifest.json"):
        record = _object(inputs[name], name)
        if (
            set(record) != {"sha256", "bytes"}
            or type(record.get("bytes")) is not int
            or record["bytes"] < 1
        ):
            raise OracleSealedCapabilityError("sealed parent input differs")
    source_binding = _object(
        manifest.get("source_bundle_binding"), "sealed source binding"
    )
    source_manifest = _object(
        source_binding.get("manifest_receipt"), "sealed source manifest"
    )
    if source_manifest.get("sha256") != parents["v2_source_manifest_sha256"]:
        raise OracleSealedCapabilityError("sealed source parent differs")
    outputs = _object(manifest.get("output_receipts"), "sealed outputs")
    if set(outputs) != set(SEALED_FILES) - {"manifest.json"}:
        raise OracleSealedCapabilityError("sealed output receipt set differs")
    schemas = {
        "episode_truth.csv": TRUTH_COLUMNS,
        "activity_cliffs.csv": CLIFF_COLUMNS,
        "sealed_episode_eligibility.csv": ELIGIBILITY_COLUMNS,
    }
    for name, columns in schemas.items():
        expected = _csv_receipt(name, data[name], columns)
        observed = _object(outputs.get(name), f"sealed receipt: {name}")
        if name == "sealed_episode_eligibility.csv":
            expected = {
                **expected,
                "relative_path": name,
                "scope": _scope_object(expected_scope),
            }
        if observed != expected:
            raise OracleSealedCapabilityError(f"sealed output receipt differs: {name}")
        if (
            name in {"episode_truth.csv", "activity_cliffs.csv"}
            and _object(inputs[name], f"sealed copied input: {name}") != expected
        ):
            raise OracleSealedCapabilityError(f"sealed copied input differs: {name}")
    truth = tuple(csv_rows(data["episode_truth.csv"], TRUTH_COLUMNS, "sealed truth"))
    cliffs = tuple(
        csv_rows(data["activity_cliffs.csv"], CLIFF_COLUMNS, "sealed cliffs")
    )
    eligibility = tuple(
        csv_rows(
            data["sealed_episode_eligibility.csv"],
            ELIGIBILITY_COLUMNS,
            "sealed eligibility",
        )
    )
    query_points = _validate_loaded_rows(expected_scope, truth, cliffs, eligibility)
    _validate_accounting(
        manifest.get("operation_accounting"),
        sum(point is not None for _, _, point in query_points),
    )
    return SealedScorerCapability(
        root,
        expected_manifest_sha256,
        expected_scope,
        manifest,
        truth,
        cliffs,
        eligibility,
        query_points,
    )


def _load_v2_root(
    root: Path, *, expected_manifest_sha256: str, expected_scope: Scope
) -> tuple[
    dict[str, Any],
    tuple[tuple[Mapping[str, str], ...], bytes],
    tuple[tuple[Mapping[str, str], ...], bytes],
]:
    _digest(expected_manifest_sha256, "V2 sealed manifest")
    data = _read_exact_root(root, V2_FILES)
    manifest_bytes = data["manifest.json"]
    if sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise OracleSealedCapabilityError("V2 sealed manifest receipt differs")
    manifest = _canonical_object(manifest_bytes, "V2 sealed manifest", compact=False)
    if (
        manifest.get("schema_version") != V2_SCHEMA_VERSION
        or manifest.get("contract_sha256") != V2_CONTRACT_SHA256
        or manifest.get("root") != "sealed-scorer"
        or manifest.get("current_cell_scope") != _scope_object(expected_scope)
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleSealedCapabilityError("V2 sealed manifest fields differ")
    outputs = _object(manifest.get("output_receipts"), "V2 sealed outputs")
    for name, columns in (
        ("episode_truth.csv", TRUTH_COLUMNS),
        ("activity_cliffs.csv", CLIFF_COLUMNS),
    ):
        if _object(outputs.get(name), name) != _csv_receipt(name, data[name], columns):
            raise OracleSealedCapabilityError(f"V2 sealed receipt differs: {name}")
    truth_rows = tuple(csv_rows(data["episode_truth.csv"], TRUTH_COLUMNS, "V2 truth"))
    cliff_rows = tuple(
        csv_rows(data["activity_cliffs.csv"], CLIFF_COLUMNS, "V2 cliffs")
    )
    if not truth_rows or len(truth_rows) != len(cliff_rows):
        raise OracleSealedCapabilityError("V2 sealed population differs")
    return (
        manifest,
        (truth_rows, data["episode_truth.csv"]),
        (cliff_rows, data["activity_cliffs.csv"]),
    )


def _load_source_material(
    root: Path, expected_manifest_sha256: str
) -> tuple[
    dict[str, Any],
    tuple[Mapping[str, str], ...],
    tuple[Mapping[str, str], ...],
    tuple[Mapping[str, str], ...],
]:
    _digest(expected_manifest_sha256, "source manifest")
    data = _secure_root(root, (*SOURCE_FILES, "manifest.json"))
    manifest_data = data["manifest.json"]
    if sha256(manifest_data).hexdigest() != expected_manifest_sha256:
        raise OracleSealedCapabilityError("source manifest receipt differs")
    manifest = _canonical_object(manifest_data, "source manifest", compact=False)
    if (
        manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA
        or manifest.get("contract_sha256") != V2_CONTRACT_SHA256
    ):
        raise OracleSealedCapabilityError("source manifest fields differ")
    outputs = _object(manifest.get("output_receipts"), "source outputs")
    required = {
        "public_episode_queries.csv": PUBLIC_QUERY_COLUMNS,
        "episode_anchor_contexts.csv": SCOPE_COLUMNS + ANCHOR_CONTEXT_COLUMNS,
        "episode_transformations.csv": EPISODE_COLUMNS,
    }
    loaded: dict[str, bytes] = {}
    for name, columns in required.items():
        leaf = data[name]
        if _object(outputs.get(name), name) != _csv_receipt(name, leaf, columns):
            raise OracleSealedCapabilityError(f"source receipt differs: {name}")
        loaded[name] = leaf
    return (
        manifest,
        tuple(
            csv_rows(
                loaded["public_episode_queries.csv"],
                PUBLIC_QUERY_COLUMNS,
                "public queries",
            )
        ),
        tuple(
            csv_rows(
                loaded["episode_anchor_contexts.csv"],
                SCOPE_COLUMNS + ANCHOR_CONTEXT_COLUMNS,
                "anchor contexts",
            )
        ),
        tuple(
            csv_rows(
                loaded["episode_transformations.csv"],
                EPISODE_COLUMNS,
                "episode geometry",
            )
        ),
    )


def _derive_eligibility(
    expected_scope: Scope,
    truth: tuple[tuple[Mapping[str, str], ...], bytes],
    public: Sequence[Mapping[str, str]],
    contexts: Sequence[Mapping[str, str]],
    geometry: Sequence[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    truth_rows = truth[0]
    public_index: dict[tuple[str, str], Mapping[str, str]] = {}
    for row in public:
        key = row["episode_id"], row["query_molecule_id"]
        if key in public_index:
            raise OracleSealedCapabilityError("public query key is duplicated")
        public_index[key] = row
    geometry_index: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in geometry:
        geometry_key = (
            row["episode_id"],
            row["query_molecule_id"],
            row["query_rank"],
        )
        if geometry_key in geometry_index:
            raise OracleSealedCapabilityError("episode geometry key is duplicated")
        geometry_index[geometry_key] = row
    context_index: dict[str, Mapping[str, str]] = {}
    for row in contexts:
        if _row_scope(row) != expected_scope:
            continue
        episode = row["episode_id"]
        if episode in context_index:
            raise OracleSealedCapabilityError("anchor context is duplicated")
        context_index[episode] = row
    result: list[dict[str, str]] = []
    for row in truth_rows:
        public_row = public_index.get((row["episode_id"], row["query_molecule_id"]))
        context = context_index.get(row["episode_id"])
        if public_row is None or context is None:
            raise OracleSealedCapabilityError("sealed/source public join differs")
        policy = public_row["episode_policy_id"]
        if (expected_scope[0] == "inner" and policy != "selected_anchor") or (
            expected_scope[0] == "outer"
            and policy not in {"selected_anchor", "deterministic_random_anchor_stress"}
        ):
            raise OracleSealedCapabilityError("sealed episode policy differs")
        rank = public_row["query_rank"]
        geometry_row = geometry_index.get(
            (row["episode_id"], row["query_molecule_id"], rank)
        )
        if geometry_row is None:
            raise OracleSealedCapabilityError("sealed/source geometry join differs")
        status = geometry_row["extraction_status"]
        if not status:
            raise OracleSealedCapabilityError("true extraction status is empty")
        available = context["anchor_point_available"]
        if available not in {"true", "false"}:
            raise OracleSealedCapabilityError("anchor completion differs")
        result.append(
            {
                "episode_id": row["episode_id"],
                "query_molecule_id": row["query_molecule_id"],
                "query_rank": rank,
                "complete_anchor": available,
                "valid_true_transformation": (
                    "true" if status in VALID_TRUE_STATUSES else "false"
                ),
                "true_extraction_status": status,
            }
        )
    result.sort(key=lambda row: (row["episode_id"], int(row["query_rank"])))
    if len(result) != len(truth_rows):
        raise OracleSealedCapabilityError("sealed eligibility cardinality differs")
    return tuple(result)


def _validate_loaded_rows(
    expected_scope: Scope,
    truth: Sequence[Mapping[str, str]],
    cliffs: Sequence[Mapping[str, str]],
    eligibility: Sequence[Mapping[str, str]],
) -> tuple[tuple[str, str, float | None], ...]:
    if not truth or len(truth) != len(cliffs) or len(truth) != len(eligibility):
        raise OracleSealedCapabilityError("sealed row cardinality differs")
    truth_keys: set[tuple[str, str]] = set()
    query_points: list[tuple[str, str, float | None]] = []
    for row in truth:
        key = row["episode_id"], row["query_molecule_id"]
        if key in truth_keys:
            raise OracleSealedCapabilityError("sealed truth key is duplicated")
        truth_keys.add(key)
        available = row["query_point_available"]
        if available not in {"true", "false"}:
            raise OracleSealedCapabilityError("sealed truth availability differs")
        if available == "true":
            point: float | None = _finite(row["query_point"], "sealed query point")
        elif row["query_point"]:
            raise OracleSealedCapabilityError("unavailable sealed truth exposes point")
        else:
            point = None
        query_points.append((*key, point))
    cliff_keys = {(row["episode_id"], row["query_molecule_id"]) for row in cliffs}
    if len(cliff_keys) != len(cliffs) or cliff_keys != truth_keys:
        raise OracleSealedCapabilityError("sealed cliff population differs")
    if any(row["activity_cliff"] not in {"true", "false"} for row in cliffs):
        raise OracleSealedCapabilityError("sealed cliff value differs")
    eligibility_keys: set[tuple[str, str]] = set()
    observed_order: list[tuple[str, int]] = []
    for row in eligibility:
        key = row["episode_id"], row["query_molecule_id"]
        if key in eligibility_keys:
            raise OracleSealedCapabilityError("sealed eligibility key is duplicated")
        eligibility_keys.add(key)
        observed_order.append(
            (row["episode_id"], _canonical_int(row["query_rank"], "query rank"))
        )
        if (
            row["complete_anchor"] not in {"true", "false"}
            or row["valid_true_transformation"] not in {"true", "false"}
            or not row["true_extraction_status"]
        ):
            raise OracleSealedCapabilityError("sealed eligibility value differs")
        expected_valid = row["true_extraction_status"] in VALID_TRUE_STATUSES
        if (row["valid_true_transformation"] == "true") != expected_valid:
            raise OracleSealedCapabilityError("sealed true-transformation flag differs")
    if eligibility_keys != truth_keys or observed_order != sorted(observed_order):
        raise OracleSealedCapabilityError("sealed eligibility population/order differs")
    if expected_scope[0] == "inner" and expected_scope[3] is None:
        raise OracleSealedCapabilityError("inner sealed scope lacks fold")
    return tuple(query_points)


def _publish_tree(
    output_root: Path, payloads: Mapping[str, bytes], expected_scope: Scope
) -> None:
    try:
        _validate_payloads(payloads, expected_scope)
        publish_readonly_tree(output_root, payloads)
    except OraclePrivateIOError as exc:
        raise OracleSealedCapabilityError(str(exc)) from exc


def _read_exact_root(root: Path, names: Sequence[str]) -> dict[str, bytes]:
    return _secure_root(root, names)


def _secure_root(root: Path, names: Sequence[str]) -> dict[str, bytes]:
    try:
        return read_exact_root(root, names)
    except OraclePrivateIOError as exc:
        raise OracleSealedCapabilityError(str(exc)) from exc


def _validate_payloads(payloads: Mapping[str, bytes], expected_scope: Scope) -> None:
    data = payloads["manifest.json"]
    manifest = _canonical_object(data, "sealed manifest", compact=True)
    if (
        set(payloads) != set(SEALED_FILES)
        or manifest.get("schema_version") != SEALED_SCHEMA_VERSION
        or manifest.get("status") != SEALED_STATUS
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("current_cell_scope") != _scope_object(expected_scope)
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleSealedCapabilityError("staged sealed manifest differs")
    outputs = _object(manifest.get("output_receipts"), "sealed outputs")
    for name, columns in {
        "episode_truth.csv": TRUTH_COLUMNS,
        "activity_cliffs.csv": CLIFF_COLUMNS,
        "sealed_episode_eligibility.csv": ELIGIBILITY_COLUMNS,
    }.items():
        expected = _csv_receipt(name, payloads[name], columns)
        if name == "sealed_episode_eligibility.csv":
            expected = {
                **expected,
                "relative_path": name,
                "scope": _scope_object(expected_scope),
            }
        if _object(outputs.get(name), name) != expected:
            raise OracleSealedCapabilityError("staged sealed receipt differs")
    truth = tuple(
        csv_rows(payloads["episode_truth.csv"], TRUTH_COLUMNS, "sealed truth")
    )
    cliffs = tuple(
        csv_rows(payloads["activity_cliffs.csv"], CLIFF_COLUMNS, "sealed cliffs")
    )
    eligibility = tuple(
        csv_rows(
            payloads["sealed_episode_eligibility.csv"],
            ELIGIBILITY_COLUMNS,
            "sealed eligibility",
        )
    )
    query_points = _validate_loaded_rows(expected_scope, truth, cliffs, eligibility)
    _validate_accounting(
        manifest.get("operation_accounting"),
        sum(point is not None for _, _, point in query_points),
    )


def _csv_receipt(name: str, data: bytes, columns: Sequence[str]) -> dict[str, Any]:
    return {
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
        "rows": data.count(b"\n") - 1,
        "columns": list(columns),
    }


def _scope_object(scope: Scope) -> dict[str, int | str]:
    return {
        "stage": scope[0],
        "repeat": scope[1],
        "outer_fold": scope[2],
        "inner_fold": "" if scope[3] is None else scope[3],
    }


def _row_scope(row: Mapping[str, str]) -> Scope:
    stage = row["stage"]
    if stage not in {"inner", "outer"}:
        raise OracleSealedCapabilityError("source scope differs")
    inner = (
        None
        if row["inner_fold"] == ""
        else _canonical_int(row["inner_fold"], "inner fold")
    )
    result: Scope = cast(
        Scope,
        (
            stage,
            _canonical_int(row["repeat"], "repeat"),
            _canonical_int(row["outer_fold"], "outer fold"),
            inner,
        ),
    )
    _validate_scope(result)
    return result


def _validate_scope(scope: Scope) -> None:
    stage, repeat, outer, inner = scope
    if (
        stage not in {"inner", "outer"}
        or type(repeat) is not int
        or repeat not in range(3)
        or type(outer) is not int
        or outer not in range(5)
        or (stage == "outer" and inner is not None)
        or (stage == "inner" and (type(inner) is not int or inner not in range(4)))
    ):
        raise OracleSealedCapabilityError("sealed scope differs")


def _canonical_object(data: bytes, label: str, *, compact: bool) -> dict[str, Any]:
    try:
        value = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleSealedCapabilityError(str(exc)) from exc
    expected = _compact_json_bytes(value) if compact else canonical_json_bytes(value)
    if expected != data:
        raise OracleSealedCapabilityError(f"{label} is not canonical")
    return value


def _compact_json_bytes(value: Mapping[str, Any]) -> bytes:
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


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OracleSealedCapabilityError(f"{label} is not an object")
    return cast(dict[str, Any], value)


def _validate_accounting(value: Any, truth_count: int) -> None:
    accounting = _object(value, "sealed accounting")
    expected = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    expected["query_truth_values_opened_by_scorers"] = truth_count
    if accounting != expected:
        raise OracleSealedCapabilityError("sealed accounting differs")


def _canonical_int(value: str, label: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise OracleSealedCapabilityError(f"{label} differs") from exc
    if str(result) != value or result < 0:
        raise OracleSealedCapabilityError(f"{label} differs")
    return result


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleSealedCapabilityError(f"{label} is not finite") from exc
    if not value or not math.isfinite(result):
        raise OracleSealedCapabilityError(f"{label} is not finite")
    return result


def _digest(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleSealedCapabilityError(f"{label} is not SHA-256")


__all__ = [
    "ELIGIBILITY_COLUMNS",
    "RESOLVED_CONTRACT_SHA256",
    "SEALED_FILES",
    "OracleSealedCapabilityError",
    "SealedScorerCapability",
    "load_v3_sealed_scorer",
    "migrate_v3_sealed_scorer",
]
