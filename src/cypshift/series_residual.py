"""One frozen, fit-free grouped-OOF series-residual experiment."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from typing import Any

from cypshift.metrics import average_precision
from cypshift.native_selection import (
    NativeSelectionError,
    _file_hash,
    _number,
    _read_csv,
    _read_json,
    _write_json,
)

SERIES_RESIDUAL_SCHEMA_VERSION = "cypshift.series_residual_result.v1"
REVIEWED_CONTRACT_SHA256 = (
    "824bff1608c01fbf1d86dc2269a258bd0ec61af298ee450e113460c88e4df4cf"
)
AGGREGATE_RECIPE = (
    "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined with newline "
    "characters, without a trailing newline"
)

PREDICTION_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "inner_fold",
    "scaffold_group_hash",
    "nearest_neighbor_similarity",
    "population",
    "weight",
    "base_prediction",
    "local_prediction",
    "residual",
    "valid_prediction",
    "shuffled_residual_prediction",
    "randomized_family_label_prediction",
    "target",
    "standardized_structure_hash",
)
SCORE_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "comparator",
    "population",
    "fold",
    "metric",
    "value",
    "rows",
    "directional_gain_vs_base",
)
BOOTSTRAP_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "comparator",
    "population",
    "point_gain_vs_base",
    "replicates",
    "lower_95",
    "upper_95",
)

COMPARATORS = (
    "global_only_unweighted_mean",
    "retained_similarity_knn",
    "similarity_shrunk_knn_residual",
    "within_fold_shuffled_residual",
    "within_fold_randomized_family_label",
)
BOOTSTRAP_COMPARATORS = COMPARATORS[1:]
POPULATIONS = (
    "all_grouped_oof_rows",
    "predeclared_analog_supported_rows",
    "remote_abstained_rows",
)


@dataclass(frozen=True, slots=True)
class SeriesResidualResult:
    """Paths and counts for one immutable grouped-OOF result."""

    manifest_path: Path
    decision_path: Path
    retained: bool
    rows: int


@dataclass(frozen=True, slots=True)
class _Row:
    benchmark: str
    task: str
    problem_type: str
    molecule_id: str
    fold: int
    target: float
    structure_hash: str
    scaffold_hash: str
    similarity: float
    base: float
    local: float

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.benchmark, self.task, self.molecule_id)


@dataclass(frozen=True, slots=True)
class _Predictions:
    weight: float
    residual: float
    valid: float
    shuffled: float
    randomized: float


def run_series_residual(
    combination_root: Path,
    research_root: Path,
    contract_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
    expected_contract_sha256: str = REVIEWED_CONTRACT_SHA256,
) -> SeriesResidualResult:
    """Run exactly the reviewed D-022 experiment on grouped OOF artifacts."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. "
            "Series-residual artifacts are immutable."
        )
    if not source_revision.strip():
        raise NativeSelectionError("source revision must not be empty")
    contract_hash = _file_hash(contract_path)
    if contract_hash != expected_contract_sha256:
        raise NativeSelectionError("series-residual contract hash mismatch")
    contract = _read_json(contract_path)
    _verify_contract(contract)

    combination_manifest = _verify_input_root(
        combination_root,
        "combination_manifest.json",
        "combination_oof_predictions.csv",
        _object(contract["inputs"], "native_combinations"),
    )
    research_manifest = _verify_input_root(
        research_root,
        "research_observation_manifest.json",
        "retained_oof_observations.csv",
        _object(contract["inputs"], "research_observations"),
    )

    rows = _load_aligned_rows(combination_root, research_root, contract)
    _verify_topology(rows, _object(contract, "topology_audit"))
    predictions = _construct_predictions(rows, _object(contract, "controls"))
    score_rows, score_values, point_evaluations = _score_rows(rows, predictions)
    bootstrap_rows, intervals, bootstrap_evaluations = _bootstrap_rows(
        rows, predictions, _object(contract, "metrics"), score_values
    )
    decision = _decision(rows, predictions, score_values, intervals)

    output_directory.mkdir(parents=True)
    predictions_path = output_directory / "series_residual_predictions.csv"
    scores_path = output_directory / "series_residual_scores.csv"
    bootstrap_path = output_directory / "series_residual_bootstrap.csv"
    decision_path = output_directory / "series_residual_decision.json"
    _write_csv(predictions_path, PREDICTION_COLUMNS, _prediction_rows(rows, predictions))
    _write_csv(scores_path, SCORE_COLUMNS, score_rows)
    _write_csv(bootstrap_path, BOOTSTRAP_COLUMNS, bootstrap_rows)
    _write_json(decision_path, decision)

    outputs = {
        path.name: _file_hash(path)
        for path in (predictions_path, scores_path, bootstrap_path, decision_path)
    }
    manifest_path = output_directory / "series_residual_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": SERIES_RESIDUAL_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "contract_sha256": contract_hash,
            "combination_manifest_sha256": _file_hash(
                combination_root / "combination_manifest.json"
            ),
            "combination_aggregate_sha256": combination_manifest["aggregate_sha256"],
            "research_manifest_sha256": _file_hash(
                research_root / "research_observation_manifest.json"
            ),
            "research_aggregate_sha256": research_manifest["aggregate_sha256"],
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "grouped_oof_rows": len(rows),
            "point_metric_evaluations": point_evaluations,
            "bootstrap_metric_evaluations": bootstrap_evaluations,
            "bootstrap_replicates": int(contract["metrics"]["paired_bootstrap_replicates"]),
            "residual_candidates": 1,
            "negative_controls": 2,
            "retained": decision["retained"],
            "model_fits": 0,
            "heldout_labels_parsed": 0,
            "heldout_predictions_consumed": 0,
            "heldout_evaluations": 0,
            "new_dependencies": 0,
        },
    )
    return SeriesResidualResult(
        manifest_path=manifest_path,
        decision_path=decision_path,
        retained=bool(decision["retained"]),
        rows=len(rows),
    )


