from __future__ import annotations

import csv
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from cypshift.chemeleon import CHEMELEON_INPUT_COLUMNS, CheMeleonInputError
from cypshift.chemeleon_attempt import (
    PREDICTION_COLUMNS,
    audit_training_overlap,
    canonicalize_predictions,
    docker_prediction_command,
    require_identical_predictions,
    validate_task_mapping_values,
    verify_model_files,
)


def test_overlap_and_prediction_receipts_are_label_free(tmp_path: Path) -> None:
    input_path, model_root, contract = _fixture(tmp_path)
    overlap_root = tmp_path / "overlap"
    audit_training_overlap(
        input_path,
        model_root,
        contract,
        overlap_root,
        source_revision="fixture-revision",
    )
    with (overlap_root / "chemeleon_training_overlap.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        overlap_rows = list(csv.DictReader(handle))
    assert [row["exact_training_structure_overlap"] for row in overlap_rows] == [
        "true",
        "false",
    ]
    overlap_manifest = json.loads(
        (overlap_root / "chemeleon_overlap_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert overlap_manifest["heldout_labels_parsed"] == 0
    assert overlap_manifest["model_evaluations"] == 0

    raw_path = tmp_path / "raw.csv"
    _write_raw_predictions(input_path, raw_path)
    prediction_root = tmp_path / "predictions"
    manifest_path = canonicalize_predictions(
        input_path,
        raw_path,
        overlap_root,
        contract,
        prediction_root,
        source_revision="fixture-revision",
        runtime_seconds=1.25,
    )
    with (prediction_root / "chemeleon_predictions.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == PREDICTION_COLUMNS
        prediction_rows = list(reader)
    assert [row["prediction"] for row in prediction_rows] == ["5.25", "6.5"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["heldout_labels_parsed"] == 0
    assert manifest["model_fits"] == 0
    assert manifest["model_evaluations"] == 0


def test_prediction_rejects_row_reordering(tmp_path: Path) -> None:
    input_path, model_root, contract = _fixture(tmp_path)
    overlap_root = tmp_path / "overlap"
    audit_training_overlap(
        input_path,
        model_root,
        contract,
        overlap_root,
        source_revision="fixture-revision",
    )
    raw_path = tmp_path / "raw.csv"
    _write_raw_predictions(input_path, raw_path, reverse=True)
    with pytest.raises(CheMeleonInputError, match="alignment mismatch"):
        canonicalize_predictions(
            input_path,
            raw_path,
            overlap_root,
            contract,
            tmp_path / "predictions",
            source_revision="fixture-revision",
            runtime_seconds=1.0,
        )


def test_prediction_rejects_nonfinite_value(tmp_path: Path) -> None:
    input_path, model_root, contract = _fixture(tmp_path)
    overlap_root = tmp_path / "overlap"
    audit_training_overlap(
        input_path,
        model_root,
        contract,
        overlap_root,
        source_revision="fixture-revision",
    )
    raw_path = tmp_path / "raw.csv"
    _write_raw_predictions(input_path, raw_path, first_prediction="nan")
    with pytest.raises(CheMeleonInputError, match="not finite"):
        canonicalize_predictions(
            input_path,
            raw_path,
            overlap_root,
            contract,
            tmp_path / "predictions",
            source_revision="fixture-revision",
            runtime_seconds=1.0,
        )


def test_model_file_tampering_is_rejected(tmp_path: Path) -> None:
    _, model_root, contract = _fixture(tmp_path)
    training_path = model_root / "anvil_training" / "data" / "X_train.csv"
    training_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(CheMeleonInputError, match="model file hash mismatch"):
        verify_model_files(model_root, contract)


def test_docker_command_mounts_only_safe_inputs(tmp_path: Path) -> None:
    input_path = tmp_path / "safe.csv"
    input_path.write_text("safe\n", encoding="utf-8")
    model_root = tmp_path / "model"
    output_root = tmp_path / "output"
    model_root.mkdir()
    output_root.mkdir()
    command = docker_prediction_command(
        image="registry/model@sha256:abc",
        input_path=input_path,
        model_directory=model_root,
        output_directory=output_root,
        output_name="raw.csv",
    )
    mounts = [command[index + 1] for index, value in enumerate(command) if value == "-v"]
    assert mounts == [
        f"{input_path.resolve()}:/input.csv:ro",
        f"{model_root.resolve()}:/model:ro",
        f"{output_root.resolve()}:/output:rw",
    ]
    assert command[command.index("--network") + 1] == "none"
    assert "measurement" not in " ".join(command)
    assert "provenance" not in " ".join(command)


def test_repeat_check_rejects_different_predictions(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("prediction\n1\n", encoding="utf-8")
    second.write_text("prediction\n2\n", encoding="utf-8")
    with pytest.raises(CheMeleonInputError, match="not identical"):
        require_identical_predictions(first, second)


def test_real_contract_task_mapping_matches_reviewed_input() -> None:
    root = Path(__file__).resolve().parents[1]
    validate_task_mapping_values(
        {
            "cyp2c9_veith",
            "cyp2d6_veith",
            "cyp3a4_veith",
            "cyp3a4_active_preincubation_pIC50",
        },
        root / "benchmarks" / "chemeleon_inference_contract.json",
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    rows = [
        {
            "benchmark": "octant_cyp",
            "task": "octant_task",
            "molecule_id": "oct-1",
            "standardized_structure": "CC",
            "standardized_structure_hash": sha256(b"CC").hexdigest(),
        },
        {
            "benchmark": "tdc_admet_group",
            "task": "tdc_task",
            "molecule_id": "tdc-1",
            "standardized_structure": "CCC",
            "standardized_structure_hash": sha256(b"CCC").hexdigest(),
        },
    ]
    input_path = tmp_path / "input.csv"
    _write_csv(input_path, CHEMELEON_INPUT_COLUMNS, rows)
    key_material = "\n".join(
        "|".join(row[field] for field in CHEMELEON_INPUT_COLUMNS[:3])
        for row in rows
    )

    model_root = tmp_path / "model_root"
    training_path = model_root / "anvil_training" / "data" / "X_train.csv"
    training_path.parent.mkdir(parents=True)
    _write_csv(
        training_path,
        ("OPENADMET_CANONICAL_SMILES",),
        [
            {"OPENADMET_CANONICAL_SMILES": "CC"},
            {"OPENADMET_CANONICAL_SMILES": "N"},
        ],
    )
    contract_path = tmp_path / "contract.json"
    _write_json(
        contract_path,
        {
            "model": {
                "training_structure_column": "OPENADMET_CANONICAL_SMILES",
                "training_rows": 2,
                "required_files": {
                    "anvil_training/data/X_train.csv": _hash(training_path)
                },
            },
            "model_facing_projection": {
                "expected_output_sha256": _hash(input_path),
                "expected_population_key_sha256": sha256(
                    key_material.encode()
                ).hexdigest(),
            },
            "expected_task_counts": {"octant_task": 1, "tdc_task": 1},
            "task_mapping": {
                "octant_task": {"model_output": "OPENADMET_LOGAC50_CYP3A4"},
                "tdc_task": {"model_output": "OPENADMET_LOGAC50_CYP2C9"},
            },
        },
    )
    return input_path, model_root, contract_path


def _write_raw_predictions(
    input_path: Path,
    output_path: Path,
    *,
    reverse: bool = False,
    first_prediction: str = "5.25",
) -> None:
    with input_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if reverse:
        rows.reverse()
    rows[0][
        "OADMET_PRED_openadmet-AC50_OPENADMET_LOGAC50_CYP3A4"
    ] = first_prediction
    rows[0]["OADMET_PRED_openadmet-AC50_OPENADMET_LOGAC50_CYP2C9"] = "4.0"
    rows[1]["OADMET_PRED_openadmet-AC50_OPENADMET_LOGAC50_CYP3A4"] = "4.5"
    rows[1]["OADMET_PRED_openadmet-AC50_OPENADMET_LOGAC50_CYP2C9"] = "6.5"
    _write_csv(
        output_path,
        (
            *CHEMELEON_INPUT_COLUMNS,
            "OADMET_PRED_openadmet-AC50_OPENADMET_LOGAC50_CYP3A4",
            "OADMET_PRED_openadmet-AC50_OPENADMET_LOGAC50_CYP2C9",
        ),
        rows,
    )


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
