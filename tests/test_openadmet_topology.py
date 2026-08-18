from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from rdkit import DataStructs
from test_openadmet_cyp import _fixture

from cypshift import openadmet_topology
from cypshift.openadmet_cyp import prepare_openadmet_cyp
from cypshift.openadmet_topology import (
    MOLECULE_AUDIT_COLUMNS,
    TOPOLOGY_COLUMNS,
    OpenADMETTopologyError,
    audit_openadmet_topology,
)


def _prepared(tmp_path: Path) -> Path:
    fixture = _fixture(tmp_path)
    output = tmp_path / "r1"
    prepare_openadmet_cyp(
        fixture["root"],
        output,
        source_revision=fixture["revision"],
        receipts_path=fixture["receipts"],
    )
    return output


def _update_manifest(input_directory: Path, filename: str) -> None:
    path = input_directory / filename
    manifest_path = input_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data = path.read_bytes()
    manifest["outputs"][filename]["sha256"] = hashlib.sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_topology_is_deterministic_and_excludes_test_rows(tmp_path: Path) -> None:
    input_directory = _prepared(tmp_path)
    first = audit_openadmet_topology(input_directory, tmp_path / "topology-1")
    second = audit_openadmet_topology(input_directory, tmp_path / "topology-2")
    for name in (
        "molecule_audit.csv",
        "training_topology.csv",
        "topology_manifest.json",
    ):
        assert (first.manifest_path.parent / name).read_bytes() == (
            second.manifest_path.parent / name
        ).read_bytes()
    with first.training_topology_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == TOPOLOGY_COLUMNS
    assert all(not row["molecule_id"].startswith("test-") for row in rows)
    with first.molecule_audit_path.open(encoding="utf-8", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    assert tuple(audit_rows[0]) == MOLECULE_AUDIT_COLUMNS
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["scope"]["family_semantics_authority"] is False


def test_receipt_valid_non_csv_source_rows_are_not_parsed(tmp_path: Path) -> None:
    input_directory = _prepared(tmp_path)
    source_rows = input_directory / "source_rows.csv"
    source_rows.write_bytes(b"not csv\n" * 8)
    _update_manifest(input_directory, "source_rows.csv")
    result = audit_openadmet_topology(input_directory, tmp_path / "topology")
    assert result.topology_rows > 0


def test_r1_manifest_schema_drift_fails_closed(tmp_path: Path) -> None:
    input_directory = _prepared(tmp_path)
    manifest_path = input_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "wrong"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(OpenADMETTopologyError, match="manifest schema"):
        audit_openadmet_topology(input_directory, tmp_path / "topology")


def test_test_chemistry_perturbation_does_not_change_training_topology(
    tmp_path: Path,
) -> None:
    input_directory = _prepared(tmp_path)
    baseline = audit_openadmet_topology(input_directory, tmp_path / "baseline")
    molecule_path = input_directory / "molecules_input.csv"
    text = molecule_path.read_text(encoding="utf-8")
    molecule_path.write_text(
        text.replace("test-1,CCO", "test-1,C", 1), encoding="utf-8"
    )
    _update_manifest(input_directory, "molecules_input.csv")
    perturbed = audit_openadmet_topology(input_directory, tmp_path / "perturbed")
    assert baseline.training_topology_path.read_bytes() == (
        perturbed.training_topology_path.read_bytes()
    )


def test_standardized_train_test_overlap_is_reported_but_test_is_ungrouped(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    train_path = fixture["root"] / "cyp-challenge-TRAIN_Emax.csv"
    train_text = train_path.read_text(encoding="utf-8")
    train_path.write_text(
        train_text.replace("train-1,CCC", "train-1,CCO", 1), encoding="utf-8"
    )
    receipts = json.loads(fixture["receipts"].read_text(encoding="utf-8"))
    for entry in receipts["sources"]["dataset"]["files"]:
        if entry["path"] == train_path.name:
            data = train_path.read_bytes()
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            entry["size_bytes"] = len(data)
    fixture["receipts"].write_text(json.dumps(receipts), encoding="utf-8")
    input_directory = tmp_path / "r1"
    prepare_openadmet_cyp(
        fixture["root"],
        input_directory,
        source_revision=fixture["revision"],
        receipts_path=fixture["receipts"],
    )
    result = audit_openadmet_topology(input_directory, tmp_path / "topology")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["exact_standardized_train_test_overlap"]["count"] == 1
    with result.training_topology_path.open(encoding="utf-8", newline="") as handle:
        assert all(
            not row["molecule_id"].startswith("test-") for row in csv.DictReader(handle)
        )
    assert manifest["downstream_modeling"]["blocked"] is True


def test_exact_standardized_duplicates_share_both_group_ids(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    source_path = fixture["root"] / "cyp-challenge-TRAIN_TDI.csv"
    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace(
            "train-2,CNC", "train-2,COC", 1
        ),
        encoding="utf-8",
    )
    receipts = json.loads(fixture["receipts"].read_text(encoding="utf-8"))
    for entry in receipts["sources"]["dataset"]["files"]:
        if entry["path"] == source_path.name:
            data = source_path.read_bytes()
            entry.update(
                {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
            )
    fixture["receipts"].write_text(json.dumps(receipts), encoding="utf-8")
    input_directory = tmp_path / "r1"
    prepare_openadmet_cyp(
        fixture["root"],
        input_directory,
        source_revision=fixture["revision"],
        receipts_path=fixture["receipts"],
    )
    result = audit_openadmet_topology(input_directory, tmp_path / "topology")
    with result.training_topology_path.open(encoding="utf-8", newline="") as handle:
        rows = {
            row["molecule_id"]: row
            for row in csv.DictReader(handle)
            if row["molecule_id"] in {"train-2", "train-3"}
        }
    assert (
        rows["train-2"]["standardized_structure_hash"]
        == rows["train-3"]["standardized_structure_hash"]
    )
    assert (
        rows["train-2"]["similarity_component_hash"]
        == rows["train-3"]["similarity_component_hash"]
    )
    assert (
        rows["train-2"]["scaffold_group_hash"] == rows["train-3"]["scaffold_group_hash"]
    )


def test_similarity_components_are_transitive(monkeypatch: pytest.MonkeyPatch) -> None:
    structures = {"a" * 64: "CCO", "b" * 64: "CCN", "c" * 64: "CCC"}
    scaffolds = {key: key for key in structures}

    def chain_similarity(_first: Any, rest: list[Any]) -> list[float]:
        return [0.7] * len(rest) if len(rest) == 1 else [0.7, 0.1]

    monkeypatch.setattr(DataStructs, "BulkTanimotoSimilarity", chain_similarity)
    components, _pairs, edges, _crossing = openadmet_topology._similarity_groups(
        structures, scaffolds
    )
    assert edges == 2
    assert len(set(components.values())) == 1


def test_scaffold_groups_keep_acyclic_exact_fallback_separate() -> None:
    groups = openadmet_topology._scaffold_groups(
        {"a" * 64: "CCO", "b" * 64: "c1ccccc1"}
    )
    assert groups["a" * 64] != groups["b" * 64]


def test_test_quarantine_is_visible_and_blocks_downstream(tmp_path: Path) -> None:
    input_directory = _prepared(tmp_path)
    molecule_path = input_directory / "molecules_input.csv"
    molecule_path.write_text(
        molecule_path.read_text(encoding="utf-8").replace("test-1,CCO", "test-1,[", 1),
        encoding="utf-8",
    )
    _update_manifest(input_directory, "molecules_input.csv")
    result = audit_openadmet_topology(input_directory, tmp_path / "topology")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"]["quarantined_test_molecules"] == 1
    assert "test_molecule_quarantine" in manifest["downstream_modeling"]["reasons"]


def test_ambiguous_provenance_fails_closed(tmp_path: Path) -> None:
    input_directory = _prepared(tmp_path)
    molecule_path = input_directory / "molecules_input.csv"
    rows: list[dict[str, str]]
    with molecule_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["provenance"] = json.dumps(
        {
            "occurrences": [
                {"source_file": "cyp-challenge-TEST-BLINDED.csv"},
                {"source_file": "cyp-challenge-TRAIN_Emax.csv"},
            ]
        }
    )
    with molecule_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    _update_manifest(input_directory, "molecules_input.csv")
    with pytest.raises(OpenADMETTopologyError, match="ambiguously mixes"):
        audit_openadmet_topology(input_directory, tmp_path / "topology")


def test_output_overwrite_is_refused(tmp_path: Path) -> None:
    input_directory = _prepared(tmp_path)
    output = tmp_path / "topology"
    audit_openadmet_topology(input_directory, output)
    with pytest.raises(OpenADMETTopologyError, match="refusing overwrite"):
        audit_openadmet_topology(input_directory, output)
