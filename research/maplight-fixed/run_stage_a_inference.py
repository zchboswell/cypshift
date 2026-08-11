"""Run the frozen paired Stage A uncertainty and sensitivity analyses."""

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
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import run_stage_a_catboost as stage
import score_stage_a_predictions as point
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()
POINT_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-point-scores-v1"
POINT_MANIFEST_PATH = POINT_ROOT / "score_manifest.json"
TOPOLOGY_ROOT = ROOT / "artifacts/benchmarks/tdc-cyp-shadow-topology-v1"
TOPOLOGY_MANIFEST_PATH = TOPOLOGY_ROOT / "topology_manifest.json"
TOPOLOGY_ROWS_PATH = TOPOLOGY_ROOT / "validation_topology.csv"
OUTPUT_ROOT = ROOT / "artifacts/benchmarks/maplight-fixed-stage-a-inference-v1"
BLOCKER_ROOT = ROOT / "artifacts/blockers/maplight-fixed-stage-a-inference-v1-blocker"

POINT_MANIFEST_SHA256 = (
    "3ca372e9a1b06b9560ff0c076c66e55f1cff347c3030fcafaf9f00544990f17a"
)
TOPOLOGY_MANIFEST_SHA256 = (
    "cf4d4bb759d93fea9d4857dd21fac8758c559bb37fa3c6cee87973f3fe6bfd77"
)
TOPOLOGY_ROWS_SHA256 = (
    "0f575a2d9c230db3e83026f44c2a3f17cdf2fe942d9eb167f487aa3d892d0c63"
)
R1 = "r1_binary_morgan_catboost_seed_1"
R5 = "r5_maplight_fixed_catboost_seed_1"
ACCEPTED_REPLICATES = 2000
MAXIMUM_ATTEMPTS = 20000
SEEDS = {"scaffold": 20260813, "community": 20260814}
TASKS = stage.TASKS
PROTOCOLS = stage.PROTOCOLS

SENSITIVITY_COLUMNS = (
    "population",
    "protocol",
    "level",
    "task",
    "cells",
    "effective_rows",
    "r1_auprc",
    "r5_auprc",
    "delta",
)
REPLICATE_COLUMNS = (
    "protocol",
    "replicate",
    "cyp2c9_delta",
    "cyp2d6_delta",
    "cyp3a4_delta",
    "macro_delta",
)
SUMMARY_COLUMNS = (
    "protocol",
    "level",
    "task",
    "point_delta",
    "bootstrap_mean_delta",
    "lower_95",
    "upper_95",
    "accepted_replicates",
    "attempted_replicates",
    "rejected_replicates",
)
INFLUENCE_COLUMNS = (
    "protocol",
    "task",
    "group_hash",
    "source_row_occurrences",
    "positive_occurrences",
    "prevalence",
    "absent_replicates",
    "task_lower_95",
    "task_upper_95",
    "protocol_macro_lower_95",
    "protocol_macro_upper_95",
)


