"""Run the frozen R1-through-R5 CatBoost shadow predictions without scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import run_nan_compat as nan

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_stage_a_contract.json"
NAN_CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_nan_compat_contract.json"
FEATURE_ROOT = (
    ROOT / "artifacts/benchmarks/maplight-fixed-upstream-int8-nan-features-v1-build-1"
)
FEATURE_REPEAT_ROOT = (
    ROOT / "artifacts/benchmarks/maplight-fixed-upstream-int8-nan-features-v1-build-2"
)
FEATURE_MANIFEST_PATH = FEATURE_ROOT / "feature_manifest.json"
FEATURE_REPEAT_MANIFEST_PATH = FEATURE_REPEAT_ROOT / "feature_manifest.json"
TARGET_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-targets-v1"
TARGET_MANIFEST_PATH = TARGET_ROOT / "target_manifest.json"
SHADOW_ROWS_PATH = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1/shadow_rows.csv"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-predictions-v1"
BLOCKER_ROOT = ROOT / "artifacts/blockers/maplight-fixed-stage-a-predictions-v1-blocker"

CONTRACT_SHA256 = "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710"
NAN_CONTRACT_SHA256 = "52f01f93470cfe461e7ee9fed0ff3a06d7362aceaef343da0c5840d2a74bea09"
FEATURE_MANIFEST_SHA256 = (
    "5a3b038e26f790e5bcd164c11c810cbc4d7ce12f9369cd92b8bb503cfeb7f32c"
)
FEATURE_REPEAT_MANIFEST_SHA256 = (
    "0afd641c5802e6f3b40e3808c4a99fc546a9de1e5ce2595e68a22f6d9cbe6300"
)
TARGET_MANIFEST_SHA256 = (
    "716ffd20d169b305e5014e368b222cf15b347f48ff216ef9cfebfafc0791705a"
)
SHADOW_ROWS_SHA256 = "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
FEATURE_SOURCE_REVISION = "9d6b719303cb18325d9598d5fadd8854d06f7952"
TARGET_SOURCE_REVISION = "1275cbc05aed77e6dbccaca3936eb3f3951ac4b9"

TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
PROTOCOLS = ("scaffold", "community")
REPEATS = (0, 1, 2)
BLOCKS = ("binary_morgan", "morgan_count", "avalon_count", "erg", "rdkit_descriptors")
FEATURE_COUNTS = {
    "binary_morgan": 2048,
    "morgan_count": 1024,
    "avalon_count": 1024,
    "erg": 315,
    "rdkit_descriptors": 200,
}
CANDIDATES = (
    ("r1_binary_morgan_catboost_seed_1", ("binary_morgan",), 1),
    ("r2_morgan_count_catboost_seed_1", ("morgan_count",), 1),
    ("r3_morgan_avalon_catboost_seed_1", ("morgan_count", "avalon_count"), 1),
    (
        "r4_morgan_avalon_erg_catboost_seed_1",
        ("morgan_count", "avalon_count", "erg"),
        1,
    ),
    *(
        (
            f"r5_maplight_fixed_catboost_seed_{seed}",
            ("morgan_count", "avalon_count", "erg", "rdkit_descriptors"),
            seed,
        )
        for seed in (1, 2, 3, 4, 5)
    ),
)
PREDICTION_COLUMNS = (
    "task",
    "protocol",
    "repeat",
    "molecule_id",
    "source_row",
    *(item[0] for item in CANDIDATES),
    "r5_maplight_fixed_catboost_mean_probability",
)


class StageAModelError(RuntimeError):
    """Fail-closed model execution error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StageAModelError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"JSON root differs: {path}")
    return cast(dict[str, Any], value)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _git(arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _clean_revision() -> str:
    _require(not _git(("status", "--porcelain", "--untracked-files=all")), "dirty tree")
    revision = _git(("rev-parse", "HEAD"))
    identity = _git(
        ("show", "-s", "--format=%G?%x00%an%x00%ae%x00%cn%x00%ce", revision)
    ).split("\0")
    _require(
        identity
        == [
            "G",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
            "zchboswell",
            "261114960+zchboswell@users.noreply.github.com",
        ],
        "signature or authorship differs",
    )
    relative = SCRIPT_PATH.relative_to(ROOT).as_posix()
    blob = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    _require(hashlib.sha256(blob).hexdigest() == _sha256(SCRIPT_PATH), "script differs")
    return revision


def _readonly_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and not bool(
            os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        )
    )


