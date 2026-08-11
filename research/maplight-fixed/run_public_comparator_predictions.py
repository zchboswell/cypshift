"""Freeze the two authorized label-free MapLight public prediction families.

This is a direct Phase 0.75 executor, not a reusable benchmark framework.  It
first strips the already frozen TDC public identities into a label-absent input,
then builds exact fixed and GIN features and fits the predeclared five CatBoost
seeds for both comparator families.  It never opens a public-test measurement
or scoring file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
FIXED_DIR = SCRIPT_PATH.parent
GIN_DIR = ROOT / "research/maplight-gin"

SOURCE_ROOT = ROOT / "artifacts/benchmarks/native-prediction-inputs-v1"
SOURCE_MANIFEST = SOURCE_ROOT / "prediction_input_manifest.json"
SOURCE_MOLECULES = SOURCE_ROOT / "tdc/molecules.csv"
SOURCE_SPLIT = SOURCE_ROOT / "tdc/official_split.csv"
SOURCE_HASHES = {
    "prediction_input_manifest.json": "9e5350490dfc4674b96960644e3e49c4887ec37d3fbb62de22d47dc6481444a1",
    "tdc/molecules.csv": "14382a9171a8b096bd8c271e949f0f2ddaf259312e3f315d4d5920c5a2b69981",
    "tdc/official_split.csv": "69ae4d7afd01e5b665e4c476731adc792e402b0fd39a20fe4e17d67aca2083e9",
}

INPUT_ROOTS = {
    3: ROOT / "artifacts/benchmarks/maplight-public-input-v1-attempt-3",
    4: ROOT / "artifacts/benchmarks/maplight-public-input-v1-attempt-4",
}
INPUT_BLOCKERS = {
    attempt: ROOT
    / f"artifacts/blockers/maplight-public-input-v1-attempt-{attempt}-blocker"
    for attempt in (3, 4)
}
PRESERVED_INPUT_BLOCKERS = {
    1: {
        "path": ROOT
        / "artifacts/blockers/maplight-public-input-v1-attempt-1-blocker/failure_receipt.json",
        "sha256": "7bcdbb5ebf331bf2340a6a4d288e24252f48e5ffcfc22a58610fac1116f0d1af",
    },
    2: {
        "path": ROOT
        / "artifacts/blockers/maplight-public-input-v1-attempt-2-blocker/failure_receipt.json",
        "sha256": "f592048b39d3cd04e9f80846cb9bb59e178bc2cd35bb0ee920bd961dd00dbef8",
    },
}
PREDICTION_ROOTS = {
    1: ROOT / "artifacts/benchmarks/maplight-public-predictions-v1-attempt-1",
    2: ROOT / "artifacts/benchmarks/maplight-public-predictions-v1-attempt-2",
}
PREDICTION_BLOCKERS = {
    attempt: ROOT
    / f"artifacts/blockers/maplight-public-predictions-v1-attempt-{attempt}-blocker"
    for attempt in (1, 2)
}

TRAIN_TARGETS = (
    ROOT
    / "artifacts/benchmarks/maplight-fixed-stage-a-targets-v1/scoring/scoring_targets.csv"
)
TRAIN_TARGETS_SHA256 = (
    "73a4ee1556fdeac293ebd4bcfa43145f29c9ffff2cd3d9640a40c84ee037d3c2"
)
EVALUATION_BUDGET = ROOT / "benchmarks/phase_0_75_evaluation_budget.json"
EVALUATION_BUDGET_SHA256 = (
    "fa5463b7fcc5aabecf786f42757f60ba6509aa3ce144c6a2ab4a8c1883408750"
)
GIN_BUILDER = GIN_DIR / "build_gin_embeddings.py"
GIN_BUILDER_SHA256 = "40da336a05057b65047b1d6a457e1ffed0b76e8b4606bf6638f584de01008e4e"
GIN_PYTHON = GIN_DIR / ".venv/bin/python"
GIN_WEIGHT_ROOT = ROOT / "artifacts/benchmarks/maplight-gin-weight-v1"

TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
TASK_ROWS = {"cyp2c9_veith": 2419, "cyp2d6_veith": 2626, "cyp3a4_veith": 2467}
TOTAL_ROWS = 7512
SEEDS = (1, 2, 3, 4, 5)
FIXED_BLOCKS = ("morgan_count", "avalon_count", "erg", "rdkit_descriptors")
FIXED_WIDTHS = (1024, 1024, 315, 200)
PUBLIC_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure",
    "standardized_structure_sha256",
    "standardization_version",
)
PREDICTION_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure_sha256",
    "standardized_structure_sha256",
    *(f"prediction_seed_{seed}" for seed in SEEDS),
    "prediction_probability_mean",
)
MOLECULE_COLUMNS = (
    "molecule_id",
    "raw_structure",
    "structure_format",
    "standardized_structure",
    "standardized_structure_hash",
    "status",
    "stereochemistry_status",
    "input_fragments",
    "standardization_changed",
    "duplicate_of",
    "warnings",
    "standardization_version",
    "source",
    "provenance",
)
SPLIT_COLUMNS = ("molecule_id", "task", "partition", "source_row")
CLAIM = (
    "Two jointly frozen label-free TDC public prediction families; no public-test "
    "label, metric, public-test-informed repair, third contender, or challenge claim."
)


class PublicPredictionError(RuntimeError):
    """Raised when the public prediction freeze violates an exact boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicPredictionError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _element_sha256(array: np.ndarray[Any, Any]) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(cast(Any, spec))
    sys.modules[name] = module
    cast(Any, spec.loader).exec_module(module)
    return module


