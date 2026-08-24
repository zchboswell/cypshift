#!/usr/bin/env python3
"""Execute the frozen EXP-G1 screen on sparse, family-safe capabilities.

This additive wrapper keeps the accepted G2-3B scientific identities but makes
cardinality dynamic and keeps point-eligible and tutorial-eligible truth masks
separate.  Model stages never receive selector or scorer truth.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import math
import os
import platform
import random
import resource
import shutil
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import global_v2_g1_execution_compiler as compiler
import global_v2_g1_runner as g1
import global_v2_maplight_runner as base
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
SCREEN_CONTRACT: Final = g1.PARENT
OFFICIAL_ATTEMPT_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-3c-g1-development-attempt-1"
)
TRACKED_ACCEPTANCE: Final = compiler.TRACKED_ACCEPTANCE
ACCEPTANCE_SOURCE: Final = compiler.OFFICIAL_SYNTHETIC_DRIVER
INNER_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat",
    "outer_fold",
    "inner_fold",
    "configuration_id",
    "prediction",
)
OUTER_COLUMNS: Final = tuple(name for name in INNER_COLUMNS if name != "inner_fold")
SELECTION_COLUMNS: Final = g1.SELECTION_COLUMNS
SELECTION_METRIC_COLUMNS: Final = g1.SELECTION_METRIC_COLUMNS
PROJECTION_COLUMNS: Final = g1.PROJECTION_COLUMNS
OUTER_CELL_COLUMNS: Final = g1.OUTER_CELL_METRIC_COLUMNS
ENDPOINT_COLUMNS: Final = g1.ENDPOINT_METRIC_COLUMNS
FUTURE_COLUMNS: Final = g1.FUTURE_TOKEN_COLUMNS
PREDICTOR = Callable[
    [str, int, np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]],
    tuple[np.ndarray[Any, Any], str],
]
FORBIDDEN_COUNTERS: Final = (
    "official_metric_evaluations",
    "confirmatory_truth_values_opened",
    "historical_r3c_row_level_artifacts_opened",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "external_records_acquired",
    "submissions_created",
    "leaderboard_observations",
    "live_uploads",
)
MAXIMUM_WALL_SECONDS: Final = 120 * 60 * 60
MAXIMUM_CPU_CORE_HOURS: Final = 1200.0
MAXIMUM_RESTRICTED_STORAGE_BYTES: Final = 40_000_000_000


class G1ExecutionWrapperError(RuntimeError):
    """A capability, model, metric, topology, or publication invariant failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G1ExecutionWrapperError(message)


def _float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise G1ExecutionWrapperError(f"{label} is not numeric") from error
    _require(
        math.isfinite(result) and value == format(result, ".17g"),
        f"{label} is nonfinite or noncanonical",
    )
    return result


def _sha_text(*values: object) -> str:
    return base.sha256_bytes("|".join(map(str, values)).encode("utf-8"))


def _authority(synthetic: bool, stage: str) -> dict[str, bool]:
    _require(stage in {"model", "selector", "scorer", "terminal"}, "stage differs")
    value = dict(g1.DENIED_AUTHORITY)
    value["official_baseline_prediction_access"] = False
    if not synthetic:
        value["official_target_access"] = True
        if stage in {"model", "terminal"}:
            value["official_feature_access"] = True
            value["official_model_fitting"] = True
            value["official_prediction_generation"] = True
        if stage in {"selector", "scorer", "terminal"}:
            value["development_metric_evaluation"] = True
        if stage in {"scorer", "terminal"}:
            value["official_baseline_prediction_access"] = True
    return value


def _runtime_identity() -> dict[str, str]:
    observed = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "catboost": importlib.metadata.version("catboost"),
    }
    _require(
        observed
        == {
            "platform": "Linux x86_64 CPU",
            "python": "3.10.13",
            "numpy": "1.25.2",
            "catboost": "1.2.1",
        },
        f"locked runtime differs: {observed}",
    )
    return observed


def _screen() -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    contract, _raw = base._load_json(SCREEN_CONTRACT)
    screen = contract["screen"]
    _require(
        tuple(item["configuration_id"] for item in screen["configurations"])
        == g1.CONFIGURATION_IDS
        and tuple(screen["model_seeds"]) == g1.MODEL_SEEDS,
        "screen identity differs",
    )
    configurations = {
        item["configuration_id"]: {
            name: value for name, value in item.items() if name != "configuration_id"
        }
        for item in screen["configurations"]
    }
    return configurations, dict(screen["common_arguments"])


def real_predictor(
    configuration_id: str,
    model_seed: int,
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    """Fit one exact locked CatBoost identity and return finite predictions."""

    try:
        from catboost import (  # type: ignore[import-not-found]  # noqa: PLC0415
            CatBoostRegressor,
        )
    except ImportError as error:
        raise G1ExecutionWrapperError("CatBoost 1.2.1 is unavailable") from error
    configurations, common = _screen()
    constructor = {
        **configurations[configuration_id],
        **common,
        "random_seed": model_seed,
    }
    model = CatBoostRegressor(**constructor)
    _require(model.get_params() == constructor, "CatBoost constructor differs")
    model.fit(training, targets)
    resolved = cast(dict[str, Any], model.get_all_params())
    _require(resolved.get("random_seed") == model_seed, "resolved seed differs")
    values = np.asarray(model.predict(prediction), dtype=np.float64)
    _require(
        values.shape == (len(prediction),) and bool(np.isfinite(values).all()),
        "CatBoost predictions differ",
    )
    return values, base.sha256_bytes(base.json_bytes(resolved))


def deterministic_test_predictor(
    configuration_id: str,
    model_seed: int,
    _training: np.ndarray[Any, Any],
    _targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    """Deterministic full-topology double; synthetic mechanics only."""

    values = prediction[:, 0].astype(np.float64)
    values += g1.CONFIGURATION_IDS.index(configuration_id) * 0.001
    values += (g1.MODEL_SEEDS.index(model_seed) - 1) * 0.0001
    return values, _sha_text("test-double", configuration_id, model_seed)


def run_runtime_probes(*, model_capability_root: Path) -> list[dict[str, object]]:
    """Fit the exact fourteen frozen constructor identities on one model root."""

    _runtime_identity()
    _manifest, molecules, _components, folds, matrix = _load_model(
        model_capability_root
    )
    index = {molecule: position for position, molecule in enumerate(molecules)}
    training_ids, prediction_ids = _cell_ids(
        molecules, folds, repeat=0, outer=0, inner=None
    )
    targets = _targets(
        model_capability_root,
        stage="outer",
        endpoint="CYP1A2",
        repeat=0,
        outer=0,
        inner=None,
    )
    target_map = {
        row["molecule_id"]: _float(row["point"], "probe target") for row in targets
    }
    fitted = [molecule for molecule in training_ids if molecule in target_map]
    _require(
        len(fitted) >= 48 and bool(prediction_ids), "runtime probe support differs"
    )
    x_train = matrix[[index[molecule] for molecule in fitted]]
    y_train = np.asarray(
        [target_map[molecule] for molecule in fitted], dtype=np.float64
    )
    x_predict = matrix[[index[molecule] for molecule in prediction_ids]]
    identities = [
        *((configuration, g1.MODEL_SEEDS[0]) for configuration in g1.CONFIGURATION_IDS),
        (g1.CONFIGURATION_IDS[0], g1.MODEL_SEEDS[1]),
        (g1.CONFIGURATION_IDS[0], g1.MODEL_SEEDS[2]),
    ]
    rows: list[dict[str, object]] = []
    for configuration, seed in identities:
        prediction, resolved = real_predictor(
            configuration, seed, x_train, y_train, x_predict
        )
        rows.append(
            {
                "configuration_id": configuration,
                "model_seed": seed,
                "resolved_parameter_sha256": resolved,
                "prediction_sha256": base.sha256_bytes(
                    base.json_bytes(
                        [format(float(value), ".17g") for value in prediction]
                    )
                ),
                "training_rows": len(fitted),
                "prediction_rows": len(prediction_ids),
                "finite_predictions": True,
            }
        )
    _require(len(rows) == 14, "runtime probe topology differs")
    return rows


def _load_model(
    root: Path,
) -> tuple[
    dict[str, Any],
    list[str],
    dict[str, str],
    dict[tuple[str, int, int], dict[str, str]],
    np.ndarray[Any, Any],
]:
    base._readonly_root(root, "G1 execution model capability")
    manifest, _raw = base._load_json(root / "manifest.json")
    synthetic = manifest.get("synthetic")
    _require(
        manifest.get("schema_version") == compiler.MODEL_SCHEMA
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("accepted_g1_runner_sha256") == base.sha256_path(g1.SCRIPT)
        and manifest.get("compiler_source_sha256") == base.sha256_path(compiler.SCRIPT)
        and isinstance(synthetic, bool)
        and manifest.get("authority") == _authority(synthetic, "model"),
        "model capability identity differs",
    )
    features = base._read_csv(root / "feature_rows.csv", g1.FEATURE_COLUMNS)
    folds = base._read_csv(root / "folds.csv", g1.FOLD_COLUMNS)
    molecules = [row["molecule_id"] for row in features]
    _require(
        molecules == sorted(molecules) and len(molecules) == len(set(molecules)),
        "model molecule order differs",
    )
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in features
    }
    fold_index: dict[tuple[str, int, int], dict[str, str]] = {}
    for row in folds:
        key = row["molecule_id"], int(row["repeat"]), int(row["outer_validation_fold"])
        _require(
            key not in fold_index
            and row["molecule_id"] in components
            and row["similarity_component_hash"] == components[row["molecule_id"]],
            "model fold identity differs",
        )
        fold_index[key] = row
    _require(len(fold_index) == len(molecules) * 15, "model fold topology differs")
    arrays: list[np.ndarray[Any, Any]] = []
    receipts = manifest.get("arrays")
    _require(isinstance(receipts, Mapping), "model array receipts differ")
    assert isinstance(receipts, Mapping)
    for name, width, dtype in base.MAP_ARRAYS:
        array = np.load(root / name, allow_pickle=False)
        _require(
            base.sha256_path(root / name) == receipts[name]["sha256"]
            and array.shape == (len(molecules), width)
            and array.dtype == dtype
            and np.isfinite(array).all(),
            f"model array differs: {name}",
        )
        arrays.append(array)
    matrix = np.ascontiguousarray(np.concatenate(arrays, axis=1), dtype=np.float32)
    _require(
        matrix.shape == (len(molecules), g1.FEATURE_WIDTH), "feature matrix differs"
    )
    return manifest, molecules, components, fold_index, matrix


def _cell_ids(
    molecules: Sequence[str],
    folds: Mapping[tuple[str, int, int], Mapping[str, str]],
    *,
    repeat: int,
    outer: int,
    inner: int | None,
) -> tuple[list[str], list[str]]:
    scope = {molecule: folds[molecule, repeat, outer] for molecule in molecules}
    return base._cell_ids(scope, "outer" if inner is None else "inner", outer, inner)


def _targets(
    root: Path, *, stage: str, endpoint: str, repeat: int, outer: int, inner: int | None
) -> list[dict[str, str]]:
    path = g1._target_path(
        root,
        stage=stage,
        endpoint=endpoint,
        repeat=repeat,
        outer=outer,
        inner=inner,
    )
    return base._read_csv(path, g1.TARGET_COLUMNS)


def _seed_mean(
    *,
    predictor: PREDICTOR,
    configuration_id: str,
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], list[str]]:
    values: list[np.ndarray[Any, Any]] = []
    receipts: list[str] = []
    for seed in g1.MODEL_SEEDS:
        predicted, resolved = predictor(
            configuration_id, seed, training, targets, prediction
        )
        _require(
            predicted.shape == (len(prediction),)
            and bool(np.isfinite(predicted).all()),
            "model output differs",
        )
        values.append(predicted)
        receipts.append(resolved)
    return np.mean(np.stack(values), axis=0), receipts


