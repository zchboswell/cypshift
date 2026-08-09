from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from cypshift.native_evaluation import run_heldout_prediction, run_heldout_scoring
from cypshift.native_selection import (
    FAMILIES,
    NativeSelectionError,
    run_native_selection,
)
from cypshift.tdc import TDC_TASKS


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _structure_hash(structure: str) -> str:
    return hashlib.sha256(structure.encode()).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_receipts(octant: Path, tdc: Path, validation: Path) -> None:
    (validation / "octant" / "split_manifest.json").write_text(
        json.dumps(
            {
                "input_hashes": {
                    "molecules.csv": _file_hash(octant / "molecules.csv"),
                    "measurements.csv": _file_hash(octant / "measurements.csv"),
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    tdc_inputs = {
        "molecules.csv": _file_hash(tdc / "molecules.csv"),
        "measurements.csv": _file_hash(tdc / "measurements.csv"),
    }
    official_split = validation / "tdc" / "official_split.csv"
    if official_split.exists():
        tdc_inputs["official_split.csv"] = _file_hash(official_split)
    (validation / "tdc" / "tdc_split_audit.json").write_text(
        json.dumps(
            {"input_hashes": tdc_inputs},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths = {
        "octant/octant_grouped_split.csv": (
            validation / "octant" / "octant_grouped_split.csv"
        ),
        "octant/split_manifest.json": validation / "octant" / "split_manifest.json",
        "tdc/tdc_inner_folds.csv": validation / "tdc" / "tdc_inner_folds.csv",
        "tdc/tdc_split_audit.json": validation / "tdc" / "tdc_split_audit.json",
        "tdc/strict_test_exclusions.csv": (
            validation / "tdc" / "strict_test_exclusions.csv"
        ),
    }
    output_hashes = {
        name: _file_hash(path) for name, path in sorted(output_paths.items())
    }
    aggregate_material = "\n".join(
        f"{name}={output_hashes[name]}" for name in sorted(output_hashes)
    )
    (validation / "public_validation_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "cypshift.public_validation_freeze.v1",
                "outputs": output_hashes,
                "aggregate_sha256": hashlib.sha256(
                    aggregate_material.encode()
                ).hexdigest(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _fixture(
    root: Path, *, valid_heldout_labels: bool = False
) -> tuple[Path, Path, Path, set[str]]:
    structures = (
        "CCO",
        "CCN",
        "CCC",
        "CCCl",
        "CCBr",
        "CCF",
        "COC",
        "CNC",
        "C1CC1",
        "c1ccccc1",
        "c1ccncc1",
        "c1ccoc1",
    )
    molecule_columns = (
        "molecule_id",
        "status",
        "standardized_structure",
        "standardized_structure_hash",
    )
    measurement_columns = ("molecule_id", "value", "lower_bound", "upper_bound")

    octant = root / "octant"
    octant_molecules = []
    octant_measurements = []
    octant_splits = []
    selected_ids = set()
    for index, structure in enumerate(structures):
        molecule_id = f"octant-{index:02d}"
        selected_ids.add(molecule_id)
        octant_molecules.append(
            {
                "molecule_id": molecule_id,
                "status": "accepted",
                "standardized_structure": structure,
                "standardized_structure_hash": _structure_hash(structure),
            }
        )
        octant_measurements.append(
            {
                "molecule_id": molecule_id,
                "value": str(3.0 + index / 4),
                "lower_bound": "",
                "upper_bound": "",
            }
        )
        octant_splits.append(
            {
                "molecule_id": molecule_id,
                "outer_partition": "train",
                "inner_fold": str(index % 4),
                "has_measurement": "true",
            }
        )
    for outer_index, (structure, value) in enumerate(
        (("CC=O", 4.5), ("CC#N", 6.5)), start=1
    ):
        molecule_id = f"octant-outer-{outer_index}"
        octant_molecules.append(
            {
                "molecule_id": molecule_id,
                "status": "accepted",
                "standardized_structure": structure,
                "standardized_structure_hash": _structure_hash(structure),
            }
        )
        octant_measurements.append(
            {
                "molecule_id": molecule_id,
                "value": str(value) if valid_heldout_labels else "DO_NOT_PARSE",
                "lower_bound": str(value - 0.25) if valid_heldout_labels else "",
                "upper_bound": str(value + 0.25) if valid_heldout_labels else "",
            }
        )
        octant_splits.append(
            {
                "molecule_id": molecule_id,
                "outer_partition": "validation",
                "inner_fold": "",
                "has_measurement": "true",
            }
        )
    _write_csv(octant / "molecules.csv", molecule_columns, octant_molecules)
    _write_csv(
        octant / "measurements.csv", measurement_columns, octant_measurements
    )

    tdc = root / "tdc"
    tdc_molecules = []
    tdc_measurements = []
    tdc_folds = []
    tdc_official = []
    for task_index, task in enumerate(TDC_TASKS):
        for index, structure in enumerate(structures):
            molecule_id = f"tdc:{task}:train_val:{index:05d}"
            selected_ids.add(molecule_id)
            decorated = structure + ".[Na+]" if task_index == 1 else structure
            tdc_molecules.append(
                {
                    "molecule_id": molecule_id,
                    "status": "accepted",
                    "standardized_structure": decorated,
                    "standardized_structure_hash": _structure_hash(decorated),
                }
            )
            tdc_measurements.append(
                {
                    "molecule_id": molecule_id,
                    "value": str(index % 2),
                    "lower_bound": "",
                    "upper_bound": "",
                }
            )
            tdc_folds.append(
                {
                    "task": task,
                    "molecule_id": molecule_id,
                    "inner_fold": str(index % 4),
                }
            )
        for test_index, test_structure in enumerate(("CC#N", "CC=O"), start=1):
            test_id = f"tdc:{task}:test:{test_index:05d}"
            tdc_molecules.append(
                {
                    "molecule_id": test_id,
                    "status": "accepted",
                    "standardized_structure": test_structure,
                    "standardized_structure_hash": _structure_hash(test_structure),
                }
            )
            tdc_measurements.append(
                {
                    "molecule_id": test_id,
                    "value": (
                        str(test_index - 1)
                        if valid_heldout_labels
                        else "DO_NOT_PARSE"
                    ),
                    "lower_bound": "",
                    "upper_bound": "",
                }
            )
            tdc_official.append(
                {
                    "molecule_id": test_id,
                    "task": task,
                    "partition": "test",
                    "source_row": str(test_index + 1),
                }
            )
    _write_csv(tdc / "molecules.csv", molecule_columns, tdc_molecules)
    _write_csv(tdc / "measurements.csv", measurement_columns, tdc_measurements)

    validation = root / "validation"
    _write_csv(
        validation / "octant" / "octant_grouped_split.csv",
        ("molecule_id", "outer_partition", "inner_fold", "has_measurement"),
        octant_splits,
    )
    _write_csv(
        validation / "tdc" / "tdc_inner_folds.csv",
        ("task", "molecule_id", "inner_fold"),
        tdc_folds,
    )
    _write_csv(
        validation / "tdc" / "official_split.csv",
        ("molecule_id", "task", "partition", "source_row"),
        tdc_official,
    )
    _write_csv(
        validation / "tdc" / "strict_test_exclusions.csv",
        ("task", "molecule_id", "standardized_structure_hash", "reason"),
        [],
    )
    _write_receipts(octant, tdc, validation)
    return octant, tdc, validation, selected_ids


def test_native_selection_is_deterministic_and_never_parses_held_out_labels(
    tmp_path: Path,
) -> None:
    octant, tdc, validation, selected_ids = _fixture(tmp_path / "fixture")

    first = run_native_selection(
        octant, tdc, validation, tmp_path / "first", nonlinear_trees=4
    )
    run_native_selection(
        octant, tdc, validation, tmp_path / "second", nonlinear_trees=4
    )

    for path in sorted((tmp_path / "first").iterdir()):
        assert path.read_bytes() == (tmp_path / "second" / path.name).read_bytes()
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    retained_models = json.loads(
        first.retained_models_path.read_text(encoding="utf-8")
    )
    with first.retained_predictions_path.open(
        encoding="utf-8", newline=""
    ) as handle:
        retained = list(csv.DictReader(handle))
    with (tmp_path / "first" / "selection_scores.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        scores = list(csv.DictReader(handle))
    assert manifest["public_test_labels_parsed"] == 0
    assert manifest["public_test_evaluations"] == 0
    assert manifest["octant_outer_labels_parsed"] == 0
    assert manifest["octant_outer_evaluations"] == 0
    assert manifest["retained_prediction_rows"] == 192
    assert first.row_count == 192
    assert first.model_fit_count == 240
    assert len(retained) == 192
    assert {row["molecule_id"] for row in retained} == selected_ids
    assert {row["family"] for row in retained} == set(FAMILIES)
    assert len(retained_models["datasets"]) == 4
    assert all(
        len(dataset["families"]) == 4
        for dataset in retained_models["datasets"]
    )
    assert all(
        sum(
            row["benchmark"] == dataset["benchmark"]
            and row["task"] == dataset["task"]
            and row["score_role"] == "candidate"
            for row in scores
        )
        == 13
        for dataset in retained_models["datasets"]
    )
    knn_rows = [row for row in retained if row["family"] == "similarity_knn"]
    assert all(row["nearest_neighbor_similarity"] for row in knn_rows)
    assert all(row["local_support_count"] for row in knn_rows)


def test_native_selection_refuses_overwrite_and_missing_selected_target(
    tmp_path: Path,
) -> None:
    octant, tdc, validation, _ = _fixture(tmp_path / "fixture")
    output = tmp_path / "selection"
    run_native_selection(octant, tdc, validation, output, nonlinear_trees=2)
    with pytest.raises(NativeSelectionError, match="already exists"):
        run_native_selection(octant, tdc, validation, output, nonlinear_trees=2)

    fold_path = validation / "tdc" / "tdc_inner_folds.csv"
    original_folds = fold_path.read_bytes()
    fold_path.write_bytes(original_folds + b"\n")
    with pytest.raises(NativeSelectionError, match="output hash mismatch"):
        run_native_selection(
            octant,
            tdc,
            validation,
            tmp_path / "tampered",
            nonlinear_trees=2,
        )
    fold_path.write_bytes(original_folds)

    rows: list[dict[str, str]]
    with (octant / "measurements.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    _write_csv(
        octant / "measurements-missing.csv",
        ("molecule_id", "value", "lower_bound", "upper_bound"),
        rows[1:],
    )
    (octant / "measurements.csv").replace(octant / "measurements-original.csv")
    (octant / "measurements-missing.csv").replace(octant / "measurements.csv")
    _write_receipts(octant, tdc, validation)
    with pytest.raises(NativeSelectionError, match="missing targets=1"):
        run_native_selection(
            octant,
            tdc,
            validation,
            tmp_path / "misaligned",
            nonlinear_trees=2,
        )


def test_heldout_prediction_is_label_blind_and_deterministic(tmp_path: Path) -> None:
    octant, tdc, validation, _ = _fixture(tmp_path / "fixture")
    selection = tmp_path / "selection"
    run_native_selection(
        octant, tdc, validation, selection, nonlinear_trees=4
    )
    official_split = validation / "tdc" / "official_split.csv"

    first = run_heldout_prediction(
        octant,
        tdc,
        official_split,
        validation,
        selection,
        tmp_path / "predictions-one",
    )
    run_heldout_prediction(
        octant,
        tdc,
        official_split,
        validation,
        selection,
        tmp_path / "predictions-two",
    )

    for path in sorted((tmp_path / "predictions-one").iterdir()):
        assert path.read_bytes() == (
            tmp_path / "predictions-two" / path.name
        ).read_bytes()
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["heldout_structures"] == 8
    assert manifest["prediction_rows"] == 32
    assert manifest["model_fits"] == 24
    assert manifest["heldout_labels_parsed"] == 0
    assert manifest["tdc_public_test_evaluations"] == 0
    assert manifest["octant_outer_evaluations"] == 0


def test_heldout_scoring_is_receipt_bound_and_deterministic(tmp_path: Path) -> None:
    octant, tdc, validation, _ = _fixture(
        tmp_path / "fixture", valid_heldout_labels=True
    )
    selection = tmp_path / "selection"
    predictions = tmp_path / "predictions"
    run_native_selection(octant, tdc, validation, selection, nonlinear_trees=4)
    run_heldout_prediction(
        octant,
        tdc,
        validation / "tdc" / "official_split.csv",
        validation,
        selection,
        predictions,
    )
    public_sources = tmp_path / "public_sources.json"
    public_sources.write_text(
        json.dumps(
            {
                "sources": {
                    "tdc_leaderboards": {
                        "pages": {
                            task: {
                                "anchors": {
                                    "MapLight + GNN": {"mean": 0.8},
                                    "Chemprop-RDKit": {"mean": 0.7},
                                    "Chemprop": {"mean": 0.6},
                                }
                            }
                            for task in TDC_TASKS
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    first = run_heldout_scoring(
        octant,
        tdc,
        validation,
        selection,
        predictions,
        public_sources,
        tmp_path / "scores-one",
    )
    run_heldout_scoring(
        octant,
        tdc,
        validation,
        selection,
        predictions,
        public_sources,
        tmp_path / "scores-two",
    )
    for path in sorted((tmp_path / "scores-one").iterdir()):
        assert path.read_bytes() == (tmp_path / "scores-two" / path.name).read_bytes()
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    with first.scorecard_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 28
    assert manifest["heldout_labels_parsed"] == 8
    assert manifest["tdc_public_test_evaluations"] == 12
    assert manifest["tdc_strict_companion_analyses"] == 12
    assert manifest["octant_outer_evaluations"] == 4
    assert manifest["scoring_attempt"] == 1

    attempt_two = run_heldout_scoring(
        octant,
        tdc,
        validation,
        selection,
        predictions,
        public_sources,
        tmp_path / "scores-attempt-two",
        attempt=2,
    )
    attempt_two_manifest = json.loads(
        attempt_two.manifest_path.read_text(encoding="utf-8")
    )
    assert attempt_two_manifest["scoring_attempt"] == 2

    prediction_path = predictions / "heldout_predictions.csv"
    original_predictions = prediction_path.read_bytes()
    prediction_path.write_bytes(original_predictions + b"\n")
    with pytest.raises(NativeSelectionError, match="prediction output hash mismatch"):
        run_heldout_scoring(
            octant,
            tdc,
            validation,
            selection,
            predictions,
            public_sources,
            tmp_path / "tampered-scores",
        )
