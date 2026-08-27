#!/usr/bin/env python3
"""Exact staged scientific runner for the frozen D-122 MapLight battery.

The model process sees only the accepted D-126 model capability.  Each stage
is atomically frozen before the separate scorer capability may be opened.
Synthetic acceptance may inject a deterministic predictor; scientific use is
restricted to the receipt-checked CatBoost predictor below.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import math
import platform
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_resource_supervisor as supervisor
import global_v2_maplight_robustness_execution_compiler as compiler
import global_v2_maplight_robustness_execution_wrapper as mechanics
import global_v2_maplight_robustness_scoring_compiler as scoring_compiler
import global_v2_maplight_runner as maplight
import numpy as np

ROOT: Final = Path(__file__).resolve().parents[2]
SCRIPT: Final = Path(__file__).resolve()
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cypshift.openadmet_global_v2_metric import (  # type: ignore[import-untyped]  # noqa: E402
    PredictionRow as TutorialPrediction,
)
from cypshift.openadmet_global_v2_metric import (  # type: ignore[import-untyped]  # noqa: E402
    TruthRow as TutorialTruth,
)
from cypshift.openadmet_global_v2_metric import (  # type: ignore[import-untyped]  # noqa: E402
    tutorial_endpoint_st_rae,
)

CONTRACT: Final = (
    ROOT / "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_execution_contract_v2.json"
)
CONTRACT_SHA256: Final = (
    "9464b0947255298a8de8836af6178857841bb2a55bc5c0f4897be2ba91151bcf"
)
SCORING_ACCEPTANCE: Final = (
    ROOT / "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_scoring_capability_acceptance_v2.json"
)
SCORING_ACCEPTANCE_SHA256: Final = (
    "9643dac8627b6729458aba3b4f886f5438b859a3c25d0347f1c71070c4873ed0"
)
PREDICTION_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_predictions.v2"
)
TERMINAL_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_terminal.v2"
)
PREDICTION_COLUMNS: Final = (
    "molecule_id",
    "endpoint",
    "standardized_structure_hash",
    "component_hash",
    "repeat",
    "outer_fold",
    "candidate_id",
    "random_seed",
    "group_id",
    "prediction",
)
BASELINE_COLUMNS: Final = maplight.OUTER_COLUMNS
EXPECTED_ACCEPTED_SOURCES: Final = {
    compiler.SCRIPT: "029afd827e3a86718e7e2493594bbc6e6ed78e258534221e32acc2027ace72a7",
    mechanics.SCRIPT: "a6e02c244d6bd1b7bcb020dcf9627f68d453ae25827527e6de9acdaa30226c66",
    supervisor.SCRIPT: "0d7b016b638fb4019eb377328f63a193d23fd6763540a636bd821cbabed63cec",
    maplight.SCRIPT: "154f8d231c490da7d2af419bfb533ec18a17c2d4ec3938c0373995a3a9acb93f",
    scoring_compiler.SCRIPT: (
        "6f15205fccb4a7c2e1cc2c7244e31acf15d7fd34b285c85145bfde551da6f492"
    ),
}
SELECTION_FEATURE_COLUMNS: Final = mechanics.EXPECTED_FEATURE_COLUMNS
BOOTSTRAP_SEED: Final = 20260827
BOOTSTRAP_REPLICATES: Final = 2000
BOOTSTRAP_MAXIMUM_ATTEMPTS: Final = 20000
MAXIMUM_TUTORIAL_METRIC_CALLS: Final = 80
SYNTHETIC_BASELINE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026."
    "global_v2_maplight_robustness_synthetic_baseline.v2"
)
OFFICIAL_BASELINE_MANIFEST_SHA256: Final = (
    "62c88f7d1213ead4fd297f1a44905e71638e704765f9abc206dd12d152bf77fe"
)
OFFICIAL_BASELINE_OUTER_OOF_SHA256: Final = (
    "189c25b7d5bb923ddbc31764947fa6fc08d4c27a7063c4ede6cdabb93ccdd7e4"
)
ZERO_FORBIDDEN: Final = tuple(compiler.DENIED_ACCOUNTING)

Predictor = Callable[
    [
        mechanics.FitIdentity,
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
    ],
    tuple[np.ndarray[Any, Any], str],
]
Checkpoint = Callable[[str], None]


class RobustnessScientificRunnerError(RuntimeError):
    """A receipt, chronology, model, metric, or frozen gate differed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessScientificRunnerError(message)


def _float(value: str, label: str) -> float:
    try:
        observed = float(value)
    except ValueError as exc:
        raise RobustnessScientificRunnerError(f"{label} is not numeric") from exc
    _require(
        math.isfinite(observed) and value == format(observed, ".17g"),
        f"{label} is nonfinite or noncanonical",
    )
    return observed


def _mean(values: Iterable[float], label: str) -> float:
    material = list(values)
    _require(bool(material) and all(math.isfinite(value) for value in material), label)
    return math.fsum(material) / len(material)


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    _require(bool(ordered) and 0.0 <= probability <= 1.0, "quantile input differs")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def authenticate_static_boundary() -> dict[str, Any]:
    """Bind the corrected contract and every accepted implementation parent."""

    _require(maplight.sha256_path(CONTRACT) == CONTRACT_SHA256, "D-133 differs")
    _require(
        maplight.sha256_path(SCORING_ACCEPTANCE) == SCORING_ACCEPTANCE_SHA256,
        "D-132 acceptance differs",
    )
    for path, expected in EXPECTED_ACCEPTED_SOURCES.items():
        _require(
            maplight.sha256_path(path) == expected,
            f"accepted source differs: {path.name}",
        )
    parents = compiler.authenticate_static_boundary()
    scoring_parents = scoring_compiler.authenticate_static_boundary()
    _require(
        scoring_compiler.OUTPUT_COLUMNS
        == (
            "molecule_id",
            "endpoint",
            "standardized_structure_hash",
            "primary_component_hash",
            "source_file",
            "point",
            "low",
            "high",
        ),
        "scoring fields differ",
    )
    return {"compiler": parents, "scorer": scoring_parents}


def runtime_identity() -> dict[str, str]:
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
        f"model runtime differs: {observed}",
    )
    return observed


def real_catboost_predictor(
    identity: mechanics.FitIdentity,
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    """Fit one exact CPU CatBoost cell with the predeclared model seed."""

    try:
        from catboost import CatBoostRegressor  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RobustnessScientificRunnerError("CatBoost 1.2.1 is unavailable") from exc
    arguments = {**maplight.CATBOOST_ARGUMENTS, "random_seed": identity.random_seed}
    _require(
        arguments
        == {
            "loss_function": "MAE",
            "random_strength": 2,
            "random_seed": identity.random_seed,
            "task_type": "CPU",
            "thread_count": 16,
            "verbose": 0,
            "allow_writing_files": False,
        },
        "CatBoost constructor differs",
    )
    model = CatBoostRegressor(**arguments)
    model.fit(training, targets)
    resolved = cast(dict[str, Any], model.get_all_params())
    for key, value in arguments.items():
        if key in {"thread_count", "verbose", "allow_writing_files"}:
            continue
        _require(resolved.get(key) == value, f"resolved CatBoost {key} differs")
    resolved_sha256 = maplight.sha256_bytes(maplight.json_bytes(resolved))
    values = np.asarray(model.predict(prediction), dtype=np.float64)
    _require(
        values.shape == (len(prediction),) and bool(np.isfinite(values).all()),
        "CatBoost prediction differs",
    )
    return values, resolved_sha256


def deterministic_test_predictor(
    identity: mechanics.FitIdentity,
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], str]:
    """Deterministic topology double; never carries model-quality authority."""

    _require(bool(len(training) and len(targets)), "test training support is empty")
    center = float(np.mean(targets))
    token = sha256(identity.token.encode()).digest()
    bias = (int.from_bytes(token[:4], "big") / (2**32 - 1) - 0.5) * 0.04
    signal = np.asarray(prediction[:, 0], dtype=np.float64) * 1.0e-6
    values = np.full(len(prediction), center + bias, dtype=np.float64) + signal
    return values, maplight.sha256_bytes(f"model-double|{identity.token}".encode())