def _readonly_root(path: Path) -> bool:
    return (
        path.is_dir()
        and not path.is_symlink()
        and not bool(
            os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        )
    )


def _verify_inputs() -> tuple[str, dict[str, Any], dict[str, Any]]:
    _, revision = nan._verify_common()
    _require(revision == _clean_revision(), "revision verification differs")
    for path, expected in (
        (CONTRACT_PATH, CONTRACT_SHA256),
        (NAN_CONTRACT_PATH, NAN_CONTRACT_SHA256),
        (FEATURE_MANIFEST_PATH, FEATURE_MANIFEST_SHA256),
        (FEATURE_REPEAT_MANIFEST_PATH, FEATURE_REPEAT_MANIFEST_SHA256),
        (TARGET_MANIFEST_PATH, TARGET_MANIFEST_SHA256),
        (SHADOW_ROWS_PATH, SHADOW_ROWS_SHA256),
    ):
        _require(_sha256(path) == expected, f"input hash differs: {path}")
    for root in (FEATURE_ROOT, FEATURE_REPEAT_ROOT, TARGET_ROOT):
        _require(_readonly_root(root), f"input root is writable: {root}")
    feature = nan._validate_build(FEATURE_ROOT, 1, FEATURE_SOURCE_REVISION)
    nan._validate_build(FEATURE_REPEAT_ROOT, 2, FEATURE_SOURCE_REVISION)
    for name in ("feature_rows.csv", *(f"{block}.npy" for block in BLOCKS)):
        _require(
            (FEATURE_ROOT / name).read_bytes()
            == (FEATURE_REPEAT_ROOT / name).read_bytes(),
            "feature repeat differs",
        )
    target = _json(TARGET_MANIFEST_PATH)
    _require(
        target["source_revision"] == TARGET_SOURCE_REVISION, "target revision differs"
    )
    _require(
        target["accounting"]["public_test_labels_parsed"] == 0,
        "target boundary differs",
    )
    _require(len(target["cells"]) == 18, "target cell count differs")
    return revision, feature, target


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: str(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _feature_matrix(
    arrays: Mapping[str, np.ndarray[Any, Any]], blocks: Sequence[str]
) -> np.ndarray[Any, Any]:
    selected = [arrays[name] for name in blocks]
    return (
        selected[0]
        if len(selected) == 1
        else np.ascontiguousarray(np.concatenate(selected, axis=1))
    )


def _peak_rss_gib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)


def _readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _remove(root: Path) -> None:
    if root.exists():
        for path in root.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        root.chmod(0o755)
        shutil.rmtree(root)


