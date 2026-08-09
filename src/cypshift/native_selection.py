"""Frozen train/validation-only selection for the Phase 0.5 native ladder."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module, metadata
from pathlib import Path
from statistics import median
from typing import Any, Literal

from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from cypshift.metrics import AUPRC_DIRECTION, average_precision
from cypshift.tdc import TDC_TASKS

SELECTION_SCHEMA_VERSION = "cypshift.native_selection.v1"
SEED = 20260809
STOCHASTIC_SEEDS = (SEED, SEED + 1, SEED + 2)
FINGERPRINT_RADIUS = 2
FINGERPRINT_BITS = 2048
FAMILIES = ("prior", "ecfp_linear", "similarity_knn", "extra_trees")
PREDICTION_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "inner_fold",
    "family",
    "configuration_id",
    "seed",
    "prediction",
    "target",
    "standardized_structure_hash",
    "nearest_neighbor_similarity",
    "local_support_count",
    "local_label_variance",
)
SCORE_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "family",
    "configuration_id",
    "score_role",
    "seed_policy",
    "primary_metric",
    "direction",
    "value",
    "rows",
)

ProblemType = Literal["classification", "regression"]


class NativeSelectionError(ValueError):
    """Raised when selection would violate a frozen data or split contract."""


@dataclass(frozen=True, slots=True)
class SelectionDataset:
    """One task restricted to rows authorized for grouped inner selection."""

    benchmark: str
    task: str
    problem_type: ProblemType
    molecule_ids: tuple[str, ...]
    structures: tuple[str, ...]
    structure_hashes: tuple[str, ...]
    targets: tuple[float, ...]
    folds: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PredictionSet:
    """Aligned OOF predictions and optional local-neighborhood diagnostics."""

    predictions: tuple[float, ...]
    nearest_similarity: tuple[float | None, ...]
    support_count: tuple[int | None, ...]
    local_variance: tuple[float | None, ...]


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Paths and counts for one immutable native-selection run."""

    manifest_path: Path
    retained_models_path: Path
    retained_predictions_path: Path
    row_count: int
    model_fit_count: int


