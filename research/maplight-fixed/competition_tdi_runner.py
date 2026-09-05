"""Frozen first TDI evaluation: two learners, nested thresholds, retained models.

Production packaging is a separate gated stage. Existing run directories are not
resumed. Run official jobs under an independent 2700-second external deadline.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
import pickle
import platform
import resource
import signal
import subprocess
import time
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# One numerical thread for logistic/scoring; CatBoost explicitly uses 16.
for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_variable] = "1"

import fcntl  # noqa: E402

import numpy as np  # noqa: E402
from catboost import CatBoostClassifier  # noqa: E402
from competition_data import balanced_nested_folds  # noqa: E402
from competition_features import featurize_binary_morgan  # noqa: E402
from competition_runner import freeze_interrupted_fits, publish, spent_cpu  # noqa: E402
from competition_tdi_data import load_tdi_development, support_report  # noqa: E402
from competition_tdi_metrics import (  # noqa: E402
    ENDPOINTS,
    confusion_mcc,
    direct_tdi_scores,
    paired_family_mcc,
)
from scipy import sparse  # noqa: E402
from sklearn.exceptions import ConvergenceWarning  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "benchmarks/openadmet_cyp_2026/phase3_tdi_v1.json"
LEARNERS = ("logistic", "catboost")
IMPLEMENTATIONS = (
    "competition_tdi_runner.py",
    "competition_tdi_data.py",
    "competition_tdi_metrics.py",
    "competition_data.py",
    "competition_features.py",
    "competition_runner.py",
    "competition_metrics.py",
    "maplight_fixed_features.py",
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def array_receipt(path: Path, values: np.ndarray) -> dict[str, Any]:
    buffer = io.BytesIO()
    np.save(buffer, values, allow_pickle=False)
    publish(path, buffer.getvalue())
    return {
        "path": str(path.resolve()),
        "sha256": file_hash(path),
        "shape": list(values.shape),
        "dtype": str(values.dtype),
    }


def read_array(spec: dict[str, Any]) -> np.ndarray:
    raw = Path(spec["path"]).read_bytes()
    if digest(raw) != spec["sha256"]:
        raise ValueError("Prediction array receipt differs")
    values = np.load(io.BytesIO(raw), allow_pickle=False)
    if list(values.shape) != spec["shape"] or str(values.dtype) != spec["dtype"]:
        raise ValueError("Prediction array layout differs")
    return values


def select_threshold(probability: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    """Every nonconstant empirical partition; deterministic proximity/lower ties."""
    if (
        probability.ndim != 1
        or labels.shape != probability.shape
        or not len(labels)
        or not np.isfinite(probability).all()
        or np.any((probability < 0) | (probability > 1))
        or not np.isin(labels, [0, 1]).all()
        or len(np.unique(labels)) != 2
    ):
        raise ValueError(
            "Threshold inputs require finite probabilities and both truth classes"
        )
    # Sort once; grouped score thresholds represent exactly p>=threshold without
    # an O(n^2) matrix or thousands of repeated sklearn validation calls.
    order = np.argsort(probability, kind="stable")
    sorted_p, sorted_y = probability[order], labels[order]
    positives = int(sorted_y.sum())
    negatives = len(labels) - positives
    prefix = np.r_[0, np.cumsum(sorted_y, dtype=np.int64)]
    thresholds = np.unique(np.r_[0.5, sorted_p])
    cuts = np.searchsorted(sorted_p, thresholds, side="left")
    eligible = (cuts > 0) & (cuts < len(labels))
    thresholds, cuts = thresholds[eligible], cuts[eligible]
    if not len(thresholds):
        return {"threshold": 0.5, "mcc": None, "supported": False}
    fn, tn = prefix[cuts], cuts - prefix[cuts]
    tp, fp = positives - fn, negatives - tn
    scores, _ = confusion_mcc(np.column_stack((tn, fp, fn, tp)))
    choices = [
        (-float(score), abs(float(threshold) - 0.5), float(threshold))
        for threshold, score in zip(thresholds, scores, strict=True)
    ]
    best = min(choices)
    return {"threshold": best[2], "mcc": -best[0], "supported": True}


def choose_learner(thresholds: dict[str, dict[str, Any]]) -> str:
    supported = [name for name in LEARNERS if thresholds[name]["supported"]]
    if not supported:
        raise ValueError("Both learners unsupported in inner threshold selection")
    return max(
        supported, key=lambda name: (thresholds[name]["mcc"], -LEARNERS.index(name))
    )


def model_parameters(learner: str) -> dict[str, Any]:
    if learner == "logistic":
        return {
            "C": 1.0,
            "penalty": "l2",
            "solver": "liblinear",
            "dual": False,
            "fit_intercept": True,
            "intercept_scaling": 1.0,
            "class_weight": None,
            "tol": 1e-4,
            "max_iter": 1000,
            "random_state": 1,
            "warm_start": False,
        }
    if learner == "catboost":
        return {
            "loss_function": "Logloss",
            "iterations": 1000,
            "depth": 6,
            "learning_rate": 0.03,
            "random_seed": 1,
            "random_strength": 2,
            "task_type": "CPU",
            "thread_count": 16,
            "verbose": False,
            "allow_writing_files": False,
            "use_best_model": False,
            "class_weights": None,
        }
    raise ValueError("Unknown frozen TDI learner")


def new_estimator(learner: str) -> Any:
    constructor = LogisticRegression if learner == "logistic" else CatBoostClassifier
    return constructor(**model_parameters(learner))


def model_inputs(features: np.ndarray, indices: np.ndarray, learner: str) -> Any:
    subset = features[indices]
    return (
        sparse.csr_matrix(subset, dtype=np.float64) if learner == "logistic" else subset
    )


def positive_probability(model: Any, inputs: Any) -> np.ndarray:
    classes = np.asarray(model.classes_)
    if classes.shape != (2,) or set(classes.tolist()) != {0, 1}:
        raise ValueError("Fitted class order/support differs")
    probability = np.asarray(model.predict_proba(inputs), dtype=np.float64)
    if probability.ndim != 2 or probability.shape[1] != 2:
        raise ValueError("Probability matrix layout differs")
    result = probability[:, int(np.flatnonzero(classes == 1)[0])]
    if not np.isfinite(result).all() or np.any((result < 0) | (result > 1)):
        raise ValueError("Nonfinite or out-of-range probability")
    return result


def load_model(spec: dict[str, Any], learner: str) -> Any:
    raw = Path(spec["path"]).read_bytes()
    if digest(raw) != spec["sha256"]:
        raise ValueError("Model checkpoint receipt differs before loading")
    if learner == "logistic":
        return pickle.loads(
            raw
        )  # Own hash-authenticated, pinned-runtime artifact only.
    model = new_estimator(learner)
    model.load_model(spec["path"])
    return model


def cpu_seconds() -> float:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + usage.ru_utime + usage.ru_stime


class Budget:
    """Native in-process fits; charge parent+small reaped Git children exactly once."""

    def __init__(self, root: Path, output: Path, seed: int) -> None:
        self.root, self.output = root, output
        self.started, self.cpu_started = time.monotonic(), cpu_seconds()
        self.fit_cpu = 0.0
        previous_cpu = spent_cpu(root)
        seed_cpu, seed_wall = 0.0, 0.0
        for path in root.rglob("run-overhead-start-*.json"):
            start = json.loads(path.read_bytes())
            if start.get("tdi_seed") != seed:
                continue
            seed_cpu += spent_cpu(path.parent)
            resources = path.parent / "resources.json"
            if not resources.exists():
                publish(
                    resources,
                    canonical(
                        {
                            "status": "interrupted_unknown",
                            "occupied_wall_seconds": max(
                                0.0, time.time() - start["started_epoch_seconds"]
                            ),
                        }
                    ),
                )
            seed_wall += json.loads(resources.read_bytes())["occupied_wall_seconds"]
        self.cpu_allowance = min(5 - seed_cpu, 1000 - previous_cpu) * 3600
        self.wall_allowance = 2700 - seed_wall
        if self.cpu_allowance <= 0 or self.wall_allowance <= 0:
            raise RuntimeError("TDI seed/program allowance exhausted")
        self.prior = {
            "program_cpu_core_hours": previous_cpu,
            "seed_cpu_core_hours": seed_cpu,
            "seed_occupied_wall_seconds": seed_wall,
        }
        publish(
            output / "run-overhead-start-0.json",
            canonical(
                {
                    "started_epoch_seconds": time.time(),
                    "threads": 24,
                    "pid": os.getpid(),
                    "process_cpu_at_start": time.process_time(),
                    "fit_cpu_at_start": 0.0,
                    "tdi_seed": seed,
                }
            ),
        )

    def remaining(self) -> tuple[float, float]:
        wall = self.wall_allowance - (time.monotonic() - self.started)
        cpu = self.cpu_allowance - (cpu_seconds() - self.cpu_started)
        if wall <= 0 or cpu <= 0:
            raise RuntimeError("TDI wall/CPU allowance exhausted")
        return wall, cpu

    def limit(self) -> None:
        _, cpu = self.remaining()
        limit = max(1, int(time.process_time() + cpu))
        hard = resource.getrlimit(resource.RLIMIT_CPU)[1]
        if hard != resource.RLIM_INFINITY:
            limit = min(limit, hard)
        resource.setrlimit(resource.RLIMIT_CPU, (limit, limit))

    @contextlib.contextmanager
    def fit(self, directory: Path) -> Iterator[None]:
        self.limit()
        wall, cpu = time.monotonic(), time.process_time()
        publish(
            directory / "fit-start-0.json",
            canonical(
                {
                    "started_epoch_seconds": time.time(),
                    "threads": 24,
                    "actual_catboost_threads": 16,
                    "accounting_scope": "Fit, predict, save and reload",
                }
            ),
        )
        status = "failed"
        try:
            yield
            status = "complete"
        finally:
            charged = time.process_time() - cpu
            self.fit_cpu += charged
            publish(
                directory / "fit-attempt-0.json",
                canonical(
                    {
                        "status": status,
                        "wall_seconds": time.monotonic() - wall,
                        "cpu_core_hours": charged / 3600,
                        "accounting_basis": "Measured in-process CPU including native threads",
                    }
                ),
            )
        self.limit()

    def finish(self, status: str) -> None:
        total = cpu_seconds() - self.cpu_started
        overhead = max(0.0, total - self.fit_cpu)
        publish(
            self.output / "run-overhead-attempt-0.json",
            canonical(
                {
                    "status": status,
                    "cpu_core_hours": overhead / 3600,
                    "accounting_basis": "Invocation parent+reaped children less already charged native fits",
                }
            ),
        )
        publish(
            self.output / "resources.json",
            canonical(
                {
                    "status": status,
                    "occupied_wall_seconds": time.monotonic() - self.started,
                    "invocation_cpu_core_hours": total / 3600,
                    "fit_cpu_core_hours": self.fit_cpu / 3600,
                    "overhead_cpu_core_hours": overhead / 3600,
                    "prior": self.prior,
                }
            ),
        )


def fit_estimator(
    output: Path,
    features: np.ndarray,
    data: Any,
    learner: str,
    endpoint: int,
    train: np.ndarray,
    predict: np.ndarray,
    identity: dict[str, Any],
    budget: Any,
) -> tuple[np.ndarray, dict[str, Any]]:
    if any(
        indices.ndim != 1
        or indices.dtype.kind not in "iu"
        or np.any(indices < 0)
        or np.any(indices >= len(data.names))
        for indices in (train, predict)
    ):
        raise ValueError("Invalid TDI fit indices")
    if (
        len(np.unique(train)) != len(train)
        or len(np.unique(predict)) != len(predict)
        or not len(train)
        or not len(predict)
        or set(train) & set(predict)
        or not data.mask[train, endpoint].all()
        or set(data.labels[train, endpoint].tolist()) != {0, 1}
        or {data.groups[i] for i in train} & {data.groups[i] for i in predict}
    ):
        raise ValueError("Illegal TDI training/assessment family membership or support")
    targets = np.asarray(data.labels[train, endpoint], dtype=np.int8)
    inputs = {
        **identity,
        "learner": learner,
        "endpoint": endpoint,
        "training_indices": train.tolist(),
        "prediction_indices": predict.tolist(),
        "training_targets_sha256": digest(targets.tobytes()),
        "parameters": model_parameters(learner),
    }
    key = digest(canonical(inputs))
    directory = output / "fits" / key
    directory.mkdir(parents=True, exist_ok=False)
    publish(directory / "inputs.json", canonical(inputs))
    with budget.fit(directory):
        model = new_estimator(learner)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(model_inputs(features, train, learner), targets)
        probability = positive_probability(
            model, model_inputs(features, predict, learner)
        )
        model_path = directory / ("model.pkl" if learner == "logistic" else "model.cbm")
        if learner == "logistic":
            publish(model_path, pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL))
            resolved = model.get_params()
            resolved["n_iter_"] = np.asarray(model.n_iter_).tolist()
        else:
            temporary = directory / "model.partial"
            model.save_model(str(temporary))
            publish(model_path, temporary.read_bytes())
            temporary.unlink()
            resolved = model.get_all_params()
        checkpoint = {
            "path": str(model_path.resolve()),
            "sha256": file_hash(model_path),
        }
        fresh = load_model(checkpoint, learner)
        replay = positive_probability(fresh, model_inputs(features, predict, learner))
        if probability.shape != (len(predict),) or not np.allclose(
            probability, replay, atol=1e-12, rtol=0
        ):
            raise ValueError("Fresh classifier probability reload differs")
        prediction = array_receipt(directory / "probability.npy", replay)
        receipt = {
            "key": key,
            "inputs": inputs,
            "inputs_sha256": file_hash(directory / "inputs.json"),
            "checkpoint": checkpoint,
            "prediction": prediction,
            "resolved_parameters": resolved,
            "classes": np.asarray(model.classes_).tolist(),
            "maximum_reload_absolute_error": float(
                np.max(np.abs(probability - replay))
            ),
        }
        publish(directory / "receipt.json", canonical(receipt))
    return replay, {
        "path": str((directory / "receipt.json").resolve()),
        "sha256": file_hash(directory / "receipt.json"),
        "key": key,
    }


def seed_evidence(data: Any, classes: dict[str, np.ndarray]) -> dict[str, Any]:
    names, groups = np.asarray(data.names), np.asarray(data.groups)
    scores = {
        name: direct_tdi_scores(names, data.labels, data.mask, pred)
        for name, pred in classes.items()
    }
    zero = np.zeros(data.labels.shape, dtype=np.int8)
    useful, against_zero = {}, {}
    for name in ("logistic", "selected"):
        paired = paired_family_mcc(
            names, groups, data.labels, data.mask, classes[name], zero
        )
        against_zero[name] = paired
        useful[name] = (
            scores[name]["macro_bootstrap_mean_mcc"] > 0
            and all(scores[name]["endpoints"][ep]["mcc"] > 0 for ep in ENDPOINTS)
            and paired["lower_95"] > 0
        )
    difference = paired_family_mcc(
        names, groups, data.labels, data.mask, classes["selected"], classes["logistic"]
    )
    gain = (
        scores["selected"]["macro_bootstrap_mean_mcc"]
        - scores["logistic"]["macro_bootstrap_mean_mcc"]
    )
    selected = bool(useful["selected"] and gain >= 0.02 and difference["lower_95"] > 0)
    return {
        "scores": scores,
        "usefulness": useful,
        "paired_vs_constant_zero": against_zero,
        "selected_vs_logistic": difference,
        "selected_macro_mcc_gain": gain,
        "selected_qualifies_this_seed": selected,
        "logistic_qualifies_this_seed": bool(useful["logistic"]),
        "repeat2_required": bool(selected or useful["logistic"]),
    }


def combine_evidence(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Apply both-seed policy to independently verified evidence, never CSV approval."""
    if (first.get("seed"), second.get("seed")) != (20260905, 20260906):
        raise ValueError("Both frozen repeats in order are required")
    if any(
        value.get("status") != "complete" or value.get("completed_fits") != 80
        for value in (first, second)
    ):
        raise ValueError("Incomplete TDI repeat")
    selected = all(value["selected_qualifies_this_seed"] for value in (first, second))
    logistic = all(value["logistic_qualifies_this_seed"] for value in (first, second))
    return {
        "recommended_procedure": "selected"
        if selected
        else "logistic"
        if logistic
        else None,
        "independent_artifact_audit_required": True,
        "release_eligible": False,
        "production_fits_if_qualified": 14 if selected else 8 if logistic else 0,
    }


