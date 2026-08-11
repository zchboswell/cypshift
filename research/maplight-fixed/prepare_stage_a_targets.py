"""Project the frozen train-only labels into Stage A scoring and cell files.

This is the only Stage A process authorized to resolve the pinned train-only
measurement file. It emits no measurement provenance and performs no feature,
model, prediction, metric, GIN, challenge, or public-test operation.
"""

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

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_stage_a_contract.json"
SHADOW_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1"
SHADOW_ROWS_PATH = SHADOW_ROOT / "shadow_rows.csv"
SHADOW_MANIFEST_PATH = SHADOW_ROOT / "shadow_manifest.json"
MEASUREMENT_ROOT = ROOT / "artifacts/benchmarks/native-prediction-inputs-v1"
MEASUREMENT_PATH = MEASUREMENT_ROOT / "tdc/measurements.csv"
MEASUREMENT_MANIFEST_PATH = MEASUREMENT_ROOT / "prediction_input_manifest.json"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-targets-v1"
FIRST_BLOCKER_ROOT = (
    ROOT / "artifacts/blockers/maplight-fixed-stage-a-targets-v1-blocker"
)
RETRY_BLOCKER_ROOT = (
    ROOT / "artifacts/blockers/maplight-fixed-stage-a-targets-v1-attempt-2-blocker"
)

CONTRACT_SHA256 = "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710"
SHADOW_ROWS_SHA256 = "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
SHADOW_MANIFEST_SHA256 = (
    "3eb972713d88e08420134e7776755d4e62510a5250edf99edc2021272c112656"
)
MEASUREMENT_SHA256 = "b3bfe56d660affcfe13c74b82721179a8e1322b6dc938c10137da5615ce62e75"
MEASUREMENT_MANIFEST_SHA256 = (
    "9e5350490dfc4674b96960644e3e49c4887ec37d3fbb62de22d47dc6481444a1"
)
FIRST_BLOCKER_SHA256 = (
    "892a3afa755e13fb11cd82ef2d95c3f15cc802a84a42041b8277b305f4eeb9ee"
)

TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
PROTOCOLS = ("scaffold", "community")
REPEATS = (0, 1, 2)
TASK_CLASS_COUNTS = {
    "cyp2c9_veith": (3275, 6398),
    "cyp2d6_veith": (2071, 8433),
    "cyp3a4_veith": (4028, 5833),
}
SCORING_COLUMNS = ("task", "molecule_id", "source_row", "target")
TRAINING_COLUMNS = (
    "task",
    "protocol",
    "repeat",
    "molecule_id",
    "source_row",
    "target",
)
SHADOW_COLUMNS = (
    "task",
    "molecule_id",
    "source_row",
    "raw_structure",
    "raw_structure_sha256",
    "standardized_structure",
    "standardized_structure_hash",
    "scaffold_group_hash",
    "community_group_hash",
    "scaffold_repeat_0_outer_fold",
    "scaffold_repeat_0_inner_fold",
    "scaffold_repeat_1_outer_fold",
    "scaffold_repeat_1_inner_fold",
    "scaffold_repeat_2_outer_fold",
    "scaffold_repeat_2_inner_fold",
    "community_repeat_0_outer_fold",
    "community_repeat_0_inner_fold",
    "community_repeat_1_outer_fold",
    "community_repeat_1_inner_fold",
    "community_repeat_2_outer_fold",
    "community_repeat_2_inner_fold",
)
MEASUREMENT_COLUMNS = (
    "measurement_id",
    "molecule_id",
    "endpoint",
    "isoform",
    "nadph_condition",
    "probe",
    "readout",
    "value",
    "lower_bound",
    "upper_bound",
    "censoring",
    "unit",
    "quality",
    "source",
    "provenance",
)
ACCOUNTING = {
    "train_val_labels_parsed": 30038,
    "training_target_values_emitted": 144183,
    "scoring_target_values_emitted": 30038,
    "cell_target_files_emitted": 18,
    "public_test_rows_used": 0,
    "public_test_labels_parsed": 0,
    "feature_arrays_opened": 0,
    "model_fits": 0,
    "predictions": 0,
    "metric_evaluations": 0,
    "gin_weight_bytes_downloaded": 0,
    "challenge_assumptions_added": 0,
}


