"""Status-specific, closed R5C oracle terminal publication."""

from __future__ import annotations

import csv
import io
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_freezer_io import SYSTEMS
from cypshift.openadmet_oracle_inner import SELECTION_COLUMNS
from cypshift.openadmet_oracle_inner_io import EXPECTED_RUNTIME
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    open_directory_no_symlinks,
    publish_readonly_tree,
    remove_private_root,
    validate_output_root,
)
from cypshift.openadmet_oracle_scoring import REQUIRED_CONTRASTS
from cypshift.openadmet_oracle_sealed import RESOLVED_CONTRACT_SHA256
from cypshift.openadmet_oracle_terminal_cleanup import (
    CleanupCapability,
    CleanupInput,
    OracleTerminalCleanupError,
    load_cleanup,
)
from cypshift.openadmet_oracle_terminal_io import (
    SUPPORT_SCHEMA,
    LoadedSupport,
    OracleTerminalIOError,
    SupportInput,
    _validate_selection_rows,
    load_support,
    terminal_source_bundle_sha256,
    validate_execution,
    validate_failure_execution,
)
from cypshift.openadmet_oracle_terminal_validation import (
    OracleTerminalValidationError,
    validate_scientific_evidence,
)
from cypshift.openadmet_transformation_io import canonical_csv_bytes, strict_json_object

MANIFEST_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_oracle_terminal.v1"
RESULT_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_oracle_result.v1"
FAILURE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.r5c_oracle_failure.v1"
FULL_STATUSES: Final = {"R5_ORACLE_NO_SIGNAL", "R5_ORACLE_SIGNAL_PASS"}
STATUS_FILES: Final = {
    "R5_ORACLE_FAILED": ("failure.json",),
    "R5_ORACLE_UNDERPOWERED": ("manifest.json", "oracle_result.json"),
    "R5_ORACLE_NO_SIGNAL": (
        "manifest.json",
        "oracle_inner_selection.csv",
        "oracle_scored_rows.csv",
        "oracle_cell_metrics.csv",
        "oracle_bootstrap_summary.csv",
        "oracle_influence_checks.csv",
        "oracle_ablation_scorecard.csv",
        "oracle_result.json",
    ),
    "R5_ORACLE_SIGNAL_PASS": (
        "manifest.json",
        "oracle_inner_selection.csv",
        "oracle_scored_rows.csv",
        "oracle_cell_metrics.csv",
        "oracle_bootstrap_summary.csv",
        "oracle_influence_checks.csv",
        "oracle_ablation_scorecard.csv",
        "oracle_result.json",
    ),
}
SCORED_COLUMNS: Final = (
    "episode_id",
    "query_molecule_id",
    "query_rank",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "component_id",
    "population_id",
    "system_id",
    "local_eligible",
    "local_available",
    "prediction_source",
    "extraction_status",
    "similarity",
    "exact_support_components",
    "class_support_components",
    "activity_cliff",
    "similarity_bin",
    "support_bin",
    "absolute_error",
    "query_weight",
    "episode_weight",
    "component_weight",
)
CELL_COLUMNS: Final = (
    "population_id",
    "system_id",
    "repeat",
    "outer_fold",
    "scored_rows",
    "scored_episodes",
    "scored_components",
    "query_macro_mae",
    "episode_macro_mae",
    "component_macro_mae",
    "contrast_vs_T0",
)
BOOTSTRAP_COLUMNS: Final = (
    "comparison_id",
    "population_id",
    "control_system_id",
    "candidate_system_id",
    "point_delta",
    "lower_95",
    "upper_95",
    "accepted_replicates",
    "attempts",
    "lower_bound_positive",
)
INFLUENCE_COLUMNS: Final = (
    "comparison_id",
    "rank",
    "component_id",
    "absolute_contribution",
    "loo_point_delta",
    "direction_preserved",
)
ABLATION_COLUMNS: Final = (
    "system_id",
    "population_id",
    "scored_rows",
    "scored_episodes",
    "scored_components",
    "query_macro_mae",
    "episode_macro_mae",
    "component_macro_mae",
    "worst_global_decile_mae",
    "activity_cliff_mae",
    "local_available_rows",
)
CSV_SCHEMAS: Final = {
    "oracle_inner_selection.csv": SELECTION_COLUMNS,
    "oracle_scored_rows.csv": SCORED_COLUMNS,
    "oracle_cell_metrics.csv": CELL_COLUMNS,
    "oracle_bootstrap_summary.csv": BOOTSTRAP_COLUMNS,
    "oracle_influence_checks.csv": INFLUENCE_COLUMNS,
    "oracle_ablation_scorecard.csv": ABLATION_COLUMNS,
}
FAILURE_STAGES: Final = (
    "pre_gate",
    "projection",
    "preflight",
    "inner_models",
    "inner_score",
    "selection_token",
    "outer_models",
    "prediction_freeze",
    "outer_score",
    "terminal_publish",
)
FAILURE_CODES: Final = (
    "CAPABILITY",
    "LEAKAGE",
    "RECEIPT",
    "SCHEMA",
    "FOLD",
    "NONFINITE",
    "ARITHMETIC",
    "NONDETERMINISM",
    "RUNTIME",
    "PROCESS",
    "CLEANUP",
)