def _model_arrays_and_folds(
    model_root: Path, *, synthetic: bool
) -> tuple[
    dict[str, Any],
    dict[str, np.ndarray[Any, Any]],
    dict[tuple[str, int, str], tuple[str, str, int]],
    list[str],
]:
    maplight._readonly_root(model_root, "model capability")
    manifest = compiler._load_json(model_root / "manifest.json")
    _require(
        manifest.get("schema_version") == compiler.MODEL_SCHEMA
        and manifest.get("synthetic") is synthetic
        and manifest.get("bounded_contract_sha256")
        == compiler.BOUNDED_CONTRACT_SHA256
        and manifest.get("parent_contract_sha256")
        == compiler.PARENT_CONTRACT_SHA256
        and manifest.get("compiler_source_sha256")
        == maplight.sha256_path(compiler.SCRIPT)
        and compiler._is_sha(manifest.get("science_identity_sha256"))
        and manifest.get("accounting") == compiler._zero_accounting()
        and manifest.get("authority") == dict(maplight.DENIED_AUTHORITY),
        "model capability identity differs",
    )
    folds_path = maplight._regular(model_root / "folds.csv", "model folds")
    folds = maplight._read_csv(folds_path, compiler.CAPABILITY_FOLD_COLUMNS)
    _require(
        maplight.sha256_path(folds_path) == manifest.get("folds_sha256"),
        "model fold receipt differs",
    )
    fold_map: dict[tuple[str, int, str], tuple[str, str, int]] = {}
    for row in folds:
        key = row["molecule_id"], int(row["repeat"]), row["group_id"]
        value = (
            row["standardized_structure_hash"],
            row["component_hash"],
            int(row["outer_fold"]),
        )
        _require(
            key not in fold_map
            and row["group_id"] in compiler.GROUPS
            and int(row["repeat"]) in compiler.REPEATS
            and int(row["outer_fold"]) in compiler.OUTER_FOLDS
            and compiler._is_sha(value[0])
            and compiler._is_sha(value[1]),
            "model fold identity differs",
        )
        fold_map[key] = value
    _require(bool(fold_map), "model folds are empty")
    molecule_ids = sorted(
        molecule
        for molecule, repeat, group in fold_map
        if repeat == 0 and group == "PRIMARY_D032"
    )
    _require(
        len(molecule_ids) == manifest["molecules"], "feature identity count differs"
    )
    feature_receipts = manifest.get("feature_receipts")
    target_receipts = manifest.get("target_capabilities")
    _require(
        isinstance(feature_receipts, Mapping)
        and isinstance(target_receipts, Mapping)
        and bool(target_receipts)
        and all(
            isinstance(name, str)
            and name.startswith("targets/")
            and compiler._is_sha(receipt)
            for name, receipt in target_receipts.items()
        ),
        "model capability receipts differ",
    )
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    for name, columns, dtype in compiler.FEATURE_FILES:
        path = maplight._regular(model_root / name, f"feature {name}")
        _require(
            maplight.sha256_path(path) == feature_receipts.get(name),
            f"feature receipt differs: {name}",
        )
        array = np.load(path, allow_pickle=False, mmap_mode="r")
        _require(
            array.shape == (len(molecule_ids), columns) and array.dtype == dtype,
            f"feature shape differs: {name}",
        )
        arrays[name] = array
    _require(
        mechanics.FEATURE_COLUMNS == mechanics.EXPECTED_FEATURE_COLUMNS,
        "feature views differ",
    )
    return manifest, arrays, fold_map, molecule_ids


def _matrix(
    arrays: Mapping[str, np.ndarray[Any, Any]],
    names: Sequence[str],
    indices: Sequence[int],
) -> np.ndarray[Any, Any]:
    return np.ascontiguousarray(
        np.concatenate([arrays[name][list(indices)] for name in names], axis=1)
    )


def run_prediction_stage(
    *,
    stage: str,
    selected_candidate: str | None,
    model_capability_root: Path,
    output_root: Path,
    predictor: Predictor = real_catboost_predictor,
    checkpoint: Checkpoint = supervisor.resource_checkpoint,
    synthetic: bool,
    reverse_fit_order: bool = False,
) -> tuple[Path, dict[str, int]]:
    """Run and atomically freeze every prediction identity for one stage."""

    _require(not output_root.exists(), "prediction stage output exists")
    _require(
        (synthetic and predictor is deterministic_test_predictor)
        or (not synthetic and predictor is real_catboost_predictor),
        "predictor authority differs from execution mode",
    )
    manifest, arrays, fold_map, molecule_ids = _model_arrays_and_folds(
        model_capability_root, synthetic=synthetic
    )
    index = {molecule: position for position, molecule in enumerate(molecule_ids)}
    _require(synthetic or not reverse_fit_order, "official fit order differs")
    canonical_identities = mechanics._fit_identities(stage, selected_candidate)
    identities = (
        list(reversed(canonical_identities))
        if reverse_fit_order
        else canonical_identities
    )
    rows: list[dict[str, object]] = []
    parameter_receipts: set[str] = set()
    training_values = 0
    checkpoint(f"before:{stage}")
    target_receipts = cast(Mapping[str, str], manifest["target_capabilities"])
    for identity in identities:
        checkpoint(f"before:fit:{identity.token}")
        target_path = mechanics._target_path(model_capability_root, identity)
        relative = target_path.relative_to(model_capability_root).as_posix()
        raw = maplight._regular(target_path, "training target capability").read_bytes()
        _require(
            maplight.sha256_bytes(raw) == target_receipts.get(relative),
            "training target receipt differs",
        )
        targets = maplight._read_csv(target_path, maplight.TARGET_COLUMNS)
        training_ids = [row["molecule_id"] for row in targets]
        validation_ids = sorted(
            molecule
            for molecule in molecule_ids
            if (molecule, identity.repeat, identity.group_id) in fold_map
            and fold_map[(molecule, identity.repeat, identity.group_id)][2]
            == identity.outer_fold
        )
        _require(
            bool(training_ids and validation_ids)
            and len(training_ids) == len(set(training_ids))
            and not set(training_ids).intersection(validation_ids),
            "fit population differs",
        )
        _require(
            all(
                (row["molecule_id"], identity.repeat, identity.group_id) in fold_map
                and fold_map[
                    (row["molecule_id"], identity.repeat, identity.group_id)
                ][2]
                != identity.outer_fold
                for row in targets
            ),
            "training target crosses the active validation fold",
        )
        y = np.asarray(
            [_float(row["point"], "training point") for row in targets],
            dtype=np.float64,
        )
        feature_names = mechanics.FEATURE_VIEWS[identity.candidate_id]
        predicted, parameter_receipt = predictor(
            identity,
            _matrix(arrays, feature_names, [index[value] for value in training_ids]),
            y,
            _matrix(arrays, feature_names, [index[value] for value in validation_ids]),
        )
        _require(
            predicted.shape == (len(validation_ids),)
            and bool(np.isfinite(predicted).all()),
            "predictor output differs",
        )
        parameter_receipts.add(parameter_receipt)
        training_values += len(y)
        for molecule, value in zip(validation_ids, predicted, strict=True):
            structure, component, fold = fold_map[
                (molecule, identity.repeat, identity.group_id)
            ]
            rows.append(
                {
                    "molecule_id": molecule,
                    "endpoint": identity.endpoint,
                    "standardized_structure_hash": structure,
                    "component_hash": component,
                    "repeat": identity.repeat,
                    "outer_fold": fold,
                    "candidate_id": identity.candidate_id,
                    "random_seed": identity.random_seed,
                    "group_id": identity.group_id,
                    "prediction": format(float(value), ".17g"),
                }
            )
        checkpoint(f"after:fit:{identity.token}")
    rows.sort(key=lambda row: tuple(str(row[name]) for name in PREDICTION_COLUMNS[:-1]))
    prediction_bytes = maplight.csv_bytes(PREDICTION_COLUMNS, rows)
    accounting = compiler._zero_accounting()
    if synthetic:
        accounting = {
            **accounting,
            "synthetic_model_fits": len(identities),
            "synthetic_predictions_generated": len(rows),
        }
    else:
        accounting = {
            **accounting,
            "official_model_fits": len(identities),
            "official_predictions_generated": len(rows),
        }
    result = {
        "schema_version": PREDICTION_SCHEMA,
        "stage": stage,
        "synthetic": synthetic,
        "contract_sha256": CONTRACT_SHA256,
        "runner_source_sha256": maplight.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": maplight.sha256_path(
            model_capability_root / "manifest.json"
        ),
        "fit_identities": len(identities),
        "prediction_identities": len(rows),
        "training_target_values_opened": training_values,
        "resolved_parameter_receipts": sorted(parameter_receipts),
        "model_double_invocations": len(identities)
        if predictor is deterministic_test_predictor
        else 0,
        "real_catboost_fits": 0
        if predictor is deterministic_test_predictor
        else len(identities),
        "output_receipts": {"predictions.csv": maplight.sha256_bytes(prediction_bytes)},
        "accounting": accounting,
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    published = maplight.publish_files(
        output_root,
        {
            "predictions.csv": prediction_bytes,
            "manifest.json": maplight.json_bytes(result),
        },
    )
    checkpoint(f"after:{stage}")
    return published, {
        "fits": len(identities),
        "predictions": len(rows),
        "training_target_values_opened": training_values,
    }


