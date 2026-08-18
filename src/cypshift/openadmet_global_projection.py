"""Receipt-bound OpenADMET V5 target projection; preflight is split out."""

from __future__ import annotations

import math
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from cypshift.openadmet_global_io import (
    PROJECTION_SOURCE_FILES,
    OpenADMETGlobalProjectionError,
    _cleanup_stage,
    _csv_bytes,
    _digest,
    _digest_match,
    _digest_text,
    _file_receipt,
    _inner_truth_key,
    _json_bytes,
    _json_object,
    _new_file,
    _object,
    _occupied,
    _outer_truth_key,
    _parse_csv,
    _read_regular,
    _readonly_tree,
    _rename_noreplace,
    _resolve_parent,
    _scope,
    _target_path,
    _target_receipt,
    _truth_eligible,
    _validate_fold_index,
    _verify_count_equations,
    _verify_projection_counts,
    _verify_staged_projection,
)
from cypshift.openadmet_global_io import (
    _runtime_gate as _shared_runtime_gate,
)
from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS

V5_SCHEMA = "cypshift.openadmet_cyp_2026.global_experiment_contract.v5"
V5_CONTRACT_SHA256 = "596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2"
V4_SCHEMA = "cypshift.openadmet_cyp_2026.global_experiment_contract.v4"
V4_CONTRACT_SHA256 = "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254"
V3_SCHEMA = "cypshift.openadmet_cyp_2026.global_experiment_contract.v3"
V3_CONTRACT_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_experiment_contract_v5.json"
)
MODEL_SCHEMA = "cypshift.openadmet_cyp_2026.r3b_model_public.v5"
SEALED_SCHEMA = "cypshift.openadmet_cyp_2026.r3b_sealed_truth.v5"
AUDIT_SCHEMA = "cypshift.openadmet_cyp_2026.r3b_projection_audit.v5"
PREFLIGHT_SCHEMA = "cypshift.openadmet_cyp_2026.r3b_preflight.v5"
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
SEEDS = (20260810, 20260811, 20260812)
MODEL_COLUMNS = FOLD_COLUMNS
TARGET_COLUMNS = ("observation_id", "molecule_id", "point")
TRUTH_COLUMNS = (
    "observation_id",
    "molecule_id",
    "endpoint",
    "component_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "scope",
    "value_state",
    "point_eligible",
    "point",
    "low",
    "high",
    "std",
)
ELIGIBILITY_KEYS = {
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


class OpenADMETGlobalPreflightError(ValueError):
    """A preflight input or post-projection invariant failed."""


@dataclass(frozen=True, slots=True)
class GlobalProjectionResult:
    output_directory: Path
    model_public_root: Path
    scorer_sealed_root: Path
    model_public_manifest: Path
    sealed_truth_manifest: Path
    private_audit: Path
    model_public_manifest_sha256: str
    sealed_truth_manifest_sha256: str
    private_audit_sha256: str
    eligibility_counts: dict[str, int]


def project_openadmet_global_targets(
    direct_observations_path: Path,
    group_folds_path: Path,
    output_directory: Path,
    *,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    expected_contract_sha256: str = V5_CONTRACT_SHA256,
    expected_input_receipts: Mapping[str, str] | None = None,
    expected_counts: Mapping[str, int] | None = None,
    expected_projector_source_sha256: str | None = None,
) -> GlobalProjectionResult:
    """Project all 300 target cells and both sealed truth files atomically."""
    if _occupied(output_directory):
        raise OpenADMETGlobalProjectionError(
            "output path already exists; refusing overwrite"
        )

    contract_data = _read_regular(contract_path, "v5 contract")
    _digest_match(contract_data, expected_contract_sha256, "v5 contract")
    contract = _json_object(contract_data, "v5 contract")
    authority, parent_data = _verify_contract(contract, contract_path)
    contract_sha = sha256(contract_data).hexdigest()
    projector_source_sha = _runtime_gate()
    if expected_projector_source_sha256 is not None:
        _digest_text(expected_projector_source_sha256, "projector source acceptance")
        if projector_source_sha != expected_projector_source_sha256:
            raise OpenADMETGlobalProjectionError(
                "projector source acceptance receipt mismatch"
            )
    elif expected_input_receipts is None and expected_counts is None:
        raise OpenADMETGlobalProjectionError(
            "official projection requires projector source acceptance receipt"
        )

    input_receipts = _input_receipts(parent_data, expected_input_receipts)
    direct_data = _read_regular(direct_observations_path, "direct_observations.csv")
    folds_data = _read_regular(group_folds_path, "group_folds.csv")
    _digest_match(
        direct_data, input_receipts["direct_observations_sha256"], "direct observations"
    )
    _digest_match(folds_data, input_receipts["group_folds_sha256"], "group folds")
    direct_rows = _parse_csv(direct_data, OBSERVATION_COLUMNS, "direct observations")
    fold_rows = _parse_csv(folds_data, FOLD_COLUMNS, "group folds")
    counts = _initial_counts(contract, direct_rows, fold_rows, expected_counts)
    observations, eligible = _validate_observations(direct_rows, counts)
    fold_index = _validate_folds(fold_rows, counts)
    if {key[0] for key in observations} != {row["molecule_id"] for row in fold_rows}:
        raise OpenADMETGlobalProjectionError("direct/fold molecule membership mismatch")

    outer_targets, outer_truth, inner_targets, inner_truth = _build_cells(
        observations, eligible, fold_index, contract_sha
    )
    outer_truth.sort(key=_outer_truth_key)
    inner_truth.sort(key=_inner_truth_key)
    counts.update(
        outer_target_files=len(outer_targets),
        inner_target_files=len(inner_targets),
        outer_target_rows=sum(len(rows) for rows in outer_targets.values()),
        inner_target_rows=sum(len(rows) for rows in inner_targets.values()),
        outer_truth_rows=len(outer_truth),
        inner_truth_rows=len(inner_truth),
        outer_truth_eligible=sum(_truth_eligible(row) for row in outer_truth),
        inner_truth_eligible=sum(_truth_eligible(row) for row in inner_truth),
    )
    _verify_count_equations(counts)
    _verify_projection_counts(contract, counts, expected_counts)

    stage_parent = output_directory.parent
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".r3b-projection-", dir=stage_parent))
    try:
        public = stage / "model-public"
        sealed = stage / "scorer-sealed"
        public.mkdir()
        sealed.mkdir()
        _write_projection_files(
            public,
            sealed,
            folds_data,
            outer_targets,
            inner_targets,
            outer_truth,
            inner_truth,
        )
        outer_receipts = _receipts_for_targets("outer", outer_targets, contract_sha)
        inner_receipts = _receipts_for_targets("inner", inner_targets, contract_sha)
        if len(outer_receipts) != 60 or len(inner_receipts) != 240:
            raise OpenADMETGlobalProjectionError("target receipt cardinality mismatch")
        model_manifest = _model_manifest(
            contract_sha,
            authority,
            projector_source_sha,
            folds_data,
            fold_rows,
            outer_receipts,
            inner_receipts,
        )
        sealed_manifest = _sealed_manifest(
            contract_sha, authority, projector_source_sha, outer_truth, inner_truth
        )
        model_manifest_data = _json_bytes(model_manifest)
        sealed_manifest_data = _json_bytes(sealed_manifest)
        _new_file(public / "model_public_manifest.json", model_manifest_data)
        _new_file(sealed / "sealed_truth_manifest.json", sealed_manifest_data)
        model_manifest_sha = sha256(model_manifest_data).hexdigest()
        sealed_manifest_sha = sha256(sealed_manifest_data).hexdigest()
        audit = _audit_receipt(
            contract_sha,
            authority,
            input_receipts,
            model_manifest_sha,
            sealed_manifest_sha,
            counts,
            projector_source_sha,
        )
        audit_data = _json_bytes(audit)
        _new_file(stage / "private_projection_audit.json", audit_data)
        _verify_staged_projection(
            stage,
            contract_sha,
            counts["direct_rows"],
            folds_data,
            model_manifest_data,
            sealed_manifest_data,
            audit_data,
            outer_targets,
            inner_targets,
            outer_truth,
            inner_truth,
            MODEL_COLUMNS,
            TARGET_COLUMNS,
            TRUTH_COLUMNS,
        )
        _readonly_tree(stage)
        if _occupied(output_directory):
            raise OpenADMETGlobalProjectionError(
                "output path already exists; refusing overwrite"
            )
        _rename_noreplace(stage, output_directory)
        stage = None  # type: ignore[assignment]
    except Exception:
        _cleanup_stage(stage)
        raise

    return GlobalProjectionResult(
        output_directory,
        output_directory / "model-public",
        output_directory / "scorer-sealed",
        output_directory / "model-public" / "model_public_manifest.json",
        output_directory / "scorer-sealed" / "sealed_truth_manifest.json",
        output_directory / "private_projection_audit.json",
        model_manifest_sha,
        sealed_manifest_sha,
        sha256(audit_data).hexdigest(),
        counts,
    )


