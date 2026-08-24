#!/usr/bin/env python3
"""Run and score sparse G2-2C MapLight development capabilities."""

from __future__ import annotations

import argparse
import math
import os
import shutil
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_execution_compiler as compiler
import global_v2_maplight_runner as runner
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
PREDICTION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_predictions.v1"
)
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_terminal.v1"
)
TRACKED_ACCEPTANCE: Final = compiler.EXECUTION_CONTRACT.with_name(
    "global_v2_maplight_execution_synthetic_acceptance.json"
)
ACCEPTANCE_SOURCE: Final = SCRIPT.with_name(
    "run_global_v2_maplight_execution_synthetic.py"
)
ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_synthetic_acceptance.v1"
)
OFFICIAL_ATTEMPT_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-attempt-1"
)
THREAD_COUNT: Final = 16
MAXIMUM_WALL_SECONDS: Final = 12 * 60 * 60
MAXIMUM_CPU_CORE_HOURS: Final = 200.0
MAXIMUM_RESTRICTED_STORAGE_BYTES: Final = 80_000_000_000
FORBIDDEN_COUNTERS: Final = (
    "confirmatory_truth_values_opened",
    "historical_r3c_row_level_artifacts_opened",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "tutorial_ma_st_rae_calls",
    "official_metric_evaluations",
    "external_records_acquired",
    "submissions_created",
    "leaderboard_observations",
    "live_uploads",
)

Predictor = Callable[
    [np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]],
    tuple[np.ndarray[Any, Any], str],
]