class OracleTerminalError(ValueError):
    """A scorer result or terminal boundary differs from the frozen contract."""


@dataclass(frozen=True, slots=True)
class FailureRecord:
    stage: str
    failure_code: str
    reason: str
    verified_receipts: Mapping[str, str]
    operation_accounting: Mapping[str, int]


def publish_underpowered_terminal(
    support_input: SupportInput,
    output_root: Path,
    *,
    expected_source_sha256: str,
    cleanup_input: CleanupInput,
) -> Path:
    source, runtime = _validate_source(expected_source_sha256)
    _validate_destination(output_root)
    loaded = _load_support(support_input)
    cleanup = load_cleanup(cleanup_input)
    if loaded.status != "UNDERPOWERED":
        raise OracleTerminalError("underpowered support status differs")
    support_receipt = loaded.sha256
    support = dict(loaded.support)
    criteria = dict(loaded.criteria)
    accounting = dict.fromkeys(ACCOUNTING_FIELDS, 0)
    authority = _authority("R5_ORACLE_UNDERPOWERED")
    result = {
        "schema_version": RESULT_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "parent_receipts": {
            "cleanup_manifest_sha256": cleanup.sha256,
            "prefit_support_sha256": support_receipt,
        },
        "status": "R5_ORACLE_UNDERPOWERED",
        "support": support,
        "criteria": criteria,
        "point_estimates": {},
        "bootstrap": {},
        "safety": {},
        "diagnostics": {},
        "operation_accounting": accounting,
        "authority": authority,
    }
    result_data = _compact_json(result)
    outputs = {"oracle_result.json": _receipt("oracle_result.json", result_data, None)}
    manifest = _manifest(
        "R5_ORACLE_UNDERPOWERED",
        {
            "cleanup_manifest_sha256": cleanup.sha256,
            "prefit_support_sha256": support_receipt,
        },
        {
            "cleanup_manifest_sha256": cleanup.sha256,
            "prefit_support_sha256": support_receipt,
        },
        source,
        runtime,
        {},
        outputs,
        accounting,
        authority,
    )
    payloads = {
        "manifest.json": _compact_json(manifest),
        "oracle_result.json": result_data,
    }
    expected_cleanup = (
        CleanupCapability(
            "prefit-support",
            support_input.root,
            "support.json",
            support_input.expected_sha256,
        ),
    )
    if cleanup.capabilities != expected_cleanup:
        raise OracleTerminalError("underpowered cleanup set differs")
    cleanup_roots = (support_input.root, cleanup_input.root)
    _validate_cleanup_output_paths(output_root, cleanup_roots)
    cleanup_private_roots(cleanup_roots)
    _publish(output_root, payloads, "R5_ORACLE_UNDERPOWERED")
    return output_root


