"""Closed, independently validated publication boundary for the outer freeze."""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_freezer_io import (
    FREEZE_SCHEMA,
    FREEZE_STATUS,
    PAIR_SYSTEMS,
    SYSTEMS,
    TOKEN_SYSTEMS,
    OracleOuterFreezerIOError,
    _validate_source_binding,
    freezer_source_bundle_sha256,
    g0_source_bundle_sha256,
    pair_runner_source_bundle_sha256,
)
from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME
from cypshift.openadmet_oracle_pair_cell import FRAGMENT_COLUMNS
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
)
from cypshift.openadmet_oracle_projection import DENIED_AUTHORITY
from cypshift.openadmet_oracle_sealed import (
    ELIGIBILITY_COLUMNS,
    RESOLVED_CONTRACT_SHA256,
    VALID_TRUE_STATUSES,
)
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    strict_json_object,
)

EXPECTED_FILES: Final = {
    "manifest.json",
    "merged_eligibility.csv",
    *(f"{system}.csv" for system in SYSTEMS),
}
METADATA_FIELDS: Final = (
    "episode_id",
    "query_molecule_id",
    "query_rank",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "component_id",
    "extraction_status",
    "similarity",
    "exact_support_components",
    "class_support_components",
)


def _publish_validated_freeze(output_root: Path, payloads: Mapping[str, bytes]) -> None:
    """Validate the exact package, then promote only byte-identical staged files."""

    try:
        _validate_payloads(payloads)
        publish_readonly_tree(output_root, payloads)
    except OraclePrivateIOError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc


def _validate_payloads(payloads: Mapping[str, bytes]) -> None:
    if set(payloads) != EXPECTED_FILES or any(
        not isinstance(value, bytes) for value in payloads.values()
    ):
        raise OracleOuterFreezerIOError("freeze package file set differs")
    manifest = _canonical_manifest(payloads["manifest.json"])
    tables = {
        system: _prediction_rows(payloads[f"{system}.csv"], system)
        for system in SYSTEMS
    }
    eligibility = _eligibility_rows(payloads["merged_eligibility.csv"])
    prediction_count = _validate_populations(tables, eligibility)
    _validate_manifest(manifest, payloads, prediction_count, len(eligibility))


def _canonical_manifest(data: bytes) -> dict[str, Any]:
    try:
        manifest = cast(dict[str, Any], strict_json_object(data, "freeze manifest"))
    except ValueError as exc:
        raise OracleOuterFreezerIOError(str(exc)) from exc
    if data != _compact_json(manifest):
        raise OracleOuterFreezerIOError("freeze manifest is not canonical")
    return manifest


def _validate_manifest(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, bytes],
    prediction_count: int,
    eligibility_count: int,
) -> None:
    fields = {
        "schema_version",
        "status",
        "contract_sha256",
        "scope",
        "parent_receipts",
        "input_receipts",
        "source_receipts",
        "runtime",
        "counts",
        "output_receipts",
        "operation_accounting",
        "authority",
    }
    if (
        set(manifest) != fields
        or manifest.get("schema_version") != FREEZE_SCHEMA
        or manifest.get("status") != FREEZE_STATUS
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("scope")
        != {"stage": "outer", "repeats": 3, "outer_folds": 5, "contexts": 15}
        or manifest.get("runtime") != EXPECTED_RUNTIME
        or manifest.get("authority") != DENIED_AUTHORITY
    ):
        raise OracleOuterFreezerIOError("freeze manifest binding differs")
    sources = _object(manifest.get("source_receipts"), "freeze sources")
    expected_sources = {
        "freezer_source_sha256": freezer_source_bundle_sha256(),
        "pair_runner_source_sha256": pair_runner_source_bundle_sha256(),
        "g0_source_bundle_sha256": g0_source_bundle_sha256(),
    }
    if sources != expected_sources:
        raise OracleOuterFreezerIOError("freeze source receipts differ")
    parents = _object(manifest.get("parent_receipts"), "freeze parents")
    if set(parents) != {
        "model_public_manifest_sha256",
        "source_bundle_binding",
    }:
        raise OracleOuterFreezerIOError("freeze parent fields differ")
    _digest(parents.get("model_public_manifest_sha256"), "freeze model parent")
    _validate_source_binding(
        _object(parents.get("source_bundle_binding"), "freeze source parent")
    )
    inputs = _validate_input_receipts(manifest.get("input_receipts"))
    counts = _object(manifest.get("counts"), "freeze counts")
    expected_counts = {
        "contexts": 15,
        "systems": 12,
        "selection_tokens": len(inputs["selection_tokens"]),
        "pair_fragments": len(inputs["pair_fragments"]),
        "g0_fragments": len(inputs["g0_fragments"]),
        "prediction_rows": prediction_count,
        "eligibility_rows": eligibility_count,
    }
    if counts != expected_counts:
        raise OracleOuterFreezerIOError("freeze counts differ")
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    accounting["predictions_frozen"] = prediction_count
    if manifest.get("operation_accounting") != accounting:
        raise OracleOuterFreezerIOError("freeze accounting differs")
    output_receipts = _object(manifest.get("output_receipts"), "freeze outputs")
    output_names = EXPECTED_FILES - {"manifest.json"}
    if set(output_receipts) != output_names:
        raise OracleOuterFreezerIOError("freeze output receipt set differs")
    for name in output_names:
        columns = (
            ELIGIBILITY_COLUMNS
            if name == "merged_eligibility.csv"
            else FRAGMENT_COLUMNS
        )
        if _object(output_receipts[name], f"freeze output: {name}") != _receipt(
            name, payloads[name], columns
        ):
            raise OracleOuterFreezerIOError("freeze output receipt differs")