class MapLightExecutionWrapperError(RuntimeError):
    """A capability, model, sparse-score, or publication invariant failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MapLightExecutionWrapperError(message)


def _require_zero_accounting(value: object, label: str) -> None:
    _require(
        isinstance(value, Mapping)
        and all(value.get(name) == 0 for name in FORBIDDEN_COUNTERS),
        f"{label} forbidden accounting differs",
    )


def _authority(synthetic: bool, stage: str) -> dict[str, bool]:
    _require(
        stage in {"capability", "prediction", "terminal"},
        "authority stage differs",
    )
    authority = dict(runner.DENIED_AUTHORITY)
    if not synthetic:
        authority.update(
            {
                "official_target_access": True,
                "official_feature_access": True,
            }
        )
        if stage in {"prediction", "terminal"}:
            authority.update(
                {
                    "official_model_fitting": True,
                    "official_prediction_generation": True,
                }
            )
        if stage == "terminal":
            authority["official_residual_or_diagnostic_computation"] = True
    return authority


def derive_consumed_claim(
    *, tracked_claim_path: Path, acceptance_path: Path
) -> dict[str, Any]:
    """Resolve the immutable template only after exact implementation acceptance."""

    _require(
        runner.sha256_path(tracked_claim_path) == compiler.TRACKED_CLAIM_SHA256,
        "tracked claim receipt differs",
    )
    claim, _raw = runner._load_json(tracked_claim_path)
    _require(
        claim.get("status") == "G2_2C_CLAIM_UNCONSUMED"
        and claim.get("contract_sha256") == compiler.EXECUTION_CONTRACT_SHA256
        and claim.get("future_official_compiler_source_sha256") is None
        and claim.get("future_attempt_wrapper_source_sha256") is None
        and claim.get("future_official_shaped_synthetic_acceptance_sha256") is None
        and claim.get("maximum_consumptions") == 1,
        "tracked claim state differs",
    )
    acceptance, _acceptance_raw = runner._load_json(acceptance_path)
    acceptance_sha = runner.sha256_path(acceptance_path)
    compiler_sha = runner.sha256_path(compiler.SCRIPT)
    wrapper_sha = runner.sha256_path(SCRIPT)
    acceptance_authority = acceptance.get("authority")
    acceptance_accounting = acceptance.get("accounting_per_replay")
    _require(
        acceptance.get("schema_version") == ACCEPTANCE_SCHEMA
        and acceptance.get("status") == "G2_2C_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED"
        and acceptance.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and acceptance.get("compiler_source_sha256") == compiler_sha
        and acceptance.get("execution_wrapper_source_sha256") == wrapper_sha
        and acceptance.get("accepted_runner_source_sha256")
        == runner.sha256_path(runner.SCRIPT)
        and acceptance.get("acceptance_source_sha256")
        == runner.sha256_path(ACCEPTANCE_SOURCE)
        and acceptance.get("roots") == 2
        and acceptance.get("second_source_physical_order_reversed") is True
        and acceptance.get("relative_byte_maps_identical") is True
        and acceptance.get("files_compared") == 6
        and compiler._is_sha(acceptance.get("combined_terminal_tree_sha256"))
        and acceptance.get("counts_per_replay")
        == {
            "component_metric_rows": 60,
            "finite_truth_rows": 1043,
            "inner_maplight_fits": 240,
            "inner_prediction_rows": 15648,
            "molecules": 326,
            "outer_maplight_fits": 60,
            "outer_prediction_rows": 3912,
            "q90_contexts": 60,
            "residual_rows": 3129,
            "uncertainty_rows": 3129,
        }
        and acceptance.get("maplight_fits_total") == 600
        and isinstance(acceptance_accounting, Mapping)
        and acceptance_accounting.get("maplight_model_fits") == 300
        and acceptance.get("sparse_truth") is True
        and acceptance.get("private_roots_retained") == 0
        and all(acceptance_accounting.get(name) == 0 for name in FORBIDDEN_COUNTERS)
        and acceptance_authority == runner.DENIED_AUTHORITY,
        "synthetic acceptance differs",
    )
    consumed = dict(claim)
    consumed.update(
        {
            "status": "G2_2C_CLAIM_CONSUMED",
            "future_official_compiler_source_sha256": compiler_sha,
            "future_attempt_wrapper_source_sha256": wrapper_sha,
            "future_official_shaped_synthetic_acceptance_sha256": acceptance_sha,
        }
    )
    return consumed


def _publish_claim(attempt_root: Path, claim: Mapping[str, Any]) -> Path:
    data = runner.json_bytes(dict(claim))
    path = attempt_root / "attempt_claim.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    directory = os.open(attempt_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return path


def _load_model_capability(
    root: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, np.ndarray[Any, Any]],
]:
    runner._readonly_root(root, "execution model capability")
    manifest, _raw = runner._load_json(root / "manifest.json")
    synthetic = manifest.get("synthetic")
    _require(
        manifest.get("schema_version") == compiler.MODEL_SCHEMA
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("g2a_contract_sha256") == runner.CONTRACT_SHA256
        and manifest.get("compiler_source_sha256")
        == runner.sha256_path(compiler.SCRIPT)
        and isinstance(synthetic, bool),
        "model capability identity differs",
    )
    _require(
        manifest.get("authority") == _authority(bool(synthetic), "capability"),
        "model capability authority differs",
    )
    _require_zero_accounting(manifest.get("accounting"), "model capability")
    official_source_receipts = manifest.get("official_source_receipts")
    _require(
        isinstance(official_source_receipts, Mapping)
        and (not synthetic or not official_source_receipts),
        "model capability source receipts differ",
    )
    preflight = manifest.get("preflight")
    _require(
        isinstance(preflight, Mapping)
        and preflight.get("status") == "G2_2C_PREFLIGHT_PASS"
        and preflight.get("maplight_model_fits") == 0,
        "model capability preflight differs",
    )
    features = runner._read_csv(root / "feature_rows.csv", runner.FEATURE_COLUMNS)
    folds = runner._read_csv(root / "folds.csv", runner.FOLD_COLUMNS)
    _require(
        runner.sha256_path(root / "feature_rows.csv")
        == manifest.get("feature_rows_sha256")
        and runner.sha256_path(root / "folds.csv") == manifest.get("folds_sha256"),
        "feature or fold receipt differs",
    )
    feature_ids = [row["molecule_id"] for row in features]
    _require(
        bool(feature_ids) and feature_ids == sorted(set(feature_ids)),
        "feature identities differ",
    )
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in features
    }
    _require(
        all(compiler._is_sha(component) for component in components.values()),
        "feature component differs",
    )
    _require(
        manifest.get("molecules") == len(features)
        and manifest.get("components") == len(set(components.values())),
        "model capability population differs",
    )
    _require(
        len(folds) == len(features) * 3 * 5,
        "fold row count differs",
    )
    seen: set[tuple[str, int, int]] = set()
    for row in folds:
        molecule = row["molecule_id"]
        repeat = int(row["repeat"])
        outer = int(row["outer_fold"])
        scope = int(row["outer_validation_fold"])
        _require(
            components.get(molecule) == row["similarity_component_hash"]
            and repeat in runner.REPEATS
            and outer in runner.OUTER_FOLDS
            and scope in runner.OUTER_FOLDS,
            "fold identity differs",
        )
        key = molecule, repeat, scope
        _require(key not in seen, "duplicate fold scope")
        seen.add(key)
        if outer == scope:
            _require(row["inner_fold"] == "", "outer validation inner differs")
        else:
            _require(int(row["inner_fold"]) in runner.INNER_FOLDS, "inner differs")
    for repeat in runner.REPEATS:
        outer_components: dict[str, set[int]] = defaultdict(set)
        for row in folds:
            if int(row["repeat"]) == repeat:
                outer_components[row["similarity_component_hash"]].add(
                    int(row["outer_fold"])
                )
        _require(
            all(len(values) == 1 for values in outer_components.values()),
            "component crosses outer fold",
        )
        for outer in runner.OUTER_FOLDS:
            inner_components: dict[str, set[int]] = defaultdict(set)
            for row in folds:
                if (
                    int(row["repeat"]) == repeat
                    and int(row["outer_validation_fold"]) == outer
                    and int(row["outer_fold"]) != outer
                ):
                    inner_components[row["similarity_component_hash"]].add(
                        int(row["inner_fold"])
                    )
            _require(
                bool(inner_components)
                and all(len(values) == 1 for values in inner_components.values()),
                "component crosses inner fold",
            )
    target_paths = sorted((root / "targets").rglob("*.csv"))
    _require(len(target_paths) == 300, "target file count differs")
    target_capabilities = manifest.get("target_capabilities")
    _require(
        isinstance(target_capabilities, Mapping)
        and target_capabilities.get("files") == 300
        and target_capabilities.get("outer_validation_truth_rows") == 0
        and target_capabilities.get("inner_validation_truth_rows") == 0,
        "target capability boundary differs",
    )
    target_material = "".join(
        f"{path.relative_to(root).as_posix()}|{runner.sha256_path(path)}\n"
        for path in target_paths
    ).encode("utf-8")
    _require(
        runner.sha256_bytes(target_material) == manifest.get("target_tree_sha256"),
        "target tree receipt differs",
    )
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    receipts = manifest.get("arrays")
    _require(isinstance(receipts, Mapping), "array receipts differ")
    assert isinstance(receipts, Mapping)
    for name, width, dtype in runner.MAP_ARRAYS:
        path = runner._regular(root / name, f"model array {name}")
        receipt = receipts.get(name)
        _require(
            isinstance(receipt, Mapping)
            and runner.sha256_path(path) == receipt.get("sha256"),
            f"array receipt differs: {name}",
        )
        array = np.load(path, mmap_mode="r", allow_pickle=False)
        _require(
            array.shape == (len(features), width)
            and array.dtype == dtype
            and array.flags.c_contiguous,
            f"array payload differs: {name}",
        )
        arrays[name] = array
    return manifest, features, folds, arrays


def _run_predictions(
    *,
    model_capability_root: Path,
    output_root: Path,
    predictor: Predictor,
    runtime: Mapping[str, str],
) -> Path:
    manifest, features, folds, arrays = _load_model_capability(model_capability_root)
    synthetic = bool(manifest["synthetic"])
    index = {row["molecule_id"]: position for position, row in enumerate(features)}
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in features
    }
    outer_rows: list[dict[str, object]] = []
    inner_rows: list[dict[str, object]] = []
    parameter_hashes: set[str] = set()
    target_values = 0
    for stage in ("outer", "inner"):
        for endpoint in runner.ENDPOINTS:
            for repeat in runner.REPEATS:
                for outer in runner.OUTER_FOLDS:
                    scope = runner._scope_rows(folds, repeat, outer)
                    inners: Iterable[int | None] = (
                        (None,) if stage == "outer" else runner.INNER_FOLDS
                    )
                    for inner in inners:
                        training_ids, prediction_ids = runner._cell_ids(
                            scope, stage, outer, inner
                        )
                        targets = runner._read_csv(
                            runner._cell_target_path(
                                model_capability_root,
                                stage,
                                endpoint,
                                repeat,
                                outer,
                                inner,
                            ),
                            runner.TARGET_COLUMNS,
                        )
                        target_ids = [row["molecule_id"] for row in targets]
                        _require(
                            target_ids == sorted(set(target_ids))
                            and set(target_ids).issubset(training_ids),
                            "sparse training target identity differs",
                        )
                        y = np.asarray(
                            [
                                runner._canonical_float(row["point"], "training point")
                                for row in targets
                            ],
                            dtype=np.float64,
                        )
                        _require(bool(len(y)), "training support is empty")
                        target_values += len(y)
                        predicted, parameter_sha = predictor(
                            runner._matrix(
                                arrays, [index[value] for value in target_ids]
                            ),
                            y,
                            runner._matrix(
                                arrays, [index[value] for value in prediction_ids]
                            ),
                        )
                        parameter_hashes.add(parameter_sha)
                        model_id = runner._identifier(
                            compiler.EXECUTION_CONTRACT_SHA256,
                            runner.SYSTEM_ID,
                            endpoint,
                            repeat,
                            outer,
                            "none" if inner is None else inner,
                        )
                        split_id = runner._identifier(
                            manifest["folds_sha256"],
                            repeat,
                            outer,
                            "none" if inner is None else inner,
                        )
                        for molecule, prediction in zip(
                            prediction_ids, predicted, strict=True
                        ):
                            row: dict[str, object] = {
                                "molecule_id": molecule,
                                "endpoint": endpoint,
                                "similarity_component_hash": components[molecule],
                                "repeat": repeat,
                                "outer_fold": outer,
                                "system_id": runner.SYSTEM_ID,
                                "prediction": format(float(prediction), ".17g"),
                                "model_id": model_id,
                                "split_id": split_id,
                            }
                            if inner is None:
                                outer_rows.append(row)
                            else:
                                row["inner_fold"] = inner
                                inner_rows.append(row)
    _require(parameter_hashes == {runner.PARAMETER_SHA256}, "parameter receipt differs")
    _require(
        isinstance(manifest.get("target_capabilities"), Mapping)
        and manifest["target_capabilities"].get("training_rows") == target_values,
        "training target accounting differs",
    )
    outer_rows.sort(
        key=lambda row: tuple(row[name] for name in runner.OUTER_COLUMNS[:5])
    )
    inner_rows.sort(
        key=lambda row: tuple(row[name] for name in runner.INNER_COLUMNS[:6])
    )
    _require(
        len(outer_rows) == len(features) * 4 * 3
        and len(inner_rows) == len(features) * 4 * 3 * 4,
        "prediction row count differs",
    )
    outer_bytes = runner.csv_bytes(runner.OUTER_COLUMNS, outer_rows)
    inner_bytes = runner.csv_bytes(runner.INNER_COLUMNS, inner_rows)
    accounting = {
        "model_training_target_values_opened": target_values,
        "outer_truth_values_opened_by_model": 0,
        "inner_truth_values_opened_by_model": 0,
        "maplight_model_fits": 300,
        "prediction_rows": len(outer_rows) + len(inner_rows),
        "official_target_values_opened": 0 if synthetic else target_values,
        "official_features_opened": 0 if synthetic else len(features) * 2563,
        "official_model_fits": 0 if synthetic else 300,
        "official_predictions_generated": (
            0 if synthetic else len(outer_rows) + len(inner_rows)
        ),
        "official_metric_evaluations": 0,
        "official_residual_values_computed": 0,
        "official_diagnostics_computed": 0,
        "confirmatory_truth_values_opened": 0,
        "historical_r3c_row_level_artifacts_opened": 0,
        "blinded_test_files_opened": 0,
        "tdi_files_opened": 0,
        "submissions_created": 0,
        "leaderboard_observations": 0,
        "external_records_acquired": 0,
        "live_uploads": 0,
        "tutorial_ma_st_rae_calls": 0,
    }
    result = {
        "schema_version": PREDICTION_SCHEMA,
        "status": (
            "G2_2C_SYNTHETIC_PREDICTIONS_FROZEN"
            if synthetic
            else "G2_2C_DEVELOPMENT_PREDICTIONS_FROZEN"
        ),
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "g2a_contract_sha256": runner.CONTRACT_SHA256,
        "accepted_runner_source_sha256": runner.sha256_path(runner.SCRIPT),
        "execution_wrapper_source_sha256": runner.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": runner.sha256_path(
            model_capability_root / "manifest.json"
        ),
        "synthetic": synthetic,
        "official_source_receipts": dict(manifest["official_source_receipts"]),
        "folds_sha256": manifest["folds_sha256"],
        "runtime": dict(runtime),
        "resolved_parameter_sha256": runner.PARAMETER_SHA256,
        "counts": {
            "molecules": len(features),
            "outer_maplight_fits": 60,
            "inner_maplight_fits": 240,
            "outer_prediction_rows": len(outer_rows),
            "inner_prediction_rows": len(inner_rows),
        },
        "output_receipts": {
            "development_outer_oof.csv": runner.sha256_bytes(outer_bytes),
            "development_inner_oof.csv": runner.sha256_bytes(inner_bytes),
        },
        "accounting": accounting,
        "authority": _authority(synthetic, "prediction"),
    }
    return cast(
        Path,
        runner.publish_files(
            output_root,
            {
                "development_outer_oof.csv": outer_bytes,
                "development_inner_oof.csv": inner_bytes,
                "manifest.json": runner.json_bytes(result),
            },
        ),
    )


def run_predictions(*, model_capability_root: Path, output_root: Path) -> Path:
    """Run all 300 fixed-MapLight cells in the locked runtime."""

    return _run_predictions(
        model_capability_root=model_capability_root,
        output_root=output_root,
        predictor=runner._catboost_predict,
        runtime=runner._verify_runtime(),
    )


def _load_predictions(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    runner._readonly_root(root, "execution predictions")
    manifest, _raw = runner._load_json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == PREDICTION_SCHEMA
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("accepted_runner_source_sha256")
        == runner.sha256_path(runner.SCRIPT)
        and manifest.get("execution_wrapper_source_sha256")
        == runner.sha256_path(SCRIPT)
        and compiler._is_sha(manifest.get("model_capability_manifest_sha256"))
        and isinstance(manifest.get("synthetic"), bool),
        "prediction identity differs",
    )
    _require(
        isinstance(manifest.get("official_source_receipts"), Mapping),
        "prediction source receipts differ",
    )
    _require(
        compiler._is_sha(manifest.get("folds_sha256")),
        "prediction fold receipt differs",
    )
    _require(
        manifest.get("authority")
        == _authority(bool(manifest["synthetic"]), "prediction"),
        "prediction authority differs",
    )
    _require_zero_accounting(manifest.get("accounting"), "prediction")
    outer = runner._read_csv(root / "development_outer_oof.csv", runner.OUTER_COLUMNS)
    inner = runner._read_csv(root / "development_inner_oof.csv", runner.INNER_COLUMNS)
    receipts = manifest.get("output_receipts")
    _require(
        isinstance(receipts, Mapping)
        and runner.sha256_path(root / "development_outer_oof.csv")
        == receipts.get("development_outer_oof.csv")
        and runner.sha256_path(root / "development_inner_oof.csv")
        == receipts.get("development_inner_oof.csv"),
        "prediction receipt differs",
    )
    counts = manifest.get("counts")
    _require(isinstance(counts, Mapping), "prediction counts differ")
    assert isinstance(counts, Mapping)
    molecules = counts.get("molecules")
    _require(
        isinstance(molecules, int)
        and molecules > 0
        and counts.get("outer_maplight_fits") == 60
        and counts.get("inner_maplight_fits") == 240
        and counts.get("outer_prediction_rows") == len(outer) == molecules * 4 * 3
        and counts.get("inner_prediction_rows") == len(inner) == molecules * 4 * 3 * 4,
        "prediction row counts differ",
    )
    folds_sha = str(manifest["folds_sha256"])
    components: dict[str, str] = {}
    outer_seen: set[tuple[str, str, int, int]] = set()
    for row in outer:
        molecule = row["molecule_id"]
        endpoint = row["endpoint"]
        repeat = int(row["repeat"])
        outer_fold = int(row["outer_fold"])
        component = row["similarity_component_hash"]
        outer_key = molecule, endpoint, repeat, outer_fold
        _require(
            outer_key not in outer_seen
            and endpoint in runner.ENDPOINTS
            and repeat in runner.REPEATS
            and outer_fold in runner.OUTER_FOLDS
            and compiler._is_sha(component)
            and row["system_id"] == runner.SYSTEM_ID
            and row["model_id"]
            == runner._identifier(
                compiler.EXECUTION_CONTRACT_SHA256,
                runner.SYSTEM_ID,
                endpoint,
                repeat,
                outer_fold,
                "none",
            )
            and row["split_id"]
            == runner._identifier(folds_sha, repeat, outer_fold, "none"),
            "outer prediction identity differs",
        )
        runner._canonical_float(row["prediction"], "outer prediction")
        outer_seen.add(outer_key)
        _require(
            components.setdefault(molecule, component) == component,
            "outer prediction component differs",
        )
    inner_seen: set[tuple[str, str, int, int, int]] = set()
    for row in inner:
        molecule = row["molecule_id"]
        endpoint = row["endpoint"]
        repeat = int(row["repeat"])
        outer_fold = int(row["outer_fold"])
        inner_fold = int(row["inner_fold"])
        component = row["similarity_component_hash"]
        inner_key = molecule, endpoint, repeat, outer_fold, inner_fold
        _require(
            inner_key not in inner_seen
            and endpoint in runner.ENDPOINTS
            and repeat in runner.REPEATS
            and outer_fold in runner.OUTER_FOLDS
            and inner_fold in runner.INNER_FOLDS
            and component == components.get(molecule)
            and row["system_id"] == runner.SYSTEM_ID
            and row["model_id"]
            == runner._identifier(
                compiler.EXECUTION_CONTRACT_SHA256,
                runner.SYSTEM_ID,
                endpoint,
                repeat,
                outer_fold,
                inner_fold,
            )
            and row["split_id"]
            == runner._identifier(folds_sha, repeat, outer_fold, inner_fold),
            "inner prediction identity differs",
        )
        runner._canonical_float(row["prediction"], "inner prediction")
        inner_seen.add(inner_key)
    return manifest, outer, inner


def _load_truth(
    root: Path,
) -> tuple[dict[str, Any], dict[tuple[str, str], tuple[str, float]]]:
    runner._readonly_root(root, "execution scorer capability")
    manifest, _raw = runner._load_json(root / "manifest.json")
    _require(
        manifest.get("schema_version") == compiler.SCORER_SCHEMA
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("compiler_source_sha256")
        == runner.sha256_path(compiler.SCRIPT)
        and compiler._is_sha(manifest.get("model_capability_manifest_sha256"))
        and isinstance(manifest.get("synthetic"), bool),
        "scorer capability identity differs",
    )
    _require(
        isinstance(manifest.get("official_source_receipts"), Mapping),
        "scorer source receipts differ",
    )
    _require(
        manifest.get("authority")
        == _authority(bool(manifest["synthetic"]), "capability"),
        "scorer authority differs",
    )
    _require_zero_accounting(manifest.get("accounting"), "scorer")
    _require(
        manifest.get("model_training_files") == 0
        and manifest.get("feature_arrays") == 0
        and manifest.get("confirmatory_truth_values") == 0,
        "scorer capability separation differs",
    )
    rows = runner._read_csv(root / "truth.csv", runner.TRUTH_COLUMNS)
    _require(
        runner.sha256_path(root / "truth.csv") == manifest.get("truth_sha256"),
        "truth receipt differs",
    )
    truth: dict[tuple[str, str], tuple[str, float]] = {}
    for row in rows:
        key = row["molecule_id"], row["endpoint"]
        _require(
            key not in truth
            and row["endpoint"] in runner.ENDPOINTS
            and compiler._is_sha(row["similarity_component_hash"]),
            "truth identity differs",
        )
        truth[key] = (
            row["similarity_component_hash"],
            runner._canonical_float(row["point"], "truth point"),
        )
    _require(len(truth) == manifest.get("truth_rows"), "truth row count differs")
    return manifest, truth


def score_predictions(
    *, prediction_root: Path, scorer_capability_root: Path, output_root: Path
) -> Path:
    """Score finite development truth only after prediction publication."""

    prediction_manifest, outer, inner = _load_predictions(prediction_root)
    scorer_manifest, truth = _load_truth(scorer_capability_root)
    synthetic = bool(prediction_manifest["synthetic"])
    _require(
        scorer_manifest["synthetic"] is synthetic
        and scorer_manifest["model_capability_manifest_sha256"]
        == prediction_manifest["model_capability_manifest_sha256"],
        "prediction/scorer binding differs",
    )
    _require(
        scorer_manifest["official_source_receipts"]
        == prediction_manifest["official_source_receipts"],
        "prediction/scorer source lineage differs",
    )
    outer_receipt = prediction_manifest["output_receipts"]["development_outer_oof.csv"]
    residual_rows: list[dict[str, object]] = []
    by_context: dict[tuple[str, int, int], list[dict[str, object]]] = defaultdict(list)
    outer_occurrences: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in outer:
        key = row["molecule_id"], row["endpoint"]
        if key not in truth:
            continue
        component, point = truth[key]
        _require(
            component == row["similarity_component_hash"], "truth component differs"
        )
        prediction = runner._canonical_float(row["prediction"], "outer prediction")
        record: dict[str, object] = {
            "molecule_id": row["molecule_id"],
            "endpoint": row["endpoint"],
            "similarity_component_hash": component,
            "repeat": int(row["repeat"]),
            "outer_fold": int(row["outer_fold"]),
            "prediction": row["prediction"],
            "point": format(point, ".17g"),
            "residual": format(prediction - point, ".17g"),
            "prediction_receipt": outer_receipt,
        }
        residual_rows.append(record)
        by_context[
            (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
        ].append(record)
        outer_occurrences[key] += 1
    inner_contexts: dict[tuple[str, int, int], list[tuple[float, str, str]]] = (
        defaultdict(list)
    )
    inner_occurrences: defaultdict[tuple[str, str], int] = defaultdict(int)
    for row in inner:
        key = row["molecule_id"], row["endpoint"]
        if key not in truth:
            continue
        component, point = truth[key]
        _require(
            component == row["similarity_component_hash"], "inner component differs"
        )
        prediction = runner._canonical_float(row["prediction"], "inner prediction")
        inner_contexts[
            (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
        ].append((abs(prediction - point), component, row["molecule_id"]))
        inner_occurrences[key] += 1
    _require(
        set(outer_occurrences) == set(truth)
        and set(inner_occurrences) == set(truth)
        and all(value == 3 for value in outer_occurrences.values())
        and all(value == 12 for value in inner_occurrences.values()),
        "sparse cross-fit truth coverage differs",
    )
    _require(
        len(by_context) == len(inner_contexts) == 60,
        "sparse score contexts differ",
    )
    uncertainty_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    for context in sorted(by_context):
        eligible = inner_contexts[context]
        q90 = runner._weighted_q90(eligible)
        inner_receipt = runner.sha256_bytes(
            runner.csv_bytes(
                ("absolute_residual", "similarity_component_hash", "molecule_id"),
                (
                    {
                        "absolute_residual": format(value, ".17g"),
                        "similarity_component_hash": component,
                        "molecule_id": molecule,
                    }
                    for value, component, molecule in sorted(
                        eligible, key=lambda item: (item[0], item[1], item[2])
                    )
                ),
            )
        )
        component_errors: dict[str, list[float]] = defaultdict(list)
        for record in by_context[context]:
            prediction = runner._canonical_float(
                str(record["prediction"]), "prediction"
            )
            point = runner._canonical_float(str(record["point"]), "point")
            component = str(record["similarity_component_hash"])
            component_errors[component].append(abs(prediction - point))
            uncertainty_rows.append(
                {
                    "molecule_id": record["molecule_id"],
                    "endpoint": record["endpoint"],
                    "similarity_component_hash": component,
                    "repeat": record["repeat"],
                    "outer_fold": record["outer_fold"],
                    "prediction": record["prediction"],
                    "q90": format(q90, ".17g"),
                    "lower": format(prediction - q90, ".17g"),
                    "upper": format(prediction + q90, ".17g"),
                    "inner_residual_receipt": inner_receipt,
                }
            )
        component_mae = math.fsum(
            math.fsum(values) / len(values) for values in component_errors.values()
        ) / len(component_errors)
        metric_rows.append(
            {
                "endpoint": context[0],
                "repeat": context[1],
                "outer_fold": context[2],
                "scored_molecules": sum(map(len, component_errors.values())),
                "scored_components": len(component_errors),
                "component_macro_mae": format(component_mae, ".17g"),
            }
        )
    residual_rows.sort(
        key=lambda row: tuple(row[name] for name in runner.RESIDUAL_COLUMNS[:5])
    )
    uncertainty_rows.sort(
        key=lambda row: tuple(row[name] for name in runner.UNCERTAINTY_COLUMNS[:5])
    )
    residual_bytes = runner.csv_bytes(runner.RESIDUAL_COLUMNS, residual_rows)
    uncertainty_bytes = runner.csv_bytes(runner.UNCERTAINTY_COLUMNS, uncertainty_rows)
    metric_bytes = runner.csv_bytes(runner.METRIC_COLUMNS, metric_rows)
    outer_bytes = (prediction_root / "development_outer_oof.csv").read_bytes()
    inner_bytes = (prediction_root / "development_inner_oof.csv").read_bytes()
    outputs = {
        "development_outer_oof.csv": outer_bytes,
        "development_inner_oof.csv": inner_bytes,
        "development_residuals.csv": residual_bytes,
        "development_uncertainty.csv": uncertainty_bytes,
        "development_component_metrics.csv": metric_bytes,
    }
    accounting = {
        **prediction_manifest["accounting"],
        "scorer_truth_values_opened_after_prediction_freeze": len(truth),
        "residual_values_computed": len(residual_rows)
        + sum(inner_occurrences.values()),
        "q90_contexts_computed": len(inner_contexts),
        "component_metric_rows_computed": len(metric_rows),
        "official_residual_values_computed": (
            0 if synthetic else len(residual_rows) + sum(inner_occurrences.values())
        ),
        "official_diagnostics_computed": 0 if synthetic else len(metric_rows),
        "tutorial_ma_st_rae_calls": 0,
    }
    terminal = {
        "schema_version": TERMINAL_SCHEMA,
        "status": (
            "G2_2C_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
            if synthetic
            else "G2_2C_DEVELOPMENT_REPLAY_COMPLETE"
        ),
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "synthetic": synthetic,
        "source_receipts": {
            **prediction_manifest["official_source_receipts"],
            "model_capability_manifest_sha256": prediction_manifest[
                "model_capability_manifest_sha256"
            ],
            "scorer_capability_manifest_sha256": runner.sha256_path(
                scorer_capability_root / "manifest.json"
            ),
        },
        "implementation_receipts": {
            "accepted_runner_source_sha256": runner.sha256_path(runner.SCRIPT),
            "compiler_source_sha256": scorer_manifest["compiler_source_sha256"],
            "execution_wrapper_source_sha256": runner.sha256_path(SCRIPT),
            "resolved_parameter_sha256": runner.PARAMETER_SHA256,
            "research_uv_lock_sha256": runner.LOCK_SHA256,
        },
        "runtime": prediction_manifest["runtime"],
        "counts": {
            **prediction_manifest["counts"],
            "finite_truth_rows": len(truth),
            "residual_rows": len(residual_rows),
            "uncertainty_rows": len(uncertainty_rows),
            "component_metric_rows": len(metric_rows),
            "q90_contexts": len(inner_contexts),
        },
        "output_receipts": {
            name: runner.sha256_bytes(value) for name, value in outputs.items()
        },
        "determinism": {
            "canonical_input_order": True,
            "duration_excluded": True,
            "retry": False,
            "resume": False,
            "overwrite": False,
        },
        "accounting": accounting,
        "authority": _authority(synthetic, "terminal"),
    }
    return cast(
        Path,
        runner.publish_files(
            output_root, {**outputs, "manifest.json": runner.json_bytes(terminal)}
        ),
    )


def _attempt_manifest(
    *,
    status: str,
    claim_sha256: str,
    source_receipts: Mapping[str, str],
    runtime: Mapping[str, str],
    accounting: Mapping[str, int],
) -> dict[str, object]:
    return {
        "schema_version": TERMINAL_SCHEMA,
        "status": status,
        "contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "source_receipts": dict(source_receipts),
        "implementation_receipts": {
            "accepted_runner_source_sha256": runner.sha256_path(runner.SCRIPT),
            "compiler_source_sha256": runner.sha256_path(compiler.SCRIPT),
            "execution_wrapper_source_sha256": runner.sha256_path(SCRIPT),
            "resolved_parameter_sha256": runner.PARAMETER_SHA256,
            "research_uv_lock_sha256": runner.LOCK_SHA256,
        },
        "runtime": dict(runtime),
        "counts": {},
        "output_receipts": {},
        "determinism": {
            "replays_completed": 0,
            "relative_byte_maps_identical": False,
            "retry": False,
            "resume": False,
            "overwrite": False,
        },
        "accounting": dict(accounting),
        "authority": _authority(False, "capability"),
    }


def _publish_attempt_receipt(
    *,
    attempt_root: Path,
    terminal: Path,
    claim_sha256: str,
    resource: Mapping[str, float | int],
) -> Path:
    manifest, _raw = runner._load_json(terminal / "manifest.json")
    receipt = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_maplight_execution_attempt_receipt.v1"
        ),
        "status": manifest["status"],
        "contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "terminal_manifest_sha256": runner.sha256_path(terminal / "manifest.json"),
        "terminal_tree": runner.relative_byte_map(terminal),
        "source_receipts": manifest["source_receipts"],
        "implementation_receipts": manifest["implementation_receipts"],
        "accounting": manifest["accounting"],
        "resource": dict(resource),
    }
    return cast(
        Path,
        runner.publish_files(
            attempt_root / "receipt",
            {"official_attempt_receipt.json": runner.json_bytes(receipt)},
        ),
    )


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _resource_snapshot(
    *, started: float, attempt_root: Path, peak_bytes: int
) -> tuple[dict[str, float | int], int]:
    peak = max(peak_bytes, _tree_bytes(attempt_root))
    wall = time.monotonic() - started
    cpu_core_hours = wall * THREAD_COUNT / 3600
    _require(wall <= MAXIMUM_WALL_SECONDS, "official wall ceiling exceeded")
    _require(
        cpu_core_hours <= MAXIMUM_CPU_CORE_HOURS,
        "official CPU-core-hour ceiling exceeded",
    )
    _require(
        peak <= MAXIMUM_RESTRICTED_STORAGE_BYTES,
        "official restricted-storage ceiling exceeded",
    )
    return (
        {
            "wall_seconds": wall,
            "cpu_core_hours_upper_bound": cpu_core_hours,
            "peak_restricted_storage_bytes": peak,
            "gpu_hours": 0,
        },
        peak,
    )


def _finalize_attempt(attempt_root: Path) -> None:
    _require(
        {path.name for path in attempt_root.iterdir()}
        == {"attempt_claim.json", "receipt", "terminal"},
        "final attempt file set differs",
    )
    runner._readonly(attempt_root)


def run_official_attempt(
    *,
    source_root: Path,
    attempt_root: Path,
    tracked_claim_path: Path = compiler.TRACKED_CLAIM,
    acceptance_path: Path = TRACKED_ACCEPTANCE,
) -> Path:
    """Consume the sole claim and execute two sequential official replays."""

    consumed = derive_consumed_claim(
        tracked_claim_path=tracked_claim_path, acceptance_path=acceptance_path
    )
    resolved_parent = attempt_root.parent.resolve(strict=True)
    resolved_attempt = resolved_parent / attempt_root.name
    repository = compiler.ROOT.resolve(strict=True)
    _require(
        resolved_parent.is_dir()
        and not attempt_root.exists()
        and not attempt_root.is_symlink()
        and not any(parent.is_symlink() for parent in attempt_root.parents),
        "fixed attempt root is unavailable",
    )
    _require(
        resolved_attempt != repository and repository not in resolved_attempt.parents,
        "official attempt root is inside Git",
    )
    _require(
        resolved_attempt == OFFICIAL_ATTEMPT_ROOT,
        "official attempt root is not the frozen private root",
    )
    _require(
        source_root.resolve(strict=True) == compiler.OFFICIAL_SOURCE_ROOT,
        "official source root is not the frozen private source",
    )
    _require(
        shutil.disk_usage(resolved_parent).free >= MAXIMUM_RESTRICTED_STORAGE_BYTES,
        "official restricted-storage reservation is unavailable",
    )
    compiler.authenticate_official_source(
        source_root=source_root,
        consumed_claim=consumed,
        expected_compiler_sha256=runner.sha256_path(compiler.SCRIPT),
    )
    verified_runtime = runner._verify_runtime()
    started = time.monotonic()
    peak_bytes = 0
    attempt_root.mkdir(mode=0o700)
    parent_descriptor = os.open(resolved_parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    claim_path = _publish_claim(attempt_root, consumed)
    claim_sha = runner.sha256_path(claim_path)
    replay_roots: list[Path] = []
    try:
        terminals: list[Path] = []
        for label in ("a", "b"):
            replay = attempt_root / f".private-replay-{label}"
            replay.mkdir(mode=0o700)
            replay_roots.append(replay)
            private = replay / "capabilities"
            predictions = replay / "predictions"
            model, scorer, _preflight = compiler.compile_capabilities(
                source_root=source_root,
                output_root=private,
                expected_compiler_sha256=runner.sha256_path(compiler.SCRIPT),
                mode="official",
                consumed_claim_path=claim_path,
            )
            _resource, peak_bytes = _resource_snapshot(
                started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
            )
            run_predictions(model_capability_root=model, output_root=predictions)
            _resource, peak_bytes = _resource_snapshot(
                started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
            )
            terminals.append(
                score_predictions(
                    prediction_root=predictions,
                    scorer_capability_root=scorer,
                    output_root=replay / "terminal",
                )
            )
            _resource, peak_bytes = _resource_snapshot(
                started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
            )
            runner._cleanup(private)
            runner._cleanup(predictions)
        maps = [runner.relative_byte_map(terminal) for terminal in terminals]
        _require(maps[0] == maps[1], "official replay byte maps differ")
        replay_manifest, _raw = runner._load_json(terminals[0] / "manifest.json")
        output_names = (
            "development_outer_oof.csv",
            "development_inner_oof.csv",
            "development_residuals.csv",
            "development_uncertainty.csv",
            "development_component_metrics.csv",
        )
        outputs = {name: (terminals[0] / name).read_bytes() for name in output_names}
        final_manifest = {
            **replay_manifest,
            "status": "G2_2_MAPLIGHT_REPRODUCED",
            "contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
            "consumed_claim_sha256": claim_sha,
            "determinism": {
                "replays_completed": 2,
                "relative_byte_maps_identical": True,
                "compared_files": len(maps[0]),
                "retry": False,
                "resume": False,
                "overwrite": False,
            },
        }
        terminal = cast(
            Path,
            runner.publish_files(
                attempt_root / "terminal",
                {**outputs, "manifest.json": runner.json_bytes(final_manifest)},
            ),
        )
        for replay in replay_roots:
            runner._cleanup(replay)
        resource, peak_bytes = _resource_snapshot(
            started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
        )
        _publish_attempt_receipt(
            attempt_root=attempt_root,
            terminal=terminal,
            claim_sha256=claim_sha,
            resource=resource,
        )
        _finalize_attempt(attempt_root)
        return terminal
    except compiler.MapLightExecutionUnderpowered as error:
        for replay in replay_roots:
            runner._cleanup(replay)
        preflight_accounting = error.preflight.get("accounting")
        _require(
            isinstance(preflight_accounting, Mapping),
            "underpowered accounting differs",
        )
        assert isinstance(preflight_accounting, Mapping)
        accounting = {
            **{str(name): int(value) for name, value in preflight_accounting.items()},
            "official_model_fits": 0,
            "official_predictions_generated": 0,
            "official_residual_values_computed": 0,
            "official_diagnostics_computed": 0,
            "official_metric_evaluations": 0,
            "confirmatory_truth_values_opened": 0,
            "historical_r3c_row_level_artifacts_opened": 0,
            "blinded_test_files_opened": 0,
            "tdi_files_opened": 0,
            "submissions_created": 0,
            "leaderboard_observations": 0,
            "external_records_acquired": 0,
            "live_uploads": 0,
        }
        manifest = _attempt_manifest(
            status="G2_2_UNDERPOWERED",
            claim_sha256=claim_sha,
            source_receipts=error.source_receipts,
            runtime=verified_runtime,
            accounting=accounting,
        )
        terminal = cast(
            Path,
            runner.publish_files(
                attempt_root / "terminal",
                {
                    "preflight.json": runner.json_bytes(error.preflight),
                    "manifest.json": runner.json_bytes(manifest),
                },
            ),
        )
        resource, peak_bytes = _resource_snapshot(
            started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
        )
        _publish_attempt_receipt(
            attempt_root=attempt_root,
            terminal=terminal,
            claim_sha256=claim_sha,
            resource=resource,
        )
        _finalize_attempt(attempt_root)
        return terminal
    except BaseException:
        for replay in replay_roots:
            runner._cleanup(replay)
        runner._readonly(attempt_root)
        raise


__all__ = [
    "MapLightExecutionWrapperError",
    "PREDICTION_SCHEMA",
    "TERMINAL_SCHEMA",
    "_run_predictions",
    "derive_consumed_claim",
    "run_official_attempt",
    "run_predictions",
    "score_predictions",
]


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r2b-root", type=Path, required=True)
    parser.add_argument("--r3a-root", type=Path, required=True)
    args = parser.parse_args()
    consumed = derive_consumed_claim(
        tracked_claim_path=compiler.TRACKED_CLAIM,
        acceptance_path=TRACKED_ACCEPTANCE,
    )
    compiler_sha = runner.sha256_path(compiler.SCRIPT)
    if compiler.OFFICIAL_SOURCE_ROOT.exists():
        compiler.authenticate_official_source(
            source_root=compiler.OFFICIAL_SOURCE_ROOT,
            consumed_claim=consumed,
            expected_compiler_sha256=compiler_sha,
        )
    else:
        compiler.publish_official_source(
            r2b_root=args.r2b_root,
            r3a_root=args.r3a_root,
            output_root=compiler.OFFICIAL_SOURCE_ROOT,
            consumed_claim=consumed,
            expected_compiler_sha256=compiler_sha,
        )
    terminal = run_official_attempt(
        source_root=compiler.OFFICIAL_SOURCE_ROOT,
        attempt_root=OFFICIAL_ATTEMPT_ROOT,
    )
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
