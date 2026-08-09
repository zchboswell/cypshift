"""Frozen OOF-only native combinations and random-optimism analysis."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module, metadata
from pathlib import Path
from statistics import median
from typing import Any

from cypshift.native_evaluation import (
    _retained_configurations,
    _verify_prediction_inputs,
    _verify_selection_receipt,
)
from cypshift.native_selection import (
    FAMILIES,
    SEED,
    STOCHASTIC_SEEDS,
    NativeSelectionError,
    SelectionDataset,
    _file_hash,
    _fingerprints,
    _load_octant_selection,
    _load_tdc_selections,
    _mean_prediction_sets,
    _number,
    _oof_extra_trees,
    _oof_knn,
    _oof_linear,
    _oof_prior,
    _primary_direction,
    _primary_metric,
    _primary_score,
    _read_csv,
    _write_json,
)

COMBINATION_SCHEMA_VERSION = "cypshift.native_combinations.v2"
COMBINATION_CANDIDATES = (
    "best_single",
    "unweighted_mean",
    "median",
    "nonnegative_linear_stack",
)
STACK_MINIMUM_GAIN = {"classification": 0.005, "regression": 0.01}
AGGREGATE_RECIPE = (
    "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined with newline "
    "characters, without a trailing newline"
)

COMBINATION_PREDICTION_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "inner_fold",
    "candidate",
    "prediction",
    "target",
    "standardized_structure_hash",
)
COMBINATION_SCORE_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "candidate",
    "primary_metric",
    "direction",
    "value",
    "rows",
    "retained",
    "retention_reason",
)
STACK_WEIGHT_COLUMNS = (
    "benchmark",
    "task",
    "outer_meta_fold",
    *FAMILIES,
    "fallback_equal_weights",
)
RANDOM_ASSIGNMENT_COLUMNS = (
    "benchmark",
    "task",
    "molecule_id",
    "standardized_structure_hash",
    "random_fold",
)
RANDOM_PREDICTION_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "random_fold",
    "family",
    "prediction",
    "target",
    "standardized_structure_hash",
)
OPTIMISM_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "family",
    "primary_metric",
    "grouped_value",
    "random_value",
    "optimism",
    "interpretation",
)


@dataclass(frozen=True, slots=True)
class CombinationResult:
    """Paths and counts for one immutable OOF-only combination run."""

    manifest_path: Path
    retained_path: Path
    combination_rows: int
    model_fits: int


def run_native_combinations(
    prediction_inputs: Path,
    selection_root: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> CombinationResult:
    """Run the frozen D-019 analysis without opening held-out labels."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. "
            "Combination artifacts are immutable."
        )
    if not source_revision.strip():
        raise NativeSelectionError("source revision must not be empty")
    input_manifest = _verify_prediction_inputs(prediction_inputs)
    verified_inputs = input_manifest["source_input_hashes"]
    selection_manifest, retained_models = _verify_selection_receipt(
        selection_root, verified_inputs
    )
    datasets = [
        _load_octant_selection(
            prediction_inputs / "octant",
            prediction_inputs / "octant" / "grouped_split.csv",
        ),
        *_load_tdc_selections(
            prediction_inputs / "tdc",
            prediction_inputs / "tdc" / "inner_folds.csv",
        ),
    ]
    configurations = _retained_configurations(retained_models)
    base_rows = _read_csv(selection_root / "retained_oof_predictions.csv")

    output_directory.mkdir(parents=True)
    combination_path = output_directory / "combination_oof_predictions.csv"
    scores_path = output_directory / "combination_scores.csv"
    weights_path = output_directory / "nested_stack_weights.csv"
    retained_path = output_directory / "retained_combinations.json"
    random_assignment_path = output_directory / "random_fold_assignments.csv"
    random_prediction_path = output_directory / "random_oof_predictions.csv"
    optimism_path = output_directory / "random_optimism.csv"

    score_rows: list[dict[str, str]] = []
    weight_rows: list[dict[str, str]] = []
    retained_datasets: list[dict[str, Any]] = []
    random_assignment_rows: list[dict[str, str]] = []
    random_prediction_rows: list[dict[str, str]] = []
    optimism_rows: list[dict[str, str]] = []
    combination_rows = 0
    model_fits = 0
    with combination_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=COMBINATION_PREDICTION_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for dataset in datasets:
            key = (dataset.benchmark, dataset.task)
            base = _aligned_base_predictions(dataset, base_rows)
            candidates, nested_weights, nested_fits = _combination_candidates(
                dataset, base, configurations[key]
            )
            model_fits += nested_fits
            scores = {
                name: _primary_score(dataset, values)
                for name, values in candidates.items()
            }
            retained, reason = _retained_candidate(dataset, scores)
            final_weights, equal_fallback = _fit_nonnegative_weights(
                _matrix_rows(base, range(len(dataset.molecule_ids))),
                dataset.targets,
            )
            retained_datasets.append(
                {
                    "benchmark": dataset.benchmark,
                    "task": dataset.task,
                    "problem_type": dataset.problem_type,
                    "retained_candidate": retained,
                    "retention_reason": reason,
                    "best_single_family": _best_single_family(dataset, base),
                    "candidate_scores": scores,
                    "final_stack_weights": dict(zip(FAMILIES, final_weights, strict=True)),
                    "final_stack_equal_weight_fallback": equal_fallback,
                    "heldout_labels_parsed": 0,
                    "heldout_evaluations": 0,
                }
            )
            for outer_fold, weights, fallback in nested_weights:
                weight_rows.append(
                    {
                        "benchmark": dataset.benchmark,
                        "task": dataset.task,
                        "outer_meta_fold": str(outer_fold),
                        **{
                            family: _number(weight)
                            for family, weight in zip(FAMILIES, weights, strict=True)
                        },
                        "fallback_equal_weights": str(fallback).lower(),
                    }
                )
            for candidate in COMBINATION_CANDIDATES:
                score_rows.append(
                    {
                        "benchmark": dataset.benchmark,
                        "task": dataset.task,
                        "problem_type": dataset.problem_type,
                        "candidate": candidate,
                        "primary_metric": _primary_metric(dataset.problem_type),
                        "direction": _primary_direction(dataset.problem_type),
                        "value": _number(scores[candidate]),
                        "rows": str(len(dataset.molecule_ids)),
                        "retained": str(candidate == retained).lower(),
                        "retention_reason": reason if candidate == retained else "",
                    }
                )
                for index, molecule_id in enumerate(dataset.molecule_ids):
                    writer.writerow(
                        {
                            "benchmark": dataset.benchmark,
                            "task": dataset.task,
                            "problem_type": dataset.problem_type,
                            "molecule_id": molecule_id,
                            "inner_fold": str(dataset.folds[index]),
                            "candidate": candidate,
                            "prediction": _number(candidates[candidate][index]),
                            "target": _number(dataset.targets[index]),
                            "standardized_structure_hash": dataset.structure_hashes[
                                index
                            ],
                        }
                    )
                    combination_rows += 1

            random_folds = _random_folds(dataset)
            random_dataset = _replace_folds(dataset, random_folds)
            random_base, random_fits = _retained_base_oof(
                random_dataset, configurations[key]
            )
            model_fits += random_fits
            for index, molecule_id in enumerate(dataset.molecule_ids):
                random_assignment_rows.append(
                    {
                        "benchmark": dataset.benchmark,
                        "task": dataset.task,
                        "molecule_id": molecule_id,
                        "standardized_structure_hash": dataset.structure_hashes[index],
                        "random_fold": str(random_folds[index]),
                    }
                )
                for family in FAMILIES:
                    random_prediction_rows.append(
                        {
                            "benchmark": dataset.benchmark,
                            "task": dataset.task,
                            "problem_type": dataset.problem_type,
                            "molecule_id": molecule_id,
                            "random_fold": str(random_folds[index]),
                            "family": family,
                            "prediction": _number(random_base[family][index]),
                            "target": _number(dataset.targets[index]),
                            "standardized_structure_hash": dataset.structure_hashes[
                                index
                            ],
                        }
                    )
            for family in FAMILIES:
                grouped_value = _primary_score(dataset, base[family])
                random_value = _primary_score(dataset, random_base[family])
                optimism = (
                    random_value - grouped_value
                    if dataset.problem_type == "classification"
                    else grouped_value - random_value
                )
                optimism_rows.append(
                    {
                        "benchmark": dataset.benchmark,
                        "task": dataset.task,
                        "problem_type": dataset.problem_type,
                        "family": family,
                        "primary_metric": _primary_metric(dataset.problem_type),
                        "grouped_value": _number(grouped_value),
                        "random_value": _number(random_value),
                        "optimism": _number(optimism),
                        "interpretation": "positive_means_random_looks_better",
                    }
                )

    _write_csv(scores_path, COMBINATION_SCORE_COLUMNS, score_rows)
    _write_csv(weights_path, STACK_WEIGHT_COLUMNS, weight_rows)
    _write_csv(
        random_assignment_path, RANDOM_ASSIGNMENT_COLUMNS, random_assignment_rows
    )
    _write_csv(
        random_prediction_path, RANDOM_PREDICTION_COLUMNS, random_prediction_rows
    )
    _write_csv(optimism_path, OPTIMISM_COLUMNS, optimism_rows)
    _write_json(
        retained_path,
        {
            "schema_version": COMBINATION_SCHEMA_VERSION,
            "selection_aggregate_sha256": selection_manifest["aggregate_sha256"],
            "family_order": list(FAMILIES),
            "candidate_order": list(COMBINATION_CANDIDATES),
            "stack_method": "scipy.optimize.nnls; no intercept; binary clip [0,1]",
            "stack_minimum_gain": STACK_MINIMUM_GAIN,
            "datasets": retained_datasets,
            "heldout_labels_parsed": 0,
            "heldout_evaluations": 0,
        },
    )
    outputs = {
        path.name: _file_hash(path)
        for path in (
            combination_path,
            scores_path,
            weights_path,
            retained_path,
            random_assignment_path,
            random_prediction_path,
            optimism_path,
        )
    }
    manifest_path = output_directory / "combination_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": COMBINATION_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "selection_manifest_sha256": _file_hash(
                selection_root / "selection_manifest.json"
            ),
            "selection_aggregate_sha256": selection_manifest["aggregate_sha256"],
            "prediction_input_manifest_sha256": _file_hash(
                prediction_inputs / "prediction_input_manifest.json"
            ),
            "prediction_input_aggregate_sha256": input_manifest["aggregate_sha256"],
            "input_hashes": verified_inputs,
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "datasets": len(datasets),
            "combination_prediction_rows": combination_rows,
            "random_assignment_rows": len(random_assignment_rows),
            "random_prediction_rows": len(random_prediction_rows),
            "model_fits": model_fits,
            "heldout_labels_parsed": 0,
            "tdc_public_test_evaluations": 0,
            "octant_outer_evaluations": 0,
            "random_results_used_for_selection": False,
            "packages": {
                "numpy": metadata.version("numpy"),
                "rdkit": metadata.version("rdkit"),
                "scikit-learn": metadata.version("scikit-learn"),
                "scipy": metadata.version("scipy"),
            },
        },
    )
    return CombinationResult(
        manifest_path=manifest_path,
        retained_path=retained_path,
        combination_rows=combination_rows,
        model_fits=model_fits,
    )


