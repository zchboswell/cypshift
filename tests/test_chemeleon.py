from __future__ import annotations

import csv
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from cypshift.chemeleon import (
    CHEMELEON_INPUT_COLUMNS,
    CheMeleonInputError,
    prepare_chemeleon_inference_input,
    validate_chemeleon_inference_input,
)


def test_projection_strips_hidden_outcomes_and_freezes_keys(tmp_path: Path) -> None:
    prediction_root, retained_root, contract = _fixture(tmp_path)
    output = tmp_path / "output"
    manifest_path = prepare_chemeleon_inference_input(
        prediction_root,
        retained_root,
        contract,
        output,
        source_revision="fixture-revision",
    )

    input_path = output / "chemeleon_inference_input.csv"
    text = input_path.read_text(encoding="utf-8")
    assert "source_label_raw" not in text
    assert "CYP3A4_pIC50" not in text
    assert "SENTINEL_OUTCOME" not in text
    with input_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == CHEMELEON_INPUT_COLUMNS
        rows = list(reader)
    assert [(row["task"], row["molecule_id"]) for row in rows] == [
        ("cyp3a4_active_preincubation_pIC50", "oct-1"),
        ("cyp2c9_veith", "tdc-1"),
    ]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rows"] == 2
    assert manifest["source_provenance_values_parsed"] == 0
    assert manifest["source_measurement_tables_opened"] == 0
    assert manifest["heldout_labels_parsed"] == 0
    assert manifest["native_prediction_values_consumed"] == 0
    assert manifest["model_facing_input_files"] == [
        "chemeleon_inference_input.csv"
    ]


def test_projection_rejects_duplicate_population_key(tmp_path: Path) -> None:
    prediction_root, retained_root, contract = _fixture(
        tmp_path, duplicate_key=True
    )
    with pytest.raises(CheMeleonInputError, match="duplicate population key"):
        prepare_chemeleon_inference_input(
            prediction_root,
            retained_root,
            contract,
            tmp_path / "output",
            source_revision="fixture-revision",
        )


def test_projection_rejects_missing_population_molecule(tmp_path: Path) -> None:
    prediction_root, retained_root, contract = _fixture(
        tmp_path, missing_molecule=True
    )
    with pytest.raises(CheMeleonInputError, match="population molecule is missing"):
        prepare_chemeleon_inference_input(
            prediction_root,
            retained_root,
            contract,
            tmp_path / "output",
            source_revision="fixture-revision",
        )