def _tutorial_score(
    truth: Sequence[Mapping[str, str]], predictions: Mapping[str, float], endpoint: str
) -> tuple[float, int]:
    normalized = [
        {
            "molecule_id": row["molecule_id"],
            "endpoint": endpoint,
            "similarity_component_hash": row["similarity_component_hash"],
            "availability": (
                "complete" if row["tutorial_eligible"] == "true" else "missing"
            ),
            "point": row["point"],
            "low": row["low"],
            "high": row["high"],
        }
        for row in truth
    ]
    return g1._tutorial_score(normalized, predictions, endpoint)


def _component_mae(
    truth: Sequence[Mapping[str, str]], predictions: Mapping[str, float]
) -> tuple[float, int, int]:
    residuals: dict[str, list[float]] = defaultdict(list)
    eligible = 0
    for row in sorted(truth, key=lambda item: item["molecule_id"]):
        if row["point_eligible"] != "true":
            continue
        molecule = row["molecule_id"]
        _require(molecule in predictions, "component prediction is missing")
        residuals[row["similarity_component_hash"]].append(
            abs(predictions[molecule] - _float(row["point"], "component point"))
        )
        eligible += 1
    _require(bool(residuals), "component metric population is empty")
    component_values = [
        math.fsum(values) / len(values)
        for _component, values in sorted(residuals.items())
    ]
    return (
        math.fsum(component_values) / len(component_values),
        eligible,
        len(component_values),
    )


def _read_truth(
    root: Path, *, selector: bool
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    label = "selector" if selector else "scorer"
    schema = compiler.SELECTOR_SCHEMA if selector else compiler.SCORER_SCHEMA
    filename = "inner_validation_truth.csv" if selector else "outer_truth.csv"
    columns = compiler.INNER_TRUTH_COLUMNS if selector else compiler.OUTER_TRUTH_COLUMNS
    base._readonly_root(root, f"G1 execution {label} capability")
    manifest, _raw = base._load_json(root / "manifest.json")
    synthetic = manifest.get("synthetic")
    _require(
        manifest.get("schema_version") == schema
        and isinstance(synthetic, bool)
        and manifest.get("authority") == _authority(synthetic, label),
        f"{label} capability identity differs",
    )
    rows = base._read_csv(root / filename, columns)
    receipt_key = "inner_truth_sha256" if selector else "outer_truth_sha256"
    _require(
        base.sha256_path(root / filename) == manifest[receipt_key],
        f"{label} truth receipt differs",
    )
    return manifest, rows


def _write_csv(
    path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, object]]
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(columns),
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
        stream.flush()
        os.fsync(stream.fileno())
    return count


def _freeze_tree(root: Path) -> Path:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)
    return root


def _inner_path(root: Path, endpoint: str, repeat: int, outer: int) -> Path:
    return root / endpoint / f"repeat-{repeat}" / f"outer-{outer}.csv"


