from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from cypshift.audit import run_audit
from cypshift.benchmark import (
    OCTANT_ASSAY_WARNING,
    OCTANT_INHIBITION_COLUMNS,
    OCTANT_NADPH_CONDITION,
    BenchmarkDataError,
    prepare_octant_inhibition,
)


def _row(molecule_id: str = "OCNT-TEST-001") -> dict[str, str]:
    return {
        "ocnt_batch": molecule_id,
        "CYP3A4_pIC50": "6.25",
        "CYP3A4_pIC50_se": "0.05",
        "CYP3A4_pIC50_ci_lower": "6.15",
        "CYP3A4_pIC50_ci_upper": "6.35",
        "slope_log2": "0.2",
        "emax_log2fc": "-4.1",
        "activity_status": "YES",
        "rollover_status": "NO",
        "saturation_status": "YES",
        "direction": "DOWN",
        "drc_qc_status": "PASS",
        "drc_qc_flag": "PASS",
        "qc_flag_primary": "PASS",
        "plate_qc_status": "PASS",
        "standardized_smiles": " CCO ",
    }


def _write_source(
    path: Path,
    rows: list[dict[str, str]],
    *,
    columns: tuple[str, ...] = OCTANT_INHIBITION_COLUMNS,
) -> str:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_octant_adapter_preserves_context_and_reuses_canonical_audit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inhibition.tsv"
    expected_hash = _write_source(
        source, [_row(), _row("OCNT-TEST-002")]
    )

    result = prepare_octant_inhibition(
        source,
        tmp_path / "adapter",
        source_revision="frozen-revision",
        expected_sha256=expected_hash,
    )
    canonical = run_audit(
        result.molecules_path,
        result.measurements_path,
        tmp_path / "canonical",
    )

    with result.molecules_path.open(encoding="utf-8", newline="") as handle:
        molecule_rows = list(csv.DictReader(handle))
    with result.measurements_path.open(encoding="utf-8", newline="") as handle:
        measurement_rows = list(csv.DictReader(handle))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.row_count == 2
    assert molecule_rows[0]["structure"] == " CCO "
    assert measurement_rows[0]["nadph_condition"] == OCTANT_NADPH_CONDITION
    assert measurement_rows[0]["probe"] == "DBOMF"
    assert measurement_rows[0]["readout"] == "fluorescence"
    provenance = json.loads(measurement_rows[0]["provenance"])
    assert provenance["assay_warning"] == OCTANT_ASSAY_WARNING
    assert provenance["source_values"]["CYP3A4_pIC50_se"] == "0.05"
    assert manifest["source_revision"] == "frozen-revision"
    assert manifest["assay_context"]["warning"] == OCTANT_ASSAY_WARNING
    assert manifest["measurement_omissions"] == {
        "missing_source_CYP3A4_pIC50": 0
    }
    assert canonical.report["summary"]["molecules_accepted"] == 2
    assert canonical.report["summary"]["measurements_total"] == 2
    assert canonical.molecules[0].raw_structure == " CCO "
    assert "input_structure_whitespace" in canonical.molecules[0].warnings


def test_octant_adapter_retains_molecules_without_numeric_results(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inhibition.tsv"
    missing = _row("OCNT-TEST-MISSING")
    for field in (
        "CYP3A4_pIC50",
        "CYP3A4_pIC50_se",
        "CYP3A4_pIC50_ci_lower",
        "CYP3A4_pIC50_ci_upper",
    ):
        missing[field] = ""
    expected_hash = _write_source(source, [_row(), missing])

    result = prepare_octant_inhibition(
        source,
        tmp_path / "adapter",
        source_revision="frozen-revision",
        expected_sha256=expected_hash,
    )

    with result.molecules_path.open(encoding="utf-8", newline="") as handle:
        molecule_rows = list(csv.DictReader(handle))
    with result.measurements_path.open(encoding="utf-8", newline="") as handle:
        measurement_rows = list(csv.DictReader(handle))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert len(molecule_rows) == 2
    assert len(measurement_rows) == 1
    missing_provenance = json.loads(molecule_rows[1]["provenance"])
    assert missing_provenance["measurement_status"] == "missing_source_pIC50"
    assert missing_provenance["source_values"]["plate_qc_status"] == "PASS"
    assert manifest["measurement_omissions"] == {
        "missing_source_CYP3A4_pIC50": 1
    }


def test_octant_adapter_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "inhibition.tsv"
    _write_source(source, [_row()])

    with pytest.raises(BenchmarkDataError, match="source hash mismatch"):
        prepare_octant_inhibition(
            source,
            tmp_path / "adapter",
            source_revision="frozen-revision",
            expected_sha256="0" * 64,
        )


def test_octant_adapter_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    source = tmp_path / "inhibition.tsv"
    expected_hash = _write_source(source, [_row(), _row()])

    with pytest.raises(BenchmarkDataError, match="duplicate Octant ocnt_batch"):
        prepare_octant_inhibition(
            source,
            tmp_path / "adapter",
            source_revision="frozen-revision",
            expected_sha256=expected_hash,
        )


def test_octant_adapter_rejects_nonfinite_measurement(tmp_path: Path) -> None:
    source = tmp_path / "inhibition.tsv"
    row = _row()
    row["CYP3A4_pIC50"] = "nan"
    expected_hash = _write_source(source, [row])

    with pytest.raises(BenchmarkDataError, match="must be finite"):
        prepare_octant_inhibition(
            source,
            tmp_path / "adapter",
            source_revision="frozen-revision",
            expected_sha256=expected_hash,
        )


def test_octant_adapter_rejects_uncertainty_without_measurement(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inhibition.tsv"
    row = _row()
    row["CYP3A4_pIC50"] = ""
    expected_hash = _write_source(source, [row])

    with pytest.raises(BenchmarkDataError, match="uncertainty values"):
        prepare_octant_inhibition(
            source,
            tmp_path / "adapter",
            source_revision="frozen-revision",
            expected_sha256=expected_hash,
        )


def test_octant_adapter_rejects_schema_drift_and_overwrite(
    tmp_path: Path,
) -> None:
    drifted_source = tmp_path / "drifted.tsv"
    drifted_columns = OCTANT_INHIBITION_COLUMNS[:-1]
    drifted_hash = _write_source(
        drifted_source,
        [{key: value for key, value in _row().items() if key in drifted_columns}],
        columns=drifted_columns,
    )
    with pytest.raises(BenchmarkDataError, match="columns do not match"):
        prepare_octant_inhibition(
            drifted_source,
            tmp_path / "drifted-adapter",
            source_revision="frozen-revision",
            expected_sha256=drifted_hash,
        )

    source = tmp_path / "inhibition.tsv"
    expected_hash = _write_source(source, [_row()])
    output = tmp_path / "adapter"
    output.mkdir()
    with pytest.raises(BenchmarkDataError, match="output path already exists"):
        prepare_octant_inhibition(
            source,
            output,
            source_revision="frozen-revision",
            expected_sha256=expected_hash,
        )
