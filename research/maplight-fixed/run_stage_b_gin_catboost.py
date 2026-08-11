"""Run the four new frozen Stage B GIN shadow controls without scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
CONTRACT_PATH = ROOT / "benchmarks/maplight_gin_stage_b_contract.json"
FIXED_ROOT = (
    ROOT / "artifacts/benchmarks/maplight-fixed-upstream-int8-nan-features-v1-build-1"
)
FIXED_REPEAT_ROOT = (
    ROOT / "artifacts/benchmarks/maplight-fixed-upstream-int8-nan-features-v1-build-2"
)
GIN_ROOT = ROOT / "artifacts/benchmarks/maplight-gin-features-v3-build-1"
GIN_REPEAT_ROOT = ROOT / "artifacts/benchmarks/maplight-gin-features-v3-build-2"
TARGET_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-targets-v1"
TARGET_MANIFEST_PATH = TARGET_ROOT / "target_manifest.json"
SHADOW_ROWS_PATH = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1/shadow_rows.csv"
STAGE_A_PREDICTION_ROOT = (
    ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-predictions-v1"
)
STAGE_A_PREDICTION_MANIFEST_PATH = STAGE_A_PREDICTION_ROOT / "prediction_manifest.json"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-gin-stage-b-predictions-v1"
BLOCKER_ROOT = ROOT / "artifacts/blockers/maplight-gin-stage-b-predictions-v1-blocker"

CONTRACT_SHA256 = "8d5c6f95e700760cdb31cb7b293c24da779adefa28a6f72e9cffdce5571bb906"
FIXED_MANIFEST_SHA256 = (
    "5a3b038e26f790e5bcd164c11c810cbc4d7ce12f9369cd92b8bb503cfeb7f32c"
)
FIXED_REPEAT_MANIFEST_SHA256 = (
    "0afd641c5802e6f3b40e3808c4a99fc546a9de1e5ce2595e68a22f6d9cbe6300"
)
GIN_MANIFEST_SHA256 = "7053c623369b4ee0f0215720033378df9214e428eab1ce0040b6cedb406f2fa3"
GIN_REPEAT_MANIFEST_SHA256 = (
    "cf6badc48fbe527074ac17c09e02ef8788fb63bd16757a84a53f2078f9157a18"
)
TARGET_MANIFEST_SHA256 = (
    "716ffd20d169b305e5014e368b222cf15b347f48ff216ef9cfebfafc0791705a"
)
STAGE_A_PREDICTION_MANIFEST_SHA256 = (
    "f7c4f711f22ce53a8b3ce7889a2104d4f9b59715afef825aff2f32cc87499182"
)
SHADOW_ROWS_SHA256 = "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
RESEARCH_PROJECT_SHA256 = (
    "20addcbfa3d7dbfa5d3a9f24f3090c22f11b556166213b2649c6c55e58556234"
)
RESEARCH_LOCK_SHA256 = (
    "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
)
RESEARCH_PYTHON_SHA256 = (
    "3817f125779f46c574b17c4adbdd0975ef8c32ae92509fed295212797d314d6a"
)

FIXED_BLOCKS = ("morgan_count", "avalon_count", "erg", "rdkit_descriptors")
FIXED_WIDTHS = (1024, 1024, 315, 200)
GIN_WIDTH = 300
SHUFFLE_SEED = 20260816
NOISE_SEED = 20260817
CONFIGURATIONS = (
    ("b1_gin_alone_catboost_seed_1", "gin", 1),
    *(
        (f"b2_maplight_fixed_plus_gin_catboost_seed_{seed}", "combined", seed)
        for seed in range(1, 6)
    ),
    ("b3_maplight_fixed_plus_shuffled_gin_catboost_seed_1", "shuffled", 1),
    ("b4_maplight_fixed_plus_noise_catboost_seed_1", "noise", 1),
)
MEAN_CONFIGURATION = "b2_maplight_fixed_plus_gin_catboost_mean_probability"
PREDICTION_COLUMNS = (
    "task",
    "protocol",
    "repeat",
    "molecule_id",
    "source_row",
    *(item[0] for item in CONFIGURATIONS),
    MEAN_CONFIGURATION,
)


class StageBModelError(RuntimeError):
    """Fail-closed Stage B prediction error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StageBModelError(message)


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(reader.fieldnames is not None, f"CSV header differs: {path}")
        return [{key: str(value) for key, value in row.items()} for row in reader]


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