def preflight_openadmet_global_targets(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper for the split preflight module."""
    from cypshift.openadmet_global_preflight import (
        preflight_openadmet_global_targets as run,
    )

    return run(*args, **kwargs)


def _verify_contract(
    contract: Mapping[str, Any], contract_path: Path
) -> tuple[dict[str, bool], bytes]:
    if contract.get("schema_version") != V5_SCHEMA:
        raise OpenADMETGlobalProjectionError("strict v5 contract schema mismatch")
    parent = _object(contract, "parent")
    if (
        parent.get("schema_version") != V4_SCHEMA
        or parent.get("sha256") != V4_CONTRACT_SHA256
    ):
        raise OpenADMETGlobalProjectionError("strict v4 parent receipt mismatch")
    parent_path = _resolve_parent(contract_path, str(parent.get("path", "")))
    parent_data = _read_regular(parent_path, "v4 parent contract")
    _digest_match(parent_data, V4_CONTRACT_SHA256, "v4 parent contract")
    parent_contract = _json_object(parent_data, "v4 parent contract")
    if parent_contract.get("schema_version") != V4_SCHEMA:
        raise OpenADMETGlobalProjectionError("v4 parent schema mismatch")
    grandparent = _object(parent_contract, "parent")
    if (
        grandparent.get("schema_version") != V3_SCHEMA
        or grandparent.get("sha256") != V3_CONTRACT_SHA256
    ):
        raise OpenADMETGlobalProjectionError("strict v3 receipt-chain mismatch")
    grandparent_path = _resolve_parent(parent_path, str(grandparent.get("path", "")))
    _digest_match(
        _read_regular(grandparent_path, "v3 parent contract"),
        V3_CONTRACT_SHA256,
        "v3 parent contract",
    )
    authority = _object(parent_contract, "authority").get("INHERITED_ONLY")
    if not isinstance(authority, dict) or not all(
        isinstance(value, bool) for value in authority.values()
    ):
        raise OpenADMETGlobalProjectionError("parent authority is not a boolean object")
    if _object(contract, "authority").get("source") != "parent.authority":
        raise OpenADMETGlobalProjectionError("v5 authority does not reference parent")
    return cast(dict[str, bool], authority), parent_data


def _runtime_gate() -> str:
    return _shared_runtime_gate(PROJECTION_SOURCE_FILES)


def _input_receipts(
    parent_data: bytes, override: Mapping[str, str] | None
) -> dict[str, str]:
    parent = _json_object(parent_data, "v4 parent contract")
    inputs = _object(_object(parent, "target_projection"), "inputs")
    result = {
        "direct_observations_sha256": _digest(inputs, "direct_observations_sha256"),
        "group_folds_sha256": _digest(inputs, "group_folds_sha256"),
    }
    if override is not None:
        for key in result:
            value = override.get(key)
            if not isinstance(value, str):
                raise OpenADMETGlobalProjectionError(f"missing fixture receipt: {key}")
            _digest_text(value, key)
            result[key] = value
    return result


def _initial_counts(
    contract: Mapping[str, Any],
    direct: Sequence[Mapping[str, str]],
    folds: Sequence[Mapping[str, str]],
    override: Mapping[str, int] | None,
) -> dict[str, int]:
    official = _object(_object(contract, "amendments"), "eligibility_counts")[
        "production"
    ]
    values = {"direct_rows": len(direct), "fold_rows": len(folds)}
    if override is None:
        if set(official) != ELIGIBILITY_KEYS:
            raise OpenADMETGlobalProjectionError("production count schema mismatch")
        expected = {
            key: int(value) for key, value in official.items() if isinstance(value, int)
        }
    else:
        if set(override) - (ELIGIBILITY_KEYS | {"fold_rows"}):
            raise OpenADMETGlobalProjectionError("invalid expected count key")
        expected = {
            key: int(value)
            for key, value in override.items()
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        }
        if set(expected) != set(override):
            raise OpenADMETGlobalProjectionError("invalid expected count override")
    for key in ("direct_rows", "fold_rows"):
        if key in expected and values[key] != expected[key]:
            raise OpenADMETGlobalProjectionError(f"input {key} mismatch")
    if (
        values["direct_rows"] % 4
        or values["fold_rows"] != values["direct_rows"] // 4 * 15
    ):
        raise OpenADMETGlobalProjectionError(
            "synthetic population is not four-endpoint/15-context aligned"
        )
    return {**expected, **values}


def _validate_observations(
    rows: Sequence[Mapping[str, str]], counts: dict[str, int]
) -> tuple[dict[tuple[str, str], dict[str, str]], set[tuple[str, str]]]:
    states = {"complete", "partial", "missing", "orphan_auxiliary"}
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    observation_ids: set[str] = set()
    eligible: set[tuple[str, str]] = set()
    state_counts = {state: 0 for state in states}
    for row in rows:
        key = (row["molecule_id"], row["endpoint"])
        if (
            not row["observation_id"]
            or row["observation_id"] in observation_ids
            or key in by_key
        ):
            raise OpenADMETGlobalProjectionError(
                "duplicate direct observation identity"
            )
        if not row["molecule_id"] or row["endpoint"] not in ENDPOINTS:
            raise OpenADMETGlobalProjectionError("invalid direct observation identity")
        if row["value_state"] not in states or row["point_eligible"] not in (
            "true",
            "false",
        ):
            raise OpenADMETGlobalProjectionError("invalid direct observation state")
        observation_ids.add(row["observation_id"])
        by_key[key] = dict(row)
        state_counts[row["value_state"]] += 1
        if row["value_state"] == "complete" and row["point_eligible"] == "true":
            try:
                if math.isfinite(float(row["point"])):
                    eligible.add(key)
            except ValueError:
                pass
    molecules = {molecule for molecule, _ in by_key}
    if any(
        sum((molecule, endpoint) in by_key for endpoint in ENDPOINTS) != 4
        for molecule in molecules
    ):
        raise OpenADMETGlobalProjectionError(
            "direct rows do not contain exactly four endpoints per molecule"
        )
    observed = {
        **state_counts,
        "eligible": len(eligible),
        "ineligible": len(rows) - len(eligible),
    }
    for count_key, value in observed.items():
        expected = counts.get(count_key)
        if expected is not None and expected >= 0 and expected != value:
            raise OpenADMETGlobalProjectionError(
                f"eligibility count mismatch: {count_key}"
            )
    counts.update(observed)
    return by_key, eligible


def _validate_folds(
    rows: Sequence[Mapping[str, str]], counts: Mapping[str, int]
) -> dict[tuple[str, int, int], dict[str, str]]:
    return _validate_fold_index(rows, counts["direct_rows"], counts["fold_rows"], SEEDS)


def _build_cells(
    observations: Mapping[tuple[str, str], Mapping[str, str]],
    eligible: set[tuple[str, str]],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    contract_sha: str,
) -> tuple[
    dict[tuple[str, int, int, None], list[dict[str, str]]],
    list[dict[str, str]],
    dict[tuple[str, int, int, int], list[dict[str, str]]],
    list[dict[str, str]],
]:
    molecules = sorted({molecule for molecule, _ in observations})
    outer: dict[tuple[str, int, int, None], list[dict[str, str]]] = {
        (endpoint, repeat, outer_fold, None): []
        for endpoint in ENDPOINTS
        for repeat in range(3)
        for outer_fold in range(5)
    }
    inner: dict[tuple[str, int, int, int], list[dict[str, str]]] = {
        (endpoint, repeat, outer_fold, inner_fold): []
        for endpoint in ENDPOINTS
        for repeat in range(3)
        for outer_fold in range(5)
        for inner_fold in range(4)
    }
    outer_truth: list[dict[str, str]] = []
    inner_truth: list[dict[str, str]] = []
    for endpoint in ENDPOINTS:
        for repeat in range(3):
            for context in range(5):
                for molecule in molecules:
                    fold = folds[(molecule, repeat, context)]
                    observation = observations[(molecule, endpoint)]
                    target = {
                        "observation_id": observation["observation_id"],
                        "molecule_id": molecule,
                        "point": observation["point"],
                    }
                    assigned_outer = int(fold["outer_fold"])
                    if assigned_outer != context:
                        assigned_inner = int(fold["inner_fold"])
                        if (molecule, endpoint) in eligible:
                            outer[(endpoint, repeat, context, None)].append(target)
                            for inner_fold in range(4):
                                if assigned_inner != inner_fold:
                                    inner[
                                        (endpoint, repeat, context, inner_fold)
                                    ].append(target)
                        inner_truth.append(
                            _truth(
                                observation,
                                fold,
                                endpoint,
                                repeat,
                                context,
                                assigned_inner,
                                _scope("inner", context),
                            )
                        )
                    else:
                        outer_truth.append(
                            _truth(
                                observation,
                                fold,
                                endpoint,
                                repeat,
                                context,
                                None,
                                _scope("outer", context),
                            )
                        )
                outer[(endpoint, repeat, context, None)].sort(
                    key=lambda row: row["molecule_id"]
                )
                for inner_fold in range(4):
                    inner[(endpoint, repeat, context, inner_fold)].sort(
                        key=lambda row: row["molecule_id"]
                    )
    return outer, outer_truth, inner, inner_truth


def _truth(
    observation: Mapping[str, str],
    fold: Mapping[str, str],
    endpoint: str,
    repeat: int,
    outer: int,
    inner: int | None,
    scope: str,
) -> dict[str, str]:
    return {
        "observation_id": observation["observation_id"],
        "molecule_id": observation["molecule_id"],
        "endpoint": endpoint,
        "component_id": fold["similarity_component_hash"],
        "repeat": str(repeat),
        "outer_fold": str(outer),
        "inner_fold": "" if inner is None else str(inner),
        "scope": scope,
        "value_state": observation["value_state"],
        "point_eligible": observation["point_eligible"],
        "point": observation["point"],
        "low": observation["low"],
        "high": observation["high"],
        "std": observation["std"],
    }


def _write_projection_files(
    public: Path,
    sealed: Path,
    folds_data: bytes,
    outer: Mapping[Any, Sequence[Mapping[str, str]]],
    inner: Mapping[Any, Sequence[Mapping[str, str]]],
    outer_truth: Sequence[Mapping[str, str]],
    inner_truth: Sequence[Mapping[str, str]],
) -> None:
    _new_file(public / "model_rows.csv", folds_data)
    for key, rows in outer.items():
        endpoint, repeat, context, _ = key
        _new_file(
            public / _target_path("outer", endpoint, repeat, context, None),
            _csv_bytes(TARGET_COLUMNS, rows),
        )
    for key, rows in inner.items():
        endpoint, repeat, context, inner_fold = key
        _new_file(
            public / _target_path("inner", endpoint, repeat, context, inner_fold),
            _csv_bytes(TARGET_COLUMNS, rows),
        )
    _new_file(sealed / "sealed_outer_truth.csv", _csv_bytes(TRUTH_COLUMNS, outer_truth))
    _new_file(sealed / "sealed_inner_truth.csv", _csv_bytes(TRUTH_COLUMNS, inner_truth))


def _receipts_for_targets(
    stage: str, cells: Mapping[Any, Sequence[Mapping[str, str]]], contract_sha: str
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for key, rows in sorted(cells.items(), key=lambda item: item[0]):
        endpoint, repeat, outer, inner = key
        path = _target_path(stage, endpoint, repeat, outer, inner)
        data = _csv_bytes(TARGET_COLUMNS, rows)
        receipts.append(
            _target_receipt(
                stage, endpoint, repeat, outer, inner, path, data, rows, contract_sha
            )
        )
    return receipts


def _model_manifest(
    contract_sha: str,
    authority: Mapping[str, bool],
    source_sha: str,
    folds_data: bytes,
    folds: Sequence[Mapping[str, str]],
    outer: Sequence[Mapping[str, Any]],
    inner: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": MODEL_SCHEMA,
        "contract_sha256": contract_sha,
        "parent_contract_sha256": V4_CONTRACT_SHA256,
        "projector_source_sha256": source_sha,
        "model_rows": _file_receipt("model_rows.csv", folds_data, folds, MODEL_COLUMNS),
        "outer_target_receipts": list(outer),
        "inner_target_receipts": list(inner),
        "accounting": {"truth_paths": 0, "truth_hashes": 0, "scores": 0, "metrics": 0},
        "authority": dict(authority),
    }


def _sealed_manifest(
    contract_sha: str,
    authority: Mapping[str, bool],
    source_sha: str,
    outer: Sequence[Mapping[str, str]],
    inner: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": SEALED_SCHEMA,
        "contract_sha256": contract_sha,
        "parent_contract_sha256": V4_CONTRACT_SHA256,
        "projector_source_sha256": source_sha,
        "outer_truth": _file_receipt(
            "sealed_outer_truth.csv",
            _csv_bytes(TRUTH_COLUMNS, outer),
            outer,
            TRUTH_COLUMNS,
            sum(_truth_eligible(row) for row in outer),
        ),
        "inner_truth": _file_receipt(
            "sealed_inner_truth.csv",
            _csv_bytes(TRUTH_COLUMNS, inner),
            inner,
            TRUTH_COLUMNS,
            sum(_truth_eligible(row) for row in inner),
        ),
        "accounting": {
            "sealed_truth_files_written": 2,
            "outer_truth_rows": len(outer),
            "inner_truth_rows": len(inner),
            "truth_metadata_public": 0,
            "tdi_files_opened": 0,
            "blinded_test_rows_opened": 0,
            "episode_or_anchor_files_opened": 0,
            "transductive_operations": 0,
        },
        "authority": dict(authority),
    }


def _audit_receipt(
    contract_sha: str,
    authority: Mapping[str, bool],
    inputs: Mapping[str, str],
    model_sha: str,
    sealed_sha: str,
    counts: Mapping[str, int],
    source_sha: str,
) -> dict[str, Any]:
    receipts = {
        "parent_contract_sha256": V4_CONTRACT_SHA256,
        **inputs,
        "direct_rows": counts["direct_rows"],
        "fold_rows": counts["fold_rows"],
    }
    accounting = {
        "outer_target_files_written": counts["outer_target_files"],
        "inner_target_files_written": counts["inner_target_files"],
        "sealed_truth_files_written": 2,
        "direct_observation_rows_parsed": counts["direct_rows"],
        "target_rows_written": counts["outer_target_rows"]
        + counts["inner_target_rows"],
        "truth_rows_written": counts["outer_truth_rows"] + counts["inner_truth_rows"],
        "tdi_files_opened": 0,
        "blinded_test_rows_opened": 0,
        "episode_or_anchor_files_opened": 0,
        "transductive_operations": 0,
    }
    eligibility = {key: value for key, value in counts.items() if key != "fold_rows"}
    return {
        "schema_version": AUDIT_SCHEMA,
        "contract_sha256": contract_sha,
        "parent_contract_sha256": V4_CONTRACT_SHA256,
        "input_receipts": receipts,
        "model_public_manifest_sha256": model_sha,
        "sealed_truth_manifest_sha256": sealed_sha,
        "eligibility_counts": eligibility,
        "projector_source_sha256": source_sha,
        "accounting": accounting,
        "authority": dict(authority),
    }


project_global_targets = project_openadmet_global_targets
preflight_global_targets = preflight_openadmet_global_targets

__all__ = [
    "GlobalProjectionResult",
    "OpenADMETGlobalPreflightError",
    "OpenADMETGlobalProjectionError",
    "PREFLIGHT_SCHEMA",
    "V5_CONTRACT_SHA256",
    "V5_SCHEMA",
    "preflight_global_targets",
    "preflight_openadmet_global_targets",
    "project_global_targets",
    "project_openadmet_global_targets",
]