def validate_recipe(recipe: dict[str, Any]) -> None:
    if recipe["learners"] != {name: model_parameters(name) for name in LEARNERS}:
        raise ValueError("Recipe differs from frozen learner parameters")
    pin = recipe.get("tdi_bundle_manifest_sha256")
    if (
        not isinstance(pin, str)
        or len(pin) != 64
        or any(c not in "0123456789abcdef" for c in pin)
    ):
        raise ValueError("Approved intake manifest must be pinned before official fits")


def evaluate_arrays(
    data: Any, features: np.ndarray, output: Path, seed: int, fit: Any
) -> dict[str, Any]:
    if (
        features.shape != (len(data.names), 4096)
        or features.dtype != np.uint8
        or not np.isin(features, [0, 1]).all()
    ):
        raise ValueError("Frozen binary feature layout differs")
    outer, inner = balanced_nested_folds(
        data.groups, data.original_direct_training_mask, seed
    )
    probabilities = {name: np.full(data.labels.shape, np.nan) for name in LEARNERS}
    classes = {
        name: np.zeros(data.labels.shape, dtype=np.int8)
        for name in (*LEARNERS, "selected")
    }
    decisions, fits = [], []
    for fold in range(5):
        outer_train, assessment = (
            np.flatnonzero(outer != fold),
            np.flatnonzero(outer == fold),
        )
        for col in range(2):
            inner_specs, thresholds = {}, {}
            for learner in LEARNERS:
                inner_probability = np.full(len(data.names), np.nan)
                inner_receipts = []
                for inner_fold in range(3):
                    fitting = np.flatnonzero(
                        (outer != fold)
                        & (inner[fold] != inner_fold)
                        & data.mask[:, col]
                    )
                    held = np.flatnonzero(inner[fold] == inner_fold)
                    prediction, receipt = fit(
                        learner=learner,
                        endpoint=col,
                        train=fitting,
                        predict=held,
                        identity={"outer": fold, "inner": inner_fold, "role": "inner"},
                    )
                    inner_probability[held] = prediction
                    fits.append(receipt)
                    inner_receipts.append(receipt)
                eligible = outer_train[data.mask[outer_train, col]]
                thresholds[learner] = select_threshold(
                    inner_probability[eligible], data.labels[eligible, col]
                )
                spec = array_receipt(
                    output / f"inner-{fold}-{col}-{learner}.npy",
                    inner_probability[outer_train],
                )
                inner_specs[learner] = {
                    "prediction": spec,
                    "fit_receipts": inner_receipts,
                }
                fitting = outer_train[data.mask[outer_train, col]]
                prediction, receipt = fit(
                    learner=learner,
                    endpoint=col,
                    train=fitting,
                    predict=assessment,
                    identity={
                        "outer": fold,
                        "inner": -1,
                        "role": "outer",
                        "inner_prediction": spec,
                        "inner_fit_receipts": inner_receipts,
                        "threshold_selection": thresholds[learner],
                    },
                )
                probabilities[learner][assessment, col] = prediction
                classes[learner][assessment, col] = (
                    prediction >= thresholds[learner]["threshold"]
                )
                fits.append(receipt)
            chosen = choose_learner(thresholds)
            classes["selected"][assessment, col] = classes[chosen][assessment, col]
            decisions.append(
                {
                    "outer": fold,
                    "endpoint": col,
                    "chosen_learner": chosen,
                    "thresholds": thresholds,
                    "inner_oof": inner_specs,
                }
            )
            print(
                json.dumps(
                    {
                        "completed_fits": len(fits),
                        "total_fits": 80,
                        "outer": fold,
                        "endpoint": ENDPOINTS[col],
                        "chosen_learner": chosen,
                    }
                ),
                flush=True,
            )
    if len(fits) != 80 or any(not np.isfinite(v).all() for v in probabilities.values()):
        raise ValueError("Incomplete TDI OOF or fit count")
    result = {
        "schema": "cypshift.phase3.tdi_result.v1",
        "status": "complete",
        "seed": seed,
        "names": list(data.names),
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer_fold": outer.tolist(),
        "inner_fold": inner.tolist(),
        "completed_fits": len(fits),
        "fit_receipts": fits,
        "decisions": decisions,
        "probabilities": {
            name: array_receipt(output / f"{name}-oof-probability.npy", v)
            for name, v in probabilities.items()
        },
        "classes": {
            name: array_receipt(output / f"{name}-oof-class.npy", v)
            for name, v in classes.items()
        },
        **seed_evidence(data, classes),
        "reserved_numeric_targets_opened": 0,
        "release_eligible": False,
        "final_promotion": False,
        "release_scope": "Two-seed independent verification required; then8logistic or14selected-procedure production fits, saved/reloaded estimators, actual750rowvalidatedCSV. No reserve or threshold adjustment on test predictions.",
    }
    return result


