"""Receipt-only R3B V5 support preflight.

Preflight opens the model-public root only.  It never opens scorer-sealed
truth, features, predictions, scores, TDI, or blinded-test inputs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from cypshift.openadmet_global_io import (
    PREFLIGHT_SOURCE_FILES,
    PROJECTION_SOURCE_FILES,
    OpenADMETGlobalProjectionError,
    _csv_bytes,
    _digest_match,
    _digest_text,
    _json_bytes,
    _json_object,
    _lookup_fold,
    _new_file,
    _object,
    _parse_csv,
    _read_regular,
    _scope,
    _target_path,
    _validate_fold_index,
    _verify_count_equations,
)
from cypshift.openadmet_global_io import (
    _runtime_gate as _shared_runtime_gate,
)
from cypshift.openadmet_global_projection import (
    AUDIT_SCHEMA,
    DEFAULT_CONTRACT_PATH,
    ENDPOINTS,
    MODEL_COLUMNS,
    MODEL_SCHEMA,
    PREFLIGHT_SCHEMA,
    TARGET_COLUMNS,
    V4_CONTRACT_SHA256,
    V5_CONTRACT_SHA256,
    OpenADMETGlobalPreflightError,
    _verify_contract,
)


@dataclass(frozen=True, slots=True)
class GlobalPreflightResult:
    receipt: dict[str, Any]
    receipt_path: Path | None = None


def preflight_openadmet_global_targets(
    projection_directory: Path,
    *,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    expected_contract_sha256: str = V5_CONTRACT_SHA256,
    expected_model_public_manifest_sha256: str | None = None,
    expected_private_audit_sha256: str | None = None,
    expected_preflight_source_sha256: str | None = None,
    output_path: Path | None = None,
) -> GlobalPreflightResult:
    """Validate all target receipts and support arrays before any fit."""
    contract_data = _read_regular(contract_path, "v5 contract")
    _digest_match(contract_data, expected_contract_sha256, "v5 contract")
    contract = _json_object(contract_data, "v5 contract")
    authority, parent_data = _verify_contract(contract, contract_path)
    del parent_data
    contract_sha = sha256(contract_data).hexdigest()
    preflight_source_sha = _shared_runtime_gate(PREFLIGHT_SOURCE_FILES)
    if expected_preflight_source_sha256 is not None:
        _digest_text(expected_preflight_source_sha256, "preflight source acceptance")
        if preflight_source_sha != expected_preflight_source_sha256:
            raise OpenADMETGlobalPreflightError(
                "preflight source acceptance receipt mismatch"
            )
    projector_source_sha = _shared_runtime_gate(PROJECTION_SOURCE_FILES)

    root = projection_directory
    public = root / "model-public"
    manifest_path = public / "model_public_manifest.json"
    audit_path = root / "private_projection_audit.json"
    manifest_data = _read_regular(manifest_path, "model-public manifest")
    manifest_sha = sha256(manifest_data).hexdigest()
    if (
        expected_model_public_manifest_sha256 is not None
        and manifest_sha != expected_model_public_manifest_sha256
    ):
        raise OpenADMETGlobalPreflightError("model-public manifest SHA-256 mismatch")
    manifest = _json_object(manifest_data, "model-public manifest")
    _verify_public_manifest(
        manifest, manifest_sha, contract_sha, projector_source_sha, authority
    )

    audit_data = _read_regular(audit_path, "private projection audit")
    audit_sha = sha256(audit_data).hexdigest()
    if (
        expected_private_audit_sha256 is not None
        and audit_sha != expected_private_audit_sha256
    ):
        raise OpenADMETGlobalPreflightError("private projection audit SHA-256 mismatch")
    audit = _json_object(audit_data, "private projection audit")
    _verify_audit(
        audit,
        contract_sha,
        manifest_sha,
        audit_sha,
        projector_source_sha,
        authority,
    )
    audit_counts = _object(audit, "eligibility_counts")
    production_counts = _object(_object(contract, "amendments"), "eligibility_counts")[
        "production"
    ]
    if expected_preflight_source_sha256 is None and audit_counts.get(
        "direct_rows"
    ) == production_counts.get("direct_rows"):
        raise OpenADMETGlobalPreflightError(
            "official preflight requires preflight source acceptance receipt"
        )

    folds_path = public / "model_rows.csv"
    folds_data = _read_regular(folds_path, "model_rows.csv")
    fold_receipt = _object(manifest, "model_rows")
    if sha256(folds_data).hexdigest() != fold_receipt.get("sha256"):
        raise OpenADMETGlobalPreflightError("model_rows.csv receipt mismatch")
    fold_rows = _parse_csv(folds_data, MODEL_COLUMNS, "model_rows.csv")
    if len(fold_rows) != fold_receipt.get("rows") or fold_receipt.get(
        "columns"
    ) != list(MODEL_COLUMNS):
        raise OpenADMETGlobalPreflightError("model_rows.csv schema receipt mismatch")
    input_receipts = _object(audit, "input_receipts")
    if len(fold_rows) != input_receipts["fold_rows"]:
        raise OpenADMETGlobalPreflightError("model rows/input receipt mismatch")
    fold_index = _validate_preflight_folds(fold_rows, audit_counts)
    cells = _read_target_cells(public, manifest, contract_sha, fold_index)
    if len(cells) != 300:
        raise OpenADMETGlobalPreflightError("target cell count mismatch")
    _verify_preflight_totals(cells, audit_counts)

    support, outer_training, inner_training = _support_arrays(cells, fold_index)
    q90 = _q90_array(cells)
    reasons: list[str] = []
    if not all(record["passes"] for record in support):
        reasons.append("OUTER_COMPONENT_SUPPORT")
    if not all(record["passes"] for record in outer_training):
        reasons.append("OUTER_TRAINING_EMPTY")
    if not all(record["passes"] for record in inner_training):
        reasons.append("INNER_TRAINING_EMPTY")
    if not all(record["passes"] for record in q90):
        reasons.append("Q90_RESIDUAL_ELIGIBILITY_EMPTY")
    receipt = {
        "schema_version": PREFLIGHT_SCHEMA,
        "contract_sha256": contract_sha,
        "model_public_manifest_sha256": manifest_sha,
        "private_projection_audit_sha256": audit_sha,
        "checks": {
            "outer_score_support_cells": support,
            "outer_training_populations": outer_training,
            "inner_training_populations": inner_training,
            "q90_residual_eligibility_populations": q90,
        },
        "passed": not reasons,
        "failure_reasons": reasons,
        "accounting": _preflight_accounting(),
        "authority": authority,
    }
    result_path: Path | None = None
    if output_path is not None:
        try:
            _new_file(output_path, _json_bytes(receipt))
        except OpenADMETGlobalProjectionError as exc:
            raise OpenADMETGlobalPreflightError(str(exc)) from exc
        output_path.chmod(0o444)
        result_path = output_path
    return GlobalPreflightResult(receipt, result_path)


def _preflight_accounting() -> dict[str, int]:
    return {
        "preflight_target_files_opened": 300,
        "outer_model_target_files_opened": 0,
        "inner_model_target_files_opened": 0,
        "sealed_truth_files_opened": 0,
        "outer_model_fits": 0,
        "inner_model_fits": 0,
        "prediction_rows": 0,
        "provisional_metric_rows": 0,
        "tdi_files_opened": 0,
        "blinded_test_files_opened": 0,
        "episode_or_anchor_files_opened": 0,
        "official_metric_calls": 0,
        "submission_rows_opened": 0,
        "leaderboard_submissions": 0,
        "transductive_operations": 0,
        "gpu_fits": 0,
    }


def _verify_public_manifest(
    manifest: dict[str, Any],
    manifest_sha: str,
    contract_sha: str,
    source_sha: str,
    authority: dict[str, bool],
) -> None:
    expected = {
        "schema_version",
        "contract_sha256",
        "parent_contract_sha256",
        "projector_source_sha256",
        "model_rows",
        "outer_target_receipts",
        "inner_target_receipts",
        "accounting",
        "authority",
    }
    if set(manifest) != expected or manifest.get("schema_version") != MODEL_SCHEMA:
        raise OpenADMETGlobalPreflightError("model-public manifest schema mismatch")
    if (
        manifest.get("contract_sha256") != contract_sha
        or manifest.get("parent_contract_sha256") != V4_CONTRACT_SHA256
    ):
        raise OpenADMETGlobalPreflightError("model-public manifest contract mismatch")
    if manifest.get("projector_source_sha256") != source_sha:
        raise OpenADMETGlobalPreflightError("projector source receipt mismatch")
    if manifest.get("authority") != authority:
        raise OpenADMETGlobalPreflightError("model-public authority mismatch")
    if manifest.get("accounting") != {
        "truth_paths": 0,
        "truth_hashes": 0,
        "scores": 0,
        "metrics": 0,
    }:
        raise OpenADMETGlobalPreflightError("public accounting mismatch")
    _reject_public_metadata(manifest)
    model_rows = _object(manifest, "model_rows")
    if set(model_rows) != {
        "path",
        "sha256",
        "bytes",
        "rows",
        "columns",
        "schema_version",
    }:
        raise OpenADMETGlobalPreflightError("model rows receipt fields mismatch")
    if model_rows.get("path") != "model_rows.csv" or model_rows.get("columns") != list(
        MODEL_COLUMNS
    ):
        raise OpenADMETGlobalPreflightError("model rows receipt schema mismatch")
    if (
        not isinstance(model_rows.get("sha256"), str)
        or not isinstance(model_rows.get("bytes"), int)
        or not isinstance(model_rows.get("rows"), int)
        or model_rows["bytes"] < 0
        or model_rows["rows"] < 0
    ):
        raise OpenADMETGlobalPreflightError("model rows receipt types mismatch")
    _digest_text(model_rows["sha256"], "model rows receipt")
    outer = manifest.get("outer_target_receipts")
    inner = manifest.get("inner_target_receipts")
    if (
        not isinstance(outer, list)
        or len(outer) != 60
        or not isinstance(inner, list)
        or len(inner) != 240
    ):
        raise OpenADMETGlobalPreflightError("target receipt cardinality mismatch")
    for receipt in [*outer, *inner]:
        if not isinstance(receipt, dict) or set(receipt) != {
            "stage",
            "cell_id",
            "endpoint",
            "repeat",
            "outer_fold",
            "inner_fold",
            "relative_path",
            "sha256",
            "rows",
            "identity_sha256",
        }:
            raise OpenADMETGlobalPreflightError("target receipt fields mismatch")
        _validate_target_receipt(receipt)


def _validate_target_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt["stage"] not in {"outer", "inner"}:
        raise OpenADMETGlobalPreflightError("target receipt stage mismatch")
    if (
        not isinstance(receipt["cell_id"], str)
        or not isinstance(receipt["endpoint"], str)
        or not isinstance(receipt["relative_path"], str)
        or not isinstance(receipt["sha256"], str)
        or not isinstance(receipt["identity_sha256"], str)
        or not isinstance(receipt["repeat"], int)
        or isinstance(receipt["repeat"], bool)
        or not isinstance(receipt["outer_fold"], int)
        or isinstance(receipt["outer_fold"], bool)
        or not isinstance(receipt["inner_fold"], (int, str))
        or not isinstance(receipt["rows"], int)
        or isinstance(receipt["rows"], bool)
        or receipt["rows"] < 0
    ):
        raise OpenADMETGlobalPreflightError("target receipt types mismatch")
    if receipt["inner_fold"] not in {"", 0, 1, 2, 3}:
        raise OpenADMETGlobalPreflightError("target receipt inner fold mismatch")
    _digest_text(receipt["cell_id"], "target cell id")
    _digest_text(receipt["sha256"], "target receipt")
    _digest_text(receipt["identity_sha256"], "target identity receipt")


def _reject_public_metadata(value: Any, path: str = "manifest") -> None:
    forbidden = (
        "truth path",
        "truth sha256",
        "truth row count",
        "private audit path",
        "private audit sha256",
        "score",
        "metric",
    )
    if isinstance(value, dict):
        if path in {"manifest.accounting", "manifest.authority"}:
            return
        for key, item in value.items():
            normalized = key.replace("_", " ").lower()
            if any(token in normalized for token in forbidden):
                raise OpenADMETGlobalPreflightError(
                    f"forbidden public metadata at {path}.{key}"
                )
            _reject_public_metadata(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_public_metadata(item, f"{path}[{index}]")


def _verify_audit(
    audit: dict[str, Any],
    contract_sha: str,
    manifest_sha: str,
    audit_sha: str,
    source_sha: str,
    authority: dict[str, bool],
) -> None:
    expected = {
        "schema_version",
        "contract_sha256",
        "parent_contract_sha256",
        "input_receipts",
        "model_public_manifest_sha256",
        "sealed_truth_manifest_sha256",
        "eligibility_counts",
        "projector_source_sha256",
        "accounting",
        "authority",
    }
    if set(audit) != expected or audit.get("schema_version") != AUDIT_SCHEMA:
        raise OpenADMETGlobalPreflightError("private audit schema mismatch")
    if (
        audit.get("contract_sha256") != contract_sha
        or audit.get("parent_contract_sha256") != V4_CONTRACT_SHA256
    ):
        raise OpenADMETGlobalPreflightError("private audit contract mismatch")
    if (
        audit.get("model_public_manifest_sha256") != manifest_sha
        or audit.get("projector_source_sha256") != source_sha
    ):
        raise OpenADMETGlobalPreflightError("private audit receipt mismatch")
    if audit.get("authority") != authority:
        raise OpenADMETGlobalPreflightError("private audit authority mismatch")
    receipts = _object(audit, "input_receipts")
    if set(receipts) != {
        "parent_contract_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "direct_rows",
        "fold_rows",
    }:
        raise OpenADMETGlobalPreflightError("private input receipt fields mismatch")
    if receipts.get("parent_contract_sha256") != V4_CONTRACT_SHA256:
        raise OpenADMETGlobalPreflightError("private audit input parent mismatch")
    for key in ("direct_observations_sha256", "group_folds_sha256"):
        _digest_text(receipts[key], f"input receipt {key}")
    if any(
        not isinstance(receipts[key], int)
        or isinstance(receipts[key], bool)
        or receipts[key] < 0
        for key in ("direct_rows", "fold_rows")
    ):
        raise OpenADMETGlobalPreflightError("private input receipt types mismatch")
    accounting = _object(audit, "accounting")
    expected_keys = {
        "outer_target_files_written",
        "inner_target_files_written",
        "sealed_truth_files_written",
        "direct_observation_rows_parsed",
        "target_rows_written",
        "truth_rows_written",
        "tdi_files_opened",
        "blinded_test_rows_opened",
        "episode_or_anchor_files_opened",
        "transductive_operations",
    }
    if (
        set(accounting) != expected_keys
        or accounting["outer_target_files_written"] != 60
        or accounting["inner_target_files_written"] != 240
        or accounting["sealed_truth_files_written"] != 2
    ):
        raise OpenADMETGlobalPreflightError("projector accounting mismatch")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in accounting.values()
    ):
        raise OpenADMETGlobalPreflightError("projector accounting types mismatch")
    if (
        accounting["tdi_files_opened"] != 0
        or accounting["blinded_test_rows_opened"] != 0
        or accounting["episode_or_anchor_files_opened"] != 0
        or accounting["transductive_operations"] != 0
    ):
        raise OpenADMETGlobalPreflightError("projector firewall accounting mismatch")
    counts = _object(audit, "eligibility_counts")
    expected_count_keys = {
        "direct_rows",
        "eligible",
        "ineligible",
        "complete",
        "partial",
        "missing",
        "orphan_auxiliary",
        "outer_target_files",
        "inner_target_files",
        "outer_target_rows",
        "inner_target_rows",
        "outer_truth_rows",
        "inner_truth_rows",
        "outer_truth_eligible",
        "inner_truth_eligible",
    }
    if set(counts) != expected_count_keys:
        raise OpenADMETGlobalPreflightError("private eligibility count schema mismatch")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in counts.values()
    ):
        raise OpenADMETGlobalPreflightError("private eligibility count types mismatch")
    if receipts["direct_rows"] != counts["direct_rows"]:
        raise OpenADMETGlobalPreflightError("input/eligibility count mismatch")
    _verify_count_equations(counts)
    if accounting["direct_observation_rows_parsed"] != receipts["direct_rows"]:
        raise OpenADMETGlobalPreflightError("projector direct-row accounting mismatch")
    if (
        accounting["target_rows_written"]
        != counts["outer_target_rows"] + counts["inner_target_rows"]
        or accounting["truth_rows_written"]
        != counts["outer_truth_rows"] + counts["inner_truth_rows"]
    ):
        raise OpenADMETGlobalPreflightError("projector total accounting mismatch")
    _digest_text(audit["sealed_truth_manifest_sha256"], "sealed truth manifest")
    del audit_sha


def _validate_preflight_folds(
    rows: list[dict[str, str]], counts: Mapping[str, Any]
) -> dict[tuple[str, int, int], dict[str, str]]:
    return _validate_fold_index(
        rows,
        int(counts["direct_rows"]),
        len(rows),
        (20260810, 20260811, 20260812),
    )


def _read_target_cells(
    public: Path,
    manifest: Mapping[str, Any],
    contract_sha: str,
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> dict[tuple[str, str, int, int, int | None], list[dict[str, str]]]:
    result: dict[tuple[str, str, int, int, int | None], list[dict[str, str]]] = {}
    pending: list[tuple[str, Mapping[str, Any], Path, bytes]] = []
    for stage, field in (
        ("outer", "outer_target_receipts"),
        ("inner", "inner_target_receipts"),
    ):
        records = manifest[field]
        for receipt in records:
            relative = str(receipt["relative_path"])
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise OpenADMETGlobalPreflightError("unsafe target path")
            path = public / relative_path
            data = _read_regular(path, relative)
            if sha256(data).hexdigest() != receipt["sha256"]:
                raise OpenADMETGlobalPreflightError("target receipt mismatch")
            pending.append((stage, receipt, relative_path, data))
    for stage, receipt, relative_path, data in pending:
        relative = relative_path.as_posix()
        rows = _parse_csv(data, TARGET_COLUMNS, relative)
        if len(rows) != receipt["rows"]:
            raise OpenADMETGlobalPreflightError("target row count mismatch")
        endpoint = receipt["endpoint"]
        repeat = receipt["repeat"]
        outer = receipt["outer_fold"]
        inner = None if receipt["inner_fold"] == "" else receipt["inner_fold"]
        if (
            endpoint not in ENDPOINTS
            or repeat not in range(3)
            or outer not in range(5)
            or (inner is not None and inner not in range(4))
        ):
            raise OpenADMETGlobalPreflightError("target cell identity out of range")
        if receipt["stage"] != stage or relative_path != _target_path(
            stage, endpoint, repeat, outer, inner
        ):
            raise OpenADMETGlobalPreflightError("target cell path mismatch")
        scope = _scope(stage, outer)
        token = "none" if inner is None else str(inner)
        material = "|".join(
            (contract_sha, stage, endpoint, str(repeat), str(outer), token, scope)
        )
        if receipt["cell_id"] != sha256(material.encode()).hexdigest():
            raise OpenADMETGlobalPreflightError("target cell id mismatch")
        _validate_target_rows(rows, folds, stage, repeat, outer, inner)
        identity_rows = [
            {
                "observation_id": row["observation_id"],
                "molecule_id": row["molecule_id"],
            }
            for row in rows
        ]
        identity = _csv_bytes(("observation_id", "molecule_id"), identity_rows)
        if sha256(identity).hexdigest() != receipt["identity_sha256"]:
            raise OpenADMETGlobalPreflightError("target identity receipt mismatch")
        key = (stage, endpoint, repeat, outer, inner)
        if key in result:
            raise OpenADMETGlobalPreflightError("duplicate target cell")
        result[key] = rows
    return result


def _validate_target_rows(
    rows: list[dict[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    stage: str,
    repeat: int,
    outer: int,
    inner: int | None,
) -> None:
    molecule_ids = [row["molecule_id"] for row in rows]
    observation_ids = [row["observation_id"] for row in rows]
    if any(
        not molecule or not observation
        for molecule, observation in zip(molecule_ids, observation_ids, strict=True)
    ):
        raise OpenADMETGlobalPreflightError("target identity is empty")
    if len(set(molecule_ids)) != len(rows) or len(set(observation_ids)) != len(rows):
        raise OpenADMETGlobalPreflightError("target identity is not unique")
    for row in rows:
        try:
            finite = math.isfinite(float(row["point"]))
        except ValueError:
            finite = False
        if not finite:
            raise OpenADMETGlobalPreflightError("target contains a nonfinite point")
        fold = _lookup_fold(folds, row["molecule_id"], repeat, outer)
        assigned_outer = int(fold["outer_fold"])
        if stage == "outer" and assigned_outer == outer:
            raise OpenADMETGlobalPreflightError(
                "outer target violates training membership"
            )
        if stage == "inner" and (
            assigned_outer == outer or int(fold["inner_fold"]) == inner
        ):
            raise OpenADMETGlobalPreflightError(
                "inner target violates training membership"
            )


def _support_arrays(
    cells: Mapping[tuple[str, str, int, int, int | None], list[dict[str, str]]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    support: list[dict[str, Any]] = []
    outer_training: list[dict[str, Any]] = []
    inner_training: list[dict[str, Any]] = []
    for endpoint in ENDPOINTS:
        universe = {
            row["molecule_id"]
            for key, rows in cells.items()
            if key[0] == "outer" and key[1] == endpoint
            for row in rows
        }
        for repeat in range(3):
            for outer in range(5):
                training = {
                    row["molecule_id"]
                    for row in cells[("outer", endpoint, repeat, outer, None)]
                }
                heldout = universe - training
                components = {
                    _lookup_fold(folds, molecule, repeat, outer)[
                        "similarity_component_hash"
                    ]
                    for molecule in heldout
                }
                support.append(
                    {
                        "endpoint": endpoint,
                        "repeat": repeat,
                        "outer_fold": outer,
                        "component_count": len(components),
                        "minimum_components": 10,
                        "passes": len(components) >= 10,
                    }
                )
                outer_training.append(
                    _population("outer", endpoint, repeat, outer, None, len(training))
                )
                for inner in range(4):
                    rows = cells[("inner", endpoint, repeat, outer, inner)]
                    inner_training.append(
                        _population("inner", endpoint, repeat, outer, inner, len(rows))
                    )
    return support, outer_training, inner_training


def _verify_preflight_totals(
    cells: Mapping[tuple[str, str, int, int, int | None], list[dict[str, str]]],
    counts: Mapping[str, Any],
) -> None:
    outer_rows = sum(len(rows) for key, rows in cells.items() if key[0] == "outer")
    inner_rows = sum(len(rows) for key, rows in cells.items() if key[0] == "inner")
    if (
        counts["outer_target_files"] != 60
        or counts["inner_target_files"] != 240
        or counts["outer_target_rows"] != outer_rows
        or counts["inner_target_rows"] != inner_rows
    ):
        raise OpenADMETGlobalPreflightError("recomputed target totals mismatch")


def _q90_array(
    cells: Mapping[tuple[str, str, int, int, int | None], list[dict[str, str]]],
) -> list[dict[str, Any]]:
    return [
        {
            "endpoint": endpoint,
            "repeat": repeat,
            "outer_fold": outer,
            "eligible_residuals": len(cells[("outer", endpoint, repeat, outer, None)]),
            "minimum_eligible_targets": 1,
            "passes": len(cells[("outer", endpoint, repeat, outer, None)]) >= 1,
        }
        for endpoint in ENDPOINTS
        for repeat in range(3)
        for outer in range(5)
    ]


def _population(
    stage: str, endpoint: str, repeat: int, outer: int, inner: int | None, count: int
) -> dict[str, Any]:
    return {
        "stage": stage,
        "endpoint": endpoint,
        "repeat": repeat,
        "outer_fold": outer,
        "inner_fold": "" if inner is None else inner,
        "eligible_targets": count,
        "minimum_eligible_targets": 1,
        "passes": count >= 1,
    }


__all__ = ["GlobalPreflightResult", "preflight_openadmet_global_targets"]
