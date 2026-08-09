"""Receipt-bound held-out prediction without parsing held-out labels."""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from statistics import median
from typing import Any, Literal

from rdkit import DataStructs

from cypshift.metrics import average_precision
from cypshift.native_selection import (
    FAMILIES,
    SEED,
    SELECTION_SCHEMA_VERSION,
    STOCHASTIC_SEEDS,
    NativeSelectionError,
    PredictionSet,
    SelectionDataset,
    _file_hash,
    _fingerprints,
    _load_octant_selection,
    _load_tdc_selections,
    _mean_prediction_sets,
    _number,
    _read_csv,
    _read_json,
    _verify_input_receipts,
    _write_json,
)
from cypshift.tdc import TDC_TASKS

HELDOUT_PREDICTION_SCHEMA_VERSION = "cypshift.heldout_prediction.v1"
HELDOUT_COLUMNS = (
    "benchmark",
    "task",
    "problem_type",
    "molecule_id",
    "family",
    "configuration_id",
    "seed",
    "prediction",
    "standardized_structure_hash",
    "nearest_neighbor_similarity",
    "local_support_count",
    "local_label_variance",
)
SCORECARD_COLUMNS = (
    "benchmark", "task", "population", "family", "configuration_id", "rows",
    "prevalence", "threshold", "primary_metric", "primary_value",
    "average_precision", "auroc", "balanced_accuracy", "mcc", "brier",
    "ece_10_equal_width", "sensitivity", "specificity", "mae",
    "median_absolute_error", "rmse", "spearman", "interval_aware_mae",
    "potent_count", "potent_mae", "maplight_gnn", "chemprop_rdkit",
    "chemprop", "delta_vs_maplight_gnn", "comparability",
)
ProblemType = Literal["classification", "regression"]


@dataclass(frozen=True, slots=True)
class HeldoutDataset:
    """Structures authorized for prediction but not label access."""

    benchmark: str
    task: str
    problem_type: ProblemType
    molecule_ids: tuple[str, ...]
    structures: tuple[str, ...]
    structure_hashes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeldoutPredictionResult:
    """Immutable held-out predictions awaiting one separate scoring pass."""

    manifest_path: Path
    predictions_path: Path
    prediction_rows: int
    model_fits: int


@dataclass(frozen=True, slots=True)
class HeldoutScoringResult:
    """One immutable held-out scoring pass."""

    manifest_path: Path
    scorecard_path: Path
    tdc_evaluations: int
    octant_evaluations: int