def first_repeat_authority(
    data: Any, path: Path, expected_sha256: str, identity: dict[str, Any]
) -> dict[str, str]:
    """Recompute the predefined continuation decision from hash-pinned OOF."""
    raw = path.read_bytes()
    if digest(raw) != expected_sha256:
        raise ValueError("First-repeat result receipt differs")
    result = json.loads(raw)
    experiment_raw = path.with_name("experiment.json").read_bytes()
    previous = json.loads(experiment_raw)
    if (
        result.get("seed") != 20260905
        or result.get("status") != "complete"
        or result.get("completed_fits") != 80
        or result["experiment_sha256"] != digest(experiment_raw)
    ):
        raise ValueError("First repeat incomplete or unauthenticated")
    for key in (
        "recipe_sha256",
        "implementation_sha256",
        "runtime",
        "data_manifest_sha256",
        "tdi_manifest_sha256",
        "source_receipts",
        "support_sha256",
        "names",
        "molecule_ids",
        "groups",
    ):
        if previous[key] != identity[key]:
            raise ValueError("First-repeat scientific identity differs")
    if previous["features"]["sha256"] != identity["features"]["sha256"]:
        raise ValueError("First-repeat feature matrix differs")
    classes = {}
    for name in (*LEARNERS, "selected"):
        spec = result["classes"][name]
        if not Path(spec["path"]).resolve().is_relative_to(path.parent.resolve()):
            raise ValueError("First-repeat OOF escaped its run")
        classes[name] = read_array(spec)
    evidence = seed_evidence(data, classes)
    if any(result[key] != value for key, value in evidence.items()):
        raise ValueError("First-repeat evidence flags differ from recomputed metrics")
    if not evidence["repeat2_required"]:
        raise ValueError("Frozen first-repeat futility rule prohibits repeat2")
    return {
        "result_sha256": expected_sha256,
        "experiment_sha256": digest(experiment_raw),
    }


