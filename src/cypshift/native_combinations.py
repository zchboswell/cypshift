"""Frozen OOF-only native combinations and random-optimism analysis."""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module, metadata
from pathlib import Path
from statistics import median
from typing import Any

from cypshift.native_evaluation import (
    SCORECARD_COLUMNS,
    _load_scoring_labels,
    _mcc_threshold,
    _octant_score_row,
    _retained_configurations,
    _tdc_anchors,
    _tdc_score_row,
    _verify_prediction_inputs,
    _verify_prediction_receipt,
    _verify_selection_receipt,
    _write_csv_rows,
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
    _read_json,
    _verify_input_receipts,
    _write_json,
)
from cypshift.tdc import TDC_TASKS

COMBINATION_SCHEMA_VERSION = "cypshift.native_combinations.v3"
RETAINED_MEAN_PREDICTION_SCHEMA_VERSION = (
    "cypshift.retained_mean_heldout_prediction.v1"
)
RETAINED_MEAN_SCORING_SCHEMA_VERSION = "cypshift.retained_mean_heldout_scoring.v1"
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
RETAINED_MEAN_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "candidate",
    "prediction",
    "standardized_structure_hash",
    "base_family_count",
)


@dataclass(frozen=True, slots=True)
class CombinationResult:
    """Paths and counts for one immutable OOF-only combination run."""

    manifest_path: Path
    retained_path: Path
    combination_rows: int
    base_model_fits: int
    total_fit_operations: int


@dataclass(frozen=True, slots=True)
class RetainedMeanPredictionResult:
    """One immutable label-free mean prediction per held-out molecule."""

    manifest_path: Path
    predictions_path: Path
    prediction_rows: int


@dataclass(frozen=True, slots=True)
class RetainedMeanScoringResult:
    """One immutable scoring pass for the retained mean only."""

    manifest_path: Path
    scores_path: Path
    tdc_evaluations: int
    octant_evaluations: int


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
    base_model_fits = 0
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
            base_model_fits += nested_fits
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
            base_model_fits += random_fits
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
    nested_nnls_fits = sum(len(set(dataset.folds)) for dataset in datasets)
    final_nnls_fits = len(datasets)
    total_fit_operations = base_model_fits + nested_nnls_fits + final_nnls_fits
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
            "base_model_fits": base_model_fits,
            "nested_nnls_fits": nested_nnls_fits,
            "final_nnls_fits": final_nnls_fits,
            "total_fit_operations": total_fit_operations,
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
        base_model_fits=base_model_fits,
        total_fit_operations=total_fit_operations,
    )