def _make_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _remove(root: Path) -> None:
    if root.exists():
        for path in root.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        root.chmod(0o755)
        shutil.rmtree(root)


def _verify_environment() -> dict[str, str]:
    _require(sys.version_info[:3] == (3, 10, 13), "Python version differs")
    _require(platform.system() == "Darwin", "platform differs")
    _require(platform.machine() == "arm64", "architecture differs")
    versions = {
        "catboost": importlib.metadata.version("catboost"),
        "numpy": importlib.metadata.version("numpy"),
    }
    _require(
        versions == {"catboost": "1.2.1", "numpy": "1.25.2"}, "package versions differ"
    )
    for path, expected in (
        (ROOT / "research/maplight-fixed/pyproject.toml", RESEARCH_PROJECT_SHA256),
        (ROOT / "research/maplight-fixed/uv.lock", RESEARCH_LOCK_SHA256),
        (ROOT / "research/maplight-fixed/.python-version", RESEARCH_PYTHON_SHA256),
    ):
        _require(_sha256(path) == expected, f"environment input differs: {path}")
    return {"python": platform.python_version(), **versions}


def _require_hash(path: Path, expected: str) -> None:
    _require(
        path.is_file() and _sha256(path) == expected, f"input hash differs: {path}"
    )


def _verify_inputs() -> tuple[str, dict[str, Any], dict[str, Any]]:
    revision = _clean_revision()
    _verify_environment()
    fixed_manifest = FIXED_ROOT / "feature_manifest.json"
    fixed_repeat_manifest = FIXED_REPEAT_ROOT / "feature_manifest.json"
    gin_manifest = GIN_ROOT / "gin_manifest.json"
    gin_repeat_manifest = GIN_REPEAT_ROOT / "gin_manifest.json"
    for path, expected in (
        (CONTRACT_PATH, CONTRACT_SHA256),
        (fixed_manifest, FIXED_MANIFEST_SHA256),
        (fixed_repeat_manifest, FIXED_REPEAT_MANIFEST_SHA256),
        (gin_manifest, GIN_MANIFEST_SHA256),
        (gin_repeat_manifest, GIN_REPEAT_MANIFEST_SHA256),
        (TARGET_MANIFEST_PATH, TARGET_MANIFEST_SHA256),
        (STAGE_A_PREDICTION_MANIFEST_PATH, STAGE_A_PREDICTION_MANIFEST_SHA256),
        (SHADOW_ROWS_PATH, SHADOW_ROWS_SHA256),
    ):
        _require_hash(path, expected)
    for root in (
        FIXED_ROOT,
        FIXED_REPEAT_ROOT,
        GIN_ROOT,
        GIN_REPEAT_ROOT,
        TARGET_ROOT,
        STAGE_A_PREDICTION_ROOT,
    ):
        _require(_readonly_root(root), f"input root is writable: {root}")
    fixed_files = (
        "feature_rows.csv",
        *(f"{name}.npy" for name in ("binary_morgan", *FIXED_BLOCKS)),
    )
    for name in fixed_files:
        _require(
            _sha256(FIXED_ROOT / name) == _sha256(FIXED_REPEAT_ROOT / name),
            f"fixed feature repeat differs: {name}",
        )
    for name in ("feature_rows.csv", "gin.npy"):
        _require(
            _sha256(GIN_ROOT / name) == _sha256(GIN_REPEAT_ROOT / name),
            f"GIN feature repeat differs: {name}",
        )
    _require(
        _sha256(FIXED_ROOT / "feature_rows.csv")
        == _sha256(GIN_ROOT / "feature_rows.csv"),
        "fixed and GIN row alignment differs",
    )
    target = _json(TARGET_MANIFEST_PATH)
    _require(len(target["cells"]) == 18, "target cell count differs")
    _require(
        target["accounting"]["public_test_labels_parsed"] == 0,
        "target public boundary differs",
    )
    stage_a = _json(STAGE_A_PREDICTION_MANIFEST_PATH)
    _require(len(stage_a["cells"]) == 18, "Stage A prediction cell count differs")
    _require(
        stage_a["accounting"]["validation_target_values_parsed"] == 0
        and stage_a["accounting"]["metric_evaluations"] == 0,
        "Stage A prediction chronology differs",
    )
    return revision, target, stage_a