def _validate_input_receipts(value: Any) -> dict[str, dict[str, Any]]:
    inputs = _object(value, "freeze inputs")
    if set(inputs) != {
        "selection_tokens",
        "pair_fragments",
        "g0_fragments",
        "eligibility_manifests",
    }:
        raise OracleOuterFreezerIOError("freeze input fields differ")
    result = {name: _object(inputs[name], f"freeze input: {name}") for name in inputs}
    scopes = [
        f"repeat-{repeat}/outer-{outer}" for repeat in range(3) for outer in range(5)
    ]
    expected_tokens = {
        f"{scope}/{system}" for scope in scopes for system in TOKEN_SYSTEMS
    }
    expected_pairs = {
        f"{scope}/{system}" for scope in scopes for system in PAIR_SYSTEMS
    }
    if (
        set(result["selection_tokens"]) != expected_tokens
        or set(result["pair_fragments"]) != expected_pairs
        or set(result["eligibility_manifests"]) != set(scopes)
    ):
        raise OracleOuterFreezerIOError("freeze input population differs")
    g0_keys = set(result["g0_fragments"])
    for scope in scopes:
        scoped = sorted(key for key in g0_keys if key.startswith(f"{scope}/"))
        if (
            scoped != [f"{scope}/{index:04d}" for index in range(len(scoped))]
            or not scoped
        ):
            raise OracleOuterFreezerIOError("freeze G0 input population differs")
    if sum(key.startswith(f"{scope}/") for scope in scopes for key in g0_keys) != len(
        g0_keys
    ):
        raise OracleOuterFreezerIOError("freeze G0 input population differs")
    for records in result.values():
        for receipt in records.values():
            _digest(receipt, "freeze input receipt")
    return result


def _prediction_rows(data: bytes, system: str) -> tuple[dict[str, str], ...]:
    rows = tuple(_csv_rows(data, FRAGMENT_COLUMNS, f"freeze {system}"))
    if not rows or data != canonical_csv_bytes(FRAGMENT_COLUMNS, rows):
        raise OracleOuterFreezerIOError("freeze prediction serialization differs")
    seen: set[tuple[str, str, str, str, str]] = set()
    order: list[tuple[int, int, str, int]] = []
    policies: dict[tuple[int, int], set[str]] = {}
    candidates: dict[tuple[int, int], set[str]] = {}
    for row in rows:
        repeat = _canonical_int(row["repeat"], "freeze repeat")
        outer = _canonical_int(row["outer_fold"], "freeze outer fold")
        rank = _canonical_int(row["query_rank"], "freeze query rank", minimum=1)
        context = repeat, outer
        key = (
            row["episode_id"],
            row["query_molecule_id"],
            row["query_rank"],
            row["system_id"],
            row["candidate_id"],
        )
        _digest(row["episode_id"], "freeze episode")
        _digest(row["component_id"], "freeze component")
        _digest(row["candidate_id"], "freeze candidate")
        if (
            repeat not in range(3)
            or outer not in range(5)
            or row["inner_fold"]
            or row["system_id"] != system
            or key in seen
            or row["episode_policy_id"]
            not in {"selected_anchor", "deterministic_random_anchor_stress"}
        ):
            raise OracleOuterFreezerIOError("freeze prediction row differs")
        seen.add(key)
        order.append((repeat, outer, row["episode_id"], rank))
        policies.setdefault(context, set()).add(row["episode_policy_id"])
        candidates.setdefault(context, set()).add(row["candidate_id"])
        _validate_prediction_values(row, system)
    expected_contexts = {(repeat, outer) for repeat in range(3) for outer in range(5)}
    expected_policies = {"selected_anchor", "deterministic_random_anchor_stress"}
    if (
        order != sorted(order)
        or set(policies) != expected_contexts
        or any(value != expected_policies for value in policies.values())
        or set(candidates) != expected_contexts
        or any(len(value) != 1 for value in candidates.values())
    ):
        raise OracleOuterFreezerIOError("freeze fixed superset differs")
    return rows