def run_inner_models(
    *,
    model_capability_root: Path,
    output_root: Path,
    predictor: PREDICTOR = real_predictor,
) -> tuple[Path, dict[str, int], dict[tuple[str, int], str]]:
    """Run all 8,640 inner fits and freeze seed-averaged predictions."""

    _require(
        not output_root.exists() and not output_root.is_symlink(), "inner output exists"
    )
    manifest, molecules, components, folds, matrix = _load_model(model_capability_root)
    index = {molecule: position for position, molecule in enumerate(molecules)}
    output_root.mkdir(parents=True)
    fits = 0
    raw_rows = 0
    frozen_rows = 0
    training_values = 0
    resolved: dict[tuple[str, int], str] = {}
    try:
        for endpoint in g1.ENDPOINTS:
            for repeat in g1.REPEATS:
                for outer in g1.OUTER_FOLDS:
                    cell_rows: list[dict[str, object]] = []
                    for inner in g1.INNER_FOLDS:
                        training_ids, prediction_ids = _cell_ids(
                            molecules,
                            folds,
                            repeat=repeat,
                            outer=outer,
                            inner=inner,
                        )
                        targets = _targets(
                            model_capability_root,
                            stage="inner",
                            endpoint=endpoint,
                            repeat=repeat,
                            outer=outer,
                            inner=inner,
                        )
                        target_map = {
                            row["molecule_id"]: _float(row["point"], "inner target")
                            for row in targets
                        }
                        fitted = [
                            molecule
                            for molecule in training_ids
                            if molecule in target_map
                        ]
                        _require(
                            len(fitted) == len(targets)
                            and set(target_map).issubset(training_ids),
                            "inner target crosses its training boundary",
                        )
                        x_train = matrix[[index[molecule] for molecule in fitted]]
                        y_train = np.asarray(
                            [target_map[molecule] for molecule in fitted],
                            dtype=np.float64,
                        )
                        x_predict = matrix[
                            [index[molecule] for molecule in prediction_ids]
                        ]
                        for configuration_id in g1.CONFIGURATION_IDS:
                            predicted, receipts = _seed_mean(
                                predictor=predictor,
                                configuration_id=configuration_id,
                                training=x_train,
                                targets=y_train,
                                prediction=x_predict,
                            )
                            fits += len(g1.MODEL_SEEDS)
                            raw_rows += len(prediction_ids) * len(g1.MODEL_SEEDS)
                            training_values += len(fitted) * len(g1.MODEL_SEEDS)
                            for seed, receipt in zip(
                                g1.MODEL_SEEDS, receipts, strict=True
                            ):
                                key = configuration_id, seed
                                if key in resolved:
                                    _require(
                                        resolved[key] == receipt,
                                        "resolved parameter drift",
                                    )
                                else:
                                    resolved[key] = receipt
                            cell_rows.extend(
                                {
                                    "molecule_id": molecule,
                                    "endpoint": endpoint,
                                    "similarity_component_hash": components[molecule],
                                    "repeat": repeat,
                                    "outer_fold": outer,
                                    "inner_fold": inner,
                                    "configuration_id": configuration_id,
                                    "prediction": format(float(value), ".17g"),
                                }
                                for molecule, value in zip(
                                    prediction_ids, predicted, strict=True
                                )
                            )
                    cell_rows.sort(
                        key=lambda row: tuple(row[name] for name in INNER_COLUMNS)
                    )
                    frozen_rows += _write_csv(
                        _inner_path(output_root, endpoint, repeat, outer),
                        INNER_COLUMNS,
                        cell_rows,
                    )
        _require(fits == 8640, "inner fit topology differs")
        cell_receipts = {
            path.relative_to(output_root).as_posix(): base.sha256_path(path)
            for path in output_root.rglob("*.csv")
        }
        result = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026.global_v2_g1_execution_inner.v1"
            ),
            "synthetic": manifest["synthetic"],
            "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
            "model_capability_manifest_sha256": base.sha256_path(
                model_capability_root / "manifest.json"
            ),
            "cells": cell_receipts,
            "counts": {
                "catboost_fits": fits,
                "raw_prediction_rows": raw_rows,
                "seed_averaged_prediction_rows": frozen_rows,
                "training_target_values_opened": training_values,
                "selector_truth_values_opened": 0,
                "outer_truth_values_opened": 0,
            },
            "authority": _authority(manifest["synthetic"], "model"),
        }
        (output_root / "manifest.json").write_bytes(base.json_bytes(result))
        return _freeze_tree(output_root), result["counts"], resolved
    except BaseException:
        base._cleanup(output_root)
        raise


def _load_inner_cell(
    root: Path, endpoint: str, repeat: int, outer: int
) -> list[dict[str, str]]:
    manifest, _raw = base._load_json(root / "manifest.json")
    path = _inner_path(root, endpoint, repeat, outer)
    relative = path.relative_to(root).as_posix()
    _require(
        manifest.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_g1_execution_inner.v1"
        and base.sha256_path(path) == manifest["cells"][relative],
        "inner frozen cell differs",
    )
    return base._read_csv(path, INNER_COLUMNS)


def select_configurations(
    *, inner_root: Path, selector_capability_root: Path, output_root: Path
) -> tuple[Path, list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    """Open inner truth after prediction freeze and select exact outer tokens."""

    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "selection output exists",
    )
    inner_manifest, _raw = base._load_json(inner_root / "manifest.json")
    selector_manifest, truth_rows = _read_truth(selector_capability_root, selector=True)
    _require(
        inner_manifest["model_capability_manifest_sha256"]
        == selector_manifest["model_capability_manifest_sha256"],
        "selector lineage differs",
    )
    truth_by_cell: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        truth_by_cell[
            row["endpoint"], int(row["repeat"]), int(row["outer_fold"])
        ].append(row)
    selections: list[dict[str, object]] = []
    metrics: list[dict[str, object]] = []
    projection_values: dict[tuple[str, str, str, int, str], list[float]] = defaultdict(
        list
    )
    tutorial_calls = 0
    metric_evaluations = 0
    for endpoint in g1.ENDPOINTS:
        for repeat in g1.REPEATS:
            for outer in g1.OUTER_FOLDS:
                truth = truth_by_cell[endpoint, repeat, outer]
                rows = _load_inner_cell(inner_root, endpoint, repeat, outer)
                predictions: dict[str, dict[str, float]] = defaultdict(dict)
                for row in rows:
                    configuration = row["configuration_id"]
                    molecule = row["molecule_id"]
                    _require(
                        molecule not in predictions[configuration],
                        "inner prediction duplicate",
                    )
                    value = _float(row["prediction"], "inner prediction")
                    predictions[configuration][molecule] = value
                    projection_values[
                        molecule,
                        endpoint,
                        row["similarity_component_hash"],
                        repeat,
                        configuration,
                    ].append(value)
                candidates: list[tuple[float, float, str, int, int, int]] = []
                for configuration in g1.CONFIGURATION_IDS:
                    configuration_predictions = predictions[configuration]
                    _require(
                        len(configuration_predictions) == len(truth),
                        "selector population differs",
                    )
                    tutorial, tutorial_rows = _tutorial_score(
                        truth, configuration_predictions, endpoint
                    )
                    component, point_rows, components = _component_mae(
                        truth, configuration_predictions
                    )
                    tutorial_calls += 1
                    metric_evaluations += 2
                    metrics.append(
                        {
                            "endpoint": endpoint,
                            "repeat": repeat,
                            "outer_fold": outer,
                            "configuration_id": configuration,
                            "tutorial_st_rae": format(tutorial, ".17g"),
                            "component_macro_mae": format(component, ".17g"),
                            "eligible_rows": tutorial_rows,
                            "components": components,
                        }
                    )
                    candidates.append(
                        (
                            tutorial,
                            component,
                            configuration,
                            tutorial_rows,
                            point_rows,
                            components,
                        )
                    )
                selected = min(candidates, key=lambda value: value[:3])
                token = _sha_text(
                    compiler.EXECUTION_CONTRACT_SHA256,
                    selector_manifest["inner_truth_sha256"],
                    endpoint,
                    repeat,
                    outer,
                    selected[2],
                    format(selected[0], ".17g"),
                    format(selected[1], ".17g"),
                )
                selections.append(
                    {
                        "endpoint": endpoint,
                        "repeat": repeat,
                        "outer_fold": outer,
                        "configuration_id": selected[2],
                        "tutorial_st_rae": format(selected[0], ".17g"),
                        "component_macro_mae": format(selected[1], ".17g"),
                        "selection_token_sha256": token,
                    }
                )
    projection: list[dict[str, object]] = []
    for key, projected_values in projection_values.items():
        _require(
            len(projected_values) == 4,
            "complete projection outer-context count differs",
        )
        projection.append(
            {
                "molecule_id": key[0],
                "endpoint": key[1],
                "similarity_component_hash": key[2],
                "repeat": key[3],
                "configuration_id": key[4],
                "prediction": format(math.fsum(projected_values) / 4.0, ".17g"),
            }
        )
    selections.sort(key=lambda row: tuple(row[name] for name in SELECTION_COLUMNS[:3]))
    metrics.sort(
        key=lambda row: tuple(row[name] for name in SELECTION_METRIC_COLUMNS[:4])
    )
    projection.sort(key=lambda row: tuple(row[name] for name in PROJECTION_COLUMNS[:5]))
    _require(
        len(selections) == 60 and len(metrics) == 720, "selection topology differs"
    )
    files = {
        "selection_tokens.csv": base.csv_bytes(SELECTION_COLUMNS, selections),
        "inner_selection_metrics.csv": base.csv_bytes(
            SELECTION_METRIC_COLUMNS, metrics
        ),
        "complete_selection_projection.csv": base.csv_bytes(
            PROJECTION_COLUMNS, projection
        ),
    }
    counts = {
        "configuration_metrics": len(metrics),
        "selection_tokens": len(selections),
        "complete_projection_rows": len(projection),
        "tutorial_metric_calls": tutorial_calls,
        "development_metric_evaluations": metric_evaluations,
        "outer_truth_values_opened": 0,
    }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_g1_execution_selections.v1",
        "synthetic": selector_manifest["synthetic"],
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "model_capability_manifest_sha256": selector_manifest[
            "model_capability_manifest_sha256"
        ],
        "selector_capability_manifest_sha256": base.sha256_path(
            selector_capability_root / "manifest.json"
        ),
        "counts": counts,
        "output_receipts": {
            name: base.sha256_bytes(value) for name, value in files.items()
        },
        "authority": _authority(selector_manifest["synthetic"], "selector"),
    }
    return (
        cast(
            Path,
            base.publish_files(
                output_root, {**files, "manifest.json": base.json_bytes(manifest)}
            ),
        ),
        selections,
        projection,
        counts,
    )


