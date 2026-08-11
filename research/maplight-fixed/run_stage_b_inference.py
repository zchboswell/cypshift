"""Score the frozen Stage B GIN predictions and run grouped inference once."""

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
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
CONTRACT_PATH = ROOT / "benchmarks/maplight_gin_stage_b_contract.json"
PREDICTION_ROOT = ROOT / "artifacts/benchmarks/maplight-gin-stage-b-predictions-v1"
PREDICTION_MANIFEST = PREDICTION_ROOT / "prediction_manifest.json"
STAGE_A_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-predictions-v1"
STAGE_A_MANIFEST = STAGE_A_ROOT / "prediction_manifest.json"
TARGET_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-targets-v1"
TARGET_MANIFEST = TARGET_ROOT / "target_manifest.json"
SHADOW_ROWS = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-v1/shadow_rows.csv"
TOPOLOGY_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-topology-v1"
TOPOLOGY_MANIFEST = TOPOLOGY_ROOT / "topology_manifest.json"
TOPOLOGY_ROWS = TOPOLOGY_ROOT / "validation_topology.csv"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-gin-stage-b-inference-v1"
BLOCKER_ROOT = ROOT / "artifacts/blockers/maplight-gin-stage-b-inference-v1-blocker"

CONTRACT_SHA256 = "8d5c6f95e700760cdb31cb7b293c24da779adefa28a6f72e9cffdce5571bb906"
PREDICTION_MANIFEST_SHA256 = (
    "a9b78b382ecf1cf4bb78843ec22edca04a7d516c6597443f59a8712ecd23f418"
)
STAGE_A_MANIFEST_SHA256 = (
    "f7c4f711f22ce53a8b3ce7889a2104d4f9b59715afef825aff2f32cc87499182"
)
TARGET_MANIFEST_SHA256 = (
    "716ffd20d169b305e5014e368b222cf15b347f48ff216ef9cfebfafc0791705a"
)
SHADOW_ROWS_SHA256 = "b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f"
TOPOLOGY_MANIFEST_SHA256 = (
    "cf4d4bb759d93fea9d4857dd21fac8758c559bb37fa3c6cee87973f3fe6bfd77"
)
TOPOLOGY_ROWS_SHA256 = (
    "0f575a2d9c230db3e83026f44c2a3f17cdf2fe942d9eb167f487aa3d892d0c63"
)
RESEARCH_PROJECT_SHA256 = (
    "20addcbfa3d7dbfa5d3a9f24f3090c22f11b556166213b2649c6c55e58556234"
)
RESEARCH_LOCK_SHA256 = (
    "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8"
)
RESEARCH_PYTHON_SHA256 = (
    "3817f125779f46c574b17c4adbdd0975ef8c32ae92509fed295212797d314d6a"
)

TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
PROTOCOLS = ("scaffold", "community")
SEEDS = {"scaffold": 20260818, "community": 20260819}
REPLICATES = 2000
MAX_ATTEMPTS = 20000
FIXED = "r5_maplight_fixed_catboost_seed_1"
FIXED_MEAN = "r5_maplight_fixed_catboost_mean_probability"
B2 = "b2_maplight_fixed_plus_gin_catboost_seed_1"
B3 = "b3_maplight_fixed_plus_shuffled_gin_catboost_seed_1"
B4 = "b4_maplight_fixed_plus_noise_catboost_seed_1"
B2_MEAN = "b2_maplight_fixed_plus_gin_catboost_mean_probability"
NEW_CONFIGS = (
    "b1_gin_alone_catboost_seed_1",
    B2,
    "b2_maplight_fixed_plus_gin_catboost_seed_2",
    "b2_maplight_fixed_plus_gin_catboost_seed_3",
    "b2_maplight_fixed_plus_gin_catboost_seed_4",
    "b2_maplight_fixed_plus_gin_catboost_seed_5",
    B3,
    B4,
    B2_MEAN,
)
POINT_CONFIGS = (FIXED, FIXED_MEAN, *NEW_CONFIGS)
BOOT_CONFIGS = (FIXED, B2, B3, B4)
CONTRASTS = {
    "primary": (B2, FIXED),
    "shuffle_control": (B2, B3),
    "noise_control": (B2, B4),
}