def run_retained_mean_prediction(
    combination_root: Path,
    base_prediction_root: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> RetainedMeanPredictionResult:
    """Apply the reviewed unweighted mean without fitting or reading labels."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. "
            "Retained-mean prediction artifacts are immutable."
        )
    if not source_revision.strip():
        raise NativeSelectionError("source revision must not be empty")
    combination_manifest, retained = _verify_combination_receipt(combination_root)
    base_manifest = _verify_prediction_receipt(base_prediction_root)
    _verify_mean_receipt_binding(combination_manifest, retained, base_manifest)

    grouped: dict[tuple[str, str, str], dict[str, Mapping[str, str]]] = {}
    for row in _read_csv(base_prediction_root / "heldout_predictions.csv"):
        key = (row["benchmark"], row["task"], row["molecule_id"])
        family = row["family"]
        if family not in FAMILIES or family in grouped.setdefault(key, {}):
            raise NativeSelectionError("held-out base family or molecule is invalid")
        grouped[key][family] = row
    if len(grouped) != base_manifest.get("heldout_structures"):
        raise NativeSelectionError("held-out molecule count does not match receipt")
    expected_rows = len(grouped) * len(FAMILIES)
    if expected_rows != base_manifest.get("prediction_rows"):
        raise NativeSelectionError("held-out base prediction count does not match receipt")

    retained_tasks = {
        (str(item["benchmark"]), str(item["task"])): str(item["problem_type"])
        for item in retained["datasets"]
    }
    output_rows: list[dict[str, str]] = []
    observed_tasks: set[tuple[str, str]] = set()
    for key, families in grouped.items():
        if set(families) != set(FAMILIES):
            raise NativeSelectionError("held-out molecule lacks four base families")
        benchmark, task, molecule_id = key
        task_key = (benchmark, task)
        observed_tasks.add(task_key)
        problem_type = retained_tasks.get(task_key)
        row_metadata = {
            (
                row["benchmark"],
                row["task"],
                row["problem_type"],
                row["molecule_id"],
                row["standardized_structure_hash"],
            )
            for row in families.values()
        }
        if len(row_metadata) != 1 or problem_type is None:
            raise NativeSelectionError("held-out base metadata alignment failed")
        (_, _, row_problem_type, _, structure_hash) = row_metadata.pop()
        if row_problem_type != problem_type:
            raise NativeSelectionError("held-out problem type does not match receipt")
        try:
            values = [float(families[family]["prediction"]) for family in FAMILIES]
        except ValueError as exc:
            raise NativeSelectionError(
                "held-out base prediction must be numeric"
            ) from exc
        if not all(math.isfinite(value) for value in values):
            raise NativeSelectionError("held-out base prediction must be finite")
        if problem_type == "classification" and any(
            value < 0.0 or value > 1.0 for value in values
        ):
            raise NativeSelectionError(
                "held-out classification prediction must be within [0, 1]"
            )
        output_rows.append(
            {
                "benchmark": benchmark,
                "task": task,
                "problem_type": problem_type,
                "molecule_id": molecule_id,
                "candidate": "unweighted_mean",
                "prediction": _number(sum(values) / len(FAMILIES)),
                "standardized_structure_hash": structure_hash,
                "base_family_count": str(len(FAMILIES)),
            }
        )
    if observed_tasks != set(retained_tasks):
        raise NativeSelectionError("held-out task population does not match receipt")

    output_directory.mkdir(parents=True)
    predictions_path = output_directory / "retained_mean_heldout_predictions.csv"
    _write_csv(predictions_path, RETAINED_MEAN_COLUMNS, output_rows)
    rows_written = len(output_rows)
    outputs = {predictions_path.name: _file_hash(predictions_path)}
    manifest_path = output_directory / "retained_mean_prediction_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": RETAINED_MEAN_PREDICTION_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "combination_schema_version": combination_manifest["schema_version"],
            "combination_manifest_sha256": _file_hash(
                combination_root / "combination_manifest.json"
            ),
            "combination_aggregate_sha256": combination_manifest["aggregate_sha256"],
            "base_prediction_schema_version": base_manifest["schema_version"],
            "base_prediction_manifest_sha256": _file_hash(
                base_prediction_root / "heldout_prediction_manifest.json"
            ),
            "base_prediction_aggregate_sha256": base_manifest["aggregate_sha256"],
            "selection_aggregate_sha256": base_manifest[
                "selection_aggregate_sha256"
            ],
            "prediction_input_aggregate_sha256": base_manifest[
                "prediction_input_aggregate_sha256"
            ],
            "candidate": "unweighted_mean",
            "family_order": list(FAMILIES),
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "tasks": len(observed_tasks),
            "heldout_structures": rows_written,
            "prediction_rows": rows_written,
            "base_predictions_averaged": rows_written * len(FAMILIES),
            "model_fits": 0,
            "heldout_measurement_tables_opened": 0,
            "heldout_labels_parsed": 0,
            "tdc_public_test_evaluations": 0,
            "octant_outer_evaluations": 0,
        },
    )
    return RetainedMeanPredictionResult(
        manifest_path=manifest_path,
        predictions_path=predictions_path,
        prediction_rows=rows_written,
    )


def run_retained_mean_scoring(
    octant_canonical: Path,
    tdc_canonical: Path,
    validation_root: Path,
    combination_root: Path,
    prediction_root: Path,
    public_sources_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
    attempt: int = 1,
) -> RetainedMeanScoringResult:
    """Score only the frozen retained mean on the declared populations."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. Scoring is immutable."
        )
    if not source_revision.strip():
        raise NativeSelectionError("source revision must not be empty")
    if attempt < 1:
        raise NativeSelectionError("scoring attempt must be positive")
    verified_inputs = _verify_input_receipts(
        octant_canonical, tdc_canonical, validation_root
    )
    combination_manifest, retained = _verify_combination_receipt(combination_root)
    if combination_manifest.get("input_hashes") != verified_inputs:
        raise NativeSelectionError("combination inputs do not match canonical receipts")
    prediction_manifest = _verify_retained_mean_prediction_receipt(
        prediction_root, combination_root, combination_manifest
    )
    predictions = _validated_mean_predictions(prediction_root, prediction_manifest, retained)
    _verify_scoring_populations(predictions, validation_root)
    thresholds = _mean_oof_thresholds(combination_root)
    exclusions = _strict_exclusions(predictions, validation_root)
    anchors = _tdc_anchors(_read_json(public_sources_path))

    octant_ids = {
        row["molecule_id"] for row in predictions if row["benchmark"] == "octant_cyp"
    }
    tdc_ids = {
        row["molecule_id"]
        for row in predictions
        if row["benchmark"] == "tdc_admet_group"
    }
    octant_labels = _load_scoring_labels(
        octant_canonical / "measurements.csv", octant_ids, regression=True
    )
    tdc_labels = _load_scoring_labels(
        tdc_canonical / "measurements.csv", tdc_ids, regression=False
    )
    if set(octant_labels) != octant_ids or set(tdc_labels) != tdc_ids:
        raise NativeSelectionError("held-out label alignment is incomplete")

    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    scored_rows: list[dict[str, str]] = []
    for row in predictions:
        labels = octant_labels if row["benchmark"] == "octant_cyp" else tdc_labels
        target = labels[row["molecule_id"]][0]
        scored_rows.append(
            {
                **row,
                "target": _number(target),
                "strict_excluded": str(row["molecule_id"] in exclusions).lower(),
            }
        )
        groups.setdefault((row["benchmark"], row["task"]), []).append(
            {
                **row,
                "family": "unweighted_mean",
                "configuration_id": "four_family_unweighted_mean",
            }
        )

    score_rows: list[dict[str, str]] = []
    for benchmark, task in sorted(groups):
        rows = groups[(benchmark, task)]
        if benchmark == "octant_cyp":
            score_rows.append(
                _octant_score_row(
                    task, "unweighted_mean", rows, octant_labels
                )
            )
            continue
        threshold = thresholds[task]
        score_rows.append(
            _tdc_score_row(
                task,
                "unweighted_mean",
                "official",
                rows,
                tdc_labels,
                threshold,
                anchors[task],
            )
        )
        strict_rows = [row for row in rows if row["molecule_id"] not in exclusions]
        score_rows.append(
            _tdc_score_row(
                task,
                "unweighted_mean",
                "strict",
                strict_rows,
                tdc_labels,
                threshold,
                None,
            )
        )

    output_directory.mkdir(parents=True)
    scored_path = output_directory / "scored_retained_mean_predictions.csv"
    scores_path = output_directory / "heldout_scores.csv"
    _write_csv(
        scored_path,
        (*RETAINED_MEAN_COLUMNS, "target", "strict_excluded"),
        scored_rows,
    )
    _write_csv_rows(scores_path, SCORECARD_COLUMNS, score_rows)
    outputs = {
        scored_path.name: _file_hash(scored_path),
        scores_path.name: _file_hash(scores_path),
    }
    manifest_path = output_directory / "retained_mean_scoring_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": RETAINED_MEAN_SCORING_SCHEMA_VERSION,
            "metric_schema_version": "cypshift.native_metrics.v1",
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "prediction_manifest_sha256": _file_hash(
                prediction_root / "retained_mean_prediction_manifest.json"
            ),
            "prediction_aggregate_sha256": prediction_manifest["aggregate_sha256"],
            "combination_manifest_sha256": _file_hash(
                combination_root / "combination_manifest.json"
            ),
            "combination_aggregate_sha256": combination_manifest["aggregate_sha256"],
            "public_sources_sha256": _file_hash(public_sources_path),
            "input_hashes": verified_inputs,
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "candidate": "unweighted_mean",
            "heldout_labels_parsed": len(octant_labels) + len(tdc_labels),
            "tdc_public_test_evaluations": len(TDC_TASKS),
            "tdc_strict_companion_analyses": len(TDC_TASKS),
            "octant_outer_evaluations": 1,
            "rejected_candidate_evaluations": 0,
            "model_fits": 0,
            "model_selection_changes": 0,
            "scoring_attempt": attempt,
        },
    )
    return RetainedMeanScoringResult(
        manifest_path=manifest_path,
        scores_path=scores_path,
        tdc_evaluations=len(TDC_TASKS),
        octant_evaluations=1,
    )