def _verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != "cypshift.series_residual_contract.v2":
        raise NativeSelectionError("unsupported series-residual contract schema")
    candidate = _object(contract, "candidate")
    expected_candidate = {
        "name": "similarity_shrunk_knn_residual",
        "weight": "clip((nearest_neighbor_similarity - 0.5) / 0.5, 0, 1)",
        "prediction": "base_prediction + weight * residual",
        "model_fits": 0,
        "tuned_parameters": 0,
    }
    if any(candidate.get(name) != value for name, value in expected_candidate.items()):
        raise NativeSelectionError("series-residual candidate contract changed")
    join = _object(contract, "join_and_preflight")
    if join.get("unique_key") != ["benchmark", "task", "molecule_id"]:
        raise NativeSelectionError("series-residual join key changed")
    if join.get("required_equal_fields") != [
        "benchmark",
        "task",
        "problem_type",
        "molecule_id",
        "inner_fold",
        "target",
        "standardized_structure_hash",
    ]:
        raise NativeSelectionError("series-residual equality fields changed")
    controls = _object(contract, "controls")
    if (
        controls.get("seed") != 20260809
        or controls.get("permutation_count") != 1
        or controls.get("shuffled_residual_namespace") != "shuffled_residual_v1"
        or controls.get("randomized_family_label_namespace")
        != "randomized_family_label_v1"
    ):
        raise NativeSelectionError("series-residual control contract changed")
    metrics = _object(contract, "metrics")
    if (
        metrics.get("paired_bootstrap_replicates") != 2000
        or metrics.get("paired_bootstrap_seed") != 20260809
        or metrics.get("bootstrap_unit") != "scaffold_group_hash"
        or metrics.get("bootstrap_comparators") != list(BOOTSTRAP_COMPARATORS)
    ):
        raise NativeSelectionError("series-residual metric contract changed")
    boundaries = _object(contract, "boundaries")
    if any(
        boundaries.get(name) != 0
        for name in (
            "heldout_labels_parsed",
            "heldout_predictions_consumed",
            "heldout_evaluations",
            "new_model_fits",
            "new_dependencies",
            "additional_residual_candidates",
        )
    ):
        raise NativeSelectionError("series-residual boundary changed")


