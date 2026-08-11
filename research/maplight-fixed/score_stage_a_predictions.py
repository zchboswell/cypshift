"""Score the sealed Stage A shadow predictions once, without model access."""

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
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import run_stage_a_catboost as stage

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
PREDICTION_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-predictions-v1"
PREDICTION_MANIFEST_PATH = PREDICTION_ROOT / "prediction_manifest.json"
TARGET_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-targets-v1"
TARGET_MANIFEST_PATH = TARGET_ROOT / "target_manifest.json"
SHADOW_ROWS_PATH = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1/shadow_rows.csv"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-point-scores-v1"
BLOCKER_ROOT = (
    ROOT / "artifacts/blockers/maplight-fixed-stage-a-point-scores-v1-blocker"
)

PREDICTION_MANIFEST_SHA256 = (
    "f7c4f711f22ce53a8b3ce7889a2104d4f9b59715afef825aff2f32cc87499182"
)
TARGET_MANIFEST_SHA256 = stage.TARGET_MANIFEST_SHA256
SCORING_TARGET_SHA256 = (
    "73a4ee1556fdeac293ebd4bcfa43145f29c9ffff2cd3d9640a40c84ee037d3c2"
)
SHADOW_ROWS_SHA256 = stage.SHADOW_ROWS_SHA256
PREDICTION_SOURCE_REVISION = "16d7c2e6e4702bd31c684206432157e8c339ab9b"
PREDICTION_IMPLEMENTATION_SHA256 = (
    "d286d326f349b139c1daa870ea7233c63fb51722fe91e3f71cf5e859c6619c6e"
)

CONFIGURATIONS = tuple(item[0] for item in stage.CANDIDATES) + (
    "r5_maplight_fixed_catboost_mean_probability",
)
CELL_METRIC_COLUMNS = (
    "task",
    "protocol",
    "repeat",
    "configuration_id",
    "rows",
    "positive",
    "negative",
    "auprc",
)
AGGREGATE_COLUMNS = (
    "level",
    "protocol",
    "task",
    "configuration_id",
    "cells",
    "auprc_mean",
)