def publish_failed_terminal(
    record: FailureRecord,
    output_root: Path,
    *,
    expected_source_sha256: str,
    cleanup_input: CleanupInput,
) -> Path:
    source, _runtime = validate_failure_execution(expected_source_sha256)
    _validate_destination(output_root)
    try:
        cleanup = load_cleanup(cleanup_input)
    except OracleTerminalCleanupError as exc:
        raise OracleTerminalError(str(exc)) from exc
    if (
        record.stage not in FAILURE_STAGES
        or record.failure_code not in FAILURE_CODES
        or not record.reason
        or len(record.reason) > 160
        or any(
            not char.isascii() or not (char.isalnum() or char in " ._:-")
            for char in record.reason
        )
    ):
        raise OracleTerminalError("failure record differs")
    receipts = dict(record.verified_receipts)
    if record.stage == "pre_gate":
        allowed = tuple(item.label for item in cleanup.capabilities)
        if allowed not in {(), ("stale-control-cleanup-witness",)} or any(
            receipts.get(item.label) != item.expected_sha256
            for item in cleanup.capabilities
        ):
            raise OracleTerminalError("pre-gate cleanup set differs")
    elif not cleanup.capabilities or any(
        receipts.get(item.label) != item.expected_sha256
        for item in cleanup.capabilities
    ):
        raise OracleTerminalError("failure cleanup set differs")
    for name, value in receipts.items():
        if (
            not name
            or name == "source_sha256"
            or any(not (char.isalnum() or char in "_-.") for char in name)
        ):
            raise OracleTerminalError("failure receipt label differs")
        _digest(value, "failure verified receipt")
    accounting = _accounting(record.operation_accounting)
    authority = _authority("R5_ORACLE_FAILED")
    failure = {
        "schema_version": FAILURE_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "stage": record.stage,
        "failure_code": record.failure_code,
        "reason": record.reason,
        "verified_receipts": {
            **dict(sorted(receipts.items())),
            "cleanup_manifest_sha256": cleanup.sha256,
            "source_sha256": source,
        },
        "operation_accounting": accounting,
        "authority": authority,
    }
    cleanup_roots = (*(item.root for item in cleanup.capabilities), cleanup_input.root)
    _validate_cleanup_output_paths(output_root, cleanup_roots)
    cleanup_private_roots(cleanup_roots)
    _publish(output_root, {"failure.json": _compact_json(failure)}, "R5_ORACLE_FAILED")
    return output_root


def _validate_cleanup_output_paths(output_root: Path, roots: Sequence[Path]) -> None:
    output = output_root.absolute()
    for root in roots:
        candidate = root.absolute()
        if (
            output == candidate
            or output in candidate.parents
            or candidate in output.parents
        ):
            raise OracleTerminalError("cleanup/output path overlap")