def run_outer_models(
    *,
    model_capability_root: Path,
    selection_root: Path,
    output_root: Path,
    predictor: PREDICTOR = real_predictor,
) -> tuple[Path, list[dict[str, object]], dict[str, int]]:
    """Refit only the 60 selected configurations under all three seeds."""

    _require(
        not output_root.exists() and not output_root.is_symlink(), "outer output exists"
    )
    model_manifest, molecules, components, folds, matrix = _load_model(
        model_capability_root
    )
    selection_manifest, _raw = base._load_json(selection_root / "manifest.json")
    _require(
        selection_manifest.get("model_capability_manifest_sha256")
        == base.sha256_path(model_capability_root / "manifest.json"),
        "outer selection lineage differs",
    )
    selection_rows = base._read_csv(
        selection_root / "selection_tokens.csv", SELECTION_COLUMNS
    )
    selections = {
        (row["endpoint"], int(row["repeat"]), int(row["outer_fold"])): row
        for row in selection_rows
    }
    _require(len(selections) == 60, "outer selection count differs")
    index = {molecule: position for position, molecule in enumerate(molecules)}
    rows: list[dict[str, object]] = []
    fits = 0
    raw_rows = 0
    training_values = 0
    resolved: dict[tuple[str, int], str] = {}
    for endpoint in g1.ENDPOINTS:
        for repeat in g1.REPEATS:
            for outer in g1.OUTER_FOLDS:
                selection = selections[endpoint, repeat, outer]
                configuration = selection["configuration_id"]
                training_ids, prediction_ids = _cell_ids(
                    molecules, folds, repeat=repeat, outer=outer, inner=None
                )
                targets = _targets(
                    model_capability_root,
                    stage="outer",
                    endpoint=endpoint,
                    repeat=repeat,
                    outer=outer,
                    inner=None,
                )
                target_map = {
                    row["molecule_id"]: _float(row["point"], "outer target")
                    for row in targets
                }
                fitted = [
                    molecule for molecule in training_ids if molecule in target_map
                ]
                _require(
                    len(fitted) == len(targets)
                    and set(target_map).issubset(training_ids),
                    "outer target crosses its training boundary",
                )
                x_train = matrix[[index[molecule] for molecule in fitted]]
                y_train = np.asarray(
                    [target_map[molecule] for molecule in fitted], dtype=np.float64
                )
                x_predict = matrix[[index[molecule] for molecule in prediction_ids]]
                predicted, receipts = _seed_mean(
                    predictor=predictor,
                    configuration_id=configuration,
                    training=x_train,
                    targets=y_train,
                    prediction=x_predict,
                )
                fits += 3
                raw_rows += len(prediction_ids) * 3
                training_values += len(fitted) * 3
                for seed, receipt in zip(g1.MODEL_SEEDS, receipts, strict=True):
                    key = configuration, seed
                    if key in resolved:
                        _require(
                            resolved[key] == receipt, "outer resolved parameter drift"
                        )
                    else:
                        resolved[key] = receipt
                rows.extend(
                    {
                        "molecule_id": molecule,
                        "endpoint": endpoint,
                        "similarity_component_hash": components[molecule],
                        "repeat": repeat,
                        "outer_fold": outer,
                        "configuration_id": configuration,
                        "prediction": format(float(value), ".17g"),
                    }
                    for molecule, value in zip(prediction_ids, predicted, strict=True)
                )
    rows.sort(key=lambda row: tuple(row[name] for name in OUTER_COLUMNS))
    _require(fits == 180, "outer fit topology differs")
    value = base.csv_bytes(OUTER_COLUMNS, rows)
    counts = {
        "catboost_fits": fits,
        "raw_prediction_rows": raw_rows,
        "seed_averaged_prediction_rows": len(rows),
        "training_target_values_opened": training_values,
        "outer_truth_values_opened": 0,
    }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_g1_execution_outer.v1",
        "synthetic": model_manifest["synthetic"],
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "model_capability_manifest_sha256": base.sha256_path(
            model_capability_root / "manifest.json"
        ),
        "selection_manifest_sha256": base.sha256_path(selection_root / "manifest.json"),
        "counts": counts,
        "resolved_parameter_receipts": {
            f"{configuration}|{seed}": receipt
            for (configuration, seed), receipt in sorted(resolved.items())
        },
        "output_receipts": {"g1_outer_predictions.csv": base.sha256_bytes(value)},
        "authority": _authority(model_manifest["synthetic"], "model"),
    }
    return (
        cast(
            Path,
            base.publish_files(
                output_root,
                {
                    "g1_outer_predictions.csv": value,
                    "manifest.json": base.json_bytes(manifest),
                },
            ),
        ),
        rows,
        counts,
    )


def _paired_bootstrap(
    *,
    truth_rows: Sequence[Mapping[str, str]],
    candidate: Mapping[tuple[str, str, int], float],
    baseline: Mapping[tuple[str, str, int], float],
) -> dict[str, object]:
    component_cells: dict[tuple[str, str, int], list[tuple[float, float]]] = (
        defaultdict(list)
    )
    for row in truth_rows:
        if row["point_eligible"] != "true":
            continue
        key = row["molecule_id"], row["endpoint"], int(row["repeat"])
        _require(
            key in candidate and key in baseline, "bootstrap paired identity differs"
        )
        point = _float(row["point"], "bootstrap point")
        component_cells[
            row["similarity_component_hash"], row["endpoint"], int(row["repeat"])
        ].append((abs(candidate[key] - point), abs(baseline[key] - point)))
    reduced = {
        key: (
            math.fsum(value[0] for value in pairs) / len(pairs),
            math.fsum(value[1] for value in pairs) / len(pairs),
        )
        for key, pairs in component_cells.items()
    }
    components = sorted({key[0] for key in reduced})
    _require(bool(components), "bootstrap component population is empty")
    generator = random.Random(20260827)
    differences: list[float] = []
    attempts = 0
    while len(differences) < 2000 and attempts < 20000:
        attempts += 1
        draw = [components[generator.randrange(len(components))] for _ in components]
        candidate_cells: list[float] = []
        baseline_cells: list[float] = []
        accepted = True
        for endpoint in g1.ENDPOINTS:
            for repeat in g1.REPEATS:
                pairs = [
                    reduced[name, endpoint, repeat]
                    for name in draw
                    if (name, endpoint, repeat) in reduced
                ]
                if not pairs:
                    accepted = False
                    break
                candidate_cells.append(
                    math.fsum(pair[0] for pair in pairs) / len(pairs)
                )
                baseline_cells.append(math.fsum(pair[1] for pair in pairs) / len(pairs))
            if not accepted:
                break
        if not accepted:
            continue
        difference = (
            math.fsum(candidate_cells) / 12.0 - math.fsum(baseline_cells) / 12.0
        )
        if math.isfinite(difference):
            differences.append(difference)
    _require(len(differences) == 2000, "bootstrap accepted replicate count differs")
    return {
        "unit": "similarity_component_hash",
        "seed": 20260827,
        "accepted_replicates": len(differences),
        "attempts": attempts,
        "maximum_attempts": 20000,
        "difference": "candidate_component_macro_mae_minus_baseline",
        "lower_95": g1._quantile(differences, 0.025),
        "upper_95": g1._quantile(differences, 0.975),
    }


