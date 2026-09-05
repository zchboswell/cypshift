#!/usr/bin/env python3
"""Recoverable 140-fit Phase 3 Tanimoto SVR comparison on frozen development folds."""

from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import io
import json
import os
import platform
import resource
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
from competition_data import balanced_nested_folds, load_development
from competition_features import featurize_binary_morgan
from competition_metrics import (
    direct_scores,
    paired_family_difference,
    release_decision,
)
from competition_runner import (
    affine_fit,
    canonical,
    digest,
    freeze_interrupted_fits,
    publish,
    spent_cpu,
)
from competition_svr import CS, EPSILON, inner_select_c, tanimoto_kernel
from sklearn.svm import SVR

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_BASELINE = (
    ROOT / "benchmarks/openadmet_cyp_2026/phase3_maplight_affine_v1_result.json"
)
SEED = 20260905


def _array_digest(value: np.ndarray) -> str:
    return digest(
        canonical({"shape": list(value.shape), "dtype": str(value.dtype)})
        + np.ascontiguousarray(value).tobytes()
    )


def _npz(values: dict[str, np.ndarray]) -> bytes:
    stream = io.BytesIO()
    np.savez(stream, **values)
    return stream.getvalue()


@contextmanager
def accounted_stage(directory: Path, *, planned_fits: int) -> Iterator[None]:
    """Account all kernel, seven-fit cell and scoring CPU, including failures."""
    directory.mkdir(parents=True, exist_ok=True)
    attempt = time.time_ns()
    wall, cpu = time.monotonic(), time.process_time()
    publish(
        directory / f"fit-start-{attempt}.json",
        canonical(
            {
                "started_epoch_seconds": time.time(),
                "threads": 16,
                "stage": directory.name,
                "planned_fits": planned_fits,
            }
        ),
    )
    status = "failed"
    try:
        yield
        status = "complete"
    finally:
        publish(
            directory / f"fit-attempt-{attempt}.json",
            canonical(
                {
                    "status": status,
                    "wall_seconds": time.monotonic() - wall,
                    "cpu_core_hours": (time.process_time() - cpu) / 3600,
                    "planned_fits": planned_fits,
                    "completed_fits": planned_fits if status == "complete" else None,
                    "recovery_granularity": "One whole outer-fold/endpoint cell; seven fits",
                }
            ),
        )


def _budget(output: Path) -> None:
    if spent_cpu(output) >= 100 or spent_cpu(output.parent) >= 1000:
        raise RuntimeError("Phase 3 CPU allocation exhausted before stage")


def cell_attempt_accounting(output: Path) -> dict[str, Any]:
    """Count completed seven-fit cells separately from unknown partial work."""
    counts = {"complete": 0, "failed": 0, "interrupted_unknown": 0, "unfinished": 0}
    for start in (output / "cells").rglob("fit-start-*.json"):
        record = json.loads(start.read_bytes())
        if record.get("planned_fits") != 7:
            raise ValueError("Unexpected SVR cell fit allocation")
        finish = start.with_name(start.name.replace("fit-start-", "fit-attempt-"))
        status = (
            json.loads(finish.read_bytes())["status"]
            if finish.exists()
            else "unfinished"
        )
        if status not in counts:
            raise ValueError("Unknown SVR cell attempt status")
        counts[status] += 1
    partial = sum(
        counts[status] for status in ("failed", "interrupted_unknown", "unfinished")
    )
    return {
        "completed_attempts": counts["complete"],
        "failed_attempts": counts["failed"],
        "interrupted_unknown_attempts": counts["interrupted_unknown"],
        "unfinished_attempts": counts["unfinished"],
        "known_completed_fit_count": counts["complete"] * 7,
        "incomplete_attempt_fit_count": None if partial else 0,
        "scope": "Completed-cell fits are counted exactly; partial-attempt fit counts are unknown and their CPU is charged",
    }