def _stage_b() -> ModuleType:
    return _module("cypshift_stage_b_public", FIXED_DIR / "run_stage_b_gin_catboost.py")


def _features() -> ModuleType:
    return _module("cypshift_features_public", FIXED_DIR / "maplight_fixed_features.py")


def _clean_revision() -> str:
    stage_b = _stage_b()
    revision = cast(str, stage_b._clean_revision())
    relative = SCRIPT_PATH.relative_to(ROOT).as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        tracked.returncode == 0 and tracked.stdout.strip() == relative,
        "runner untracked",
    )
    return revision


def _readonly_file(path: Path) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and not bool(path.stat().st_mode & 0o222)
    )


def _readonly_root(path: Path) -> bool:
    return (
        path.is_dir()
        and not path.is_symlink()
        and not bool(path.stat().st_mode & 0o222)
    )


def _make_readonly(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        elif path.is_dir():
            path.chmod(
                stat.S_IRUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            )
    root.chmod(
        stat.S_IRUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IXGRP
        | stat.S_IROTH
        | stat.S_IXOTH
    )


def _peak_rss_gib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)


def _write_failure(
    root: Path,
    operation: str,
    attempt: int,
    error: Exception,
    accounting: dict[str, int],
    source_revision: str | None,
) -> None:
    if root.exists():
        return
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
    receipt = {
        "schema_version": "cypshift.maplight_public_prediction_failure.v1",
        "operation": operation,
        "attempt": attempt,
        "source_revision": source_revision,
        "implementation_sha256": _sha256(SCRIPT_PATH),
        "bindings": {
            "evaluation_budget_sha256": (
                _sha256(EVALUATION_BUDGET) if EVALUATION_BUDGET.is_file() else None
            ),
            "trusted_source_sha256": SOURCE_HASHES,
            "public_input_rows_sha256": (
                _sha256(INPUT_ROOTS[3] / "public_rows.csv")
                if (INPUT_ROOTS[3] / "public_rows.csv").is_file()
                else None
            ),
            "train_val_targets_sha256": (
                _sha256(TRAIN_TARGETS) if TRAIN_TARGETS.is_file() else None
            ),
        },
        "failure": {"kind": type(error).__name__, "message": str(error)[:400]},
        "accounting": accounting,
        "claim_boundary": CLAIM,
    }
    (staging / "failure_receipt.json").write_bytes(_json_bytes(receipt))
    staging.rename(root)
    _make_readonly(root)