class StageBInferenceError(RuntimeError):
    """Fail-closed Stage B inference error."""


class StageBForensicStop(StageBInferenceError):
    """Stop after retaining point evidence that reached the forensic gate."""

    def __init__(
        self,
        trigger: Mapping[str, object],
        point: list[dict[str, object]],
        aggregate: list[dict[str, object]],
    ) -> None:
        super().__init__("AUPRC forensic threshold reached")
        self.trigger = dict(trigger)
        self.point = point
        self.aggregate = aggregate


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StageBInferenceError(message)


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
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, object]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


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


def _metric() -> Callable[..., float]:
    module = __import__("sklearn.metrics", fromlist=["average_precision_score"])
    return cast(Callable[..., float], module.average_precision_score)


def _verify_environment() -> dict[str, str]:
    _require(sys.version_info[:3] == (3, 10, 13), "Python version differs")
    _require(platform.system() == "Darwin", "platform differs")
    _require(platform.machine() == "arm64", "architecture differs")
    versions = {
        "numpy": importlib.metadata.version("numpy"),
        "scikit-learn": importlib.metadata.version("scikit-learn"),
    }
    _require(
        versions == {"numpy": "1.25.2", "scikit-learn": "1.3.0"},
        "metric package versions differ",
    )
    for path, expected in (
        (ROOT / "research/maplight-fixed/pyproject.toml", RESEARCH_PROJECT_SHA256),
        (ROOT / "research/maplight-fixed/uv.lock", RESEARCH_LOCK_SHA256),
        (ROOT / "research/maplight-fixed/.python-version", RESEARCH_PYTHON_SHA256),
    ):
        _require(_sha256(path) == expected, f"environment input differs: {path}")
    return {"python": platform.python_version(), **versions}


def _verify_prediction_files(root: Path, manifest: Mapping[str, Any]) -> None:
    cells = cast(Mapping[str, Mapping[str, Any]], manifest["cells"])
    _require(len(cells) == 18, "prediction cell count differs")
    for cell, record in cells.items():
        cell_root = root / "cells" / cell
        _require(
            {path.name for path in cell_root.iterdir()}
            == {"predictions.csv", "cell_receipt.json"},
            "prediction cell files differ",
        )
        _require(
            all(_readonly(path) for path in cell_root.iterdir()),
            "prediction cell file is writable",
        )
        _require(
            _sha256(cell_root / "predictions.csv") == record["prediction_sha256"]
            and _sha256(cell_root / "cell_receipt.json") == record["receipt_sha256"],
            "prediction cell hash differs",
        )


def _verify_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    environment = _verify_environment()
    for path, expected in (
        (CONTRACT_PATH, CONTRACT_SHA256),
        (PREDICTION_MANIFEST, PREDICTION_MANIFEST_SHA256),
        (STAGE_A_MANIFEST, STAGE_A_MANIFEST_SHA256),
        (TARGET_MANIFEST, TARGET_MANIFEST_SHA256),
        (SHADOW_ROWS, SHADOW_ROWS_SHA256),
        (TOPOLOGY_MANIFEST, TOPOLOGY_MANIFEST_SHA256),
        (TOPOLOGY_ROWS, TOPOLOGY_ROWS_SHA256),
    ):
        _require(_sha256(path) == expected, f"input hash differs: {path}")
    for root in (
        PREDICTION_ROOT,
        STAGE_A_ROOT,
        TARGET_ROOT,
        SHADOW_ROWS.parent,
        TOPOLOGY_ROOT,
    ):
        _require(root.exists() and _readonly(root), f"input root is writable: {root}")
    prediction = _json(PREDICTION_MANIFEST)
    _require(
        prediction["accounting"]["cells"] == 18
        and prediction["accounting"]["metric_evaluations"] == 0
        and prediction["accounting"]["validation_target_values_parsed"] == 0,
        "prediction chronology differs",
    )
    stage_a = _json(STAGE_A_MANIFEST)
    _verify_prediction_files(PREDICTION_ROOT, prediction)
    _verify_prediction_files(STAGE_A_ROOT, stage_a)
    target = _json(TARGET_MANIFEST)
    return prediction, target, environment


