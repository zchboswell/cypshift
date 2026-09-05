"""Bounded three-arm joint MLP evaluation; CPU science, isolated Torch fits.

No production CSV is emitted. Existing attempt directories are never resumed.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import resource
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
from competition_data import (
    balanced_group_folds,
    balanced_nested_folds,
    load_development,
)
from competition_features import featurize_binary_morgan
from competition_metrics import ENDPOINTS, direct_scores, paired_family_difference
from competition_runner import affine_fit, freeze_interrupted_fits, publish, spent_cpu

RECIPE = (
    Path(__file__).resolve().parents[2]
    / "benchmarks/openadmet_cyp_2026/phase3_mlp_auxiliary_v1.json"
)
ARMS = ("direct", "real_aux", "shuffled_aux")
FEATURE_MODES = ("morgan_descriptors", "morgan_only")


def recipe_path(feature_mode: str = "morgan_descriptors") -> Path:
    if feature_mode not in FEATURE_MODES:
        raise ValueError("Unknown MLP feature mode")
    return (
        RECIPE
        if feature_mode == "morgan_descriptors"
        else RECIPE.with_name("phase3_mlp_morgan_only_v1.json")
    )


def build_features(data: Any, feature_mode: str = "morgan_descriptors") -> np.ndarray:
    """Keep original Morgan bytes; the separate ablation zeroes all descriptor inputs."""
    recipe_path(feature_mode)  # Reject unknown modes before featurizing.
    descriptors = (
        data.legacy_features[:, 2363:]
        if feature_mode == "morgan_descriptors"
        else np.zeros((len(data.raw_smiles), 200), dtype=np.float64)
    )
    return np.column_stack((featurize_binary_morgan(data.raw_smiles), descriptors))


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def seed_for(seed: int, outer: int, inner: int, role: str) -> int:
    """Stable arm-independent streams, independent of Python's salted hash."""
    return int(sha(canonical([seed, outer, inner, role]))[:8], 16)


def array_file(path: Path, value: np.ndarray) -> dict[str, Any]:
    stream = io.BytesIO()
    np.save(stream, value, allow_pickle=False)
    publish(path, stream.getvalue())
    return {
        "path": str(path.resolve()),
        "sha256": file_sha(path),
        "shape": list(value.shape),
        "dtype": str(value.dtype),
    }


def read_array(spec: dict[str, Any]) -> np.ndarray:
    raw = Path(spec["path"]).read_bytes()
    if sha(raw) != spec["sha256"]:
        raise ValueError("Array hash differs")
    value = np.load(io.BytesIO(raw), allow_pickle=False)
    if list(value.shape) != spec["shape"] or str(value.dtype) != spec["dtype"]:
        raise ValueError("Array shape/dtype differs")
    return value