def _verify_input_root(
    root: Path,
    manifest_name: str,
    selected_output: str,
    contract_input: Mapping[str, Any],
) -> dict[str, Any]:
    manifest_path = root / manifest_name
    if _file_hash(manifest_path) != contract_input.get("manifest_sha256"):
        raise NativeSelectionError(f"input manifest hash mismatch: {manifest_name}")
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != contract_input.get("schema_version"):
        raise NativeSelectionError(f"input manifest schema mismatch: {manifest_name}")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise NativeSelectionError(f"input manifest outputs invalid: {manifest_name}")
    normalized: dict[str, str] = {}
    for name, expected in outputs.items():
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not isinstance(expected, str)
        ):
            raise NativeSelectionError(f"input manifest output invalid: {manifest_name}")
        if _file_hash(root / name) != expected:
            raise NativeSelectionError(f"input output hash mismatch: {name}")
        normalized[name] = expected
    aggregate = _hash_mapping(normalized)
    if (
        manifest.get("aggregate_sha256") != aggregate
        or contract_input.get("aggregate_sha256") != aggregate
    ):
        raise NativeSelectionError(f"input aggregate mismatch: {manifest_name}")
    if outputs.get(selected_output) != contract_input.get(
        "prediction_sha256", contract_input.get("observation_sha256")
    ):
        raise NativeSelectionError(f"selected input hash mismatch: {selected_output}")
    return manifest


def _load_aligned_rows(
    combination_root: Path,
    research_root: Path,
    contract: Mapping[str, Any],
) -> list[_Row]:
    combination_path = combination_root / "combination_oof_predictions.csv"
    research_path = research_root / "retained_oof_observations.csv"
    combination = [
        row
        for row in _read_csv(combination_path)
        if row.get("candidate") == contract["inputs"]["native_combinations"]["base_candidate"]
    ]
    research = [
        row
        for row in _read_csv(research_path)
        if row.get("family") == contract["inputs"]["research_observations"]["local_family"]
        and row.get("configuration_id")
        == contract["inputs"]["research_observations"]["local_configuration"]
    ]
    join = _object(contract, "join_and_preflight")
    if len(combination) != join.get("expected_base_rows"):
        raise NativeSelectionError("unexpected base OOF row count")
    if len(research) != join.get("expected_local_rows"):
        raise NativeSelectionError("unexpected local OOF row count")
    base_by_key = _unique_rows(combination, combination_path)
    local_by_key = _unique_rows(research, research_path)
    if base_by_key.keys() != local_by_key.keys():
        raise NativeSelectionError("base and local OOF keys differ")

    aligned: list[_Row] = []
    equal_fields = tuple(str(value) for value in join["required_equal_fields"])
    for key in sorted(base_by_key):
        base = base_by_key[key]
        local = local_by_key[key]
        if any(base.get(field) != local.get(field) for field in equal_fields):
            raise NativeSelectionError(f"base and local OOF fields differ: {key}")
        problem_type = _required(base, "problem_type", combination_path)
        target = _finite(base, "target", combination_path)
        base_prediction = _finite(base, "prediction", combination_path)
        local_prediction = _finite(local, "prediction", research_path)
        similarity = _finite(local, "nearest_neighbor_similarity", research_path)
        if problem_type not in {"classification", "regression"}:
            raise NativeSelectionError(f"unsupported problem type: {problem_type}")
        if problem_type == "classification" and target not in {0.0, 1.0}:
            raise NativeSelectionError("classification targets must be binary")
        if not 0.0 <= similarity <= 1.0:
            raise NativeSelectionError("nearest-neighbor similarity must be in [0, 1]")
        fold = _integer(base, "inner_fold", combination_path)
        if fold not in {0, 1, 2, 3}:
            raise NativeSelectionError("inner fold must be 0, 1, 2, or 3")
        aligned.append(
            _Row(
                benchmark=_required(base, "benchmark", combination_path),
                task=_required(base, "task", combination_path),
                problem_type=problem_type,
                molecule_id=_required(base, "molecule_id", combination_path),
                fold=fold,
                target=target,
                structure_hash=_required(
                    base, "standardized_structure_hash", combination_path
                ),
                scaffold_hash=_required(local, "scaffold_group_hash", research_path),
                similarity=similarity,
                base=base_prediction,
                local=local_prediction,
            )
        )
    return sorted(
        aligned, key=lambda row: (row.benchmark, row.task, row.fold, row.molecule_id)
    )


def _unique_rows(
    rows: Sequence[Mapping[str, str]], path: Path
) -> dict[tuple[str, str, str], Mapping[str, str]]:
    result: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in rows:
        key = (
            _required(row, "benchmark", path),
            _required(row, "task", path),
            _required(row, "molecule_id", path),
        )
        if key in result:
            raise NativeSelectionError(f"duplicate OOF key: {key}")
        result[key] = row
    return result