def _load_cells(
    target: Mapping[str, Any],
    on_labels_parsed: Callable[[int], None],
) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    scoring = cast(Mapping[str, Any], target["scoring_targets"])
    scoring_path = TARGET_ROOT / str(scoring["path"])
    _require(_sha256(scoring_path) == scoring["sha256"], "scoring target differs")
    target_rows = _read_csv(scoring_path)
    on_labels_parsed(len(target_rows))
    shadow_rows = _read_csv(SHADOW_ROWS)
    _require(len(target_rows) == len(shadow_rows) == 30038, "source row count differs")
    shadow = {row["molecule_id"]: row for row in shadow_rows}
    targets = {
        (row["task"], row["molecule_id"], row["source_row"]): int(row["target"])
        for row in target_rows
    }
    labels: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in target_rows:
        labels[
            (row["task"], shadow[row["molecule_id"]]["standardized_structure_hash"])
        ].add(int(row["target"]))
    conflicts = {key for key, values in labels.items() if len(values) > 1}
    _require(len(conflicts) == 11, "conflicting structure-task count differs")
    topology = {
        (
            row["task"],
            row["protocol"],
            int(row["repeat"]),
            row["standardized_structure_hash"],
        ): row
        for row in _read_csv(TOPOLOGY_ROWS)
    }
    _require(len(topology) == 35963, "topology row count differs")
    cells: list[dict[str, Any]] = []
    for cell in sorted(cast(Mapping[str, Any], target["cells"])):
        task, protocol, repeat_text = cell.split("__")
        repeat = int(repeat_text.removeprefix("repeat_"))
        new_rows = _read_csv(PREDICTION_ROOT / "cells" / cell / "predictions.csv")
        old_rows = _read_csv(STAGE_A_ROOT / "cells" / cell / "predictions.csv")
        new_ids = [(row["molecule_id"], row["source_row"]) for row in new_rows]
        old_ids = [(row["molecule_id"], row["source_row"]) for row in old_rows]
        _require(new_ids == old_ids, "prediction row alignment differs")
        y: list[int] = []
        structures: list[str] = []
        groups: list[str] = []
        similarities: list[float] = []
        scores: dict[str, list[float]] = {name: [] for name in POINT_CONFIGS}
        for new, old in zip(new_rows, old_rows, strict=True):
            identity = (task, new["molecule_id"], new["source_row"])
            structure = shadow[new["molecule_id"]]["standardized_structure_hash"]
            top = topology[(task, protocol, repeat, structure)]
            y.append(targets[identity])
            structures.append(structure)
            groups.append(top["group_hash"])
            similarities.append(float(top["max_train_tanimoto"]))
            scores[FIXED].append(float(old[FIXED]))
            scores[FIXED_MEAN].append(float(old[FIXED_MEAN]))
            for name in NEW_CONFIGS:
                scores[name].append(float(new[name]))
        score_arrays = {
            name: np.asarray(values, dtype=np.float64)
            for name, values in scores.items()
        }
        _require(
            all(
                bool(np.isfinite(values).all())
                and bool(((values >= 0) & (values <= 1)).all())
                for values in score_arrays.values()
            ),
            "prediction probability differs",
        )
        cells.append(
            {
                "cell": cell,
                "task": task,
                "protocol": protocol,
                "repeat": repeat,
                "y": np.asarray(y, dtype=np.int8),
                "structures": np.asarray(structures),
                "groups": np.asarray(groups),
                "similarities": np.asarray(similarities, dtype=np.float64),
                "scores": score_arrays,
            }
        )
    return cells, conflicts