def _source_rows() -> list[dict[str, str]]:
    for relative, expected in SOURCE_HASHES.items():
        path = SOURCE_ROOT / relative
        _require(_sha256(path) == expected, f"source hash differs: {relative}")
        _require(_readonly_file(path), f"source input is writable: {relative}")
    with SOURCE_SPLIT.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _require(tuple(next(reader)) == SPLIT_COLUMNS, "split columns differ")
        split_rows = list(reader)
    _require(
        len(split_rows) == 37550 and all(len(row) == 4 for row in split_rows),
        "split population differs",
    )
    split_by_id = {row[0]: row for row in split_rows}
    _require(len(split_by_id) == len(split_rows), "split identities differ")
    with SOURCE_MOLECULES.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _require(tuple(next(reader)) == MOLECULE_COLUMNS, "molecule columns differ")
        # The parser tokenizes every CSV field, but only these whitelisted positions
        # are accessed.  In particular, provenance/source_label_raw is never read.
        molecules = [
            (row[0], row[1], row[2], row[3], row[4], row[5], row[11]) for row in reader
        ]
    _require(len(molecules) == 37550, "molecule population differs")
    molecule_by_id = {row[0]: row for row in molecules}
    _require(
        len(molecule_by_id) == len(molecules)
        and set(molecule_by_id) == set(split_by_id),
        "source join differs",
    )
    output: list[dict[str, str]] = []
    for molecule_id, split in split_by_id.items():
        if split[2] != "test":
            continue
        molecule = molecule_by_id[molecule_id]
        _require(
            molecule[2] == "smiles"
            and molecule[5] == "accepted"
            and molecule[6] == "rdkit-cleanup-fragment-parent-v1",
            "public molecule contract differs",
        )
        raw = molecule[1]
        standardized = molecule[3]
        standardized_hash = molecule[4]
        _require(
            hashlib.sha256(standardized.encode()).hexdigest() == standardized_hash,
            "standardized hash differs",
        )
        output.append(
            {
                "task": split[1],
                "molecule_id": molecule_id,
                "source_row": str(int(split[3])),
                "raw_structure": raw,
                "raw_structure_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "standardized_structure": standardized,
                "standardized_structure_sha256": standardized_hash,
                "standardization_version": molecule[6],
            }
        )
    output.sort(
        key=lambda row: (row["task"], int(row["source_row"]), row["molecule_id"])
    )
    _require(
        len(output) == TOTAL_ROWS
        and len({row["molecule_id"] for row in output}) == TOTAL_ROWS,
        "public rows differ",
    )
    _require(
        {task: sum(row["task"] == task for row in output) for task in TASKS}
        == TASK_ROWS,
        "task rows differ",
    )
    return output


def prepare_public_input(attempt: int) -> Path:
    _require(attempt in (3, 4), "input attempt differs")
    output = INPUT_ROOTS[attempt]
    blocker = INPUT_BLOCKERS[attempt]
    _require(
        not output.exists() and not blocker.exists(), "input attempt already exists"
    )
    accounting = {
        "public_rows_emitted": 0,
        "provenance_values_interpreted": 0,
        "public_test_labels_parsed": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
    }
    staging: Path | None = None
    revision: str | None = None
    try:
        revision = _clean_revision()
        for record in PRESERVED_INPUT_BLOCKERS.values():
            path = cast(Path, record["path"])
            _require(
                _readonly_file(path) and _sha256(path) == record["sha256"],
                "preserved input blocker differs",
            )
        rows = _source_rows()
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
        row_path = staging / "public_rows.csv"
        with row_path.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=PUBLIC_COLUMNS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        accounting["public_rows_emitted"] = len(rows)
        manifest = {
            "schema_version": "cypshift.maplight_public_input.v1",
            "attempt": attempt,
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "inputs": SOURCE_HASHES,
            "rows": {
                "path": "public_rows.csv",
                "sha256": _sha256(row_path),
                "count": TOTAL_ROWS,
                "task_rows": TASK_ROWS,
                "columns": list(PUBLIC_COLUMNS),
            },
            "accounting": accounting,
            "claim_boundary": "Label-absent TDC public identity projection; no public-test label or metric access.",
        }
        (staging / "input_manifest.json").write_bytes(_json_bytes(manifest))
        if attempt == 4:
            prior = INPUT_ROOTS[3]
            _require(_readonly_root(prior), "input attempt 1 is not immutable")
            for name in ("public_rows.csv", "input_manifest.json"):
                if name == "input_manifest.json":
                    first = _read_json(prior / name)
                    second = _read_json(staging / name)
                    first["attempt"] = second["attempt"]
                    _require(first == second, "input repeat manifest differs")
                else:
                    _require(
                        (prior / name).read_bytes() == (staging / name).read_bytes(),
                        "input repeat rows differ",
                    )
        _require(
            _clean_revision() == revision, "source changed during input preparation"
        )
        _make_readonly(staging)
        staging.rename(output)
        return output
    except Exception as error:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        _write_failure(blocker, "prepare", attempt, error, accounting, revision)
        raise


