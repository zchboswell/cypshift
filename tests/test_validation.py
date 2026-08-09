from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cypshift.audit import (
    MEASUREMENT_COLUMNS,
    MOLECULE_INPUT_COLUMNS,
    run_audit,
)
from cypshift.tdc import TDC_SPLIT_COLUMNS, TDC_TASKS
from cypshift.validation import (
    ValidationDataError,
    audit_tdc_official_splits,
    freeze_octant_grouped_split,
)


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _measurement(molecule_id: str, value: str, isoform: str = "CYP3A4") -> dict[str, str]:
    return {
        "measurement_id": f"{molecule_id}:measurement",
        "molecule_id": molecule_id,
        "endpoint": "benchmark_endpoint",
        "isoform": isoform,
        "nadph_condition": "not_reported",
        "probe": "not_reported",
        "readout": "benchmark_readout",
        "value": value,
        "lower_bound": "",
        "upper_bound": "",
        "censoring": "none",
        "unit": "benchmark_unit",
        "quality": "synthetic_test",
        "source": "synthetic_test",
        "provenance": "synthetic_test",
    }


def _audit(
    root: Path,
    molecule_rows: list[dict[str, str]],
    measurement_rows: list[dict[str, str]],
) -> Path:
    root.mkdir()
    molecules_path = root / "molecules_input.csv"
    measurements_path = root / "measurements_input.csv"
    _write_csv(molecules_path, MOLECULE_INPUT_COLUMNS, molecule_rows)
    _write_csv(measurements_path, MEASUREMENT_COLUMNS, measurement_rows)
    canonical = root / "canonical"
    run_audit(molecules_path, measurements_path, canonical)
    return canonical


def test_octant_grouped_split_is_deterministic_and_scaffold_safe(
    tmp_path: Path,
) -> None:
    structures = [
        "c1ccccc1",
        "Cc1ccccc1",
        "C1CCCCC1",
        "CC1CCCCC1",
        "c1ccncc1",
        "Cc1ccncc1",
        "c1ccoc1",
        "Cc1ccoc1",
        "CCO",
        "CCN",
    ]
    molecules = [
        {
            "molecule_id": f"octant-{index:02d}",
            "structure": structure,
            "structure_format": "smiles",
            "source": "synthetic_octant",
            "provenance": "synthetic_octant",
        }
        for index, structure in enumerate(structures)
    ]
    measurements = [
        _measurement(f"octant-{index:02d}", str(5.0 + index / 10))
        for index in range(8)
    ]
    canonical = _audit(tmp_path / "octant", molecules, measurements)

    first = freeze_octant_grouped_split(canonical, tmp_path / "first")
    second = freeze_octant_grouped_split(canonical, tmp_path / "second")

    assert first.split_path.read_bytes() == second.split_path.read_bytes()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    with first.split_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    by_id = {row["molecule_id"]: row for row in rows}
    assert by_id["octant-00"]["group_hash"] == by_id["octant-01"]["group_hash"]
    assert by_id["octant-00"]["outer_fold"] == by_id["octant-01"]["outer_fold"]
    assert by_id["octant-08"]["group_type"] == "acyclic_exact_structure"
    assert {row["outer_partition"] for row in rows} == {"train", "validation"}
    assert {row["inner_fold"] for row in rows if row["inner_fold"]} == {
        "0",
        "1",
        "2",
        "3",
    }
    assert manifest["rows"] == 10
    assert manifest["measured_rows"] == 8
    assert manifest["unmeasured_rows"] == 2


def test_tdc_split_audit_preserves_official_and_flags_standardized_overlap(
    tmp_path: Path,
) -> None:
    molecules = []
    measurements = []
    split_rows = []
    isoforms = dict(TDC_TASKS)
    for task, isoform in isoforms.items():
        source_rows = [
            ("train_val", "C(C)O", "0"),
            ("train_val", "c1ccncc1", "1"),
            ("test", "CCO", "0"),
            ("test", "C1CCCCC1", "1"),
        ]
        for index, (partition, structure, label) in enumerate(source_rows, start=1):
            molecule_id = f"tdc:{task}:{partition}:{index:05d}"
            molecules.append(
                {
                    "molecule_id": molecule_id,
                    "structure": structure,
                    "structure_format": "smiles",
                    "source": f"synthetic_tdc/{task}",
                    "provenance": "synthetic_tdc",
                }
            )
            measurements.append(_measurement(molecule_id, label, isoform))
            split_rows.append(
                {
                    "molecule_id": molecule_id,
                    "task": task,
                    "partition": partition,
                    "source_row": str(index + 1),
                }
            )
    canonical = _audit(tmp_path / "tdc", molecules, measurements)
    split_path = tmp_path / "official_split.csv"
    _write_csv(split_path, TDC_SPLIT_COLUMNS, split_rows)

    first = audit_tdc_official_splits(canonical, split_path, tmp_path / "first")
    second = audit_tdc_official_splits(canonical, split_path, tmp_path / "second")

    assert first.report_path.read_bytes() == second.report_path.read_bytes()
    assert first.exclusions_path.read_bytes() == second.exclusions_path.read_bytes()
    report = json.loads(first.report_path.read_text(encoding="utf-8"))
    assert first.exclusion_count == 3
    assert report["metric"] == {
        "direction": "higher_is_better",
        "name": "AUPRC",
    }
    assert report["public_test_evaluations"] == 0
    for task in TDC_TASKS:
        overlap = report["tasks"][task]["standardized_structure_overlap"]
        assert overlap == {
            "conflicting_label_structures": 0,
            "structures": 1,
            "test_rows": 1,
            "train_val_rows": 1,
        }
        assert report["tasks"][task]["raw_structure_overlap"]["structures"] == 0


def test_validation_artifacts_refuse_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(ValidationDataError, match="output path already exists"):
        freeze_octant_grouped_split(tmp_path / "missing", output)