def _prediction_stage_rows(
    root: Path,
    stage: str,
    *,
    selected_candidate: str | None,
    synthetic: bool,
    model_capability_root: Path,
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> list[dict[str, str]]:
    maplight._readonly_root(root, f"{stage} prediction root")
    manifest, _raw = maplight._load_json(root / "manifest.json")
    rows = maplight._read_csv(root / "predictions.csv", PREDICTION_COLUMNS)
    identities = mechanics._fit_identities(stage, selected_candidate)
    allowed = {
        (
            identity.candidate_id,
            identity.random_seed,
            identity.group_id,
            identity.repeat,
            identity.endpoint,
            identity.outer_fold,
        )
        for identity in identities
    }
    expected_accounting = {
        **compiler._zero_accounting(),
        "synthetic_model_fits": len(identities) if synthetic else 0,
        "synthetic_predictions_generated": len(rows) if synthetic else 0,
        "official_model_fits": 0 if synthetic else len(identities),
        "official_predictions_generated": 0 if synthetic else len(rows),
    }
    parameter_receipts = manifest.get("resolved_parameter_receipts")
    _require(
        manifest.get("schema_version") == PREDICTION_SCHEMA
        and manifest.get("stage") == stage
        and manifest.get("synthetic") is synthetic
        and manifest.get("contract_sha256") == CONTRACT_SHA256
        and manifest.get("runner_source_sha256") == maplight.sha256_path(SCRIPT)
        and manifest.get("model_capability_manifest_sha256")
        == maplight.sha256_path(model_capability_root / "manifest.json")
        and manifest.get("fit_identities") == len(identities)
        and manifest.get("output_receipts", {}).get("predictions.csv")
        == maplight.sha256_path(root / "predictions.csv")
        and manifest.get("prediction_identities") == len(rows),
        f"{stage} prediction freeze differs",
    )
    _require(
        isinstance(parameter_receipts, list)
        and bool(parameter_receipts)
        and all(compiler._is_sha(value) for value in parameter_receipts)
        and manifest.get("training_target_values_opened", 0) > 0
        and manifest.get("model_double_invocations")
        == (len(identities) if synthetic else 0)
        and manifest.get("real_catboost_fits")
        == (0 if synthetic else len(identities))
        and manifest.get("accounting") == expected_accounting
        and manifest.get("authority") == dict(maplight.DENIED_AUTHORITY),
        f"{stage} prediction authority differs",
    )
    seen: dict[tuple[str, int, str, int, str, int], int] = defaultdict(int)
    seen_rows: set[tuple[str, int, str, int, str, int, str]] = set()
    for row in rows:
        repeat = int(row["repeat"])
        fold = int(row["outer_fold"])
        fit_identity = (
            row["candidate_id"],
            int(row["random_seed"]),
            row["group_id"],
            repeat,
            row["endpoint"],
            fold,
        )
        fold_key = row["molecule_id"], repeat, row["group_id"]
        prediction_identity = (*fit_identity, row["molecule_id"])
        _require(
            fit_identity in allowed
            and prediction_identity not in seen_rows
            and fold_key in fold_map
            and fold_map[fold_key]
            == (
                row["standardized_structure_hash"],
                row["component_hash"],
                fold,
            ),
            f"{stage} prediction identity differs",
        )
        _float(row["prediction"], f"{stage} prediction")
        seen[fit_identity] += 1
        seen_rows.add(prediction_identity)
    expected_counts = {
        identity: sum(
            fold_map[(molecule, identity[3], identity[2])][2] == identity[5]
            for molecule in {
                key[0]
                for key in fold_map
                if key[1] == identity[3] and key[2] == identity[2]
            }
        )
        for identity in allowed
    }
    _require(
        set(seen) == allowed
        and seen == expected_counts
        and len(rows) == sum(expected_counts.values()),
        f"{stage} fit coverage differs",
    )
    return rows


def _scoring_truth(
    root: Path,
    *,
    synthetic: bool,
    model_capability_root: Path,
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, str]]]:
    maplight._readonly_root(root, "eight-field scorer capability")
    manifest, _raw = maplight._load_json(root / "manifest.json")
    rows = maplight._read_csv(
        root / "scoring_truth.csv", scoring_compiler.OUTPUT_COLUMNS
    )
    _require(
        manifest.get("schema_version") == scoring_compiler.CAPABILITY_SCHEMA
        and manifest.get("synthetic") is synthetic
        and manifest.get("status")
        == (
            "G2_7E_SYNTHETIC_SCORING_CAPABILITY_FROZEN"
            if synthetic
            else "G2_7E_DEVELOPMENT_SCORING_CAPABILITY_FROZEN"
        )
        and manifest.get("d126_model_manifest_sha256")
        == maplight.sha256_path(model_capability_root / "manifest.json")
        and manifest.get("output_columns") == list(scoring_compiler.OUTPUT_COLUMNS)
        and manifest.get("output_receipts", {}).get("scoring_truth.csv")
        == maplight.sha256_path(root / "scoring_truth.csv")
        and manifest.get("confirmatory_suffixes_opaque") is True
        and manifest.get("model_capability_fields") == 0
        and manifest.get("feature_arrays") == 0
        and manifest.get("training_target_files") == 0
        and manifest.get("real_catboost_fits") == 0
        and manifest.get("development_metric_evaluations") == 0
        and manifest.get("model_quality_authority") is False
        and manifest.get("claim_authority") is False
        and manifest.get("authority") == dict(maplight.DENIED_AUTHORITY),
        "eight-field scorer capability differs",
    )
    truth: dict[tuple[str, str], dict[str, str]] = {}
    sources: set[str] = set()
    for row in rows:
        key = row["molecule_id"], row["endpoint"]
        _require(
            key not in truth
            and row["endpoint"] in compiler.ENDPOINTS
            and compiler._is_sha(row["standardized_structure_hash"])
            and compiler._is_sha(row["primary_component_hash"]),
            "scoring truth identity differs",
        )
        _float(row["point"], "scoring point")
        if row["low"] or row["high"]:
            _require(bool(row["low"] and row["high"]), "partial tutorial bounds")
            low = _float(row["low"], "scoring low")
            point = _float(row["point"], "scoring point")
            high = _float(row["high"], "scoring high")
            _require(low <= point <= high, "reported bounds do not contain point")
        sources.add(row["source_file"])
        for repeat in compiler.REPEATS:
            fold_key = row["molecule_id"], repeat, "PRIMARY_D032"
            _require(
                fold_key in fold_map
                and fold_map[fold_key][0] == row["standardized_structure_hash"]
                and fold_map[fold_key][1] == row["primary_component_hash"],
                "scoring truth does not match primary folds",
            )
        truth[key] = row
    _require(
        bool(truth) and sources == {scoring_compiler.DIRECT_SOURCE_FILE},
        "source provenance differs",
    )
    return manifest, truth


