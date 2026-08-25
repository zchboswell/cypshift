#!/usr/bin/env python3
"""Execute the fixed EXP-G3 expert through least-privilege capabilities."""

from __future__ import annotations

import csv
import importlib.metadata
import math
import os
import platform
import resource
import sys
import time
import warnings
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import g3_execution_compiler as compiler
import g3_runner as g3
import numpy as np

sys.path.insert(0, str(g3.ROOT / "src"))
from cypshift.openadmet_global_v2_metric import (  # noqa: E402
    PredictionRow,
    TruthRow,
    tutorial_endpoint_st_rae,
)

SCRIPT: Final = Path(__file__).resolve()
OFFICIAL_ATTEMPT_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-6t-g3-development-attempt-1"
)
SYSTEM_ID: Final = g3.SYSTEM_ID
BASELINE_ID: Final = "FIXED-MAPL-DEVELOPMENT-OOF"
PREDICTION_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "similarity_component_hash",
    "repeat_seed",
    "outer_fold",
    "prediction",
    "fit_id",
)
FIT_COLUMNS: Final = (
    "fit_id",
    "repeat_seed",
    "outer_fold",
    "endpoint",
    "training_components_sha256",
    "validation_components_sha256",
    "training_target_rows",
    "validation_prediction_rows",
    "parameter_receipt_sha256",
)
REPEAT_COLUMNS: Final = (
    "system_id",
    "repeat_seed",
    "tutorial_macro_st_rae",
    "component_macro_mae",
    "tutorial_rows",
    "finite_rows",
)
OUTER_CELL_COLUMNS: Final = (
    "repeat_seed",
    "outer_fold",
    "candidate_component_macro_mae",
    "baseline_component_macro_mae",
    "candidate_minus_baseline",
    "favorable",
)
ENDPOINT_COLUMNS: Final = (
    "endpoint",
    "candidate_component_mae",
    "baseline_component_mae",
    "baseline_minus_candidate",
    "degradation",
    "targeted",
    "targeted_gate_pass",
)
TERMINAL_NAMES: Final = (
    "g3_repeat_metrics.csv",
    "g3_outer_cell_metrics.csv",
    "g3_endpoint_metrics.csv",
    "g3_bootstrap_summary.json",
    "g3_result.json",
    "manifest.json",
)
FORBIDDEN_COUNTERS: Final = (
    "official_metric_evaluations",
    "confirmatory_truth_values_opened",
    "historical_r3c_row_level_artifacts_opened",
    "blinded_test_files_opened",
    "tdi_files_opened",
    "external_records_acquired",
    "submissions_created",
    "leaderboard_observations_used_for_selection",
    "live_uploads",
)
Predictor = Callable[
    [str, np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]],
    tuple[np.ndarray[Any, Any], str],
]


