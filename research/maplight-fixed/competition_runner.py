#!/usr/bin/env python3
"""Recoverable Phase 3 nested MapLight and inner-OOF calibration experiment.

Only authenticated development targets enter this process. Each complete fit is
cached by all model inputs and implementation/runtime identity. The reserved
comparison and blinded-test features are not part of this evaluator.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
from catboost import CatBoostRegressor
from competition_data import balanced_nested_folds, load_development
from competition_metrics import (
    direct_scores,
    interval_distance,
    paired_family_difference,
    release_decision,
)
from scipy import sparse
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[2]
CORRECTED_RECIPE = (
    ROOT / "benchmarks/openadmet_cyp_2026/phase3_corrected_counts_ablation_v1.json"
)
PARAMETERS = {
    "loss_function": "MAE",
    "random_strength": 2,
    "random_seed": 1,
    "task_type": "CPU",
    "thread_count": 16,
    "verbose": 0,
    "allow_writing_files": False,
}


def model_parameters(loss: str = "MAE") -> dict[str, Any]:
    """Preserve legacy MAE; prevent RMSE from choosing an automatic learning rate.

    All 80 original MAE receipts resolve depth=6, iterations=1000, and learning
    rate=0.029999999329447743 (CatBoost's float32 representation of 0.03).
    Objective-specific optimization defaults remain native and are recorded.
    """
    if loss == "MAE":
        return dict(PARAMETERS)
    if loss == "RMSE":
        return {
            **PARAMETERS,
            "loss_function": "RMSE",
            "learning_rate": 0.03,
            "iterations": 1000,
            "depth": 6,
        }
    raise ValueError("Only the frozen MAE and RMSE objectives are supported")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def publish(path: Path, raw: bytes) -> None:
    """Atomically finish a file; callers hold the run lock and verify reuse."""
    temporary = path.with_name(path.name + ".partial")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def corrected_recipe(source: Path) -> tuple[dict[str, Any], str]:
    """Accept only the separate prospective count-repair recipe, not RMSE edits."""
    raw = CORRECTED_RECIPE.read_bytes()
    recipe = json.loads(raw)
    expected = {
        "schema": "cypshift.phase3.corrected_counts_ablation.v1",
        "status": "prespecified_before_corrected_count_outcomes",
        "data_manifest_sha256": digest((source / "manifest.json").read_bytes()),
        "seeds": [20260905, 20260906],
        "new_fits_per_seed": 80,
        "new_fits_total": 160,
        "cpu_core_hours_per_seed": 5,
        "cpu_core_hours_total": 10,
        "model": {
            "loss_function": "MAE",
            "random_strength": 2,
            "random_seed": 1,
            "task_type": "CPU",
            "thread_count": 16,
            "verbose": 0,
            "allow_writing_files": False,
        },
        "resolved_shared_settings": {
            "depth": 6,
            "iterations": 1000,
            "learning_rate": 0.03,
        },
        "features": {
            "mode": "corrected_counts",
            "raw_structures": True,
            "morgan_radius": 2,
            "morgan_count_bits": 1024,
            "morgan_chirality": False,
            "avalon_count_bits": 1024,
            "count_dtype": "int32",
            "matrix_dtype": "float64",
            "erg_columns": 315,
            "descriptor_columns": 200,
        },
        "implementation_sha256": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ("competition_features.py", "maplight_fixed_features.py")
        },
        "recommendation_gate_each_seed": {
            "relative_macro_primary_gain_over_calibrated_incumbent_min": 0.02,
            "paired_family_primary_upper95_max_exclusive": 0,
            "max_endpoint_component_mae_harm": 0.02,
        },
        "independent_comparison_required": True,
        "reserved_comparison": "closed",
        "final_promotion": False,
    }
    if (
        any(recipe.get(key) != value for key, value in expected.items())
        or recipe["nested_folds"]
        != {
            "outer": 5,
            "inner": 3,
            "family_policy": "unchanged development union groups",
        }
        or recipe["affine"]
        != {
            "slope_bounds": [0.8, 1.2],
            "intercept_bounds": [-0.25, 0.25],
            "scope": "inner OOF interval distance; identity ties",
        }
    ):
        raise ValueError("Corrected-count prospective recipe differs")
    return recipe, digest(raw)


def corrected_feature_matrix(data: Any) -> tuple[np.ndarray, dict[str, Any]]:
    """Regenerate raw-structure counts and prove this changes only count storage."""
    from competition_features import featurize_corrected_counts

    features = featurize_corrected_counts(data.raw_smiles)
    counts = features[:, :2048]
    if (
        features.shape != data.legacy_features.shape
        or features.dtype != np.dtype("float64")
        or not np.isfinite(counts).all()
        or np.any(counts < 0)
        or np.any(counts > np.iinfo(np.int32).max)
        or np.any(counts != np.floor(counts))
    ):
        raise ValueError(
            "Corrected feature shape or nonnegative integral counts differ"
        )
    wrapped = ((counts.astype(np.int64) + 128) % 256) - 128
    if not np.array_equal(wrapped, data.legacy_features[:, :2048]):
        raise ValueError("Corrected counts do not reproduce all legacy count bytes")
    if not np.array_equal(
        features[:, 2048:], data.legacy_features[:, 2048:], equal_nan=True
    ):
        raise ValueError("Corrected ErG/descriptors differ from legacy features")
    changed = counts != data.legacy_features[:, :2048]
    return features, {
        "mode": "corrected_counts",
        "matrix_sha256": digest(np.ascontiguousarray(features).tobytes()),
        "shape": list(features.shape),
        "dtype": str(features.dtype),
        "ordered_raw_identity_sha256": digest(
            canonical(list(zip(data.molecule_ids, data.raw_smiles, strict=True)))
        ),
        "all_legacy_count_bytes_reproduced": True,
        "erg_descriptors_equal_including_nan": True,
        "changed_count_cells": int(changed.sum()),
        "changed_molecules": int(np.any(changed, axis=1).sum()),
    }


def affine_fit(
    prediction: np.ndarray, low: np.ndarray, high: np.ndarray
) -> tuple[float, float]:
    """Fit bounded affine interval-distance loss on training OOF only."""
    if not (prediction.shape == low.shape == high.shape) or not len(prediction):
        raise ValueError("Calibration arrays differ or are empty")
    if not all(np.isfinite(v).all() for v in (prediction, low, high)) or np.any(
        low > high
    ):
        raise ValueError("Invalid calibration values")
    n = len(prediction)
    design = sparse.csr_matrix(np.column_stack((prediction, np.ones(n))))
    constraints = sparse.vstack(
        [
            sparse.hstack([design, -sparse.eye(n)]),
            sparse.hstack([-design, -sparse.eye(n)]),
        ]
    ).tocsr()
    result = linprog(
        np.r_[0.0, 0.0, np.full(n, 1 / n)],
        A_ub=constraints,
        b_ub=np.r_[high, -low],
        bounds=[(0.8, 1.2), (-0.25, 0.25)] + [(0, None)] * n,
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"Calibration optimization failed: {result.message}")
    slope, intercept = map(float, result.x[:2])
    identity_loss = interval_distance(prediction, low, high).mean()
    fitted_loss = interval_distance(slope * prediction + intercept, low, high).mean()
    if fitted_loss >= identity_loss - 1e-12:
        return 1.0, 0.0
    return slope, intercept


def cached_fit(
    cache: Path,
    features: np.ndarray,
    targets: np.ndarray,
    train: np.ndarray,
    predict: np.ndarray,
    identity: dict[str, Any],
    *,
    loss: str = "MAE",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Never reuse a prediction without exact train and prediction identities."""
    parameters = model_parameters(loss)
    if features.ndim != 2 or targets.shape != (len(features),):
        raise ValueError("Invalid model array dimensions")
    for indices in (train, predict):
        if (
            indices.ndim != 1
            or indices.dtype.kind not in "iu"
            or not len(indices)
            or np.any(indices < 0)
            or np.any(indices >= len(features))
            or len(np.unique(indices)) != len(indices)
        ):
            raise ValueError("Invalid training or prediction indices")
    if np.intersect1d(train, predict).size or not np.isfinite(targets[train]).all():
        raise ValueError("Illegal training membership or nonfinite training target")
    material = {
        **identity,
        "parameters": parameters,
        "features_sha256": digest(np.ascontiguousarray(features).tobytes()),
        "training_indices": train.tolist(),
        "prediction_indices": predict.tolist(),
        "training_targets_sha256": digest(
            np.ascontiguousarray(targets[train]).tobytes()
        ),
        "features_shape": list(features.shape),
        "features_dtype": str(features.dtype),
    }
    key = digest(canonical(material))
    directory = cache / key
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path = directory / "receipt.json"
    prediction_path = directory / "prediction.npy"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        if (
            receipt["key"] != key
            or receipt["inputs"] != material
            or digest(prediction_path.read_bytes()) != receipt["prediction_sha256"]
        ):
            raise ValueError(
                "Damaged fit checkpoint; quarantine it before a documented repair"
            )
        values = np.load(prediction_path, allow_pickle=False)
        if values.shape != (len(predict),) or not np.isfinite(values).all():
            raise ValueError("Invalid cached prediction")
        return values, {**receipt, "reused": True}
    wall, cpu = time.monotonic(), time.process_time()
    attempt_id = time.time_ns()
    publish(
        directory / f"fit-start-{attempt_id}.json",
        canonical({"started_epoch_seconds": time.time(), "threads": 16}),
    )
    model = CatBoostRegressor(**parameters)
    status = "failed"
    try:
        model.fit(features[train], targets[train])
        prediction = np.asarray(model.predict(features[predict]), dtype=np.float64)
        status = "complete"
    finally:
        publish(
            directory / f"fit-attempt-{attempt_id}.json",
            canonical(
                {
                    "status": status,
                    "wall_seconds": time.monotonic() - wall,
                    "cpu_core_hours": (time.process_time() - cpu) / 3600,
                }
            ),
        )
    if prediction.shape != (len(predict),) or not np.isfinite(prediction).all():
        raise ValueError("Model produced invalid predictions")
    with prediction_path.with_suffix(".partial").open("wb") as handle:
        np.save(handle, prediction, allow_pickle=False)
    os.replace(prediction_path.with_suffix(".partial"), prediction_path)
    receipt = {
        "key": key,
        "inputs": material,
        "prediction_sha256": digest(prediction_path.read_bytes()),
        "wall_seconds": time.monotonic() - wall,
        "cpu_core_hours": (time.process_time() - cpu) / 3600,
        "resolved_parameters": model.get_all_params(),
        "reused": False,
    }
    publish(receipt_path, canonical(receipt))
    return prediction, receipt


def freeze_interrupted_fits(root: Path) -> int:
    """Freeze orphan charges once, only while holding the shared compute lock.

    Lock acquisition establishes that an earlier lock-holding evaluator stopped.
    Its exact fit CPU use is unknown; elapsed wall time times recorded threads
    conservatively includes idle time until recovery. Finished attempts stay intact.
    """
    recovered = time.time()
    frozen = 0
    for start in root.rglob("fit-start-*.json"):
        attempt = start.with_name(start.name.replace("fit-start-", "fit-attempt-"))
        if attempt.exists():
            continue
        raw = start.read_bytes()
        record = json.loads(raw)
        elapsed = max(0.0, recovered - record["started_epoch_seconds"])
        publish(
            attempt,
            canonical(
                {
                    "status": "interrupted_unknown",
                    "wall_seconds": elapsed,
                    "cpu_core_hours": elapsed * record["threads"] / 3600,
                    "recovered_epoch_seconds": recovered,
                    "start_sha256": digest(raw),
                    "accounting_basis": "Elapsed wall time times recorded threads; includes recovery delay",
                }
            ),
        )
        frozen += 1
    for start in root.rglob("run-overhead-start-*.json"):
        attempt = start.with_name(
            start.name.replace("run-overhead-start-", "run-overhead-attempt-")
        )
        if attempt.exists():
            continue
        publish(
            attempt,
            canonical(
                {
                    "status": "interrupted_unknown",
                    "cpu_core_hours": _overhead_cpu(start, recovered=recovered),
                    "recovered_epoch_seconds": recovered,
                    "accounting_basis": "Elapsed invocation wall time times threads, less already charged fit work; includes recovery delay",
                }
            ),
        )
        frozen += 1
    return frozen


def _fit_cpu(root: Path) -> float:
    """Fit-only charges, excluding invocation overhead to prevent double counting."""
    total = 0.0
    for start in root.rglob("fit-start-*.json"):
        attempt = start.with_name(start.name.replace("fit-start-", "fit-attempt-"))
        if attempt.exists():
            total += float(json.loads(attempt.read_bytes())["cpu_core_hours"])
        else:
            record = json.loads(start.read_bytes())
            total += (
                max(0.0, time.time() - record["started_epoch_seconds"])
                * record["threads"]
                / 3600
            )
    return total


def _overhead_cpu(start: Path, *, recovered: float | None = None) -> float:
    record = json.loads(start.read_bytes())
    fit_delta = max(0.0, _fit_cpu(start.parent) - record["fit_cpu_at_start"])
    if recovered is None and record["pid"] == os.getpid():
        invocation = (time.process_time() - record["process_cpu_at_start"]) / 3600
    else:
        observed = time.time() if recovered is None else recovered
        invocation = (
            max(0.0, observed - record["started_epoch_seconds"])
            * record["threads"]
            / 3600
        )
    return max(0.0, invocation - fit_delta)


def spent_cpu(root: Path) -> float:
    """Charge fits and non-fit invocation CPU, including failed/interrupted work."""
    total = _fit_cpu(root)
    for start in root.rglob("run-overhead-start-*.json"):
        attempt = start.with_name(
            start.name.replace("run-overhead-start-", "run-overhead-attempt-")
        )
        total += (
            float(json.loads(attempt.read_bytes())["cpu_core_hours"])
            if attempt.exists()
            else _overhead_cpu(start)
        )
    return total


def _limit_remaining_cpu(remaining_core_hours: float) -> None:
    """Linux limit covers fits, preprocessing, calibration and scoring mid-stage."""
    if remaining_core_hours <= 0:
        raise RuntimeError("CPU allocation exhausted before invocation")
    limit = max(1, int(time.process_time() + remaining_core_hours * 3600))
    old_limit = resource.getrlimit(resource.RLIMIT_CPU)[1]
    if old_limit != resource.RLIM_INFINITY:
        limit = min(limit, old_limit)
    resource.setrlimit(resource.RLIMIT_CPU, (limit, limit))


def evaluate(
    source: Path,
    output: Path,
    *,
    expected_compiled_sha256: str,
    seed: int = 20260905,
    loss: str = "MAE",
    max_cpu_core_hours: float = 100,
    feature_mode: str = "legacy",
) -> dict[str, Any]:
    model_parameters(loss)  # Reject unsupported objectives before creating output.
    if feature_mode not in {"legacy", "corrected_counts"} or (
        feature_mode == "corrected_counts"
        and (
            loss != "MAE" or seed not in (20260905, 20260906) or max_cpu_core_hours != 5
        )
    ):
        raise ValueError(
            "Corrected counts require frozen MAE, seed, and five-core-hour budget"
        )
    if not np.isfinite(max_cpu_core_hours) or not 0 < max_cpu_core_hours <= 1000:
        raise ValueError("Run CPU budget must be finite and in (0, 1000]")
    if ROOT == output.resolve() or ROOT in output.resolve().parents:
        raise ValueError("Experiment output must stay outside Git")
    if digest((source / "manifest.json").read_bytes()) != expected_compiled_sha256:
        raise ValueError("Compiled development receipt differs")
    output.mkdir(parents=True, exist_ok=True)
    # An interrupted process releases this lock; another active process cannot duplicate work.
    with (output.parent / "compute.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze_interrupted_fits(output.parent)
        if loss == "RMSE" or feature_mode == "corrected_counts":
            _limit_remaining_cpu(
                min(
                    max_cpu_core_hours - spent_cpu(output),
                    1000 - spent_cpu(output.parent),
                )
            )
        if feature_mode == "legacy":
            return _evaluate_locked(source, output, seed, loss, max_cpu_core_hours)
        return _evaluate_locked(
            source, output, seed, loss, max_cpu_core_hours, feature_mode
        )


def _evaluate_locked(
    source: Path,
    output: Path,
    seed: int,
    loss: str = "MAE",
    max_cpu_core_hours: float = 100,
    feature_mode: str = "legacy",
) -> dict[str, Any]:
    started_cpu = time.process_time()
    attempt = time.time_ns()
    start = output / f"run-overhead-start-{attempt}.json"
    publish(
        start,
        canonical(
            {
                "pid": os.getpid(),
                "started_epoch_seconds": time.time(),
                "process_cpu_at_start": started_cpu,
                "threads": 16,
                "fit_cpu_at_start": _fit_cpu(output),
            }
        ),
    )
    status = "failed"
    try:
        report = _evaluate_scientific(
            source, output, seed, loss, max_cpu_core_hours, feature_mode
        )
        status = "complete"
    finally:
        invocation_cpu = (time.process_time() - started_cpu) / 3600
        publish(
            output / f"run-overhead-attempt-{attempt}.json",
            canonical(
                {
                    "status": status,
                    "cpu_core_hours": _overhead_cpu(start),
                    "invocation_cpu_core_hours": invocation_cpu,
                    "accounting_basis": "Measured process CPU minus newly charged fits; no fit double counting",
                }
            ),
        )
    report["invocation_cpu_core_hours"] = invocation_cpu
    report["budget_accounted_fit_cpu_core_hours"] = _fit_cpu(output)
    report["budget_accounted_cpu_core_hours"] = spent_cpu(output)
    report["program_accounted_cpu_core_hours"] = spent_cpu(output.parent)
    # Historical field is retained with its explicitly fit-only meaning.
    report["program_accounted_fit_cpu_core_hours"] = _fit_cpu(output.parent)
    publish(output / "result.json", canonical(report))
    return report


def _evaluate_scientific(
    source: Path,
    output: Path,
    seed: int,
    loss: str,
    max_cpu_core_hours: float,
    feature_mode: str = "legacy",
) -> dict[str, Any]:
    wall, cpu = time.monotonic(), time.process_time()
    parameters = model_parameters(loss)
    candidate = (
        "maplight-inner-oof-affine"
        if loss == "MAE"
        else "maplight-rmse-inner-oof-affine"
    )
    if feature_mode == "corrected_counts":
        candidate = "maplight-corrected-counts-inner-oof-affine"
    execution_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    expected_runtime = {
        "python": "3.10.13",
        "catboost": "1.2.1",
        "numpy": "1.25.2",
        "rdkit": "2023.3.3",
        "scipy": "1.11.2",
    }
    runtime = {
        "python": platform.python_version(),
        **{
            name: importlib.metadata.version(name)
            for name in expected_runtime
            if name != "python"
        },
    }
    if runtime != expected_runtime:
        raise ValueError("Run the existing locked MapLight research environment")
    data = load_development(source)
    features = data.legacy_features
    feature_receipt = None
    if feature_mode == "corrected_counts":
        features, feature_receipt = corrected_feature_matrix(data)
    receipts = data.receipts
    if any(data.report["metric_targets_missing_bounds"]):
        raise ValueError(
            "Finite central truth has missing bounds; review before fitting"
        )
    outer, inner = balanced_nested_folds(data.groups, data.training_mask, seed=seed)
    names, groups = np.asarray(data.names), np.asarray(data.groups)
    for fold in range(5):
        for col in range(4):
            if not np.any((outer == fold) & data.metric_mask[:, col]):
                raise ValueError("Outer scoring support missing")
            for inner_fold in range(3):
                train = (
                    (outer != fold)
                    & (inner[fold] != inner_fold)
                    & data.training_mask[:, col]
                )
                if train.sum() < 2 or np.unique(data.point[train, col]).size < 2:
                    raise ValueError("Nested training support missing")
    identity = {
        "objective": loss,
        "parameters": parameters,
        "candidate": candidate,
        "optimizer_scope": "Shared fixed settings; objective-specific optimizer defaults are retained and recorded, not asserted identical",
        "cpu_budget_policy": "RMSE uses a remaining-allocation Linux CPU hard cap under the shared lock; MAE retains between-fit enforcement. Both account non-fit invocation CPU",
        "runtime": {
            "python": platform.python_version(),
            **{
                name: importlib.metadata.version(name)
                for name in ("catboost", "numpy", "rdkit", "scipy")
            },
        },
        "implementation": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in (
                "competition_runner.py",
                "competition_data.py",
                "competition_metrics.py",
            )
        },
        "source_receipts": receipts,
        "seed": seed,
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer": outer.tolist(),
        "inner": inner.tolist(),
    }
    if feature_receipt is not None:
        _, recipe_hash = corrected_recipe(source)
        identity.update(
            feature_receipt=feature_receipt,
            prospective_recipe_sha256=recipe_hash,
            compiled_manifest_sha256=digest((source / "manifest.json").read_bytes()),
        )
        identity["implementation"].update(
            {
                name: digest(Path(__file__).with_name(name).read_bytes())
                for name in ("competition_features.py", "maplight_fixed_features.py")
            }
        )
        identity["cpu_budget_policy"] = (
            "Corrected-count MAE uses remaining-allocation CPU hard cap under shared lock, including feature construction and scoring"
        )
    frozen = output / "experiment.json"
    if frozen.exists() and frozen.read_bytes() != canonical(identity):
        raise ValueError("Experiment inputs changed; create a new prospective attempt")
    publish(frozen, canonical(identity))
    publish(output / "intake_report.json", canonical(data.report))
    baseline = np.full(data.point.shape, np.nan)
    calibrated = np.full(data.point.shape, np.nan)
    fit_identity = {"experiment_sha256": digest(canonical(identity))}
    publish(
        output / "execution.json",
        canonical(
            {
                "git_commit": execution_commit,
                "seed": seed,
                "max_cpu_core_hours": max_cpu_core_hours,
                "compiled_manifest_sha256": digest(
                    (source / "manifest.json").read_bytes()
                ),
            }
        ),
    )
    fits, calibrations = [], []
    for fold in range(5):
        for col in range(4):
            outer_training = outer != fold
            heldout = np.flatnonzero(~outer_training)
            calibration_predictions = np.full(len(names), np.nan)
            for inner_fold in range(3):
                if (
                    spent_cpu(output) >= max_cpu_core_hours
                    or spent_cpu(output.parent) >= 1000
                ):
                    raise RuntimeError("CPU allocation exhausted before fitting")
                train = np.flatnonzero(
                    outer_training
                    & (inner[fold] != inner_fold)
                    & data.training_mask[:, col]
                )
                predict = np.flatnonzero(outer_training & (inner[fold] == inner_fold))
                values, receipt = cached_fit(
                    output / "fits",
                    features,
                    data.point[:, col],
                    train,
                    predict,
                    fit_identity,
                    loss=loss,
                )
                calibration_predictions[predict] = values
                fits.append(receipt)
                if len(fits) == 1:
                    publish(
                        output / "profile.json",
                        canonical(
                            {
                                "first_fit_wall_seconds": receipt["wall_seconds"],
                                "first_fit_cpu_core_hours": receipt["cpu_core_hours"],
                                "linear_80_fit_cpu_projection": receipt[
                                    "cpu_core_hours"
                                ]
                                * 80,
                                "scope": "Representative real fit; estimate, not a quality gate",
                            }
                        ),
                    )
                    print(
                        "First real fit profile: "
                        + json.dumps(
                            {
                                "wall_seconds": receipt["wall_seconds"],
                                "projected_cpu_core_hours": receipt["cpu_core_hours"]
                                * 80,
                            }
                        ),
                        flush=True,
                    )
            eligible = outer_training & np.isfinite(data.point[:, col])
            slope, intercept = affine_fit(
                calibration_predictions[eligible],
                data.low[eligible, col],
                data.high[eligible, col],
            )
            train = np.flatnonzero(outer_training & data.training_mask[:, col])
            if (
                spent_cpu(output) >= max_cpu_core_hours
                or spent_cpu(output.parent) >= 1000
            ):
                raise RuntimeError("CPU allocation exhausted before outer fitting")
            values, receipt = cached_fit(
                output / "fits",
                features,
                data.point[:, col],
                train,
                heldout,
                fit_identity,
                loss=loss,
            )
            baseline[heldout, col] = values
            calibrated[heldout, col] = slope * values + intercept
            fits.append(receipt)
            calibrations.append(
                {"fold": fold, "endpoint": col, "slope": slope, "intercept": intercept}
            )
            publish(
                output / "progress.json",
                canonical(
                    {
                        "completed_fits": len(fits),
                        "planned_fits": 80,
                        "outer_fold": fold,
                        "endpoint": col,
                        "cpu_core_hours": sum(f["cpu_core_hours"] for f in fits),
                        "elapsed_wall_seconds": time.monotonic() - wall,
                    }
                ),
            )
            print(f"Completed {len(fits)}/80 fits", flush=True)
            if spent_cpu(output) > max_cpu_core_hours:
                raise RuntimeError("Experiment CPU-core-hour allocation exhausted")
    # Freeze complete OOF predictions before scoring or fitting deployment calibration.
    with (output / "oof.partial").open("wb") as handle:
        np.savez(
            handle,
            baseline=baseline,
            calibrated=calibrated,
            names=names,
            groups=groups,
            outer=outer,
            inner=inner,
        )
    os.replace(output / "oof.partial", output / "oof.npz")
    baseline_scores = direct_scores(
        names, groups, data.point, data.low, data.high, baseline
    )
    candidate_scores = direct_scores(
        names, groups, data.point, data.low, data.high, calibrated
    )
    paired = paired_family_difference(
        names, groups, data.point, data.low, data.high, calibrated, baseline
    )
    deployment = []
    for col in range(4):
        eligible = np.isfinite(data.point[:, col])
        deployment.append(
            affine_fit(
                baseline[eligible, col],
                data.low[eligible, col],
                data.high[eligible, col],
            )
        )
    decision = release_decision(candidate_scores, baseline_scores, paired)
    if loss == "RMSE" or feature_mode == "corrected_counts":
        decision = {
            "within_objective_calibration": decision,
            "incumbent_comparison_complete": False,
            "release_eligible_on_paired_metrics": False,
            "promotion_metric_gate": False,
            "final_promotion": False,
            "reason": (
                "Raw RMSE versus its own affine calibration does not compare either candidate with the current MAE incumbent"
                if feature_mode == "legacy"
                else "Corrected-count raw versus affine does not compare either candidate with the current MAE incumbent"
            ),
        }
    report = {
        "status": "complete",
        "execution_git_commit": execution_commit,
        "candidate": candidate,
        "objective": loss,
        "parameters": parameters,
        "max_cpu_core_hours": max_cpu_core_hours,
        "baseline": baseline_scores,
        "candidate_scores": candidate_scores,
        "paired_family": paired,
        "decision": decision,
        "outer_calibration": calibrations,
        "deployment_calibration": deployment,
        "fits": len(fits),
        "new_fits": sum(not f["reused"] for f in fits),
        "fit_cpu_core_hours": sum(f["cpu_core_hours"] for f in fits),
        "budget_accounted_fit_cpu_core_hours": spent_cpu(output),
        "program_accounted_fit_cpu_core_hours": spent_cpu(output.parent),
        "invocation_cpu_core_hours": (time.process_time() - cpu) / 3600,
        "wall_seconds": time.monotonic() - wall,
        "experiment_sha256": digest(frozen.read_bytes()),
        "oof_sha256": digest((output / "oof.npz").read_bytes()),
        "reserved_numeric_targets_opened": 0,
        "release_scope": (
            "Interim calibration may transform authenticated legacy full-train baseline; no reserved targets opened"
            if loss == "MAE" and feature_mode == "legacy"
            else (
                "RMSE requires matched comparison against the MAE incumbent, new production estimator fitting and reload verification, and actual RMSE test predictions. Never apply these calibration parameters to the historical MAE CSV; no reserved targets opened"
                if feature_mode == "legacy"
                else "Corrected-count estimators require matched comparison, saved/reloaded development-only models and their own predictions. Never apply these calibration parameters to the historical MAE CSV; no reserved targets opened"
            )
        ),
        "resolved_parameter_variants": {
            digest(canonical(fit["resolved_parameters"])): fit["resolved_parameters"]
            for fit in fits
        },
    }
    if feature_receipt is not None:
        report.update(
            feature_receipt=feature_receipt,
            prospective_recipe_sha256=identity["prospective_recipe_sha256"],
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", required=True, type=Path)
    parser.add_argument("--compiled-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260905)
    parser.add_argument("--loss", choices=("MAE", "RMSE"), default="MAE")
    parser.add_argument(
        "--features", choices=("legacy", "corrected_counts"), default="legacy"
    )
    parser.add_argument("--max-cpu-core-hours", type=float, default=100)
    args = parser.parse_args()
    if ROOT == args.output.resolve() or ROOT in args.output.resolve().parents:
        raise ValueError("Experiment output must stay outside Git")
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:16])
    resource.setrlimit(resource.RLIMIT_AS, (20 * 1024**3, 20 * 1024**3))
    try:
        report = evaluate(
            args.compiled,
            args.output,
            expected_compiled_sha256=args.compiled_sha256,
            seed=args.seed,
            loss=args.loss,
            max_cpu_core_hours=args.max_cpu_core_hours,
            feature_mode=args.features,
        )
    except Exception as exc:
        # Distinct timestamps preserve failed engineering attempts; no model outcomes discarded.
        args.output.mkdir(parents=True, exist_ok=True)
        publish(
            args.output / f"failure-{time.time_ns()}.json",
            canonical(
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            ),
        )
        raise
    print(json.dumps(report["decision"], sort_keys=True))


if __name__ == "__main__":
    main()