def _verify_topology(rows: Sequence[_Row], topology: Mapping[str, Any]) -> None:
    if len(rows) != topology.get("selection_rows"):
        raise NativeSelectionError("series-residual topology row count mismatch")
    tasks = _object(topology, "task_counts")
    grouped: dict[str, list[_Row]] = defaultdict(list)
    scaffold_folds: dict[tuple[str, str, str], int] = {}
    for row in rows:
        grouped[row.task].append(row)
        scaffold_key = (row.benchmark, row.task, row.scaffold_hash)
        previous = scaffold_folds.setdefault(scaffold_key, row.fold)
        if previous != row.fold:
            raise NativeSelectionError("scaffold group crosses an inner fold")
    if set(grouped) != set(tasks):
        raise NativeSelectionError("series-residual topology tasks mismatch")
    threshold_counts: dict[str, int] = {}
    for task, task_rows in grouped.items():
        expected = _object(tasks, task)
        supported = [row for row in task_rows if row.similarity >= 0.5]
        threshold_counts[task] = sum(row.similarity == 0.5 for row in task_rows)
        actual = {
            "rows": len(task_rows),
            "supported_rows": len(supported),
            "supported_by_fold": [
                sum(row.fold == fold for row in supported) for fold in range(4)
            ],
            "all_scaffold_groups_by_fold": [
                len({row.scaffold_hash for row in task_rows if row.fold == fold})
                for fold in range(4)
            ],
            "supported_scaffold_groups_by_fold": [
                len({row.scaffold_hash for row in supported if row.fold == fold})
                for fold in range(4)
            ],
        }
        if actual != expected:
            raise NativeSelectionError(f"series-residual topology mismatch: {task}")
    if threshold_counts != topology.get("rows_at_exact_threshold"):
        raise NativeSelectionError("series-residual threshold-equality count mismatch")


def _construct_predictions(
    rows: Sequence[_Row], controls: Mapping[str, Any]
) -> dict[tuple[str, str, str], _Predictions]:
    seed = int(controls["seed"])
    residuals = _permuted_values(
        rows,
        lambda row: row.local - row.base,
        str(controls["shuffled_residual_namespace"]),
        seed,
    )
    weights = _permuted_values(
        rows,
        _weight,
        str(controls["randomized_family_label_namespace"]),
        seed,
    )
    result: dict[tuple[str, str, str], _Predictions] = {}
    for row in rows:
        weight = _weight(row)
        residual = row.local - row.base
        result[row.key] = _Predictions(
            weight=weight,
            residual=residual,
            valid=_bounded(row, row.base + weight * residual),
            shuffled=_bounded(row, row.base + weight * residuals[row.key]),
            randomized=_bounded(row, row.base + weights[row.key] * residual),
        )
    return result


def _permuted_values(
    rows: Sequence[_Row],
    value: Callable[[_Row], float],
    namespace: str,
    seed: int,
) -> dict[tuple[str, str, str], float]:
    groups: dict[tuple[str, str, int], list[_Row]] = defaultdict(list)
    for row in rows:
        groups[(row.benchmark, row.task, row.fold)].append(row)
    result: dict[tuple[str, str, str], float] = {}
    for (benchmark, task, fold), group in sorted(groups.items()):
        targets = sorted(group, key=lambda row: row.molecule_id)
        sources = sorted(
            group,
            key=lambda row: (
                sha256(
                    f"{seed}|{namespace}|{benchmark}|{task}|{fold}|{row.molecule_id}".encode()
                ).hexdigest(),
                row.molecule_id,
            ),
        )
        for target, source in zip(targets, sources, strict=True):
            result[target.key] = value(source)
    return result