def _load_array(
    path: Path, shape: tuple[int, int], dtype: np.dtype[Any]
) -> np.ndarray[Any, Any]:
    read_magic = cast(Callable[[Any], tuple[int, int]], np.lib.format.read_magic)
    with path.open("rb") as handle:
        _require(read_magic(handle) == (1, 0), f"NPY version differs: {path}")
    array = np.load(path, allow_pickle=False, mmap_mode="r")
    _require(
        array.shape == shape and array.dtype == dtype, f"array contract differs: {path}"
    )
    _require(array.flags.c_contiguous, f"array order differs: {path}")
    return cast(np.ndarray[Any, Any], array)


def _make_controls(
    gin: np.ndarray[Any, Any], raw_hashes: Sequence[str]
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    unique_hashes = sorted(set(raw_hashes))
    indices_by_hash: dict[str, list[int]] = {key: [] for key in unique_hashes}
    for index, key in enumerate(raw_hashes):
        indices_by_hash[key].append(index)
    representative_indices = np.asarray(
        [indices_by_hash[key][0] for key in unique_hashes], dtype=np.int64
    )
    for key in unique_hashes:
        indices = indices_by_hash[key]
        _require(
            all(np.array_equal(gin[indices[0]], gin[index]) for index in indices[1:]),
            "exact-raw GIN repeat differs",
        )
    code_by_hash = {key: index for index, key in enumerate(unique_hashes)}
    row_codes = np.fromiter((code_by_hash[key] for key in raw_hashes), dtype=np.int64)
    unique_gin = np.asarray(gin[representative_indices], dtype=np.float64)
    permutation = np.random.default_rng(SHUFFLE_SEED).permutation(len(unique_hashes))
    shuffled = np.ascontiguousarray(unique_gin[permutation][row_codes])
    unique_noise = np.random.default_rng(NOISE_SEED).standard_normal(
        (len(unique_hashes), gin.shape[1])
    )
    noise = np.ascontiguousarray(unique_noise[row_codes])
    _require(
        bool(np.isfinite(shuffled).all()) and bool(np.isfinite(noise).all()),
        "control finiteness differs",
    )
    _require(
        np.array_equal(np.sort(permutation), np.arange(len(unique_hashes))),
        "shuffle permutation differs",
    )
    return shuffled, noise


def _load_features(
    rows: Sequence[Mapping[str, str]],
) -> tuple[np.ndarray[Any, Any], ...]:
    fixed_arrays = [
        _load_array(
            FIXED_ROOT / f"{name}.npy",
            (30038, width),
            np.dtype("<f8" if name in {"erg", "rdkit_descriptors"} else "int8"),
        )
        for name, width in zip(FIXED_BLOCKS, FIXED_WIDTHS, strict=True)
    ]
    for name, array in zip(FIXED_BLOCKS[:-1], fixed_arrays[:-1], strict=True):
        _require(
            bool(np.isfinite(array).all()), f"non-finite fixed block differs: {name}"
        )
    descriptors = np.asarray(fixed_arrays[-1])
    _require(not bool(np.isinf(descriptors).any()), "descriptor infinity differs")
    nan_rows, nan_columns = np.where(np.isnan(descriptors))
    _require(len(nan_rows) == 328, "descriptor NaN count differs")
    _require(
        set(int(value) for value in nan_columns) == {39, 41, 43, 45},
        "descriptor NaN columns differ",
    )
    fixed = np.ascontiguousarray(np.concatenate(fixed_arrays, axis=1))
    _require(fixed.shape == (30038, 2563), "fixed matrix dimensions differ")
    gin = np.asarray(
        _load_array(GIN_ROOT / "gin.npy", (30038, GIN_WIDTH), np.dtype("<f8"))
    )
    _require(bool(np.isfinite(gin).all()), "GIN non-finite values differ")
    raw_hashes = [row["raw_structure_sha256"] for row in rows]
    _require(len(set(raw_hashes)) == 15399, "exact-raw population differs")
    shuffled, noise = _make_controls(gin, raw_hashes)
    return fixed, gin, shuffled, noise


def _matrix(
    kind: str,
    fixed: np.ndarray[Any, Any],
    gin: np.ndarray[Any, Any],
    shuffled: np.ndarray[Any, Any],
    noise: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    if kind == "gin":
        return gin
    suffix = {"combined": gin, "shuffled": shuffled, "noise": noise}[kind]
    return np.ascontiguousarray(np.concatenate((fixed, suffix), axis=1))


def _peak_rss_gib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)


def _worker(cell: str, target_path: Path, target_sha256: str, output: Path) -> int:
    start = time.perf_counter()
    revision, _, _ = _verify_inputs()
    _require_hash(target_path, target_sha256)
    task, protocol, repeat_text = cell.split("__")
    repeat = int(repeat_text.removeprefix("repeat_"))
    targets = _read_csv(target_path)
    _require(
        tuple(targets[0])
        == ("task", "protocol", "repeat", "molecule_id", "source_row", "target"),
        "target columns differ",
    )
    _require(
        all(
            row["task"] == task
            and row["protocol"] == protocol
            and row["repeat"] == str(repeat)
            for row in targets
        ),
        "target cell identity differs",
    )
    target_by_id = {row["molecule_id"]: int(row["target"]) for row in targets}
    _require(len(target_by_id) == len(targets), "target identities differ")
    rows = _read_csv(FIXED_ROOT / "feature_rows.csv")
    shadow = _read_csv(SHADOW_ROWS_PATH)
    _require(len(rows) == len(shadow) == 30038, "source row count differs")
    _require(
        [row["molecule_id"] for row in rows] == [row["molecule_id"] for row in shadow],
        "feature and shadow row order differs",
    )
    index_by_id = {row["molecule_id"]: index for index, row in enumerate(rows)}
    _require(len(index_by_id) == len(rows), "feature identities differ")
    train_index = np.asarray(
        [index_by_id[row["molecule_id"]] for row in targets], dtype=np.int64
    )
    validation_rows = [
        row
        for row in shadow
        if row["task"] == task and row[f"{protocol}_repeat_{repeat}_outer_fold"] == "0"
    ]
    validation_index = np.asarray(
        [index_by_id[row["molecule_id"]] for row in validation_rows], dtype=np.int64
    )
    _require(
        not set(target_by_id) & {row["molecule_id"] for row in validation_rows},
        "validation identity entered training",
    )
    y = np.asarray([target_by_id[row["molecule_id"]] for row in targets], dtype=np.int8)
    _require(set(y.tolist()) == {0, 1}, "training class support differs")
    fixed, gin, shuffled, noise = _load_features(rows)
    output.mkdir()
    progress_path = output / "worker_progress.json"
    progress_path.write_bytes(
        _json_bytes(
            {"cell": cell, "training_targets_parsed": len(targets), "completed_fits": 0}
        )
    )
    catboost = __import__("catboost")
    predictions: dict[str, np.ndarray[Any, Any]] = {}
    fits: list[dict[str, object]] = []
    for configuration, kind, seed in CONFIGURATIONS:
        matrix = _matrix(kind, fixed, gin, shuffled, noise)
        expected_width = GIN_WIDTH if kind == "gin" else 2563 + GIN_WIDTH
        _require(
            matrix.shape == (30038, expected_width), "model matrix dimensions differ"
        )
        fit_start = time.perf_counter()
        model = catboost.CatBoostClassifier(
            random_strength=2,
            random_seed=seed,
            verbose=0,
            loss_function="Logloss",
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
                "feature_kind": kind,
                "feature_count": expected_width,
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
    mean = np.mean(
        np.stack(
            [
                predictions[f"b2_maplight_fixed_plus_gin_catboost_seed_{seed}"]
                for seed in range(1, 6)
            ]
        ),
        axis=0,
        dtype=np.float64,
    )
    prediction_path = output / "predictions.csv"
    with prediction_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PREDICTION_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for index, row in enumerate(validation_rows):
            record: dict[str, object] = {
                "task": task,
                "protocol": protocol,
                "repeat": repeat,
                "molecule_id": row["molecule_id"],
                "source_row": row["source_row"],
            }
            record.update(
                {
                    name: repr(float(values[index]))
                    for name, values in predictions.items()
                }
            )
            record[MEAN_CONFIGURATION] = repr(float(mean[index]))
            writer.writerow(record)
    runtime_seconds = time.perf_counter() - start
    peak_rss_gib = _peak_rss_gib()
    receipt = {
        "schema_version": "cypshift.maplight_gin_stage_b_cell_predictions.v1",
        "source_revision": revision,
        "cell": cell,
        "task": task,
        "protocol": protocol,
        "repeat": repeat,
        "target_sha256": target_sha256,
        "prediction_path": "predictions.csv",
        "prediction_sha256": _sha256(prediction_path),
        "rows": len(validation_rows),
        "fits": fits,
        "controls": {
            "shuffle_seed": SHUFFLE_SEED,
            "noise_seed": NOISE_SEED,
            "shuffled_element_sha256": hashlib.sha256(shuffled.tobytes()).hexdigest(),
            "noise_element_sha256": hashlib.sha256(noise.tobytes()).hexdigest(),
        },
        "runtime_seconds": runtime_seconds,
        "peak_rss_gib": peak_rss_gib,
        "accounting": {
            "training_target_values_parsed": len(targets),
            "validation_target_values_parsed": 0,
            "model_fits": 8,
            "model_prediction_vectors": 8,
            "derived_prediction_vectors": 1,
            "metric_evaluations": 0,
            "public_test_rows_used": 0,
            "public_test_labels_parsed": 0,
            "challenge_assumptions_added": 0,
        },
        "claim_boundary": "Stage B shadow predictions only; no validation/public-test label or metric access.",
    }
    progress_path.unlink()
    (output / "cell_receipt.json").write_bytes(_json_bytes(receipt))
    _require(
        runtime_seconds <= 28800 and peak_rss_gib <= 12, "cell resource cap exceeded"
    )
    _make_readonly(output)
    return 0


def _validate_cell(
    root: Path,
    cell: str,
    target: Mapping[str, Any],
    revision: str,
    validation_rows: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    _require(_readonly_root(root), "cell root is writable")
    _require(
        {path.name for path in root.iterdir()}
        == {"cell_receipt.json", "predictions.csv"},
        "cell files differ",
    )
    _require(
        all(_readonly_file(path) for path in root.iterdir()), "cell file is writable"
    )
    receipt = _json(root / "cell_receipt.json")
    _require(
        receipt["schema_version"] == "cypshift.maplight_gin_stage_b_cell_predictions.v1"
        and receipt["source_revision"] == revision
        and receipt["cell"] == cell
        and receipt["target_sha256"] == target["sha256"],
        "cell receipt identity differs",
    )
    task, protocol, repeat_text = cell.split("__")
    repeat = int(repeat_text.removeprefix("repeat_"))
    _require(
        receipt["task"] == task
        and receipt["protocol"] == protocol
        and receipt["repeat"] == repeat,
        "cell receipt fields differ",
    )
    prediction_path = root / "predictions.csv"
    _require(
        receipt["prediction_path"] == "predictions.csv"
        and receipt["prediction_sha256"] == _sha256(prediction_path),
        "cell prediction hash differs",
    )
    rows = _read_csv(prediction_path)
    _require(
        len(rows) == receipt["rows"] == len(validation_rows), "cell row count differs"
    )
    _require(tuple(rows[0]) == PREDICTION_COLUMNS, "prediction columns differ")
    _require(
        [(row["molecule_id"], row["source_row"]) for row in rows]
        == [(row["molecule_id"], row["source_row"]) for row in validation_rows],
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
    for configuration in (*[item[0] for item in CONFIGURATIONS], MEAN_CONFIGURATION):
        vector = np.asarray(
            [float(row[configuration]) for row in rows], dtype=np.float64
        )
        _require(
            bool(np.isfinite(vector).all())
            and bool(((vector >= 0) & (vector <= 1)).all()),
            "retained prediction differs",
        )
        values[configuration] = vector
    expected_mean = np.mean(
        np.stack(
            [
                values[f"b2_maplight_fixed_plus_gin_catboost_seed_{seed}"]
                for seed in range(1, 6)
            ]
        ),
        axis=0,
        dtype=np.float64,
    )
    _require(
        np.array_equal(values[MEAN_CONFIGURATION], expected_mean),
        "mean prediction differs",
    )
    fits = receipt["fits"]
    _require(isinstance(fits, list) and len(fits) == 8, "cell fit count differs")
    for fit, (configuration, kind, seed) in zip(fits, CONFIGURATIONS, strict=True):
        _require(isinstance(fit, dict), "fit receipt differs")
        resolved = fit["resolved_parameters"]
        _require(isinstance(resolved, dict), "resolved parameters differ")
        _require(
            fit["configuration_id"] == configuration
            and fit["feature_kind"] == kind
            and fit["feature_count"] == (GIN_WIDTH if kind == "gin" else 2863)
            and fit["seed"] == seed
            and fit["train_rows"] == target["rows"]
            and fit["validation_rows"] == len(rows)
            and fit["class_order"] == [0, 1]
            and fit["prediction_element_sha256"]
            == hashlib.sha256(values[configuration].tobytes()).hexdigest()
            and resolved["random_seed"] == seed
            and resolved["random_strength"] == 2
            and resolved["loss_function"] == "Logloss"
            and resolved["nan_mode"] == "Min",
            "fit receipt differs",
        )
    controls = receipt["controls"]
    _require(
        isinstance(controls, dict)
        and controls["shuffle_seed"] == SHUFFLE_SEED
        and controls["noise_seed"] == NOISE_SEED
        and len(str(controls["shuffled_element_sha256"])) == 64
        and len(str(controls["noise_element_sha256"])) == 64,
        "control receipt differs",
    )
    _require(
        receipt["accounting"]
        == {
            "training_target_values_parsed": target["rows"],
            "validation_target_values_parsed": 0,
            "model_fits": 8,
            "model_prediction_vectors": 8,
            "derived_prediction_vectors": 1,
            "metric_evaluations": 0,
            "public_test_rows_used": 0,
            "public_test_labels_parsed": 0,
            "challenge_assumptions_added": 0,
        },
        "cell accounting differs",
    )
    _require(
        0 <= float(receipt["runtime_seconds"]) <= 28800
        and 0 <= float(receipt["peak_rss_gib"]) <= 12,
        "cell resource receipt differs",
    )
    _require(
        receipt["claim_boundary"]
        == "Stage B shadow predictions only; no validation/public-test label or metric access.",
        "cell claim boundary differs",
    )
    return {
        "receipt_sha256": _sha256(root / "cell_receipt.json"),
        "prediction_sha256": receipt["prediction_sha256"],
        "rows": len(rows),
        "shuffled_element_sha256": controls["shuffled_element_sha256"],
        "noise_element_sha256": controls["noise_element_sha256"],
    }


def _write_failure(
    error: Exception,
    revision: str | None,
    completed_cells: Sequence[str],
    current_cell: str | None,
    target_rows: int,
    completed_fits: int,
    elapsed: float,
) -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not BLOCKER_ROOT.exists(),
        "prediction output exists",
    )
    staging = Path(
        tempfile.mkdtemp(prefix=".stage-b-prediction-blocker-", dir=BLOCKER_ROOT.parent)
    )
    target = _json(TARGET_MANIFEST_PATH)
    total_fits = len(completed_cells) * 8 + completed_fits
    receipt = {
        "schema_version": "cypshift.maplight_gin_stage_b_prediction_failure.v1",
        "source_revision": revision,
        "implementation_sha256": _sha256(SCRIPT_PATH),
        "contract_sha256": CONTRACT_SHA256,
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
            + target_rows,
            "validation_target_values_parsed": 0,
            "model_fits_completed": total_fits,
            "model_prediction_vectors_completed": total_fits,
            "metric_evaluations": 0,
            "public_test_rows_used": 0,
            "public_test_labels_parsed": 0,
            "challenge_assumptions_added": 0,
        },
        "claim_boundary": "Stage B prediction failure; no validation/public-test label or metric access.",
    }
    (staging / "failure_receipt.json").write_bytes(_json_bytes(receipt))
    _make_readonly(staging)
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
        revision, target, _ = _verify_inputs()
        staging = Path(
            tempfile.mkdtemp(prefix=".stage-b-predictions-", dir=OUTPUT_ROOT.parent)
        )
        scratch = Path(tempfile.mkdtemp(prefix="cypshift-stage-b-models-", dir="/tmp"))
        cells_root = staging / "cells"
        cells_root.mkdir()
        for cell, record in sorted(target["cells"].items()):
            current_cell = cell
            cell_scratch = scratch / cell
            cell_scratch.mkdir()
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--_cell",
                    cell,
                    "--_target",
                    str(TARGET_ROOT / record["path"]),
                    "--_target-sha256",
                    record["sha256"],
                    "--_output",
                    str(cells_root / cell),
                ],
                cwd=cell_scratch,
                check=True,
                timeout=28800,
            )
            completed_cells.append(cell)
            current_cell = None
        shadow = _read_csv(SHADOW_ROWS_PATH)
        receipts: dict[str, object] = {}
        total_rows = 0
        shuffled_hashes: set[str] = set()
        noise_hashes: set[str] = set()
        for cell, record in sorted(target["cells"].items()):
            task, protocol, repeat_text = cell.split("__")
            repeat = int(repeat_text.removeprefix("repeat_"))
            validation_rows = [
                row
                for row in shadow
                if row["task"] == task
                and row[f"{protocol}_repeat_{repeat}_outer_fold"] == "0"
            ]
            bound = _validate_cell(
                cells_root / cell, cell, record, revision, validation_rows
            )
            receipts[cell] = bound
            total_rows += cast(int, bound["rows"])
            shuffled_hashes.add(str(bound["shuffled_element_sha256"]))
            noise_hashes.add(str(bound["noise_element_sha256"]))
        _require(total_rows == 36045, "prediction row total differs")
        _require(
            len(shuffled_hashes) == len(noise_hashes) == 1,
            "control matrix repeat differs across cells",
        )
        runtime_seconds = time.perf_counter() - start
        manifest = {
            "schema_version": "cypshift.maplight_gin_stage_b_predictions.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "contract_sha256": CONTRACT_SHA256,
            "inputs": {
                "fixed_feature_manifest": FIXED_MANIFEST_SHA256,
                "fixed_feature_repeat_manifest": FIXED_REPEAT_MANIFEST_SHA256,
                "gin_feature_manifest": GIN_MANIFEST_SHA256,
                "gin_feature_repeat_manifest": GIN_REPEAT_MANIFEST_SHA256,
                "target_manifest": TARGET_MANIFEST_SHA256,
                "stage_a_prediction_manifest": STAGE_A_PREDICTION_MANIFEST_SHA256,
                "shadow_rows": SHADOW_ROWS_SHA256,
            },
            "controls": {
                "shuffle_seed": SHUFFLE_SEED,
                "noise_seed": NOISE_SEED,
                "shuffled_element_sha256": next(iter(shuffled_hashes)),
                "noise_element_sha256": next(iter(noise_hashes)),
            },
            "cells": receipts,
            "runtime_seconds": runtime_seconds,
            "peak_rss_gib": _peak_rss_gib(),
            "accounting": {
                "cells": 18,
                "training_target_values_parsed": 144183,
                "validation_target_values_parsed": 0,
                "model_fits": 144,
                "model_prediction_vectors": 144,
                "model_prediction_rows": 288360,
                "derived_prediction_vectors": 18,
                "derived_prediction_rows": 36045,
                "retained_probability_values": 324405,
                "metric_evaluations": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
                "public_test_family_task_slots_consumed": 0,
                "challenge_assumptions_added": 0,
            },
            "claim_boundary": "Immutable Stage B shadow predictions only; no validation/public-test label or metric access.",
        }
        _require(runtime_seconds <= 144000, "prediction runtime cap exceeded")
        (staging / "prediction_manifest.json").write_bytes(_json_bytes(manifest))
        _require(_verify_inputs()[0] == revision, "inputs changed during predictions")
        _make_readonly(staging)
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
        raise StageBModelError(
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
                arguments._target is not None
                and arguments._target_sha256 is not None
                and arguments._output is not None,
                "worker arguments differ",
            )
            return _worker(
                arguments._cell,
                arguments._target,
                arguments._target_sha256,
                arguments._output,
            )
        output = run_predictions()
    except (StageBModelError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