def _validate_prediction_values(row: Mapping[str, str], system: str) -> None:
    prediction = _finite(row["prediction"], "freeze prediction")
    if format(prediction, ".17g") != row["prediction"]:
        raise OracleOuterFreezerIOError("freeze prediction serialization differs")
    if row["local_available"] not in {"true", "false"}:
        raise OracleOuterFreezerIOError("freeze local availability differs")
    expected_local = system if system in {"C0", "C1", "F0", "F1"} else "LOCAL"
    expected_source = "G0" if row["local_available"] == "false" else expected_local
    if system == "G0":
        expected_source = "G0"
        if row["local_available"] != "false":
            raise OracleOuterFreezerIOError("freeze G0 availability differs")
    if row["prediction_source"] != expected_source:
        raise OracleOuterFreezerIOError("freeze prediction source differs")
    if row["similarity"]:
        similarity = _finite(row["similarity"], "freeze similarity")
        if format(similarity, ".17g") != row["similarity"]:
            raise OracleOuterFreezerIOError("freeze similarity serialization differs")
    for name in ("exact_support_components", "class_support_components"):
        _canonical_int(row[name], f"freeze {name}")


def _eligibility_rows(data: bytes) -> tuple[dict[str, str], ...]:
    rows = tuple(_csv_rows(data, ELIGIBILITY_COLUMNS, "merged eligibility"))
    if not rows or data != canonical_csv_bytes(ELIGIBILITY_COLUMNS, rows):
        raise OracleOuterFreezerIOError("merged eligibility serialization differs")
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
        _digest(row["episode_id"], "eligibility episode")
        _canonical_int(row["query_rank"], "eligibility query rank", minimum=1)
        if (
            key in seen
            or row["complete_anchor"] not in {"true", "false"}
            or row["valid_true_transformation"] not in {"true", "false"}
            or not row["true_extraction_status"]
            or (row["valid_true_transformation"] == "true")
            != (row["true_extraction_status"] in VALID_TRUE_STATUSES)
        ):
            raise OracleOuterFreezerIOError("merged eligibility row differs")
        seen.add(key)
    return rows


def _validate_populations(
    tables: Mapping[str, Sequence[Mapping[str, str]]],
    eligibility: Sequence[Mapping[str, str]],
) -> int:
    base = tables["G0"]
    base_metadata = [tuple(row[field] for field in METADATA_FIELDS) for row in base]
    base_keys = [
        (row["episode_id"], row["query_molecule_id"], row["query_rank"]) for row in base
    ]
    for system in SYSTEMS:
        rows = tables[system]
        if [
            tuple(row[field] for field in METADATA_FIELDS) for row in rows
        ] != base_metadata:
            raise OracleOuterFreezerIOError("freeze public metadata differs")
    eligibility_keys = [
        (row["episode_id"], row["query_molecule_id"], row["query_rank"])
        for row in eligibility
    ]
    if eligibility_keys != base_keys or any(
        eligibility[index]["true_extraction_status"] != row["extraction_status"]
        for index, row in enumerate(base)
    ):
        raise OracleOuterFreezerIOError("freeze eligibility join differs")
    g0 = {key: base[index]["prediction"] for index, key in enumerate(base_keys)}
    for system in PAIR_SYSTEMS:
        for row in tables[system]:
            key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
            if row["prediction_source"] == "G0" and row["prediction"] != g0[key]:
                raise OracleOuterFreezerIOError("freeze fallback differs")
    return sum(len(rows) for rows in tables.values())


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


def _receipt(name: str, data: bytes, columns: Sequence[str]) -> dict[str, Any]:
    return {
        "relative_path": name,
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
        "rows": data.count(b"\n") - 1,
        "columns": list(columns),
    }


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


def _compact_json(value: Mapping[str, Any]) -> bytes:
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


__all__: tuple[str, ...] = ()