def _baseline_predictions(
    root: Path,
    *,
    synthetic: bool,
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> tuple[dict[str, Any], dict[tuple[str, str, int], float]]:
    maplight._readonly_root(root, "fixed MapLight baseline terminal")
    manifest, _raw = maplight._load_json(root / "manifest.json")
    path = maplight._regular(
        root / "development_outer_oof.csv", "fixed MapLight baseline predictions"
    )
    rows = maplight._read_csv(path, BASELINE_COLUMNS)
    receipts = manifest.get("output_receipts")
    _require(
        isinstance(receipts, Mapping)
        and receipts.get("development_outer_oof.csv") == maplight.sha256_path(path),
        "baseline prediction receipt differs",
    )
    if synthetic:
        _require(
            manifest.get("schema_version") == SYNTHETIC_BASELINE_SCHEMA
            and manifest.get("synthetic") is True
            and manifest.get("official_operations") == 0
            and manifest.get("model_quality_authority") is False
            and manifest.get("claim_authority") is False,
            "synthetic baseline authority differs",
        )
    else:
        _require(
            maplight.sha256_path(root / "manifest.json")
            == OFFICIAL_BASELINE_MANIFEST_SHA256
            and maplight.sha256_path(path) == OFFICIAL_BASELINE_OUTER_OOF_SHA256,
            "official baseline receipt differs",
        )
    predictions: dict[tuple[str, str, int], float] = {}
    for row in rows:
        repeat = int(row["repeat"])
        fold = int(row["outer_fold"])
        key = row["molecule_id"], row["endpoint"], repeat
        fold_key = row["molecule_id"], repeat, "PRIMARY_D032"
        _require(
            key not in predictions
            and row["endpoint"] in compiler.ENDPOINTS
            and repeat in compiler.REPEATS
            and fold in compiler.OUTER_FOLDS
            and row["system_id"] == maplight.SYSTEM_ID
            and compiler._is_sha(row["model_id"])
            and compiler._is_sha(row["split_id"])
            and fold_key in fold_map
            and fold_map[fold_key][1] == row["similarity_component_hash"]
            and fold_map[fold_key][2] == fold,
            "baseline identity differs",
        )
        predictions[key] = _float(row["prediction"], "baseline prediction")
    _require(bool(predictions), "baseline predictions are empty")
    return manifest, predictions


def _prediction_index(
    rows: Sequence[Mapping[str, str]],
) -> dict[tuple[str, int, str, int, str, str], float]:
    result: dict[tuple[str, int, str, int, str, str], float] = {}
    for row in rows:
        key = (
            row["candidate_id"],
            int(row["random_seed"]),
            row["group_id"],
            int(row["repeat"]),
            row["molecule_id"],
            row["endpoint"],
        )
        _require(key not in result, "prediction identity is duplicated")
        result[key] = _float(row["prediction"], "prediction")
    return result


def _recipe_predictions(
    index: Mapping[tuple[str, int, str, int, str, str], float],
    *,
    candidate: str,
    seed: int,
    group: str,
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> dict[tuple[str, str, int], float]:
    available = {
        (molecule, endpoint, repeat): value
        for (
            observed_candidate,
            observed_seed,
            observed_group,
            repeat,
            molecule,
            endpoint,
        ), value in index.items()
        if observed_candidate == candidate
        and observed_seed == seed
        and observed_group == group
    }
    expected = {
        (molecule, endpoint, repeat)
        for molecule, endpoint in truth
        for repeat in compiler.REPEATS
        if (molecule, repeat, group) in fold_map
    }
    _require(bool(expected) and expected.issubset(available), "recipe rows differ")
    result = {key: available[key] for key in sorted(expected)}
    return result


def _matched_predictions(
    predictions: Mapping[tuple[str, str, int], float],
    *,
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
    group: str,
) -> dict[tuple[str, str, int], float]:
    expected = {
        (molecule, endpoint, repeat)
        for molecule, endpoint in truth
        for repeat in compiler.REPEATS
        if (molecule, repeat, group) in fold_map
    }
    _require(bool(expected) and expected.issubset(predictions), "paired rows differ")
    return {key: predictions[key] for key in sorted(expected)}


def _component_errors(
    *,
    predictions: Mapping[tuple[str, str, int], float],
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
    group: str,
    collapse_duplicates: bool = False,
    excluded_components: frozenset[str] = frozenset(),
) -> dict[tuple[str, int], dict[str, float]]:
    raw: dict[tuple[str, int, str], dict[str, list[tuple[str, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (molecule, endpoint), truth_row in sorted(truth.items()):
        point = _float(truth_row["point"], "component point")
        for repeat in compiler.REPEATS:
            fold_key = molecule, repeat, group
            prediction_key = molecule, endpoint, repeat
            _require(
                fold_key in fold_map and prediction_key in predictions,
                "metric paired row is absent",
            )
            structure, component, _fold = fold_map[fold_key]
            if component in excluded_components:
                continue
            raw[(endpoint, repeat, component)][structure].append(
                (molecule, abs(predictions[prediction_key] - point))
            )
    result: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    for (endpoint, repeat, component), structures in sorted(raw.items()):
        if collapse_duplicates:
            values = [
                _mean((value for _molecule, value in members), "duplicate mean")
                for _structure, members in sorted(structures.items())
            ]
        else:
            values = [
                value
                for _structure, members in sorted(structures.items())
                for _molecule, value in sorted(members)
            ]
        result[(endpoint, repeat)][component] = _mean(values, "component mean")
    expected = {
        (endpoint, repeat)
        for endpoint in compiler.ENDPOINTS
        for repeat in compiler.REPEATS
    }
    _require(set(result) == expected, "component metric contexts differ")
    return dict(result)


def _component_summary(
    errors: Mapping[tuple[str, int], Mapping[str, float]],
) -> tuple[float, dict[str, float]]:
    endpoint_values: dict[str, float] = {}
    for endpoint in compiler.ENDPOINTS:
        endpoint_values[endpoint] = _mean(
            (
                _mean(errors[(endpoint, repeat)].values(), "component cell")
                for repeat in compiler.REPEATS
            ),
            "endpoint component mean",
        )
    return _mean(endpoint_values.values(), "component macro"), endpoint_values


def _tutorial_summary(
    *,
    predictions: Mapping[tuple[str, str, int], float],
    truth: Mapping[tuple[str, str], Mapping[str, str]],
) -> tuple[float, dict[str, float], int]:
    endpoint_values: dict[str, float] = {}
    calls = 0
    for endpoint in compiler.ENDPOINTS:
        eligible = [
            row
            for (molecule, observed), row in sorted(truth.items())
            if observed == endpoint and row["low"] and row["high"]
        ]
        _require(bool(eligible), f"tutorial endpoint is empty: {endpoint}")
        truth_rows = [
            TutorialTruth(
                molecule_id=row["molecule_id"],
                endpoint=endpoint,
                point=_float(row["point"], "tutorial point"),
                low=_float(row["low"], "tutorial low"),
                high=_float(row["high"], "tutorial high"),
            )
            for row in eligible
        ]
        prediction_rows = [
            TutorialPrediction(
                molecule_id=row.molecule_id,
                endpoint=endpoint,
                prediction=_mean(
                    (
                        predictions[(row.molecule_id, endpoint, repeat)]
                        for repeat in compiler.REPEATS
                    ),
                    "repeat-mean prediction",
                ),
            )
            for row in truth_rows
        ]
        endpoint_values[endpoint] = tutorial_endpoint_st_rae(
            truth_rows, prediction_rows, endpoint
        ).value
        calls += 1
    return _mean(endpoint_values.values(), "tutorial macro"), endpoint_values, calls


def _outer_cells(
    *,
    errors: Mapping[tuple[str, int], Mapping[str, float]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
    group: str,
) -> dict[tuple[int, int], float]:
    component_folds = {
        (component, repeat): fold
        for (_molecule, repeat, observed_group), (
            _structure,
            component,
            fold,
        ) in fold_map.items()
        if observed_group == group
    }
    values: dict[tuple[int, int], float] = {}
    for repeat in compiler.REPEATS:
        for fold in compiler.OUTER_FOLDS:
            endpoint_values = []
            for endpoint in compiler.ENDPOINTS:
                selected = [
                    value
                    for component, value in errors[(endpoint, repeat)].items()
                    if component_folds[(component, repeat)] == fold
                ]
                endpoint_values.append(_mean(selected, "outer cell endpoint"))
            values[(repeat, fold)] = _mean(endpoint_values, "outer cell macro")
    return values


def metric_summary(
    *,
    predictions: Mapping[tuple[str, str, int], float],
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
    group: str,
    collapse_duplicates: bool = False,
    excluded_components: frozenset[str] = frozenset(),
    include_tutorial: bool = True,
) -> dict[str, Any]:
    expected = {
        (molecule, endpoint, repeat)
        for molecule, endpoint in truth
        for repeat in compiler.REPEATS
        if (molecule, repeat, group) in fold_map
    }
    _require(
        bool(expected) and set(predictions) == expected,
        "metric prediction rows do not exactly match truth",
    )
    errors = _component_errors(
        predictions=predictions,
        truth=truth,
        fold_map=fold_map,
        group=group,
        collapse_duplicates=collapse_duplicates,
        excluded_components=excluded_components,
    )
    component, endpoint_component = _component_summary(errors)
    if include_tutorial:
        tutorial, endpoint_tutorial, calls = _tutorial_summary(
            predictions=predictions, truth=truth
        )
    else:
        tutorial, endpoint_tutorial, calls = None, {}, 0
    cells = _outer_cells(errors=errors, fold_map=fold_map, group=group)
    return {
        "tutorial_primary": tutorial,
        "component_macro_mae": component,
        "endpoint_tutorial": endpoint_tutorial,
        "endpoint_component_mae": endpoint_component,
        "outer_cells": {
            f"r{repeat}|f{fold}": value for (repeat, fold), value in cells.items()
        },
        "tutorial_metric_calls": calls,
        "component_errors": errors,
    }


def paired_component_bootstrap(
    *,
    candidate_errors: Mapping[tuple[str, int], Mapping[str, float]],
    baseline_errors: Mapping[tuple[str, int], Mapping[str, float]],
    accepted_replicates: int = BOOTSTRAP_REPLICATES,
    maximum_attempts: int = BOOTSTRAP_MAXIMUM_ATTEMPTS,
) -> dict[str, float | int]:
    """Paired original-component bootstrap with frozen draw seed and quantiles."""

    contexts = [
        (endpoint, repeat)
        for endpoint in compiler.ENDPOINTS
        for repeat in compiler.REPEATS
    ]
    _require(
        all(
            set(candidate_errors[context]) == set(baseline_errors[context])
            for context in contexts
        ),
        "paired bootstrap component rows differ",
    )
    frame = sorted(
        {
            component
            for errors in (candidate_errors, baseline_errors)
            for context in contexts
            for component in errors[context]
        }
    )
    _require(bool(frame), "bootstrap frame is empty")
    position = {component: index for index, component in enumerate(frame)}
    candidate = np.full((len(contexts), len(frame)), np.nan, dtype=np.float64)
    baseline = np.full_like(candidate, np.nan)
    for context_index, context in enumerate(contexts):
        for component, value in candidate_errors[context].items():
            candidate[context_index, position[component]] = value
        for component, value in baseline_errors[context].items():
            baseline[context_index, position[component]] = value
    candidate_mask = np.isfinite(candidate)
    baseline_mask = np.isfinite(baseline)
    _require(
        bool(candidate_mask.any(axis=1).all() and baseline_mask.any(axis=1).all()),
        "bootstrap context support differs",
    )
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    draws: list[float] = []
    attempts = 0
    while attempts < maximum_attempts and len(draws) < accepted_replicates:
        attempts += 1
        sampled = rng.integers(0, len(frame), size=len(frame), endpoint=False)
        multiplicity = np.bincount(sampled, minlength=len(frame)).astype(np.float64)
        candidate_denominator = candidate_mask @ multiplicity
        baseline_denominator = baseline_mask @ multiplicity
        if bool(
            (candidate_denominator <= 0).any() or (baseline_denominator <= 0).any()
        ):
            continue
        candidate_values = (
            np.nan_to_num(candidate) @ multiplicity / candidate_denominator
        )
        baseline_values = np.nan_to_num(baseline) @ multiplicity / baseline_denominator
        draws.append(float(np.mean(candidate_values - baseline_values)))
    _require(len(draws) == accepted_replicates, "bootstrap attempt exhaustion")
    point = _mean(
        (
            _mean(candidate_errors[context].values(), "candidate bootstrap point")
            - _mean(baseline_errors[context].values(), "baseline bootstrap point")
            for context in contexts
        ),
        "bootstrap point",
    )
    return {
        "point_delta": point,
        "lower_95": _quantile(draws, 0.025),
        "upper_95": _quantile(draws, 0.975),
        "accepted_replicates": accepted_replicates,
        "attempts": attempts,
    }


def select_stage_a_candidate(
    *,
    stage_a_root: Path,
    scoring_capability_root: Path,
    baseline_terminal_root: Path,
    model_capability_root: Path,
    synthetic: bool,
) -> tuple[str, dict[str, Any]]:
    """Open truth only after stage-A freeze and issue exactly one selection token."""

    _model_manifest, _arrays, fold_map, _molecules = _model_arrays_and_folds(
        model_capability_root, synthetic=synthetic
    )
    rows = _prediction_stage_rows(
        stage_a_root,
        "stage_a",
        selected_candidate=None,
        synthetic=synthetic,
        model_capability_root=model_capability_root,
        fold_map=fold_map,
    )
    _scoring_manifest, truth = _scoring_truth(
        scoring_capability_root,
        synthetic=synthetic,
        model_capability_root=model_capability_root,
        fold_map=fold_map,
    )
    _baseline_manifest, baseline_all = _baseline_predictions(
        baseline_terminal_root, synthetic=synthetic, fold_map=fold_map
    )
    baseline_predictions = _matched_predictions(
        baseline_all,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
    )
    predictions = _prediction_index(rows)
    baseline = metric_summary(
        predictions=baseline_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
    )
    evaluations: dict[str, dict[str, Any]] = {}
    eligible: list[str] = []
    for candidate in compiler.CANDIDATES[1:]:
        candidate_predictions = _recipe_predictions(
            predictions,
            candidate=candidate,
            seed=1,
            group="PRIMARY_D032",
            truth=truth,
            fold_map=fold_map,
        )
        summary = metric_summary(
            predictions=candidate_predictions,
            truth=truth,
            fold_map=fold_map,
            group="PRIMARY_D032",
        )
        bootstrap = paired_component_bootstrap(
            candidate_errors=summary["component_errors"],
            baseline_errors=baseline["component_errors"],
        )
        relative_improvement = (
            baseline["tutorial_primary"] - summary["tutorial_primary"]
        ) / baseline["tutorial_primary"]
        component_improvement = (
            baseline["component_macro_mae"] - summary["component_macro_mae"]
        )
        favorable = sum(
            summary["outer_cells"][cell] < baseline["outer_cells"][cell]
            for cell in sorted(baseline["outer_cells"])
        )
        maximum_endpoint_degradation = max(
            summary["endpoint_component_mae"][endpoint]
            - baseline["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        )
        endpoint_degradation = {
            endpoint: summary["endpoint_component_mae"][endpoint]
            - baseline["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        }
        gates = {
            "material_improvement": relative_improvement >= 0.01
            or component_improvement >= 0.005,
            "paired_bootstrap_upper_95_below_zero": bootstrap["upper_95"] < 0.0,
            "favorable_outer_cells_at_least_8": favorable >= 8,
            "maximum_endpoint_degradation_at_most_0_005": (
                maximum_endpoint_degradation <= 0.005
            ),
        }
        if all(gates.values()):
            eligible.append(candidate)
        evaluations[candidate] = {
            "tutorial_primary": summary["tutorial_primary"],
            "component_macro_mae": summary["component_macro_mae"],
            "endpoint_component_mae": summary["endpoint_component_mae"],
            "endpoint_component_mae_degradation": endpoint_degradation,
            "relative_tutorial_improvement": relative_improvement,
            "component_mae_improvement": component_improvement,
            "favorable_outer_cells": favorable,
            "maximum_endpoint_degradation": maximum_endpoint_degradation,
            "bootstrap": bootstrap,
            "gates": gates,
            "eligible": all(gates.values()),
            "tutorial_metric_calls": summary["tutorial_metric_calls"],
        }
    selected = min(
        eligible,
        key=lambda candidate: (
            SELECTION_FEATURE_COLUMNS[candidate],
            evaluations[candidate]["tutorial_primary"],
            evaluations[candidate]["component_macro_mae"],
            candidate,
        ),
        default="G2-7-M0-FULL",
    )
    token_payload = {
        "selected_candidate": selected,
        "selection_tokens": 1,
        "runner_ups": 0,
        "full_is_default": True,
        "ordering": [
            "feature_columns",
            "tutorial_primary",
            "component_macro_mae",
            "candidate_id",
        ],
        "baseline": {
            "tutorial_primary": baseline["tutorial_primary"],
            "component_macro_mae": baseline["component_macro_mae"],
            "endpoint_component_mae": baseline["endpoint_component_mae"],
        },
        "drop_one_evaluations": evaluations,
        "tutorial_metric_calls": baseline["tutorial_metric_calls"]
        + sum(value["tutorial_metric_calls"] for value in evaluations.values()),
    }
    token_payload["selection_token_sha256"] = maplight.sha256_bytes(
        maplight.json_bytes(token_payload)
    )
    return selected, token_payload


def _seed_diagnostics(
    *,
    selected: str,
    selected_primary: Mapping[str, Any],
    stage_a_index: Mapping[tuple[str, int, str, int, str, str], float],
    stage_c_index: Mapping[tuple[str, int, str, int, str, str], float] | None,
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> dict[str, Any]:
    source = stage_a_index if selected == "G2-7-M0-FULL" else stage_c_index
    _require(source is not None, "selected seed predictions are absent")
    assert source is not None
    values: dict[str, Any] = {}
    all_pass = True
    for seed in compiler.SEED_PERTURBATIONS:
        predictions = _recipe_predictions(
            source,
            candidate=selected,
            seed=seed,
            group="PRIMARY_D032",
            truth=truth,
            fold_map=fold_map,
        )
        summary = metric_summary(
            predictions=predictions,
            truth=truth,
            fold_map=fold_map,
            group="PRIMARY_D032",
        )
        tutorial_degradation = (
            summary["tutorial_primary"] - selected_primary["tutorial_primary"]
        ) / selected_primary["tutorial_primary"]
        component_degradation = (
            summary["component_macro_mae"] - selected_primary["component_macro_mae"]
        )
        endpoint_degradation = max(
            summary["endpoint_component_mae"][endpoint]
            - selected_primary["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        )
        endpoint_degradations = {
            endpoint: summary["endpoint_component_mae"][endpoint]
            - selected_primary["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        }
        gates = {
            "relative_tutorial_degradation_at_most_0_03": tutorial_degradation <= 0.03,
            "component_degradation_at_most_0_015": component_degradation <= 0.015,
            "endpoint_degradation_at_most_0_025": endpoint_degradation <= 0.025,
        }
        all_pass &= all(gates.values())
        values[str(seed)] = {
            "tutorial_primary": summary["tutorial_primary"],
            "component_macro_mae": summary["component_macro_mae"],
            "endpoint_component_mae": summary["endpoint_component_mae"],
            "endpoint_component_mae_degradation": endpoint_degradations,
            "relative_tutorial_degradation": tutorial_degradation,
            "component_degradation": component_degradation,
            "maximum_endpoint_degradation": endpoint_degradation,
            "gates": gates,
            "tutorial_metric_calls": summary["tutorial_metric_calls"],
        }
    return {
        "values": values,
        "pass": all_pass,
        "tutorial_metric_calls": sum(
            value["tutorial_metric_calls"] for value in values.values()
        ),
    }


def _group_diagnostics(
    *,
    selected: str,
    selected_primary_predictions: Mapping[tuple[str, str, int], float],
    selected_primary: Mapping[str, Any],
    stage_b_index: Mapping[tuple[str, int, str, int, str, str], float],
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    all_pass = True
    for group in compiler.GROUPS[1:]:
        active_truth = {
            key: row
            for key, row in truth.items()
            if all((key[0], repeat, group) in fold_map for repeat in compiler.REPEATS)
        }
        predictions = _recipe_predictions(
            stage_b_index,
            candidate=selected,
            seed=1,
            group=group,
            truth=active_truth,
            fold_map=fold_map,
        )
        summary = metric_summary(
            predictions=predictions,
            truth=active_truth,
            fold_map=fold_map,
            group=group,
            include_tutorial=False,
        )
        matched_primary = metric_summary(
            predictions=_matched_predictions(
                selected_primary_predictions,
                truth=active_truth,
                fold_map=fold_map,
                group="PRIMARY_D032",
            ),
            truth=active_truth,
            fold_map=fold_map,
            group="PRIMARY_D032",
            include_tutorial=False,
        )
        component_degradation = (
            summary["component_macro_mae"] - matched_primary["component_macro_mae"]
        )
        endpoint_degradation = max(
            summary["endpoint_component_mae"][endpoint]
            - matched_primary["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        )
        endpoint_degradations = {
            endpoint: summary["endpoint_component_mae"][endpoint]
            - matched_primary["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        }
        gates = {
            "component_degradation_at_most_0_030": component_degradation <= 0.030,
            "endpoint_degradation_at_most_0_050": endpoint_degradation <= 0.050,
        }
        all_pass &= all(gates.values())
        values[group] = {
            "active_truth_rows": len(active_truth),
            "matched_primary_component_macro_mae": matched_primary[
                "component_macro_mae"
            ],
            "matched_primary_endpoint_component_mae": matched_primary[
                "endpoint_component_mae"
            ],
            "component_macro_mae": summary["component_macro_mae"],
            "endpoint_component_mae": summary["endpoint_component_mae"],
            "endpoint_component_mae_degradation": endpoint_degradations,
            "component_degradation": component_degradation,
            "maximum_endpoint_degradation": endpoint_degradation,
            "gates": gates,
        }
    return {"values": values, "pass": all_pass, "tutorial_metric_calls": 0}


def _clipped_predictions(
    *,
    predictions: Mapping[tuple[str, str, int], float],
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
    quantiles: tuple[float, float] | None,
) -> dict[tuple[str, str, int], float]:
    result: dict[tuple[str, str, int], float] = {}
    for key, prediction in predictions.items():
        molecule, endpoint, repeat = key
        fold_key = molecule, repeat, "PRIMARY_D032"
        if fold_key not in fold_map:
            continue
        validation_fold = fold_map[fold_key][2]
        training_points = [
            _float(row["point"], "clip training point")
            for (other, observed_endpoint), row in truth.items()
            if observed_endpoint == endpoint
            and (other, repeat, "PRIMARY_D032") in fold_map
            and fold_map[(other, repeat, "PRIMARY_D032")][2] != validation_fold
        ]
        _require(bool(training_points), "clip training support is empty")
        if quantiles is None:
            low, high = min(training_points), max(training_points)
        else:
            low = _quantile(training_points, quantiles[0])
            high = _quantile(training_points, quantiles[1])
        result[key] = min(max(prediction, low), high)
    _require(set(result) == set(predictions), "clipped prediction identity differs")
    return result


def _aggregate_diagnostics(
    *,
    selected: str,
    selected_predictions: Mapping[tuple[str, str, int], float],
    baseline_predictions: Mapping[tuple[str, str, int], float],
    selected_primary: Mapping[str, Any],
    baseline_primary: Mapping[str, Any],
    truth: Mapping[tuple[str, str], Mapping[str, str]],
    fold_map: Mapping[tuple[str, int, str], tuple[str, str, int]],
) -> dict[str, Any]:
    selected_duplicate = metric_summary(
        predictions=selected_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
        collapse_duplicates=True,
        include_tutorial=False,
    )
    baseline_duplicate = metric_summary(
        predictions=baseline_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
        collapse_duplicates=True,
        include_tutorial=False,
    )
    duplicate_change = (
        selected_duplicate["component_macro_mae"]
        - selected_primary["component_macro_mae"]
    )
    baseline_duplicate_change = (
        baseline_duplicate["component_macro_mae"]
        - baseline_primary["component_macro_mae"]
    )
    selected_duplicate_endpoint_change = {
        endpoint: selected_duplicate["endpoint_component_mae"][endpoint]
        - selected_primary["endpoint_component_mae"][endpoint]
        for endpoint in compiler.ENDPOINTS
    }
    baseline_duplicate_endpoint_change = {
        endpoint: baseline_duplicate["endpoint_component_mae"][endpoint]
        - baseline_primary["endpoint_component_mae"][endpoint]
        for endpoint in compiler.ENDPOINTS
    }

    contributions: dict[str, float] = defaultdict(float)
    for context in sorted(selected_primary["component_errors"]):
        for component, value in selected_primary["component_errors"][context].items():
            contributions[component] += value
    _require(
        len(contributions) >= 10, "influence population has fewer than ten components"
    )
    top_ten = tuple(
        component
        for component, _value in sorted(
            contributions.items(), key=lambda item: (-item[1], item[0])
        )[:10]
    )
    excluded = frozenset(top_ten)
    selected_influence = metric_summary(
        predictions=selected_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
        excluded_components=excluded,
        include_tutorial=False,
    )
    baseline_influence = metric_summary(
        predictions=baseline_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
        excluded_components=excluded,
        include_tutorial=False,
    )
    influence_change = (
        selected_influence["component_macro_mae"]
        - selected_primary["component_macro_mae"]
    )
    influence_selected_minus_full = (
        selected_influence["component_macro_mae"]
        - baseline_influence["component_macro_mae"]
    )
    influence_endpoint_change = {
        endpoint: selected_influence["endpoint_component_mae"][endpoint]
        - selected_primary["endpoint_component_mae"][endpoint]
        for endpoint in compiler.ENDPOINTS
    }
    influence_selected_minus_full_endpoint = {
        endpoint: selected_influence["endpoint_component_mae"][endpoint]
        - baseline_influence["endpoint_component_mae"][endpoint]
        for endpoint in compiler.ENDPOINTS
    }

    clips: dict[str, Any] = {}
    clip_pass = True
    for name, quantiles in (
        ("OUTER_TRAIN_MINMAX_DIAGNOSTIC", None),
        ("OUTER_TRAIN_Q005_Q995_DIAGNOSTIC", (0.005, 0.995)),
    ):
        clipped = metric_summary(
            predictions=_clipped_predictions(
                predictions=selected_predictions,
                truth=truth,
                fold_map=fold_map,
                quantiles=quantiles,
            ),
            truth=truth,
            fold_map=fold_map,
            group="PRIMARY_D032",
        )
        relative_tutorial_improvement = (
            selected_primary["tutorial_primary"] - clipped["tutorial_primary"]
        ) / selected_primary["tutorial_primary"]
        component_improvement = (
            selected_primary["component_macro_mae"] - clipped["component_macro_mae"]
        )
        endpoint_component_improvement = {
            endpoint: selected_primary["endpoint_component_mae"][endpoint]
            - clipped["endpoint_component_mae"][endpoint]
            for endpoint in compiler.ENDPOINTS
        }
        passes = (
            relative_tutorial_improvement <= 0.01 and component_improvement <= 0.005
        )
        clip_pass &= passes
        clips[name] = {
            "tutorial_primary": clipped["tutorial_primary"],
            "component_macro_mae": clipped["component_macro_mae"],
            "endpoint_component_mae": clipped["endpoint_component_mae"],
            "endpoint_component_mae_improvement": endpoint_component_improvement,
            "relative_tutorial_improvement": relative_tutorial_improvement,
            "component_improvement": component_improvement,
            "pass": passes,
            "tutorial_metric_calls": clipped["tutorial_metric_calls"],
        }
    return {
        "duplicate": {
            "selected_component_macro_mae": selected_duplicate["component_macro_mae"],
            "full_component_macro_mae": baseline_duplicate["component_macro_mae"],
            "selected_endpoint_component_mae": selected_duplicate[
                "endpoint_component_mae"
            ],
            "full_endpoint_component_mae": baseline_duplicate[
                "endpoint_component_mae"
            ],
            "selected_change": duplicate_change,
            "full_change": baseline_duplicate_change,
            "selected_endpoint_change": selected_duplicate_endpoint_change,
            "full_endpoint_change": baseline_duplicate_endpoint_change,
            "pass": abs(duplicate_change) <= 0.010,
        },
        "influence": {
            "removed_component_hashes_sha256": maplight.sha256_bytes(
                maplight.json_bytes(list(top_ten))
            ),
            "components_removed": 10,
            "selected_component_macro_mae": selected_influence["component_macro_mae"],
            "full_component_macro_mae": baseline_influence["component_macro_mae"],
            "selected_endpoint_component_mae": selected_influence[
                "endpoint_component_mae"
            ],
            "full_endpoint_component_mae": baseline_influence[
                "endpoint_component_mae"
            ],
            "selected_change": influence_change,
            "selected_minus_full": influence_selected_minus_full,
            "selected_endpoint_change": influence_endpoint_change,
            "selected_minus_full_endpoint": influence_selected_minus_full_endpoint,
            "pass": abs(influence_change) <= 0.020
            and influence_selected_minus_full <= 0.005,
        },
        "source": {
            "status": "SINGLE_SOURCE_NOT_APPLICABLE",
            "source_ablations": 0,
            "pass": True,
        },
        "clipping": {
            "deployable_recipe": "NO_CLIP_PRIMARY",
            "diagnostics": clips,
            "pass": clip_pass,
        },
        "selected_candidate": selected,
        "tutorial_metric_calls": sum(
            value["tutorial_metric_calls"] for value in clips.values()
        ),
    }


def score_frozen_battery(
    *,
    selected_candidate: str,
    selection_evidence: Mapping[str, Any],
    stage_a_root: Path,
    stage_b_root: Path,
    stage_c_root: Path | None,
    scoring_capability_root: Path,
    baseline_terminal_root: Path,
    model_capability_root: Path,
    output_root: Path,
    synthetic: bool,
    consumed_claim_sha256: str | None = None,
) -> Path:
    """Score all frozen stages once and publish aggregate-only terminal evidence."""

    _require(
        not output_root.exists()
        and (
            (synthetic and consumed_claim_sha256 is None)
            or (not synthetic and compiler._is_sha(consumed_claim_sha256))
        ),
        "scientific terminal or claim authority differs",
    )
    _require(
        (selected_candidate == "G2-7-M0-FULL") == (stage_c_root is None),
        "conditional stage-C root differs",
    )
    _model_manifest, _arrays, fold_map, _molecules = _model_arrays_and_folds(
        model_capability_root, synthetic=synthetic
    )
    stage_a_rows = _prediction_stage_rows(
        stage_a_root,
        "stage_a",
        selected_candidate=None,
        synthetic=synthetic,
        model_capability_root=model_capability_root,
        fold_map=fold_map,
    )
    stage_b_rows = _prediction_stage_rows(
        stage_b_root,
        "stage_b",
        selected_candidate=selected_candidate,
        synthetic=synthetic,
        model_capability_root=model_capability_root,
        fold_map=fold_map,
    )
    stage_c_rows = (
        _prediction_stage_rows(
            stage_c_root,
            "stage_c",
            selected_candidate=selected_candidate,
            synthetic=synthetic,
            model_capability_root=model_capability_root,
            fold_map=fold_map,
        )
        if stage_c_root is not None
        else []
    )
    _scoring_manifest, truth = _scoring_truth(
        scoring_capability_root,
        synthetic=synthetic,
        model_capability_root=model_capability_root,
        fold_map=fold_map,
    )
    _baseline_manifest, baseline_all = _baseline_predictions(
        baseline_terminal_root, synthetic=synthetic, fold_map=fold_map
    )
    baseline_predictions = _matched_predictions(
        baseline_all,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
    )
    selection_payload = dict(selection_evidence)
    selection_token = selection_payload.pop("selection_token_sha256", None)
    _require(
        selection_evidence.get("selected_candidate") == selected_candidate
        and selection_evidence.get("selection_tokens") == 1
        and selection_evidence.get("runner_ups") == 0
        and selection_token
        == maplight.sha256_bytes(maplight.json_bytes(selection_payload)),
        "selection token differs",
    )
    stage_a = _prediction_index(stage_a_rows)
    stage_b = _prediction_index(stage_b_rows)
    stage_c = _prediction_index(stage_c_rows) if stage_c_rows else None
    selected_predictions = (
        baseline_predictions
        if selected_candidate == "G2-7-M0-FULL"
        else _recipe_predictions(
            stage_a,
            candidate=selected_candidate,
            seed=1,
            group="PRIMARY_D032",
            truth=truth,
            fold_map=fold_map,
        )
    )
    baseline_primary = metric_summary(
        predictions=baseline_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
    )
    selected_primary = metric_summary(
        predictions=selected_predictions,
        truth=truth,
        fold_map=fold_map,
        group="PRIMARY_D032",
    )
    seed = _seed_diagnostics(
        selected=selected_candidate,
        selected_primary=selected_primary,
        stage_a_index=stage_a,
        stage_c_index=stage_c,
        truth=truth,
        fold_map=fold_map,
    )
    grouping = _group_diagnostics(
        selected=selected_candidate,
        selected_primary_predictions=selected_predictions,
        selected_primary=selected_primary,
        stage_b_index=stage_b,
        truth=truth,
        fold_map=fold_map,
    )
    diagnostics = _aggregate_diagnostics(
        selected=selected_candidate,
        selected_predictions=selected_predictions,
        baseline_predictions=baseline_predictions,
        selected_primary=selected_primary,
        baseline_primary=baseline_primary,
        truth=truth,
        fold_map=fold_map,
    )
    tutorial_metric_calls = (
        int(selection_evidence.get("tutorial_metric_calls", -1))
        + baseline_primary["tutorial_metric_calls"]
        + selected_primary["tutorial_metric_calls"]
        + seed["tutorial_metric_calls"]
        + grouping["tutorial_metric_calls"]
        + diagnostics["tutorial_metric_calls"]
    )
    _require(
        selection_evidence.get("tutorial_metric_calls") == 20
        and 0 < tutorial_metric_calls <= MAXIMUM_TUTORIAL_METRIC_CALLS,
        "tutorial metric call accounting differs",
    )
    all_gates = {
        "selection_constituent": selection_evidence.get("selected_candidate")
        == selected_candidate,
        "seed": seed["pass"],
        "grouping": grouping["pass"],
        "duplicate": diagnostics["duplicate"]["pass"],
        "influence": diagnostics["influence"]["pass"],
        "source": diagnostics["source"]["pass"],
        "endpoint": seed["pass"] and grouping["pass"],
        "clipping": diagnostics["clipping"]["pass"],
    }
    status = (
        "G2_7G_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
        if synthetic
        else "G2_7_PRIMARY_CONTENDER_FROZEN"
        if all(all_gates.values())
        else "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED"
    )
    fit_counts = {
        "stage_a": len(mechanics._fit_identities("stage_a")),
        "stage_b": len(mechanics._fit_identities("stage_b", selected_candidate)),
        "stage_c": (
            len(mechanics._fit_identities("stage_c", selected_candidate))
            if selected_candidate != "G2-7-M0-FULL"
            else 0
        ),
    }
    prediction_counts = {
        "stage_a": len(stage_a_rows),
        "stage_b": len(stage_b_rows),
        "stage_c": len(stage_c_rows),
    }
    aggregate = {
        "selection.json": maplight.json_bytes(dict(selection_evidence)),
        "primary_metrics.json": maplight.json_bytes(
            {
                "selected_candidate": selected_candidate,
                "selected_tutorial_primary": selected_primary["tutorial_primary"],
                "full_tutorial_primary": baseline_primary["tutorial_primary"],
                "selected_component_macro_mae": selected_primary["component_macro_mae"],
                "full_component_macro_mae": baseline_primary["component_macro_mae"],
                "selected_endpoint_component_mae": selected_primary[
                    "endpoint_component_mae"
                ],
                "full_endpoint_component_mae": baseline_primary[
                    "endpoint_component_mae"
                ],
            }
        ),
        "robustness.json": maplight.json_bytes(
            {
                "seed": seed,
                "grouping": grouping,
                **diagnostics,
                "gates": all_gates,
                "tutorial_metric_calls": tutorial_metric_calls,
            }
        ),
    }
    accounting = {
        **compiler._zero_accounting(),
        "synthetic_model_fits": sum(fit_counts.values()) if synthetic else 0,
        "synthetic_predictions_generated": sum(prediction_counts.values())
        if synthetic
        else 0,
        "official_model_fits": 0 if synthetic else sum(fit_counts.values()),
        "official_predictions_generated": 0
        if synthetic
        else sum(prediction_counts.values()),
        "development_metric_evaluations": 0 if synthetic else 1,
    }
    _require(
        all(
            accounting.get(name, 0) == 0
            for name in ZERO_FORBIDDEN
            if name
            not in {
                "official_model_fits",
                "official_predictions_generated",
                "development_metric_evaluations",
            }
        ),
        "forbidden accounting differs",
    )
    manifest = {
        "schema_version": TERMINAL_SCHEMA,
        "status": status,
        "synthetic": synthetic,
        "contract_sha256": CONTRACT_SHA256,
        "consumed_claim_sha256": consumed_claim_sha256,
        "selected_candidate": selected_candidate,
        "selection_tokens": 1,
        "runner_ups": 0,
        "fit_counts": fit_counts,
        "prediction_counts": prediction_counts,
        "all_required_gates_pass": all(all_gates.values()),
        "tutorial_metric_calls": tutorial_metric_calls,
        "maximum_tutorial_metric_calls": MAXIMUM_TUTORIAL_METRIC_CALLS,
        "implementation_receipts": {
            "scientific_runner_source_sha256": maplight.sha256_path(SCRIPT),
            **{
                path.name: expected
                for path, expected in EXPECTED_ACCEPTED_SOURCES.items()
            },
        },
        "source_receipts": {
            "model_capability_manifest_sha256": maplight.sha256_path(
                model_capability_root / "manifest.json"
            ),
            "scoring_capability_manifest_sha256": maplight.sha256_path(
                scoring_capability_root / "manifest.json"
            ),
            "baseline_manifest_sha256": maplight.sha256_path(
                baseline_terminal_root / "manifest.json"
            ),
        },
        "output_receipts": {
            name: maplight.sha256_bytes(value) for name, value in aggregate.items()
        },
        "row_level_values_retained": 0,
        "model_binaries_retained": 0,
        "deployable_clips": 0,
        "accounting": accounting,
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    return maplight.publish_files(
        output_root, {**aggregate, "manifest.json": maplight.json_bytes(manifest)}
    )


def run_real_catboost_controls(*, output_root: Path) -> Path:
    """Run exactly two constructor/runtime controls with no scientific authority."""

    runtime = runtime_identity()
    controls = (
        mechanics.FitIdentity(
            "control",
            "G2-7-M0-FULL",
            1,
            "PRIMARY_D032",
            "CYP1A2",
            0,
            0,
        ),
        mechanics.FitIdentity(
            "control",
            "G2-7-M1-DROP-MORGAN",
            2026082411,
            "THRESHOLD_0_55",
            "CYP2D6",
            2,
            4,
        ),
    )
    rows: list[dict[str, Any]] = []
    for index, identity in enumerate(controls):
        supervisor.resource_checkpoint(f"before:real-control:{index}")
        width = SELECTION_FEATURE_COLUMNS[identity.candidate_id]
        training = np.arange(48 * width, dtype=np.float64).reshape(48, width)
        training = np.ascontiguousarray((training % 29) / 29.0)
        targets = np.linspace(0.0, 1.0, 48, dtype=np.float64)
        prediction = np.ascontiguousarray(training[:8] + 0.001)
        values, receipt = real_catboost_predictor(
            identity, training, targets, prediction
        )
        rows.append(
            {
                "identity_sha256": maplight.sha256_bytes(identity.token.encode()),
                "candidate_id": identity.candidate_id,
                "random_seed": identity.random_seed,
                "feature_columns": width,
                "prediction_rows": len(values),
                "resolved_parameter_sha256": receipt,
                "finite": bool(np.isfinite(values).all()),
            }
        )
        supervisor.resource_checkpoint(f"after:real-control:{index}")
    manifest = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_real_controls.v2"
        ),
        "runtime": runtime,
        "real_catboost_fits": 2,
        "controls": rows,
        "scientific_model_fits": 0,
        "model_quality_authority": False,
        "claim_authority": False,
    }
    return maplight.publish_files(
        output_root, {"manifest.json": maplight.json_bytes(manifest)}
    )


def _main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    stage = subparsers.add_parser("prediction-stage")
    stage.add_argument(
        "--stage", choices=("stage_a", "stage_b", "stage_c"), required=True
    )
    stage.add_argument("--selected-candidate", default="-")
    stage.add_argument("--model-root", type=Path, required=True)
    stage.add_argument("--output-root", type=Path, required=True)
    stage.add_argument("--synthetic-model-double", action="store_true")
    stage.add_argument("--reverse-fit-order", action="store_true")
    controls = subparsers.add_parser("real-controls")
    controls.add_argument("--output-root", type=Path, required=True)
    parsed = parser.parse_args(arguments)
    authenticate_static_boundary()
    if parsed.command == "real-controls":
        run_real_catboost_controls(output_root=parsed.output_root)
        return 0
    runtime_identity()
    selected = None if parsed.selected_candidate == "-" else parsed.selected_candidate
    run_prediction_stage(
        stage=parsed.stage,
        selected_candidate=selected,
        model_capability_root=parsed.model_root,
        output_root=parsed.output_root,
        predictor=(
            deterministic_test_predictor
            if parsed.synthetic_model_double
            else real_catboost_predictor
        ),
        checkpoint=supervisor.resource_checkpoint,
        synthetic=parsed.synthetic_model_double,
        reverse_fit_order=parsed.reverse_fit_order,
    )
    return 0


__all__ = [
    "BOOTSTRAP_MAXIMUM_ATTEMPTS",
    "BOOTSTRAP_REPLICATES",
    "CONTRACT_SHA256",
    "PREDICTION_COLUMNS",
    "PREDICTION_SCHEMA",
    "RobustnessScientificRunnerError",
    "SCRIPT",
    "TERMINAL_SCHEMA",
    "authenticate_static_boundary",
    "deterministic_test_predictor",
    "metric_summary",
    "paired_component_bootstrap",
    "real_catboost_predictor",
    "run_prediction_stage",
    "runtime_identity",
    "run_real_catboost_controls",
    "score_frozen_battery",
    "select_stage_a_candidate",
]


if __name__ == "__main__":
    raise SystemExit(_main())