def resource_receipt() -> dict[str, Any]:
    relative = Path("/proc/self/cgroup").read_text().strip().split("0::")[-1]
    if "cypshift.slice" not in relative.split("/"):
        raise RuntimeError("Use the shared cypshift.slice")
    directory = Path("/sys/fs/cgroup") / (
        relative.split("/cypshift.slice")[0] + "/cypshift.slice"
    ).lstrip("/")
    quota, period = map(int, (directory / "cpu.max").read_text().split())
    memory = int((directory / "memory.max").read_text())
    affinity = sorted(os.sched_getaffinity(0))
    if (
        quota / period > 24
        or memory > 21474836480
        or not set(affinity) <= (set(range(12)) | set(range(16, 28)))
    ):
        raise RuntimeError("Shared resource caps differ")
    return {
        "cgroup": relative,
        "cpu_max": [quota, period],
        "memory_max": memory,
        "affinity": affinity,
    }


def source_identity(recipe: dict[str, Any]) -> dict[str, Any]:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    hashes = {}
    for name in (*IMPLEMENTATIONS, "phase3_tdi_v1.json"):
        path = RECIPE if name.endswith(".json") else Path(__file__).with_name(name)
        relative = path.relative_to(ROOT)
        committed = subprocess.check_output(
            ["git", "show", f"{commit}:{relative}"], cwd=ROOT
        )
        if digest(committed) != file_hash(path):
            raise ValueError("TDI implementation/recipe differs from execution commit")
        hashes[name] = file_hash(path)
    versions = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "rdkit", "scipy", "scikit-learn", "catboost", "pandas")
    }
    versions["python"] = platform.python_version()
    if versions != recipe["runtime"]:
        raise ValueError("Locked TDI runtime differs")
    return {
        "execution_git_commit": commit,
        "implementation_sha256": hashes,
        "runtime": versions,
    }