class StageAScoringError(RuntimeError):
    """Fail-closed point-scoring error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StageAScoringError(message)


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
        _require(reader.fieldnames is not None, f"CSV header missing: {path}")
        return [dict(row) for row in reader]


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
    blob = subprocess.run(
        ["git", "show", f"{revision}:{SCRIPT_PATH.relative_to(ROOT).as_posix()}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    _require(hashlib.sha256(blob).hexdigest() == _sha256(SCRIPT_PATH), "script differs")
    return revision


def _readonly(path: Path) -> bool:
    return not bool(
        os.stat(path).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
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


def _verify_predictions() -> tuple[dict[str, Any], dict[str, Any]]:
    for path, expected in (
        (PREDICTION_MANIFEST_PATH, PREDICTION_MANIFEST_SHA256),
        (TARGET_MANIFEST_PATH, TARGET_MANIFEST_SHA256),
        (SHADOW_ROWS_PATH, SHADOW_ROWS_SHA256),
        (stage.SCRIPT_PATH, PREDICTION_IMPLEMENTATION_SHA256),
    ):
        _require(_sha256(path) == expected, f"input hash differs: {path}")
    for root in (PREDICTION_ROOT, TARGET_ROOT, SHADOW_ROWS_PATH.parent):
        _require(root.exists() and _readonly(root), f"input root is writable: {root}")
    prediction = _json(PREDICTION_MANIFEST_PATH)
    target = _json(TARGET_MANIFEST_PATH)
    _require(
        prediction["source_revision"] == PREDICTION_SOURCE_REVISION
        and prediction["implementation_sha256"] == PREDICTION_IMPLEMENTATION_SHA256,
        "prediction implementation binding differs",
    )
    _require(
        prediction["accounting"]["metric_evaluations"] == 0,
        "prediction score chronology differs",
    )
    _require(
        prediction["accounting"]["validation_target_values_parsed"] == 0,
        "prediction label boundary differs",
    )
    shadow = stage._read_csv(SHADOW_ROWS_PATH)
    for cell, target_record in sorted(target["cells"].items()):
        task, protocol, repeat_text = cell.split("__")
        repeat = int(repeat_text.removeprefix("repeat_"))
        expected_rows = [
            row
            for row in shadow
            if row["task"] == task
            and row[f"{protocol}_repeat_{repeat}_outer_fold"] == "0"
        ]
        bound = prediction["cells"][cell]
        observed = stage._validate_cell_output(
            PREDICTION_ROOT / "cells" / cell,
            cell,
            target_record,
            PREDICTION_SOURCE_REVISION,
            expected_rows,
        )
        _require(observed == bound, "prediction manifest cell binding differs")
    _require(len(prediction["cells"]) == len(target["cells"]) == 18, "cell set differs")
    return prediction, target


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _score(
    target: Mapping[str, Any],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object], int]:
    sklearn_metrics = __import__(
        "sklearn.metrics", fromlist=["average_precision_score"]
    )
    average_precision_score = sklearn_metrics.average_precision_score
    scoring_record = target["scoring_targets"]
    scoring_path = TARGET_ROOT / scoring_record["path"]
    _require(
        _sha256(scoring_path) == SCORING_TARGET_SHA256 == scoring_record["sha256"],
        "scoring target hash differs",
    )
    target_rows = _read_csv(scoring_path)
    _require(
        tuple(target_rows[0]) == ("task", "molecule_id", "source_row", "target"),
        "scoring target columns differ",
    )
    _require(len(target_rows) == 30038, "scoring target rows differ")
    targets = {
        (row["task"], row["molecule_id"], row["source_row"]): int(row["target"])
        for row in target_rows
    }
    _require(len(targets) == len(target_rows), "scoring target identities differ")
    cell_metrics: list[dict[str, object]] = []
    for cell in sorted(target["cells"]):
        rows = _read_csv(PREDICTION_ROOT / "cells" / cell / "predictions.csv")
        task, protocol, repeat_text = cell.split("__")
        repeat = int(repeat_text.removeprefix("repeat_"))
        y = np.asarray(
            [targets[(task, row["molecule_id"], row["source_row"])] for row in rows],
            dtype=np.int8,
        )
        _require(set(y.tolist()) == {0, 1}, "scoring class support differs")
        for configuration in CONFIGURATIONS:
            probability = np.asarray(
                [float(row[configuration]) for row in rows], dtype=np.float64
            )
            score = float(average_precision_score(y, probability))
            _require(np.isfinite(score) and 0 <= score <= 1, "AUPRC differs")
            cell_metrics.append(
                {
                    "task": task,
                    "protocol": protocol,
                    "repeat": repeat,
                    "configuration_id": configuration,
                    "rows": len(rows),
                    "positive": int(y.sum()),
                    "negative": int(len(y) - y.sum()),
                    "auprc": repr(score),
                }
            )
    _require(len(cell_metrics) == 180, "point metric count differs")
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in cell_metrics:
        grouped[
            (str(row["protocol"]), str(row["task"]), str(row["configuration_id"]))
        ].append(float(cast(str, row["auprc"])))
    aggregate: list[dict[str, object]] = []
    task_means: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (protocol, task, configuration), values in sorted(grouped.items()):
        _require(len(values) == 3, "repeat count differs")
        mean = float(np.mean(values, dtype=np.float64))
        aggregate.append(
            {
                "level": "task_repeat_mean",
                "protocol": protocol,
                "task": task,
                "configuration_id": configuration,
                "cells": 3,
                "auprc_mean": repr(mean),
            }
        )
        task_means[(protocol, configuration)].append(mean)
    protocol_macro: dict[str, dict[str, float]] = defaultdict(dict)
    for (protocol, configuration), values in sorted(task_means.items()):
        _require(len(values) == 3, "task count differs")
        mean = float(np.mean(values, dtype=np.float64))
        aggregate.append(
            {
                "level": "protocol_macro",
                "protocol": protocol,
                "task": "macro",
                "configuration_id": configuration,
                "cells": 9,
                "auprc_mean": repr(mean),
            }
        )
        protocol_macro[protocol][configuration] = mean
    primary: dict[str, object] = {}
    for protocol in stage.PROTOCOLS:
        protocol_values = protocol_macro[protocol]
        primary[protocol] = {
            "r1_binary_morgan_seed_1": protocol_values[
                "r1_binary_morgan_catboost_seed_1"
            ],
            "r5_maplight_fixed_seed_1": protocol_values[
                "r5_maplight_fixed_catboost_seed_1"
            ],
            "r5_maplight_fixed_mean_probability": protocol_values[
                "r5_maplight_fixed_catboost_mean_probability"
            ],
            "r5_seed_1_minus_r1_seed_1": protocol_values[
                "r5_maplight_fixed_catboost_seed_1"
            ]
            - protocol_values["r1_binary_morgan_catboost_seed_1"],
        }
    return cell_metrics, aggregate, primary, len(target_rows)


def run_scoring() -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not BLOCKER_ROOT.exists(), "score output exists"
    )
    start = time.perf_counter()
    revision: str | None = None
    labels_parsed = 0
    metrics_completed = 0
    staging: Path | None = None
    try:
        revision = _clean_revision()
        prediction, target = _verify_predictions()
        cell_metrics, aggregate, primary, labels_parsed = _score(target)
        metrics_completed = len(cell_metrics)
        staging = Path(
            tempfile.mkdtemp(prefix=".stage-a-scores-", dir=OUTPUT_ROOT.parent)
        )
        cell_path = staging / "cell_metrics.csv"
        aggregate_path = staging / "aggregate_metrics.csv"
        _write_csv(cell_path, CELL_METRIC_COLUMNS, cell_metrics)
        _write_csv(aggregate_path, AGGREGATE_COLUMNS, aggregate)
        runtime = time.perf_counter() - start
        manifest = {
            "schema_version": "cypshift.maplight_stage_a_point_scores.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "inputs": {
                "prediction_manifest_sha256": PREDICTION_MANIFEST_SHA256,
                "target_manifest_sha256": TARGET_MANIFEST_SHA256,
                "scoring_target_sha256": SCORING_TARGET_SHA256,
                "shadow_rows_sha256": SHADOW_ROWS_SHA256,
            },
            "outputs": {
                "cell_metrics_path": "cell_metrics.csv",
                "cell_metrics_sha256": _sha256(cell_path),
                "aggregate_metrics_path": "aggregate_metrics.csv",
                "aggregate_metrics_sha256": _sha256(aggregate_path),
            },
            "primary_point_summary": primary,
            "forensic_trigger": any(
                float(cast(str, row["auprc"])) >= 0.95 for row in cell_metrics
            ),
            "runtime_seconds": runtime,
            "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**3),
            "accounting": {
                "prediction_cells_revalidated": len(prediction["cells"]),
                "train_val_scoring_labels_parsed": labels_parsed,
                "point_metric_evaluations": metrics_completed,
                "bootstrap_metric_evaluations": 0,
                "model_fits": 0,
                "predictions_generated": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
                "gin_weight_bytes_downloaded": 0,
                "challenge_assumptions_added": 0,
            },
            "claim_boundary": "Shadow point AUPRC only; no uncertainty, superiority, public-test, GIN, or challenge claim.",
        }
        (staging / "score_manifest.json").write_bytes(_json_bytes(manifest))
        _require(_clean_revision() == revision, "source changed during scoring")
        _make_readonly(staging)
        staging.rename(OUTPUT_ROOT)
        return OUTPUT_ROOT
    except Exception as error:
        if staging is not None:
            _remove(staging)
        blocker = Path(
            tempfile.mkdtemp(prefix=".stage-a-score-blocker-", dir=BLOCKER_ROOT.parent)
        )
        receipt = {
            "schema_version": "cypshift.maplight_stage_a_point_score_failure.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "failure": {"kind": type(error).__name__, "message": str(error)},
            "runtime_seconds": time.perf_counter() - start,
            "accounting": {
                "train_val_scoring_labels_parsed": labels_parsed,
                "point_metric_evaluations": metrics_completed,
                "bootstrap_metric_evaluations": 0,
                "model_fits": 0,
                "predictions_generated": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
            },
        }
        (blocker / "failure_receipt.json").write_bytes(_json_bytes(receipt))
        _make_readonly(blocker)
        blocker.rename(BLOCKER_ROOT)
        raise StageAScoringError(
            f"scoring failed; blocker retained at {BLOCKER_ROOT}"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        output = run_scoring()
    except (StageAScoringError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