def _verify_retained_mean_prediction_receipt(
    root: Path,
    combination_root: Path,
    combination_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = _read_json(root / "retained_mean_prediction_manifest.json")
    if manifest.get("schema_version") != RETAINED_MEAN_PREDICTION_SCHEMA_VERSION:
        raise NativeSelectionError("unsupported retained-mean prediction schema")
    if any(
        manifest.get(field) != 0
        for field in (
            "model_fits",
            "heldout_measurement_tables_opened",
            "heldout_labels_parsed",
            "tdc_public_test_evaluations",
            "octant_outer_evaluations",
        )
    ):
        raise NativeSelectionError("retained-mean prediction is not label clean")
    if (
        manifest.get("candidate") != "unweighted_mean"
        or manifest.get("combination_manifest_sha256")
        != _file_hash(combination_root / "combination_manifest.json")
        or manifest.get("combination_aggregate_sha256")
        != combination_manifest.get("aggregate_sha256")
    ):
        raise NativeSelectionError("retained-mean prediction is not bound to combination")
    for field in (
        "selection_aggregate_sha256",
        "prediction_input_aggregate_sha256",
    ):
        if manifest.get(field) != combination_manifest.get(field):
            raise NativeSelectionError(f"retained-mean prediction {field} differs")
    outputs = manifest.get("outputs")
    expected_outputs = {"retained_mean_heldout_predictions.csv"}
    if not isinstance(outputs, dict) or set(outputs) != expected_outputs:
        raise NativeSelectionError("retained-mean prediction outputs are invalid")
    for name, expected in outputs.items():
        if not isinstance(expected, str) or _file_hash(root / name) != expected:
            raise NativeSelectionError(f"retained-mean output hash mismatch: {name}")
    if _hash_mapping(outputs) != manifest.get("aggregate_sha256"):
        raise NativeSelectionError("retained-mean prediction aggregate hash mismatch")
    return manifest


def _validated_mean_predictions(
    root: Path,
    manifest: Mapping[str, Any],
    retained: Mapping[str, Any],
) -> list[dict[str, str]]:
    rows = _read_csv(root / "retained_mean_heldout_predictions.csv")
    datasets = retained.get("datasets")
    if not isinstance(datasets, list):
        raise NativeSelectionError("retained-combination datasets are invalid")
    tasks = {
        (str(item["benchmark"]), str(item["task"])): str(item["problem_type"])
        for item in datasets
    }
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row["benchmark"], row["task"], row["molecule_id"])
        problem_type = tasks.get(key[:2])
        try:
            prediction = float(row["prediction"])
        except ValueError as exc:
            raise NativeSelectionError("retained-mean prediction must be numeric") from exc
        if (
            key in seen
            or row.get("candidate") != "unweighted_mean"
            or row.get("base_family_count") != str(len(FAMILIES))
            or row.get("problem_type") != problem_type
            or not row.get("standardized_structure_hash")
            or not math.isfinite(prediction)
            or (problem_type == "classification" and not 0.0 <= prediction <= 1.0)
        ):
            raise NativeSelectionError("retained-mean prediction row is invalid")
        seen.add(key)
    if (
        len(rows) != manifest.get("prediction_rows")
        or len(rows) != manifest.get("heldout_structures")
        or {key[:2] for key in seen} != set(tasks)
    ):
        raise NativeSelectionError("retained-mean prediction population is incomplete")
    return rows