def evaluate(
    compiled: Path,
    tdi_bundle: Path,
    expected_tdi_sha256: str,
    output: Path,
    seed: int,
    repeat1: Path | None = None,
    repeat1_sha256: str | None = None,
) -> dict[str, Any]:
    if not (
        output.resolve().parent
        == compiled.resolve().parent
        == tdi_bundle.resolve().parent
    ):
        raise ValueError("TDI inputs and output must share the phase3 accounting root")
    if seed == 20260906 and (repeat1 is None or repeat1_sha256 is None):
        raise ValueError("Repeat2 requires hash-pinned repeat1 evidence")
    if seed == 20260905 and (repeat1 is not None or repeat1_sha256 is not None):
        raise ValueError("First seed cannot consume repeat evidence")
    recipe_raw = RECIPE.read_bytes()
    recipe = json.loads(recipe_raw)
    validate_recipe(recipe)
    if expected_tdi_sha256 != recipe["tdi_bundle_manifest_sha256"]:
        raise ValueError("TDI bundle differs from prospectively approved intake pin")
    if seed not in recipe["seeds"] or output.resolve().is_relative_to(ROOT):
        raise ValueError("Unsupported seed or output inside repository")
    if file_hash(compiled / "manifest.json") != recipe["data_manifest_sha256"]:
        raise ValueError("Development manifest differs")
    if file_hash(tdi_bundle / "manifest.json") != expected_tdi_sha256:
        raise ValueError("TDI bundle manifest differs")
    resources = resource_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / "compute.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        freeze_interrupted_fits(output.parent)
        output.mkdir(exist_ok=False)
        budget = Budget(output.parent, output, seed)
        old_handler = signal.getsignal(signal.SIGALRM)

        def deadline(signum: int, frame: Any) -> None:
            raise TimeoutError("TDI occupied wall allowance exhausted")

        signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, budget.remaining()[0])
        status = "failed"
        try:
            budget.limit()
            code = source_identity(recipe)
            data = load_tdi_development(compiled, tdi_bundle)
            support = support_report(data)
            publish(output / "support.json", canonical(support))
            if not support["supported"]:
                raise ValueError(
                    "Both-seed TDI fold support preflight failed before fitting"
                )
            features = featurize_binary_morgan(data.raw_smiles)
            feature_spec = array_receipt(output / "features.npy", features)
            identity = {
                "schema": "cypshift.phase3.tdi_experiment.v1",
                "seed": seed,
                "recipe_sha256": digest(recipe_raw),
                **code,
                "resources": resources,
                "data_manifest_sha256": recipe["data_manifest_sha256"],
                "tdi_manifest_sha256": expected_tdi_sha256,
                "source_receipts": data.receipts,
                "support_sha256": file_hash(output / "support.json"),
                "features": feature_spec,
                "names": list(data.names),
                "molecule_ids": list(data.molecule_ids),
                "groups": list(data.groups),
            }
            if seed == 20260906:
                assert repeat1 is not None and repeat1_sha256 is not None
                identity["first_repeat_authority"] = first_repeat_authority(
                    data, repeat1, repeat1_sha256, identity
                )
            publish(output / "experiment.json", canonical(identity))

            def fit(**kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
                local = kwargs.pop("identity")
                return fit_estimator(
                    output,
                    features,
                    data,
                    identity={**identity, **local},
                    budget=budget,
                    **kwargs,
                )

            result = evaluate_arrays(data, features, output, seed, fit)
            budget.remaining()
            result["experiment_sha256"] = file_hash(output / "experiment.json")
            publish(output / "result.json", canonical(result))
            status = "complete"
            return result
        except BaseException as error:
            publish(
                output / "failure.json",
                canonical({"type": type(error).__name__, "message": str(error)}),
            )
            raise
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
            budget.finish(status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--tdi-bundle", type=Path, required=True)
    parser.add_argument("--tdi-bundle-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, choices=(20260905, 20260906), required=True)
    parser.add_argument("--repeat1", type=Path)
    parser.add_argument("--repeat1-sha256")
    args = parser.parse_args()
    result = evaluate(
        args.compiled,
        args.tdi_bundle,
        args.tdi_bundle_sha256,
        args.output,
        args.seed,
        args.repeat1,
        args.repeat1_sha256,
    )
    print(
        json.dumps(
            {
                "completed_fits": result["completed_fits"],
                "repeat2_required": result["repeat2_required"],
                "release_eligible": False,
            }
        )
    )


if __name__ == "__main__":
    main()