def fit_scale(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Finite train-only medians/IQR; unsupported columns explicitly neutral."""
    center, scale = np.zeros(values.shape[1]), np.ones(values.shape[1])
    for col in range(values.shape[1]):
        finite = values[:, col][np.isfinite(values[:, col])]
        if len(finite):
            center[col] = np.median(finite)
            width = np.percentile(finite, 75) - np.percentile(finite, 25)
            scale[col] = width if width > 0 else 1
    return center, scale


def scaled(values: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return ((np.where(np.isfinite(values), values, center) - center) / scale).astype(
        np.float32
    )


def prepare_arrays(
    features: np.ndarray,
    point: np.ndarray,
    direct_mask: np.ndarray,
    auxiliary: np.ndarray,
    auxiliary_mask: np.ndarray,
    train: np.ndarray,
    predict: np.ndarray,
    stop: np.ndarray | None,
    arm: str,
    shuffle_seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if arm not in ARMS or features.shape[1] != 4296:
        raise ValueError("Unknown arm or feature width")
    populations = [train, predict] + ([] if stop is None else [stop])
    if not len(train) or any(len(set(v.tolist())) != len(v) for v in populations):
        raise ValueError("Empty or duplicated fitting population")
    if set(train) & set(predict) or (stop is not None and set(train) & set(stop)):
        raise ValueError("Training overlaps assessment")
    center, scale = fit_scale(features[train, 4096:])
    aux_center, aux_scale = fit_scale(
        np.where(auxiliary_mask[train], auxiliary[train], np.nan)
    )

    def x(indices: np.ndarray) -> np.ndarray:
        return np.column_stack(
            (features[indices, :4096], scaled(features[indices, 4096:], center, scale))
        ).astype(np.float32)

    def y(indices: np.ndarray) -> np.ndarray:
        return np.where(direct_mask[indices], point[indices], 0).astype(np.float32)

    order = np.arange(len(train))
    if arm == "shuffled_aux":
        order = np.random.default_rng(shuffle_seed).permutation(len(train))
    donors = train[order]
    mask = auxiliary_mask[donors]
    aux = scaled(auxiliary[donors], aux_center, aux_scale)
    arrays = {
        "train_x": x(train),
        "train_direct_y": y(train),
        "train_direct_mask": direct_mask[train],
        "train_aux_y": np.where(mask, aux, 0).astype(np.float32),
        "train_aux_mask": mask,
        "predict_x": x(predict),
    }
    if stop is not None:
        arrays.update(
            stop_x=x(stop), stop_direct_y=y(stop), stop_direct_mask=direct_mask[stop]
        )
    if any(v.dtype != bool and not np.isfinite(v).all() for v in arrays.values()):
        raise ValueError("Nonfinite prepared fitting payload")
    return arrays, {
        "descriptor_center": center.tolist(),
        "descriptor_scale": scale.tolist(),
        "auxiliary_center": aux_center.tolist(),
        "auxiliary_scale": aux_scale.tolist(),
        "auxiliary_donor_indices": donors.tolist(),
    }


def stopping_split(
    groups: tuple[str, ...], mask: np.ndarray, train: np.ndarray, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    fold = balanced_group_folds([groups[i] for i in train], mask[train], 5, seed)
    fitting, stopping = train[fold != 0], train[fold == 0]
    if any(not mask[idx].any(axis=0).all() for idx in (fitting, stopping)):
        raise ValueError("Unsupported direct stopping/fitting endpoint")
    if {groups[i] for i in fitting} & {groups[i] for i in stopping}:
        raise ValueError("Family crosses stopping boundary")
    return fitting, stopping


def load_auxiliary(
    path: Path, data: Any, expected: str
) -> tuple[np.ndarray, np.ndarray]:
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError("Auxiliary receipt differs before decoding")
    lookup = {identity: index for index, identity in enumerate(data.molecule_ids)}
    values = np.zeros(data.point.shape)
    mask = np.zeros(data.point.shape, dtype=bool)
    for line in raw.splitlines():
        record = json.loads(line)
        index = lookup[record["molecule_id"]]
        metadata = record["metadata"]
        col = ENDPOINTS.index(metadata["enzyme"])
        if (
            mask[index, col]
            or record["family"] != data.groups[index]
            or metadata["Molecule_Name"] != data.names[index]
            or metadata["SMILES"] != data.raw_smiles[index]
            or metadata["concentration_M"] != "4.95049505e-05"
        ):
            raise ValueError("Auxiliary context/identity/duplicate differs")
        cell = record["responses"]["log2fc_estimate"]
        if cell["state"] != "finite" or not np.isfinite(cell["parsed_value"]):
            raise ValueError("Frozen finite auxiliary coverage differs")
        values[index, col] = cell["parsed_value"]
        mask[index, col] = True
    if mask.sum() != 13972 or not np.all(mask.sum(axis=0) == 3493):
        raise ValueError("Auxiliary coverage differs")
    return values, mask


def cpu_seconds() -> float:
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + children.ru_utime + children.ru_stime


def check_resources() -> dict[str, Any]:
    relative = Path("/proc/self/cgroup").read_text().strip().split("0::")[-1]
    if "cypshift.slice" not in relative.split("/"):
        raise RuntimeError("Run inside shared cypshift.slice")
    prefix = relative.split("/cypshift.slice")[0] + "/cypshift.slice"
    root = Path("/sys/fs/cgroup") / prefix.lstrip("/")
    cpu, memory = (
        (root / "cpu.max").read_text().strip(),
        (root / "memory.max").read_text().strip(),
    )
    quota, period = map(int, cpu.split())
    allowed = set(range(12)) | set(range(16, 28))
    affinity = set(os.sched_getaffinity(0))
    if quota / period > 24 or int(memory) > 20 * 1024**3 or not affinity <= allowed:
        raise RuntimeError("Shared CPU/memory/affinity cap differs")
    return {
        "cgroup": relative,
        "cpu_max": cpu,
        "memory_max": memory,
        "affinity": sorted(affinity),
    }


class Budget:
    """Single invocation: charge reaped children and parent independently."""

    def __init__(
        self,
        root: Path,
        output: Path,
        lock_fd: int,
        seed: int | None = None,
        feature_mode: str = "morgan_descriptors",
    ) -> None:
        recipe_path(feature_mode)
        self.root, self.output, self.lock_fd = root, output, lock_fd
        self.wall_start, self.cpu_start = time.monotonic(), cpu_seconds()
        self.parent_start = time.process_time()
        self.seed = seed
        self.child_start = self.cpu_start - self.parent_start
        self.previous = spent_cpu(root)
        self.fit_cpu = 0.0
        self.observed_fit_cpu = 0.0
        self.uncertain_cpu_surcharge = 0.0
        prior_cpu, prior_wall = 0.0, 0.0
        if seed is not None:
            for start in root.rglob("run-overhead-start-*.json"):
                record = json.loads(start.read_bytes())
                if (
                    record.get("mlp_seed") != seed
                    or record.get("mlp_feature_mode", "morgan_descriptors")
                    != feature_mode
                ):
                    continue
                prior_cpu += spent_cpu(start.parent)
                receipt = start.parent / "resources.json"
                if not receipt.exists():
                    publish(
                        receipt,
                        canonical(
                            {
                                "status": "interrupted_unknown",
                                "occupied_wall_seconds": max(
                                    0.0, time.time() - record["started_epoch_seconds"]
                                ),
                            }
                        ),
                    )
                prior_wall += json.loads(receipt.read_bytes())["occupied_wall_seconds"]
        self.prior_seed_cpu, self.prior_seed_wall = prior_cpu, prior_wall
        self.wall_allowance = 3600 - prior_wall
        self.allowance = min(10.0 - prior_cpu, 1000.0 - self.previous)
        if self.allowance <= 0 or self.wall_allowance <= 0:
            raise RuntimeError("Program CPU budget exhausted")
        self.start = output / "run-overhead-start-0.json"
        publish(
            self.start,
            canonical(
                {
                    "started_epoch_seconds": time.time(),
                    "threads": 24,
                    "mlp_seed": seed,
                    "mlp_feature_mode": feature_mode,
                    "pid": os.getpid(),
                    "process_cpu_at_start": time.process_time(),
                    "fit_cpu_at_start": 0.0,
                }
            ),
        )

    def remaining(self) -> tuple[float, float]:
        wall = self.wall_allowance - (time.monotonic() - self.wall_start)
        cpu = (
            self.allowance * 3600
            - (cpu_seconds() - self.cpu_start)
            - self.uncertain_cpu_surcharge
        )
        if wall <= 0 or cpu <= 0:
            raise RuntimeError("MLP wall/CPU allowance exhausted")
        return wall, cpu

    def limit_parent(self) -> None:
        _, remaining = self.remaining()
        limit = max(1, int(time.process_time() + remaining))
        hard = resource.getrlimit(resource.RLIMIT_CPU)[1]
        if hard != resource.RLIM_INFINITY:
            limit = min(hard, limit)
        resource.setrlimit(resource.RLIMIT_CPU, (limit, limit))

    def run(self, command: list[str], directory: Path) -> None:
        wall, cpu = self.remaining()
        self.limit_parent()
        started = time.monotonic()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = "failed"
        uncertain = False
        publish(
            directory / "fit-start-0.json",
            canonical(
                {
                    "started_epoch_seconds": time.time(),
                    "threads": 24,
                    "actual_numeric_threads": 1,
                    "command": command,
                }
            ),
        )

        def cap_child() -> None:
            cap = max(1, int(cpu))
            hard = resource.getrlimit(resource.RLIMIT_CPU)[1]
            if hard != resource.RLIM_INFINITY:
                cap = min(cap, hard)
            resource.setrlimit(resource.RLIMIT_CPU, (cap, cap))

        process = None
        try:
            env = dict(os.environ)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            ):
                env[key] = "1"
            cache = self.output / "runtime-cache"
            for key in (
                "XDG_CACHE_HOME",
                "TORCH_HOME",
                "TRITON_CACHE_DIR",
                "MIOPEN_USER_DB_PATH",
                "TORCHINDUCTOR_CACHE_DIR",
            ):
                env[key] = str(cache / key.lower())
            with (directory / "worker.log").open("xb") as log:
                process = subprocess.Popen(
                    ["timeout", "--signal=KILL", str(wall), *command],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env,
                    start_new_session=True,
                    pass_fds=(self.lock_fd,),
                    preexec_fn=cap_child,
                )
                try:
                    code = process.wait(timeout=wall)
                except BaseException:
                    uncertain = True
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    finally:
                        process.wait()
                    raise
                if code:
                    uncertain = code < 0 or code >= 124
                    raise RuntimeError(
                        f"GPU worker exited {code}; inspect private worker.log"
                    )
            status = "complete"
        finally:
            if uncertain and process is not None:
                # A killed timeout wrapper may leave descendants unreaped. Stop
                # the whole inherited group even if the wrapper already exited.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            observed = max(
                0.0, after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
            )
            elapsed = time.monotonic() - started
            charged = max(observed, elapsed * 24) if uncertain else observed
            self.observed_fit_cpu += observed
            self.fit_cpu += charged
            self.uncertain_cpu_surcharge += charged - observed
            publish(
                directory / "fit-attempt-0.json",
                canonical(
                    {
                        "status": status,
                        "wall_seconds": elapsed,
                        "cpu_core_hours": charged / 3600,
                        "observed_reaped_cpu_seconds": observed,
                        "uncertain_termination": uncertain,
                        "uncertainty_surcharge_cpu_seconds": charged - observed,
                        "accounting_basis": (
                            "Unknown descendant CPU after timeout/kill: max(reaped CPU, elapsed wall times enforced24CPUcap)"
                            if uncertain
                            else "Reaped child user+system CPU after normal wrapper termination"
                        ),
                    }
                ),
            )
        self.limit_parent()

    def finish(self, status: str) -> dict[str, Any]:
        parent = time.process_time() - self.parent_start
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        child_total = usage.ru_utime + usage.ru_stime - self.child_start
        nonfit_child = max(0.0, child_total - self.observed_fit_cpu)
        report = {
            "status": status,
            "occupied_wall_seconds": time.monotonic() - self.wall_start,
            "parent_cpu_seconds": parent,
            "child_cpu_seconds": child_total,
            "charged_fit_cpu_seconds": self.fit_cpu,
            "observed_fit_cpu_seconds": self.observed_fit_cpu,
            "uncertainty_surcharge_cpu_seconds": self.uncertain_cpu_surcharge,
            "nonfit_child_cpu_seconds": nonfit_child,
            "prior_seed_cpu_core_hours": self.prior_seed_cpu,
            "prior_seed_occupied_wall_seconds": self.prior_seed_wall,
            "invocation_cpu_core_hours": (
                parent + child_total + self.uncertain_cpu_surcharge
            )
            / 3600,
            "prior_program_cpu_core_hours": self.previous,
        }
        publish(
            self.output / "run-overhead-attempt-0.json",
            canonical(
                {
                    "status": status,
                    "cpu_core_hours": (parent + nonfit_child) / 3600,
                    "accounting_basis": "Parent and nonfit child CPU; fit children charged separately",
                }
            ),
        )
        publish(self.output / "resources.json", canonical(report))
        return report


def run_fit(
    output: Path,
    worker: Path,
    python: Path,
    runtime: dict[str, str],
    data: Any,
    features: np.ndarray,
    auxiliary: np.ndarray,
    aux_mask: np.ndarray,
    train: np.ndarray,
    predict: np.ndarray,
    stop: np.ndarray | None,
    arm: str,
    seed: int,
    outer: int,
    inner: int,
    role: str,
    epochs: int,
    identity: dict[str, Any],
    hyperparameters: dict[str, Any],
    budget: Budget,
) -> tuple[np.ndarray, dict[str, Any]]:
    directory = output / "fits" / f"{arm}-{outer}-{inner}-{role}"
    directory.mkdir(parents=True, exist_ok=False)
    arrays, transforms = prepare_arrays(
        features,
        data.point,
        data.training_mask,
        auxiliary,
        aux_mask,
        train,
        predict,
        stop,
        arm,
        seed_for(seed, outer, inner, role + "-shuffle"),
    )
    files = {
        name: array_file(directory / f"{name}.npy", value)
        for name, value in arrays.items()
    }
    params = dict(hyperparameters, aux_weight=0.0 if arm == "direct" else 0.25)
    request = {
        "schema": "cypshift.mlp.fit.v1",
        "identity": {
            **identity,
            "train": train.tolist(),
            "predict": predict.tolist(),
            "stop": None if stop is None else stop.tolist(),
            "transforms": transforms,
            "outer": outer,
            "inner": inner,
            "role": role,
        },
        "arm": arm,
        "mode": "fixed" if stop is None else "stopped",
        "epochs": epochs,
        **{
            key: seed_for(seed, outer, inner, role + "-" + key)
            for key in ("model_seed", "batch_seed", "dropout_seed")
        },
        "hyperparameters": params,
        "files": files,
        "worker_sha256": file_sha(worker),
        "runtime_receipt": runtime,
    }
    request_path = directory / "request.json"
    publish(request_path, canonical(request))
    worker_output = directory / "worker"
    budget.run(
        [
            str(python),
            str(worker),
            "--request",
            str(request_path),
            "--output",
            str(worker_output),
        ],
        directory,
    )
    receipt_path = worker_output / "receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    if (
        receipt["schema"] != "cypshift.mlp.fit_receipt.v1"
        or receipt["status"] != "complete"
        or receipt["worker_sha256"] != request["worker_sha256"]
        or receipt["runtime_receipt_sha256"] != runtime["sha256"]
        or receipt["identity"] != request["identity"]
        or receipt["arm"] != arm
        or receipt["mode"] != request["mode"]
        or receipt["hyperparameters"] != params
        or not receipt["reload_parity"]["model_and_optimizer_state_exact"]
        or receipt["request_sha256"] != file_sha(request_path)
        or file_sha(Path(receipt["checkpoint"]["path"]))
        != receipt["checkpoint"]["sha256"]
        or not 1 <= receipt["selected_epoch"] <= epochs
        or not receipt["finite_loss"]
        or not np.isfinite(receipt["reload_parity"]["maximum_absolute_error"])
        or receipt["reload_parity"]["maximum_absolute_error"] > 1e-6
    ):
        raise ValueError("Worker receipt authentication/fit check failed")
    prediction = read_array(receipt["predictions"])
    if (
        prediction.shape != (len(predict), 4)
        or prediction.dtype != np.float32
        or not np.isfinite(prediction).all()
    ):
        raise ValueError("Worker prediction shape/dtype/finiteness differs")
    if stop is None and receipt["selected_epoch"] != epochs:
        raise ValueError("Fixed refit epoch differs")
    return prediction.astype(np.float64), {
        "path": str(receipt_path),
        "sha256": file_sha(receipt_path),
        "request_sha256": file_sha(request_path),
        "selected_epoch": receipt["selected_epoch"],
        "initial_state_sha256": receipt["initial_state_sha256"],
        "batch_order_epoch_sha256": receipt["batch_order_epoch_sha256"],
    }


def evaluate_arrays(
    data: Any,
    features: np.ndarray,
    auxiliary: np.ndarray,
    aux_mask: np.ndarray,
    output: Path,
    seed: int,
    fit: Any,
) -> dict[str, Any]:
    """Joint-fit topology, independent of worker startup; synthetic-test seam."""
    outer, inner = balanced_nested_folds(data.groups, data.training_mask, seed)
    predictions = {
        arm: {
            variant: np.full(data.point.shape, np.nan) for variant in ("raw", "affine")
        }
        for arm in ARMS
    }
    receipts, calibrations = [], []
    matched: dict[tuple[int, int, str], dict[str, Any]] = {}

    def checked_fit(**kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        prediction, receipt = fit(**kwargs)
        key = (kwargs["outer"], kwargs["inner"], kwargs["role"])
        if key in matched:
            ref = matched[key]
            n = min(
                len(ref["batch_order_epoch_sha256"]),
                len(receipt["batch_order_epoch_sha256"]),
            )
            if (
                ref["initial_state_sha256"] != receipt["initial_state_sha256"]
                or ref["batch_order_epoch_sha256"][:n]
                != receipt["batch_order_epoch_sha256"][:n]
            ):
                raise ValueError(
                    "Matched initialization/batch schedule differs across arms"
                )
        else:
            matched[key] = receipt
        if (len(receipts) + 1) % 7 == 0:
            print(
                json.dumps(
                    {
                        "completed_fits": len(receipts) + 1,
                        "total_fits": 105,
                        "arm": kwargs["arm"],
                        "outer": kwargs["outer"],
                        "selected_epoch": receipt["selected_epoch"],
                    }
                ),
                flush=True,
            )
        receipts.append(
            {
                "arm": kwargs["arm"],
                "outer": kwargs["outer"],
                "inner": kwargs["inner"],
                "role": kwargs["role"],
                **receipt,
            }
        )
        return prediction, receipt

    for arm in ARMS:
        for fold in range(5):
            outer_train, assessment = (
                np.flatnonzero(outer != fold),
                np.flatnonzero(outer == fold),
            )
            inner_oof = np.full(data.point.shape, np.nan)
            stopped = []
            for inner_fold in range(3):
                train = np.flatnonzero((outer != fold) & (inner[fold] != inner_fold))
                held = np.flatnonzero(inner[fold] == inner_fold)
                fitting, stopping = stopping_split(
                    data.groups,
                    data.training_mask,
                    train,
                    seed_for(seed, fold, inner_fold, "stopping"),
                )
                _, stop_receipt = checked_fit(
                    train=fitting,
                    predict=stopping,
                    stop=stopping,
                    arm=arm,
                    outer=fold,
                    inner=inner_fold,
                    role="stop",
                    epochs=200,
                    identity={},
                )
                stopped.append(stop_receipt)
                pred, _ = checked_fit(
                    train=train,
                    predict=held,
                    stop=None,
                    arm=arm,
                    outer=fold,
                    inner=inner_fold,
                    role="refit",
                    epochs=stop_receipt["selected_epoch"],
                    identity={"stopping_receipt": stop_receipt},
                )
                inner_oof[held] = pred
            pred, _ = checked_fit(
                train=outer_train,
                predict=assessment,
                stop=None,
                arm=arm,
                outer=fold,
                inner=-1,
                role="outer",
                epochs=int(np.median([r["selected_epoch"] for r in stopped])),
                identity={"stopping_receipts": stopped},
            )
            predictions[arm]["raw"][assessment] = pred
            inner_spec = array_file(
                output / f"{arm}-outer-{fold}-inner-oof.npy", inner_oof[outer_train]
            )
            for col in range(4):
                eligible = outer_train[data.metric_mask[outer_train, col]]
                slope, intercept = affine_fit(
                    inner_oof[eligible, col],
                    data.low[eligible, col],
                    data.high[eligible, col],
                )
                predictions[arm]["affine"][assessment, col] = (
                    slope * pred[:, col] + intercept
                )
                calibrations.append(
                    {
                        "arm": arm,
                        "outer": fold,
                        "endpoint": col,
                        "slope": slope,
                        "intercept": intercept,
                        "inner_oof": inner_spec,
                    }
                )
    arrays = {
        f"{arm}_{variant}": array_file(output / f"{arm}-{variant}-oof.npy", pred)
        for arm, variants in predictions.items()
        for variant, pred in variants.items()
    }
    names, groups = np.asarray(data.names), np.asarray(data.groups)
    scores = {
        arm: {
            variant: direct_scores(names, groups, data.point, data.low, data.high, pred)
            for variant, pred in variants.items()
        }
        for arm, variants in predictions.items()
    }
    paired = {
        variant: {
            control: paired_family_difference(
                names,
                groups,
                data.point,
                data.low,
                data.high,
                predictions["real_aux"][variant],
                predictions[control][variant],
            )
            for control in ("direct", "shuffled_aux")
        }
        for variant in ("raw", "affine")
    }
    return {
        "schema": "cypshift.phase3.mlp_auxiliary_result.v1",
        "status": "complete",
        "reserved_numeric_targets_opened": 0,
        "seed": seed,
        "names": list(data.names),
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer_fold": outer.tolist(),
        "inner_fold": inner.tolist(),
        "scores": scores,
        "paired_auxiliary_controls": paired,
        "oof": arrays,
        "fit_receipts": receipts,
        "calibrations": calibrations,
        "completed_fits": len(receipts),
        "release_eligible": False,
        "final_promotion": False,
        "release_scope": "Pending independent matched-incumbent comparison across both seeds; qualified model needs seven separately authorized production joint fits, saved/reloaded estimators and actual blinded predictions. Never transform historical MAE CSV.",
    }


def evaluate(
    compiled: Path,
    auxiliary_path: Path,
    output: Path,
    seed: int,
    gpu_python: Path,
    runtime_path: Path,
    feature_mode: str = "morgan_descriptors",
) -> dict[str, Any]:
    selected_recipe = recipe_path(feature_mode)
    recipe_raw = selected_recipe.read_bytes()
    recipe = json.loads(recipe_raw)
    if recipe.get("feature_mode", "morgan_descriptors") != feature_mode:
        raise ValueError("Recipe and requested MLP representation differ")
    if seed not in recipe["seeds"] or output.resolve().is_relative_to(
        RECIPE.parents[2]
    ):
        raise ValueError("Unsupported seed or output inside repository")
    if file_sha(compiled / "manifest.json") != recipe["data_manifest_sha256"]:
        raise ValueError("Compiled data receipt differs")
    if file_sha(runtime_path) != recipe["gpu_runtime_receipt_sha256"]:
        raise ValueError("GPU runtime receipt differs")
    runtime = {"path": str(runtime_path.resolve()), "sha256": file_sha(runtime_path)}
    worker = Path(__file__).with_name("competition_mlp_worker.py")
    if (
        gpu_python.resolve()
        != Path(json.loads(runtime_path.read_bytes())["runtime"]).resolve()
    ):
        raise ValueError("GPU interpreter differs from verified runtime")
    resources = check_resources()
    versions = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "rdkit", "scipy", "catboost")
    }
    versions["python"] = platform.python_version()
    if versions != recipe["cpu_runtime_versions"]:
        raise ValueError("Locked CPU runtime versions differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / "compute.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        freeze_interrupted_fits(output.parent)
        output.mkdir(exist_ok=False)
        budget = Budget(output.parent, output, lock.fileno(), seed, feature_mode)
        old_alarm = signal.getsignal(signal.SIGALRM)

        def deadline(signum: int, frame: Any) -> None:
            raise TimeoutError("MLP whole-invocation occupied wall allowance exhausted")

        signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, budget.remaining()[0])
        status = "failed"
        try:
            budget.limit_parent()
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=RECIPE.parents[2], text=True
            ).strip()
            sources = [selected_recipe, Path(__file__), worker] + [
                Path(__file__).with_name(name)
                for name in (
                    "competition_data.py",
                    "competition_features.py",
                    "competition_metrics.py",
                    "competition_runner.py",
                    "maplight_fixed_features.py",
                )
            ]
            for source in sources:
                relative = source.resolve().relative_to(RECIPE.parents[2])
                committed = subprocess.check_output(
                    ["git", "show", f"{commit}:{relative}"], cwd=RECIPE.parents[2]
                )
                if sha(committed) != file_sha(source):
                    raise ValueError(
                        "Scientific source/recipe differs from execution commit"
                    )
            data = load_development(compiled)
            auxiliary, mask = load_auxiliary(
                auxiliary_path, data, recipe["auxiliary_records_sha256"]
            )
            features = build_features(data, feature_mode)
            feature_spec = array_file(output / "raw-features.npy", features)
            identity = {
                "recipe_sha256": sha(recipe_raw),
                "feature_mode": feature_mode,
                "execution_git_commit": commit,
                "gpu_runtime_receipt": runtime,
                "seed": seed,
                "source_receipts": data.receipts,
                "data_manifest_sha256": recipe["data_manifest_sha256"],
                "auxiliary_records_sha256": recipe["auxiliary_records_sha256"],
                "features": feature_spec,
                "names": list(data.names),
                "molecule_ids": list(data.molecule_ids),
                "groups": list(data.groups),
                "cpu_runtime": versions,
                "resources": resources,
                "implementation_sha256": {
                    name: file_sha(Path(__file__).with_name(name))
                    for name in (
                        "competition_mlp_runner.py",
                        "competition_mlp_worker.py",
                        "competition_data.py",
                        "competition_features.py",
                        "competition_metrics.py",
                        "competition_runner.py",
                        "maplight_fixed_features.py",
                    )
                },
            }
            publish(output / "experiment.json", canonical(identity))

            def fit(**kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
                supplied = kwargs.pop("identity")
                return run_fit(
                    output,
                    worker,
                    gpu_python,
                    runtime,
                    data,
                    features,
                    auxiliary,
                    mask,
                    seed=seed,
                    identity={**identity, **supplied},
                    hyperparameters=recipe["hyperparameters"],
                    budget=budget,
                    **kwargs,
                )

            result = evaluate_arrays(data, features, auxiliary, mask, output, seed, fit)
            result["feature_mode"] = feature_mode
            budget.remaining()
            result["experiment_sha256"] = file_sha(output / "experiment.json")
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
            signal.signal(signal.SIGALRM, old_alarm)
            budget.finish(status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--auxiliary-records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, choices=(20260905, 20260906), required=True)
    parser.add_argument("--gpu-python", type=Path, required=True)
    parser.add_argument("--gpu-runtime-receipt", type=Path, required=True)
    parser.add_argument(
        "--feature-mode", choices=FEATURE_MODES, default=FEATURE_MODES[0]
    )
    args = parser.parse_args()
    result = evaluate(
        args.compiled,
        args.auxiliary_records,
        args.output,
        args.seed,
        args.gpu_python,
        args.gpu_runtime_receipt,
        args.feature_mode,
    )
    print(
        json.dumps(
            {"completed_fits": result["completed_fits"], "release_eligible": False}
        )
    )


if __name__ == "__main__":
    main()