def _array_record(path: Path, array: np.ndarray[Any, Any]) -> dict[str, object]:
    with path.open("rb") as handle:
        _require(np.lib.format.read_magic(handle) == (1, 0), "NPY version differs")
    loaded = np.load(path, allow_pickle=False, mmap_mode="r")
    _require(
        loaded.shape == array.shape
        and loaded.dtype == array.dtype
        and loaded.flags.c_contiguous,
        "persisted array differs",
    )
    return {
        "path": path.name,
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "element_sha256": _element_sha256(array),
        "npy_sha256": _sha256(path),
        "nonfinite_count": int(np.size(array) - np.isfinite(array).sum()),
    }


def _write_npy(path: Path, array: np.ndarray[Any, Any]) -> None:
    features = _features()
    features.write_npy_v1(path, np.ascontiguousarray(array))


def _gin_worker(input_rows: Path, output: Path) -> int:
    builder = _module("cypshift_public_gin_builder", GIN_BUILDER)
    contract = builder._contract()
    inputs = builder._verify_inputs(contract)
    builder._verify_environment(contract)
    weight = builder._verify_weight(contract, GIN_WEIGHT_ROOT)
    os.environ["MOLFEAT_MODEL_STORE_BUCKET"] = str(GIN_WEIGHT_ROOT)
    rows = _read_csv(input_rows)
    _require(tuple(rows[0]) == PUBLIC_COLUMNS, "public GIN row columns differ")
    raw = [row["raw_structure"] for row in rows]
    array = np.asarray(builder._embed(raw, None, None), dtype=np.float64)
    _require(
        array.shape == (TOTAL_ROWS, 300) and bool(np.isfinite(array).all()),
        "public GIN array differs",
    )
    output.mkdir()
    builder._write_npy(output / "gin.npy", array)
    receipt = {
        "rows": TOTAL_ROWS,
        "shape": [TOTAL_ROWS, 300],
        "dtype": "float64",
        "element_sha256": _element_sha256(array),
        "npy_sha256": _sha256(output / "gin.npy"),
        "weight_receipt_sha256": _sha256(GIN_WEIGHT_ROOT / "weight_receipt.json"),
        "weight_model_sha256": weight["model"]["sha256"],
        "builder_inputs": {
            name: path.relative_to(ROOT).as_posix() for name, path in inputs.items()
        },
    }
    (output / "gin_worker_receipt.json").write_bytes(_json_bytes(receipt))
    return 0