def run_native_selection(
    octant_canonical: Path,
    tdc_canonical: Path,
    validation_root: Path,
    output_directory: Path,
    *,
    seed: int = SEED,
    nonlinear_trees: int = 128,
) -> SelectionResult:
    """Select four native families using grouped inner folds and no held-out labels."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. "
            "Selection artifacts are immutable."
        )
    if nonlinear_trees < 1:
        raise NativeSelectionError("nonlinear_trees must be positive")
    if seed != SEED:
        raise NativeSelectionError(f"native selection seed is frozen at {SEED}")

    verified_inputs = _verify_input_receipts(
        octant_canonical, tdc_canonical, validation_root
    )
    datasets = [
        _load_octant_selection(
            octant_canonical,
            validation_root / "octant" / "octant_grouped_split.csv",
        ),
        *_load_tdc_selections(
            tdc_canonical,
            validation_root / "tdc" / "tdc_inner_folds.csv",
        ),
    ]
    output_directory.mkdir(parents=True)
    candidate_path = output_directory / "candidate_oof_predictions.csv"
    retained_path = output_directory / "retained_oof_predictions.csv"
    stochastic_path = output_directory / "retained_stochastic_seed_predictions.csv"
    scores_path = output_directory / "selection_scores.csv"
    retained_models_path = output_directory / "retained_models.json"
    manifest_path = output_directory / "selection_manifest.json"

    score_rows: list[dict[str, str]] = []
    retained_datasets: list[dict[str, Any]] = []
    model_fit_count = 0
    retained_row_count = 0
    with (
        candidate_path.open("x", encoding="utf-8", newline="") as candidate_file,
        retained_path.open("x", encoding="utf-8", newline="") as retained_file,
        stochastic_path.open("x", encoding="utf-8", newline="") as stochastic_file,
    ):
        candidate_writer = csv.DictWriter(
            candidate_file, fieldnames=PREDICTION_COLUMNS, lineterminator="\n"
        )
        retained_writer = csv.DictWriter(
            retained_file, fieldnames=PREDICTION_COLUMNS, lineterminator="\n"
        )
        stochastic_writer = csv.DictWriter(
            stochastic_file, fieldnames=PREDICTION_COLUMNS, lineterminator="\n"
        )
        candidate_writer.writeheader()
        retained_writer.writeheader()
        stochastic_writer.writeheader()
        for dataset in datasets:
            result = _select_dataset(
                dataset,
                candidate_writer,
                retained_writer,
                stochastic_writer,
                seed=seed,
                nonlinear_trees=nonlinear_trees,
            )
            score_rows.extend(result["scores"])
            retained_datasets.append(result["retained"])
            model_fit_count += result["model_fits"]
            retained_row_count += len(dataset.molecule_ids) * len(FAMILIES)

    _write_csv(scores_path, SCORE_COLUMNS, score_rows)
    retained_models = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "selection_policy": (
            "Grouped inner-fold evidence only. Octant outer validation and TDC "
            "public-test labels are neither parsed nor evaluated."
        ),
        "seed": seed,
        "stochastic_seeds": list(STOCHASTIC_SEEDS),
        "fingerprint": {
            "type": "Morgan/ECFP",
            "radius": FINGERPRINT_RADIUS,
            "diameter": 2 * FINGERPRINT_RADIUS,
            "bits": FINGERPRINT_BITS,
            "include_chirality": True,
        },
        "nonlinear_estimator": {
            "name": "ExtraTreesClassifier/ExtraTreesRegressor",
            "n_estimators": nonlinear_trees,
            "n_jobs": 1,
        },
        "datasets": retained_datasets,
        "public_test_labels_parsed": 0,
        "public_test_evaluations": 0,
        "octant_outer_labels_parsed": 0,
        "octant_outer_evaluations": 0,
    }
    _write_json(retained_models_path, retained_models)
    outputs = {
        candidate_path.name: _file_hash(candidate_path),
        retained_path.name: _file_hash(retained_path),
        stochastic_path.name: _file_hash(stochastic_path),
        scores_path.name: _file_hash(scores_path),
        retained_models_path.name: _file_hash(retained_models_path),
    }
    aggregate_material = "\n".join(
        f"{name}={outputs[name]}" for name in sorted(outputs)
    )
    manifest = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "seed": seed,
        "input_hashes": verified_inputs,
        "outputs": outputs,
        "aggregate_recipe": (
            "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined "
            "with newline characters, without a trailing newline"
        ),
        "aggregate_sha256": sha256(aggregate_material.encode()).hexdigest(),
        "packages": {
            "numpy": metadata.version("numpy"),
            "rdkit": metadata.version("rdkit"),
            "scikit-learn": metadata.version("scikit-learn"),
            "scipy": metadata.version("scipy"),
        },
        "datasets": len(datasets),
        "selection_rows": sum(len(dataset.molecule_ids) for dataset in datasets),
        "retained_prediction_rows": retained_row_count,
        "model_fits": model_fit_count,
        "public_test_labels_parsed": 0,
        "public_test_evaluations": 0,
        "octant_outer_labels_parsed": 0,
        "octant_outer_evaluations": 0,
    }
    _write_json(manifest_path, manifest)
    return SelectionResult(
        manifest_path=manifest_path,
        retained_models_path=retained_models_path,
        retained_predictions_path=retained_path,
        row_count=retained_row_count,
        model_fit_count=model_fit_count,
    )


def _select_dataset(
    dataset: SelectionDataset,
    candidate_writer: Any,
    retained_writer: Any,
    stochastic_writer: Any,
    *,
    seed: int,
    nonlinear_trees: int,
) -> dict[str, Any]:
    fingerprints, matrix = _fingerprints(dataset.structures)
    configurations = _configurations(dataset.problem_type, nonlinear_trees)
    predictions_by_family: dict[str, dict[str, PredictionSet]] = {
        family: {} for family in FAMILIES
    }
    fits = 0

    prior_config = configurations["prior"][0]
    prior_predictions = _oof_prior(dataset)
    predictions_by_family["prior"][prior_config["id"]] = prior_predictions
    fits += len(set(dataset.folds))

    for config in configurations["ecfp_linear"]:
        prediction_set = _oof_linear(dataset, matrix, config, seed)
        predictions_by_family["ecfp_linear"][config["id"]] = prediction_set
        fits += len(set(dataset.folds))

    knn_results = _oof_knn(dataset, fingerprints, configurations["similarity_knn"])
    predictions_by_family["similarity_knn"].update(knn_results)
    fits += len(configurations["similarity_knn"]) * len(set(dataset.folds))

    for config in configurations["extra_trees"]:
        prediction_set = _oof_extra_trees(dataset, matrix, config, seed)
        predictions_by_family["extra_trees"][config["id"]] = prediction_set
        fits += len(set(dataset.folds))

    scores: list[dict[str, str]] = []
    retained_families: list[dict[str, Any]] = []
    config_by_id = {
        config["id"]: config
        for family_configs in configurations.values()
        for config in family_configs
    }
    for family in FAMILIES:
        family_predictions = predictions_by_family[family]
        family_scores: dict[str, float] = {}
        for configuration_id, prediction_set in family_predictions.items():
            score = _primary_score(dataset, prediction_set.predictions)
            family_scores[configuration_id] = score
            scores.append(
                _score_row(
                    dataset,
                    family,
                    configuration_id,
                    "candidate",
                    "canonical_seed" if family == "extra_trees" else "deterministic",
                    score,
                )
            )
            _write_prediction_rows(
                candidate_writer,
                dataset,
                family,
                configuration_id,
                str(seed) if family == "extra_trees" else "not_applicable",
                prediction_set,
            )

        retained_id = _best_configuration(dataset.problem_type, family_scores)
        retained_prediction_set = family_predictions[retained_id]
        seed_policy = "deterministic"
        if family == "extra_trees":
            seed_sets = []
            for stochastic_seed in STOCHASTIC_SEEDS:
                if stochastic_seed == seed:
                    seed_set = retained_prediction_set
                else:
                    seed_set = _oof_extra_trees(
                        dataset,
                        matrix,
                        config_by_id[retained_id],
                        stochastic_seed,
                    )
                    fits += len(set(dataset.folds))
                seed_sets.append(seed_set)
                _write_prediction_rows(
                    stochastic_writer,
                    dataset,
                    family,
                    retained_id,
                    str(stochastic_seed),
                    seed_set,
                )
            retained_prediction_set = _mean_prediction_sets(seed_sets)
            seed_policy = "mean_of_three_predeclared_seeds"

        retained_score = _primary_score(
            dataset, retained_prediction_set.predictions
        )
        scores.append(
            _score_row(
                dataset,
                family,
                retained_id,
                "retained",
                seed_policy,
                retained_score,
            )
        )
        _write_prediction_rows(
            retained_writer,
            dataset,
            family,
            retained_id,
            "ensemble" if family == "extra_trees" else "not_applicable",
            retained_prediction_set,
        )
        retained_families.append(
            {
                "family": family,
                "configuration": config_by_id[retained_id],
                "selection_metric": _primary_metric(dataset.problem_type),
                "direction": _primary_direction(dataset.problem_type),
                "candidate_selection_value": family_scores[retained_id],
                "retained_oof_value": retained_score,
                "seed_policy": seed_policy,
            }
        )

    return {
        "scores": scores,
        "model_fits": fits,
        "retained": {
            "benchmark": dataset.benchmark,
            "task": dataset.task,
            "problem_type": dataset.problem_type,
            "selection_rows": len(dataset.molecule_ids),
            "inner_folds": sorted(set(dataset.folds)),
            "families": retained_families,
        },
    }


def _load_octant_selection(
    canonical_directory: Path, split_path: Path
) -> SelectionDataset:
    split_rows = _read_csv(split_path)
    selected: dict[str, int] = {}
    for row in split_rows:
        if row.get("outer_partition") != "train":
            continue
        if row.get("has_measurement") != "true":
            continue
        molecule_id = _required(row, "molecule_id", split_path)
        selected[molecule_id] = _fold(row, split_path)
    if not selected:
        raise NativeSelectionError("Octant selection contains no measured train rows")
    return _load_dataset(
        canonical_directory,
        selected,
        benchmark="octant_cyp",
        task="cyp3a4_active_preincubation_pIC50",
        problem_type="regression",
    )


def _load_tdc_selections(
    canonical_directory: Path, inner_folds_path: Path
) -> list[SelectionDataset]:
    selected_by_task: dict[str, dict[str, int]] = {task: {} for task in TDC_TASKS}
    for row in _read_csv(inner_folds_path):
        task = _required(row, "task", inner_folds_path)
        if task not in selected_by_task:
            raise NativeSelectionError(f"unexpected TDC task in inner folds: {task}")
        molecule_id = _required(row, "molecule_id", inner_folds_path)
        if molecule_id in selected_by_task[task]:
            raise NativeSelectionError(f"duplicate TDC inner-fold row: {molecule_id}")
        selected_by_task[task][molecule_id] = _fold(row, inner_folds_path)
    return [
        _load_dataset(
            canonical_directory,
            selected_by_task[task],
            benchmark="tdc_admet_group",
            task=task,
            problem_type="classification",
        )
        for task in TDC_TASKS
    ]


def _load_dataset(
    canonical_directory: Path,
    selected: Mapping[str, int],
    *,
    benchmark: str,
    task: str,
    problem_type: ProblemType,
) -> SelectionDataset:
    if set(selected.values()) != {0, 1, 2, 3}:
        raise NativeSelectionError(
            f"{benchmark}/{task} must contain exactly inner folds 0, 1, 2, 3"
        )
    molecules: dict[str, tuple[str, str]] = {}
    molecules_path = canonical_directory / "molecules.csv"
    for row in _read_csv(molecules_path):
        molecule_id = row.get("molecule_id", "")
        if molecule_id not in selected:
            continue
        if row.get("status") != "accepted":
            raise NativeSelectionError(f"selection molecule is not accepted: {molecule_id}")
        structure = _required(row, "standardized_structure", molecules_path)
        structure_hash = _required(
            row, "standardized_structure_hash", molecules_path
        )
        if molecule_id in molecules:
            raise NativeSelectionError(f"duplicate canonical molecule: {molecule_id}")
        molecules[molecule_id] = (structure, structure_hash)

    targets: dict[str, float] = {}
    measurements_path = canonical_directory / "measurements.csv"
    for row in _read_csv(measurements_path):
        molecule_id = row.get("molecule_id", "")
        if molecule_id not in selected:
            continue
        if molecule_id in targets:
            raise NativeSelectionError(
                f"selection expects one measurement per molecule: {molecule_id}"
            )
        try:
            value = float(_required(row, "value", measurements_path))
        except ValueError as exc:
            raise NativeSelectionError(
                f"selection measurement is not numeric: {molecule_id}"
            ) from exc
        if not math.isfinite(value):
            raise NativeSelectionError(
                f"selection measurement is not finite: {molecule_id}"
            )
        if problem_type == "classification" and value not in {0.0, 1.0}:
            raise NativeSelectionError(
                f"classification target is not binary: {molecule_id}"
            )
        targets[molecule_id] = value

    missing_molecules = sorted(set(selected) - set(molecules))
    missing_targets = sorted(set(selected) - set(targets))
    if missing_molecules or missing_targets:
        raise NativeSelectionError(
            f"selection alignment failed for {benchmark}/{task}: "
            f"missing molecules={len(missing_molecules)}, "
            f"missing targets={len(missing_targets)}"
        )
    molecule_ids = tuple(sorted(selected))
    dataset = SelectionDataset(
        benchmark=benchmark,
        task=task,
        problem_type=problem_type,
        molecule_ids=molecule_ids,
        structures=tuple(molecules[item][0] for item in molecule_ids),
        structure_hashes=tuple(molecules[item][1] for item in molecule_ids),
        targets=tuple(targets[item] for item in molecule_ids),
        folds=tuple(selected[item] for item in molecule_ids),
    )
    _validate_fold_targets(dataset)
    return dataset


def _validate_fold_targets(dataset: SelectionDataset) -> None:
    for held_out in sorted(set(dataset.folds)):
        training_targets = [
            target
            for target, fold in zip(dataset.targets, dataset.folds, strict=True)
            if fold != held_out
        ]
        if not training_targets:
            raise NativeSelectionError("inner fold leaves no training rows")
        if dataset.problem_type == "classification" and set(training_targets) != {
            0.0,
            1.0,
        }:
            raise NativeSelectionError(
                f"classification training fold lacks both classes: {dataset.task}"
            )


def _verify_input_receipts(
    octant_canonical: Path, tdc_canonical: Path, validation_root: Path
) -> dict[str, str]:
    root_path = validation_root / "public_validation_manifest.json"
    root = _read_json(root_path)
    if root.get("schema_version") != "cypshift.public_validation_freeze.v1":
        raise NativeSelectionError("unsupported public-validation manifest schema")
    outputs = root.get("outputs")
    if not isinstance(outputs, dict):
        raise NativeSelectionError("public-validation outputs must be an object")
    required_outputs = {
        "octant/octant_grouped_split.csv",
        "octant/split_manifest.json",
        "tdc/tdc_inner_folds.csv",
        "tdc/tdc_split_audit.json",
    }
    if not required_outputs.issubset(outputs):
        missing = sorted(required_outputs - set(outputs))
        raise NativeSelectionError(
            "public-validation manifest lacks required outputs: " + ", ".join(missing)
        )
    verified: dict[str, str] = {
        "validation/public_validation_manifest.json": _file_hash(root_path)
    }
    for relative_name, expected_hash in sorted(outputs.items()):
        if (
            not isinstance(relative_name, str)
            or not isinstance(expected_hash, str)
            or Path(relative_name).is_absolute()
            or ".." in Path(relative_name).parts
        ):
            raise NativeSelectionError("public-validation output entry is invalid")
        actual_hash = _file_hash(validation_root / relative_name)
        if actual_hash != expected_hash:
            raise NativeSelectionError(
                f"public-validation output hash mismatch: {relative_name}"
            )
        verified[f"validation/{relative_name}"] = actual_hash
    aggregate_material = "\n".join(
        f"{name}={outputs[name]}" for name in sorted(outputs)
    )
    if sha256(aggregate_material.encode()).hexdigest() != root.get(
        "aggregate_sha256"
    ):
        raise NativeSelectionError("public-validation aggregate hash mismatch")

    octant_manifest = _read_json(validation_root / "octant" / "split_manifest.json")
    tdc_audit = _read_json(validation_root / "tdc" / "tdc_split_audit.json")
    for prefix, canonical, receipt in (
        ("octant", octant_canonical, octant_manifest),
        ("tdc", tdc_canonical, tdc_audit),
    ):
        input_hashes = receipt.get("input_hashes")
        if not isinstance(input_hashes, dict):
            raise NativeSelectionError(f"{prefix} receipt input hashes must be an object")
        for filename in ("molecules.csv", "measurements.csv"):
            expected_hash = input_hashes.get(filename)
            actual_hash = _file_hash(canonical / filename)
            if expected_hash != actual_hash:
                raise NativeSelectionError(
                    f"{prefix} canonical hash does not match validation receipt: "
                    f"{filename}"
                )
            verified[f"{prefix}/{filename}"] = actual_hash
    return dict(sorted(verified.items()))


def _configurations(
    problem_type: ProblemType, nonlinear_trees: int
) -> dict[str, list[dict[str, Any]]]:
    linear = (
        [
            {"id": f"ecfp-logistic-c{value:g}", "C": value}
            for value in (0.1, 1.0, 10.0)
        ]
        if problem_type == "classification"
        else [
            {"id": f"ecfp-ridge-a{value:g}", "alpha": value}
            for value in (0.1, 1.0, 10.0)
        ]
    )
    return {
        "prior": [
            {
                "id": (
                    "training-prevalence"
                    if problem_type == "classification"
                    else "training-median"
                )
            }
        ],
        "ecfp_linear": linear,
        "similarity_knn": [
            {
                "id": f"tanimoto-k{k:02d}-p{power}",
                "neighbors": k,
                "similarity_power": power,
            }
            for k in (5, 15, 50)
            for power in (1, 2)
        ],
        "extra_trees": [
            {
                "id": f"extra-trees-leaf{leaf}",
                "n_estimators": nonlinear_trees,
                "min_samples_leaf": leaf,
                "max_features": "sqrt",
                "class_weight": (
                    "balanced" if problem_type == "classification" else None
                ),
            }
            for leaf in (1, 3, 10)
        ],
    }


def _fingerprints(structures: Sequence[str]) -> tuple[list[Any], Any]:
    np = import_module("numpy")
    sparse = import_module("scipy.sparse")
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=FINGERPRINT_RADIUS,
        fpSize=FINGERPRINT_BITS,
        includeChirality=True,
    )
    fingerprints = []
    rows: list[int] = []
    columns: list[int] = []
    for row_index, structure in enumerate(structures):
        molecule = Chem.MolFromSmiles(structure)
        if molecule is None:
            raise NativeSelectionError(
                "audited standardized structure cannot be fingerprinted"
            )
        fingerprint = generator.GetFingerprint(molecule)
        fingerprints.append(fingerprint)
        on_bits = list(fingerprint.GetOnBits())
        rows.extend([row_index] * len(on_bits))
        columns.extend(on_bits)
    values = np.ones(len(rows), dtype=np.float64)
    matrix = sparse.csr_matrix(
        (values, (rows, columns)), shape=(len(structures), FINGERPRINT_BITS)
    )
    return fingerprints, matrix


def _oof_prior(dataset: SelectionDataset) -> PredictionSet:
    predictions = [0.0] * len(dataset.targets)
    for fold in sorted(set(dataset.folds)):
        train = [
            target
            for target, item_fold in zip(
                dataset.targets, dataset.folds, strict=True
            )
            if item_fold != fold
        ]
        prior = (
            sum(train) / len(train)
            if dataset.problem_type == "classification"
            else median(train)
        )
        for index, item_fold in enumerate(dataset.folds):
            if item_fold == fold:
                predictions[index] = prior
    return _plain_predictions(predictions)


def _oof_linear(
    dataset: SelectionDataset, matrix: Any, config: Mapping[str, Any], seed: int
) -> PredictionSet:
    np = import_module("numpy")
    linear_model = import_module("sklearn.linear_model")
    targets = np.asarray(dataset.targets, dtype=np.float64)
    predictions = np.empty(len(dataset.targets), dtype=np.float64)
    for fold in sorted(set(dataset.folds)):
        train = np.asarray([item != fold for item in dataset.folds], dtype=bool)
        valid = ~train
        if dataset.problem_type == "classification":
            model = linear_model.LogisticRegression(
                C=float(config["C"]),
                l1_ratio=0.0,
                solver="liblinear",
                max_iter=2000,
                random_state=seed,
            )
            model.fit(matrix[train], targets[train])
            positive_index = list(model.classes_).index(1.0)
            predictions[valid] = model.predict_proba(matrix[valid])[:, positive_index]
        else:
            model = linear_model.Ridge(
                alpha=float(config["alpha"]), solver="lsqr", tol=1e-6
            )
            model.fit(matrix[train], targets[train])
            predictions[valid] = model.predict(matrix[valid])
    return _plain_predictions(predictions.tolist())


def _oof_knn(
    dataset: SelectionDataset,
    fingerprints: Sequence[Any],
    configurations: Sequence[Mapping[str, Any]],
) -> dict[str, PredictionSet]:
    predictions = {
        str(config["id"]): [0.0] * len(dataset.targets)
        for config in configurations
    }
    nearest = {
        str(config["id"]): [0.0] * len(dataset.targets)
        for config in configurations
    }
    support = {
        str(config["id"]): [0] * len(dataset.targets)
        for config in configurations
    }
    variance = {
        str(config["id"]): [0.0] * len(dataset.targets)
        for config in configurations
    }
    for fold in sorted(set(dataset.folds)):
        train_indices = [
            index for index, item_fold in enumerate(dataset.folds) if item_fold != fold
        ]
        train_fingerprints = [fingerprints[index] for index in train_indices]
        train_targets = [dataset.targets[index] for index in train_indices]
        fallback = (
            sum(train_targets) / len(train_targets)
            if dataset.problem_type == "classification"
            else median(train_targets)
        )
        for valid_index, item_fold in enumerate(dataset.folds):
            if item_fold != fold:
                continue
            similarities = DataStructs.BulkTanimotoSimilarity(
                fingerprints[valid_index], train_fingerprints
            )
            ordered = sorted(
                range(len(train_indices)),
                key=lambda item: (-similarities[item], train_indices[item]),
            )
            for config in configurations:
                configuration_id = str(config["id"])
                count = min(int(config["neighbors"]), len(ordered))
                selected = ordered[:count]
                weights = [
                    similarities[item] ** int(config["similarity_power"])
                    for item in selected
                ]
                weight_sum = sum(weights)
                labels = [train_targets[item] for item in selected]
                prediction = (
                    sum(
                        weight * train_targets[item]
                        for weight, item in zip(weights, selected, strict=True)
                    )
                    / weight_sum
                    if weight_sum > 0
                    else fallback
                )
                predictions[configuration_id][valid_index] = prediction
                nearest[configuration_id][valid_index] = (
                    similarities[selected[0]] if selected else 0.0
                )
                support[configuration_id][valid_index] = sum(
                    similarities[item] > 0 for item in selected
                )
                label_mean = sum(labels) / len(labels)
                variance[configuration_id][valid_index] = sum(
                    (label - label_mean) ** 2 for label in labels
                ) / len(labels)
    return {
        configuration_id: PredictionSet(
            predictions=tuple(values),
            nearest_similarity=tuple(nearest[configuration_id]),
            support_count=tuple(support[configuration_id]),
            local_variance=tuple(variance[configuration_id]),
        )
        for configuration_id, values in predictions.items()
    }


def _oof_extra_trees(
    dataset: SelectionDataset,
    matrix: Any,
    config: Mapping[str, Any],
    seed: int,
) -> PredictionSet:
    np = import_module("numpy")
    ensemble = import_module("sklearn.ensemble")
    targets = np.asarray(dataset.targets, dtype=np.float64)
    predictions = np.empty(len(dataset.targets), dtype=np.float64)
    for fold in sorted(set(dataset.folds)):
        train = np.asarray([item != fold for item in dataset.folds], dtype=bool)
        valid = ~train
        common = {
            "n_estimators": int(config["n_estimators"]),
            "min_samples_leaf": int(config["min_samples_leaf"]),
            "max_features": config["max_features"],
            "n_jobs": 1,
            "random_state": seed,
        }
        if dataset.problem_type == "classification":
            model = ensemble.ExtraTreesClassifier(
                **common, class_weight=config["class_weight"]
            )
            model.fit(matrix[train], targets[train])
            positive_index = list(model.classes_).index(1.0)
            predictions[valid] = model.predict_proba(matrix[valid])[:, positive_index]
        else:
            model = ensemble.ExtraTreesRegressor(**common)
            model.fit(matrix[train], targets[train])
            predictions[valid] = model.predict(matrix[valid])
    return _plain_predictions(predictions.tolist())


def _plain_predictions(values: Sequence[float]) -> PredictionSet:
    length = len(values)
    return PredictionSet(
        predictions=tuple(float(value) for value in values),
        nearest_similarity=(None,) * length,
        support_count=(None,) * length,
        local_variance=(None,) * length,
    )


def _mean_prediction_sets(prediction_sets: Sequence[PredictionSet]) -> PredictionSet:
    if not prediction_sets:
        raise NativeSelectionError("cannot average zero prediction sets")
    length = len(prediction_sets[0].predictions)
    if any(len(item.predictions) != length for item in prediction_sets):
        raise NativeSelectionError("stochastic prediction lengths differ")
    predictions = tuple(
        sum(item.predictions[index] for item in prediction_sets)
        / len(prediction_sets)
        for index in range(length)
    )
    return _plain_predictions(predictions)


def _primary_score(
    dataset: SelectionDataset, predictions: Sequence[float]
) -> float:
    if dataset.problem_type == "classification":
        return average_precision(
            [int(value) for value in dataset.targets], predictions
        )
    return sum(
        abs(target - prediction)
        for target, prediction in zip(dataset.targets, predictions, strict=True)
    ) / len(dataset.targets)


def _best_configuration(
    problem_type: ProblemType, scores: Mapping[str, float]
) -> str:
    if not scores:
        raise NativeSelectionError("family contains no configurations")
    if problem_type == "classification":
        return min(scores, key=lambda item: (-scores[item], item))
    return min(scores, key=lambda item: (scores[item], item))


def _primary_metric(problem_type: ProblemType) -> str:
    return "average_precision" if problem_type == "classification" else "mae"


def _primary_direction(problem_type: ProblemType) -> str:
    return AUPRC_DIRECTION if problem_type == "classification" else "lower_is_better"


def _score_row(
    dataset: SelectionDataset,
    family: str,
    configuration_id: str,
    score_role: str,
    seed_policy: str,
    score: float,
) -> dict[str, str]:
    return {
        "benchmark": dataset.benchmark,
        "task": dataset.task,
        "problem_type": dataset.problem_type,
        "family": family,
        "configuration_id": configuration_id,
        "score_role": score_role,
        "seed_policy": seed_policy,
        "primary_metric": _primary_metric(dataset.problem_type),
        "direction": _primary_direction(dataset.problem_type),
        "value": _number(score),
        "rows": str(len(dataset.molecule_ids)),
    }


def _write_prediction_rows(
    writer: Any,
    dataset: SelectionDataset,
    family: str,
    configuration_id: str,
    seed: str,
    prediction_set: PredictionSet,
) -> None:
    for index, molecule_id in enumerate(dataset.molecule_ids):
        writer.writerow(
            {
                "benchmark": dataset.benchmark,
                "task": dataset.task,
                "problem_type": dataset.problem_type,
                "molecule_id": molecule_id,
                "inner_fold": str(dataset.folds[index]),
                "family": family,
                "configuration_id": configuration_id,
                "seed": seed,
                "prediction": _number(prediction_set.predictions[index]),
                "target": _number(dataset.targets[index]),
                "standardized_structure_hash": dataset.structure_hashes[index],
                "nearest_neighbor_similarity": _optional_number(
                    prediction_set.nearest_similarity[index]
                ),
                "local_support_count": _optional_int(
                    prediction_set.support_count[index]
                ),
                "local_label_variance": _optional_number(
                    prediction_set.local_variance[index]
                ),
            }
        )


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise NativeSelectionError(f"cannot read {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NativeSelectionError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise NativeSelectionError(f"{path} must contain a JSON object")
    return value


def _required(row: Mapping[str, str], field: str, path: Path) -> str:
    value = row.get(field)
    if not value:
        raise NativeSelectionError(f"{path} requires nonempty field {field!r}")
    return value


def _fold(row: Mapping[str, str], path: Path) -> int:
    try:
        fold = int(_required(row, "inner_fold", path))
    except ValueError as exc:
        raise NativeSelectionError(f"{path} contains a non-integer inner fold") from exc
    if fold not in {0, 1, 2, 3}:
        raise NativeSelectionError(f"{path} inner fold must be 0, 1, 2, or 3")
    return fold


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise NativeSelectionError("prediction artifacts require finite numbers")
    return format(value, ".17g")


def _optional_number(value: float | None) -> str:
    return "" if value is None else _number(value)


def _optional_int(value: int | None) -> str:
    return "" if value is None else str(value)


__all__ = [
    "FAMILIES",
    "NativeSelectionError",
    "SELECTION_SCHEMA_VERSION",
    "SelectionResult",
    "run_native_selection",
]