class TargetProjectionError(RuntimeError):
    """A fail-closed target-projection error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TargetProjectionError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _git(arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
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
        "source signature or authorship differs",
    )
    relative = SCRIPT_PATH.relative_to(ROOT).as_posix()
    tracked = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    _require(
        hashlib.sha256(tracked).hexdigest() == _sha256(SCRIPT_PATH), "script differs"
    )
    return revision


def _verify_inputs() -> str:
    for path, expected in (
        (CONTRACT_PATH, CONTRACT_SHA256),
        (SHADOW_ROWS_PATH, SHADOW_ROWS_SHA256),
        (SHADOW_MANIFEST_PATH, SHADOW_MANIFEST_SHA256),
        (MEASUREMENT_PATH, MEASUREMENT_SHA256),
        (MEASUREMENT_MANIFEST_PATH, MEASUREMENT_MANIFEST_SHA256),
    ):
        _require(path.is_file() and not path.is_symlink(), f"input is invalid: {path}")
        _require(_sha256(path) == expected, f"input hash differs: {path}")
    for path in (
        SHADOW_ROWS_PATH,
        SHADOW_MANIFEST_PATH,
        MEASUREMENT_PATH,
        MEASUREMENT_MANIFEST_PATH,
    ):
        _require(
            not bool(
                os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            ),
            f"ignored input is writable: {path}",
        )
    _require(
        not bool(
            os.stat(SHADOW_ROOT).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        )
        and not bool(
            os.stat(MEASUREMENT_ROOT).st_mode
            & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        ),
        "input root is writable",
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    _require(
        contract["schema_version"] == "cypshift.maplight_fixed_stage_a_contract.v1",
        "contract identity differs",
    )
    return _clean_revision()


def _verify_prior_failure() -> None:
    if not FIRST_BLOCKER_ROOT.exists():
        return
    receipt = FIRST_BLOCKER_ROOT / "failure_receipt.json"
    _require(
        FIRST_BLOCKER_ROOT.is_dir()
        and not FIRST_BLOCKER_ROOT.is_symlink()
        and {path.name for path in FIRST_BLOCKER_ROOT.iterdir()}
        == {"failure_receipt.json"}
        and receipt.is_file()
        and not receipt.is_symlink()
        and _sha256(receipt) == FIRST_BLOCKER_SHA256,
        "prior infrastructure blocker differs",
    )
    record = json.loads(receipt.read_text(encoding="utf-8"))
    _require(
        record["failure"]
        == {
            "kind": "TargetProjectionError",
            "message": f"input is writable: {CONTRACT_PATH}",
        }
        and record["source_revision"] is None
        and all(value == 0 for value in record["accounting"].values()),
        "prior infrastructure blocker content differs",
    )


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require(tuple(reader.fieldnames or ()) == columns, f"columns differ: {path}")
        rows = [{key: str(value) for key, value in row.items()} for row in reader]
    _require(
        all(set(row) == set(columns) for row in rows), f"row width differs: {path}"
    )
    return rows


def _targets() -> tuple[list[dict[str, str]], dict[str, str]]:
    measurements = _read_csv(MEASUREMENT_PATH, MEASUREMENT_COLUMNS)
    _require(len(measurements) == 30038, "measurement row count differs")
    labels: dict[str, str] = {}
    for row in measurements:
        molecule_id = row["molecule_id"]
        _require(molecule_id not in labels, "duplicate measurement molecule ID")
        _require(
            "train_val" in molecule_id and "test" not in molecule_id,
            "partition differs",
        )
        _require(row["value"] in {"0.0", "1.0"}, "target value differs")
        labels[molecule_id] = row["value"][0]

    shadow = _read_csv(SHADOW_ROWS_PATH, SHADOW_COLUMNS)
    _require(len(shadow) == 30038, "shadow row count differs")
    _require(
        {row["molecule_id"] for row in shadow} == set(labels),
        "shadow and target identity sets differ",
    )
    _require(
        len({row["molecule_id"] for row in shadow}) == 30038,
        "shadow identities are not unique",
    )
    _require({row["task"] for row in shadow} == set(TASKS), "shadow tasks differ")
    _require(
        all(
            row["molecule_id"].startswith(f"tdc:{row['task']}:train_val:")
            for row in shadow
        ),
        "shadow task identity differs",
    )
    for task in TASKS:
        task_labels = [
            labels[row["molecule_id"]] for row in shadow if row["task"] == task
        ]
        positive = sum(value == "1" for value in task_labels)
        _require(
            (positive, len(task_labels) - positive) == TASK_CLASS_COUNTS[task],
            "task class count differs",
        )
    return shadow, labels


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: Sequence[Mapping[str, str]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row[key] for key in columns} for row in rows)


def _cell_name(task: str, protocol: str, repeat: int) -> str:
    return f"{task}__{protocol}__repeat_{repeat}"


def _readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _peak_rss_gib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**3)


def _remove(root: Path) -> None:
    if root.exists():
        for path in root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            else:
                path.chmod(0o644)
        root.chmod(0o755)
        shutil.rmtree(root)


def _write_failure(
    error: Exception, revision: str | None, elapsed: float, labels_parsed: int
) -> Path:
    blocker = RETRY_BLOCKER_ROOT if FIRST_BLOCKER_ROOT.exists() else FIRST_BLOCKER_ROOT
    _require(not OUTPUT_ROOT.exists() and not blocker.exists(), "output already exists")
    staging = Path(
        tempfile.mkdtemp(prefix=".stage-a-target-blocker-", dir=blocker.parent)
    )
    receipt = {
        "schema_version": "cypshift.maplight_stage_a_target_failure.v1",
        "source_revision": revision,
        "contract_sha256": CONTRACT_SHA256,
        "implementation_sha256": _sha256(SCRIPT_PATH),
        "inputs": {
            "shadow_rows": SHADOW_ROWS_SHA256,
            "shadow_manifest": SHADOW_MANIFEST_SHA256,
            "train_val_measurements": MEASUREMENT_SHA256,
            "measurement_parent_manifest": MEASUREMENT_MANIFEST_SHA256,
        },
        "failure": {"kind": type(error).__name__, "message": str(error)},
        "runtime_seconds": elapsed,
        "peak_rss_gib": _peak_rss_gib(),
        "accounting": {
            "train_val_labels_parsed": labels_parsed,
            "public_test_rows_used": 0,
            "public_test_labels_parsed": 0,
            "feature_arrays_opened": 0,
            "model_fits": 0,
            "predictions": 0,
            "metric_evaluations": 0,
        },
        "claim_boundary": "Train-only target projection failure; no model or score.",
    }
    (staging / "failure_receipt.json").write_bytes(_json_bytes(receipt))
    _readonly(staging)
    staging.rename(blocker)
    return blocker


def prepare_targets() -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not RETRY_BLOCKER_ROOT.exists(),
        "output already exists",
    )
    _verify_prior_failure()
    revision: str | None = None
    staging: Path | None = None
    start = time.perf_counter()
    labels_parsed = 0
    try:
        revision = _verify_inputs()
        shadow, labels = _targets()
        labels_parsed = len(labels)
        staging = Path(
            tempfile.mkdtemp(prefix=".stage-a-targets-", dir=OUTPUT_ROOT.parent)
        )
        scoring_root = staging / "scoring"
        cells_root = staging / "cells"
        scoring_root.mkdir()
        cells_root.mkdir()

        scoring_rows = [
            {
                "task": row["task"],
                "molecule_id": row["molecule_id"],
                "source_row": row["source_row"],
                "target": labels[row["molecule_id"]],
            }
            for row in shadow
        ]
        scoring_path = scoring_root / "scoring_targets.csv"
        _write_csv(scoring_path, SCORING_COLUMNS, scoring_rows)

        cells: dict[str, dict[str, object]] = {}
        total_training_rows = 0
        for task in TASKS:
            for protocol in PROTOCOLS:
                for repeat in REPEATS:
                    name = _cell_name(task, protocol, repeat)
                    cell_root = cells_root / name
                    cell_root.mkdir()
                    fold_column = f"{protocol}_repeat_{repeat}_outer_fold"
                    training_rows = [
                        {
                            "task": task,
                            "protocol": protocol,
                            "repeat": str(repeat),
                            "molecule_id": row["molecule_id"],
                            "source_row": row["source_row"],
                            "target": labels[row["molecule_id"]],
                        }
                        for row in shadow
                        if row["task"] == task and row[fold_column] != "0"
                    ]
                    positives = sum(row["target"] == "1" for row in training_rows)
                    negatives = len(training_rows) - positives
                    _require(
                        positives > 0 and negatives > 0, "cell lacks class support"
                    )
                    path = cell_root / "outer_training_targets.csv"
                    _write_csv(path, TRAINING_COLUMNS, training_rows)
                    total_training_rows += len(training_rows)
                    cells[name] = {
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": _sha256(path),
                        "task": task,
                        "protocol": protocol,
                        "repeat": repeat,
                        "rows": len(training_rows),
                        "positive": positives,
                        "negative": negatives,
                    }
        _require(len(cells) == 18, "cell count differs")
        _require(total_training_rows == 144183, "training row total differs")
        positives = sum(row["target"] == "1" for row in scoring_rows)
        runtime_seconds = time.perf_counter() - start
        peak_rss_gib = _peak_rss_gib()
        manifest = {
            "schema_version": "cypshift.maplight_stage_a_targets.v1",
            "source_revision": revision,
            "contract_sha256": CONTRACT_SHA256,
            "implementation": {
                "path": SCRIPT_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(SCRIPT_PATH),
            },
            "inputs": {
                "shadow_rows": SHADOW_ROWS_SHA256,
                "shadow_manifest": SHADOW_MANIFEST_SHA256,
                "train_val_measurements": MEASUREMENT_SHA256,
                "measurement_parent_manifest": MEASUREMENT_MANIFEST_SHA256,
            },
            "scoring_targets": {
                "path": scoring_path.relative_to(staging).as_posix(),
                "sha256": _sha256(scoring_path),
                "columns": list(SCORING_COLUMNS),
                "rows": 30038,
                "positive": positives,
                "negative": 30038 - positives,
            },
            "cells": cells,
            "runtime_seconds": runtime_seconds,
            "peak_rss_gib": peak_rss_gib,
            "accounting": ACCOUNTING,
            "claim_boundary": "Train-only target projection; no feature, model, prediction, metric, GIN, challenge, or public-test operation.",
        }
        _require(
            runtime_seconds <= 600 and peak_rss_gib <= 2,
            "target projection resource cap exceeded",
        )
        (staging / "target_manifest.json").write_bytes(_json_bytes(manifest))
        _require(_verify_inputs() == revision, "inputs changed during projection")
        _readonly(staging)
        staging.rename(OUTPUT_ROOT)
        return OUTPUT_ROOT
    except Exception as error:
        if staging is not None:
            _remove(staging)
        blocker = _write_failure(
            error, revision, time.perf_counter() - start, labels_parsed
        )
        raise TargetProjectionError(
            f"target projection failed; blocker at {blocker}"
        ) from error


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _arguments(argv)
    try:
        output = prepare_targets()
    except (TargetProjectionError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