def _validate_cell_output(
    root: Path,
    cell: str,
    target_record: Mapping[str, Any],
    revision: str,
    expected_validation_rows: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    _require(_readonly_root(root), "cell root is writable")
    _require(
        {path.name for path in root.iterdir()}
        == {"cell_receipt.json", "predictions.csv"},
        "cell file set differs",
    )
    _require(
        all(_readonly_file(path) for path in root.iterdir()), "cell file is writable"
    )
    receipt = _json(root / "cell_receipt.json")
    _require(
        receipt["schema_version"] == "cypshift.maplight_stage_a_cell_predictions.v1",
        "cell receipt schema differs",
    )
    _require(
        receipt["cell"] == cell
        and receipt["source_revision"] == revision
        and receipt["target_sha256"] == target_record["sha256"]
        and receipt["feature_manifest_sha256"] == FEATURE_MANIFEST_SHA256,
        "cell receipt identity differs",
    )
    prediction_path = root / "predictions.csv"
    _require(
        receipt["prediction_path"] == "predictions.csv"
        and _sha256(prediction_path) == receipt["prediction_sha256"],
        "cell prediction binding differs",
    )
    rows = _read_csv(prediction_path)
    _require(
        len(rows) == receipt["rows"] == len(expected_validation_rows),
        "cell row count differs",
    )
    _require(
        tuple(rows[0]) == PREDICTION_COLUMNS if rows else not expected_validation_rows,
        "prediction columns differ",
    )
    task, protocol, repeat_text = cell.split("__")
    repeat = int(repeat_text.removeprefix("repeat_"))
    _require(
        [(row["molecule_id"], row["source_row"]) for row in rows]
        == [
            (row["molecule_id"], row["source_row"]) for row in expected_validation_rows
        ],
        "prediction row alignment differs",
    )
    _require(
        all(
            row["task"] == task
            and row["protocol"] == protocol
            and row["repeat"] == str(repeat)
            for row in rows
        ),
        "prediction cell fields differ",
    )
    values: dict[str, np.ndarray[Any, Any]] = {}
    for configuration, _, _ in CANDIDATES:
        vector = np.asarray(
            [float(row[configuration]) for row in rows], dtype=np.float64
        )
        _require(
            bool(np.isfinite(vector).all())
            and bool(((vector >= 0) & (vector <= 1)).all()),
            "retained prediction range differs",
        )
        values[configuration] = vector
    retained_mean = np.asarray(
        [float(row["r5_maplight_fixed_catboost_mean_probability"]) for row in rows],
        dtype=np.float64,
    )
    expected_mean = np.mean(
        np.stack(
            [
                values[f"r5_maplight_fixed_catboost_seed_{seed}"]
                for seed in (1, 2, 3, 4, 5)
            ]
        ),
        axis=0,
        dtype=np.float64,
    )
    _require(
        np.array_equal(retained_mean, expected_mean),
        "retained mean probability differs",
    )
    fits = receipt["fits"]
    _require(
        isinstance(fits, list) and len(fits) == len(CANDIDATES),
        "cell fit count differs",
    )
    for fit, (configuration, blocks, seed) in zip(fits, CANDIDATES, strict=True):
        _require(isinstance(fit, dict), "fit receipt differs")
        _require(
            fit["configuration_id"] == configuration
            and fit["feature_blocks"] == list(blocks)
            and fit["feature_count"] == sum(FEATURE_COUNTS[name] for name in blocks)
            and fit["seed"] == seed
            and fit["train_rows"] == target_record["rows"]
            and fit["validation_rows"] == len(rows)
            and fit["class_order"] == [0, 1]
            and fit["prediction_element_sha256"]
            == hashlib.sha256(values[configuration].tobytes()).hexdigest(),
            "fit receipt differs",
        )
    expected_accounting = {
        "training_targets_parsed": target_record["rows"],
        "validation_targets_parsed": 0,
        "model_fits": 9,
        "model_prediction_vectors": 9,
        "derived_prediction_vectors": 1,
        "metric_evaluations": 0,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
    }
    _require(receipt["accounting"] == expected_accounting, "cell accounting differs")
    _require(
        receipt["derived_vectors"] == 1
        and 0 <= float(receipt["runtime_seconds"]) <= 28800
        and 0 <= float(receipt["peak_rss_gib"]) <= 12,
        "cell resource receipt differs",
    )
    return {
        "receipt_sha256": _sha256(root / "cell_receipt.json"),
        "prediction_sha256": receipt["prediction_sha256"],
        "rows": len(rows),
    }


def _worker(
    cell: str, target_path: Path, expected_target_hash: str, output: Path
) -> int:
    start = time.perf_counter()
    revision, _, _ = _verify_inputs()
    _require(_sha256(target_path) == expected_target_hash, "cell target hash differs")
    task, protocol, repeat_text = cell.split("__")
    repeat = int(repeat_text.removeprefix("repeat_"))
    targets = _read_csv(target_path)
    target_by_id = {row["molecule_id"]: int(row["target"]) for row in targets}
    _require(len(target_by_id) == len(targets), "cell target identities differ")
    feature_rows = _read_csv(FEATURE_ROOT / "feature_rows.csv")
    shadow = _read_csv(SHADOW_ROWS_PATH)
    _require(len(feature_rows) == len(shadow) == 30038, "row count differs")
    _require(
        [row["molecule_id"] for row in feature_rows]
        == [row["molecule_id"] for row in shadow],
        "feature row order differs",
    )
    index_by_id = {row["molecule_id"]: index for index, row in enumerate(feature_rows)}
    train_index = np.array(
        [index_by_id[row["molecule_id"]] for row in targets], dtype=np.int64
    )
    validation_rows = [
        row
        for row in shadow
        if row["task"] == task and row[f"{protocol}_repeat_{repeat}_outer_fold"] == "0"
    ]
    validation_index = np.array(
        [index_by_id[row["molecule_id"]] for row in validation_rows], dtype=np.int64
    )
    _require(
        not set(target_by_id) & {row["molecule_id"] for row in validation_rows},
        "validation identity entered training",
    )
    y = np.array([target_by_id[row["molecule_id"]] for row in targets], dtype=np.int8)
    _require(set(y.tolist()) == {0, 1}, "training class support differs")
    arrays = {
        name: np.load(FEATURE_ROOT / f"{name}.npy", allow_pickle=False, mmap_mode="r")
        for name in BLOCKS
    }
    output.mkdir()
    progress_path = output / "worker_progress.json"
    progress_path.write_bytes(
        _json_bytes(
            {"cell": cell, "training_targets_parsed": len(targets), "completed_fits": 0}
        )
    )
    predictions: dict[str, np.ndarray[Any, Any]] = {}
    fits: list[dict[str, object]] = []
    catboost = __import__("catboost")
    for configuration, blocks, seed in CANDIDATES:
        matrix = _feature_matrix(arrays, blocks)
        fit_start = time.perf_counter()
        model = catboost.CatBoostClassifier(
            random_strength=2, random_seed=seed, verbose=0, loss_function="Logloss"
        )
        model.fit(matrix[train_index], y)
        classes = [int(value) for value in model.classes_]
        _require(classes == [0, 1], "CatBoost class order differs")
        probability = np.asarray(
            model.predict_proba(matrix[validation_index])[:, 1], dtype=np.float64
        )
        _require(
            bool(np.isfinite(probability).all())
            and bool(((probability >= 0) & (probability <= 1)).all()),
            "prediction range differs",
        )
        predictions[configuration] = probability
        fits.append(
            {
                "configuration_id": configuration,
                "feature_blocks": list(blocks),
                "feature_count": int(matrix.shape[1]),
                "seed": seed,
                "train_rows": len(train_index),
                "validation_rows": len(validation_index),
                "class_order": classes,
                "runtime_seconds": time.perf_counter() - fit_start,
                "prediction_element_sha256": hashlib.sha256(
                    probability.tobytes()
                ).hexdigest(),
                "resolved_parameters": model.get_all_params(),
            }
        )
        progress_path.write_bytes(
            _json_bytes(
                {
                    "cell": cell,
                    "training_targets_parsed": len(targets),
                    "completed_fits": len(fits),
                }
            )
        )
    r5 = [
        predictions[f"r5_maplight_fixed_catboost_seed_{seed}"]
        for seed in (1, 2, 3, 4, 5)
    ]
    mean = np.asarray(np.mean(np.stack(r5), axis=0, dtype=np.float64))
    prediction_path = output / "predictions.csv"
    with prediction_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PREDICTION_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for index, row in enumerate(validation_rows):
            record = {
                "task": task,
                "protocol": protocol,
                "repeat": str(repeat),
                "molecule_id": row["molecule_id"],
                "source_row": row["source_row"],
            }
            record.update(
                {
                    name: repr(float(values[index]))
                    for name, values in predictions.items()
                }
            )
            record["r5_maplight_fixed_catboost_mean_probability"] = repr(
                float(mean[index])
            )
            writer.writerow(record)
    runtime_seconds = time.perf_counter() - start
    peak_rss_gib = _peak_rss_gib()
    receipt = {
        "schema_version": "cypshift.maplight_stage_a_cell_predictions.v1",
        "source_revision": revision,
        "cell": cell,
        "task": task,
        "protocol": protocol,
        "repeat": repeat,
        "target_sha256": expected_target_hash,
        "feature_manifest_sha256": FEATURE_MANIFEST_SHA256,
        "prediction_path": "predictions.csv",
        "prediction_sha256": _sha256(prediction_path),
        "rows": len(validation_rows),
        "fits": fits,
        "derived_vectors": 1,
        "runtime_seconds": runtime_seconds,
        "peak_rss_gib": peak_rss_gib,
        "accounting": {
            "training_targets_parsed": len(targets),
            "validation_targets_parsed": 0,
            "model_fits": 9,
            "model_prediction_vectors": 9,
            "derived_prediction_vectors": 1,
            "metric_evaluations": 0,
            "public_test_rows_used": 0,
            "public_test_labels_parsed": 0,
        },
    }
    progress_path.unlink()
    (output / "cell_receipt.json").write_bytes(_json_bytes(receipt))
    _require(
        runtime_seconds <= 28800 and peak_rss_gib <= 12,
        "cell resource cap exceeded",
    )
    _readonly(output)
    return 0


def _write_failure(
    error: Exception,
    revision: str | None,
    completed_cells: Sequence[str],
    current_cell: str | None,
    current_target_rows: int,
    current_completed_fits: int,
    elapsed: float,
) -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not BLOCKER_ROOT.exists(),
        "prediction output exists",
    )
    staging = Path(
        tempfile.mkdtemp(prefix=".stage-a-prediction-blocker-", dir=BLOCKER_ROOT.parent)
    )
    target = _json(TARGET_MANIFEST_PATH)
    completed_fits = len(completed_cells) * 9 + current_completed_fits
    receipt = {
        "schema_version": "cypshift.maplight_stage_a_prediction_failure.v1",
        "source_revision": revision,
        "implementation_sha256": _sha256(SCRIPT_PATH),
        "contracts": {
            "stage_a": CONTRACT_SHA256,
            "nan_compatibility": NAN_CONTRACT_SHA256,
        },
        "inputs": {
            "feature_manifest": FEATURE_MANIFEST_SHA256,
            "feature_repeat_manifest": FEATURE_REPEAT_MANIFEST_SHA256,
            "target_manifest": TARGET_MANIFEST_SHA256,
            "shadow_rows": SHADOW_ROWS_SHA256,
        },
        "failure": {
            "kind": type(error).__name__,
            "message": str(error),
            "current_cell": current_cell,
        },
        "completed_cells": list(completed_cells),
        "runtime_seconds": elapsed,
        "peak_rss_gib": _peak_rss_gib(),
        "accounting": {
            "training_target_values_parsed": sum(
                int(target["cells"][cell]["rows"]) for cell in completed_cells
            )
            + current_target_rows,
            "validation_target_values_parsed": 0,
            "model_fits_completed": completed_fits,
            "model_prediction_vectors_completed": completed_fits,
            "metric_evaluations": 0,
            "public_test_rows_used": 0,
            "public_test_labels_parsed": 0,
        },
        "claim_boundary": "Stage A prediction failure; no validation/public-test label or metric access.",
    }
    (staging / "failure_receipt.json").write_bytes(_json_bytes(receipt))
    _readonly(staging)
    staging.rename(BLOCKER_ROOT)
    return BLOCKER_ROOT


