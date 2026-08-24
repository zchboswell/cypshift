#!/usr/bin/env python3
"""Run one raw or fold-local-quantized EXP-G1 resource probe mode."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

import global_v2_g1_execution_wrapper as wrapper
import global_v2_g1_runner as g1
import global_v2_maplight_runner as base
import numpy as np

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
CONTRACT: Final = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_v2_g1_resource_feasibility_contract.json"
)
CONTRACT_SHA256: Final = (
    "173273102393794ec345782ad8298d66d675a91d3569301ea3fd3e0297b24a92"
)
OPTIMIZATION_ID: Final = "FOLD_LOCAL_QUANTIZED_POOL_REUSE_V1"
PROBE_ENDPOINT: Final = "CYP1A2"
PROBE_REPEAT: Final = 0
PROBE_OUTER: Final = 0
PROBE_IDENTITIES: Final = (
    *((configuration, g1.MODEL_SEEDS[0]) for configuration in g1.CONFIGURATION_IDS),
    (g1.CONFIGURATION_IDS[0], g1.MODEL_SEEDS[1]),
    (g1.CONFIGURATION_IDS[0], g1.MODEL_SEEDS[2]),
)
PROBE_SCHEMA: Final = "cypshift.openadmet_cyp_2026.global_v2_g1_resource_probe_mode.v1"


class G1ResourceFeasibilityError(RuntimeError):
    """Raised when the bounded resource falsifier fails closed."""

    def __init__(
        self,
        message: str,
        *,
        completed_fits: int = 0,
        prediction_values: int = 0,
    ) -> None:
        super().__init__(message)
        self.completed_fits = completed_fits
        self.prediction_values = prediction_values


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G1ResourceFeasibilityError(message)


def _static_contract() -> dict[str, Any]:
    _require(base.sha256_path(CONTRACT) == CONTRACT_SHA256, "contract receipt differs")
    contract, _raw = base._load_json(CONTRACT)
    _require(
        contract.get("gate") == "G2_3D_EXP_G1_RESOURCE_FEASIBILITY_CONTRACT_FROZEN"
        and contract["single_optimization"]["optimization_id"] == OPTIMIZATION_ID
        and contract["resource_measurement"]["thread_count_per_fit"] == 16
        and contract["resource_measurement"]["maximum_concurrent_catboost_fits"] == 1,
        "resource contract identity differs",
    )
    accepted = contract["accepted_implementation"]
    for path_key, sha_key in (
        ("compiler_path", "compiler_sha256"),
        ("wrapper_path", "wrapper_sha256"),
        ("synthetic_driver_path", "synthetic_driver_sha256"),
        ("focused_tests_path", "focused_tests_sha256"),
        ("research_lock_path", "research_lock_sha256"),
    ):
        _require(
            base.sha256_path(ROOT / accepted[path_key]) == accepted[sha_key],
            f"accepted implementation receipt differs: {path_key}",
        )
    return contract


def _array_receipt(array: np.ndarray[Any, Any]) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(contiguous.dtype.str.encode("ascii"))
    digest.update(b"|")
    digest.update(",".join(str(value) for value in contiguous.shape).encode("ascii"))
    digest.update(b"|")
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def cache_identity(
    *,
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
    model_manifest_sha256: str,
) -> str:
    """Bind quantized reuse to exact ordered arrays, runtime, and probe fold."""

    payload = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_g1_quantized_pool_cache.v1"
        ),
        "optimization_id": OPTIMIZATION_ID,
        "model_capability_manifest_sha256": model_manifest_sha256,
        "endpoint": PROBE_ENDPOINT,
        "repeat": PROBE_REPEAT,
        "outer_fold": PROBE_OUTER,
        "feature_width": g1.FEATURE_WIDTH,
        "training_sha256": _array_receipt(training),
        "targets_sha256": _array_receipt(targets),
        "prediction_sha256": _array_receipt(prediction),
        "runtime": wrapper._runtime_identity(),
    }
    return base.sha256_bytes(base.json_bytes(payload))


def _probe_arrays(
    model_capability_root: Path,
) -> tuple[
    np.ndarray[Any, Any],
    np.ndarray[Any, Any],
    np.ndarray[Any, Any],
    str,
]:
    _manifest, molecules, _components, folds, matrix = wrapper._load_model(
        model_capability_root
    )
    index = {molecule: position for position, molecule in enumerate(molecules)}
    training_ids, prediction_ids = wrapper._cell_ids(
        molecules,
        folds,
        repeat=PROBE_REPEAT,
        outer=PROBE_OUTER,
        inner=None,
    )
    targets = wrapper._targets(
        model_capability_root,
        stage="outer",
        endpoint=PROBE_ENDPOINT,
        repeat=PROBE_REPEAT,
        outer=PROBE_OUTER,
        inner=None,
    )
    target_map = {
        row["molecule_id"]: wrapper._float(row["point"], "probe target")
        for row in targets
    }
    fitted = [molecule for molecule in training_ids if molecule in target_map]
    _require(
        len(fitted) >= 48
        and bool(prediction_ids)
        and len(fitted) == len(targets)
        and set(target_map).issubset(training_ids),
        "runtime probe support differs",
    )
    training = np.ascontiguousarray(
        matrix[[index[molecule] for molecule in fitted]], dtype=np.float32
    )
    target_values = np.ascontiguousarray(
        [target_map[molecule] for molecule in fitted], dtype=np.float64
    )
    prediction = np.ascontiguousarray(
        matrix[[index[molecule] for molecule in prediction_ids]], dtype=np.float32
    )
    return (
        training,
        target_values,
        prediction,
        base.sha256_path(model_capability_root / "manifest.json"),
    )


def _prediction_receipt(values: np.ndarray[Any, Any]) -> str:
    exact = np.ascontiguousarray(values, dtype="<f8")
    return base.sha256_bytes(exact.tobytes(order="C"))


def _row(
    *,
    configuration_id: str,
    model_seed: int,
    values: np.ndarray[Any, Any],
    resolved_parameter_sha256: str,
    training_rows: int,
    prediction_rows: int,
) -> dict[str, object]:
    _require(
        values.shape == (prediction_rows,) and bool(np.isfinite(values).all()),
        "probe prediction differs",
    )
    return {
        "configuration_id": configuration_id,
        "model_seed": model_seed,
        "resolved_parameter_sha256": resolved_parameter_sha256,
        "prediction_float64_sha256": _prediction_receipt(values),
        "training_rows": training_rows,
        "prediction_rows": prediction_rows,
        "finite_predictions": True,
    }


def _reference_index(
    reference_path: Path | None,
) -> dict[tuple[str, int], dict[str, Any]]:
    if reference_path is None:
        return {}
    reference, _raw = base._load_json(reference_path)
    _require(
        reference.get("schema_version") == PROBE_SCHEMA
        and reference.get("mode") == "accepted_raw_array_reference"
        and reference.get("status") == "G2_3D_PROBE_MODE_COMPLETE",
        "reference probe identity differs",
    )
    rows = reference.get("probe_rows")
    _require(isinstance(rows, list) and len(rows) == 14, "reference rows differ")
    return {
        (cast(str, row["configuration_id"]), cast(int, row["model_seed"])): row
        for row in rows
    }


def _assert_equivalent(
    row: Mapping[str, object], reference: Mapping[str, object]
) -> None:
    for key in (
        "configuration_id",
        "model_seed",
        "resolved_parameter_sha256",
        "prediction_float64_sha256",
        "training_rows",
        "prediction_rows",
        "finite_predictions",
    ):
        _require(row[key] == reference[key], f"exact equivalence differs: {key}")


def _raw_rows(
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
    reference: Mapping[tuple[str, int], Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for position, (configuration_id, model_seed) in enumerate(PROBE_IDENTITIES):
        values, resolved = wrapper.real_predictor(
            configuration_id, model_seed, training, targets, prediction
        )
        row = _row(
            configuration_id=configuration_id,
            model_seed=model_seed,
            values=values,
            resolved_parameter_sha256=resolved,
            training_rows=len(training),
            prediction_rows=len(prediction),
        )
        if reference:
            try:
                _assert_equivalent(row, reference[configuration_id, model_seed])
            except G1ResourceFeasibilityError as error:
                raise G1ResourceFeasibilityError(
                    f"{error}; identity={configuration_id}/{model_seed}",
                    completed_fits=position + 1,
                    prediction_values=(position + 1) * len(prediction),
                ) from error
        rows.append(row)
    return rows


def _optimized_rows(
    training: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    prediction: np.ndarray[Any, Any],
    reference: Mapping[tuple[str, int], Mapping[str, object]],
) -> list[dict[str, object]]:
    try:
        from catboost import (  # type: ignore[import-not-found]  # noqa: PLC0415
            CatBoostRegressor,
            Pool,
        )
    except ImportError as error:
        raise G1ResourceFeasibilityError("CatBoost 1.2.1 is unavailable") from error

    configurations, common = wrapper._screen()
    with tempfile.TemporaryDirectory(prefix="cypshift-g1-quantized-") as temporary:
        border_path = Path(temporary) / "training-borders.tsv"
        training_pool = Pool(training, label=targets)
        training_pool.quantize(
            border_count=254,
            feature_border_type="GreedyLogSum",
            nan_mode="Min",
            task_type="CPU",
            random_seed=g1.MODEL_SEEDS[0],
        )
        _require(training_pool.is_quantized(), "training Pool is not quantized")
        training_pool.save_quantization_borders(border_path)
        _require(
            border_path.is_file()
            and not border_path.is_symlink()
            and border_path.stat().st_size > 0,
            "training borders differ",
        )
        prediction_pool = Pool(prediction)
        prediction_pool.quantize(input_borders=border_path, task_type="CPU")
        _require(prediction_pool.is_quantized(), "prediction Pool is not quantized")

        rows: list[dict[str, object]] = []
        for position, (configuration_id, model_seed) in enumerate(PROBE_IDENTITIES):
            constructor = {
                **configurations[configuration_id],
                **common,
                "random_seed": model_seed,
            }
            model = CatBoostRegressor(**constructor)
            _require(model.get_params() == constructor, "CatBoost constructor differs")
            model.fit(training_pool)
            resolved = cast(dict[str, Any], model.get_all_params())
            _require(
                resolved.get("random_seed") == model_seed,
                "resolved CatBoost seed differs",
            )
            values = np.asarray(model.predict(prediction_pool), dtype=np.float64)
            row = _row(
                configuration_id=configuration_id,
                model_seed=model_seed,
                values=values,
                resolved_parameter_sha256=base.sha256_bytes(base.json_bytes(resolved)),
                training_rows=len(training),
                prediction_rows=len(prediction),
            )
            _require(
                (configuration_id, model_seed) in reference,
                "optimized reference identity is missing",
            )
            try:
                _assert_equivalent(row, reference[configuration_id, model_seed])
            except G1ResourceFeasibilityError as error:
                raise G1ResourceFeasibilityError(
                    f"{error}; identity={configuration_id}/{model_seed}",
                    completed_fits=position + 1,
                    prediction_values=(position + 1) * len(prediction),
                ) from error
            rows.append(row)
    _require(not Path(temporary).exists(), "temporary quantization state remains")
    return rows


def run_probe_mode(
    *,
    model_capability_root: Path,
    mode: str,
    output_root: Path,
    reference_path: Path | None,
) -> Path:
    """Run one fresh mode and publish aggregate exact-prediction receipts."""

    contract = _static_contract()
    wrapper._runtime_identity()
    _require(
        mode in {"accepted_raw_array_reference", "fold_local_quantized_pool_reuse"},
        "probe mode differs",
    )
    _require(
        not output_root.exists() and not output_root.is_symlink(),
        "probe output exists",
    )
    reference = _reference_index(reference_path)
    _require(
        (mode == "accepted_raw_array_reference") or bool(reference),
        "optimized mode requires a complete raw reference",
    )
    training, targets, prediction, model_manifest_sha256 = _probe_arrays(
        model_capability_root
    )
    started = time.monotonic_ns()
    process_started = os.times()
    rows = (
        _raw_rows(training, targets, prediction, reference)
        if mode == "accepted_raw_array_reference"
        else _optimized_rows(training, targets, prediction, reference)
    )
    process_finished = os.times()
    elapsed_ns = time.monotonic_ns() - started
    _require(len(rows) == 14, "probe identity count differs")
    result = {
        "schema_version": PROBE_SCHEMA,
        "status": "G2_3D_PROBE_MODE_COMPLETE",
        "mode": mode,
        "optimization_id": OPTIMIZATION_ID,
        "contract_sha256": CONTRACT_SHA256,
        "implementation_source_sha256": base.sha256_path(SCRIPT),
        "model_capability_manifest_sha256": model_manifest_sha256,
        "cache_identity_sha256": cache_identity(
            training=training,
            targets=targets,
            prediction=prediction,
            model_manifest_sha256=model_manifest_sha256,
        ),
        "probe_rows": rows,
        "counts": {
            "real_catboost_fits": 14,
            "training_rows": len(training),
            "prediction_rows": len(prediction),
            "prediction_values": len(prediction) * 14,
        },
        "in_process_telemetry": {
            "elapsed_ns": elapsed_ns,
            "user_cpu_seconds": process_finished.user - process_started.user,
            "system_cpu_seconds": process_finished.system - process_started.system,
        },
        "accounting": {
            "synthetic_catboost_fits": 14,
            "synthetic_predictions_generated": len(prediction) * 14,
            "official_target_values_opened": 0,
            "official_features_opened": 0,
            "official_model_fits": 0,
            "official_predictions_generated": 0,
            "development_metric_evaluations": 0,
            "confirmatory_truth_values_opened": 0,
            "historical_r3c_row_level_artifacts_opened": 0,
            "blinded_test_files_opened": 0,
            "tdi_files_opened": 0,
            "external_records_acquired": 0,
            "submissions_created": 0,
            "official_metric_evaluations": 0,
            "leaderboard_observations": 0,
            "live_uploads": 0,
            "claim_consumptions": 0,
        },
        "authority": contract["current_authority"],
    }
    return cast(
        Path,
        base.publish_files(output_root, {"probe.json": base.json_bytes(result)}),
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-capability-root", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("accepted_raw_array_reference", "fold_local_quantized_pool_reuse"),
        required=True,
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    try:
        run_probe_mode(
            model_capability_root=args.model_capability_root,
            mode=args.mode,
            output_root=args.output_root,
            reference_path=args.reference,
        )
    except G1ResourceFeasibilityError as error:
        failure = {
            "schema_version": (
                "cypshift.openadmet_cyp_2026.global_v2_g1_resource_probe_failure.v1"
            ),
            "status": "G2_3D_PROBE_MODE_REJECTED",
            "mode": args.mode,
            "optimization_id": OPTIMIZATION_ID,
            "contract_sha256": CONTRACT_SHA256,
            "implementation_source_sha256": base.sha256_path(SCRIPT),
            "failure": str(error),
            "completed_real_catboost_fits": error.completed_fits,
            "synthetic_predictions_generated": error.prediction_values,
            "claim_consumptions": 0,
            "official_operations": 0,
            "forbidden_operations": 0,
        }
        if not args.output_root.exists() and not args.output_root.is_symlink():
            base.publish_files(
                args.output_root, {"failure.json": base.json_bytes(failure)}
            )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