def _score_rows(
    rows: Sequence[_Row], predictions: Mapping[tuple[str, str, str], _Predictions]
) -> tuple[
    list[dict[str, str]], dict[tuple[str, str, str, str], float], int
]:
    output: list[dict[str, str]] = []
    values: dict[tuple[str, str, str, str], float] = {}
    tasks = _task_rows(rows)
    for (benchmark, task), task_rows in sorted(tasks.items()):
        problem_type = _one_problem_type(task_rows)
        for population in POPULATIONS:
            population_rows = _population_rows(task_rows, population)
            for fold_name, selected in (
                [("all", population_rows)]
                + [
                    (str(fold), [row for row in population_rows if row.fold == fold])
                    for fold in range(4)
                ]
            ):
                if not selected:
                    raise NativeSelectionError("declared score population is empty")
                base_value = _metric(selected, predictions, COMPARATORS[0])
                for comparator in COMPARATORS:
                    current = (
                        base_value
                        if comparator == COMPARATORS[0]
                        else _metric(selected, predictions, comparator)
                    )
                    gain = _gain(problem_type, base_value, current)
                    values[(task, population, fold_name, comparator)] = current
                    output.append(
                        {
                            "benchmark": benchmark,
                            "task": task,
                            "problem_type": problem_type,
                            "comparator": comparator,
                            "population": population,
                            "fold": fold_name,
                            "metric": _metric_name(problem_type),
                            "value": _number(current),
                            "rows": str(len(selected)),
                            "directional_gain_vs_base": _number(gain),
                        }
                    )
    return output, values, len(output)


def _bootstrap_rows(
    rows: Sequence[_Row],
    predictions: Mapping[tuple[str, str, str], _Predictions],
    metrics: Mapping[str, Any],
    point_values: Mapping[tuple[str, str, str, str], float],
) -> tuple[
    list[dict[str, str]], dict[tuple[str, str, str], tuple[float, float]], int
]:
    output: list[dict[str, str]] = []
    intervals: dict[tuple[str, str, str], tuple[float, float]] = {}
    evaluations = 0
    replicates = int(metrics["paired_bootstrap_replicates"])
    seed = int(metrics["paired_bootstrap_seed"])
    for (benchmark, task), task_rows in sorted(_task_rows(rows).items()):
        problem_type = _one_problem_type(task_rows)
        for population in POPULATIONS[:2]:
            selected = _population_rows(task_rows, population)
            groups = _scaffold_groups(selected)
            gains: dict[str, list[float]] = {
                name: [] for name in BOOTSTRAP_COMPARATORS
            }
            for replicate in range(replicates):
                sampled: list[_Row] = []
                for fold in range(4):
                    fold_groups = groups[fold]
                    count = len(fold_groups)
                    if count == 0:
                        raise NativeSelectionError("bootstrap fold has no scaffold group")
                    for draw in range(count):
                        material = (
                            f"{seed}|scaffold_bootstrap_v1|{population}|{benchmark}|"
                            f"{task}|{replicate}|{fold}|{draw}"
                        )
                        index = int.from_bytes(
                            sha256(material.encode()).digest()[:8], "big"
                        ) % count
                        sampled.extend(fold_groups[index])
                base_value = _metric(sampled, predictions, COMPARATORS[0])
                evaluations += 1
                for comparator in BOOTSTRAP_COMPARATORS:
                    current = _metric(sampled, predictions, comparator)
                    evaluations += 1
                    gains[comparator].append(
                        _gain(problem_type, base_value, current)
                    )
            for comparator in BOOTSTRAP_COMPARATORS:
                lower = _percentile(gains[comparator], 0.025)
                upper = _percentile(gains[comparator], 0.975)
                intervals[(task, population, comparator)] = (lower, upper)
                base_point = point_values[(task, population, "all", COMPARATORS[0])]
                current_point = point_values[(task, population, "all", comparator)]
                output.append(
                    {
                        "benchmark": benchmark,
                        "task": task,
                        "problem_type": problem_type,
                        "comparator": comparator,
                        "population": population,
                        "point_gain_vs_base": _number(
                            _gain(problem_type, base_point, current_point)
                        ),
                        "replicates": str(replicates),
                        "lower_95": _number(lower),
                        "upper_95": _number(upper),
                    }
                )
    return output, intervals, evaluations