def run_heldout_prediction(
    octant_canonical: Path,
    tdc_canonical: Path,
    tdc_official_split: Path,
    validation_root: Path,
    selection_root: Path,
    output_directory: Path,
) -> HeldoutPredictionResult:
    """Retrain frozen candidates and predict held-out structures without labels."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. "
            "Held-out prediction artifacts are immutable."
        )
    verified_inputs = _verify_input_receipts(
        octant_canonical, tdc_canonical, validation_root
    )
    selection_manifest, retained_models = _verify_selection_receipt(
        selection_root, verified_inputs
    )
    _verify_official_split(tdc_official_split, validation_root)
    training = [
        _load_octant_selection(
            octant_canonical,
            validation_root / "octant" / "octant_grouped_split.csv",
        ),
        *_load_tdc_selections(
            tdc_canonical,
            validation_root / "tdc" / "tdc_inner_folds.csv",
        ),
    ]
    heldout = [
        _load_octant_heldout(
            octant_canonical,
            validation_root / "octant" / "octant_grouped_split.csv",
        ),
        *_load_tdc_heldout(tdc_canonical, tdc_official_split),
    ]
    retained_configs = _retained_configurations(retained_models)
    if [(item.benchmark, item.task) for item in training] != [
        (item.benchmark, item.task) for item in heldout
    ]:
        raise NativeSelectionError("training and held-out task order differs")

    output_directory.mkdir(parents=True)
    predictions_path = output_directory / "heldout_predictions.csv"
    stochastic_path = output_directory / "heldout_stochastic_seed_predictions.csv"
    model_fits = 0
    prediction_rows = 0
    with (
        predictions_path.open("x", encoding="utf-8", newline="") as output_file,
        stochastic_path.open("x", encoding="utf-8", newline="") as seed_file,
    ):
        writer = csv.DictWriter(
            output_file, fieldnames=HELDOUT_COLUMNS, lineterminator="\n"
        )
        seed_writer = csv.DictWriter(
            seed_file, fieldnames=HELDOUT_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        seed_writer.writeheader()
        for train, test in zip(training, heldout, strict=True):
            configurations = retained_configs[(train.benchmark, train.task)]
            result = _predict_task(train, test, configurations)
            model_fits += result["model_fits"]
            for family in FAMILIES:
                prediction_set = result["retained"][family]
                _write_rows(
                    writer,
                    test,
                    family,
                    str(configurations[family]["id"]),
                    "ensemble" if family == "extra_trees" else "not_applicable",
                    prediction_set,
                )
                prediction_rows += len(test.molecule_ids)
            for seed, prediction_set in result["stochastic"]:
                _write_rows(
                    seed_writer,
                    test,
                    "extra_trees",
                    str(configurations["extra_trees"]["id"]),
                    str(seed),
                    prediction_set,
                )

    outputs = {
        predictions_path.name: _file_hash(predictions_path),
        stochastic_path.name: _file_hash(stochastic_path),
    }
    aggregate_material = "\n".join(
        f"{name}={outputs[name]}" for name in sorted(outputs)
    )
    manifest_path = output_directory / "heldout_prediction_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": HELDOUT_PREDICTION_SCHEMA_VERSION,
            "selection_schema_version": SELECTION_SCHEMA_VERSION,
            "selection_aggregate_sha256": selection_manifest["aggregate_sha256"],
            "selection_manifest_sha256": _file_hash(
                selection_root / "selection_manifest.json"
            ),
            "official_split_sha256": _file_hash(tdc_official_split),
            "outputs": outputs,
            "aggregate_recipe": (
                "SHA-256 of UTF-8 path=sha256 lines sorted by path and joined "
                "with newline characters, without a trailing newline"
            ),
            "aggregate_sha256": sha256(aggregate_material.encode()).hexdigest(),
            "tasks": len(heldout),
            "heldout_structures": sum(len(item.molecule_ids) for item in heldout),
            "prediction_rows": prediction_rows,
            "model_fits": model_fits,
            "heldout_labels_parsed": 0,
            "tdc_public_test_evaluations": 0,
            "octant_outer_evaluations": 0,
        },
    )
    return HeldoutPredictionResult(
        manifest_path=manifest_path,
        predictions_path=predictions_path,
        prediction_rows=prediction_rows,
        model_fits=model_fits,
    )


def run_heldout_scoring(
    octant_canonical: Path,
    tdc_canonical: Path,
    validation_root: Path,
    selection_root: Path,
    prediction_root: Path,
    public_sources_path: Path,
    output_directory: Path,
) -> HeldoutScoringResult:
    """Parse held-out labels once and score the frozen prediction receipt."""

    if output_directory.exists():
        raise NativeSelectionError(
            f"output path already exists: {output_directory}. Scoring is immutable."
        )
    verified = _verify_input_receipts(octant_canonical, tdc_canonical, validation_root)
    selection_manifest, _ = _verify_selection_receipt(selection_root, verified)
    prediction_manifest = _verify_prediction_receipt(prediction_root)
    selection_hash_differs = prediction_manifest.get(
        "selection_manifest_sha256"
    ) != _file_hash(selection_root / "selection_manifest.json")
    aggregate_differs = prediction_manifest.get(
        "selection_aggregate_sha256"
    ) != selection_manifest.get("aggregate_sha256")
    if selection_hash_differs or aggregate_differs:
        raise NativeSelectionError("prediction receipt does not bind current selection")
    predictions = _read_csv(prediction_root / "heldout_predictions.csv")
    groups = _prediction_groups(predictions)
    octant_ids = {
        row["molecule_id"] for row in predictions if row["benchmark"] == "octant_cyp"
    }
    tdc_ids = {
        row["molecule_id"] for row in predictions if row["benchmark"] == "tdc_admet_group"
    }
    octant_labels = _load_scoring_labels(
        octant_canonical / "measurements.csv", octant_ids, regression=True
    )
    tdc_labels = _load_scoring_labels(
        tdc_canonical / "measurements.csv", tdc_ids, regression=False
    )
    if set(octant_labels) != octant_ids or set(tdc_labels) != tdc_ids:
        raise NativeSelectionError("held-out label alignment is incomplete")
    thresholds = _oof_thresholds(selection_root / "retained_oof_predictions.csv")
    exclusions = {
        row["molecule_id"]
        for row in _read_csv(validation_root / "tdc" / "strict_test_exclusions.csv")
    }
    sources = _read_json(public_sources_path)
    anchors = _tdc_anchors(sources)

    output_directory.mkdir(parents=True)
    scored_path = output_directory / "scored_predictions.csv"
    scorecard_path = output_directory / "scorecard.csv"
    scored_columns = (*HELDOUT_COLUMNS, "target", "strict_excluded")
    with scored_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=scored_columns, lineterminator="\n")
        writer.writeheader()
        for row in predictions:
            labels = octant_labels if row["benchmark"] == "octant_cyp" else tdc_labels
            label = labels[row["molecule_id"]]
            writer.writerow(
                {
                    **row,
                    "target": _number(label[0]),
                    "strict_excluded": str(row["molecule_id"] in exclusions).lower(),
                }
            )

    score_rows = []
    for key in sorted(groups):
        benchmark, task, family = key
        rows = groups[key]
        labels = octant_labels if benchmark == "octant_cyp" else tdc_labels
        if benchmark == "octant_cyp":
            score_rows.append(_octant_score_row(task, family, rows, labels))
        else:
            threshold = thresholds[(task, family)]
            score_rows.append(
                _tdc_score_row(
                    task, family, "official", rows, labels, threshold, anchors[task]
                )
            )
            strict_rows = [row for row in rows if row["molecule_id"] not in exclusions]
            score_rows.append(
                _tdc_score_row(
                    task, family, "strict", strict_rows, labels, threshold, None
                )
            )
    _write_csv_rows(scorecard_path, SCORECARD_COLUMNS, score_rows)
    outputs = {
        scored_path.name: _file_hash(scored_path),
        scorecard_path.name: _file_hash(scorecard_path),
    }
    material = "\n".join(f"{name}={outputs[name]}" for name in sorted(outputs))
    manifest_path = output_directory / "heldout_scoring_manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": "cypshift.heldout_scoring.v1",
            "prediction_aggregate_sha256": prediction_manifest["aggregate_sha256"],
            "prediction_manifest_sha256": _file_hash(
                prediction_root / "heldout_prediction_manifest.json"
            ),
            "public_sources_sha256": _file_hash(public_sources_path),
            "outputs": outputs,
            "aggregate_sha256": sha256(material.encode()).hexdigest(),
            "heldout_labels_parsed": len(octant_labels) + len(tdc_labels),
            "tdc_public_test_evaluations": 12,
            "tdc_strict_companion_analyses": 12,
            "octant_outer_evaluations": 4,
            "scoring_attempt": 1,
        },
    )
    return HeldoutScoringResult(manifest_path, scorecard_path, 12, 4)


def _verify_prediction_receipt(root: Path) -> dict[str, Any]:
    manifest = _read_json(root / "heldout_prediction_manifest.json")
    if manifest.get("schema_version") != HELDOUT_PREDICTION_SCHEMA_VERSION:
        raise NativeSelectionError("unsupported held-out prediction schema")
    if any(
        manifest.get(field) != 0
        for field in (
            "heldout_labels_parsed",
            "tdc_public_test_evaluations",
            "octant_outer_evaluations",
        )
    ):
        raise NativeSelectionError("prediction receipt is not label clean")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise NativeSelectionError("prediction outputs must be an object")
    for name, expected in outputs.items():
        if not isinstance(name, str) or _file_hash(root / name) != expected:
            raise NativeSelectionError(f"prediction output hash mismatch: {name}")
    material = "\n".join(f"{name}={outputs[name]}" for name in sorted(outputs))
    if sha256(material.encode()).hexdigest() != manifest.get("aggregate_sha256"):
        raise NativeSelectionError("prediction aggregate hash mismatch")
    return manifest


def _prediction_groups(
    rows: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str, str], list[Mapping[str, str]]]:
    result: dict[tuple[str, str, str], list[Mapping[str, str]]] = {}
    seen = set()
    for row in rows:
        key = (row["benchmark"], row["task"], row["family"])
        identity = (*key, row["molecule_id"])
        if identity in seen:
            raise NativeSelectionError("duplicate held-out prediction")
        seen.add(identity)
        result.setdefault(key, []).append(row)
    if len(result) != 16:
        raise NativeSelectionError("held-out predictions must contain 16 task families")
    by_task: dict[tuple[str, str], list[set[str]]] = {}
    for (benchmark, task, _), items in result.items():
        by_task.setdefault((benchmark, task), []).append(
            {item["molecule_id"] for item in items}
        )
    if any(
        len(families) != 4
        or len({frozenset(ids) for ids in families}) != 1
        for families in by_task.values()
    ):
        raise NativeSelectionError("held-out family populations are not identical")
    return result


def _load_scoring_labels(
    path: Path, ids: set[str], *, regression: bool
) -> dict[str, tuple[float, float | None, float | None]]:
    result = {}
    for row in _read_csv(path):
        molecule_id = row.get("molecule_id", "")
        if molecule_id not in ids:
            continue
        if molecule_id in result:
            raise NativeSelectionError("duplicate held-out label")
        value = float(row["value"])
        if not math.isfinite(value):
            raise NativeSelectionError("held-out label is not finite")
        if not regression and value not in {0.0, 1.0}:
            raise NativeSelectionError("held-out classification label is not binary")
        lower = float(row["lower_bound"]) if row.get("lower_bound") else None
        upper = float(row["upper_bound"]) if row.get("upper_bound") else None
        result[molecule_id] = (value, lower, upper)
    return result


def _oof_thresholds(path: Path) -> dict[tuple[str, str], float]:
    groups: dict[tuple[str, str], list[tuple[int, float]]] = {}
    for row in _read_csv(path):
        if row["problem_type"] != "classification":
            continue
        groups.setdefault((row["task"], row["family"]), []).append(
            (int(float(row["target"])), float(row["prediction"]))
        )
    return {key: _mcc_threshold(values) for key, values in groups.items()}


def _mcc_threshold(values: Sequence[tuple[int, float]]) -> float:
    ordered = sorted(values, key=lambda item: item[1], reverse=True)
    positives = sum(label for label, _ in ordered)
    negatives = len(ordered) - positives
    tp = fp = 0
    best_score = -1.0
    best_threshold = ordered[0][1]
    index = 0
    while index < len(ordered):
        threshold = ordered[index][1]
        while index < len(ordered) and ordered[index][1] == threshold:
            if ordered[index][0] == 1:
                tp += 1
            else:
                fp += 1
            index += 1
        fn = positives - tp
        tn = negatives - fp
        denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
        score = (tp * tn - fp * fn) / denominator if denominator else 0.0
        if score > best_score or (score == best_score and threshold < best_threshold):
            best_score = score
            best_threshold = threshold
    return best_threshold


def _tdc_score_row(
    task: str,
    family: str,
    population: str,
    rows: Sequence[Mapping[str, str]],
    labels: Mapping[str, tuple[float, float | None, float | None]],
    threshold: float,
    anchors: Mapping[str, float] | None,
) -> dict[str, str]:
    metrics = import_module("sklearn.metrics")
    y = [int(labels[row["molecule_id"]][0]) for row in rows]
    p = [float(row["prediction"]) for row in rows]
    classified = [int(value >= threshold) for value in p]
    tn, fp, fn, tp = metrics.confusion_matrix(y, classified, labels=[0, 1]).ravel()
    ap = average_precision(y, p)
    maplight = anchors.get("MapLight + GNN") if anchors else None
    return _blank_score_row() | {
        "benchmark": "tdc_admet_group", "task": task, "population": population,
        "family": family, "configuration_id": rows[0]["configuration_id"],
        "rows": str(len(rows)), "prevalence": _number(sum(y) / len(y)),
        "threshold": _number(threshold), "primary_metric": "average_precision",
        "primary_value": _number(ap), "average_precision": _number(ap),
        "auroc": _number(float(metrics.roc_auc_score(y, p))),
        "balanced_accuracy": _number(float(metrics.balanced_accuracy_score(y, classified))),
        "mcc": _number(float(metrics.matthews_corrcoef(y, classified))),
        "brier": _number(sum((label - pred) ** 2 for label, pred in zip(y, p, strict=True)) / len(y)),
        "ece_10_equal_width": _number(_ece(y, p)),
        "sensitivity": _number(tp / (tp + fn)), "specificity": _number(tn / (tn + fp)),
        "maplight_gnn": "" if maplight is None else _number(maplight),
        "chemprop_rdkit": "" if not anchors else _number(anchors["Chemprop-RDKit"]),
        "chemprop": "" if not anchors else _number(anchors["Chemprop"]),
        "delta_vs_maplight_gnn": "" if maplight is None else _number(ap - maplight),
        "comparability": (
            "official fixed TDC test; cypshift standardization and chiral ECFP "
            "disclosed"
            if population == "official"
            else "strict leakage companion; not leaderboard population"
        ),
    }


def _octant_score_row(
    task: str,
    family: str,
    rows: Sequence[Mapping[str, str]],
    labels: Mapping[str, tuple[float, float | None, float | None]],
) -> dict[str, str]:
    stats = import_module("scipy.stats")
    y = [labels[row["molecule_id"]][0] for row in rows]
    p = [float(row["prediction"]) for row in rows]
    errors = [abs(a - b) for a, b in zip(y, p, strict=True)]
    interval_errors = []
    for row, prediction in zip(rows, p, strict=True):
        _, lower, upper = labels[row["molecule_id"]]
        if lower is None or upper is None:
            continue
        interval_errors.append(max(lower - prediction, 0.0, prediction - upper))
    potent = [error for error, target in zip(errors, y, strict=True) if target >= 6.0]
    mae = sum(errors) / len(errors)
    spearman = (
        math.nan
        if len(set(y)) < 2 or len(set(p)) < 2
        else float(stats.spearmanr(y, p).statistic)
    )
    return _blank_score_row() | {
        "benchmark": "octant_cyp", "task": task, "population": "outer_validation",
        "family": family, "configuration_id": rows[0]["configuration_id"],
        "rows": str(len(rows)), "primary_metric": "mae", "primary_value": _number(mae),
        "mae": _number(mae), "median_absolute_error": _number(median(errors)),
        "rmse": _number((sum((a - b) ** 2 for a, b in zip(y, p, strict=True)) / len(y)) ** 0.5),
        "spearman": "" if not math.isfinite(spearman) else _number(spearman),
        "interval_aware_mae": _number(sum(interval_errors) / len(interval_errors)),
        "potent_count": str(len(potent)), "potent_mae": "" if not potent else _number(sum(potent) / len(potent)),
        "comparability": "Octant grouped outer validation; active preincubation assay",
    }


def _ece(labels: Sequence[int], predictions: Sequence[float]) -> float:
    total = len(labels)
    result = 0.0
    for index in range(10):
        lower, upper = index / 10, (index + 1) / 10
        members = [i for i, value in enumerate(predictions) if lower <= value < upper or (index == 9 and value == 1.0)]
        if members:
            confidence = sum(predictions[i] for i in members) / len(members)
            observed = sum(labels[i] for i in members) / len(members)
            result += len(members) / total * abs(confidence - observed)
    return result


def _tdc_anchors(sources: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    try:
        pages = sources["sources"]["tdc_admet"]["tdc_leaderboards"]["pages"]
        return {
            task: {name: float(value["mean"]) for name, value in pages[task]["anchors"].items()}
            for task in TDC_TASKS
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise NativeSelectionError("public source anchors are invalid") from exc


def _blank_score_row() -> dict[str, str]:
    return {column: "" for column in SCORECARD_COLUMNS}


def _write_csv_rows(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _verify_selection_receipt(
    selection_root: Path, verified_inputs: Mapping[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = selection_root / "selection_manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != SELECTION_SCHEMA_VERSION:
        raise NativeSelectionError("unsupported native-selection manifest schema")
    if any(
        manifest.get(field) != 0
        for field in (
            "public_test_labels_parsed",
            "public_test_evaluations",
            "octant_outer_labels_parsed",
            "octant_outer_evaluations",
        )
    ):
        raise NativeSelectionError("selection receipt is not held-out clean")
    recorded_inputs = manifest.get("input_hashes")
    if recorded_inputs != dict(verified_inputs):
        raise NativeSelectionError("selection inputs do not match current receipts")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise NativeSelectionError("selection outputs must be an object")
    for name, expected in sorted(outputs.items()):
        if not isinstance(name, str) or not isinstance(expected, str):
            raise NativeSelectionError("selection output entry is invalid")
        if _file_hash(selection_root / name) != expected:
            raise NativeSelectionError(f"selection output hash mismatch: {name}")
    material = "\n".join(f"{name}={outputs[name]}" for name in sorted(outputs))
    if sha256(material.encode()).hexdigest() != manifest.get("aggregate_sha256"):
        raise NativeSelectionError("selection aggregate hash mismatch")
    retained = _read_json(selection_root / "retained_models.json")
    return manifest, retained


def _verify_official_split(split_path: Path, validation_root: Path) -> None:
    audit = _read_json(validation_root / "tdc" / "tdc_split_audit.json")
    inputs = audit.get("input_hashes")
    if not isinstance(inputs, dict) or inputs.get("official_split.csv") != _file_hash(
        split_path
    ):
        raise NativeSelectionError("official TDC split does not match audit receipt")


def _retained_configurations(
    retained_models: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Mapping[str, Any]]]:
    datasets = retained_models.get("datasets")
    if not isinstance(datasets, list):
        raise NativeSelectionError("retained model datasets must be an array")
    result = {}
    for dataset in datasets:
        if not isinstance(dataset, dict) or not isinstance(
            dataset.get("families"), list
        ):
            raise NativeSelectionError("retained model dataset is invalid")
        key = (str(dataset.get("benchmark")), str(dataset.get("task")))
        families = {}
        for family in dataset["families"]:
            if not isinstance(family, dict) or not isinstance(
                family.get("configuration"), dict
            ):
                raise NativeSelectionError("retained family is invalid")
            families[str(family.get("family"))] = family["configuration"]
        if set(families) != set(FAMILIES):
            raise NativeSelectionError("retained dataset must contain four families")
        result[key] = families
    return result


def _load_octant_heldout(canonical: Path, split_path: Path) -> HeldoutDataset:
    ids = {
        row["molecule_id"]
        for row in _read_csv(split_path)
        if row.get("outer_partition") == "validation"
        and row.get("has_measurement") == "true"
    }
    return _load_heldout_structures(
        canonical,
        ids,
        benchmark="octant_cyp",
        task="cyp3a4_active_preincubation_pIC50",
        problem_type="regression",
    )


def _load_tdc_heldout(canonical: Path, split_path: Path) -> list[HeldoutDataset]:
    ids: dict[str, set[str]] = {task: set() for task in TDC_TASKS}
    for row in _read_csv(split_path):
        if row.get("partition") == "test":
            task = row.get("task", "")
            if task not in ids:
                raise NativeSelectionError(f"unexpected official split task: {task}")
            ids[task].add(row.get("molecule_id", ""))
    return [
        _load_heldout_structures(
            canonical,
            ids[task],
            benchmark="tdc_admet_group",
            task=task,
            problem_type="classification",
        )
        for task in TDC_TASKS
    ]


def _load_heldout_structures(
    canonical: Path,
    ids: set[str],
    *,
    benchmark: str,
    task: str,
    problem_type: ProblemType,
) -> HeldoutDataset:
    found = {}
    for row in _read_csv(canonical / "molecules.csv"):
        molecule_id = row.get("molecule_id", "")
        if molecule_id not in ids:
            continue
        if row.get("status") != "accepted":
            raise NativeSelectionError(f"held-out molecule is not accepted: {molecule_id}")
        found[molecule_id] = (
            row.get("standardized_structure", ""),
            row.get("standardized_structure_hash", ""),
        )
    if set(found) != ids or any(not value[0] or not value[1] for value in found.values()):
        raise NativeSelectionError(f"held-out structure alignment failed: {task}")
    ordered = tuple(sorted(ids))
    return HeldoutDataset(
        benchmark=benchmark,
        task=task,
        problem_type=problem_type,
        molecule_ids=ordered,
        structures=tuple(found[item][0] for item in ordered),
        structure_hashes=tuple(found[item][1] for item in ordered),
    )


def _predict_task(
    train: SelectionDataset,
    test: HeldoutDataset,
    configurations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    fingerprints, matrix = _fingerprints((*train.structures, *test.structures))
    split = len(train.structures)
    train_fingerprints = fingerprints[:split]
    test_fingerprints = fingerprints[split:]
    train_matrix = matrix[:split]
    test_matrix = matrix[split:]
    retained = {
        "prior": _predict_prior(train, len(test.molecule_ids)),
        "ecfp_linear": _predict_linear(
            train, train_matrix, test_matrix, configurations["ecfp_linear"]
        ),
        "similarity_knn": _predict_knn(
            train,
            train_fingerprints,
            test_fingerprints,
            configurations["similarity_knn"],
        ),
    }
    seed_sets = [
        (
            seed,
            _predict_extra_trees(
                train,
                train_matrix,
                test_matrix,
                configurations["extra_trees"],
                seed,
            ),
        )
        for seed in STOCHASTIC_SEEDS
    ]
    retained["extra_trees"] = _mean_prediction_sets(
        [item[1] for item in seed_sets]
    )
    return {"retained": retained, "stochastic": seed_sets, "model_fits": 6}


def _predict_prior(train: SelectionDataset, rows: int) -> PredictionSet:
    value = (
        sum(train.targets) / len(train.targets)
        if train.problem_type == "classification"
        else median(train.targets)
    )
    return _plain_external([value] * rows)


def _predict_linear(
    train: SelectionDataset,
    train_matrix: Any,
    test_matrix: Any,
    config: Mapping[str, Any],
) -> PredictionSet:
    np = import_module("numpy")
    linear = import_module("sklearn.linear_model")
    targets = np.asarray(train.targets, dtype=np.float64)
    if train.problem_type == "classification":
        model = linear.LogisticRegression(
            C=float(config["C"]),
            l1_ratio=0.0,
            solver="liblinear",
            max_iter=2000,
            random_state=SEED,
        )
        model.fit(train_matrix, targets)
        positive = list(model.classes_).index(1.0)
        values = model.predict_proba(test_matrix)[:, positive]
    else:
        model = linear.Ridge(alpha=float(config["alpha"]), solver="lsqr", tol=1e-6)
        model.fit(train_matrix, targets)
        values = model.predict(test_matrix)
    return _plain_external(values.tolist())


def _predict_knn(
    train: SelectionDataset,
    train_fingerprints: Sequence[Any],
    test_fingerprints: Sequence[Any],
    config: Mapping[str, Any],
) -> PredictionSet:
    predictions = []
    nearest = []
    support = []
    variances = []
    fallback = (
        sum(train.targets) / len(train.targets)
        if train.problem_type == "classification"
        else median(train.targets)
    )
    for fingerprint in test_fingerprints:
        similarities = DataStructs.BulkTanimotoSimilarity(
            fingerprint, train_fingerprints
        )
        ordered = sorted(
            range(len(train.targets)), key=lambda item: (-similarities[item], item)
        )[: min(int(config["neighbors"]), len(train.targets))]
        weights = [
            similarities[item] ** int(config["similarity_power"])
            for item in ordered
        ]
        total = sum(weights)
        labels = [train.targets[item] for item in ordered]
        predictions.append(
            sum(
                weight * train.targets[item]
                for weight, item in zip(weights, ordered, strict=True)
            )
            / total
            if total > 0
            else fallback
        )
        nearest.append(similarities[ordered[0]] if ordered else 0.0)
        support.append(sum(similarities[item] > 0 for item in ordered))
        mean = sum(labels) / len(labels)
        variances.append(sum((label - mean) ** 2 for label in labels) / len(labels))
    return PredictionSet(
        tuple(predictions), tuple(nearest), tuple(support), tuple(variances)
    )


def _predict_extra_trees(
    train: SelectionDataset,
    train_matrix: Any,
    test_matrix: Any,
    config: Mapping[str, Any],
    seed: int,
) -> PredictionSet:
    np = import_module("numpy")
    ensemble = import_module("sklearn.ensemble")
    targets = np.asarray(train.targets, dtype=np.float64)
    common = {
        "n_estimators": int(config["n_estimators"]),
        "min_samples_leaf": int(config["min_samples_leaf"]),
        "max_features": config["max_features"],
        "n_jobs": 1,
        "random_state": seed,
    }
    if train.problem_type == "classification":
        model = ensemble.ExtraTreesClassifier(
            **common, class_weight=config["class_weight"]
        )
        model.fit(train_matrix, targets)
        positive = list(model.classes_).index(1.0)
        values = model.predict_proba(test_matrix)[:, positive]
    else:
        model = ensemble.ExtraTreesRegressor(**common)
        model.fit(train_matrix, targets)
        values = model.predict(test_matrix)
    return _plain_external(values.tolist())


def _plain_external(values: Sequence[float]) -> PredictionSet:
    length = len(values)
    return PredictionSet(
        tuple(float(value) for value in values),
        (None,) * length,
        (None,) * length,
        (None,) * length,
    )


def _write_rows(
    writer: Any,
    dataset: HeldoutDataset,
    family: str,
    configuration_id: str,
    seed: str,
    predictions: PredictionSet,
) -> None:
    for index, molecule_id in enumerate(dataset.molecule_ids):
        nearest = predictions.nearest_similarity[index]
        variance = predictions.local_variance[index]
        writer.writerow(
            {
                "benchmark": dataset.benchmark,
                "task": dataset.task,
                "problem_type": dataset.problem_type,
                "molecule_id": molecule_id,
                "family": family,
                "configuration_id": configuration_id,
                "seed": seed,
                "prediction": _number(predictions.predictions[index]),
                "standardized_structure_hash": dataset.structure_hashes[index],
                "nearest_neighbor_similarity": (
                    "" if nearest is None else _number(nearest)
                ),
                "local_support_count": (
                    ""
                    if predictions.support_count[index] is None
                    else str(predictions.support_count[index])
                ),
                "local_label_variance": (
                    "" if variance is None else _number(variance)
                ),
            }
        )


__all__ = [
    "HELDOUT_PREDICTION_SCHEMA_VERSION",
    "HeldoutPredictionResult",
    "HeldoutScoringResult",
    "run_heldout_prediction",
    "run_heldout_scoring",
]