def authenticate_baseline(
    directory: Path,
    data: Any,
    outer: np.ndarray,
    inner: np.ndarray,
    *,
    public_record: Path = PUBLIC_BASELINE,
) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Use only OOF arrays publicly bound to the original same-fold experiment."""
    public_raw = public_record.read_bytes()
    expected = json.loads(public_raw)
    receipts = {"public_record_sha256": digest(public_raw)}
    for name, field in (
        ("experiment.json", "experiment_sha256"),
        ("oof.npz", "oof_sha256"),
    ):
        raw = (directory / name).read_bytes()
        if digest(raw) != expected[field]:
            raise ValueError(f"Original MapLight receipt differs: {name}")
        receipts[field] = digest(raw)
    experiment = json.loads((directory / "experiment.json").read_bytes())
    for key, value in {
        "source_receipts": data.receipts,
        "seed": SEED,
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer": outer.tolist(),
        "inner": inner.tolist(),
    }.items():
        if experiment.get(key) != value:
            raise ValueError(f"Original MapLight experiment population differs: {key}")
    raw_result = (directory / "result.json").read_bytes()
    result = json.loads(raw_result)
    for key in (
        "baseline",
        "candidate_scores",
        "decision",
        "experiment_sha256",
        "oof_sha256",
    ):
        if result.get(key) != expected[key]:
            raise ValueError(f"Original MapLight result differs: {key}")
    receipts["private_result_sha256"] = digest(raw_result)
    with np.load(directory / "oof.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    for key, value in {
        "names": np.asarray(data.names),
        "groups": np.asarray(data.groups),
        "outer": outer,
        "inner": inner,
    }.items():
        if key not in arrays or not np.array_equal(arrays[key], value):
            raise ValueError(f"Original MapLight OOF population differs: {key}")
    for key in ("baseline", "calibrated"):
        if arrays[key].shape != data.point.shape or not np.isfinite(arrays[key]).all():
            raise ValueError("Original MapLight OOF predictions invalid")
    return {key: arrays[key] for key in ("baseline", "calibrated")}, receipts


def cached_kernel(
    output: Path, data: Any, runtime: dict[str, str]
) -> tuple[np.ndarray, dict[str, Any]]:
    material = {
        "molecule_ids": list(data.molecule_ids),
        "raw_smiles_sha256": digest(canonical(list(data.raw_smiles))),
        "runtime": runtime,
        "radius": 2,
        "bits": 4096,
        "chirality": True,
        "implementation": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in (
                "competition_features.py",
                "competition_svr.py",
                "maplight_fixed_features.py",
            )
        },
    }
    key = digest(canonical(material))
    directory = output / "kernel" / key
    directory.mkdir(parents=True, exist_ok=True)
    receipt_file, kernel_file = directory / "receipt.json", directory / "kernel.npy"
    if receipt_file.exists():
        receipt = json.loads(receipt_file.read_bytes())
        if receipt.get("inputs") != material or receipt.get("kernel_sha256") != digest(
            kernel_file.read_bytes()
        ):
            raise ValueError(
                "Damaged kernel checkpoint; preserve it for documented repair"
            )
        kernel = np.load(kernel_file, allow_pickle=False)
    else:
        _budget(output)
        with accounted_stage(directory, planned_fits=0):
            kernel = tanimoto_kernel(featurize_binary_morgan(data.raw_smiles))
            stream = io.BytesIO()
            np.save(stream, kernel, allow_pickle=False)
            publish(kernel_file, stream.getvalue())
            receipt = {
                "inputs": material,
                "key": key,
                "kernel_sha256": digest(stream.getvalue()),
            }
            publish(receipt_file, canonical(receipt))
    if (
        kernel.shape != (len(data.names), len(data.names))
        or kernel.dtype != np.dtype("float64")
        or not np.isfinite(kernel).all()
    ):
        raise ValueError("Invalid kernel checkpoint layout")
    return kernel, receipt


def cached_cell(
    output: Path,
    kernel: np.ndarray,
    data: Any,
    outer: np.ndarray,
    inner: np.ndarray,
    fold: int,
    endpoint: int,
    identity: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Checkpoint seven fits atomically; a partial cell reruns all seven."""
    groups = np.asarray(data.groups)
    train_rows, heldout = np.flatnonzero(outer != fold), np.flatnonzero(outer == fold)
    if (
        not len(train_rows)
        or not len(heldout)
        or set(groups[train_rows]).intersection(groups[heldout])
    ):
        raise ValueError("Family crosses outer boundary or cell is empty")
    scoped_inner = inner[fold, train_rows]
    if set(scoped_inner.tolist()) != {0, 1, 2} or np.any(inner[fold, heldout] != -1):
        raise ValueError("Invalid inner scope")
    for group in set(groups[train_rows]):
        if len(set(scoped_inner[groups[train_rows] == group])) != 1:
            raise ValueError("Family crosses inner boundary")
    point, low, high = (
        getattr(data, name)[train_rows, endpoint] for name in ("point", "low", "high")
    )
    mask = data.training_mask[train_rows, endpoint]
    material = {
        "identity": identity,
        "outer_fold": fold,
        "endpoint": endpoint,
        "training_population": train_rows.tolist(),
        "heldout_population": heldout.tolist(),
        "inner_folds": scoped_inner.tolist(),
        "groups": list(data.groups),
        "kernel_sha256": _array_digest(kernel),
        "outer_training_labels": {
            name: _array_digest(value)
            for name, value in (
                ("point", point),
                ("low", low),
                ("high", high),
                ("mask", mask),
            )
        },
        "C": list(CS),
        "epsilon": EPSILON,
    }
    key = digest(canonical(material))
    directory = output / "cells" / key
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path, prediction_path = (
        directory / "receipt.json",
        directory / "predictions.npz",
    )
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        if receipt.get("inputs") != material or receipt.get(
            "prediction_sha256"
        ) != digest(prediction_path.read_bytes()):
            raise ValueError(
                "Damaged cell checkpoint; preserve it for documented repair"
            )
        with np.load(prediction_path, allow_pickle=False) as archive:
            raw, calibrated = archive["raw"], archive["calibrated"]
        if any(
            value.shape != (len(heldout),) or not np.isfinite(value).all()
            for value in (raw, calibrated)
        ):
            raise ValueError("Invalid cell checkpoint predictions")
        return raw, calibrated, {**receipt, "reused": True}
    _budget(output)
    with accounted_stage(directory, planned_fits=7):
        chosen, oof = inner_select_c(
            kernel[np.ix_(train_rows, train_rows)], point, low, high, mask, scoped_inner
        )
        eligible = np.isfinite(point)
        slope, intercept = affine_fit(
            oof[chosen][eligible], low[eligible], high[eligible]
        )
        train = train_rows[mask]
        model = SVR(C=chosen, epsilon=EPSILON, kernel="precomputed", cache_size=256)
        model.fit(kernel[np.ix_(train, train)], data.point[train, endpoint])
        raw = np.asarray(
            model.predict(kernel[np.ix_(heldout, train)]), dtype=np.float64
        )
        calibrated = slope * raw + intercept
        if raw.shape != (len(heldout),) or not np.isfinite(calibrated).all():
            raise ValueError("Invalid outer SVR predictions")
        prediction_raw = _npz(
            {
                "raw": raw,
                "calibrated": calibrated,
                "inner_C1": oof[1.0],
                "inner_C10": oof[10.0],
            }
        )
        publish(prediction_path, prediction_raw)
        receipt = {
            "key": key,
            "inputs": material,
            "prediction_sha256": digest(prediction_raw),
            "chosen_C": chosen,
            "slope": slope,
            "intercept": intercept,
            "fits": 7,
            "inner_oof_sha256": {str(c): _array_digest(oof[c]) for c in CS},
        }
        publish(receipt_path, canonical(receipt))
    return raw, calibrated, {**receipt, "reused": False}