def _future_configurations(
    *,
    projection: Sequence[Mapping[str, object]],
    truth_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, object]], int, int]:
    truth_unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in truth_rows:
        truth_key = row["molecule_id"], row["endpoint"]
        normalized = {name: row[name] for name in compiler.TRUTH_COLUMNS}
        if truth_key in truth_unique:
            _require(
                truth_unique[truth_key] == normalized, "future truth copies differ"
            )
        else:
            truth_unique[truth_key] = normalized
    predictions: dict[tuple[str, int, str], dict[str, float]] = defaultdict(dict)
    for row in projection:
        projection_key = (
            str(row["endpoint"]),
            int(row["repeat"]),
            str(row["configuration_id"]),
        )
        molecule = str(row["molecule_id"])
        _require(
            molecule not in predictions[projection_key], "future projection duplicate"
        )
        predictions[projection_key][molecule] = _float(
            str(row["prediction"]), "future prediction"
        )
    tokens: list[dict[str, object]] = []
    calls = 0
    evaluations = 0
    for endpoint in g1.ENDPOINTS:
        truth = [
            truth_unique[molecule, endpoint]
            for molecule in sorted(
                molecule for molecule, observed in truth_unique if observed == endpoint
            )
        ]
        candidates: list[tuple[float, float, str]] = []
        for configuration in g1.CONFIGURATION_IDS:
            tutorial_values: list[float] = []
            component_values: list[float] = []
            for repeat in g1.REPEATS:
                values = predictions[endpoint, repeat, configuration]
                _require(
                    len(values) == len(truth), "future projection population differs"
                )
                tutorial_values.append(_tutorial_score(truth, values, endpoint)[0])
                component_values.append(_component_mae(truth, values)[0])
                calls += 1
                evaluations += 2
            candidates.append(
                (
                    math.fsum(tutorial_values) / 3.0,
                    math.fsum(component_values) / 3.0,
                    configuration,
                )
            )
        selected = min(candidates)
        token = _sha_text(
            compiler.EXECUTION_CONTRACT_SHA256,
            endpoint,
            selected[2],
            format(selected[0], ".17g"),
            format(selected[1], ".17g"),
        )
        tokens.append(
            {
                "endpoint": endpoint,
                "configuration_id": selected[2],
                "tutorial_st_rae": format(selected[0], ".17g"),
                "component_macro_mae": format(selected[1], ".17g"),
                "future_configuration_token_sha256": token,
            }
        )
    return tokens, calls, evaluations


