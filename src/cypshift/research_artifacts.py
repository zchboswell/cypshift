"""Complete, receipt-bound research artifacts for the first public scorecard."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from statistics import pstdev
from typing import Any

from cypshift.metrics import average_precision
from cypshift.native_evaluation import HELDOUT_COLUMNS
from cypshift.native_selection import (
    NativeSelectionError,
    _file_hash,
    _number,
    _read_csv,
    _read_json,
    _write_json,
)

RESEARCH_OBSERVATION_SCHEMA_VERSION = "cypshift.research_observations.v1"
SCORECARD_SCHEMA_VERSION = "cypshift.public_scorecard.v4"
RETAINED_MEAN_SCORECARD_SCHEMA_VERSION = "cypshift.retained_mean_scorecard.v2"
METRIC_SCHEMA_VERSION = "cypshift.native_metrics.v1"
AGGREGATE_RECIPE = (
    "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined with newline "
    "characters, without a trailing newline"
)

RESEARCH_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "inner_fold",
    "family",
    "configuration_id",
    "seed",
    "prediction",
    "prediction_uncertainty",
    "uncertainty_type",
    "applicability",
    "nearest_neighbor_similarity",
    "local_support_count",
    "local_label_variance",
    "scaffold_group_hash",
    "scaffold_support_count",
    "target",
    "measurement_quality",
    "standardized_structure_hash",
    "configuration_sha256",
    "data_sha256",
    "split_sha256",
    "selection_aggregate_sha256",
)

SCORECARD_ADDITIONAL_COLUMNS = (
    "dataset_revision",
    "split_sha256",
    "population_sha256",
    "native_seed_policy",
    "native_seed_count",
    "native_seed_primary_values",
    "native_seed_primary_min",
    "native_seed_primary_max",
    "native_seed_primary_std",
    "maplight_gnn_std",
    "chemprop_rdkit_std",
    "chemprop_std",
    "delta_vs_chemprop_rdkit",
    "delta_vs_chemprop",
    "selection_runtime_seconds",
    "heldout_prediction_runtime_seconds",
    "scoring_runtime_seconds",
    "hardware",
    "comparison_status",
    "contamination_warning",
    "aggregation_warning",
)


def complete_oof_research_artifact(
    selection_root: Path,
    octant_canonical: Path,
    tdc_canonical: Path,
    validation_root: Path,
    output_directory: Path,
    *,
    source_revision: str,
) -> Path:
    """Enrich immutable OOF rows with the declared observation-level contract."""

    _require_new_directory(output_directory)
    selection_manifest = _verify_manifest_outputs(
        selection_root / "selection_manifest.json", selection_root
    )
    retained_models = _read_json(selection_root / "retained_models.json")
    retained_rows = _read_csv(selection_root / "retained_oof_predictions.csv")
    seed_rows = _read_csv(
        selection_root / "retained_stochastic_seed_predictions.csv"
    )
    split_rows = {
        "octant_cyp": _read_csv(
            validation_root / "octant" / "octant_grouped_split.csv"
        ),
        "tdc_admet_group": _read_csv(
            validation_root / "tdc" / "tdc_inner_folds.csv"
        ),
    }
    split_paths = {
        "octant_cyp": validation_root / "octant" / "octant_grouped_split.csv",
        "tdc_admet_group": validation_root / "tdc" / "tdc_inner_folds.csv",
    }
    split_hashes = {
        benchmark: _file_hash(path) for benchmark, path in split_paths.items()
    }
    split_metadata, support = _split_metadata(split_rows)
    quality = {
        "octant_cyp": _measurement_quality(octant_canonical / "measurements.csv"),
        "tdc_admet_group": _measurement_quality(
            tdc_canonical / "measurements.csv"
        ),
    }
    uncertainty = _prediction_uncertainty(seed_rows)
    configuration_hashes = _configuration_hashes(retained_models)
    inputs = selection_manifest.get("input_hashes")
    if not isinstance(inputs, dict):
        raise NativeSelectionError("selection manifest input hashes are invalid")
    data_hashes = {
        benchmark: _hash_mapping(
            {
                name: str(inputs[name])
                for name in (
                    ("octant/measurements.csv", "octant/molecules.csv")
                    if benchmark == "octant_cyp"
                    else ("tdc/measurements.csv", "tdc/molecules.csv")
                )
            }
        )
        for benchmark in ("octant_cyp", "tdc_admet_group")
    }
    output_directory.mkdir(parents=True)
    observations_path = output_directory / "retained_oof_observations.csv"
    with observations_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=RESEARCH_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for row in retained_rows:
            benchmark = row["benchmark"]
            task = row["task"]
            molecule_id = row["molecule_id"]
            family = row["family"]
            key = (benchmark, task, molecule_id)
            scaffold_hash, fold = split_metadata[key]
            seed_std = uncertainty.get((benchmark, task, molecule_id, family))
            writer.writerow(
                {
                    **{name: row.get(name, "") for name in RESEARCH_COLUMNS},
                    "prediction_uncertainty": (
                        "" if seed_std is None else _number(seed_std)
                    ),
                    "uncertainty_type": (
                        "allowed_seed_prediction_population_std"
                        if seed_std is not None
                        else "not_available_deterministic"
                    ),
                    "applicability": (
                        "observed_local_analog_support"
                        if row.get("nearest_neighbor_similarity")
                        else "not_estimated_for_family"
                    ),
                    "scaffold_group_hash": scaffold_hash,
                    "scaffold_support_count": str(
                        support[(benchmark, task, scaffold_hash, fold)]
                    ),
                    "measurement_quality": quality[benchmark][molecule_id],
                    "configuration_sha256": configuration_hashes[
                        (benchmark, task, family)
                    ],
                    "data_sha256": data_hashes[benchmark],
                    "split_sha256": split_hashes[benchmark],
                    "selection_aggregate_sha256": selection_manifest[
                        "aggregate_sha256"
                    ],
                }
            )
    outputs = {observations_path.name: _file_hash(observations_path)}
    manifest_path = output_directory / "research_observation_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": RESEARCH_OBSERVATION_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "selection_manifest_sha256": _file_hash(
                selection_root / "selection_manifest.json"
            ),
            "selection_aggregate_sha256": selection_manifest["aggregate_sha256"],
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "rows": len(retained_rows),
            "uncertainty": (
                "ExtraTrees carries the population standard deviation of the "
                "three allowed seed predictions; deterministic families are "
                "explicitly marked unavailable."
            ),
            "applicability": (
                "Local analog support is observed only for similarity kNN; no "
                "post-result applicability threshold is introduced."
            ),
        },
    )
    return manifest_path


def complete_first_scorecard(
    scoring_v1_root: Path,
    prediction_v2_root: Path,
    selection_root: Path,
    validation_root: Path,
    public_sources_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
    selection_runtime_seconds: float,
    prediction_runtime_seconds: float,
    scoring_runtime_seconds: float,
    hardware: str,
) -> Path:
    """Version the observed scorecard and add required provenance/uncertainty."""

    _require_new_directory(output_directory)
    scoring_manifest = _verify_manifest_outputs(
        scoring_v1_root / "heldout_scoring_manifest.json", scoring_v1_root
    )
    prediction_manifest = _verify_manifest_outputs(
        prediction_v2_root / "heldout_prediction_manifest.json", prediction_v2_root
    )
    selection_manifest = _verify_manifest_outputs(
        selection_root / "selection_manifest.json", selection_root
    )
    _assert_prediction_alignment(
        scoring_v1_root / "scored_predictions.csv",
        prediction_v2_root / "heldout_predictions.csv",
    )
    sources = _read_json(public_sources_path)
    rows, original_columns = _read_csv_columns(scoring_v1_root / "scorecard.csv")
    scored = _read_csv(scoring_v1_root / "scored_predictions.csv")
    seeds = _read_csv(
        prediction_v2_root / "heldout_stochastic_seed_predictions.csv"
    )
    seed_values = _heldout_seed_primary_values(rows, scored, seeds)
    split_hashes = {
        "octant_cyp": _file_hash(
            validation_root / "octant" / "octant_grouped_split.csv"
        ),
        "tdc_admet_group": str(prediction_manifest["official_split_sha256"]),
    }
    dataset_revisions = _dataset_revisions(sources)
    anchors = _anchor_statistics(sources)
    population_hashes = _population_hashes(scored)
    completed_rows: list[dict[str, str]] = []
    for row in rows:
        benchmark = row["benchmark"]
        task = row["task"]
        population = row["population"]
        family = row["family"]
        values = seed_values[(benchmark, task, population, family)]
        point = float(row["primary_value"])
        if family == "extra_trees":
            seed_policy = "three_allowed_seeds; point_scores_mean_prediction"
        else:
            seed_policy = "deterministic_single_fit"
        reference = anchors.get(task, {}) if population == "official" else {}
        completed = dict(row)
        completed.update(
            {
                "dataset_revision": dataset_revisions[benchmark],
                "split_sha256": split_hashes[benchmark],
                "population_sha256": population_hashes[
                    (benchmark, task, population)
                ],
                "native_seed_policy": seed_policy,
                "native_seed_count": str(len(values)),
                "native_seed_primary_values": "|".join(_number(v) for v in values),
                "native_seed_primary_min": _number(min(values)),
                "native_seed_primary_max": _number(max(values)),
                "native_seed_primary_std": _number(pstdev(values)),
                "maplight_gnn_std": _reference_std(reference, "MapLight + GNN"),
                "chemprop_rdkit_std": _reference_std(reference, "Chemprop-RDKit"),
                "chemprop_std": _reference_std(reference, "Chemprop"),
                "delta_vs_chemprop_rdkit": _delta(
                    point, reference, "Chemprop-RDKit"
                ),
                "delta_vs_chemprop": _delta(point, reference, "Chemprop"),
                "selection_runtime_seconds": _number(selection_runtime_seconds),
                "heldout_prediction_runtime_seconds": _number(
                    prediction_runtime_seconds
                ),
                "scoring_runtime_seconds": _number(scoring_runtime_seconds),
                "hardware": hardware,
                "comparison_status": _comparison_status(benchmark, population),
                "contamination_warning": _contamination_warning(
                    benchmark, task, population
                ),
                "aggregation_warning": (
                    "Local deterministic scores and the score of a three-seed "
                    "mean ExtraTrees prediction are compared with published "
                    "leaderboard mean+/-SD values; aggregation differs."
                    if population == "official"
                    else "No public leaderboard delta is asserted."
                ),
            }
        )
        completed_rows.append(completed)

    output_directory.mkdir(parents=True)
    columns = (*original_columns, *SCORECARD_ADDITIONAL_COLUMNS)
    csv_path = output_directory / "scorecard.csv"
    _write_csv(csv_path, columns, completed_rows)
    json_path = output_directory / "scorecard.json"
    _write_json(
        json_path,
        {
            "schema_version": SCORECARD_SCHEMA_VERSION,
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "rows": completed_rows,
        },
    )
    outputs = {
        csv_path.name: _file_hash(csv_path),
        json_path.name: _file_hash(json_path),
    }
    manifest_path = output_directory / "scorecard_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": SCORECARD_SCHEMA_VERSION,
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "selection_manifest_sha256": _file_hash(
                selection_root / "selection_manifest.json"
            ),
            "selection_aggregate_sha256": selection_manifest["aggregate_sha256"],
            "prediction_manifest_sha256": _file_hash(
                prediction_v2_root / "heldout_prediction_manifest.json"
            ),
            "prediction_aggregate_sha256": prediction_manifest["aggregate_sha256"],
            "scoring_v1_manifest_sha256": _file_hash(
                scoring_v1_root / "heldout_scoring_manifest.json"
            ),
            "scoring_v1_aggregate_sha256": scoring_manifest["aggregate_sha256"],
            "public_sources_sha256": _file_hash(public_sources_path),
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "point_score_changes": 0,
            "model_selection_changes": 0,
            "additional_label_dependent_analyses": {
                "tdc_official_allowed_seed_evaluations": 9,
                "tdc_strict_allowed_seed_evaluations": 9,
                "octant_outer_allowed_seed_evaluations": 3,
                "total_allowed_seed_evaluations": 21,
            },
            "aggregation_boundary": (
                "Allowed-seed ranges score each of the three already-declared "
                "ExtraTrees seed predictions. The retained point score remains "
                "the metric of their mean prediction. Deterministic families "
                "have a one-value interval. No result selected a seed."
            ),
        },
    )
    return manifest_path


def complete_retained_mean_scorecard(
    scoring_root: Path,
    validation_root: Path,
    public_sources_path: Path,
    output_directory: Path,
    *,
    source_revision: str,
    selection_runtime_seconds: float,
    combination_runtime_seconds: float,
    prediction_runtime_seconds: float,
    mean_prediction_runtime_upper_bound_seconds: float,
    scoring_runtime_seconds: float,
    hardware: str,
) -> Path:
    """Complete the retained-mean scorecard without reopening held-out labels."""

    _require_new_directory(output_directory)
    scoring_manifest = _verify_manifest_outputs(
        scoring_root / "retained_mean_scoring_manifest.json", scoring_root
    )
    expected_counts = {
        "tdc_public_test_evaluations": 3,
        "tdc_strict_companion_analyses": 3,
        "octant_outer_evaluations": 1,
        "rejected_candidate_evaluations": 0,
        "model_fits": 0,
        "model_selection_changes": 0,
    }
    if (
        scoring_manifest.get("schema_version")
        != "cypshift.retained_mean_heldout_scoring.v1"
        or any(scoring_manifest.get(key) != value for key, value in expected_counts.items())
    ):
        raise NativeSelectionError("retained-mean scoring receipt is invalid")
    rows, original_columns = _read_csv_columns(scoring_root / "heldout_scores.csv")
    scored = _read_csv(scoring_root / "scored_retained_mean_predictions.csv")
    if (
        len(rows) != 7
        or len(scored) != scoring_manifest.get("heldout_labels_parsed")
        or {row.get("family") for row in rows} != {"unweighted_mean"}
    ):
        raise NativeSelectionError("retained-mean score population is invalid")
    sources = _read_json(public_sources_path)
    dataset_revisions = _dataset_revisions(sources)
    anchors = _anchor_statistics(sources)
    population_hashes = _population_hashes(scored)
    split_hashes = {
        "octant_cyp": _file_hash(
            validation_root / "octant" / "octant_grouped_split.csv"
        ),
        "tdc_admet_group": str(scoring_manifest["official_split_sha256"]),
    }
    completed_rows: list[dict[str, str]] = []
    for row in rows:
        benchmark = row["benchmark"]
        task = row["task"]
        population = row["population"]
        point = float(row["primary_value"])
        reference = anchors.get(task, {}) if population == "official" else {}
        completed = dict(row)
        completed.update(
            {
                "dataset_revision": dataset_revisions[benchmark],
                "split_sha256": split_hashes[benchmark],
                "population_sha256": population_hashes[
                    (benchmark, task, population)
                ],
                "native_seed_policy": (
                    "fixed_unweighted_mean_of_four_frozen_family_predictions"
                ),
                "native_seed_count": "1",
                "native_seed_primary_values": _number(point),
                "native_seed_primary_min": _number(point),
                "native_seed_primary_max": _number(point),
                "native_seed_primary_std": "0",
                "maplight_gnn_std": _reference_std(reference, "MapLight + GNN"),
                "chemprop_rdkit_std": _reference_std(
                    reference, "Chemprop-RDKit"
                ),
                "chemprop_std": _reference_std(reference, "Chemprop"),
                "delta_vs_chemprop_rdkit": _delta(
                    point, reference, "Chemprop-RDKit"
                ),
                "delta_vs_chemprop": _delta(point, reference, "Chemprop"),
                "selection_runtime_seconds": _number(selection_runtime_seconds),
                "heldout_prediction_runtime_seconds": _number(
                    prediction_runtime_seconds
                ),
                "scoring_runtime_seconds": _number(scoring_runtime_seconds),
                "hardware": hardware,
                "comparison_status": _comparison_status(benchmark, population),
                "contamination_warning": _contamination_warning(
                    benchmark, task, population
                ),
                "aggregation_warning": (
                    "The fixed cypshift mean is compared with published "
                    "leaderboard mean+/-SD values; aggregation differs."
                    if population == "official"
                    else "No public leaderboard delta is asserted."
                ),
            }
        )
        completed_rows.append(completed)

    output_directory.mkdir(parents=True)
    columns = (*original_columns, *SCORECARD_ADDITIONAL_COLUMNS)
    csv_path = output_directory / "scorecard.csv"
    _write_csv(csv_path, columns, completed_rows)
    json_path = output_directory / "scorecard.json"
    _write_json(
        json_path,
        {
            "schema_version": RETAINED_MEAN_SCORECARD_SCHEMA_VERSION,
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "rows": completed_rows,
        },
    )
    outputs = {
        csv_path.name: _file_hash(csv_path),
        json_path.name: _file_hash(json_path),
    }
    manifest_path = output_directory / "scorecard_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": RETAINED_MEAN_SCORECARD_SCHEMA_VERSION,
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "source_revision": source_revision,
            "package_version": metadata.version("cypshift"),
            "scoring_manifest_sha256": _file_hash(
                scoring_root / "retained_mean_scoring_manifest.json"
            ),
            "scoring_aggregate_sha256": scoring_manifest["aggregate_sha256"],
            "public_sources_sha256": _file_hash(public_sources_path),
            "outputs": outputs,
            "aggregate_recipe": AGGREGATE_RECIPE,
            "aggregate_sha256": _hash_mapping(outputs),
            "rows": len(completed_rows),
            "point_score_changes": 0,
            "model_selection_changes": 0,
            "additional_heldout_label_access": 0,
            "additional_heldout_evaluations": 0,
            "combination_selection_runtime_seconds": _number(
                combination_runtime_seconds
            ),
            "retained_mean_prediction_runtime_upper_bound_seconds": _number(
                mean_prediction_runtime_upper_bound_seconds
            ),
            "runtime_boundary": (
                "Scorecard row selection and prediction runtimes are the frozen "
                "base-family stages. The manifest separately records combination "
                "selection and retained-mean arithmetic."
            ),
        },
    )
    return manifest_path


def _require_new_directory(path: Path) -> None:
    if path.exists():
        raise NativeSelectionError(f"output path already exists: {path}")


def _verify_manifest_outputs(manifest_path: Path, root: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise NativeSelectionError(f"manifest outputs are invalid: {manifest_path}")
    for name, expected in outputs.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise NativeSelectionError("manifest output entry is invalid")
        if _file_hash(root / name) != expected:
            raise NativeSelectionError(f"manifest output hash mismatch: {name}")
    expected_aggregate = _hash_mapping({str(k): str(v) for k, v in outputs.items()})
    if manifest.get("aggregate_sha256") != expected_aggregate:
        raise NativeSelectionError("manifest aggregate hash mismatch")
    return manifest


def _hash_mapping(values: Mapping[str, str]) -> str:
    material = "\n".join(f"{name}={values[name]}" for name in sorted(values))
    return sha256(material.encode()).hexdigest()


def _split_metadata(
    rows_by_benchmark: Mapping[str, Sequence[Mapping[str, str]]],
) -> tuple[
    dict[tuple[str, str, str], tuple[str, int]],
    dict[tuple[str, str, str, int], int],
]:
    metadata_rows: dict[tuple[str, str, str], tuple[str, int]] = {}
    counts: Counter[tuple[str, str, str, int]] = Counter()
    totals: Counter[tuple[str, str, str]] = Counter()
    for benchmark, rows in rows_by_benchmark.items():
        for row in rows:
            fold_text = row.get("inner_fold", "")
            if not fold_text:
                continue
            task = (
                row.get("task", "")
                if benchmark == "tdc_admet_group"
                else "cyp3a4_active_preincubation_pIC50"
            )
            molecule_id = row.get("molecule_id", "")
            group_hash = row.get("group_hash", "")
            fold = int(fold_text)
            metadata_rows[(benchmark, task, molecule_id)] = (group_hash, fold)
            counts[(benchmark, task, group_hash, fold)] += 1
            totals[(benchmark, task, group_hash)] += 1
    support = {
        key: totals[key[:3]] - count for key, count in counts.items()
    }
    return metadata_rows, support


def _measurement_quality(path: Path) -> dict[str, str]:
    return {row["molecule_id"]: row.get("quality", "not_reported") for row in _read_csv(path)}


def _prediction_uncertainty(
    rows: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str, str, str], float]:
    grouped: dict[tuple[str, str, str, str], list[float]] = {}
    for row in rows:
        key = (row["benchmark"], row["task"], row["molecule_id"], row["family"])
        grouped.setdefault(key, []).append(float(row["prediction"]))
    if any(len(values) != 3 for values in grouped.values()):
        raise NativeSelectionError("stochastic OOF rows do not contain three seeds")
    return {key: pstdev(values) for key, values in grouped.items()}


def _configuration_hashes(
    retained_models: Mapping[str, Any],
) -> dict[tuple[str, str, str], str]:
    result: dict[tuple[str, str, str], str] = {}
    datasets = retained_models.get("datasets")
    if not isinstance(datasets, list):
        raise NativeSelectionError("retained model datasets are invalid")
    for dataset in datasets:
        if not isinstance(dataset, dict) or not isinstance(dataset.get("families"), list):
            raise NativeSelectionError("retained model dataset is invalid")
        for family in dataset["families"]:
            if not isinstance(family, dict) or not isinstance(
                family.get("configuration"), dict
            ):
                raise NativeSelectionError("retained model family is invalid")
            material = json.dumps(
                family["configuration"], sort_keys=True, separators=(",", ":")
            )
            result[
                (
                    str(dataset["benchmark"]),
                    str(dataset["task"]),
                    str(family["family"]),
                )
            ] = sha256(material.encode()).hexdigest()
    return result


def _assert_prediction_alignment(scored_path: Path, prediction_path: Path) -> None:
    scored = _read_csv(scored_path)
    predictions = _read_csv(prediction_path)
    projected = [
        {column: row[column] for column in HELDOUT_COLUMNS} for row in scored
    ]
    if projected != predictions:
        raise NativeSelectionError("v2 predictions do not match scored v1 predictions")


def _read_csv_columns(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise NativeSelectionError(f"CSV has no header: {path}")
        return list(reader), tuple(reader.fieldnames)


def _heldout_seed_primary_values(
    score_rows: Sequence[Mapping[str, str]],
    scored_rows: Sequence[Mapping[str, str]],
    seed_rows: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str, str, str], tuple[float, ...]]:
    labels = {
        (row["benchmark"], row["task"], row["molecule_id"]): float(row["target"])
        for row in scored_rows
    }
    excluded = {
        (row["benchmark"], row["task"], row["molecule_id"])
        for row in scored_rows
        if row["strict_excluded"] == "true"
    }
    by_seed: dict[tuple[str, str, str], list[Mapping[str, str]]] = {}
    for row in seed_rows:
        by_seed.setdefault((row["benchmark"], row["task"], row["seed"]), []).append(row)
    result: dict[tuple[str, str, str, str], tuple[float, ...]] = {}
    for score in score_rows:
        benchmark = score["benchmark"]
        task = score["task"]
        population = score["population"]
        family = score["family"]
        key = (benchmark, task, population, family)
        if family != "extra_trees":
            result[key] = (float(score["primary_value"]),)
            continue
        values = []
        for seed_key in sorted(k for k in by_seed if k[:2] == (benchmark, task)):
            members = by_seed[seed_key]
            if population == "strict":
                members = [
                    row
                    for row in members
                    if (benchmark, task, row["molecule_id"]) not in excluded
                ]
            targets = [labels[(benchmark, task, row["molecule_id"])] for row in members]
            predictions = [float(row["prediction"]) for row in members]
            if benchmark == "tdc_admet_group":
                values.append(average_precision([int(v) for v in targets], predictions))
            else:
                values.append(
                    sum(abs(a - b) for a, b in zip(targets, predictions, strict=True))
                    / len(targets)
                )
        if len(values) != 3:
            raise NativeSelectionError("held-out seed interval requires three seeds")
        result[key] = tuple(values)
    return result


def _dataset_revisions(sources: Mapping[str, Any]) -> dict[str, str]:
    try:
        octant = sources["sources"]["octant_cyp"]
        tdc = sources["sources"]["tdc_admet"]
        archive = tdc["archive"]
        return {
            "octant_cyp": str(octant["revision"]),
            "tdc_admet_group": (
                f"{archive['dataset_persistent_id']}@{archive['dataset_version']};"
                f"sha256={archive['sha256']}"
            ),
        }
    except (KeyError, TypeError) as exc:
        raise NativeSelectionError("public dataset revisions are invalid") from exc


def _anchor_statistics(sources: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        return dict(sources["sources"]["tdc_leaderboards"]["pages"])
    except (KeyError, TypeError) as exc:
        raise NativeSelectionError("public anchor statistics are invalid") from exc


def _population_hashes(
    rows: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str, str], str]:
    populations: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        benchmark = row["benchmark"]
        task = row["task"]
        molecule_id = row["molecule_id"]
        population = "outer_validation" if benchmark == "octant_cyp" else "official"
        populations.setdefault((benchmark, task, population), set()).add(molecule_id)
        if benchmark == "tdc_admet_group" and row["strict_excluded"] != "true":
            populations.setdefault((benchmark, task, "strict"), set()).add(molecule_id)
    return {
        key: sha256("\n".join(sorted(ids)).encode()).hexdigest()
        for key, ids in populations.items()
    }


def _reference_std(reference: Mapping[str, Any], name: str) -> str:
    entry = reference.get("anchors", {}).get(name) if reference else None
    return "" if not isinstance(entry, dict) else _number(float(entry["std"]))


def _delta(point: float, reference: Mapping[str, Any], name: str) -> str:
    entry = reference.get("anchors", {}).get(name) if reference else None
    return "" if not isinstance(entry, dict) else _number(point - float(entry["mean"]))


def _comparison_status(benchmark: str, population: str) -> str:
    if benchmark == "octant_cyp":
        return "internally_reproduced_same_split_unofficial"
    return (
        "official_fixed_public_test_comparison"
        if population == "official"
        else "unofficial_strict_companion"
    )


def _contamination_warning(benchmark: str, task: str, population: str) -> str:
    if benchmark != "tdc_admet_group":
        return "no official leaderboard comparison"
    task_counts = {
        "cyp2c9_veith": 4,
        "cyp2d6_veith": 2,
        "cyp3a4_veith": 1,
    }
    count = task_counts.get(task)
    if count is None:
        raise NativeSelectionError(f"unknown TDC task for contamination warning: {task}")
    disposition = "retained" if population == "official" else "excluded"
    row_word = "row" if count == 1 else "rows"
    return (
        f"{count} task-specific standardized overlap {row_word} {disposition}; "
        "seven across all three tasks"
    )


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