def _verify_public_inputs() -> tuple[list[dict[str, str]], dict[str, Any]]:
    for attempt in (3, 4):
        root = INPUT_ROOTS[attempt]
        _require(_readonly_root(root), f"public input {attempt} is not immutable")
        _require(
            {path.name for path in root.iterdir()}
            == {"public_rows.csv", "input_manifest.json"},
            "public input files differ",
        )
    _require(
        (INPUT_ROOTS[3] / "public_rows.csv").read_bytes()
        == (INPUT_ROOTS[4] / "public_rows.csv").read_bytes(),
        "public input repeats differ",
    )
    first = _read_json(INPUT_ROOTS[3] / "input_manifest.json")
    second = _read_json(INPUT_ROOTS[4] / "input_manifest.json")
    first_compare = dict(first)
    second_compare = dict(second)
    first_compare["attempt"] = second_compare["attempt"]
    _require(first_compare == second_compare, "public input receipts differ")
    _require(
        first["accounting"]["public_test_labels_parsed"] == 0,
        "public input label boundary differs",
    )
    rows = _read_csv(INPUT_ROOTS[3] / "public_rows.csv")
    _require(
        len(rows) == TOTAL_ROWS and tuple(rows[0]) == PUBLIC_COLUMNS,
        "public input population differs",
    )
    return rows, first


def _load_training(
    stage_b: ModuleType,
    accounting: dict[str, int],
) -> tuple[
    list[dict[str, str]], np.ndarray[Any, Any], np.ndarray[Any, Any], dict[str, int]
]:
    stage_b._verify_inputs()
    rows = stage_b._read_csv(stage_b.FIXED_ROOT / "feature_rows.csv")
    fixed, gin, _, _ = stage_b._load_features(rows)
    targets = _read_csv(TRAIN_TARGETS)
    _require(
        _sha256(TRAIN_TARGETS) == TRAIN_TARGETS_SHA256 and len(targets) == 30038,
        "training targets differ",
    )
    _require(
        tuple(targets[0]) == ("task", "molecule_id", "source_row", "target"),
        "training target columns differ",
    )
    target_by_id: dict[str, int] = {}
    for row in targets:
        target_by_id[row["molecule_id"]] = int(row["target"])
        accounting["train_val_labels_parsed"] += 1
    _require(
        len(target_by_id) == 30038
        and [row["molecule_id"] for row in rows]
        == [row["molecule_id"] for row in targets],
        "training alignment differs",
    )
    return rows, fixed, gin, target_by_id


def _public_fixed(
    rows: list[dict[str, str]], staging: Path, accounting: dict[str, int]
) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
    features = _features()
    raw_by_hash: dict[str, str] = {}
    inverse_hashes: list[str] = []
    for row in rows:
        key = row["raw_structure_sha256"]
        _require(
            hashlib.sha256(row["raw_structure"].encode()).hexdigest() == key,
            "raw hash differs",
        )
        if key in raw_by_hash:
            _require(raw_by_hash[key] == row["raw_structure"], "raw hash collision")
        raw_by_hash[key] = row["raw_structure"]
        inverse_hashes.append(key)
    hashes = sorted(raw_by_hash)

    def block_completed(_name: str) -> None:
        accounting["public_fixed_block_arrays_generated"] += 1

    unique, overflow = features.featurize_raw_structures_upstream_int8(
        tuple(raw_by_hash[key] for key in hashes),
        tuple(hashes),
        block_completed=block_completed,
        nonfinite_policy="allow_gasteiger_charge_nan",
    )
    accounting["public_fixed_exact_raw_featurizations"] = len(hashes)
    index = {key: position for position, key in enumerate(hashes)}
    inverse = np.asarray([index[key] for key in inverse_hashes], dtype=np.int64)
    arrays: list[np.ndarray[Any, Any]] = []
    records: dict[str, Any] = {}
    for name, width in zip(FIXED_BLOCKS, FIXED_WIDTHS, strict=True):
        array = np.ascontiguousarray(getattr(unique, name)[inverse])
        _require(
            array.shape == (TOTAL_ROWS, width), f"public fixed block differs: {name}"
        )
        if name == "rdkit_descriptors":
            _require(not bool(np.isinf(array).any()), "public descriptor infinity")
            nan_columns = set(int(value) for value in np.where(np.isnan(array))[1])
            _require(
                nan_columns <= {39, 41, 43, 45}, "public descriptor NaN scope differs"
            )
        else:
            _require(bool(np.isfinite(array).all()), f"public nonfinite block: {name}")
        path = staging / f"{name}.npy"
        _write_npy(path, array)
        accounting["public_fixed_block_arrays_persisted"] += 1
        records[name] = _array_record(path, array)
        arrays.append(array)
    fixed = np.ascontiguousarray(np.concatenate(arrays, axis=1))
    _require(fixed.shape == (TOTAL_ROWS, 2563), "public fixed dimensions differ")
    records["exact_raw_featurizations"] = len(hashes)
    records["overflow"] = {name: asdict(record) for name, record in overflow.items()}
    return fixed, records