def cleanup_private_roots(roots: Sequence[Path]) -> None:
    normalized = tuple(roots)
    if len(normalized) != len(set(normalized)) or any(
        left in right.parents or right in left.parents
        for index, left in enumerate(normalized)
        for right in normalized[index + 1 :]
    ):
        raise OracleTerminalError("cleanup root set differs")
    for root in normalized:
        try:
            remove_private_root(root)
        except OraclePrivateIOError as exc:
            raise OracleTerminalError(str(exc)) from exc
    for root in normalized:
        parent_fd = open_directory_no_symlinks(root.parent)
        try:
            try:
                os.stat(root.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise OracleTerminalError("cleanup root remains")
        finally:
            os.close(parent_fd)


def _publish(output_root: Path, payloads: Mapping[str, bytes], status: str) -> None:
    if status in FULL_STATUSES:
        raise OracleTerminalError("raw full-terminal publication is unavailable")
    try:
        validate_output_root(output_root)
        _validate_terminal(payloads, status)
        publish_readonly_tree(output_root, payloads)
    except (OraclePrivateIOError, OracleTerminalIOError) as exc:
        raise OracleTerminalError(str(exc)) from exc


def _validate_destination(output_root: Path) -> None:
    try:
        validate_output_root(output_root)
    except OraclePrivateIOError as exc:
        raise OracleTerminalError(str(exc)) from exc


def _validate_terminal(payloads: Mapping[str, bytes], status: str) -> None:
    if status not in STATUS_FILES or set(payloads) != set(STATUS_FILES[status]):
        raise OracleTerminalError("terminal status file set differs")
    if status == "R5_ORACLE_FAILED":
        failure = _canonical_object(payloads["failure.json"], "failure terminal")
        if (
            set(failure)
            != {
                "schema_version",
                "contract_sha256",
                "stage",
                "failure_code",
                "reason",
                "verified_receipts",
                "operation_accounting",
                "authority",
            }
            or failure.get("schema_version") != FAILURE_SCHEMA
            or failure.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
            or failure.get("stage") not in FAILURE_STAGES
            or failure.get("failure_code") not in FAILURE_CODES
            or not failure.get("reason")
            or failure.get("authority") != _authority(status)
        ):
            raise OracleTerminalError("failure terminal differs")
        _accounting(failure.get("operation_accounting"))
        for value in _object(
            failure.get("verified_receipts"), "failure receipts"
        ).values():
            _digest(value, "failure receipt")
        return
    manifest = _canonical_object(payloads["manifest.json"], "terminal manifest")
    result = _canonical_object(payloads["oracle_result.json"], "oracle result")
    _validate_manifest(manifest, payloads, status)
    _validate_result(result, status, manifest)
    if status in FULL_STATUSES:
        for name, columns in CSV_SCHEMAS.items():
            rows = _csv_rows(payloads[name], columns, name)
            if payloads[name] != canonical_csv_bytes(columns, rows):
                raise OracleTerminalError(f"terminal CSV is not canonical: {name}")
        _validate_full_rows(payloads, result, status)


def validate_terminal_payloads(payloads: Mapping[str, bytes], status: str) -> None:
    """Independently validate one complete status-specific terminal package."""

    _validate_terminal(payloads, status)


def _validate_manifest(
    manifest: Mapping[str, Any], payloads: Mapping[str, bytes], status: str
) -> None:
    fields = {
        "schema_version",
        "contract_sha256",
        "status",
        "parent_receipts",
        "input_receipts",
        "source_receipts",
        "runtime_receipts",
        "randomization_receipts",
        "output_receipts",
        "operation_accounting",
        "authority",
    }
    if (
        set(manifest) != fields
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or manifest.get("status") != status
        or manifest.get("authority") != _authority(status)
    ):
        raise OracleTerminalError("terminal manifest binding differs")
    _accounting(manifest.get("operation_accounting"))
    parents = _object(manifest.get("parent_receipts"), "terminal parents")
    inputs = _object(manifest.get("input_receipts"), "terminal inputs")
    expected_parent_fields = (
        {
            "aggregate_accounting_sha256",
            "cleanup_manifest_sha256",
            "inner_selection_manifest_sha256",
            "outer_freeze_manifest_sha256",
            "outer_sealed_set_sha256",
            "prefit_support_sha256",
        }
        if status in FULL_STATUSES
        else {"cleanup_manifest_sha256", "prefit_support_sha256"}
    )
    if inputs != parents or set(parents) != expected_parent_fields:
        raise OracleTerminalError("terminal input/parent receipts differ")
    for values in (parents, inputs):
        for value in values.values():
            _digest(value, "terminal input receipt")
    if _object(manifest.get("source_receipts"), "terminal sources") != {
        "terminal_source_sha256": terminal_source_bundle_sha256()
    }:
        raise OracleTerminalError("terminal source receipt differs")
    runtime = _object(manifest.get("runtime_receipts"), "terminal runtime")
    if runtime != EXPECTED_RUNTIME:
        raise OracleTerminalError("terminal runtime differs")
    randomization = _object(manifest.get("randomization_receipts"), "randomization")
    if status in FULL_STATUSES and randomization != {
        "primary_bootstrap_seed": 20260821,
        "safety_bootstrap_seed": 20260822,
        "accepted_replicates": 2000,
        "maximum_attempts": 20000,
    }:
        raise OracleTerminalError("terminal randomization differs")
    if status == "R5_ORACLE_UNDERPOWERED" and randomization:
        raise OracleTerminalError("underpowered randomization differs")
    outputs = _object(manifest.get("output_receipts"), "terminal outputs")
    expected = {
        name: _receipt(name, data, CSV_SCHEMAS.get(name))
        for name, data in payloads.items()
        if name != "manifest.json"
    }
    if outputs != dict(sorted(expected.items())):
        raise OracleTerminalError("terminal output receipts differ")


def _validate_result(
    result: Mapping[str, Any], status: str, manifest: Mapping[str, Any]
) -> None:
    fields = {
        "schema_version",
        "contract_sha256",
        "parent_receipts",
        "status",
        "support",
        "criteria",
        "point_estimates",
        "bootstrap",
        "safety",
        "diagnostics",
        "operation_accounting",
        "authority",
    }
    if (
        set(result) != fields
        or result.get("schema_version") != RESULT_SCHEMA
        or result.get("contract_sha256") != RESOLVED_CONTRACT_SHA256
        or result.get("status") != status
        or result.get("authority") != _authority(status)
        or result.get("operation_accounting") != manifest.get("operation_accounting")
        or result.get("parent_receipts") != manifest.get("parent_receipts")
    ):
        raise OracleTerminalError("oracle result binding differs")
    for name in (
        "support",
        "criteria",
        "point_estimates",
        "bootstrap",
        "safety",
        "diagnostics",
    ):
        _object(result.get(name), f"oracle result {name}")
    if status == "R5_ORACLE_UNDERPOWERED" and any(
        result.get(name)
        for name in ("point_estimates", "bootstrap", "safety", "diagnostics")
    ):
        raise OracleTerminalError("underpowered sentinels differ")
    if status in FULL_STATUSES:
        criteria = _object(result.get("criteria"), "oracle criteria")
        signal = all(
            criteria.get(name) is True
            for name in (
                "all_required_bootstrap_lower_bounds_positive",
                "positive_G0_T0_cells_at_least_12",
                "each_repeat_positive_G0_T0_cells_at_least_3",
                "all_top10_leave_one_out_directions_positive",
                "safety_upper_95_below_0.01",
                "safety_worst_decile_degradation_at_most_0.05",
            )
        )
        if signal != (status == "R5_ORACLE_SIGNAL_PASS"):
            raise OracleTerminalError("oracle status criteria differ")
        accounting = _accounting(result.get("operation_accounting"))
        if (
            accounting["predictions_frozen"] <= 0
            or accounting["query_truth_values_opened_by_scorers"] <= 0
            or accounting["internal_absolute_error_evaluations"] <= 0
        ):
            raise OracleTerminalError("full terminal accounting differs")


def _validate_full_rows(
    payloads: Mapping[str, bytes], result: Mapping[str, Any], status: str
) -> None:
    selection = _csv_rows(
        payloads["oracle_inner_selection.csv"],
        SELECTION_COLUMNS,
        "inner selection",
    )
    try:
        _validate_selection_rows(selection)
    except OracleTerminalIOError as exc:
        raise OracleTerminalError(str(exc)) from exc
    scored = _csv_rows(
        payloads["oracle_scored_rows.csv"], SCORED_COLUMNS, "scored rows"
    )
    seen: set[tuple[str, str, str, str, str]] = set()
    order: list[tuple[int, int, int, int, str, int, str]] = []
    system_order = {system: index for index, system in enumerate(SYSTEMS)}
    population_order = {
        "primary_local_eligible": 0,
        "all_row_safety": 1,
        "diagnostic_stress": 2,
    }
    for row in scored:
        key = (
            row["population_id"],
            row["system_id"],
            row["episode_id"],
            row["query_rank"],
            row["query_molecule_id"],
        )
        if key in seen or any(
            name in row for name in ("query_point", "prediction", "anchor_point")
        ):
            raise OracleTerminalError("terminal scored row differs")
        seen.add(key)
        population = row["population_id"]
        system = row["system_id"]
        if population not in population_order:
            raise OracleTerminalError("terminal scored population differs")
        if population == "all_row_safety":
            if system not in {"G0", "SAFETY_FUSION"}:
                raise OracleTerminalError("terminal safety system differs")
            system_index = 0 if system == "G0" else 1
        else:
            if system not in system_order:
                raise OracleTerminalError("terminal scored system differs")
            system_index = system_order[system]
        repeat = _canonical_int(row["repeat"], "scored repeat")
        outer = _canonical_int(row["outer_fold"], "scored outer")
        rank = _canonical_int(row["query_rank"], "scored rank", minimum=1)
        if repeat not in range(3) or outer not in range(5):
            raise OracleTerminalError("terminal scored scope differs")
        order.append(
            (
                population_order[population],
                system_index,
                repeat,
                outer,
                row["episode_id"],
                rank,
                row["query_molecule_id"],
            )
        )
        for name in ("local_eligible", "local_available", "activity_cliff"):
            if row[name] not in {"true", "false"}:
                raise OracleTerminalError("terminal scored boolean differs")
        for name in ("exact_support_components", "class_support_components"):
            _canonical_int(row[name], f"scored {name}")
        for name in (
            "absolute_error",
            "query_weight",
            "episode_weight",
            "component_weight",
        ):
            _finite(row[name], f"scored {name}")
    if not scored or order != sorted(order):
        raise OracleTerminalError("terminal scored row order differs")
    bootstrap = _csv_rows(
        payloads["oracle_bootstrap_summary.csv"], BOOTSTRAP_COLUMNS, "bootstrap"
    )
    influence = _csv_rows(
        payloads["oracle_influence_checks.csv"], INFLUENCE_COLUMNS, "influence"
    )
    cells = _csv_rows(payloads["oracle_cell_metrics.csv"], CELL_COLUMNS, "cells")
    ablations = _csv_rows(
        payloads["oracle_ablation_scorecard.csv"], ABLATION_COLUMNS, "ablations"
    )
    if (
        len(bootstrap) != 10
        or [row["comparison_id"] for row in bootstrap]
        != [item[0] for item in REQUIRED_CONTRASTS]
        or len(influence) != 10
        or [row["rank"] for row in influence] != [str(rank) for rank in range(1, 11)]
        or len(cells) != 180
        or [(row["system_id"], row["repeat"], row["outer_fold"]) for row in cells]
        != [
            (system, str(repeat), str(outer))
            for system in SYSTEMS
            for repeat in range(3)
            for outer in range(5)
        ]
        or len(ablations) != 12
        or [row["system_id"] for row in ablations] != list(SYSTEMS)
    ):
        raise OracleTerminalError("terminal evidence cardinality differs")
    try:
        validate_scientific_evidence(
            status=status,
            scored_rows=scored,
            cell_rows=cells,
            bootstrap_rows=bootstrap,
            influence_rows=influence,
            ablation_rows=ablations,
            result=result,
        )
    except OracleTerminalValidationError as exc:
        raise OracleTerminalError(str(exc)) from exc


def _load_support(source: SupportInput) -> LoadedSupport:
    try:
        return load_support(source)
    except OracleTerminalIOError as exc:
        raise OracleTerminalError(str(exc)) from exc


def _manifest(
    status: str,
    parents: Mapping[str, str],
    inputs: Mapping[str, str],
    source: str,
    runtime: Mapping[str, str],
    randomization: Mapping[str, Any],
    outputs: Mapping[str, Any],
    accounting: Mapping[str, int],
    authority: Mapping[str, bool],
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "contract_sha256": RESOLVED_CONTRACT_SHA256,
        "status": status,
        "parent_receipts": dict(sorted(parents.items())),
        "input_receipts": dict(sorted(inputs.items())),
        "source_receipts": {"terminal_source_sha256": source},
        "runtime_receipts": dict(runtime),
        "randomization_receipts": dict(randomization),
        "output_receipts": dict(sorted(outputs.items())),
        "operation_accounting": dict(accounting),
        "authority": dict(authority),
    }


def _authority(status: str) -> dict[str, bool]:
    result = {
        "oracle_evidence": status != "R5_ORACLE_FAILED",
        "inferred_anchor_contract": status == "R5_ORACLE_SIGNAL_PASS",
        "model_fits": False,
        "predictions": False,
        "internal_metrics": status in FULL_STATUSES,
        "official_st_rae": False,
        "test_access": False,
        "tdi": False,
        "submission": False,
        "transduction": False,
    }
    return result


def _validate_source(expected: str) -> tuple[str, Mapping[str, str]]:
    try:
        return validate_execution(expected)
    except OracleTerminalIOError as exc:
        raise OracleTerminalError(str(exc)) from exc


def _accounting(value: Any) -> dict[str, int]:
    accounting = _object(value, "terminal accounting")
    if (
        set(accounting) != set(ACCOUNTING_FIELDS)
        or any(type(item) is not int or item < 0 for item in accounting.values())
        or any(accounting[name] for name in ACCOUNTING_FIELDS[8:])
    ):
        raise OracleTerminalError("terminal accounting differs")
    return cast(dict[str, int], accounting)


def _receipt(name: str, data: bytes, columns: Sequence[str] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "relative_path": name,
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
    }
    if columns is not None:
        result.update(rows=data.count(b"\n") - 1, columns=list(columns))
    return result


def _csv_rows(data: bytes, columns: Sequence[str], label: str) -> list[dict[str, str]]:
    if not data.endswith(b"\n") or b"\r" in data:
        raise OracleTerminalError(f"{label} line endings differ")
    try:
        reader = csv.reader(io.StringIO(data.decode(), newline=""), strict=True)
        if next(reader, None) != list(columns):
            raise OracleTerminalError(f"{label} columns differ")
        return [dict(zip(columns, values, strict=True)) for values in reader]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise OracleTerminalError(f"{label} is invalid") from exc


def _canonical_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        result = strict_json_object(data, label)
    except ValueError as exc:
        raise OracleTerminalError(str(exc)) from exc
    if data != _compact_json(result):
        raise OracleTerminalError(f"{label} is not canonical")
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


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleTerminalError(f"{label} is not an object")
    return dict(cast(Mapping[str, Any], value))


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OracleTerminalError(f"{label} is not SHA-256")
    return value


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleTerminalError(f"{label} is not finite") from exc
    if not math.isfinite(result) or format(result, ".17g") != value:
        raise OracleTerminalError(f"{label} is not canonical finite")
    return result


def _canonical_int(value: str, label: str, *, minimum: int = 0) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise OracleTerminalError(f"{label} differs") from exc
    if str(result) != value or result < minimum:
        raise OracleTerminalError(f"{label} differs")
    return result


__all__ = [
    "ABLATION_COLUMNS",
    "BOOTSTRAP_COLUMNS",
    "CELL_COLUMNS",
    "FAILURE_CODES",
    "FAILURE_STAGES",
    "FailureRecord",
    "INFLUENCE_COLUMNS",
    "OracleTerminalError",
    "RESULT_SCHEMA",
    "SCORED_COLUMNS",
    "STATUS_FILES",
    "SUPPORT_SCHEMA",
    "cleanup_private_roots",
    "publish_failed_terminal",
    "publish_underpowered_terminal",
    "validate_terminal_payloads",
]