def _verify_scoring_populations(
    predictions: Sequence[Mapping[str, str]], validation_root: Path
) -> None:
    expected: dict[tuple[str, str], set[str]] = {
        ("octant_cyp", "cyp3a4_active_preincubation_pIC50"): {
            row["molecule_id"]
            for row in _read_csv(
                validation_root / "octant" / "octant_grouped_split.csv"
            )
            if row.get("outer_partition") == "validation"
            and row.get("has_measurement") == "true"
        }
    }
    for task in TDC_TASKS:
        expected[("tdc_admet_group", task)] = set()
    for row in _read_csv(validation_root / "tdc" / "official_split.csv"):
        if row.get("partition") == "test":
            key = ("tdc_admet_group", row.get("task", ""))
            if key not in expected:
                raise NativeSelectionError("official split contains an unknown task")
            expected[key].add(row["molecule_id"])
    observed: dict[tuple[str, str], set[str]] = {}
    for prediction_row in predictions:
        observed.setdefault(
            (prediction_row["benchmark"], prediction_row["task"]), set()
        ).add(
            prediction_row["molecule_id"]
        )
    if observed != expected:
        raise NativeSelectionError("retained-mean scoring population differs from split")


def _mean_oof_thresholds(root: Path) -> dict[str, float]:
    groups: dict[str, list[tuple[int, float]]] = {}
    seen: set[tuple[str, str]] = set()
    for row in _read_csv(root / "combination_oof_predictions.csv"):
        if row.get("candidate") != "unweighted_mean" or row.get(
            "problem_type"
        ) != "classification":
            continue
        identity = (row["task"], row["molecule_id"])
        if identity in seen:
            raise NativeSelectionError("duplicate retained-mean OOF prediction")
        seen.add(identity)
        target = int(float(row["target"]))
        prediction = float(row["prediction"])
        if target not in {0, 1} or not math.isfinite(prediction):
            raise NativeSelectionError("retained-mean OOF row is invalid")
        groups.setdefault(row["task"], []).append((target, prediction))
    if set(groups) != set(TDC_TASKS):
        raise NativeSelectionError("retained-mean OOF thresholds are incomplete")
    return {task: _mcc_threshold(values) for task, values in groups.items()}