def _weight(
    cell: Mapping[str, Any], population: str, conflicts: set[tuple[str, str]]
) -> NDArray[np.float64]:
    if population == "official_row_weighted":
        return np.ones(len(cell["y"]), dtype=np.float64)
    if population == "unique_structure_task_cell":
        _, inverse, counts = np.unique(
            cell["structures"], return_inverse=True, return_counts=True
        )
        return np.asarray(1.0 / counts[inverse], dtype=np.float64)
    if population == "conflict_excluded":
        return np.asarray(
            [
                0.0 if (cell["task"], value) in conflicts else 1.0
                for value in cell["structures"]
            ],
            dtype=np.float64,
        )
    if population == "low_neighbor_below_0_60":
        return np.asarray(cell["similarities"] < 0.60, dtype=np.float64)
    raise StageBInferenceError(f"unknown population: {population}")


def _point(
    cells: Sequence[Mapping[str, Any]], metric: Callable[..., float]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for cell in cells:
        for name in POINT_CONFIGS:
            value = float(metric(cell["y"], cell["scores"][name]))
            rows.append(
                {
                    "cell": cell["cell"],
                    "task": cell["task"],
                    "protocol": cell["protocol"],
                    "repeat": cell["repeat"],
                    "configuration": name,
                    "auprc": repr(value),
                }
            )
            grouped[(cell["protocol"], cell["task"], name)].append(value)
    aggregate: list[dict[str, object]] = []
    macros: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (protocol, task, name), values in sorted(grouped.items()):
        _require(len(values) == 3, "point repeat count differs")
        mean = float(np.mean(values, dtype=np.float64))
        macros[(protocol, name)].append(mean)
        aggregate.append(
            {
                "protocol": protocol,
                "level": "task_repeat_mean",
                "task": task,
                "configuration": name,
                "auprc": repr(mean),
            }
        )
    for (protocol, name), values in sorted(macros.items()):
        _require(len(values) == 3, "point task count differs")
        aggregate.append(
            {
                "protocol": protocol,
                "level": "protocol_macro",
                "task": "macro",
                "configuration": name,
                "auprc": repr(float(np.mean(values, dtype=np.float64))),
            }
        )
    return rows, aggregate


def _sensitivity(
    cells: Sequence[Mapping[str, Any]],
    conflicts: set[tuple[str, str]],
    metric: Callable[..., float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for population in (
        "unique_structure_task_cell",
        "conflict_excluded",
        "low_neighbor_below_0_60",
    ):
        grouped: dict[tuple[str, str], list[tuple[float, float, float]]] = defaultdict(
            list
        )
        for cell in cells:
            weight = _weight(cell, population, conflicts)
            y = cell["y"]
            _require(
                float(weight[y == 0].sum()) > 0 and float(weight[y == 1].sum()) > 0,
                "sensitivity class support differs",
            )
            fixed = float(metric(y, cell["scores"][FIXED], sample_weight=weight))
            b2 = float(metric(y, cell["scores"][B2], sample_weight=weight))
            grouped[(cell["protocol"], cell["task"])].append(
                (fixed, b2, float(weight.sum()))
            )
        macros: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
        for (protocol, task), values in sorted(grouped.items()):
            fixed = float(np.mean([v[0] for v in values]))
            b2 = float(np.mean([v[1] for v in values]))
            effective = float(sum(v[2] for v in values))
            macros[protocol].append((fixed, b2, effective))
            rows.append(
                {
                    "population": population,
                    "protocol": protocol,
                    "level": "task_repeat_mean",
                    "task": task,
                    "effective_rows": repr(effective),
                    "fixed_auprc": repr(fixed),
                    "b2_auprc": repr(b2),
                    "delta": repr(b2 - fixed),
                }
            )
        for protocol, values in sorted(macros.items()):
            fixed = float(np.mean([v[0] for v in values]))
            b2 = float(np.mean([v[1] for v in values]))
            rows.append(
                {
                    "population": population,
                    "protocol": protocol,
                    "level": "protocol_macro",
                    "task": "macro",
                    "effective_rows": repr(float(sum(v[2] for v in values))),
                    "fixed_auprc": repr(fixed),
                    "b2_auprc": repr(b2),
                    "delta": repr(b2 - fixed),
                }
            )
    return rows


def _interval(values: Sequence[float]) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    lower, upper = np.quantile(array, [0.025, 0.975], method="linear")
    return float(np.mean(array)), float(lower), float(upper)


def _bootstrap(
    protocol: str, cells: Sequence[Mapping[str, Any]], metric: Callable[..., float]
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, int],
]:
    selected = [cell for cell in cells if cell["protocol"] == protocol]
    shadow = _read_csv(SHADOW_ROWS)
    column = f"{protocol}_group_hash"
    universe = sorted({row[column] for row in shadow})
    expected = 9114 if protocol == "scaffold" else 9902
    _require(
        len(selected) == 9 and len(universe) == expected, "bootstrap population differs"
    )
    index = {value: i for i, value in enumerate(universe)}
    cell_index = [
        np.asarray([index[value] for value in cell["groups"]], dtype=np.int64)
        for cell in selected
    ]
    top: dict[tuple[str, str], tuple[int, int]] = {}
    for task in TASKS:
        counts: Counter[str] = Counter()
        positives: Counter[str] = Counter()
        for cell in selected:
            if cell["task"] == task:
                for group, label in zip(cell["groups"], cell["y"], strict=True):
                    counts[str(group)] += 1
                    positives[str(group)] += int(label)
        for group in sorted(counts, key=lambda value: (-counts[value], value))[:10]:
            top[(task, group)] = (counts[group], positives[group])
    distributions: dict[tuple[str, str], list[float]] = {
        (contrast, task): [] for contrast in CONTRASTS for task in (*TASKS, "macro")
    }
    absence = {key: [] for key in top}
    rows: list[dict[str, object]] = []
    attempts = rejected = 0
    rng = np.random.Generator(np.random.PCG64(SEEDS[protocol]))
    while len(rows) < REPLICATES and attempts < MAX_ATTEMPTS:
        attempts += 1
        sampled = rng.choice(len(universe), size=len(universe), replace=True)
        multiplicity = np.bincount(sampled, minlength=len(universe)).astype(np.int64)
        weights = [multiplicity[value] for value in cell_index]
        if any(
            int(weight[cell["y"] == 0].sum()) == 0
            or int(weight[cell["y"] == 1].sum()) == 0
            for cell, weight in zip(selected, weights, strict=True)
        ):
            rejected += 1
            continue
        scores: dict[tuple[str, str], list[float]] = defaultdict(list)
        for cell, weight in zip(selected, weights, strict=True):
            for name in BOOT_CONFIGS:
                scores[(cell["task"], name)].append(
                    float(metric(cell["y"], cell["scores"][name], sample_weight=weight))
                )
        record: dict[str, object] = {"protocol": protocol, "replicate": len(rows)}
        for contrast, (left, right) in CONTRASTS.items():
            task_delta = {
                task: float(np.mean(scores[(task, left)]))
                - float(np.mean(scores[(task, right)]))
                for task in TASKS
            }
            macro = float(np.mean(list(task_delta.values())))
            for task, value in task_delta.items():
                distributions[(contrast, task)].append(value)
                record[f"{contrast}_{task}_delta"] = repr(value)
            distributions[(contrast, "macro")].append(macro)
            record[f"{contrast}_macro_delta"] = repr(macro)
        rows.append(record)
        for key in absence:
            absence[key].append(multiplicity[index[key[1]]] == 0)
    _require(len(rows) == REPLICATES, "accepted bootstrap count differs")
    summaries: list[dict[str, object]] = []
    for contrast in CONTRASTS:
        for task in (*TASKS, "macro"):
            mean, lower, upper = _interval(distributions[(contrast, task)])
            summaries.append(
                {
                    "protocol": protocol,
                    "contrast": contrast,
                    "level": "protocol_macro"
                    if task == "macro"
                    else "task_repeat_mean",
                    "task": task,
                    "bootstrap_mean_delta": repr(mean),
                    "lower_95": repr(lower),
                    "upper_95": repr(upper),
                    "accepted_replicates": REPLICATES,
                    "attempted_replicates": attempts,
                    "rejected_replicates": rejected,
                }
            )
    influence: list[dict[str, object]] = []
    for (task, group), (count, positive) in sorted(top.items()):
        mask = np.asarray(absence[(task, group)], dtype=bool)
        _require(int(mask.sum()) >= 500, "group absence count differs")
        _, task_lower, task_upper = _interval(
            np.asarray(distributions[("primary", task)])[mask]
        )
        _, macro_lower, macro_upper = _interval(
            np.asarray(distributions[("primary", "macro")])[mask]
        )
        influence.append(
            {
                "protocol": protocol,
                "task": task,
                "group_hash": group,
                "source_row_occurrences": count,
                "positive_occurrences": positive,
                "absent_replicates": int(mask.sum()),
                "task_lower_95": repr(task_lower),
                "task_upper_95": repr(task_upper),
                "protocol_macro_lower_95": repr(macro_lower),
                "protocol_macro_upper_95": repr(macro_upper),
            }
        )
    return (
        rows,
        summaries,
        influence,
        {
            "seed": SEEDS[protocol],
            "groups": len(universe),
            "attempted": attempts,
            "accepted": REPLICATES,
            "rejected": rejected,
        },
    )


def run_inference() -> Path:
    _require(
        not OUTPUT_ROOT.exists() and not BLOCKER_ROOT.exists(),
        "inference output exists",
    )
    start = time.perf_counter()
    revision: str | None = None
    environment: dict[str, str] | None = None
    labels = metrics = 0
    staging: Path | None = None
    try:
        revision = _clean_revision()
        _, target, environment = _verify_inputs()
        raw_metric = _metric()

        def metric(*args: object, **kwargs: object) -> float:
            nonlocal metrics
            value = float(raw_metric(*args, **kwargs))
            metrics += 1
            return value

        def labels_parsed(value: int) -> None:
            nonlocal labels
            labels = value

        cells, conflicts = _load_cells(target, labels_parsed)
        _require(labels == 30038, "label accounting differs")
        point, aggregate = _point(cells, metric)
        _require(metrics == 198, "point metric accounting differs")
        trigger = max(point, key=lambda row: float(row["auprc"]))
        maximum = float(trigger["auprc"])
        if maximum >= 0.95:
            raise StageBForensicStop(trigger, point, aggregate)
        sensitivity = _sensitivity(cells, conflicts, metric)
        _require(metrics == 306, "sensitivity metric accounting differs")
        replicates: list[dict[str, object]] = []
        summaries: list[dict[str, object]] = []
        influence: list[dict[str, object]] = []
        protocols: dict[str, object] = {}
        for protocol in PROTOCOLS:
            a, b, c, d = _bootstrap(protocol, cells, metric)
            replicates.extend(a)
            summaries.extend(b)
            influence.extend(c)
            protocols[protocol] = d
        _require(metrics == 144306, "metric accounting differs")
        by_aggregate = {
            (row["protocol"], row["task"], row["configuration"]): float(row["auprc"])
            for row in aggregate
        }
        official_rule = all(
            sum(
                by_aggregate[(protocol, task, B2)]
                - by_aggregate[(protocol, task, FIXED)]
                > 0
                for task in TASKS
            )
            >= 2
            and min(
                by_aggregate[(protocol, task, B2)]
                - by_aggregate[(protocol, task, FIXED)]
                for task in TASKS
            )
            >= -0.005
            for protocol in PROTOCOLS
        )
        macro_summary = {
            (row["protocol"], row["contrast"]): row
            for row in summaries
            if row["task"] == "macro"
        }
        sensitivity_rule = all(
            float(row["delta"]) > 0
            for row in sensitivity
            if row["level"] == "protocol_macro"
        ) and all(
            sum(
                float(row["delta"]) > 0
                for row in sensitivity
                if row["population"] == population
                and row["protocol"] == protocol
                and row["level"] == "task_repeat_mean"
            )
            >= 2
            and min(
                float(row["delta"])
                for row in sensitivity
                if row["population"] == population
                and row["protocol"] == protocol
                and row["level"] == "task_repeat_mean"
            )
            >= -0.005
            for population in (
                "unique_structure_task_cell",
                "conflict_excluded",
                "low_neighbor_below_0_60",
            )
            for protocol in PROTOCOLS
        )
        gate = {
            "primary_macro_lower_positive_both_protocols": all(
                float(macro_summary[(protocol, "primary")]["lower_95"]) > 0
                for protocol in PROTOCOLS
            ),
            "official_task_direction_rule": official_rule,
            "shuffle_control_lower_positive_both_protocols": all(
                float(macro_summary[(protocol, "shuffle_control")]["lower_95"]) > 0
                for protocol in PROTOCOLS
            ),
            "noise_control_lower_positive_both_protocols": all(
                float(macro_summary[(protocol, "noise_control")]["lower_95"]) > 0
                for protocol in PROTOCOLS
            ),
            "sensitivity_direction_rule": sensitivity_rule,
            "top_group_absence_macro_lower_positive": all(
                float(row["protocol_macro_lower_95"]) > 0 for row in influence
            ),
        }
        gate["gin_keep_gate_passed"] = all(gate.values())
        staging = Path(
            tempfile.mkdtemp(prefix=".stage-b-inference-", dir=OUTPUT_ROOT.parent)
        )
        files = {
            "point_scores.csv": (
                ("cell", "task", "protocol", "repeat", "configuration", "auprc"),
                point,
            ),
            "aggregate_scores.csv": (
                ("protocol", "level", "task", "configuration", "auprc"),
                aggregate,
            ),
            "sensitivity_metrics.csv": (
                (
                    "population",
                    "protocol",
                    "level",
                    "task",
                    "effective_rows",
                    "fixed_auprc",
                    "b2_auprc",
                    "delta",
                ),
                sensitivity,
            ),
            "bootstrap_replicates.csv": (
                (
                    "protocol",
                    "replicate",
                    *[
                        f"{contrast}_{task}_delta"
                        for contrast in CONTRASTS
                        for task in (*TASKS, "macro")
                    ],
                ),
                replicates,
            ),
            "bootstrap_summary.csv": (
                (
                    "protocol",
                    "contrast",
                    "level",
                    "task",
                    "bootstrap_mean_delta",
                    "lower_95",
                    "upper_95",
                    "accepted_replicates",
                    "attempted_replicates",
                    "rejected_replicates",
                ),
                summaries,
            ),
            "group_influence.csv": (
                (
                    "protocol",
                    "task",
                    "group_hash",
                    "source_row_occurrences",
                    "positive_occurrences",
                    "absent_replicates",
                    "task_lower_95",
                    "task_upper_95",
                    "protocol_macro_lower_95",
                    "protocol_macro_upper_95",
                ),
                influence,
            ),
        }
        outputs: dict[str, str] = {}
        for name, (columns, rows) in files.items():
            _write_csv(staging / name, columns, rows)
            outputs[name] = _sha256(staging / name)
        manifest = {
            "schema_version": "cypshift.maplight_gin_stage_b_inference.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "contract_sha256": CONTRACT_SHA256,
            "inputs": {
                "prediction_manifest_sha256": PREDICTION_MANIFEST_SHA256,
                "stage_a_prediction_manifest_sha256": STAGE_A_MANIFEST_SHA256,
                "target_manifest_sha256": TARGET_MANIFEST_SHA256,
                "topology_manifest_sha256": TOPOLOGY_MANIFEST_SHA256,
                "topology_rows_sha256": TOPOLOGY_ROWS_SHA256,
            },
            "outputs": outputs,
            "environment": environment,
            "protocols": protocols,
            "maximum_point_auprc": maximum,
            "forensic_trigger": False,
            "gate": gate,
            "runtime_seconds": time.perf_counter() - start,
            "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**3),
            "accounting": {
                "train_val_scoring_labels_parsed": labels,
                "point_metric_evaluations": 198,
                "sensitivity_metric_evaluations": 108,
                "bootstrap_metric_evaluations": 144000,
                "total_metric_evaluations": metrics,
                "model_fits": 0,
                "predictions_generated": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
                "public_test_family_task_slots_consumed": 0,
                "challenge_assumptions_added": 0,
            },
            "claim_boundary": "Stage B paired grouped shadow inference only; no public-test or OpenADMET challenge claim.",
        }
        (staging / "inference_manifest.json").write_bytes(_json_bytes(manifest))
        _require(_clean_revision() == revision, "source changed during inference")
        _make_readonly(staging)
        staging.rename(OUTPUT_ROOT)
        return OUTPUT_ROOT
    except Exception as error:
        if staging is not None:
            _remove(staging)
        blocker = Path(
            tempfile.mkdtemp(
                prefix=".stage-b-inference-blocker-", dir=BLOCKER_ROOT.parent
            )
        )
        outputs: dict[str, str] = {}
        failure: dict[str, object] = {
            "kind": type(error).__name__,
            "message": str(error),
        }
        if isinstance(error, StageBForensicStop):
            point_path = blocker / "point_scores.csv"
            aggregate_path = blocker / "aggregate_scores.csv"
            _write_csv(
                point_path,
                ("cell", "task", "protocol", "repeat", "configuration", "auprc"),
                error.point,
            )
            _write_csv(
                aggregate_path,
                ("protocol", "level", "task", "configuration", "auprc"),
                error.aggregate,
            )
            outputs = {
                "point_scores.csv": _sha256(point_path),
                "aggregate_scores.csv": _sha256(aggregate_path),
            }
            failure["forensic_trigger"] = error.trigger
        receipt = {
            "schema_version": "cypshift.maplight_gin_stage_b_inference_failure.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "contract_sha256": CONTRACT_SHA256,
            "inputs": {
                "prediction_manifest_sha256": PREDICTION_MANIFEST_SHA256,
                "stage_a_prediction_manifest_sha256": STAGE_A_MANIFEST_SHA256,
                "target_manifest_sha256": TARGET_MANIFEST_SHA256,
                "shadow_rows_sha256": SHADOW_ROWS_SHA256,
                "topology_manifest_sha256": TOPOLOGY_MANIFEST_SHA256,
                "topology_rows_sha256": TOPOLOGY_ROWS_SHA256,
            },
            "environment": environment,
            "failure": failure,
            "outputs": outputs,
            "runtime_seconds": time.perf_counter() - start,
            "accounting": {
                "train_val_scoring_labels_parsed": labels,
                "metric_evaluations_completed": metrics,
                "model_fits": 0,
                "predictions_generated": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
                "public_test_family_task_slots_consumed": 0,
                "challenge_assumptions_added": 0,
            },
        }
        (blocker / "failure_receipt.json").write_bytes(_json_bytes(receipt))
        _make_readonly(blocker)
        blocker.rename(BLOCKER_ROOT)
        raise StageBInferenceError(
            f"inference failed; blocker retained at {BLOCKER_ROOT}"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        output = run_inference()
    except (StageBInferenceError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=os.sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
