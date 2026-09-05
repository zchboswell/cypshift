#!/usr/bin/env python3
"""One authenticated GPU MLP fit; chemistry and split policy remain on CPU."""

from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import io
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Applied before NumPy/Torch import; one computational CPU thread per worker.
for _key in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_key] = "1"

import numpy as np  # noqa: E402

HYPERPARAMETERS_BASE = {
    "input_dim": 4296,
    "hidden_dims": [256, 128],
    "output_dim": 8,
    "dropout": 0.1,
    "learning_rate": 0.001,
    "betas": [0.9, 0.999],
    "eps": 1e-8,
    "weight_decay": 0.0,
    "amsgrad": False,
    "batch_size": 128,
    "patience": 20,
    "min_delta": 0.0,
    "aux_weight": 0.25,
    "huber_delta": 1.0,
    "max_epochs": 200,
    "cpu_threads": 1,
    "vram_limit_bytes": 2147483648,
}
RUNTIME_RECEIPT_SHA256 = (
    "67b51adfd831eb03714a3928d0896764dc7c0edc31eebf6c31318eeba6af3085"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def load_request(
    path: Path,
) -> tuple[dict[str, Any], dict[str, np.ndarray], str, dict[str, Any]]:
    raw = path.read_bytes()
    request = json.loads(raw)
    expected_keys = {
        "schema",
        "identity",
        "arm",
        "mode",
        "epochs",
        "model_seed",
        "batch_seed",
        "dropout_seed",
        "hyperparameters",
        "files",
        "worker_sha256",
        "runtime_receipt",
    }
    if (
        set(request) != expected_keys
        or request["schema"] != "cypshift.mlp.fit.v1"
        or not isinstance(request["identity"], dict)
        or not request["identity"]
    ):
        raise ValueError("Invalid MLP request schema or identity")
    if request["arm"] not in {"direct", "real_aux", "shuffled_aux"} or request[
        "mode"
    ] not in {"stopped", "fixed"}:
        raise ValueError("Unsupported MLP arm or fit mode")
    expected_hyperparameters = {
        **HYPERPARAMETERS_BASE,
        "aux_weight": 0.0 if request["arm"] == "direct" else 0.25,
    }
    if request["hyperparameters"] != expected_hyperparameters:
        raise ValueError("MLP hyperparameters differ from frozen design")
    if (
        type(request["epochs"]) is not int
        or not 1 <= request["epochs"] <= 200
        or (request["mode"] == "stopped" and request["epochs"] != 200)
    ):
        raise ValueError("Invalid fixed epoch count or stopped epoch ceiling")
    if any(
        type(request[key]) is not int or not 0 <= request[key] < 2**63
        for key in ("model_seed", "batch_seed", "dropout_seed")
    ):
        raise ValueError("Invalid random seed")
    if request["worker_sha256"] != digest(Path(__file__).read_bytes()):
        raise ValueError("Worker source receipt differs")
    runtime_spec = request["runtime_receipt"]
    runtime_raw = Path(runtime_spec["path"]).read_bytes()
    if (
        runtime_spec["sha256"] != RUNTIME_RECEIPT_SHA256
        or digest(runtime_raw) != RUNTIME_RECEIPT_SHA256
    ):
        raise ValueError("Unverified GPU runtime receipt")
    runtime = json.loads(runtime_raw)
    if Path(sys.prefix) != Path(runtime["runtime"]).parent.parent:
        raise ValueError("Use the verified private GPU interpreter")
    required = {
        "train_x",
        "train_direct_y",
        "train_direct_mask",
        "train_aux_y",
        "train_aux_mask",
        "predict_x",
    }
    if request["mode"] == "stopped":
        required |= {"stop_x", "stop_direct_y", "stop_direct_mask"}
    if set(request["files"]) != required:
        raise ValueError("Request contains missing or forbidden array roles")
    arrays = {}
    for name, spec in request["files"].items():
        if (
            set(spec) != {"path", "sha256", "shape", "dtype"}
            or not Path(spec["path"]).is_absolute()
        ):
            raise ValueError("Array descriptor must bind an absolute NPY path")
        payload = Path(spec["path"]).read_bytes()
        if digest(payload) != spec["sha256"]:
            raise ValueError(f"Array receipt differs: {name}")
        value = np.load(io.BytesIO(payload), allow_pickle=False)
        expected_dtype = np.dtype("bool" if name.endswith("_mask") else "float32")
        width = 4296 if name.endswith("_x") else 4
        if (
            list(value.shape) != spec["shape"]
            or str(value.dtype) != spec["dtype"]
            or value.dtype != expected_dtype
            or value.ndim != 2
            or not 1 <= len(value) <= 3908
            or value.shape[1] != width
            or not np.isfinite(value).all()
        ):
            raise ValueError(
                f"Array layout or finite-placeholder policy differs: {name}"
            )
        arrays[name] = np.ascontiguousarray(value)
    for prefix in ("train", "stop"):
        if f"{prefix}_x" not in arrays:
            continue
        n = len(arrays[f"{prefix}_x"])
        if any(
            len(value) != n
            for name, value in arrays.items()
            if name.startswith(prefix + "_")
        ):
            raise ValueError("Within-population array lengths differ")
        if not arrays[f"{prefix}_direct_mask"].any(axis=0).all():
            raise ValueError("Every direct endpoint requires fit/stopping support")
    return request, arrays, digest(raw), runtime


def task_mean_loss(
    prediction: Any, targets: Any, mask: Any, *, huber: bool = False
) -> Any:
    """Equal weight per supported task; an empty task family is differentiable zero."""
    import torch.nn.functional as functional

    error = (
        functional.huber_loss(prediction, targets, reduction="none", delta=1.0)
        if huber
        else (prediction - targets).abs()
    )
    counts = mask.sum(dim=0)
    supported = counts > 0
    means = (error * mask).sum(dim=0) / counts.clamp_min(1)
    return (means * supported).sum() / supported.sum().clamp_min(1)


def _state_hash(state: dict[str, Any]) -> str:
    result = hashlib.sha256()
    for name, value in sorted(state.items()):
        array = value.detach().cpu().contiguous().numpy()
        result.update(
            canonical(
                {"name": name, "dtype": str(array.dtype), "shape": list(array.shape)}
            )
        )
        result.update(array.tobytes())
    return result.hexdigest()


def _same_state(left: Any, right: Any) -> bool:
    import torch

    if isinstance(left, torch.Tensor):
        return (
            isinstance(right, torch.Tensor)
            and left.dtype == right.dtype
            and left.shape == right.shape
            and torch.equal(left.cpu(), right.cpu())
        )
    if isinstance(left, dict):
        return (
            isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_same_state(value, right[key]) for key, value in left.items())
        )
    if isinstance(left, (tuple, list)):
        return (
            isinstance(right, type(left))
            and len(left) == len(right)
            and all(_same_state(a, b) for a, b in zip(left, right, strict=True))
        )
    return bool(left == right)