def _public_gin(
    rows_path: Path, staging: Path, accounting: dict[str, int]
) -> tuple[np.ndarray[Any, Any], dict[str, Any]]:
    worker = staging / "gin-worker"
    result = subprocess.run(
        [
            str(GIN_PYTHON),
            str(SCRIPT_PATH),
            "--_gin-worker",
            "--_input",
            str(rows_path),
            "--_output",
            str(worker),
        ],
        cwd=ROOT,
        check=False,
        env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
    )
    _require(result.returncode == 0, "public GIN worker failed")
    accounting["public_gin_rows_featurized"] = TOTAL_ROWS
    accounting["public_gin_arrays_generated"] = 1
    array = np.load(worker / "gin.npy", allow_pickle=False)
    _require(
        array.shape == (TOTAL_ROWS, 300) and bool(np.isfinite(array).all()),
        "public GIN output differs",
    )
    target = staging / "gin.npy"
    shutil.copyfile(worker / "gin.npy", target)
    accounting["public_gin_arrays_persisted"] = 1
    worker_receipt = staging / "gin_worker_receipt.json"
    shutil.copyfile(worker / "gin_worker_receipt.json", worker_receipt)
    record = _array_record(target, np.asarray(array))
    record["worker_receipt_path"] = worker_receipt.name
    record["worker_receipt_sha256"] = _sha256(worker_receipt)
    shutil.rmtree(worker)
    return np.asarray(array), record


def _write_predictions(
    path: Path, rows: list[dict[str, str]], values: dict[int, np.ndarray[Any, Any]]
) -> None:
    mean = np.mean(np.stack([values[seed] for seed in SEEDS]), axis=0, dtype=np.float64)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PREDICTION_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for row_index, row in enumerate(rows):
            record: dict[str, object] = {
                name: row[name] for name in PREDICTION_COLUMNS[:5]
            }
            for seed in SEEDS:
                record[f"prediction_seed_{seed}"] = repr(float(values[seed][row_index]))
            record["prediction_probability_mean"] = repr(float(mean[row_index]))
            writer.writerow(record)


def _repeat_comparable_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    comparable = cast(dict[str, Any], json.loads(json.dumps(manifest)))
    comparable.pop("attempt")
    comparable.pop("runtime_seconds")
    comparable.pop("peak_rss_gib")
    comparable["accounting"].pop("additional_family_task_slots_consumed_this_attempt")
    for fit in comparable["fits"]:
        fit.pop("runtime_seconds")
    return comparable