def _aligned_base_predictions(
    dataset: SelectionDataset, rows: Sequence[Mapping[str, str]]
) -> dict[str, tuple[float, ...]]:
    grouped: dict[str, dict[str, Mapping[str, str]]] = {family: {} for family in FAMILIES}
    for row in rows:
        if row["benchmark"] != dataset.benchmark or row["task"] != dataset.task:
            continue
        family = row["family"]
        molecule_id = row["molecule_id"]
        if family not in grouped or molecule_id in grouped[family]:
            raise NativeSelectionError("retained OOF family or molecule is invalid")
        grouped[family][molecule_id] = row
    result: dict[str, tuple[float, ...]] = {}
    for family in FAMILIES:
        if set(grouped[family]) != set(dataset.molecule_ids):
            raise NativeSelectionError(f"retained OOF alignment failed: {family}")
        values = []
        for index, molecule_id in enumerate(dataset.molecule_ids):
            row = grouped[family][molecule_id]
            if (
                int(row["inner_fold"]) != dataset.folds[index]
                or float(row["target"]) != dataset.targets[index]
                or row["standardized_structure_hash"]
                != dataset.structure_hashes[index]
            ):
                raise NativeSelectionError("retained OOF metadata alignment failed")
            values.append(float(row["prediction"]))
        result[family] = tuple(values)
    return result