def evaluate(
    compiled: Path,
    output: Path,
    *,
    expected_compiled_sha256: str,
    baseline_experiment: Path,
) -> dict[str, Any]:
    if ROOT == output.resolve() or ROOT in output.resolve().parents:
        raise ValueError("Experiment output must stay outside Git")
    if not (
        output.parent.resolve()
        == compiled.parent.resolve()
        == baseline_experiment.parent.resolve()
    ):
        raise ValueError(
            "Compiled, baseline and output must share the Phase 3 compute root"
        )
    if digest((compiled / "manifest.json").read_bytes()) != expected_compiled_sha256:
        raise ValueError("Compiled development receipt differs")
    output.mkdir(parents=True, exist_ok=True)
    with (output.parent / "compute.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze_interrupted_fits(output.parent)
        _budget(output)
        return _evaluate_locked(
            compiled, output, baseline_experiment, expected_compiled_sha256
        )


def _evaluate_locked(
    compiled: Path, output: Path, baseline_experiment: Path, compiled_sha: str
) -> dict[str, Any]:
    started = time.monotonic()
    runtime = {
        "python": platform.python_version(),
        **{
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "scikit-learn", "rdkit")
        },
    }
    if runtime != {
        "python": "3.10.13",
        "numpy": "1.25.2",
        "scipy": "1.11.2",
        "scikit-learn": "1.3.0",
        "rdkit": "2023.3.3",
    }:
        raise ValueError("Use the locked MapLight research runtime")
    # Linux enforces the remaining run/program CPU allocation even inside a cell.
    # A killed stage is conservatively charged by freeze_interrupted_fits on retry.
    remaining = min(100 - spent_cpu(output), 1000 - spent_cpu(output.parent))
    cpu_limit = max(1, int(time.process_time() + remaining * 3600))
    old_limit = resource.getrlimit(resource.RLIMIT_CPU)[1]
    if old_limit != resource.RLIM_INFINITY:
        cpu_limit = min(cpu_limit, old_limit)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    data = load_development(compiled)
    outer, inner = balanced_nested_folds(data.groups, data.training_mask, seed=SEED)
    reference, baseline_receipts = authenticate_baseline(
        baseline_experiment, data, outer, inner
    )
    identity = {
        "candidate": "tanimoto-svr-C1-C10-inner-affine",
        "seed": SEED,
        "planned_fits": 140,
        "runtime": runtime,
        "compiled_manifest_sha256": compiled_sha,
        "baseline_receipts": baseline_receipts,
        "source_receipts": data.receipts,
        "names": list(data.names),
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer": outer.tolist(),
        "inner": inner.tolist(),
        "implementation": {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in (
                "competition_svr_runner.py",
                "competition_svr.py",
                "competition_features.py",
                "competition_data.py",
                "competition_metrics.py",
                "competition_runner.py",
            )
        },
        "recovery_granularity": "Seven fits per outer-fold/endpoint cell; preserve and charge partial attempts",
        "deployment_if_eligible": {
            "training_scope": "Retained development only; reserved comparison stays closed",
            "selection": "Three family-balanced full-development folds, seed 20260905; C in {1,10} by pooled inner OOF ST-RAE",
            "calibration": "Fit the same bounded affine interval-loss transform on selected-C full-development OOF",
            "fit_budget": {"selection": 24, "production": 4, "total": 28},
            "prediction": "Fit selected C on all eligible development labels per endpoint; predict raw blinded-test Morgan radius2/4096 using the identical frozen runtime",
            "release": "Apply raw or affine recipe according to qualified nested evidence; validate the actual CSV under current upload rules and provide manual handoff",
            "executed_by_this_evaluator": False,
        },
    }
    frozen = output / "experiment.json"
    if frozen.exists() and frozen.read_bytes() != canonical(identity):
        raise ValueError("Experiment identity changed; use a new prospective attempt")
    publish(frozen, canonical(identity))
    # Refuse to overwrite a completed result; authenticate and return it on retry.
    result_path = output / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_bytes())
        if result["experiment_sha256"] != digest(frozen.read_bytes()) or result[
            "oof_sha256"
        ] != digest((output / "oof.npz").read_bytes()):
            raise ValueError("Completed SVR result receipt differs")
        return result
    kernel, kernel_receipt = cached_kernel(output, data, runtime)
    raw, calibrated = (
        np.full(data.point.shape, np.nan),
        np.full(data.point.shape, np.nan),
    )
    cells = []
    for fold in range(5):
        for endpoint in range(4):
            pred, adjusted, receipt = cached_cell(
                output,
                kernel,
                data,
                outer,
                inner,
                fold,
                endpoint,
                {"experiment_sha256": digest(frozen.read_bytes())},
            )
            raw[outer == fold, endpoint], calibrated[outer == fold, endpoint] = (
                pred,
                adjusted,
            )
            cells.append(receipt)
            publish(
                output / "progress.json",
                canonical(
                    {
                        "completed_fits": len(cells) * 7,
                        "planned_fits": 140,
                        "cpu_core_hours": spent_cpu(output),
                        "outer_fold": fold,
                        "endpoint": endpoint,
                    }
                ),
            )
            print(f"Completed {len(cells) * 7}/140 SVR fits", flush=True)
    names, groups = np.asarray(data.names), np.asarray(data.groups)
    publish(
        output / "oof.npz",
        _npz(
            {
                "raw": raw,
                "calibrated": calibrated,
                "names": names,
                "groups": groups,
                "outer": outer,
                "inner": inner,
            }
        ),
    )
    _budget(output)
    with accounted_stage(output / "scoring", planned_fits=0):
        comparison = {}
        reference_scores = {
            name: direct_scores(names, groups, data.point, data.low, data.high, values)
            for name, values in reference.items()
        }
        for name, prediction in (("raw_svr", raw), ("affine_svr", calibrated)):
            scores = direct_scores(
                names, groups, data.point, data.low, data.high, prediction
            )
            against = {}
            for baseline, values in reference.items():
                paired = paired_family_difference(
                    names, groups, data.point, data.low, data.high, prediction, values
                )
                baseline_scores = reference_scores[baseline]
                against[baseline] = {
                    "baseline_scores": baseline_scores,
                    "paired_family": paired,
                    "decision": release_decision(scores, baseline_scores, paired),
                }
            comparison[name] = {"scores": scores, "against": against}
    report = {
        "status": "complete",
        "candidate": identity["candidate"],
        "comparisons": comparison,
        "incumbent_reference": "calibrated",
        "promotion_reference": "baseline",
        "completed_recipe_fits": 140,
        "new_completed_cell_fits": 7 * sum(not cell["reused"] for cell in cells),
        "cell_attempt_accounting": cell_attempt_accounting(output),
        "cells": [
            {
                key: cell[key]
                for key in (
                    "key",
                    "chosen_C",
                    "slope",
                    "intercept",
                    "reused",
                    "prediction_sha256",
                    "inner_oof_sha256",
                )
            }
            for cell in cells
        ],
        "kernel_receipt": kernel_receipt,
        "experiment_sha256": digest(frozen.read_bytes()),
        "oof_sha256": digest((output / "oof.npz").read_bytes()),
        "budget_accounted_cpu_core_hours": spent_cpu(output),
        "program_accounted_cpu_core_hours": spent_cpu(output.parent),
        "wall_seconds": time.monotonic() - started,
        "reserved_numeric_targets_opened": 0,
        "submission_produced": False,
        "deployment_next_steps": identity["deployment_if_eligible"],
        "execution_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    publish(result_path, canonical(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", required=True, type=Path)
    parser.add_argument("--compiled-sha256", required=True)
    parser.add_argument("--baseline-experiment", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if ROOT == args.output.resolve() or ROOT in args.output.resolve().parents:
        raise ValueError("Experiment output must stay outside Git")
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:16])
    resource.setrlimit(resource.RLIMIT_AS, (20 * 1024**3, 20 * 1024**3))
    from threadpoolctl import threadpool_limits

    try:
        with threadpool_limits(limits=16):
            report = evaluate(
                args.compiled,
                args.output,
                expected_compiled_sha256=args.compiled_sha256,
                baseline_experiment=args.baseline_experiment,
            )
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        publish(
            args.output / f"failure-{time.time_ns()}.json",
            canonical({"type": type(exc).__name__, "message": str(exc)}),
        )
        raise
    print(
        json.dumps(
            {
                name: result["against"]["calibrated"]["decision"]
                for name, result in report["comparisons"].items()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