def run_predictions(attempt: int) -> Path:
    output = PREDICTION_ROOTS[attempt]
    blocker = PREDICTION_BLOCKERS[attempt]
    _require(
        not output.exists() and not blocker.exists(),
        "prediction attempt already exists",
    )
    if attempt == 2:
        _require(
            _readonly_root(PREDICTION_ROOTS[1]) and not PREDICTION_BLOCKERS[1].exists(),
            "prediction attempt 1 gate failed",
        )
    accounting = {
        "train_val_labels_parsed": 0,
        "public_test_rows_used": 0,
        "public_test_labels_parsed": 0,
        "public_fixed_exact_raw_featurizations": 0,
        "public_fixed_block_arrays_generated": 0,
        "public_fixed_block_arrays_persisted": 0,
        "public_gin_rows_featurized": 0,
        "public_gin_arrays_generated": 0,
        "public_gin_arrays_persisted": 0,
        "model_fits": 0,
        "model_prediction_vectors": 0,
        "derived_prediction_vectors": 0,
        "staging_family_task_artifacts_completed": 0,
        "canonical_family_task_artifacts": 0,
        "public_test_family_task_slots_consumed": 0,
        "additional_family_task_slots_consumed_this_attempt": 0,
        "metric_evaluations": 0,
        "challenge_assumptions_added": 0,
    }
    staging: Path | None = None
    revision: str | None = None
    start = time.perf_counter()
    try:
        revision = _clean_revision()
        _require(
            _sha256(EVALUATION_BUDGET) == EVALUATION_BUDGET_SHA256,
            "evaluation budget differs",
        )
        _require(_sha256(GIN_BUILDER) == GIN_BUILDER_SHA256, "GIN builder differs")
        rows, input_manifest = _verify_public_inputs()
        accounting["public_test_rows_used"] = len(rows)
        stage_b = _stage_b()
        train_rows, train_fixed, train_gin, targets = _load_training(
            stage_b, accounting
        )
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
        shutil.copyfile(INPUT_ROOTS[3] / "public_rows.csv", staging / "public_rows.csv")
        test_fixed, fixed_records = _public_fixed(rows, staging, accounting)
        test_gin, gin_record = _public_gin(
            staging / "public_rows.csv", staging, accounting
        )
        catboost = __import__("catboost")
        fits: list[dict[str, object]] = []
        prediction_records: dict[str, Any] = {}
        train_index_by_task = {
            task: np.asarray(
                [index for index, row in enumerate(train_rows) if row["task"] == task],
                dtype=np.int64,
            )
            for task in TASKS
        }
        test_index_by_task = {
            task: np.asarray(
                [index for index, row in enumerate(rows) if row["task"] == task],
                dtype=np.int64,
            )
            for task in TASKS
        }
        for family, train_matrix, test_matrix in (
            ("maplight_fixed", train_fixed, test_fixed),
            (
                "maplight_gin",
                np.ascontiguousarray(np.concatenate((train_fixed, train_gin), axis=1)),
                np.ascontiguousarray(np.concatenate((test_fixed, test_gin), axis=1)),
            ),
        ):
            for task in TASKS:
                train_index = train_index_by_task[task]
                test_index = test_index_by_task[task]
                y = np.asarray(
                    [
                        targets[train_rows[index]["molecule_id"]]
                        for index in train_index
                    ],
                    dtype=np.int8,
                )
                _require(set(y.tolist()) == {0, 1}, "training class support differs")
                probabilities: dict[int, np.ndarray[Any, Any]] = {}
                for seed in SEEDS:
                    fit_start = time.perf_counter()
                    model = catboost.CatBoostClassifier(
                        random_strength=2,
                        random_seed=seed,
                        verbose=0,
                        loss_function="Logloss",
                    )
                    model.fit(train_matrix[train_index], y)
                    accounting["model_fits"] += 1
                    _require(
                        [int(value) for value in model.classes_] == [0, 1],
                        "CatBoost class order differs",
                    )
                    probability = np.asarray(
                        model.predict_proba(test_matrix[test_index])[:, 1],
                        dtype=np.float64,
                    )
                    accounting["model_prediction_vectors"] += 1
                    _require(
                        bool(np.isfinite(probability).all())
                        and bool(((probability >= 0) & (probability <= 1)).all()),
                        "public probability differs",
                    )
                    probabilities[seed] = probability
                    fits.append(
                        {
                            "family": family,
                            "task": task,
                            "seed": seed,
                            "train_rows": len(train_index),
                            "public_rows": len(test_index),
                            "feature_count": int(train_matrix.shape[1]),
                            "class_order": [0, 1],
                            "prediction_element_sha256": _element_sha256(probability),
                            "resolved_parameters": model.get_all_params(),
                            "runtime_seconds": time.perf_counter() - fit_start,
                        }
                    )
                task_rows = [rows[index] for index in test_index]
                path = staging / f"{family}__{task}.csv"
                _write_predictions(path, task_rows, probabilities)
                accounting["derived_prediction_vectors"] += 1
                accounting["staging_family_task_artifacts_completed"] += 1
                prediction_records[f"{family}__{task}"] = {
                    "path": path.name,
                    "sha256": _sha256(path),
                    "rows": len(task_rows),
                    "columns": list(PREDICTION_COLUMNS),
                }
        _require(
            accounting["model_fits"] == 30
            and accounting["staging_family_task_artifacts_completed"] == 6,
            "prediction accounting differs",
        )
        accounting["canonical_family_task_artifacts"] = 6
        accounting["public_test_family_task_slots_consumed"] = 6
        accounting["additional_family_task_slots_consumed_this_attempt"] = (
            6 if attempt == 1 else 0
        )
        elapsed = time.perf_counter() - start
        peak = _peak_rss_gib()
        _require(elapsed <= 28800 and peak <= 12, "prediction resource cap exceeded")
        manifest = {
            "schema_version": "cypshift.maplight_public_predictions.v1",
            "attempt": attempt,
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "evaluation_budget_sha256": EVALUATION_BUDGET_SHA256,
            "public_input": {
                "manifest_sha256": _sha256(INPUT_ROOTS[3] / "input_manifest.json"),
                "rows_sha256": _sha256(INPUT_ROOTS[3] / "public_rows.csv"),
                "verified_repeat": True,
                "source_manifest": input_manifest,
            },
            "training": {
                "target_sha256": TRAIN_TARGETS_SHA256,
                "fixed_manifest_sha256": stage_b.FIXED_MANIFEST_SHA256,
                "gin_manifest_sha256": stage_b.GIN_MANIFEST_SHA256,
            },
            "features": {
                "fixed": fixed_records,
                "gin": gin_record,
                "block_order": list(FIXED_BLOCKS),
                "fixed_dimensions": 2563,
                "gin_dimensions": 300,
            },
            "predictions": prediction_records,
            "fits": fits,
            "runtime_seconds": elapsed,
            "peak_rss_gib": peak,
            "accounting": accounting,
            "claim_boundary": CLAIM,
        }
        (staging / "prediction_manifest.json").write_bytes(_json_bytes(manifest))
        if attempt == 2:
            prior = PREDICTION_ROOTS[1]
            payload = {path.name for path in staging.iterdir()} - {
                "prediction_manifest.json"
            }
            _require(
                payload
                == {path.name for path in prior.iterdir()}
                - {"prediction_manifest.json"},
                "prediction repeat files differ",
            )
            for name in payload:
                _require(
                    (staging / name).read_bytes() == (prior / name).read_bytes(),
                    f"prediction repeat differs: {name}",
                )
            _require(
                _repeat_comparable_manifest(
                    _read_json(prior / "prediction_manifest.json")
                )
                == _repeat_comparable_manifest(
                    _read_json(staging / "prediction_manifest.json")
                ),
                "prediction repeat receipt differs",
            )
        _require(_clean_revision() == revision, "source changed during prediction")
        _make_readonly(staging)
        staging.rename(output)
        return output
    except Exception as error:
        accounting["canonical_family_task_artifacts"] = 0
        accounting["public_test_family_task_slots_consumed"] = 0
        accounting["additional_family_task_slots_consumed_this_attempt"] = 0
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        _write_failure(blocker, "predict", attempt, error, accounting, revision)
        raise


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--predict", action="store_true")
    modes.add_argument("--_gin-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3, 4))
    parser.add_argument("--_input", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    if args._gin_worker:
        _require(
            args._input is not None and args._output is not None,
            "GIN worker arguments missing",
        )
        return _gin_worker(args._input, args._output)
    _require(args.attempt is not None, "attempt is required")
    _require(
        (args.prepare and args.attempt in (3, 4))
        or (args.predict and args.attempt in (1, 2)),
        "attempt does not match operation",
    )
    path = (
        prepare_public_input(args.attempt)
        if args.prepare
        else run_predictions(args.attempt)
    )
    print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublicPredictionError as error:
        print(f"public comparator prediction failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