def _publish_directory(source: Path, target: Path) -> None:
    # Linux atomic no-clobber rename also rejects a racing empty destination.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        raise OSError(
            ctypes.get_errno(), "Cannot atomically publish new fit", str(target)
        )


def fit(request_path: Path, output: Path) -> dict[str, Any]:
    started, cpu_started = time.monotonic(), time.process_time()
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Worker never overwrites or resumes an output directory")
    if any((parent / ".git").exists() for parent in output.resolve().parents):
        raise ValueError("Worker outputs must stay outside Git")
    request, arrays, request_hash, runtime_receipt = load_request(request_path)
    import torch

    if (
        platform.python_version(),
        np.__version__,
        torch.__version__,
        torch.version.hip,
    ) != ("3.12.3", "1.26.4", "2.12.0+rocm7.14.0", "7.14.60850") or os.environ.get(
        "HSA_OVERRIDE_GFX_VERSION"
    ):
        raise ValueError("GPU software runtime differs from verified build")
    if "cypshift.slice" not in Path("/proc/self/cgroup").read_text():
        raise ValueError("Worker must run within the shared cypshift.slice")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("Exactly one verified GPU must be visible")
    properties = torch.cuda.get_device_properties(0)
    if properties.gcnArchName.split(":")[0] != "gfx1100":
        raise ValueError("Unverified GPU architecture")
    torch.cuda.set_device(0)
    torch.cuda.set_per_process_memory_fraction(2147483648 / properties.total_memory, 0)
    torch.cuda.reset_peak_memory_stats(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False

    def network() -> Any:
        return torch.nn.Sequential(
            torch.nn.Linear(4296, 256),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(256, 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.1),
            torch.nn.Linear(128, 8),
        )

    def optimizer_for(model: Any) -> Any:
        return torch.optim.Adam(
            model.parameters(),
            lr=0.001,
            betas=(0.9, 0.999),
            eps=1e-8,
            weight_decay=0,
            amsgrad=False,
        )

    torch.manual_seed(request["model_seed"])
    model = network()
    initial_hash = _state_hash(model.state_dict())
    model = model.to("cuda")
    optimizer = optimizer_for(model)
    torch.cuda.manual_seed_all(request["dropout_seed"])
    tensors = {
        name: torch.from_numpy(value).to("cuda") for name, value in arrays.items()
    }
    batch_rng = np.random.default_rng(request["batch_seed"])
    batch_hash = hashlib.sha256()
    epoch_hashes, history = [], []
    best, best_score, bad_epochs, steps = None, float("inf"), 0, 0
    last_loss = None
    aux_weight = request["hyperparameters"]["aux_weight"]
    for epoch in range(1, request["epochs"] + 1):
        order = batch_rng.permutation(len(arrays["train_x"])).astype(
            "int64", copy=False
        )
        batch_hash.update(order.tobytes())
        epoch_hashes.append(digest(order.tobytes()))
        model.train()
        for start in range(0, len(order), 128):
            take = torch.from_numpy(order[start : start + 128]).to("cuda")
            optimizer.zero_grad(set_to_none=True)
            prediction = model(tensors["train_x"][take])
            loss = task_mean_loss(
                prediction[:, :4],
                tensors["train_direct_y"][take],
                tensors["train_direct_mask"][take],
            )
            loss = loss + aux_weight * task_mean_loss(
                prediction[:, 4:],
                tensors["train_aux_y"][take],
                tensors["train_aux_mask"][take],
                huber=True,
            )
            if not torch.isfinite(loss).item():
                raise ValueError("Nonfinite training loss")
            loss.backward()
            if (
                not torch.stack(
                    [
                        torch.isfinite(parameter.grad).all()
                        for parameter in model.parameters()
                    ]
                )
                .all()
                .item()
            ):
                raise ValueError("Nonfinite training gradients")
            optimizer.step()
            steps += 1
            last_loss = float(loss.detach().item())
        model.eval()
        if request["mode"] == "stopped":
            with torch.no_grad():
                score = float(
                    task_mean_loss(
                        model(tensors["stop_x"])[:, :4],
                        tensors["stop_direct_y"],
                        tensors["stop_direct_mask"],
                    ).item()
                )
            if not np.isfinite(score):
                raise ValueError("Nonfinite direct stopping score")
            history.append(score)
            if score < best_score:  # min_delta0, strict improvement, earliest tie.
                best_score, bad_epochs = score, 0
                best = copy.deepcopy(
                    {
                        "model": model.state_dict(),
                        "optimizer": optimizer.state_dict(),
                        "selected_epoch": epoch,
                        "optimizer_steps": steps,
                    }
                )
            else:
                bad_epochs += 1
            if bad_epochs >= 20:
                break
    epochs_run = epoch
    if request["mode"] == "fixed":
        best = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "selected_epoch": epoch,
            "optimizer_steps": steps,
        }
    assert best is not None
    model.load_state_dict(best["model"], strict=True)
    model.eval()
    with torch.no_grad():
        before = model(tensors["predict_x"])[:, :4].detach().cpu()
        training_prediction = model(tensors["train_x"])
        final_loss = task_mean_loss(
            training_prediction[:, :4],
            tensors["train_direct_y"],
            tensors["train_direct_mask"],
        )
        final_loss = final_loss + aux_weight * task_mean_loss(
            training_prediction[:, 4:],
            tensors["train_aux_y"],
            tensors["train_aux_mask"],
            huber=True,
        )
    if not torch.isfinite(before).all() or not torch.isfinite(final_loss):
        raise ValueError("Nonfinite selected-checkpoint prediction or loss")
    best.update(
        request_sha256=request_hash,
        worker_sha256=request["worker_sha256"],
        hyperparameters=request["hyperparameters"],
        seeds={
            key: request[key] for key in ("model_seed", "batch_seed", "dropout_seed")
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".mlp-fit-", dir=output.parent))
    try:
        checkpoint = temporary / "checkpoint.pt"
        torch.save(best, checkpoint)
        # Adam's scalar step state stays on CPU; load_state_dict places moments
        # on the fresh model's GPU while preserving that optimizer convention.
        loaded = torch.load(checkpoint, weights_only=True, map_location="cpu")
        fresh = network().to("cuda")
        fresh.load_state_dict(loaded["model"], strict=True)
        fresh_optimizer = optimizer_for(fresh)
        fresh_optimizer.load_state_dict(loaded["optimizer"])
        if not _same_state(best["model"], fresh.state_dict()) or not _same_state(
            best["optimizer"], fresh_optimizer.state_dict()
        ):
            raise ValueError("Fresh model or optimizer reload differs")
        fresh.eval()
        with torch.no_grad():
            after = fresh(tensors["predict_x"])[:, :4].detach().cpu()
        torch.testing.assert_close(after, before, rtol=1e-6, atol=1e-6)
        prediction_path = temporary / "predictions.npy"
        np.save(
            prediction_path,
            after.numpy().astype("float32", copy=False),
            allow_pickle=False,
        )
        torch.cuda.synchronize(0)
        peak_allocated = torch.cuda.max_memory_allocated(0)
        peak_reserved = torch.cuda.max_memory_reserved(0)
        if peak_reserved > 2147483648:
            raise ValueError("GPU allocator exceeded the frozen2GiB budget")
        receipt = {
            "schema": "cypshift.mlp.fit_receipt.v1",
            "status": "complete",
            "request_sha256": request_hash,
            "worker_sha256": request["worker_sha256"],
            "runtime_receipt_sha256": request["runtime_receipt"]["sha256"],
            "identity": request["identity"],
            "arm": request["arm"],
            "mode": request["mode"],
            "hyperparameters": request["hyperparameters"],
            "selected_epoch": best["selected_epoch"],
            "epochs_run": epochs_run,
            "optimizer_steps": steps,
            "checkpoint_optimizer_steps": best["optimizer_steps"],
            "initial_state_sha256": initial_hash,
            "batch_order_sha256": batch_hash.hexdigest(),
            "batch_order_epoch_sha256": epoch_hashes,
            "seeds": best["seeds"],
            "finite_loss": True,
            "final_train_loss": float(final_loss.item()),
            "last_optimizer_loss": last_loss,
            "direct_stopping_mae_by_epoch": history,
            "selected_stopping_mae": None if request["mode"] == "fixed" else best_score,
            "checkpoint": {
                "path": str(output / "checkpoint.pt"),
                "sha256": digest(checkpoint.read_bytes()),
            },
            "predictions": {
                "path": str(output / "predictions.npy"),
                "sha256": digest(prediction_path.read_bytes()),
                "shape": list(after.shape),
                "dtype": "float32",
            },
            "reload_parity": {
                "atol": 1e-6,
                "rtol": 1e-6,
                "maximum_absolute_error": float((after - before).abs().max().item()),
                "model_and_optimizer_state_exact": True,
            },
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "torch": torch.__version__,
                "hip": torch.version.hip,
                "architecture": properties.gcnArchName,
                "device": properties.name,
                "closure_sha256": runtime_receipt["artifact_hashes"][
                    "resolved-closure.json"
                ],
            },
            "cpu_threads": 1,
            "affinity": sorted(os.sched_getaffinity(0)),
            "peak_allocated_bytes": peak_allocated,
            "peak_reserved_bytes": peak_reserved,
            "gpu_allocator_cap_bytes": 2147483648,
            "allocator_limit_scope": "PyTorch caching allocator; vendor/driver allocations are outside this cap",
            "process_cpu_seconds": time.process_time() - cpu_started,
            "wall_seconds": time.monotonic() - started,
        }
        (temporary / "receipt.json").write_bytes(canonical(receipt))
        for path in temporary.iterdir():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
            path.chmod(0o444)
        _publish_directory(temporary, output)
        return receipt
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = fit(args.request, args.output)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "selected_epoch": receipt["selected_epoch"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