def _combination_candidates(
    dataset: SelectionDataset,
    base: Mapping[str, Sequence[float]],
    configurations: Mapping[str, Mapping[str, Any]],
) -> tuple[
    dict[str, tuple[float, ...]],
    list[tuple[int, tuple[float, ...], bool]],
    int,
]:
    single = _best_single_family(dataset, base)
    rows = _matrix_rows(base, range(len(dataset.molecule_ids)))
    mean_values = tuple(sum(row) / len(row) for row in rows)
    median_values = tuple(median(row) for row in rows)
    stack_values = [0.0] * len(dataset.molecule_ids)
    nested_weights = []
    fits = 0
    for outer_fold in sorted(set(dataset.folds)):
        training_indices = [
            index for index, fold in enumerate(dataset.folds) if fold != outer_fold
        ]
        nested_dataset = _subset_dataset(dataset, training_indices)
        nested_base, nested_fits = _retained_base_oof(
            nested_dataset, configurations
        )
        fits += nested_fits
        weights, fallback = _fit_nonnegative_weights(
            _matrix_rows(nested_base, range(len(training_indices))),
            nested_dataset.targets,
        )
        nested_weights.append((outer_fold, weights, fallback))
        valid_indices = [
            index for index, fold in enumerate(dataset.folds) if fold == outer_fold
        ]
        predictions = _apply_weights(
            _matrix_rows(base, valid_indices), weights, dataset.problem_type
        )
        for index, prediction in zip(valid_indices, predictions, strict=True):
            stack_values[index] = prediction
    return (
        {
            "best_single": tuple(base[single]),
            "unweighted_mean": mean_values,
            "median": median_values,
            "nonnegative_linear_stack": tuple(stack_values),
        },
        nested_weights,
        fits,
    )