class StageAInferenceError(RuntimeError):
    """Fail-closed Stage A inference error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StageAInferenceError(message)


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


def _validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(
        _sha256(POINT_MANIFEST_PATH) == POINT_MANIFEST_SHA256, "point manifest differs"
    )
    _require(
        _sha256(TOPOLOGY_MANIFEST_PATH) == TOPOLOGY_MANIFEST_SHA256,
        "topology manifest differs",
    )
    _require(
        _sha256(TOPOLOGY_ROWS_PATH) == TOPOLOGY_ROWS_SHA256, "topology rows differ"
    )
    for root in (POINT_ROOT, TOPOLOGY_ROOT, point.PREDICTION_ROOT, point.TARGET_ROOT):
        _require(root.exists() and _readonly(root), f"input root is writable: {root}")
    point_manifest = _json(POINT_MANIFEST_PATH)
    _require(
        point_manifest["accounting"]["point_metric_evaluations"] == 180,
        "point metric count differs",
    )
    _require(
        point_manifest["accounting"]["bootstrap_metric_evaluations"] == 0,
        "bootstrap chronology differs",
    )
    _, target = point._verify_predictions()
    return point_manifest, target


def _average_precision() -> Callable[..., float]:
    module = __import__("sklearn.metrics", fromlist=["average_precision_score"])
    return cast(Callable[..., float], module.average_precision_score)


def _weighted_metric_fixture(metric: Callable[..., float]) -> None:
    y = np.asarray([0, 1, 0, 1], dtype=np.int8)
    score = np.asarray([0.2, 0.7, 0.7, 0.9], dtype=np.float64)
    weight = np.asarray([2, 3, 1, 2], dtype=np.int64)
    weighted = float(metric(y, score, sample_weight=weight))
    expanded = float(metric(np.repeat(y, weight), np.repeat(score, weight)))
    _require(weighted == expanded, "weighted AUPRC fixture differs")


def _load_cells(
    target: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    scoring = target["scoring_targets"]
    scoring_path = point.TARGET_ROOT / scoring["path"]
    _require(
        _sha256(scoring_path) == point.SCORING_TARGET_SHA256, "scoring target differs"
    )
    target_rows = _read_csv(scoring_path)
    shadow_rows = _read_csv(point.SHADOW_ROWS_PATH)
    _require(len(target_rows) == len(shadow_rows) == 30038, "source row count differs")
    shadow_by_id = {row["molecule_id"]: row for row in shadow_rows}
    _require(len(shadow_by_id) == len(shadow_rows), "shadow identities differ")
    target_by_key = {
        (row["task"], row["molecule_id"], row["source_row"]): int(row["target"])
        for row in target_rows
    }
    labels_by_cell: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in target_rows:
        structure_hash = shadow_by_id[row["molecule_id"]]["standardized_structure_hash"]
        labels_by_cell[(row["task"], structure_hash)].add(int(row["target"]))
    conflicts = {key for key, labels in labels_by_cell.items() if len(labels) > 1}
    _require(len(conflicts) == 11, "conflicting structure-task count differs")
    topology = {
        (
            row["task"],
            row["protocol"],
            int(row["repeat"]),
            row["standardized_structure_hash"],
        ): row
        for row in _read_csv(TOPOLOGY_ROWS_PATH)
    }
    _require(len(topology) == 35963, "topology identity count differs")
    cells: list[dict[str, Any]] = []
    for cell in sorted(target["cells"]):
        task, protocol, repeat_text = cell.split("__")
        repeat = int(repeat_text.removeprefix("repeat_"))
        predictions = _read_csv(
            point.PREDICTION_ROOT / "cells" / cell / "predictions.csv"
        )
        y: list[int] = []
        structures: list[str] = []
        groups: list[str] = []
        similarities: list[float] = []
        for row in predictions:
            shadow = shadow_by_id[row["molecule_id"]]
            structure_hash = shadow["standardized_structure_hash"]
            topology_row = topology[(task, protocol, repeat, structure_hash)]
            y.append(target_by_key[(task, row["molecule_id"], row["source_row"])])
            structures.append(structure_hash)
            groups.append(topology_row["group_hash"])
            similarities.append(float(topology_row["max_train_tanimoto"]))
        cells.append(
            {
                "cell": cell,
                "task": task,
                "protocol": protocol,
                "repeat": repeat,
                "y": np.asarray(y, dtype=np.int8),
                "r1": np.asarray(
                    [float(row[R1]) for row in predictions], dtype=np.float64
                ),
                "r5": np.asarray(
                    [float(row[R5]) for row in predictions], dtype=np.float64
                ),
                "structures": np.asarray(structures),
                "groups": np.asarray(groups),
                "similarities": np.asarray(similarities, dtype=np.float64),
            }
        )
    return cells, conflicts


def _population_weight(
    cell: Mapping[str, Any], population: str, conflicts: set[tuple[str, str]]
) -> NDArray[np.float64]:
    rows = len(cell["y"])
    if population == "official_row_weighted":
        return np.ones(rows, dtype=np.float64)
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
    raise StageAInferenceError(f"unknown population: {population}")


def _score_populations(
    cells: Sequence[Mapping[str, Any]],
    conflicts: set[tuple[str, str]],
    metric: Callable[..., float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    populations = (
        "official_row_weighted",
        "unique_structure_task_cell",
        "conflict_excluded",
        "low_neighbor_below_0_60",
    )
    for population in populations:
        task_scores: dict[tuple[str, str], list[tuple[float, float, float]]] = (
            defaultdict(list)
        )
        for cell in cells:
            weight = _population_weight(cell, population, conflicts)
            y = cell["y"]
            _require(
                float(weight[y == 1].sum()) > 0 and float(weight[y == 0].sum()) > 0,
                "sensitivity class support differs",
            )
            r1 = float(metric(y, cell["r1"], sample_weight=weight))
            r5 = float(metric(y, cell["r5"], sample_weight=weight))
            task_scores[(cell["protocol"], cell["task"])].append(
                (r1, r5, float(weight.sum()))
            )
        protocol_scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for (protocol, task), task_values in sorted(task_scores.items()):
            _require(len(task_values) == 3, "sensitivity repeat count differs")
            r1 = float(np.mean([value[0] for value in task_values]))
            r5 = float(np.mean([value[1] for value in task_values]))
            rows.append(
                {
                    "population": population,
                    "protocol": protocol,
                    "level": "task_repeat_mean",
                    "task": task,
                    "cells": 3,
                    "effective_rows": repr(
                        float(sum(value[2] for value in task_values))
                    ),
                    "r1_auprc": repr(r1),
                    "r5_auprc": repr(r5),
                    "delta": repr(r5 - r1),
                }
            )
            protocol_scores[protocol].append((r1, r5))
        for protocol, protocol_values in sorted(protocol_scores.items()):
            _require(len(protocol_values) == 3, "sensitivity task count differs")
            r1 = float(np.mean([value[0] for value in protocol_values]))
            r5 = float(np.mean([value[1] for value in protocol_values]))
            rows.append(
                {
                    "population": population,
                    "protocol": protocol,
                    "level": "protocol_macro",
                    "task": "macro",
                    "cells": 9,
                    "effective_rows": repr(
                        float(
                            sum(
                                float(cast(str, row["effective_rows"]))
                                for row in rows
                                if row["population"] == population
                                and row["protocol"] == protocol
                                and row["level"] == "task_repeat_mean"
                            )
                        )
                    ),
                    "r1_auprc": repr(r1),
                    "r5_auprc": repr(r5),
                    "delta": repr(r5 - r1),
                }
            )
    return rows


def _interval(values: NDArray[np.float64]) -> tuple[float, float, float]:
    _require(len(values) > 0, "empty interval population")
    lower, upper = np.quantile(values, [0.025, 0.975], method="linear")
    return float(np.mean(values)), float(lower), float(upper)


def _bootstrap_protocol(
    protocol: str,
    cells: Sequence[Mapping[str, Any]],
    metric: Callable[..., float],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    protocol_cells = [cell for cell in cells if cell["protocol"] == protocol]
    _require(len(protocol_cells) == 9, "protocol cell count differs")
    group_column = f"{protocol}_group_hash"
    universe = sorted({row[group_column] for row in _read_csv(point.SHADOW_ROWS_PATH)})
    expected_groups = 9114 if protocol == "scaffold" else 9902
    _require(len(universe) == expected_groups, "global group universe differs")
    group_index = {value: index for index, value in enumerate(universe)}
    cell_indices = [
        np.asarray([group_index[value] for value in cell["groups"]], dtype=np.int64)
        for cell in protocol_cells
    ]
    top_groups: dict[tuple[str, str], tuple[int, int]] = {}
    for task in TASKS:
        counter: Counter[str] = Counter()
        positives: Counter[str] = Counter()
        for cell in protocol_cells:
            if cell["task"] != task:
                continue
            for group, label in zip(cell["groups"], cell["y"], strict=True):
                counter[str(group)] += 1
                positives[str(group)] += int(label)
        selected = sorted(counter, key=lambda value: (-counter[value], value))[:10]
        for group in selected:
            top_groups[(task, group)] = (counter[group], positives[group])
    rng = np.random.Generator(np.random.PCG64(SEEDS[protocol]))
    replicate_rows: list[dict[str, object]] = []
    task_distributions: dict[str, list[float]] = {task: [] for task in TASKS}
    macro_distribution: list[float] = []
    absence: dict[tuple[str, str], list[bool]] = {key: [] for key in top_groups}
    attempts = 0
    rejected = 0
    while len(replicate_rows) < ACCEPTED_REPLICATES and attempts < MAXIMUM_ATTEMPTS:
        attempts += 1
        sampled = rng.choice(len(universe), size=len(universe), replace=True)
        multiplicity = np.bincount(sampled, minlength=len(universe)).astype(np.int64)
        weights = [multiplicity[index] for index in cell_indices]
        if any(
            int(weight[cell["y"] == 1].sum()) == 0
            or int(weight[cell["y"] == 0].sum()) == 0
            for cell, weight in zip(protocol_cells, weights, strict=True)
        ):
            rejected += 1
            continue
        cell_deltas: dict[str, list[float]] = defaultdict(list)
        for cell, weight in zip(protocol_cells, weights, strict=True):
            r1 = float(metric(cell["y"], cell["r1"], sample_weight=weight))
            r5 = float(metric(cell["y"], cell["r5"], sample_weight=weight))
            cell_deltas[cell["task"]].append(r5 - r1)
        task_delta = {
            task: float(np.mean(cell_deltas[task], dtype=np.float64)) for task in TASKS
        }
        macro = float(np.mean(list(task_delta.values()), dtype=np.float64))
        replicate_rows.append(
            {
                "protocol": protocol,
                "replicate": len(replicate_rows),
                "cyp2c9_delta": repr(task_delta["cyp2c9_veith"]),
                "cyp2d6_delta": repr(task_delta["cyp2d6_veith"]),
                "cyp3a4_delta": repr(task_delta["cyp3a4_veith"]),
                "macro_delta": repr(macro),
            }
        )
        for task in TASKS:
            task_distributions[task].append(task_delta[task])
        macro_distribution.append(macro)
        for key in absence:
            absence[key].append(multiplicity[group_index[key[1]]] == 0)
    _require(
        len(replicate_rows) == ACCEPTED_REPLICATES, "accepted bootstrap count differs"
    )
    official_task: dict[str, list[float]] = defaultdict(list)
    for cell in protocol_cells:
        official_task[cell["task"]].append(
            float(metric(cell["y"], cell["r5"])) - float(metric(cell["y"], cell["r1"]))
        )
    official = {
        task: float(np.mean(values, dtype=np.float64))
        for task, values in official_task.items()
    }
    official_macro = float(np.mean(list(official.values()), dtype=np.float64))
    summaries: list[dict[str, object]] = []
    for task in TASKS:
        distribution = np.asarray(task_distributions[task], dtype=np.float64)
        mean, lower, upper = _interval(distribution)
        summaries.append(
            {
                "protocol": protocol,
                "level": "task_repeat_mean",
                "task": task,
                "point_delta": repr(official[task]),
                "bootstrap_mean_delta": repr(mean),
                "lower_95": repr(lower),
                "upper_95": repr(upper),
                "accepted_replicates": ACCEPTED_REPLICATES,
                "attempted_replicates": attempts,
                "rejected_replicates": rejected,
            }
        )
    macro_array = np.asarray(macro_distribution, dtype=np.float64)
    mean, lower, upper = _interval(macro_array)
    summaries.append(
        {
            "protocol": protocol,
            "level": "protocol_macro",
            "task": "macro",
            "point_delta": repr(official_macro),
            "bootstrap_mean_delta": repr(mean),
            "lower_95": repr(lower),
            "upper_95": repr(upper),
            "accepted_replicates": ACCEPTED_REPLICATES,
            "attempted_replicates": attempts,
            "rejected_replicates": rejected,
        }
    )
    influence: list[dict[str, object]] = []
    for (task, group), (row_count, positive) in sorted(top_groups.items()):
        mask = np.asarray(absence[(task, group)], dtype=bool)
        _require(int(mask.sum()) >= 500, "absent-group replicate count differs")
        _, task_lower, task_upper = _interval(
            np.asarray(task_distributions[task], dtype=np.float64)[mask]
        )
        _, macro_lower, macro_upper = _interval(macro_array[mask])
        influence.append(
            {
                "protocol": protocol,
                "task": task,
                "group_hash": group,
                "source_row_occurrences": row_count,
                "positive_occurrences": positive,
                "prevalence": repr(positive / row_count),
                "absent_replicates": int(mask.sum()),
                "task_lower_95": repr(task_lower),
                "task_upper_95": repr(task_upper),
                "protocol_macro_lower_95": repr(macro_lower),
                "protocol_macro_upper_95": repr(macro_upper),
            }
        )
    return (
        replicate_rows,
        summaries,
        influence,
        {
            "protocol": protocol,
            "seed": SEEDS[protocol],
            "group_universe": len(universe),
            "attempted": attempts,
            "accepted": ACCEPTED_REPLICATES,
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
    metric_calls = 0
    staging: Path | None = None
    try:
        revision = _clean_revision()
        point_manifest, target = _validate_inputs()
        metric = _average_precision()
        _weighted_metric_fixture(metric)
        metric_calls = 2
        cells, conflicts = _load_cells(target)
        sensitivity = _score_populations(cells, conflicts, metric)
        metric_calls += 4 * 18 * 2
        for protocol in PROTOCOLS:
            official_macro = next(
                row
                for row in sensitivity
                if row["population"] == "official_row_weighted"
                and row["protocol"] == protocol
                and row["level"] == "protocol_macro"
            )
            _require(
                float(cast(str, official_macro["delta"]))
                == point_manifest["primary_point_summary"][protocol][
                    "r5_seed_1_minus_r1_seed_1"
                ],
                "point-result continuity differs",
            )
        replicates: list[dict[str, object]] = []
        summaries: list[dict[str, object]] = []
        influence: list[dict[str, object]] = []
        protocols: dict[str, object] = {}
        for protocol in PROTOCOLS:
            protocol_replicates, protocol_summaries, protocol_influence, accounting = (
                _bootstrap_protocol(protocol, cells, metric)
            )
            replicates.extend(protocol_replicates)
            summaries.extend(protocol_summaries)
            influence.extend(protocol_influence)
            protocols[protocol] = accounting
            metric_calls += ACCEPTED_REPLICATES * 9 * 2 + 9 * 2
        _require(metric_calls == 72182, "metric accounting differs")
        macro_summary = [row for row in summaries if row["level"] == "protocol_macro"]
        sensitivity_macro = [
            row for row in sensitivity if row["level"] == "protocol_macro"
        ]
        sensitivity_task_rule = True
        for population in (
            "unique_structure_task_cell",
            "conflict_excluded",
            "low_neighbor_below_0_60",
        ):
            for protocol in PROTOCOLS:
                deltas = [
                    float(cast(str, row["delta"]))
                    for row in sensitivity
                    if row["population"] == population
                    and row["protocol"] == protocol
                    and row["level"] == "task_repeat_mean"
                ]
                sensitivity_task_rule = sensitivity_task_rule and (
                    len(deltas) == 3
                    and sum(delta > 0 for delta in deltas) >= 2
                    and min(deltas) >= -0.005
                )
        gate = {
            "macro_lower_bound_positive_both_protocols": all(
                float(cast(str, row["lower_95"])) > 0 for row in macro_summary
            ),
            "all_task_point_deltas_positive_both_protocols": all(
                float(cast(str, row["delta"])) > 0
                for row in sensitivity
                if row["population"] == "official_row_weighted"
                and row["level"] == "task_repeat_mean"
            ),
            "sensitivity_macro_deltas_positive": all(
                float(cast(str, row["delta"])) > 0 for row in sensitivity_macro
            ),
            "sensitivity_task_direction_rule": sensitivity_task_rule,
            "top_group_absence_macro_lower_bound_positive": all(
                float(cast(str, row["protocol_macro_lower_95"])) > 0
                for row in influence
            ),
        }
        gate["representation_value_gate_passed"] = all(gate.values())
        staging = Path(
            tempfile.mkdtemp(prefix=".stage-a-inference-", dir=OUTPUT_ROOT.parent)
        )
        paths = {
            "sensitivity_metrics.csv": (SENSITIVITY_COLUMNS, sensitivity),
            "bootstrap_replicates.csv": (REPLICATE_COLUMNS, replicates),
            "bootstrap_summary.csv": (SUMMARY_COLUMNS, summaries),
            "group_influence.csv": (INFLUENCE_COLUMNS, influence),
        }
        outputs = {}
        for name, (columns, rows) in paths.items():
            _write_csv(staging / name, columns, rows)
            outputs[name] = _sha256(staging / name)
        runtime = time.perf_counter() - start
        manifest = {
            "schema_version": "cypshift.maplight_stage_a_inference.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "inputs": {
                "point_manifest_sha256": POINT_MANIFEST_SHA256,
                "topology_manifest_sha256": TOPOLOGY_MANIFEST_SHA256,
                "topology_rows_sha256": TOPOLOGY_ROWS_SHA256,
            },
            "outputs": outputs,
            "protocols": protocols,
            "gate": gate,
            "runtime_seconds": runtime,
            "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**3),
            "accounting": {
                "train_val_scoring_labels_parsed": 30038,
                "synthetic_metric_evaluations": 2,
                "point_metric_evaluations_recomputed_for_sensitivity": 144,
                "bootstrap_metric_evaluations": 72000,
                "bootstrap_point_reference_metric_evaluations": 36,
                "total_metric_evaluations": metric_calls,
                "model_fits": 0,
                "predictions_generated": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
                "gin_weight_bytes_downloaded": 0,
                "challenge_assumptions_added": 0,
            },
            "claim_boundary": "Paired grouped shadow inference for R5 seed 1 versus R1 seed 1 only; no MapLight+GIN superiority, public-test, or challenge claim.",
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
                prefix=".stage-a-inference-blocker-", dir=BLOCKER_ROOT.parent
            )
        )
        receipt = {
            "schema_version": "cypshift.maplight_stage_a_inference_failure.v1",
            "source_revision": revision,
            "implementation_sha256": _sha256(SCRIPT_PATH),
            "failure": {"kind": type(error).__name__, "message": str(error)},
            "runtime_seconds": time.perf_counter() - start,
            "accounting": {
                "metric_evaluations_completed": metric_calls,
                "model_fits": 0,
                "predictions_generated": 0,
                "public_test_rows_used": 0,
                "public_test_labels_parsed": 0,
            },
        }
        (blocker / "failure_receipt.json").write_bytes(_json_bytes(receipt))
        _make_readonly(blocker)
        blocker.rename(BLOCKER_ROOT)
        raise StageAInferenceError(
            f"inference failed; blocker retained at {BLOCKER_ROOT}"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        output = run_inference()
    except (StageAInferenceError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