def run_predictions() -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not BLOCKER_ROOT.exists(),
        "prediction output exists",
    )
    start = time.perf_counter()
    revision: str | None = None
    target: dict[str, Any] | None = None
    staging: Path | None = None
    scratch: Path | None = None
    completed_cells: list[str] = []
    current_cell: str | None = None
    try:
        revision, _, target = _verify_inputs()
        staging = Path(
            tempfile.mkdtemp(prefix=".stage-a-predictions-", dir=OUTPUT_ROOT.parent)
        )
        scratch = Path(tempfile.mkdtemp(prefix="cypshift-stage-a-models-", dir="/tmp"))
        cells_root = staging / "cells"
        cells_root.mkdir()
        for cell, record in sorted(target["cells"].items()):
            current_cell = cell
            cell_output = cells_root / cell
            cell_scratch = scratch / cell
            cell_scratch.mkdir()
            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--_cell",
                cell,
                "--_target",
                str(TARGET_ROOT / record["path"]),
                "--_target-sha256",
                record["sha256"],
                "--_output",
                str(cell_output),
            ]
            subprocess.run(command, cwd=cell_scratch, check=True, timeout=28800)
            completed_cells.append(cell)
            current_cell = None
        receipts = {}
        total_rows = 0
        shadow_rows = _read_csv(SHADOW_ROWS_PATH)
        for cell in sorted(target["cells"]):
            root = cells_root / cell
            task, protocol, repeat_text = cell.split("__")
            repeat = int(repeat_text.removeprefix("repeat_"))
            expected_validation_rows = [
                row
                for row in shadow_rows
                if row["task"] == task
                and row[f"{protocol}_repeat_{repeat}_outer_fold"] == "0"
            ]
            record = _validate_cell_output(
                root,
                cell,
                target["cells"][cell],
                revision,
                expected_validation_rows,
            )
            receipts[cell] = record
            total_rows += cast(int, record["rows"])
        _require(total_rows == 36045, "prediction row total differs")
        runtime_seconds = time.perf_counter() - start
        manifest = {
            "schema_version": "cypshift.maplight_stage_a_predictions.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "contracts": {
                "stage_a": CONTRACT_SHA256,
                "nan_compatibility": NAN_CONTRACT_SHA256,
            },
            "inputs": {
                "feature_manifest": FEATURE_MANIFEST_SHA256,
                "feature_repeat_manifest": FEATURE_REPEAT_MANIFEST_SHA256,
                "target_manifest": TARGET_MANIFEST_SHA256,
                "shadow_rows": SHADOW_ROWS_SHA256,
            },
            "cells": receipts,
            "accounting": {
                "cells": 18,
                "training_target_values_parsed": 144183,
                "validation_target_values_parsed": 0,
                "model_fits": 162,
                "model_prediction_vectors": 162,
                "model_prediction_rows": 324405,
                "derived_prediction_vectors": 18,
                "derived_prediction_rows": 36045,
                "metric_evaluations": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
                "gin_weight_bytes_downloaded": 0,
                "challenge_assumptions_added": 0,
            },
            "runtime_seconds": runtime_seconds,
            "peak_rss_gib": _peak_rss_gib(),
            "claim_boundary": "Label-free validation predictions only; no validation/public-test label or metric access.",
        }
        _require(runtime_seconds <= 28800, "model runtime cap exceeded")
        (staging / "prediction_manifest.json").write_bytes(_json_bytes(manifest))
        _require(_verify_inputs()[0] == revision, "inputs changed during predictions")
        _readonly(staging)
        staging.rename(OUTPUT_ROOT)
        return OUTPUT_ROOT
    except Exception as error:
        current_target_rows = 0
        current_completed_fits = 0
        if staging is not None and current_cell is not None:
            progress = staging / "cells" / current_cell / "worker_progress.json"
            if progress.is_file():
                record = _json(progress)
                current_target_rows = int(record["training_targets_parsed"])
                current_completed_fits = int(record["completed_fits"])
        if staging is not None:
            _remove(staging)
        blocker = _write_failure(
            error,
            revision,
            completed_cells,
            current_cell,
            current_target_rows,
            current_completed_fits,
            time.perf_counter() - start,
        )
        raise StageAModelError(
            f"predictions failed; blocker retained at {blocker}"
        ) from error
    finally:
        if scratch is not None:
            _remove(scratch)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--_cell", help=argparse.SUPPRESS)
    parser.add_argument("--_target", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_target-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--_output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        if arguments._cell:
            _require(
                arguments._target and arguments._target_sha256 and arguments._output,
                "worker arguments differ",
            )
            return _worker(
                arguments._cell,
                arguments._target,
                arguments._target_sha256,
                arguments._output,
            )
        output = run_predictions()
    except (StageAModelError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