class G3ExecutionWrapperError(RuntimeError):
    """A fit, prediction-freeze, scoring, or attempt invariant failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise G3ExecutionWrapperError(message)


def _float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise G3ExecutionWrapperError(f"{label} is not numeric") from error
    require(
        math.isfinite(result) and value == format(result, ".17g"),
        f"{label} is nonfinite or noncanonical",
    )
    return result


def _runtime_identity() -> dict[str, str]:
    observed = {
        "platform": f"{platform.system()} {platform.machine()} CPU",
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "rdkit": importlib.metadata.version("rdkit"),
        "lightgbm": importlib.metadata.version("lightgbm"),
    }
    require(
        observed
        == {
            "platform": "Linux x86_64 CPU",
            "python": "3.12.3",
            "numpy": "2.5.2",
            "scipy": "1.18.0",
            "rdkit": "2026.3.5",
            "lightgbm": "4.7.0",
        },
        f"locked runtime differs: {observed}",
    )
    return observed


def _authority(synthetic: bool, stage: str) -> dict[str, bool]:
    require(stage in {"model", "scorer", "terminal"}, "authority stage differs")
    authority = {
        name: False
        for name in (
            "official_target_access",
            "official_feature_access",
            "official_baseline_prediction_access",
            "official_model_fitting",
            "official_prediction_generation",
            "development_metric_evaluation",
            "official_metric_evaluation",
            "confirmatory_truth_access",
            "historical_row_level_access",
            "blinded_test_access",
            "tdi_access",
            "external_record_acquisition",
            "submission_generation",
            "leaderboard_selection",
            "live_upload",
        )
    }
    if not synthetic:
        if stage in {"model", "terminal"}:
            authority["official_target_access"] = True
            authority["official_feature_access"] = True
            authority["official_model_fitting"] = True
            authority["official_prediction_generation"] = True
        if stage in {"scorer", "terminal"}:
            authority["official_baseline_prediction_access"] = True
            authority["development_metric_evaluation"] = True
    return authority


def real_predictor(
    _endpoint: str,
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    """Fit the exact D-116 LightGBM identity without validation capability."""

    import lightgbm as lgb

    require(
        training.ndim == prediction.ndim == 2
        and training.shape[1] == prediction.shape[1] == g3.FEATURE_WIDTH
        and targets.shape == (len(training),)
        and len(training) > 0
        and len(prediction) > 0
        and not np.isinf(training).any()
        and not np.isinf(prediction).any()
        and np.isfinite(targets).all(),
        "real predictor capability differs",
    )
    parameters = g3.model_parameters()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dataset = lgb.Dataset(training, label=targets, free_raw_data=True)
        booster = lgb.train(parameters, dataset, num_boost_round=g3.NUM_BOOST_ROUND)
        values = np.asarray(booster.predict(prediction), dtype=np.float64)
    require(not caught, f"LightGBM emitted {len(caught)} Python warnings")
    require(
        values.shape == (len(prediction),) and np.isfinite(values).all(),
        "LightGBM prediction differs",
    )
    resolved = {
        name: value.item() if isinstance(value, np.generic) else value
        for name, value in booster.params.items()
        if name in parameters
    }
    require(
        resolved == parameters and booster.current_iteration() == g3.NUM_BOOST_ROUND,
        "resolved parameters differ",
    )
    receipt = {"num_boost_round": g3.NUM_BOOST_ROUND, "parameters": resolved}
    receipt_sha = g3.sha256_bytes(g3.json_bytes(receipt))
    require(
        receipt_sha == g3.parameter_receipt()["sha256"],
        "prospective parameter receipt differs",
    )
    return values, receipt_sha


def deterministic_test_predictor(
    endpoint: str,
    _training: np.ndarray[Any, Any],
    _targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    """Full-topology model double with no validation-truth capability."""

    require(endpoint in g3.ENDPOINTS, "model-double endpoint differs")
    values = prediction[:, g3.MORGAN_WIDTH].astype(np.float64).copy()
    values += 0.25 * g3.ENDPOINTS.index(endpoint)
    require(np.isfinite(values).all(), "model-double prediction is nonfinite")
    return values, cast(str, g3.parameter_receipt()["sha256"])


def run_runtime_control() -> dict[str, object]:
    """Run one bounded exact 1,500-tree D-118-engine control."""

    runtime = _runtime_identity()
    train, prediction, targets = g3.probe_matrix(reverse_physical=False)
    values, parameter_sha = real_predictor("CYP1A2", train, targets[:, 0], prediction)
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_runtime_control.v1",
        "runtime": runtime,
        "accepted_g3_runner_sha256": g3.sha256_path(g3.SCRIPT),
        "parameter_receipt_sha256": parameter_sha,
        "training_rows": len(train),
        "prediction_rows": len(prediction),
        "columns": train.shape[1],
        "num_boost_round": g3.NUM_BOOST_ROUND,
        "prediction_sha256": g3.sha256_bytes(g3.little_f8_bytes(values)),
        "finite_predictions": int(np.isfinite(values).sum()),
        "model_quality_authority": False,
        "resource_projection_authority": False,
    }


def _read_csv(path: Path, columns: Sequence[str]) -> list[dict[str, str]]:
    require(
        path.exists() and path.is_file() and not path.is_symlink(),
        f"CSV differs: {path.name}",
    )
    try:
        reader = csv.DictReader(path.open(encoding="utf-8", newline=""))
        require(
            tuple(reader.fieldnames or ()) == tuple(columns),
            f"CSV columns differ: {path.name}",
        )
        rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise G3ExecutionWrapperError(f"CSV decoding differs: {path.name}") from error
    require(all(None not in row for row in rows), f"CSV row width differs: {path.name}")
    return rows


def _load_model(
    root: Path,
) -> tuple[
    dict[str, Any],
    list[str],
    dict[str, str],
    dict[tuple[str, int], int],
    np.ndarray[Any, Any],
]:
    compiler._readonly_root(root, "G3 model capability")
    manifest = compiler._load_json(root / "manifest.json")
    synthetic = manifest.get("synthetic")
    require(
        manifest.get("schema_version") == compiler.MODEL_SCHEMA
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("tracked_claim_sha256") == compiler.TRACKED_CLAIM_SHA256
        and manifest.get("accepted_g3_runner_sha256") == g3.sha256_path(g3.SCRIPT)
        and manifest.get("compiler_source_sha256") == g3.sha256_path(compiler.SCRIPT)
        and isinstance(synthetic, bool)
        and manifest.get("authority") == _authority(synthetic, "model"),
        "model capability identity differs",
    )
    features = _read_csv(root / "feature_rows.csv", compiler.FEATURE_COLUMNS)
    folds = _read_csv(root / "folds.csv", compiler.FOLD_COLUMNS)
    molecules = [row["molecule_id"] for row in features]
    require(
        molecules == sorted(molecules) and len(molecules) == len(set(molecules)),
        "model molecule order differs",
    )
    components = {
        row["molecule_id"]: row["similarity_component_hash"] for row in features
    }
    fold_index: dict[tuple[str, int], int] = {}
    for row in folds:
        key = row["molecule_id"], int(row["repeat_seed"])
        require(
            key not in fold_index
            and row["molecule_id"] in components
            and row["similarity_component_hash"] == components[row["molecule_id"]]
            and int(row["repeat_seed"]) in g3.REPEAT_SEEDS
            and int(row["outer_fold"]) in g3.OUTER_FOLDS,
            "model fold identity differs",
        )
        fold_index[key] = int(row["outer_fold"])
    require(len(fold_index) == len(molecules) * 3, "model fold topology differs")
    matrix = np.load(root / "features.npy", allow_pickle=False)
    require(
        g3.sha256_path(root / "features.npy") == manifest["feature_array_sha256"]
        and matrix.shape == (len(molecules), g3.FEATURE_WIDTH)
        and matrix.dtype == np.dtype("float64")
        and matrix.flags.c_contiguous
        and not np.isinf(matrix).any(),
        "model feature array differs",
    )
    return manifest, molecules, components, fold_index, matrix


def _target_path(root: Path, repeat_seed: int, outer: int, endpoint: str) -> Path:
    return root / "targets" / str(repeat_seed) / f"outer-{outer}" / f"{endpoint}.csv"


def run_models(
    *,
    model_capability_root: Path,
    output_root: Path,
    predictor: Predictor = real_predictor,
) -> Path:
    """Run all sixty fits and atomically freeze complete candidate OOF rows."""

    require(
        not output_root.exists() and not output_root.is_symlink(),
        "candidate output exists",
    )
    manifest, molecules, components, folds, matrix = _load_model(model_capability_root)
    index = {molecule: position for position, molecule in enumerate(molecules)}
    feature_sha = cast(str, manifest["feature_array_sha256"])
    parameter_sha = cast(str, g3.parameter_receipt()["sha256"])
    fit_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    for repeat_seed in g3.REPEAT_SEEDS:
        for outer in g3.OUTER_FOLDS:
            training_ids = sorted(
                molecule
                for molecule in molecules
                if folds[molecule, repeat_seed] != outer
            )
            prediction_ids = sorted(
                molecule
                for molecule in molecules
                if folds[molecule, repeat_seed] == outer
            )
            training_components = sorted(
                {components[molecule] for molecule in training_ids}
            )
            prediction_components = sorted(
                {components[molecule] for molecule in prediction_ids}
            )
            require(
                training_ids
                and prediction_ids
                and not set(training_components) & set(prediction_components),
                "fit family boundary differs",
            )
            for endpoint in g3.ENDPOINTS:
                target_path = _target_path(
                    model_capability_root, repeat_seed, outer, endpoint
                )
                target_rows = _read_csv(target_path, compiler.TARGET_COLUMNS)
                require(
                    g3.sha256_path(target_path)
                    == manifest["target_receipts"][
                        target_path.relative_to(model_capability_root).as_posix()
                    ],
                    "target capability receipt differs",
                )
                target_map = {
                    row["molecule_id"]: _float(row["point"], "training target")
                    for row in target_rows
                }
                fitted = sorted(target_map)
                require(
                    len(fitted) == len(target_map)
                    and set(fitted) <= set(training_ids)
                    and not set(fitted) & set(prediction_ids),
                    "training target scope differs",
                )
                identity = [
                    "cypshift.openadmet_cyp_2026.g3_execution_fit_identity.v1",
                    SYSTEM_ID,
                    repeat_seed,
                    outer,
                    endpoint,
                    training_components,
                    prediction_components,
                    feature_sha,
                    parameter_sha,
                ]
                fit_id = g3.sha256_bytes(g3.json_bytes(identity))
                values, resolved_sha = predictor(
                    endpoint,
                    matrix[[index[molecule] for molecule in fitted]],
                    np.asarray(
                        [target_map[molecule] for molecule in fitted], dtype=np.float64
                    ),
                    matrix[[index[molecule] for molecule in prediction_ids]],
                )
                require(
                    values.shape == (len(prediction_ids),)
                    and np.isfinite(values).all()
                    and resolved_sha == parameter_sha,
                    "fit result differs",
                )
                fit_rows.append(
                    {
                        "fit_id": fit_id,
                        "repeat_seed": repeat_seed,
                        "outer_fold": outer,
                        "endpoint": endpoint,
                        "training_components_sha256": g3.sha256_bytes(
                            g3.json_bytes(training_components)
                        ),
                        "validation_components_sha256": g3.sha256_bytes(
                            g3.json_bytes(prediction_components)
                        ),
                        "training_target_rows": len(fitted),
                        "validation_prediction_rows": len(prediction_ids),
                        "parameter_receipt_sha256": resolved_sha,
                    }
                )
                prediction_rows.extend(
                    {
                        "molecule_id": molecule,
                        "endpoint": endpoint,
                        "similarity_component_hash": components[molecule],
                        "repeat_seed": repeat_seed,
                        "outer_fold": outer,
                        "prediction": format(float(value), ".17g"),
                        "fit_id": fit_id,
                    }
                    for molecule, value in zip(prediction_ids, values, strict=True)
                )
    fit_rows.sort(
        key=lambda row: (
            int(row["repeat_seed"]),
            int(row["outer_fold"]),
            str(row["endpoint"]),
        )
    )
    prediction_rows.sort(
        key=lambda row: tuple(str(row[name]) for name in PREDICTION_COLUMNS[:5])
    )
    expected_predictions = len(molecules) * len(g3.ENDPOINTS) * len(g3.REPEAT_SEEDS)
    require(
        len(fit_rows) == len({row["fit_id"] for row in fit_rows}) == 60
        and len(prediction_rows) == expected_predictions,
        "candidate topology differs",
    )
    prediction_bytes = g3.csv_bytes(PREDICTION_COLUMNS, prediction_rows)
    fit_bytes = g3.csv_bytes(FIT_COLUMNS, fit_rows)
    candidate_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_candidate_freeze.v1",
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "model_capability_manifest_sha256": g3.sha256_path(
            model_capability_root / "manifest.json"
        ),
        "synthetic": manifest["synthetic"],
        "predictions_frozen_before_scorer_access": True,
        "fit_receipts_sha256": g3.sha256_bytes(fit_bytes),
        "outer_predictions_sha256": g3.sha256_bytes(prediction_bytes),
        "fits": 60,
        "outer_prediction_rows": len(prediction_rows),
        "parameter_receipt_sha256": parameter_sha,
        "warnings": 0,
        "fallbacks": 0,
        "nonzero_exits": 0,
        "authority": _authority(bool(manifest["synthetic"]), "model"),
    }
    return compiler._publish_files(
        output_root,
        {
            "fit_receipts.csv": fit_bytes,
            "g3_outer_predictions.csv": prediction_bytes,
            "manifest.json": g3.json_bytes(candidate_manifest),
        },
    )


def _load_scorer(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    compiler._readonly_root(root, "G3 scorer capability")
    manifest = compiler._load_json(root / "manifest.json")
    synthetic = manifest.get("synthetic")
    require(
        manifest.get("schema_version") == compiler.SCORER_SCHEMA
        and isinstance(synthetic, bool)
        and manifest.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and manifest.get("authority") == _authority(synthetic, "scorer"),
        "scorer capability identity differs",
    )
    truth = _read_csv(root / "outer_truth.csv", compiler.TRUTH_COLUMNS)
    require(
        g3.sha256_path(root / "outer_truth.csv") == manifest["outer_truth_sha256"],
        "scorer truth receipt differs",
    )
    return manifest, truth


def _baseline_after_prediction_freeze(
    *,
    baseline_terminal_root: Path,
    scorer_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
) -> list[dict[str, str]]:
    require(
        candidate_manifest.get("predictions_frozen_before_scorer_access") is True,
        "candidate is not frozen",
    )
    baseline = scorer_manifest.get("baseline")
    require(isinstance(baseline, Mapping), "baseline capability differs")
    metadata = cast(Mapping[str, object], baseline)
    root = baseline_terminal_root
    compiler._readonly_root(root, "fixed baseline terminal")
    manifest_path = compiler._regular(root / "manifest.json", "baseline manifest")
    prediction_path = compiler._regular(
        root / "development_outer_oof.csv", "baseline predictions"
    )
    require(
        g3.sha256_path(manifest_path) == metadata["manifest_sha256"]
        and g3.sha256_path(prediction_path) == metadata["outer_oof_sha256"],
        "baseline receipt differs",
    )
    baseline_manifest = compiler._load_json(manifest_path)
    require(
        baseline_manifest.get("synthetic") is scorer_manifest["synthetic"],
        "baseline mode differs",
    )
    return _read_csv(prediction_path, compiler.BASELINE_COLUMNS)


def _component_mae(rows: Sequence[tuple[str, float]]) -> tuple[float, int, int]:
    residuals: dict[str, list[float]] = defaultdict(list)
    for component, residual in rows:
        require(math.isfinite(residual), "component residual is nonfinite")
        residuals[component].append(residual)
    require(bool(residuals), "component metric population is empty")
    values = [
        math.fsum(items) / len(items) for _component, items in sorted(residuals.items())
    ]
    return (
        math.fsum(values) / len(values),
        sum(map(len, residuals.values())),
        len(values),
    )


def _linear_quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    require(bool(ordered) and 0 <= probability <= 1, "bootstrap quantile input differs")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _paired_bootstrap(
    paired: Sequence[Mapping[str, object]], components: Sequence[str]
) -> dict[str, object]:
    errors: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)
    for row in paired:
        component = str(row["similarity_component_hash"])
        endpoint = str(row["endpoint"])
        repeat_seed = int(row["repeat_seed"])
        errors["candidate", component, endpoint, repeat_seed].append(
            float(row["candidate_error"])
        )
        errors["baseline", component, endpoint, repeat_seed].append(
            float(row["baseline_error"])
        )
    rng = np.random.Generator(np.random.PCG64(20260827))
    accepted: list[float] = []
    attempts = 0
    while len(accepted) < 2000 and attempts < 20000:
        attempts += 1
        sampled = [
            components[int(index)]
            for index in rng.integers(0, len(components), size=len(components))
        ]
        system_values: dict[str, float] = {}
        valid = True
        for system in ("candidate", "baseline"):
            cells: list[float] = []
            for endpoint in g3.ENDPOINTS:
                for repeat_seed in g3.REPEAT_SEEDS:
                    component_values = [
                        math.fsum(errors[system, component, endpoint, repeat_seed])
                        / len(errors[system, component, endpoint, repeat_seed])
                        for component in sampled
                        if errors[system, component, endpoint, repeat_seed]
                    ]
                    if not component_values:
                        valid = False
                        break
                    cells.append(math.fsum(component_values) / len(component_values))
                if not valid:
                    break
            if not valid or len(cells) != 12:
                break
            system_values[system] = math.fsum(cells) / len(cells)
        if valid and len(system_values) == 2:
            difference = system_values["candidate"] - system_values["baseline"]
            if math.isfinite(difference):
                accepted.append(difference)
    require(len(accepted) == 2000, "bootstrap attempt exhaustion")
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_bootstrap.v1",
        "difference": "EXP-G3 component-macro MAE minus fixed MapLight component-macro MAE",
        "unit": "D-032 component shared across endpoints repeats and systems",
        "rng": "NumPy PCG64",
        "seed": 20260827,
        "accepted_replicates": len(accepted),
        "attempts": attempts,
        "maximum_attempts": 20000,
        "lower_95": _linear_quantile(accepted, 0.025),
        "median": _linear_quantile(accepted, 0.5),
        "upper_95": _linear_quantile(accepted, 0.975),
    }


def score_and_publish(
    *,
    candidate_root: Path,
    scorer_capability_root: Path,
    baseline_terminal_root: Path,
    output_root: Path,
) -> Path:
    """Open scorer truth/baseline only after the complete candidate freeze."""

    compiler._readonly_root(candidate_root, "frozen candidate")
    candidate_manifest = compiler._load_json(candidate_root / "manifest.json")
    require(
        candidate_manifest.get("predictions_frozen_before_scorer_access") is True,
        "prediction freeze differs",
    )
    candidate_rows = _read_csv(
        candidate_root / "g3_outer_predictions.csv", PREDICTION_COLUMNS
    )
    require(
        g3.sha256_path(candidate_root / "g3_outer_predictions.csv")
        == candidate_manifest["outer_predictions_sha256"]
        and candidate_manifest.get("fits") == 60,
        "candidate receipt differs",
    )
    scorer_manifest, truth_rows = _load_scorer(scorer_capability_root)
    require(
        candidate_manifest["synthetic"] is scorer_manifest["synthetic"],
        "candidate/scorer mode differs",
    )
    baseline_rows = _baseline_after_prediction_freeze(
        baseline_terminal_root=baseline_terminal_root,
        scorer_manifest=scorer_manifest,
        candidate_manifest=candidate_manifest,
    )
    candidate: dict[tuple[str, str, str, int, int], float] = {}
    for row in candidate_rows:
        key = (
            row["molecule_id"],
            row["endpoint"],
            row["similarity_component_hash"],
            int(row["repeat_seed"]),
            int(row["outer_fold"]),
        )
        require(key not in candidate, "candidate identity is duplicated")
        candidate[key] = _float(row["prediction"], "candidate prediction")
    baseline: dict[tuple[str, str, str, int, int], float] = {}
    for row in baseline_rows:
        repeat = int(row["repeat"])
        require(repeat in range(3), "baseline repeat differs")
        key = (
            row["molecule_id"],
            row["endpoint"],
            row["similarity_component_hash"],
            g3.REPEAT_SEEDS[repeat],
            int(row["outer_fold"]),
        )
        require(key not in baseline, "baseline identity is duplicated")
        baseline[key] = _float(row["prediction"], "baseline prediction")
    require(
        candidate.keys() == baseline.keys(),
        "candidate/baseline prediction identity differs",
    )
    truth: dict[tuple[str, str, str, int, int], dict[str, str]] = {}
    for row in truth_rows:
        key = (
            row["molecule_id"],
            row["endpoint"],
            row["similarity_component_hash"],
            int(row["repeat_seed"]),
            int(row["outer_fold"]),
        )
        require(key not in truth and key in candidate, "scorer truth identity differs")
        truth[key] = row
    require(truth.keys() == candidate.keys(), "truth/prediction topology differs")

    repeat_rows: list[dict[str, object]] = []
    endpoint_repeat_mae: dict[tuple[str, str, int], float] = {}
    tutorial_calls = 0
    paired: list[dict[str, object]] = []
    finite_truth = 0
    tutorial_truth = 0
    for system, predictions in ((SYSTEM_ID, candidate), (BASELINE_ID, baseline)):
        for repeat_seed in g3.REPEAT_SEEDS:
            tutorial_scores: list[float] = []
            component_scores: list[float] = []
            repeat_tutorial_rows = 0
            repeat_finite_rows = 0
            for endpoint in g3.ENDPOINTS:
                selected = [
                    (key, row)
                    for key, row in truth.items()
                    if key[1] == endpoint and key[3] == repeat_seed
                ]
                metric_truth = [
                    TruthRow(
                        key[0],
                        endpoint,
                        _float(row["point"], "tutorial point"),
                        _float(row["low"], "tutorial low"),
                        _float(row["high"], "tutorial high"),
                    )
                    for key, row in selected
                    if row["tutorial_eligible"] == "true"
                ]
                metric_predictions = [
                    PredictionRow(key[0], endpoint, predictions[key])
                    for key, row in selected
                    if row["tutorial_eligible"] == "true"
                ]
                score = tutorial_endpoint_st_rae(
                    metric_truth, metric_predictions, endpoint
                )
                tutorial_calls += 1
                tutorial_scores.append(score.value)
                repeat_tutorial_rows += score.eligible_rows
                residual_rows = [
                    (
                        key[2],
                        abs(predictions[key] - _float(row["point"], "component point")),
                    )
                    for key, row in selected
                    if row["point_eligible"] == "true"
                ]
                mae, eligible, _components = _component_mae(residual_rows)
                endpoint_repeat_mae[system, endpoint, repeat_seed] = mae
                component_scores.append(mae)
                repeat_finite_rows += eligible
            repeat_rows.append(
                {
                    "system_id": system,
                    "repeat_seed": repeat_seed,
                    "tutorial_macro_st_rae": format(
                        math.fsum(tutorial_scores) / 4, ".17g"
                    ),
                    "component_macro_mae": format(
                        math.fsum(component_scores) / 4, ".17g"
                    ),
                    "tutorial_rows": repeat_tutorial_rows,
                    "finite_rows": repeat_finite_rows,
                }
            )
    require(tutorial_calls == 24, "tutorial metric call count differs")

    for key, row in truth.items():
        if row["point_eligible"] != "true":
            continue
        point = _float(row["point"], "paired point")
        finite_truth += 1
        paired.append(
            {
                "molecule_id": key[0],
                "endpoint": key[1],
                "similarity_component_hash": key[2],
                "repeat_seed": key[3],
                "outer_fold": key[4],
                "candidate_error": abs(candidate[key] - point),
                "baseline_error": abs(baseline[key] - point),
            }
        )
        tutorial_truth += int(row["tutorial_eligible"] == "true")

    outer_rows: list[dict[str, object]] = []
    favorable = 0
    for repeat_seed in g3.REPEAT_SEEDS:
        for outer in g3.OUTER_FOLDS:
            values: dict[str, float] = {}
            for system, predictions in (
                ("candidate", candidate),
                ("baseline", baseline),
            ):
                endpoints: list[float] = []
                for endpoint in g3.ENDPOINTS:
                    residuals = [
                        (
                            key[2],
                            abs(predictions[key] - _float(row["point"], "cell point")),
                        )
                        for key, row in truth.items()
                        if key[1] == endpoint
                        and key[3] == repeat_seed
                        and key[4] == outer
                        and row["point_eligible"] == "true"
                    ]
                    endpoints.append(_component_mae(residuals)[0])
                values[system] = math.fsum(endpoints) / 4
            is_favorable = values["candidate"] < values["baseline"]
            favorable += int(is_favorable)
            outer_rows.append(
                {
                    "repeat_seed": repeat_seed,
                    "outer_fold": outer,
                    "candidate_component_macro_mae": format(
                        values["candidate"], ".17g"
                    ),
                    "baseline_component_macro_mae": format(values["baseline"], ".17g"),
                    "candidate_minus_baseline": format(
                        values["candidate"] - values["baseline"], ".17g"
                    ),
                    "favorable": "true" if is_favorable else "false",
                }
            )

    endpoint_rows: list[dict[str, object]] = []
    endpoint_improvements: dict[str, float] = {}
    for endpoint in g3.ENDPOINTS:
        candidate_value = (
            math.fsum(
                endpoint_repeat_mae[SYSTEM_ID, endpoint, seed]
                for seed in g3.REPEAT_SEEDS
            )
            / 3
        )
        baseline_value = (
            math.fsum(
                endpoint_repeat_mae[BASELINE_ID, endpoint, seed]
                for seed in g3.REPEAT_SEEDS
            )
            / 3
        )
        improvement = baseline_value - candidate_value
        endpoint_improvements[endpoint] = improvement
        targeted = endpoint in {"CYP1A2", "CYP2D6"}
        endpoint_rows.append(
            {
                "endpoint": endpoint,
                "candidate_component_mae": format(candidate_value, ".17g"),
                "baseline_component_mae": format(baseline_value, ".17g"),
                "baseline_minus_candidate": format(improvement, ".17g"),
                "degradation": format(max(-improvement, 0), ".17g"),
                "targeted": "true" if targeted else "false",
                "targeted_gate_pass": "true"
                if targeted and improvement >= 0.01
                else "false",
            }
        )
    components = sorted({str(row["similarity_component_hash"]) for row in paired})
    bootstrap = _paired_bootstrap(paired, components)
    candidate_repeat = [row for row in repeat_rows if row["system_id"] == SYSTEM_ID]
    baseline_repeat = [row for row in repeat_rows if row["system_id"] == BASELINE_ID]
    candidate_primary = (
        math.fsum(
            _float(str(row["tutorial_macro_st_rae"]), "candidate primary")
            for row in candidate_repeat
        )
        / 3
    )
    baseline_primary = (
        math.fsum(
            _float(str(row["tutorial_macro_st_rae"]), "baseline primary")
            for row in baseline_repeat
        )
        / 3
    )
    candidate_component = (
        math.fsum(
            _float(str(row["component_macro_mae"]), "candidate component")
            for row in candidate_repeat
        )
        / 3
    )
    baseline_component = (
        math.fsum(
            _float(str(row["component_macro_mae"]), "baseline component")
            for row in baseline_repeat
        )
        / 3
    )
    require(baseline_primary > 0, "baseline primary denominator is nonpositive")
    relative_primary = (baseline_primary - candidate_primary) / baseline_primary
    absolute_component = baseline_component - candidate_component
    gates = {
        "relative_primary_improvement": relative_primary >= 0.03,
        "absolute_component_mae_improvement": absolute_component >= 0.015,
        "paired_component_mae_upper_95_below_zero": float(bootstrap["upper_95"]) < 0,
        "favorable_outer_cells": favorable >= 8,
        "endpoint_harm": max(-value for value in endpoint_improvements.values())
        <= 0.015,
        "targeted_endpoint_improvement": any(
            endpoint_improvements[name] >= 0.01 for name in ("CYP1A2", "CYP2D6")
        ),
    }
    result = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_result.v1",
        "status": "G2_6T_G3_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
        if scorer_manifest["synthetic"]
        else ("G2_6R_G3_ACCEPTED" if all(gates.values()) else "G2_6R_G3_REJECTED"),
        "synthetic": scorer_manifest["synthetic"],
        "candidate_primary": candidate_primary,
        "baseline_primary": baseline_primary,
        "relative_primary_improvement": relative_primary,
        "candidate_component_macro_mae": candidate_component,
        "baseline_component_macro_mae": baseline_component,
        "absolute_component_mae_improvement": absolute_component,
        "favorable_outer_cells": favorable,
        "endpoint_improvements": endpoint_improvements,
        "promotion_gates": gates,
        "all_promotion_gates_pass": all(gates.values()),
        "tutorial_metric_calls": tutorial_calls,
        "metric_name_boundary": "Pinned local tutorial diagnostic; not an official challenge score.",
    }
    repeat_bytes = g3.csv_bytes(REPEAT_COLUMNS, repeat_rows)
    outer_bytes = g3.csv_bytes(OUTER_CELL_COLUMNS, outer_rows)
    endpoint_bytes = g3.csv_bytes(ENDPOINT_COLUMNS, endpoint_rows)
    bootstrap_bytes = g3.json_bytes(bootstrap)
    result_bytes = g3.json_bytes(result)
    terminal_files = {
        TERMINAL_NAMES[0]: repeat_bytes,
        TERMINAL_NAMES[1]: outer_bytes,
        TERMINAL_NAMES[2]: endpoint_bytes,
        TERMINAL_NAMES[3]: bootstrap_bytes,
        TERMINAL_NAMES[4]: result_bytes,
    }
    hashes = {name: g3.sha256_bytes(value) for name, value in terminal_files.items()}
    accounting = {
        "synthetic_model_fits": 60 if scorer_manifest["synthetic"] else 0,
        "synthetic_predictions": len(candidate_rows)
        if scorer_manifest["synthetic"]
        else 0,
        "official_model_fits": 0 if scorer_manifest["synthetic"] else 60,
        "official_predictions_generated": 0
        if scorer_manifest["synthetic"]
        else len(candidate_rows),
        "development_metric_evaluations": 0 if scorer_manifest["synthetic"] else 1,
        "tutorial_metric_calls": tutorial_calls,
        "finite_paired_rows": finite_truth,
        "tutorial_paired_rows": tutorial_truth,
        "baseline_prediction_rows_opened_after_freeze": len(baseline_rows),
        **{name: 0 for name in FORBIDDEN_COUNTERS},
    }
    terminal_manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_terminal_manifest.v1",
        "status": result["status"],
        "synthetic": scorer_manifest["synthetic"],
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "compiler_source_sha256": g3.sha256_path(compiler.SCRIPT),
        "execution_wrapper_source_sha256": g3.sha256_path(SCRIPT),
        "candidate_manifest_sha256": g3.sha256_path(candidate_root / "manifest.json"),
        "scorer_manifest_sha256": g3.sha256_path(
            scorer_capability_root / "manifest.json"
        ),
        "relative_files": hashes,
        "deterministic_tree_sha256": g3.sha256_bytes(g3.json_bytes(hashes)),
        "counts": {
            "development_molecules": len(candidate_rows) // 12,
            "model_fits": 60,
            "candidate_outer_prediction_rows": len(candidate_rows),
            "baseline_outer_prediction_rows": len(baseline_rows),
            "tutorial_metric_calls": tutorial_calls,
            "bootstrap_accepted_replicates": bootstrap["accepted_replicates"],
        },
        "accounting": accounting,
        "authority": _authority(bool(scorer_manifest["synthetic"]), "terminal"),
        "scientific_interpretation": "Official-shaped synthetic mechanics only; no model-quality interpretation."
        if scorer_manifest["synthetic"]
        else "Frozen family-safe development evidence only; confirmatory and official metric remain closed.",
    }
    terminal_files[TERMINAL_NAMES[5]] = g3.json_bytes(terminal_manifest)
    return compiler._publish_files(output_root, terminal_files)


def run_compiled_replay(
    *,
    model_capability_root: Path,
    scorer_capability_root: Path,
    baseline_terminal_root: Path,
    work_root: Path,
    predictor: Predictor = real_predictor,
) -> Path:
    require(
        not work_root.exists() and not work_root.is_symlink(),
        "execution work root exists",
    )
    work_root.mkdir(parents=True)
    try:
        candidate = run_models(
            model_capability_root=model_capability_root,
            output_root=work_root / "candidate-freeze",
            predictor=predictor,
        )
        return score_and_publish(
            candidate_root=candidate,
            scorer_capability_root=scorer_capability_root,
            baseline_terminal_root=baseline_terminal_root,
            output_root=work_root / "terminal",
        )
    except BaseException:
        compiler._cleanup(work_root)
        raise


def derive_consumed_claim() -> dict[str, Any]:
    """Derive the only valid private claim without mutating its tracked template."""

    require(
        g3.sha256_path(compiler.TRACKED_CLAIM) == compiler.TRACKED_CLAIM_SHA256,
        "tracked claim differs",
    )
    acceptance = compiler._load_json(compiler.TRACKED_ACCEPTANCE)
    require(
        acceptance.get("status") == "G2_6T_G3_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED"
        and acceptance.get("execution_contract_sha256")
        == compiler.EXECUTION_CONTRACT_SHA256
        and acceptance.get("official_compiler_source_sha256")
        == g3.sha256_path(compiler.SCRIPT)
        and acceptance.get("execution_wrapper_source_sha256") == g3.sha256_path(SCRIPT)
        and acceptance.get("official_shaped_synthetic_driver_source_sha256")
        == g3.sha256_path(compiler.OFFICIAL_SYNTHETIC_DRIVER),
        "official-shaped synthetic acceptance differs",
    )
    template = compiler._load_json(compiler.TRACKED_CLAIM)
    result = dict(template)
    result.update(
        {
            "future_official_compiler_source_sha256": g3.sha256_path(compiler.SCRIPT),
            "future_execution_wrapper_source_sha256": g3.sha256_path(SCRIPT),
            "future_official_shaped_synthetic_driver_source_sha256": g3.sha256_path(
                compiler.OFFICIAL_SYNTHETIC_DRIVER
            ),
            "future_official_shaped_synthetic_acceptance_sha256": g3.sha256_path(
                compiler.TRACKED_ACCEPTANCE
            ),
        }
    )
    compiler.validate_consumed_claim(result)
    return result


def consume_claim(*, attempt_root: Path) -> Path:
    """Atomically consume the sole claim through no-replace root creation."""

    claim = derive_consumed_claim()
    require(
        not attempt_root.exists() and not attempt_root.is_symlink(),
        "attempt root exists",
    )
    attempt_root.mkdir(parents=True)
    path = attempt_root / "attempt_claim.json"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        try:
            os.write(descriptor, g3.json_bytes(claim))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        path.chmod(0o400)
        return path
    except BaseException:
        compiler._cleanup(attempt_root)
        raise


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _status_terminal_files(
    *,
    status: str,
    failure_type: str | None,
    preflight: Mapping[str, object] | None,
    completed_fits: int,
    completed_predictions: int,
) -> dict[str, bytes]:
    require(
        status in {"G2_6R_G3_FAILED", "G2_6R_G3_UNDERPOWERED"},
        "non-scientific terminal status differs",
    )
    terminal_files = {
        TERMINAL_NAMES[0]: g3.csv_bytes(REPEAT_COLUMNS, []),
        TERMINAL_NAMES[1]: g3.csv_bytes(OUTER_CELL_COLUMNS, []),
        TERMINAL_NAMES[2]: g3.csv_bytes(ENDPOINT_COLUMNS, []),
        TERMINAL_NAMES[3]: g3.json_bytes(
            {
                "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_bootstrap.v1",
                "status": status,
                "accepted_replicates": 0,
                "attempts": 0,
            }
        ),
        TERMINAL_NAMES[4]: g3.json_bytes(
            {
                "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_result.v1",
                "status": status,
                "synthetic": False,
                "failure_type": failure_type,
                "preflight": dict(preflight) if preflight is not None else None,
                "promotion_gates": {
                    "relative_primary_improvement": False,
                    "absolute_component_mae_improvement": False,
                    "paired_component_mae_upper_95_below_zero": False,
                    "favorable_outer_cells": False,
                    "endpoint_harm": False,
                    "targeted_endpoint_improvement": False,
                },
                "all_promotion_gates_pass": False,
                "metric_name_boundary": "No model-quality result was produced.",
            }
        ),
    }
    hashes = {name: g3.sha256_bytes(value) for name, value in terminal_files.items()}
    accounting = {
        "synthetic_model_fits": 0,
        "synthetic_predictions": 0,
        "official_model_fits": completed_fits,
        "official_predictions_generated": completed_predictions,
        "development_metric_evaluations": 0,
        "tutorial_metric_calls": 0,
        "finite_paired_rows": 0,
        "tutorial_paired_rows": 0,
        "baseline_prediction_rows_opened_after_freeze": 0,
        **{name: 0 for name in FORBIDDEN_COUNTERS},
    }
    terminal_files[TERMINAL_NAMES[5]] = g3.json_bytes(
        {
            "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_terminal_manifest.v1",
            "status": status,
            "synthetic": False,
            "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
            "compiler_source_sha256": g3.sha256_path(compiler.SCRIPT),
            "execution_wrapper_source_sha256": g3.sha256_path(SCRIPT),
            "relative_files": hashes,
            "deterministic_tree_sha256": g3.sha256_bytes(g3.json_bytes(hashes)),
            "counts": {
                "development_molecules": 0,
                "model_fits": completed_fits,
                "candidate_outer_prediction_rows": completed_predictions,
                "baseline_outer_prediction_rows": 0,
                "tutorial_metric_calls": 0,
                "bootstrap_accepted_replicates": 0,
            },
            "accounting": accounting,
            "authority": _authority(False, "terminal"),
            "scientific_interpretation": "Terminal failure or underpowered evidence only; no model-quality result.",
        }
    )
    return terminal_files


def _write_readonly_no_replace(path: Path, value: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(descriptor, value)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    path.chmod(0o400)


def _lock_attempt_root(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def run_official_attempt() -> Path:
    """Consume and execute the sole official attempt; never retry or resume."""

    require(
        OFFICIAL_ATTEMPT_ROOT.name == "g2-6t-g3-development-attempt-1",
        "unsafe attempt root",
    )
    runtime = _runtime_identity()
    claim_path = consume_claim(attempt_root=OFFICIAL_ATTEMPT_ROOT)
    work = OFFICIAL_ATTEMPT_ROOT / ".work"
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    status = "G2_6R_G3_FAILED"
    failure_type: str | None = None
    preflight: dict[str, object] | None = None
    completed_fits = 0
    completed_predictions = 0
    terminal_files: dict[str, bytes] | None = None

    def counting_predictor(
        endpoint: str,
        training: np.ndarray[Any, Any],
        targets: np.ndarray[Any, Any],
        prediction: np.ndarray[Any, Any],
    ) -> tuple[np.ndarray[Any, Any], str]:
        nonlocal completed_fits, completed_predictions
        values, receipt_sha = real_predictor(endpoint, training, targets, prediction)
        completed_fits += 1
        completed_predictions += len(values)
        return values, receipt_sha

    try:
        model, scorer, observed_preflight = compiler.compile_capabilities(
            source_root=compiler.OFFICIAL_SOURCE_ROOT,
            baseline_terminal_root=compiler.OFFICIAL_BASELINE_ROOT,
            output_root=work / "capabilities",
            expected_compiler_sha256=g3.sha256_path(compiler.SCRIPT),
            mode="official",
            consumed_claim_path=claim_path,
        )
        preflight = observed_preflight
        terminal = run_compiled_replay(
            model_capability_root=model,
            scorer_capability_root=scorer,
            baseline_terminal_root=compiler.OFFICIAL_BASELINE_ROOT,
            work_root=work / "execution",
            predictor=counting_predictor,
        )
        result = compiler._load_json(terminal / "g3_result.json")
        status = cast(str, result["status"])
        require(
            status in {"G2_6R_G3_REJECTED", "G2_6R_G3_ACCEPTED"},
            "scientific terminal status differs",
        )
        terminal_files = {
            name: compiler._regular(terminal / name, f"terminal {name}").read_bytes()
            for name in TERMINAL_NAMES
        }
        wall_hours = (time.perf_counter() - started_wall) / 3600
        cpu_hours = (time.process_time() - started_cpu) / 3600
        peak_rss_gib = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / (1024**3)
        )
        storage_gb = (
            _tree_bytes(work) + _tree_bytes(compiler.SCRIPT.parent / ".venv")
        ) / 1_000_000_000
        require(
            wall_hours <= 24
            and cpu_hours <= 160
            and peak_rss_gib <= 24
            and storage_gb <= 32,
            "official resource ceiling exceeded",
        )
    except compiler.G3ExecutionUnderpowered as error:
        status = "G2_6R_G3_UNDERPOWERED"
        preflight = error.preflight
        failure_type = type(error).__name__
    except BaseException as error:
        status = "G2_6R_G3_FAILED"
        failure_type = type(error).__name__
    finally:
        compiler._cleanup(work)
    require(not work.exists(), "official private cleanup differs")
    wall_hours = (time.perf_counter() - started_wall) / 3600
    cpu_hours = (time.process_time() - started_cpu) / 3600
    peak_rss_gib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / (1024**3)
    storage_gb = _tree_bytes(compiler.SCRIPT.parent / ".venv") / 1_000_000_000
    if terminal_files is None:
        terminal_files = _status_terminal_files(
            status=status,
            failure_type=failure_type,
            preflight=preflight,
            completed_fits=completed_fits,
            completed_predictions=completed_predictions,
        )
    published = compiler._publish_files(
        OFFICIAL_ATTEMPT_ROOT / "terminal", terminal_files
    )
    receipt = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_execution_attempt_receipt.v1",
        "status": status,
        "claim_sha256": g3.sha256_path(claim_path),
        "terminal_manifest_sha256": g3.sha256_path(published / "manifest.json"),
        "runtime": runtime,
        "wall_hours": wall_hours,
        "cpu_core_hours": cpu_hours,
        "peak_rss_gib": peak_rss_gib,
        "restricted_storage_gb": storage_gb,
        "gpu_hours": 0,
        "preflight_status": preflight.get("status") if preflight else None,
        "failure_type": failure_type,
        "completed_fits": completed_fits,
        "completed_predictions": completed_predictions,
        "cleanup_complete": True,
        "attempt_root_file_set": ["attempt_claim.json", "receipt", "terminal"],
    }
    _write_readonly_no_replace(
        OFFICIAL_ATTEMPT_ROOT / "receipt", g3.json_bytes(receipt)
    )
    _lock_attempt_root(OFFICIAL_ATTEMPT_ROOT)
    return published


__all__ = [
    "ENDPOINT_COLUMNS",
    "FIT_COLUMNS",
    "G3ExecutionWrapperError",
    "OUTER_CELL_COLUMNS",
    "PREDICTION_COLUMNS",
    "REPEAT_COLUMNS",
    "SCRIPT",
    "TERMINAL_NAMES",
    "consume_claim",
    "derive_consumed_claim",
    "deterministic_test_predictor",
    "real_predictor",
    "run_compiled_replay",
    "run_models",
    "run_official_attempt",
    "run_runtime_control",
    "score_and_publish",
]
