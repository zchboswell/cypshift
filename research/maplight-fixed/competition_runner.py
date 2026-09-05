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
PARAMETERS = {
    "loss_function": "MAE",
    "random_strength": 2,
    "random_seed": 1,
    "task_type": "CPU",
    "thread_count": 16,
    "verbose": 0,
    "allow_writing_files": False,
}


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
) -> tuple[np.ndarray, dict[str, Any]]:
    """Never reuse a prediction without exact train and prediction identities."""
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
        "parameters": PARAMETERS,
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
    model = CatBoostRegressor(**PARAMETERS)
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
    return frozen


def spent_cpu(root: Path) -> float:
    """Include failed fits and conservative charges for unfinished processes."""
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


def evaluate(
    source: Path, output: Path, *, expected_compiled_sha256: str, seed: int = 20260905
) -> dict[str, Any]:
    if ROOT == output.resolve() or ROOT in output.resolve().parents:
        raise ValueError("Experiment output must stay outside Git")
    if digest((source / "manifest.json").read_bytes()) != expected_compiled_sha256:
        raise ValueError("Compiled development receipt differs")
    output.mkdir(parents=True, exist_ok=True)
    # An interrupted process releases this lock; another active process cannot duplicate work.
    with (output.parent / "compute.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze_interrupted_fits(output.parent)
        return _evaluate_locked(source, output, seed)


def _evaluate_locked(source: Path, output: Path, seed: int) -> dict[str, Any]:
    wall, cpu = time.monotonic(), time.process_time()
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
                if spent_cpu(output) >= 100 or spent_cpu(output.parent) >= 1000:
                    raise RuntimeError("CPU allocation exhausted before fitting")
                train = np.flatnonzero(
                    outer_training
                    & (inner[fold] != inner_fold)
                    & data.training_mask[:, col]
                )
                predict = np.flatnonzero(outer_training & (inner[fold] == inner_fold))
                values, receipt = cached_fit(
                    output / "fits",
                    data.legacy_features,
                    data.point[:, col],
                    train,
                    predict,
                    fit_identity,
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
            values, receipt = cached_fit(
                output / "fits",
                data.legacy_features,
                data.point[:, col],
                train,
                heldout,
                fit_identity,
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
            if sum(f["cpu_core_hours"] for f in fits) > 100:
                raise RuntimeError(
                    "Initial experiment 100 CPU-core-hour allocation exhausted"
                )
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
    report = {
        "status": "complete",
        "execution_git_commit": execution_commit,
        "candidate": "maplight-inner-oof-affine",
        "baseline": baseline_scores,
        "candidate_scores": candidate_scores,
        "paired_family": paired,
        "decision": release_decision(candidate_scores, baseline_scores, paired),
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
        "release_scope": "Interim calibration may transform authenticated legacy full-train baseline; no reserved targets opened",
    }
    publish(output / "result.json", canonical(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", required=True, type=Path)
    parser.add_argument("--compiled-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260905)
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