def _retained_base_oof(
    dataset: SelectionDataset,
    configurations: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, tuple[float, ...]], int]:
    fingerprints, matrix = _fingerprints(dataset.structures)
    prior = _oof_prior(dataset)
    linear = _oof_linear(dataset, matrix, configurations["ecfp_linear"], SEED)
    knn = _oof_knn(
        dataset, fingerprints, [configurations["similarity_knn"]]
    )[str(configurations["similarity_knn"]["id"])]
    seed_sets = [
        _oof_extra_trees(dataset, matrix, configurations["extra_trees"], seed)
        for seed in STOCHASTIC_SEEDS
    ]
    trees = _mean_prediction_sets(seed_sets)
    folds = len(set(dataset.folds))
    return (
        {
            "prior": prior.predictions,
            "ecfp_linear": linear.predictions,
            "similarity_knn": knn.predictions,
            "extra_trees": trees.predictions,
        },
        folds * 6,
    )


def _best_single_family(
    dataset: SelectionDataset, base: Mapping[str, Sequence[float]]
) -> str:
    scores = {family: _primary_score(dataset, base[family]) for family in FAMILIES}
    if dataset.problem_type == "classification":
        return min(FAMILIES, key=lambda family: (-scores[family], family))
    return min(FAMILIES, key=lambda family: (scores[family], family))


