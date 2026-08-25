#!/usr/bin/env python3
"""Deterministic synthetic mechanics and exact LightGBM primitives for EXP-G3."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import warnings
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH: Final = BENCHMARK / "global_v2_g3_synthetic_contract.json"
PARENT_PATH: Final = BENCHMARK / "global_v2_g3_single_expert_contract.json"
CONTRACT_SHA256: Final = hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()
PARENT_SHA256: Final = hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest()
EXPECTED_CONTRACT_SHA256: Final = (
    "6ec0e73bb7c62a4b0c01987f1ef51bc964cc07b17d307c95f8c90f7574da4f9f"
)
EXPECTED_PARENT_SHA256: Final = (
    "ee2725ba2ea634fab7db35aa9b2d0e396b5f46feac3d1819891cc240bd25da47"
)
ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
REPEAT_SEEDS: Final = (20260810, 20260811, 20260812)
OUTER_FOLDS: Final = tuple(range(5))
SYSTEM_ID: Final = "EXP-G3-LGBM-L1-FIXED"
FEATURE_WIDTH: Final = 2248
MORGAN_WIDTH: Final = 2048
DESCRIPTOR_WIDTH: Final = 200
FIXTURE_SEED: Final = 20260901
NUM_BOOST_ROUND: Final = 1500
PROBE_ROWS: Final = 3908
PROBE_TRAIN_ROWS: Final = 3120
PROBE_PREDICT_ROWS: Final = 788
TERMINAL_NAMES: Final = (
    "g3_synthetic_feature_receipt.json",
    "g3_synthetic_fit_identity_receipts.csv",
    "g3_synthetic_outer_predictions.csv",
    "g3_synthetic_metrics.json",
    "g3_probe_parameter_receipts.csv",
    "g3_probe_predictions.csv",
    "g3_synthetic_terminal_manifest.json",
)
OFFICIAL_ZERO_FIELDS: Final = (
    "official_inputs_opened",
    "official_model_fits",
    "official_predictions",
    "development_metrics",
    "confirmatory_truth_values_opened",
    "historical_row_level_artifacts_opened",
    "blinded_test_rows_opened",
    "tdi_rows_opened",
    "external_records_opened",
    "submission_rows_generated",
    "official_metric_calls",
    "leaderboard_observations_used_for_selection",
    "live_uploads",
    "claims_created_or_consumed",
)


class G3Error(RuntimeError):
    """Fail-closed EXP-G3 contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise G3Error(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def csv_bytes(fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def static_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    require(
        CONTRACT_SHA256 == EXPECTED_CONTRACT_SHA256, "G3 synthetic contract differs"
    )
    require(PARENT_SHA256 == EXPECTED_PARENT_SHA256, "G3 parent contract differs")
    contract = cast(dict[str, Any], json.loads(CONTRACT_PATH.read_text()))
    parent = cast(dict[str, Any], json.loads(PARENT_PATH.read_text()))
    require(
        contract["parents"]["g3_single_expert_contract"]["sha256"] == PARENT_SHA256,
        "G3 contract parent binding differs",
    )
    require(
        tuple(parent["population_and_splits"]["repeat_seeds"]) == REPEAT_SEEDS,
        "repeat seeds differ",
    )
    require(
        parent["population_and_splits"]["outer_folds"] == 5, "outer fold count differs"
    )
    require(parent["model_contract"]["system_id"] == SYSTEM_ID, "system id differs")
    require(
        parent["model_contract"]["num_boost_round"] == NUM_BOOST_ROUND,
        "tree count differs",
    )
    return contract, parent


def model_parameters() -> dict[str, object]:
    _contract, parent = static_contract()
    return cast(dict[str, object], dict(parent["model_contract"]["parameters"]))


def parameter_receipt() -> dict[str, object]:
    parameters = model_parameters()
    payload = {"num_boost_round": NUM_BOOST_ROUND, "parameters": parameters}
    return {**payload, "sha256": sha256_bytes(json_bytes(payload))}


def component_pool() -> tuple[list[str], list[str]]:
    development: list[str] = []
    confirmatory: list[str] = []
    counter = 0
    while len(development) < 40 or len(confirmatory) < 10:
        component = hashlib.sha256(
            f"cypshift-g3-synthetic-component-v1|{counter}".encode()
        ).hexdigest()
        material = f"openadmet-global-v2-confirmatory-v1|20260824|{component}"
        value = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")
        target = confirmatory if value % 5 == 0 else development
        limit = 10 if target is confirmatory else 40
        if len(target) < limit:
            target.append(component)
        counter += 1
    return development, confirmatory


def build_fixture(*, reverse: bool = False) -> dict[str, list[dict[str, object]]]:
    development, confirmatory = component_pool()
    components = development + confirmatory
    molecules: list[dict[str, object]] = []
    truth: list[dict[str, object]] = []
    for index in range(100):
        molecule_id = f"g3-synthetic-{index:03d}"
        component = components[index // 2]
        partition = "development" if index < 80 else "confirmatory"
        molecules.append(
            {
                "molecule_id": molecule_id,
                "molecule_index": index,
                "component": component,
                "partition": partition,
            }
        )
        if partition == "development":
            for endpoint_index, endpoint in enumerate(ENDPOINTS):
                finite = (index + endpoint_index) % 5 != 0
                truth.append(
                    {
                        "molecule_id": molecule_id,
                        "molecule_index": index,
                        "component": component,
                        "endpoint": endpoint,
                        "central": (
                            4.0
                            + 0.025 * index
                            + 0.2 * endpoint_index
                            + 0.05 * ((7 * index + endpoint_index) % 5)
                        )
                        if finite
                        else None,
                    }
                )
    folds: list[dict[str, object]] = []
    molecules_by_component = {
        component: [
            cast(str, row["molecule_id"])
            for row in molecules
            if row["component"] == component
        ]
        for component in development
    }
    for repeat_seed in REPEAT_SEEDS:
        ordered = sorted(
            development,
            key=lambda component: hashlib.sha256(
                f"{repeat_seed}|OUTER|{component}".encode()
            ).hexdigest(),
        )
        fold_by_component = {
            component: rank % 5 for rank, component in enumerate(ordered)
        }
        for component in development:
            for molecule_id in molecules_by_component[component]:
                folds.append(
                    {
                        "molecule_id": molecule_id,
                        "component": component,
                        "repeat_seed": repeat_seed,
                        "outer_fold": fold_by_component[component],
                    }
                )
    if reverse:
        molecules.reverse()
        truth.reverse()
        folds.reverse()
    return {"molecules": molecules, "development_truth": truth, "folds": folds}


def build_feature_matrix(
    row_indices: Sequence[int] | np.ndarray[Any, Any], *, reverse_physical: bool = False
) -> np.ndarray[Any, Any]:
    canonical = np.asarray(row_indices, dtype=np.int64)
    require(
        canonical.ndim == 1 and len(set(canonical.tolist())) == canonical.size,
        "feature row identities differ",
    )
    physical = canonical[::-1] if reverse_physical else canonical.copy()
    rows_u = physical.astype(np.uint64)[:, None]
    morgan_j = np.arange(MORGAN_WIDTH, dtype=np.uint64)[None, :]
    expression = (
        np.uint64(1315423911) * rows_u
        + np.uint64(2654435761) * morgan_j
        + np.uint64(FIXTURE_SEED)
    ) % np.uint64(64)
    morgan = np.where(expression < 2, 1 + expression % 3, 0).astype(np.float64)
    descriptor_j = np.arange(DESCRIPTOR_WIDTH, dtype=np.uint64)[None, :]
    descriptor_expression = (
        np.uint64(37) * rows_u + np.uint64(53) * descriptor_j + np.uint64(FIXTURE_SEED)
    )
    descriptor = (
        (
            np.uint64(17) * rows_u
            + np.uint64(31) * descriptor_j
            + np.uint64(FIXTURE_SEED)
        )
        % np.uint64(1009)
    ).astype(np.float64) / 1009.0
    descriptor[descriptor_expression % np.uint64(29) == 0] = np.nan
    matrix = np.concatenate((morgan, descriptor), axis=1)
    if reverse_physical:
        matrix = np.ascontiguousarray(matrix[::-1])
    require(matrix.shape == (canonical.size, FEATURE_WIDTH), "feature shape differs")
    require(
        matrix.flags.c_contiguous and matrix.dtype == np.float64,
        "feature representation differs",
    )
    require(not np.isinf(matrix).any(), "feature infinity detected")
    return matrix


def little_f8_bytes(array: np.ndarray[Any, Any]) -> bytes:
    return np.asarray(array, dtype="<f8", order="C").tobytes(order="C")


def feature_receipt(fixture: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    molecules = sorted(fixture["molecules"], key=lambda row: int(row["molecule_index"]))
    indices = [int(row["molecule_index"]) for row in molecules]
    matrix = build_feature_matrix(indices)
    components = [str(row["component"]) for row in molecules]
    return {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_synthetic_feature_receipt.v1",
        "contract_sha256": CONTRACT_SHA256,
        "rows": matrix.shape[0],
        "columns": matrix.shape[1],
        "morgan_columns": MORGAN_WIDTH,
        "descriptor_columns": DESCRIPTOR_WIDTH,
        "development_molecules": sum(
            row["partition"] == "development" for row in molecules
        ),
        "confirmatory_molecules": sum(
            row["partition"] == "confirmatory" for row in molecules
        ),
        "components": len(set(components)),
        "descriptor_nan_values": int(np.isnan(matrix[:, MORGAN_WIDTH:]).sum()),
        "infinite_values": int(np.isinf(matrix).sum()),
        "feature_bytes_sha256": sha256_bytes(little_f8_bytes(matrix)),
        "canonical_identity_sha256": sha256_bytes(json_bytes(indices)),
        "confirmatory_truth_values_parsed": 0,
    }


@dataclass(frozen=True)
class ModelCapability:
    """The complete and intentionally narrow capability of one model-double fit."""

    training_target_rows: tuple[str, ...]
    training_feature_rows: tuple[str, ...]
    validation_feature_rows: tuple[str, ...]
    parameter_receipt_sha256: str
    identity_token: str


FIT_FIELDS: Final = (
    "fit_id",
    "system_id",
    "repeat_seed",
    "outer_fold",
    "endpoint",
    "training_components_sha256",
    "validation_components_sha256",
    "training_molecules",
    "validation_molecules",
    "feature_receipt_sha256",
    "parameter_receipt_sha256",
)
PREDICTION_FIELDS: Final = (
    "molecule_id",
    "component",
    "endpoint",
    "repeat_seed",
    "outer_fold",
    "prediction",
    "fit_id",
)
PROBE_PARAMETER_FIELDS: Final = (
    "endpoint",
    "resolved_parameter_sha256",
    "num_boost_round",
    "training_rows",
    "prediction_rows",
    "columns",
)
PROBE_PREDICTION_FIELDS: Final = ("endpoint", "row_index", "prediction")


def model_double_files(*, reverse_execution_order: bool = False) -> dict[str, bytes]:
    fixture = build_fixture(reverse=reverse_execution_order)
    feature = feature_receipt(fixture)
    feature_sha = sha256_bytes(json_bytes(feature))
    parameter_sha = cast(str, parameter_receipt()["sha256"])
    molecules = {
        str(row["molecule_id"]): row
        for row in fixture["molecules"]
        if row["partition"] == "development"
    }
    fold_rows = list(fixture["folds"])
    contexts = [
        (repeat_seed, outer_fold, endpoint_index, endpoint)
        for repeat_seed in REPEAT_SEEDS
        for outer_fold in OUTER_FOLDS
        for endpoint_index, endpoint in enumerate(ENDPOINTS)
    ]
    if reverse_execution_order:
        contexts.reverse()
    fit_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    for repeat_seed, outer_fold, endpoint_index, endpoint in contexts:
        validation_ids = sorted(
            str(row["molecule_id"])
            for row in fold_rows
            if row["repeat_seed"] == repeat_seed and row["outer_fold"] == outer_fold
        )
        training_ids = sorted(set(molecules) - set(validation_ids))
        training_components = sorted(
            {str(molecules[value]["component"]) for value in training_ids}
        )
        validation_components = sorted(
            {str(molecules[value]["component"]) for value in validation_ids}
        )
        require(
            training_components and validation_components, "empty component partition"
        )
        require(
            not set(training_components) & set(validation_components),
            "component crossed a fit boundary",
        )
        identity_payload = [
            "cypshift.openadmet_cyp_2026.g3_fit_identity.v1",
            SYSTEM_ID,
            repeat_seed,
            outer_fold,
            endpoint,
            training_components,
            validation_components,
            feature_sha,
            parameter_sha,
        ]
        fit_id = sha256_bytes(json_bytes(identity_payload))
        capability = ModelCapability(
            training_target_rows=tuple(training_ids),
            training_feature_rows=tuple(training_ids),
            validation_feature_rows=tuple(validation_ids),
            parameter_receipt_sha256=parameter_sha,
            identity_token=fit_id,
        )
        require(
            capability.training_target_rows == capability.training_feature_rows,
            "training capability differs",
        )
        fit_rows.append(
            {
                "fit_id": fit_id,
                "system_id": SYSTEM_ID,
                "repeat_seed": repeat_seed,
                "outer_fold": outer_fold,
                "endpoint": endpoint,
                "training_components_sha256": sha256_bytes(
                    json_bytes(training_components)
                ),
                "validation_components_sha256": sha256_bytes(
                    json_bytes(validation_components)
                ),
                "training_molecules": len(training_ids),
                "validation_molecules": len(validation_ids),
                "feature_receipt_sha256": feature_sha,
                "parameter_receipt_sha256": parameter_sha,
            }
        )
        repeat_index = REPEAT_SEEDS.index(repeat_seed)
        for molecule_id in validation_ids:
            molecule_index = int(molecules[molecule_id]["molecule_index"])
            prediction = (
                3.5
                + 0.02 * molecule_index
                + 0.15 * endpoint_index
                + 0.001 * repeat_index
                + 0.0001 * outer_fold
            )
            prediction_rows.append(
                {
                    "molecule_id": molecule_id,
                    "component": str(molecules[molecule_id]["component"]),
                    "endpoint": endpoint,
                    "repeat_seed": repeat_seed,
                    "outer_fold": outer_fold,
                    "prediction": format(prediction, ".17g"),
                    "fit_id": fit_id,
                }
            )
    fit_rows.sort(key=lambda row: str(row["fit_id"]))
    prediction_rows.sort(
        key=lambda row: (
            int(row["repeat_seed"]),
            int(row["outer_fold"]),
            str(row["endpoint"]),
            str(row["molecule_id"]),
        )
    )
    require(
        len(fit_rows) == 60 and len({row["fit_id"] for row in fit_rows}) == 60,
        "fit topology differs",
    )
    require(len(prediction_rows) == 960, "prediction topology differs")
    truth = {
        (str(row["molecule_id"]), str(row["endpoint"])): float(row["central"])
        for row in fixture["development_truth"]
        if row["central"] is not None
    }
    absolute_errors = [
        abs(
            float(row["prediction"])
            - truth[(str(row["molecule_id"]), str(row["endpoint"]))]
        )
        for row in prediction_rows
        if (str(row["molecule_id"]), str(row["endpoint"])) in truth
    ]
    metrics = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_synthetic_metrics.v1",
        "contract_sha256": CONTRACT_SHA256,
        "truth_resolved_after_prediction_freeze": True,
        "finite_truth_rows_per_endpoint": {endpoint: 64 for endpoint in ENDPOINTS},
        "scored_outer_prediction_rows": len(absolute_errors),
        "synthetic_mean_absolute_error": format(
            sum(absolute_errors) / len(absolute_errors), ".17g"
        ),
        "model_quality_authority": False,
        "scientific_interpretation": "Synthetic mechanics only; metric magnitude has no model-quality meaning.",
    }
    return {
        TERMINAL_NAMES[0]: json_bytes(feature),
        TERMINAL_NAMES[1]: csv_bytes(FIT_FIELDS, fit_rows),
        TERMINAL_NAMES[2]: csv_bytes(PREDICTION_FIELDS, prediction_rows),
        TERMINAL_NAMES[3]: json_bytes(metrics),
    }


def probe_matrix(
    *, reverse_physical: bool
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    matrix = build_feature_matrix(
        np.arange(PROBE_ROWS), reverse_physical=reverse_physical
    )
    targets = np.empty((PROBE_TRAIN_ROWS, len(ENDPOINTS)), dtype=np.float64)
    first_morgan = matrix[:PROBE_TRAIN_ROWS, :16].sum(axis=1)
    for endpoint_index in range(len(ENDPOINTS)):
        descriptor = np.nan_to_num(
            matrix[:PROBE_TRAIN_ROWS, MORGAN_WIDTH + endpoint_index], nan=0.0
        )
        index_term = np.arange(PROBE_TRAIN_ROWS, dtype=np.float64) % 101
        targets[:, endpoint_index] = (
            4.0
            + 0.2 * endpoint_index
            + 0.03 * descriptor
            + 0.01 * first_morgan
            + 0.0001 * index_term
        )
    require(np.isfinite(targets).all(), "probe target is nonfinite")
    return matrix[:PROBE_TRAIN_ROWS], matrix[PROBE_TRAIN_ROWS:], targets


def _normalized_parameter_value(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    return value


def fit_exact_lightgbm(
    train_features: np.ndarray[Any, Any],
    train_target: np.ndarray[Any, Any],
    prediction_features: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], dict[str, object]]:
    import lightgbm as lgb

    require(
        train_features.shape == (PROBE_TRAIN_ROWS, FEATURE_WIDTH),
        "probe training shape differs",
    )
    require(
        prediction_features.shape == (PROBE_PREDICT_ROWS, FEATURE_WIDTH),
        "probe prediction shape differs",
    )
    require(train_target.shape == (PROBE_TRAIN_ROWS,), "probe target shape differs")
    require(
        not np.isinf(train_features).any() and not np.isinf(prediction_features).any(),
        "probe infinity detected",
    )
    parameters = model_parameters()
    dataset = lgb.Dataset(train_features, label=train_target, free_raw_data=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        booster = lgb.train(parameters, dataset, num_boost_round=NUM_BOOST_ROUND)
        predictions = np.asarray(booster.predict(prediction_features), dtype=np.float64)
    require(not caught, f"LightGBM emitted {len(caught)} Python warnings")
    require(
        predictions.shape == (PROBE_PREDICT_ROWS,), "probe prediction count differs"
    )
    require(np.isfinite(predictions).all(), "probe prediction is nonfinite")
    resolved = {
        name: _normalized_parameter_value(booster.params[name]) for name in parameters
    }
    require(resolved == parameters, "resolved LightGBM parameters differ")
    require(
        int(booster.current_iteration()) == NUM_BOOST_ROUND,
        "resolved tree count differs",
    )
    return predictions, {
        "num_boost_round": NUM_BOOST_ROUND,
        "parameters": resolved,
    }


def complete_terminal_files(
    *,
    model_double: dict[str, bytes],
    probe_parameter_rows: list[dict[str, object]],
    probe_prediction_rows: list[dict[str, object]],
) -> dict[str, bytes]:
    require(
        set(model_double) == set(TERMINAL_NAMES[:4]),
        "model-double terminal set differs",
    )
    probe_parameter_rows.sort(key=lambda row: str(row["endpoint"]))
    probe_prediction_rows.sort(
        key=lambda row: (str(row["endpoint"]), int(row["row_index"]))
    )
    require(len(probe_parameter_rows) == 4, "probe parameter receipt count differs")
    require(
        len(probe_prediction_rows) == 3152, "probe prediction receipt count differs"
    )
    files = dict(model_double)
    files[TERMINAL_NAMES[4]] = csv_bytes(PROBE_PARAMETER_FIELDS, probe_parameter_rows)
    files[TERMINAL_NAMES[5]] = csv_bytes(PROBE_PREDICTION_FIELDS, probe_prediction_rows)
    hashes = {name: sha256_bytes(files[name]) for name in TERMINAL_NAMES[:6]}
    manifest = {
        "schema_version": "cypshift.openadmet_cyp_2026.g3_synthetic_terminal_manifest.v1",
        "contract_sha256": CONTRACT_SHA256,
        "relative_files": hashes,
        "deterministic_tree_sha256": sha256_bytes(json_bytes(hashes)),
        "model_double_fits": 60,
        "model_double_outer_predictions": 960,
        "real_lightgbm_fits": 4,
        "real_lightgbm_predictions": 3152,
        "accounting": {name: 0 for name in OFFICIAL_ZERO_FIELDS},
        "scientific_interpretation": "Synthetic mechanics and resources only; no model-quality interpretation.",
    }
    files[TERMINAL_NAMES[6]] = json_bytes(manifest)
    require(set(files) == set(TERMINAL_NAMES), "terminal file set differs")
    return files


static_contract()
