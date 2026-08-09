from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cypshift.audit import AuditError, run_audit
from cypshift.cli import main

FIXTURE = Path(__file__).parents[1] / "examples" / "synthetic"


def test_fixture_audit_writes_canonical_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    result = run_audit(
        FIXTURE / "molecules.csv", FIXTURE / "measurements.csv", output
    )

    assert sorted(path.name for path in output.iterdir()) == [
        "audit.json",
        "measurements.csv",
        "molecules.csv",
    ]
    assert result.report["summary"] == {
        "measurements_linked_to_quarantined_molecules": 1,
        "measurements_total": 11,
        "molecules_accepted": 7,
        "molecules_quarantined": 1,
        "molecules_total": 8,
        "standardization_changes": 2,
        "standardized_duplicates": 1,
        "warning_counts": {
            "duplicate_standardized_structure": 1,
            "invalid_structure": 1,
            "multiple_fragments_input": 2,
            "standardization_changed": 2,
            "stereochemistry_unspecified": 1,
        },
    }

    with (output / "molecules.csv").open(encoding="utf-8", newline="") as file:
        molecules = {row["molecule_id"]: row for row in csv.DictReader(file)}
    assert molecules["syn-006"]["raw_structure"] == "not-a-smiles"
    assert molecules["syn-006"]["status"] == "quarantined"
    assert molecules["syn-003"]["standardization_changed"] == "true"
    assert molecules["syn-002"]["duplicate_of"] == "syn-001"


def test_audit_json_is_stable_and_contains_input_hashes(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    run_audit(FIXTURE / "molecules.csv", FIXTURE / "measurements.csv", first)
    run_audit(FIXTURE / "molecules.csv", FIXTURE / "measurements.csv", second)

    assert (first / "audit.json").read_bytes() == (second / "audit.json").read_bytes()
    report = json.loads((first / "audit.json").read_text(encoding="utf-8"))
    assert len(report["inputs"]["molecules"]["sha256"]) == 64
    assert len(report["inputs"]["measurements"]["sha256"]) == 64


def test_audit_refuses_to_overwrite_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(AuditError, match="never overwrites"):
        run_audit(
            FIXTURE / "molecules.csv", FIXTURE / "measurements.csv", output
        )


def test_audit_rejects_unknown_columns_without_silent_loss(tmp_path: Path) -> None:
    molecules = tmp_path / "molecules.csv"
    molecules.write_text(
        "molecule_id,structure,structure_format,source,provenance,unexpected\n"
        "one,CCO,smiles,test,test,value\n",
        encoding="utf-8",
    )

    with pytest.raises(AuditError, match="columns do not match"):
        run_audit(molecules, FIXTURE / "measurements.csv", tmp_path / "out")


def test_audit_cli_reports_counts_and_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cli-audit"

    status = main(
        [
            "audit",
            str(FIXTURE / "molecules.csv"),
            "--measurements",
            str(FIXTURE / "measurements.csv"),
            "--out",
            str(output),
        ]
    )

    assert status == 0
    message = capsys.readouterr().out
    assert "7 accepted, 1 quarantined" in message
    assert f"Outputs: {output}" in message