def _retained_candidate(
    dataset: SelectionDataset, scores: Mapping[str, float]
) -> tuple[str, str]:
    nonlearned = COMBINATION_CANDIDATES[:3]
    if dataset.problem_type == "classification":
        winner = min(nonlearned, key=lambda item: (-scores[item], item))
        gain = scores["nonnegative_linear_stack"] - scores[winner]
    else:
        winner = min(nonlearned, key=lambda item: (scores[item], item))
        gain = scores[winner] - scores["nonnegative_linear_stack"]
    margin = STACK_MINIMUM_GAIN[dataset.problem_type]
    if gain >= margin:
        return (
            "nonnegative_linear_stack",
            f"stack_gain={_number(gain)} meets complexity_margin={_number(margin)}",
        )
    return (
        winner,
        f"stack_gain={_number(gain)} below complexity_margin={_number(margin)}",
    )


def _fit_nonnegative_weights(
    rows: Sequence[Sequence[float]], targets: Sequence[float]
) -> tuple[tuple[float, ...], bool]:
    np = import_module("numpy")
    optimize = import_module("scipy.optimize")
    matrix = np.asarray(rows, dtype=np.float64)
    target = np.asarray(targets, dtype=np.float64)
    weights, _ = optimize.nnls(matrix, target)
    if float(weights.sum()) == 0.0:
        return (tuple(1.0 / len(FAMILIES) for _ in FAMILIES), True)
    return (tuple(float(value) for value in weights), False)


def _apply_weights(
    rows: Sequence[Sequence[float]],
    weights: Sequence[float],
    problem_type: str,
) -> tuple[float, ...]:
    values = [
        sum(value * weight for value, weight in zip(row, weights, strict=True))
        for row in rows
    ]
    if problem_type == "classification":
        values = [min(max(value, 0.0), 1.0) for value in values]
    return tuple(values)


def _matrix_rows(
    base: Mapping[str, Sequence[float]], indices: Sequence[int] | range
) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(base[family][index] for family in FAMILIES) for index in indices)


def _subset_dataset(
    dataset: SelectionDataset, indices: Sequence[int]
) -> SelectionDataset:
    return SelectionDataset(
        benchmark=dataset.benchmark,
        task=dataset.task,
        problem_type=dataset.problem_type,
        molecule_ids=tuple(dataset.molecule_ids[index] for index in indices),
        structures=tuple(dataset.structures[index] for index in indices),
        structure_hashes=tuple(dataset.structure_hashes[index] for index in indices),
        targets=tuple(dataset.targets[index] for index in indices),
        folds=tuple(dataset.folds[index] for index in indices),
    )


def _replace_folds(dataset: SelectionDataset, folds: Sequence[int]) -> SelectionDataset:
    return SelectionDataset(
        benchmark=dataset.benchmark,
        task=dataset.task,
        problem_type=dataset.problem_type,
        molecule_ids=dataset.molecule_ids,
        structures=dataset.structures,
        structure_hashes=dataset.structure_hashes,
        targets=dataset.targets,
        folds=tuple(folds),
    )


def _random_folds(dataset: SelectionDataset) -> tuple[int, ...]:
    groups: dict[str, list[int]] = {}
    for index, structure_hash in enumerate(dataset.structure_hashes):
        groups.setdefault(structure_hash, []).append(index)
    ordered = sorted(
        groups,
        key=lambda structure_hash: sha256(
            f"{SEED}|{dataset.benchmark}|{dataset.task}|{structure_hash}".encode()
        ).hexdigest(),
    )
    counts = [0, 0, 0, 0]
    assignment: dict[str, int] = {}
    for structure_hash in ordered:
        fold = min(range(4), key=lambda item: (counts[item], item))
        assignment[structure_hash] = fold
        counts[fold] += len(groups[structure_hash])
    if max(counts) - min(counts) > max(len(indices) for indices in groups.values()):
        raise NativeSelectionError("random fold balancing exceeded one group size")
    return tuple(assignment[value] for value in dataset.structure_hashes)


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