def _strict_exclusions(
    predictions: Sequence[Mapping[str, str]], validation_root: Path
) -> set[str]:
    expected = {
        (row["task"], row["molecule_id"]): row["standardized_structure_hash"]
        for row in predictions
        if row["benchmark"] == "tdc_admet_group"
    }
    result: set[str] = set()
    for row in _read_csv(validation_root / "tdc" / "strict_test_exclusions.csv"):
        key = (row.get("task", ""), row.get("molecule_id", ""))
        if (
            key not in expected
            or row.get("standardized_structure_hash") != expected[key]
            or row.get("reason") != "standardized_structure_in_train_val"
            or key[1] in result
        ):
            raise NativeSelectionError("strict exclusion row is invalid")
        result.add(key[1])
    return result


def _verify_combination_receipt(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _read_json(root / "combination_manifest.json")
    if manifest.get("schema_version") != COMBINATION_SCHEMA_VERSION:
        raise NativeSelectionError("unsupported native-combination schema")
    if any(
        manifest.get(field) != 0
        for field in (
            "heldout_labels_parsed",
            "tdc_public_test_evaluations",
            "octant_outer_evaluations",
        )
    ):
        raise NativeSelectionError("native-combination receipt is not label clean")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise NativeSelectionError("native-combination outputs must be an object")
    for name, expected in outputs.items():
        if (
            not isinstance(name, str)
            or not isinstance(expected, str)
            or Path(name).is_absolute()
            or ".." in Path(name).parts
        ):
            raise NativeSelectionError("native-combination output entry is invalid")
        if _file_hash(root / name) != expected:
            raise NativeSelectionError(f"native-combination output hash mismatch: {name}")
    if _hash_mapping(outputs) != manifest.get("aggregate_sha256"):
        raise NativeSelectionError("native-combination aggregate hash mismatch")
    retained = _read_json(root / "retained_combinations.json")
    return manifest, retained


def _verify_mean_receipt_binding(
    combination: Mapping[str, Any],
    retained: Mapping[str, Any],
    base_prediction: Mapping[str, Any],
) -> None:
    datasets = retained.get("datasets")
    if (
        retained.get("schema_version") != COMBINATION_SCHEMA_VERSION
        or not isinstance(datasets, list)
        or len(datasets) != combination.get("datasets")
    ):
        raise NativeSelectionError("retained-combination receipt is invalid")
    keys: set[tuple[str, str]] = set()
    for item in datasets:
        if (
            not isinstance(item, dict)
            or item.get("retained_candidate") != "unweighted_mean"
        ):
            raise NativeSelectionError("unweighted mean was not retained for every task")
        key = (str(item.get("benchmark")), str(item.get("task")))
        if key in keys or item.get("problem_type") not in {
            "classification",
            "regression",
        }:
            raise NativeSelectionError("retained-combination task is invalid")
        keys.add(key)
    for field in (
        "selection_aggregate_sha256",
        "prediction_input_aggregate_sha256",
    ):
        if combination.get(field) != base_prediction.get(field):
            raise NativeSelectionError(f"combination and base prediction {field} differ")
    if retained.get("selection_aggregate_sha256") != combination.get(
        "selection_aggregate_sha256"
    ):
        raise NativeSelectionError("retained combination is not bound to selection")


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