def _decision(
    rows: Sequence[_Row],
    predictions: Mapping[tuple[str, str, str], _Predictions],
    scores: Mapping[tuple[str, str, str, str], float],
    intervals: Mapping[tuple[str, str, str], tuple[float, float]],
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for (_, task), task_rows in sorted(_task_rows(rows).items()):
        problem_type = _one_problem_type(task_rows)
        valid = COMPARATORS[2]
        full_gain = _score_gain(scores, task, POPULATIONS[0], "all", valid, problem_type)
        supported_gain = _score_gain(
            scores, task, POPULATIONS[1], "all", valid, problem_type
        )
        lower = intervals[(task, POPULATIONS[1], valid)][0]
        positive_folds = sum(
            _score_gain(scores, task, POPULATIONS[0], str(fold), valid, problem_type)
            > 0.0
            for fold in range(4)
        )
        remote_rows = _population_rows(task_rows, POPULATIONS[2])
        remote_predictions_exact = all(
            predictions[row.key].valid == row.base for row in remote_rows
        )
        remote_metric_tie = (
            scores[(task, POPULATIONS[2], "all", valid)]
            == scores[(task, POPULATIONS[2], "all", COMPARATORS[0])]
        )
        controls: dict[str, dict[str, float | bool]] = {}
        for control in COMPARATORS[3:]:
            full = _valid_minus_control(
                scores, task, POPULATIONS[0], valid, control, problem_type
            )
            supported = _valid_minus_control(
                scores, task, POPULATIONS[1], valid, control, problem_type
            )
            controls[control] = {
                "full_gain": full,
                "supported_gain": supported,
                "pass": full > 0.0 and supported > 0.0,
            }
        checks = {
            "full_gain": full_gain,
            "full_gain_pass": full_gain > 0.0,
            "supported_gain": supported_gain,
            "supported_lower_95": lower,
            "supported_gain_pass": supported_gain > 0.0 and lower > 0.0,
            "positive_all_row_folds": positive_folds,
            "fold_consistency_pass": positive_folds >= 3,
            "remote_predictions_exact": remote_predictions_exact,
            "remote_metric_tie": remote_metric_tie,
            "controls": controls,
            "controls_pass": all(bool(value["pass"]) for value in controls.values()),
        }
        retained = all(
            (
                checks["full_gain_pass"],
                checks["supported_gain_pass"],
                checks["fold_consistency_pass"],
                checks["remote_predictions_exact"],
                checks["remote_metric_tie"],
                checks["controls_pass"],
            )
        )
        tasks.append(
            {
                "benchmark": task_rows[0].benchmark,
                "task": task,
                "problem_type": problem_type,
                "checks": checks,
                "retained": retained,
            }
        )
    return {
        "schema_version": SERIES_RESIDUAL_SCHEMA_VERSION,
        "candidate": COMPARATORS[2],
        "retention_rule": "all predeclared checks must pass on all four tasks",
        "tasks": tasks,
        "retained": all(bool(task["retained"]) for task in tasks),
        "model_fits": 0,
        "heldout_labels_parsed": 0,
        "heldout_predictions_consumed": 0,
        "heldout_evaluations": 0,
    }


def _prediction_rows(
    rows: Sequence[_Row], predictions: Mapping[tuple[str, str, str], _Predictions]
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        values = predictions[row.key]
        output.append(
            {
                "benchmark": row.benchmark,
                "task": row.task,
                "problem_type": row.problem_type,
                "molecule_id": row.molecule_id,
                "inner_fold": str(row.fold),
                "scaffold_group_hash": row.scaffold_hash,
                "nearest_neighbor_similarity": _number(row.similarity),
                "population": (
                    "analog_supported" if row.similarity >= 0.5 else "remote_abstained"
                ),
                "weight": _number(values.weight),
                "base_prediction": _number(row.base),
                "local_prediction": _number(row.local),
                "residual": _number(values.residual),
                "valid_prediction": _number(values.valid),
                "shuffled_residual_prediction": _number(values.shuffled),
                "randomized_family_label_prediction": _number(values.randomized),
                "target": _number(row.target),
                "standardized_structure_hash": row.structure_hash,
            }
        )
    return output


def _task_rows(rows: Sequence[_Row]) -> dict[tuple[str, str], list[_Row]]:
    result: dict[tuple[str, str], list[_Row]] = defaultdict(list)
    for row in rows:
        result[(row.benchmark, row.task)].append(row)
    return result


def _population_rows(rows: Sequence[_Row], population: str) -> list[_Row]:
    if population == POPULATIONS[0]:
        return list(rows)
    if population == POPULATIONS[1]:
        return [row for row in rows if row.similarity >= 0.5]
    if population == POPULATIONS[2]:
        return [row for row in rows if row.similarity < 0.5]
    raise NativeSelectionError(f"unknown series-residual population: {population}")


def _scaffold_groups(rows: Sequence[_Row]) -> dict[int, list[list[_Row]]]:
    by_fold: dict[int, dict[str, list[_Row]]] = {
        fold: defaultdict(list) for fold in range(4)
    }
    for row in rows:
        by_fold[row.fold][row.scaffold_hash].append(row)
    return {
        fold: [
            sorted(groups[name], key=lambda row: row.molecule_id)
            for name in sorted(groups)
        ]
        for fold, groups in by_fold.items()
    }


def _metric(
    rows: Sequence[_Row],
    predictions: Mapping[tuple[str, str, str], _Predictions],
    comparator: str,
) -> float:
    values = [_prediction(row, predictions[row.key], comparator) for row in rows]
    problem_type = _one_problem_type(rows)
    if problem_type == "classification":
        return average_precision([int(row.target) for row in rows], values)
    return sum(abs(row.target - value) for row, value in zip(rows, values, strict=True)) / len(rows)


def _prediction(row: _Row, values: _Predictions, comparator: str) -> float:
    if comparator == COMPARATORS[0]:
        return row.base
    if comparator == COMPARATORS[1]:
        return row.local
    if comparator == COMPARATORS[2]:
        return values.valid
    if comparator == COMPARATORS[3]:
        return values.shuffled
    if comparator == COMPARATORS[4]:
        return values.randomized
    raise NativeSelectionError(f"unknown series-residual comparator: {comparator}")


def _score_gain(
    scores: Mapping[tuple[str, str, str, str], float],
    task: str,
    population: str,
    fold: str,
    comparator: str,
    problem_type: str,
) -> float:
    base = scores[(task, population, fold, COMPARATORS[0])]
    current = scores[(task, population, fold, comparator)]
    return _gain(problem_type, base, current)


def _valid_minus_control(
    scores: Mapping[tuple[str, str, str, str], float],
    task: str,
    population: str,
    valid: str,
    control: str,
    problem_type: str,
) -> float:
    valid_value = scores[(task, population, "all", valid)]
    control_value = scores[(task, population, "all", control)]
    return (
        valid_value - control_value
        if problem_type == "classification"
        else control_value - valid_value
    )


def _gain(problem_type: str, base: float, comparator: float) -> float:
    return comparator - base if problem_type == "classification" else base - comparator


def _metric_name(problem_type: str) -> str:
    return "average_precision" if problem_type == "classification" else "mean_absolute_error"


def _one_problem_type(rows: Sequence[_Row]) -> str:
    values = {row.problem_type for row in rows}
    if len(values) != 1:
        raise NativeSelectionError("task contains mixed problem types")
    return next(iter(values))


def _weight(row: _Row) -> float:
    return min(1.0, max(0.0, (row.similarity - 0.5) / 0.5))


def _bounded(row: _Row, value: float) -> float:
    if row.problem_type == "classification":
        return min(1.0, max(0.0, value))
    return value


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _object(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise NativeSelectionError(f"series-residual contract field {key!r} is invalid")
    return result


def _required(row: Mapping[str, str], field: str, path: Path) -> str:
    value = row.get(field)
    if not value:
        raise NativeSelectionError(f"{path} requires nonempty field {field!r}")
    return value


def _finite(row: Mapping[str, str], field: str, path: Path) -> float:
    try:
        value = float(_required(row, field, path))
    except ValueError as exc:
        raise NativeSelectionError(f"{path} field {field!r} must be numeric") from exc
    if not math.isfinite(value):
        raise NativeSelectionError(f"{path} field {field!r} must be finite")
    return value


def _integer(row: Mapping[str, str], field: str, path: Path) -> int:
    try:
        return int(_required(row, field, path))
    except ValueError as exc:
        raise NativeSelectionError(f"{path} field {field!r} must be an integer") from exc


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _hash_mapping(values: Mapping[str, str]) -> str:
    material = "\n".join(f"{name}={values[name]}" for name in sorted(values))
    return sha256(material.encode()).hexdigest()


__all__ = [
    "REVIEWED_CONTRACT_SHA256",
    "SERIES_RESIDUAL_SCHEMA_VERSION",
    "SeriesResidualResult",
    "run_series_residual",
]