def score_and_publish(
    *,
    inner_root: Path,
    outer_root: Path,
    selection_root: Path,
    selector_capability_root: Path,
    scorer_capability_root: Path,
    output_root: Path,
    inner_counts: Mapping[str, int],
    outer_counts: Mapping[str, int],
    selection_counts: Mapping[str, int],
    projection: Sequence[Mapping[str, object]],
    consumed_claim_sha256: str | None = None,
) -> Path:
    """Open outer truth only after outer predictions and baseline are frozen."""

    _require(
        not output_root.exists() and not output_root.is_symlink(), "terminal exists"
    )
    outer_manifest, _raw = base._load_json(outer_root / "manifest.json")
    selector_manifest, selector_truth = _read_truth(
        selector_capability_root, selector=True
    )
    scorer_manifest, truth_rows = _read_truth(scorer_capability_root, selector=False)
    _require(
        outer_manifest["model_capability_manifest_sha256"]
        == selector_manifest["model_capability_manifest_sha256"]
        == scorer_manifest["model_capability_manifest_sha256"],
        "scorer lineage differs",
    )
    outer_rows = base._read_csv(outer_root / "g1_outer_predictions.csv", OUTER_COLUMNS)
    baseline_rows = base._read_csv(
        scorer_capability_root / "baseline_predictions.csv", compiler.BASELINE_COLUMNS
    )
    _require(
        base.sha256_path(scorer_capability_root / "baseline_predictions.csv")
        == scorer_manifest["baseline_predictions_sha256"],
        "baseline prediction receipt differs",
    )
    candidate: dict[tuple[str, str, int], float] = {}
    candidate_cell: dict[tuple[str, str, int, int], float] = {}
    for row in outer_rows:
        key = row["molecule_id"], row["endpoint"], int(row["repeat"])
        cell = (*key, int(row["outer_fold"]))
        _require(
            key not in candidate and cell not in candidate_cell, "candidate duplicate"
        )
        candidate[key] = _float(row["prediction"], "candidate prediction")
        candidate_cell[cell] = candidate[key]
    baseline: dict[tuple[str, str, int], float] = {}
    for row in baseline_rows:
        key = row["molecule_id"], row["endpoint"], int(row["repeat"])
        _require(key not in baseline, "baseline duplicate")
        baseline[key] = _float(row["prediction"], "baseline prediction")
    _require(set(candidate) == set(baseline), "candidate/baseline join differs")

    truth_by_endpoint_repeat: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(
        list
    )
    truth_by_cell: dict[tuple[str, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        truth_by_endpoint_repeat[row["endpoint"], int(row["repeat"])].append(row)
        truth_by_cell[
            row["endpoint"], int(row["repeat"]), int(row["outer_fold"])
        ].append(row)
    values: dict[tuple[str, int], tuple[float, float, float, float]] = {}
    tutorial_calls = 0
    metric_evaluations = 0
    for endpoint in g1.ENDPOINTS:
        for repeat in g1.REPEATS:
            truth = truth_by_endpoint_repeat[endpoint, repeat]
            candidate_predictions = {
                row["molecule_id"]: candidate[row["molecule_id"], endpoint, repeat]
                for row in truth
            }
            baseline_predictions = {
                row["molecule_id"]: baseline[row["molecule_id"], endpoint, repeat]
                for row in truth
            }
            candidate_tutorial = _tutorial_score(
                truth, candidate_predictions, endpoint
            )[0]
            baseline_tutorial = _tutorial_score(truth, baseline_predictions, endpoint)[
                0
            ]
            candidate_component = _component_mae(truth, candidate_predictions)[0]
            baseline_component = _component_mae(truth, baseline_predictions)[0]
            tutorial_calls += 2
            metric_evaluations += 4
            values[endpoint, repeat] = (
                candidate_tutorial,
                baseline_tutorial,
                candidate_component,
                baseline_component,
            )

    endpoint_rows: list[dict[str, object]] = []
    for endpoint in g1.ENDPOINTS:
        candidate_tutorial = (
            math.fsum(values[endpoint, repeat][0] for repeat in g1.REPEATS) / 3.0
        )
        baseline_tutorial = (
            math.fsum(values[endpoint, repeat][1] for repeat in g1.REPEATS) / 3.0
        )
        candidate_component = (
            math.fsum(values[endpoint, repeat][2] for repeat in g1.REPEATS) / 3.0
        )
        baseline_component = (
            math.fsum(values[endpoint, repeat][3] for repeat in g1.REPEATS) / 3.0
        )
        endpoint_rows.append(
            {
                "endpoint": endpoint,
                "candidate_tutorial_st_rae": format(candidate_tutorial, ".17g"),
                "baseline_tutorial_st_rae": format(baseline_tutorial, ".17g"),
                "candidate_component_macro_mae": format(candidate_component, ".17g"),
                "baseline_component_macro_mae": format(baseline_component, ".17g"),
                "component_mae_difference": format(
                    candidate_component - baseline_component, ".17g"
                ),
            }
        )

    outer_cells: list[dict[str, object]] = []
    favorable = 0
    for repeat in g1.REPEATS:
        for outer in g1.OUTER_FOLDS:
            candidate_endpoint: list[float] = []
            baseline_endpoint: list[float] = []
            for endpoint in g1.ENDPOINTS:
                truth = truth_by_cell[endpoint, repeat, outer]
                candidate_predictions = {
                    row["molecule_id"]: candidate_cell[
                        row["molecule_id"], endpoint, repeat, outer
                    ]
                    for row in truth
                }
                baseline_predictions = {
                    row["molecule_id"]: baseline[row["molecule_id"], endpoint, repeat]
                    for row in truth
                }
                candidate_endpoint.append(
                    _component_mae(truth, candidate_predictions)[0]
                )
                baseline_endpoint.append(_component_mae(truth, baseline_predictions)[0])
                metric_evaluations += 2
            candidate_value = math.fsum(candidate_endpoint) / 4.0
            baseline_value = math.fsum(baseline_endpoint) / 4.0
            is_favorable = candidate_value < baseline_value
            favorable += int(is_favorable)
            outer_cells.append(
                {
                    "repeat": repeat,
                    "outer_fold": outer,
                    "candidate_component_macro_mae": format(candidate_value, ".17g"),
                    "baseline_component_macro_mae": format(baseline_value, ".17g"),
                    "difference": format(candidate_value - baseline_value, ".17g"),
                    "favorable": "true" if is_favorable else "false",
                }
            )

    candidate_primary = (
        math.fsum(
            values[endpoint, repeat][0]
            for endpoint in g1.ENDPOINTS
            for repeat in g1.REPEATS
        )
        / 12.0
    )
    baseline_primary = (
        math.fsum(
            values[endpoint, repeat][1]
            for endpoint in g1.ENDPOINTS
            for repeat in g1.REPEATS
        )
        / 12.0
    )
    candidate_component = (
        math.fsum(
            values[endpoint, repeat][2]
            for endpoint in g1.ENDPOINTS
            for repeat in g1.REPEATS
        )
        / 12.0
    )
    baseline_component = (
        math.fsum(
            values[endpoint, repeat][3]
            for endpoint in g1.ENDPOINTS
            for repeat in g1.REPEATS
        )
        / 12.0
    )
    _require(baseline_primary > 0.0, "baseline tutorial metric is nonpositive")
    bootstrap = _paired_bootstrap(
        truth_rows=truth_rows, candidate=candidate, baseline=baseline
    )
    future_rows, future_calls, future_evaluations = _future_configurations(
        projection=projection, truth_rows=selector_truth
    )
    tutorial_calls += future_calls
    metric_evaluations += future_evaluations
    relative_improvement = (baseline_primary - candidate_primary) / baseline_primary
    component_improvement = baseline_component - candidate_component
    max_endpoint_degradation = max(
        _float(str(row["component_mae_difference"]), "endpoint degradation")
        for row in endpoint_rows
    )
    gates = {
        "relative_primary_improvement_at_least_0_03": relative_improvement >= 0.03,
        "absolute_component_mae_improvement_at_least_0_015": component_improvement
        >= 0.015,
        "paired_component_mae_upper_95_below_zero": cast(float, bootstrap["upper_95"])
        < 0.0,
        "favorable_outer_cells_at_least_8": favorable >= 8,
        "maximum_endpoint_mae_degradation_at_most_0_015": max_endpoint_degradation
        <= 0.015,
    }
    synthetic = bool(scorer_manifest["synthetic"])
    status = (
        "G2_3C_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
        if synthetic
        else "G2_3_G1_ACCEPTED"
        if all(gates.values())
        else "G2_3_G1_REJECTED"
    )
    result = {
        "status": status,
        "candidate_primary_tutorial_st_rae": candidate_primary,
        "baseline_primary_tutorial_st_rae": baseline_primary,
        "relative_primary_improvement": relative_improvement,
        "candidate_component_macro_mae": candidate_component,
        "baseline_component_macro_mae": baseline_component,
        "absolute_component_mae_improvement": component_improvement,
        "favorable_outer_cells": favorable,
        "maximum_endpoint_mae_degradation": max_endpoint_degradation,
        "paired_component_upper_95": bootstrap["upper_95"],
        "gates": gates,
        "all_five_gates_pass": all(gates.values()),
        "scientific_interpretation": (
            "Official-shaped synthetic mechanics only."
            if synthetic
            else "Frozen development evidence; not a verified live-backend score."
        ),
    }

    selection_rows = base._read_csv(
        selection_root / "selection_tokens.csv", SELECTION_COLUMNS
    )
    summary: list[dict[str, object]] = [
        {
            "scope": "outer",
            "endpoint": row["endpoint"],
            "repeat": row["repeat"],
            "outer_fold": row["outer_fold"],
            "configuration_id": row["configuration_id"],
            "tutorial_st_rae": row["tutorial_st_rae"],
            "component_macro_mae": row["component_macro_mae"],
            "token_sha256": row["selection_token_sha256"],
        }
        for row in selection_rows
    ]
    summary.extend(
        {
            "scope": "future",
            "endpoint": row["endpoint"],
            "repeat": "",
            "outer_fold": "",
            "configuration_id": row["configuration_id"],
            "tutorial_st_rae": row["tutorial_st_rae"],
            "component_macro_mae": row["component_macro_mae"],
            "token_sha256": row["future_configuration_token_sha256"],
        }
        for row in future_rows
    )
    aggregate = {
        "g1_selection_summary.csv": base.csv_bytes(
            g1.SELECTION_SUMMARY_COLUMNS, summary
        ),
        "g1_outer_cell_metrics.csv": base.csv_bytes(OUTER_CELL_COLUMNS, outer_cells),
        "g1_endpoint_metrics.csv": base.csv_bytes(ENDPOINT_COLUMNS, endpoint_rows),
        "g1_bootstrap_summary.json": base.json_bytes(bootstrap),
        "g1_result.json": base.json_bytes(result),
    }
    inner_payload = bytearray()
    inner_payload.extend((",".join(INNER_COLUMNS) + "\n").encode("utf-8"))
    for endpoint in g1.ENDPOINTS:
        for repeat in g1.REPEATS:
            for outer in g1.OUTER_FOLDS:
                data = _inner_path(inner_root, endpoint, repeat, outer).read_bytes()
                inner_payload.extend(data.split(b"\n", 1)[1])
    private = {
        "g1_inner_predictions.csv": bytes(inner_payload),
        "g1_outer_predictions.csv": (
            outer_root / "g1_outer_predictions.csv"
        ).read_bytes(),
        "g1_complete_selection_projection.csv": (
            selection_root / "complete_selection_projection.csv"
        ).read_bytes(),
    }
    compiler_accounting = scorer_manifest["accounting"]
    selection_tutorial_calls = int(selection_counts["tutorial_metric_calls"])
    total_tutorial_calls = selection_tutorial_calls + tutorial_calls
    total_metric_evaluations = (
        int(selection_counts["development_metric_evaluations"]) + metric_evaluations
    )
    accounting = {
        **compiler_accounting,
        "official_baseline_prediction_rows_opened": (
            0 if synthetic else len(baseline_rows)
        ),
        "official_model_fits": 0 if synthetic else 8820,
        "official_predictions_generated": (
            0
            if synthetic
            else int(inner_counts["raw_prediction_rows"])
            + int(outer_counts["raw_prediction_rows"])
        ),
        "development_metric_evaluations": 0 if synthetic else total_metric_evaluations,
        "tutorial_ma_st_rae_calls": 0 if synthetic else total_tutorial_calls,
        "synthetic_model_fits": 8820 if synthetic else 0,
        "synthetic_tutorial_ma_st_rae_calls": total_tutorial_calls if synthetic else 0,
    }
    _require(
        all(accounting.get(name) == 0 for name in FORBIDDEN_COUNTERS),
        "forbidden accounting differs",
    )
    counts = {
        "molecules": len({row["molecule_id"] for row in truth_rows}),
        "inner_catboost_fits": int(inner_counts["catboost_fits"]),
        "inner_raw_prediction_rows": int(inner_counts["raw_prediction_rows"]),
        "inner_seed_averaged_prediction_rows": int(
            inner_counts["seed_averaged_prediction_rows"]
        ),
        "outer_catboost_fits": int(outer_counts["catboost_fits"]),
        "outer_raw_prediction_rows": int(outer_counts["raw_prediction_rows"]),
        "outer_seed_averaged_prediction_rows": int(
            outer_counts["seed_averaged_prediction_rows"]
        ),
        "selection_tokens": 60,
        "future_tokens": 4,
        "tutorial_metric_calls": total_tutorial_calls,
    }
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_v2_g1_execution_terminal.v1",
        "status": status,
        "synthetic": synthetic,
        "consumed_claim_sha256": consumed_claim_sha256,
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "implementation_receipts": {
            "accepted_g1_runner_sha256": base.sha256_path(g1.SCRIPT),
            "compiler_source_sha256": base.sha256_path(compiler.SCRIPT),
            "execution_wrapper_source_sha256": base.sha256_path(SCRIPT),
            "research_uv_lock_sha256": base.sha256_path(g1.LOCK),
            "tutorial_metric_source_sha256": base.sha256_path(g1.METRIC_SOURCE),
        },
        "source_receipts": {
            "selector_capability_manifest_sha256": base.sha256_path(
                selector_capability_root / "manifest.json"
            ),
            "scorer_capability_manifest_sha256": base.sha256_path(
                scorer_capability_root / "manifest.json"
            ),
            "inner_prediction_manifest_sha256": base.sha256_path(
                inner_root / "manifest.json"
            ),
            "outer_prediction_manifest_sha256": base.sha256_path(
                outer_root / "manifest.json"
            ),
            "selection_manifest_sha256": base.sha256_path(
                selection_root / "manifest.json"
            ),
        },
        "runtime": _runtime_identity(),
        "counts": counts,
        "accounting": accounting,
        "result": result,
        "output_receipts": {
            name: base.sha256_bytes(value)
            for name, value in {**aggregate, **private}.items()
        },
        "authority": _authority(synthetic, "terminal"),
    }
    return cast(
        Path,
        base.publish_files(
            output_root,
            {**aggregate, **private, "manifest.json": base.json_bytes(manifest)},
        ),
    )


def run_compiled_replay(
    *,
    model_capability_root: Path,
    selector_capability_root: Path,
    scorer_capability_root: Path,
    work_root: Path,
    predictor: PREDICTOR = real_predictor,
    consumed_claim_sha256: str | None = None,
) -> Path:
    """Execute one fresh compiled replay with immutable stage boundaries."""

    _require(not work_root.exists() and not work_root.is_symlink(), "work root exists")
    work_root.mkdir(parents=True)
    try:
        inner, inner_counts, _inner_resolved = run_inner_models(
            model_capability_root=model_capability_root,
            output_root=work_root / "inner",
            predictor=predictor,
        )
        selection, _selections, projection, selection_counts = select_configurations(
            inner_root=inner,
            selector_capability_root=selector_capability_root,
            output_root=work_root / "selection",
        )
        outer, _outer_rows, outer_counts = run_outer_models(
            model_capability_root=model_capability_root,
            selection_root=selection,
            output_root=work_root / "outer",
            predictor=predictor,
        )
        return score_and_publish(
            inner_root=inner,
            outer_root=outer,
            selection_root=selection,
            selector_capability_root=selector_capability_root,
            scorer_capability_root=scorer_capability_root,
            output_root=work_root / "terminal",
            inner_counts=inner_counts,
            outer_counts=outer_counts,
            selection_counts=selection_counts,
            projection=projection,
            consumed_claim_sha256=consumed_claim_sha256,
        )
    except BaseException:
        base._cleanup(work_root)
        raise


def derive_consumed_claim(
    *, tracked_claim_path: Path, acceptance_path: Path
) -> dict[str, Any]:
    """Derive the sole private claim from exact integrated acceptance receipts."""

    _require(
        base.sha256_path(tracked_claim_path) == compiler.TRACKED_CLAIM_SHA256,
        "tracked claim receipt differs",
    )
    claim, _claim_raw = base._load_json(tracked_claim_path)
    _require(
        claim.get("status") == "G2_3C_CLAIM_UNCONSUMED"
        and claim.get("contract_sha256") == compiler.EXECUTION_CONTRACT_SHA256
        and claim.get("future_official_compiler_source_sha256") is None
        and claim.get("future_attempt_wrapper_source_sha256") is None
        and claim.get("future_official_shaped_synthetic_driver_source_sha256") is None
        and claim.get("future_official_shaped_synthetic_acceptance_sha256") is None
        and claim.get("maximum_consumptions") == 1,
        "tracked claim state differs",
    )
    acceptance, _acceptance_raw = base._load_json(acceptance_path)
    accounting = acceptance.get("accounting_per_replay")
    counts = acceptance.get("counts_per_replay")
    resource_bounds = acceptance.get("resource_bounds")
    _require(
        acceptance.get("schema_version")
        == "cypshift.openadmet_cyp_2026.global_v2_g1_execution_synthetic_acceptance.v1"
        and acceptance.get("status") == "G2_3C_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED"
        and acceptance.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and acceptance.get("compiler_source_sha256")
        == base.sha256_path(compiler.SCRIPT)
        and acceptance.get("execution_wrapper_source_sha256")
        == base.sha256_path(SCRIPT)
        and acceptance.get("acceptance_source_sha256")
        == base.sha256_path(ACCEPTANCE_SOURCE)
        and acceptance.get("accepted_g1_runner_source_sha256")
        == base.sha256_path(g1.SCRIPT)
        and acceptance.get("runtime_lock_sha256") == base.sha256_path(g1.LOCK)
        and acceptance.get("roots") == 2
        and acceptance.get("second_source_physical_order_reversed") is True
        and acceptance.get("relative_byte_maps_identical") is True
        and acceptance.get("files_compared") == 9
        and compiler._is_sha(acceptance.get("combined_terminal_tree_sha256"))
        and compiler._is_sha(acceptance.get("runtime_probe_receipt_sha256"))
        and acceptance.get("full_topology_model_fits_per_replay") == 8820
        and acceptance.get("full_topology_model_fits_total") == 17640
        and acceptance.get("real_runtime_probe_fits_total") == 28
        and acceptance.get("runtime_probe_fits_per_root") == 14
        and acceptance.get("sparse_point_and_tutorial_masks_distinct") is True
        and acceptance.get("private_roots_retained") == 0
        and isinstance(accounting, Mapping)
        and isinstance(counts, Mapping)
        and isinstance(resource_bounds, Mapping)
        and counts
        == {
            "future_tokens": 4,
            "inner_catboost_fits": 8640,
            "inner_raw_prediction_rows": 539136,
            "inner_seed_averaged_prediction_rows": 179712,
            "molecules": 312,
            "outer_catboost_fits": 180,
            "outer_raw_prediction_rows": 11232,
            "outer_seed_averaged_prediction_rows": 3744,
            "selection_tokens": 60,
            "tutorial_metric_calls": 888,
        }
        and accounting.get("synthetic_model_fits") == 8820
        and accounting.get("synthetic_tutorial_ma_st_rae_calls") == 888
        and accounting.get("development_finite_targets") == 999
        and accounting.get("development_tutorial_eligible_rows") == 860
        and accounting.get("development_point_only_rows") == 139
        and accounting.get("development_tutorial_without_std_rows") == 424
        and accounting.get("confirmatory_rows_kept_opaque") == 352
        and accounting.get("confirmatory_target_values_parsed") == 0
        and all(accounting.get(name) == 0 for name in FORBIDDEN_COUNTERS)
        and resource_bounds
        == {
            "maximum_concurrent_catboost_fits": 1,
            "thread_count_per_fit": 16,
            "maximum_wall_seconds": MAXIMUM_WALL_SECONDS,
            "maximum_cpu_core_hours": MAXIMUM_CPU_CORE_HOURS,
            "maximum_restricted_storage_bytes": MAXIMUM_RESTRICTED_STORAGE_BYTES,
            "retry": False,
            "resume": False,
            "move": False,
            "overwrite": False,
        }
        and acceptance.get("authority") == g1.DENIED_AUTHORITY,
        "synthetic acceptance differs",
    )
    consumed = dict(claim)
    consumed.update(
        {
            "status": "G2_3C_CLAIM_CONSUMED",
            "future_official_compiler_source_sha256": base.sha256_path(compiler.SCRIPT),
            "future_attempt_wrapper_source_sha256": base.sha256_path(SCRIPT),
            "future_official_shaped_synthetic_driver_source_sha256": (
                base.sha256_path(ACCEPTANCE_SOURCE)
            ),
            "future_official_shaped_synthetic_acceptance_sha256": (
                base.sha256_path(acceptance_path)
            ),
        }
    )
    return consumed


def _publish_claim(attempt_root: Path, claim: Mapping[str, Any]) -> Path:
    data = base.json_bytes(dict(claim))
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
    return path


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _resource_snapshot(
    *, started: float, attempt_root: Path, peak_bytes: int
) -> tuple[dict[str, float | int], int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.monotonic() - started
    cpu_hours = (usage.ru_utime + usage.ru_stime) / 3600.0
    peak = max(peak_bytes, _tree_bytes(attempt_root))
    _require(wall <= MAXIMUM_WALL_SECONDS, "official wall ceiling exceeded")
    _require(
        cpu_hours <= MAXIMUM_CPU_CORE_HOURS,
        "official CPU-core-hour ceiling exceeded",
    )
    _require(
        peak <= MAXIMUM_RESTRICTED_STORAGE_BYTES,
        "official restricted-storage ceiling exceeded",
    )
    return (
        {
            "wall_seconds": wall,
            "process_cpu_core_hours": cpu_hours,
            "peak_restricted_storage_bytes": peak,
            "gpu_hours": 0,
        },
        peak,
    )


def _copy_terminal(source: Path, destination: Path) -> Path:
    staging = destination.with_name(".terminal-staging")
    _require(
        not staging.exists()
        and not staging.is_symlink()
        and not destination.exists()
        and not destination.is_symlink(),
        "terminal publication target exists",
    )
    shutil.copytree(source, staging, copy_function=shutil.copyfile)
    _freeze_tree(staging)
    os.rename(staging, destination)
    return destination


def _attempt_receipt(
    *,
    attempt_root: Path,
    terminal: Path,
    claim_sha256: str,
    resource_usage: Mapping[str, float | int],
) -> Path:
    manifest, _raw = base._load_json(terminal / "manifest.json")
    receipt = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_g1_execution_attempt_receipt.v1"
        ),
        "status": manifest["status"],
        "contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "terminal_manifest_sha256": base.sha256_path(terminal / "manifest.json"),
        "terminal_tree": base.relative_byte_map(terminal),
        "implementation_receipts": manifest.get("implementation_receipts", {}),
        "accounting": manifest.get("accounting", {}),
        "resource": dict(resource_usage),
    }
    return cast(
        Path,
        base.publish_files(
            attempt_root / "receipt",
            {"official_attempt_receipt.json": base.json_bytes(receipt)},
        ),
    )