def test_projection_rejects_receipt_tampering(tmp_path: Path) -> None:
    prediction_root, retained_root, contract = _fixture(tmp_path)
    molecules_path = prediction_root / "tdc" / "molecules.csv"
    molecules_path.write_text(
        molecules_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(CheMeleonInputError, match="file hash mismatch"):
        prepare_chemeleon_inference_input(
            prediction_root,
            retained_root,
            contract,
            tmp_path / "output",
            source_revision="fixture-revision",
        )


def test_model_facing_validator_rejects_extra_column(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    _write_csv(
        input_path,
        (*CHEMELEON_INPUT_COLUMNS, "provenance"),
        [
            {
                "benchmark": "octant_cyp",
                "task": "cyp3a4_active_preincubation_pIC50",
                "molecule_id": "oct-1",
                "standardized_structure": "CC",
                "standardized_structure_hash": sha256(b"CC").hexdigest(),
                "provenance": "SENTINEL_OUTCOME",
            }
        ],
    )
    with pytest.raises(CheMeleonInputError, match="unexpected columns"):
        validate_chemeleon_inference_input(
            input_path,
            expected_rows=1,
            expected_task_counts={"cyp3a4_active_preincubation_pIC50": 1},
        )


def test_model_facing_validator_rejects_key_hash_mismatch(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.csv"
    _write_csv(
        input_path,
        CHEMELEON_INPUT_COLUMNS,
        [
            {
                "benchmark": "octant_cyp",
                "task": "cyp3a4_active_preincubation_pIC50",
                "molecule_id": "oct-1",
                "standardized_structure": "CC",
                "standardized_structure_hash": sha256(b"CC").hexdigest(),
            }
        ],
    )
    with pytest.raises(CheMeleonInputError, match="population-key hash mismatch"):
        validate_chemeleon_inference_input(
            input_path,
            expected_rows=1,
            expected_task_counts={"cyp3a4_active_preincubation_pIC50": 1},
            expected_key_sha256="0" * 64,
        )


def _fixture(
    tmp_path: Path,
    *,
    duplicate_key: bool = False,
    missing_molecule: bool = False,
) -> tuple[Path, Path, Path]:
    prediction_root = tmp_path / "prediction_inputs"
    retained_root = tmp_path / "retained"
    (prediction_root / "octant").mkdir(parents=True)
    (prediction_root / "tdc").mkdir()
    retained_root.mkdir()

    octant_rows = [
        {
            "molecule_id": "oct-1",
            "standardized_structure": "CC",
            "standardized_structure_hash": sha256(b"CC").hexdigest(),
            "provenance": '{"source_values":{"CYP3A4_pIC50":"SENTINEL_OUTCOME"}}',
        }
    ]
    tdc_rows = [] if missing_molecule else [
        {
            "molecule_id": "tdc-1",
            "standardized_structure": "CCC",
            "standardized_structure_hash": sha256(b"CCC").hexdigest(),
            "provenance": '{"source_label_raw":"SENTINEL_OUTCOME"}',
        }
    ]
    _write_csv(
        prediction_root / "octant" / "molecules.csv",
        (
            "molecule_id",
            "standardized_structure",
            "standardized_structure_hash",
            "provenance",
        ),
        octant_rows,
    )
    _write_csv(
        prediction_root / "tdc" / "molecules.csv",
        (
            "molecule_id",
            "standardized_structure",
            "standardized_structure_hash",
            "provenance",
        ),
        tdc_rows,
    )
    prediction_outputs = {
        "octant/molecules.csv": _hash(
            prediction_root / "octant" / "molecules.csv"
        ),
        "tdc/molecules.csv": _hash(prediction_root / "tdc" / "molecules.csv"),
    }
    prediction_manifest = {
        "outputs": prediction_outputs,
        "aggregate_sha256": _mapping_hash(prediction_outputs),
    }
    _write_json(
        prediction_root / "prediction_input_manifest.json", prediction_manifest
    )

    prediction_rows = [
        {
            "benchmark": "tdc_admet_group",
            "task": "cyp2c9_veith",
            "molecule_id": "tdc-1",
            "prediction": "0.9",
        },
        {
            "benchmark": "octant_cyp",
            "task": "cyp3a4_active_preincubation_pIC50",
            "molecule_id": "oct-1",
            "prediction": "5.1",
        },
    ]
    if duplicate_key:
        prediction_rows.append(dict(prediction_rows[0]))
    prediction_path = retained_root / "retained_mean_heldout_predictions.csv"
    _write_csv(
        prediction_path,
        ("benchmark", "task", "molecule_id", "prediction"),
        prediction_rows,
    )
    retained_outputs = {prediction_path.name: _hash(prediction_path)}
    retained_manifest = {
        "outputs": retained_outputs,
        "aggregate_sha256": _mapping_hash(retained_outputs),
    }
    retained_manifest_path = retained_root / "retained_mean_prediction_manifest.json"
    _write_json(retained_manifest_path, retained_manifest)

    expected_path = tmp_path / "expected.csv"
    expected_rows = [
        {
            "benchmark": "octant_cyp",
            "task": "cyp3a4_active_preincubation_pIC50",
            "molecule_id": "oct-1",
            "standardized_structure": "CC",
            "standardized_structure_hash": sha256(b"CC").hexdigest(),
        },
        {
            "benchmark": "tdc_admet_group",
            "task": "cyp2c9_veith",
            "molecule_id": "tdc-1",
            "standardized_structure": "CCC",
            "standardized_structure_hash": sha256(b"CCC").hexdigest(),
        },
    ]
    _write_csv(expected_path, CHEMELEON_INPUT_COLUMNS, expected_rows)
    expected_output_hash = _hash(expected_path)
    expected_key_material = "\n".join(
        "|".join(row[field] for field in CHEMELEON_INPUT_COLUMNS[:3])
        for row in expected_rows
    )
    expected_key_hash = sha256(expected_key_material.encode()).hexdigest()
    expected_aggregate = _mapping_hash(
        {"chemeleon_inference_input.csv": expected_output_hash}
    )

    contract = tmp_path / "contract.json"
    _write_json(
        contract,
        {
            "benchmark_input": {
                "prediction_input_manifest_sha256": _hash(
                    prediction_root / "prediction_input_manifest.json"
                ),
                "prediction_input_aggregate_sha256": prediction_manifest[
                    "aggregate_sha256"
                ],
            },
            "population_key_source": {
                "manifest_sha256": _hash(retained_manifest_path),
                "aggregate_sha256": retained_manifest["aggregate_sha256"],
                "prediction_csv_sha256": _hash(prediction_path),
            },
            "expected_task_counts": {
                "cyp2c9_veith": 2 if duplicate_key else 1,
                "cyp3a4_active_preincubation_pIC50": 1,
            },
            "model_facing_projection": {
                "expected_output_sha256": expected_output_hash,
                "expected_population_key_sha256": expected_key_hash,
                "expected_aggregate_sha256": expected_aggregate,
            },
        },
    )
    return prediction_root, retained_root, contract


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


def _mapping_hash(values: dict[str, str]) -> str:
    material = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    return sha256(material.encode()).hexdigest()