def _failure_terminal(
    *,
    attempt_root: Path,
    claim_sha256: str,
    runtime: Mapping[str, str],
    category: str,
) -> Path:
    manifest = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_g1_execution_terminal.v1"
        ),
        "status": "G2_3_G1_FAILED",
        "synthetic": False,
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "failure_category": category,
        "runtime": dict(runtime),
        "accounting": {
            **{name: 0 for name in FORBIDDEN_COUNTERS},
            "submissions_created": 0,
            "leaderboard_observations": 0,
            "live_uploads": 0,
        },
        "authority": _authority(False, "terminal"),
    }
    return cast(
        Path,
        base.publish_files(
            attempt_root / "terminal", {"manifest.json": base.json_bytes(manifest)}
        ),
    )


def run_official_attempt(
    *,
    source_root: Path = compiler.OFFICIAL_SOURCE_ROOT,
    baseline_terminal_root: Path = compiler.OFFICIAL_BASELINE_ROOT,
    attempt_root: Path = OFFICIAL_ATTEMPT_ROOT,
    tracked_claim_path: Path = compiler.TRACKED_CLAIM,
    acceptance_path: Path = TRACKED_ACCEPTANCE,
) -> Path:
    """Consume the sole claim and run exactly one non-resumable official attempt."""

    consumed = derive_consumed_claim(
        tracked_claim_path=tracked_claim_path, acceptance_path=acceptance_path
    )
    runtime = _runtime_identity()
    parent = attempt_root.parent.resolve(strict=True)
    resolved_attempt = parent / attempt_root.name
    repository = compiler.ROOT.resolve(strict=True)
    _require(
        resolved_attempt == OFFICIAL_ATTEMPT_ROOT
        and resolved_attempt != repository
        and repository not in resolved_attempt.parents
        and not attempt_root.exists()
        and not attempt_root.is_symlink()
        and not any(path.is_symlink() for path in attempt_root.parents),
        "fixed official attempt root is unavailable",
    )
    _require(
        source_root.resolve(strict=True) == compiler.OFFICIAL_SOURCE_ROOT
        and baseline_terminal_root.resolve(strict=True)
        == compiler.OFFICIAL_BASELINE_ROOT,
        "fixed official input root differs",
    )
    _require(
        shutil.disk_usage(parent).free >= MAXIMUM_RESTRICTED_STORAGE_BYTES,
        "official storage reservation is unavailable",
    )
    started = time.monotonic()
    peak_bytes = 0
    attempt_root.mkdir(mode=0o700)
    claim_path = _publish_claim(attempt_root, consumed)
    claim_sha = base.sha256_path(claim_path)
    private = attempt_root / ".private-execution"
    private.mkdir(mode=0o700)

    def bounded_predictor(
        configuration_id: str,
        model_seed: int,
        training: np.ndarray[Any, Any],
        targets: np.ndarray[Any, Any],
        prediction: np.ndarray[Any, Any],
    ) -> tuple[np.ndarray[Any, Any], str]:
        nonlocal peak_bytes
        result = real_predictor(
            configuration_id,
            model_seed,
            training,
            targets,
            prediction,
        )
        _usage, peak_bytes = _resource_snapshot(
            started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
        )
        return result

    try:
        model, selector, scorer, _preflight = compiler.compile_capabilities(
            source_root=source_root,
            baseline_terminal_root=baseline_terminal_root,
            output_root=private / "capabilities",
            expected_compiler_sha256=base.sha256_path(compiler.SCRIPT),
            mode="official",
            consumed_claim_path=claim_path,
        )
        terminal_private = run_compiled_replay(
            model_capability_root=model,
            selector_capability_root=selector,
            scorer_capability_root=scorer,
            work_root=private / "execution",
            predictor=bounded_predictor,
            consumed_claim_sha256=claim_sha,
        )
        _usage, peak_bytes = _resource_snapshot(
            started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
        )
        projected_publication_bytes = _tree_bytes(attempt_root) + _tree_bytes(
            terminal_private
        )
        _require(
            projected_publication_bytes <= MAXIMUM_RESTRICTED_STORAGE_BYTES,
            "official terminal publication exceeds storage ceiling",
        )
        peak_bytes = max(peak_bytes, projected_publication_bytes)
        terminal = _copy_terminal(terminal_private, attempt_root / "terminal")
        base._cleanup(private)
        usage, peak_bytes = _resource_snapshot(
            started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
        )
        _attempt_receipt(
            attempt_root=attempt_root,
            terminal=terminal,
            claim_sha256=claim_sha,
            resource_usage=usage,
        )
        _require(
            {path.name for path in attempt_root.iterdir()}
            == {"attempt_claim.json", "receipt", "terminal"},
            "final attempt file set differs",
        )
        base._readonly(attempt_root)
        return terminal
    except compiler.MapLightExecutionUnderpowered as error:
        base._cleanup(private)
        terminal = cast(
            Path,
            base.publish_files(
                attempt_root / "terminal",
                {
                    "preflight.json": base.json_bytes(error.preflight),
                    "manifest.json": base.json_bytes(
                        {
                            "schema_version": (
                                "cypshift.openadmet_cyp_2026.global_v2_g1_execution_terminal.v1"
                            ),
                            "status": "G2_3_G1_UNDERPOWERED",
                            "synthetic": False,
                            "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
                            "consumed_claim_sha256": claim_sha,
                            "runtime": runtime,
                            "accounting": error.preflight["accounting"],
                            "authority": _authority(False, "terminal"),
                        }
                    ),
                },
            ),
        )
        usage, peak_bytes = _resource_snapshot(
            started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
        )
        _attempt_receipt(
            attempt_root=attempt_root,
            terminal=terminal,
            claim_sha256=claim_sha,
            resource_usage=usage,
        )
        base._readonly(attempt_root)
        return terminal
    except BaseException as error:
        base._cleanup(private)
        base._cleanup(attempt_root / ".terminal-staging")
        category = type(error).__name__
        try:
            terminal = _failure_terminal(
                attempt_root=attempt_root,
                claim_sha256=claim_sha,
                runtime=runtime,
                category=category,
            )
            usage, peak_bytes = _resource_snapshot(
                started=started, attempt_root=attempt_root, peak_bytes=peak_bytes
            )
            _attempt_receipt(
                attempt_root=attempt_root,
                terminal=terminal,
                claim_sha256=claim_sha,
                resource_usage=usage,
            )
        finally:
            base._readonly(attempt_root)
        return terminal


__all__ = [
    "G1ExecutionWrapperError",
    "OFFICIAL_ATTEMPT_ROOT",
    "SCRIPT",
    "deterministic_test_predictor",
    "derive_consumed_claim",
    "real_predictor",
    "run_compiled_replay",
    "run_official_attempt",
    "run_runtime_probes",
]


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path, default=compiler.OFFICIAL_SOURCE_ROOT
    )
    parser.add_argument(
        "--baseline-terminal-root",
        type=Path,
        default=compiler.OFFICIAL_BASELINE_ROOT,
    )
    parser.add_argument("--attempt-root", type=Path, default=OFFICIAL_ATTEMPT_ROOT)
    parser.add_argument("--tracked-claim", type=Path, default=compiler.TRACKED_CLAIM)
    parser.add_argument("--acceptance", type=Path, default=TRACKED_ACCEPTANCE)
    args = parser.parse_args()
    terminal = run_official_attempt(
        source_root=args.source_root,
        baseline_terminal_root=args.baseline_terminal_root,
        attempt_root=args.attempt_root,
        tracked_claim_path=args.tracked_claim,
        acceptance_path=args.acceptance,
    )
    manifest, _raw = base._load_json(terminal / "manifest.json")
    print(manifest["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
