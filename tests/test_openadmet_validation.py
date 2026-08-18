from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_openadmet_cyp import _fixture

from cypshift.openadmet_cyp import OPENADMET_SOURCE_FILES, prepare_openadmet_cyp
from cypshift.openadmet_topology import audit_openadmet_topology
from cypshift.openadmet_validation import (
    FOLD_COLUMNS,
    OBSERVATION_COLUMNS,
    OpenADMETValidationError,
    build_openadmet_validation_inputs,
)

ROOT = Path(__file__).parents[1]
BASE_CONTRACT = ROOT / "benchmarks" / "openadmet_cyp_2026" / "validation_contract.json"
DIRECT_FILE = "cyp-challenge-TRAIN_inhibition.csv"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _direct_rows(header: list[str], *, shift: float = 0.0) -> list[dict[str, str]]:
    identities = [
        ("direct-0", "CCCl"),
        ("direct-1", "c1ccncc1"),
        ("direct-2", "CC(=O)O"),
        ("direct-3", "C1CCCCC1"),
        ("direct-4", "CCCl"),
        ("direct-5", "CCCCO"),
    ]
    rows = [dict.fromkeys(header, "") for _ in identities]
    for row, (name, smiles) in zip(rows, identities, strict=True):
        row["Molecule_Name"] = name
        row["SMILES"] = smiles
    prefix = "CYP1A2_pIC50_direct_inhibition"
    rows[0][prefix] = str(5.0 + shift)
    rows[0][f"{prefix}_conf_low"] = str(4.8 + shift)
    rows[0][f"{prefix}_conf_high"] = str(5.2 + shift)
    rows[0][f"{prefix}_std"] = "0.1"
    partial = "CYP2C9_pIC50_direct_inhibition"
    rows[0][partial] = str(4.0 + shift)
    rows[0][f"{partial}_std"] = "0.2"
    orphan = "CYP2D6_pIC50_direct_inhibition"
    rows[0][f"{orphan}_conf_low"] = "3.0"
    for index, row in enumerate(rows[1:], start=1):
        for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"):
            base = f"{endpoint}_pIC50_direct_inhibition"
            point = 4.0 + index / 10 + shift
            row[base] = str(point)
            row[f"{base}_conf_low"] = str(point - 0.2)
            row[f"{base}_conf_high"] = str(point + 0.2)
            row[f"{base}_std"] = "0.1"
    return rows


def _chain(
    root: Path,
    *,
    shift: float = 0.0,
    mutate: Callable[[list[dict[str, str]]], None] | None = None,
) -> dict[str, Any]:
    root.mkdir()
    fixture = _fixture(root)
    receipts = json.loads(fixture["receipts"].read_text(encoding="utf-8"))
    entry = next(
        item
        for item in receipts["sources"]["dataset"]["files"]
        if item["path"] == DIRECT_FILE
    )
    rows = _direct_rows(entry["header"], shift=shift)
    if mutate is not None:
        mutate(rows)
    direct_path = fixture["root"] / DIRECT_FILE
    with direct_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=entry["header"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    entry.update(
        {
            "sha256": _digest(direct_path),
            "size_bytes": direct_path.stat().st_size,
            "rows": len(rows),
        }
    )
    fixture["receipts"].write_text(json.dumps(receipts), encoding="utf-8")
    r1 = root / "r1"
    prepare_openadmet_cyp(
        fixture["root"],
        r1,
        source_revision=fixture["revision"],
        receipts_path=fixture["receipts"],
    )
    topology = root / "topology"
    audit_openadmet_topology(r1, topology)
    contract = json.loads(BASE_CONTRACT.read_text(encoding="utf-8"))
    contract["input_chain"]["dataset_revision"] = fixture["revision"]
    contract["input_chain"]["direct_source"].update(
        {"sha256": _digest(direct_path), "rows": len(rows)}
    )
    contract["direct_compiler"]["row_contract"].update(
        {
            "source_identities": len(rows),
            "expected_rows": len(rows) * 4,
        }
    )
    contract["input_chain"]["r1_source_row_adapter"] = {
        "manifest_sha256": _digest(r1 / "manifest.json"),
        "molecules_sha256": _digest(r1 / "molecules_input.csv"),
        "source_rows_sha256": _digest(r1 / "source_rows.csv"),
    }
    contract["input_chain"]["r1_topology"].update(
        {
            "manifest_sha256": _digest(topology / "topology_manifest.json"),
            "molecule_audit_sha256": _digest(topology / "molecule_audit.csv"),
            "training_topology_sha256": _digest(topology / "training_topology.csv"),
        }
    )
    contract_path = root / "validation_contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return {
        "validation_contract_path": contract_path,
        "direct_source_path": direct_path,
        "r1_directory": r1,
        "topology_directory": topology,
        "source_revision": fixture["revision"],
        "dataset_root": fixture["root"],
    }


def _build(chain: dict[str, Any], output: Path) -> Any:
    return build_openadmet_validation_inputs(
        validation_contract_path=chain["validation_contract_path"],
        direct_source_path=chain["direct_source_path"],
        r1_directory=chain["r1_directory"],
        topology_directory=chain["topology_directory"],
        output_directory=output,
        source_revision=chain["source_revision"],
    )


def test_r2a_outputs_are_deterministic_and_preserve_all_states(tmp_path: Path) -> None:
    chain = _chain(tmp_path / "chain")
    first = _build(chain, tmp_path / "first")
    second = _build(chain, tmp_path / "second")
    for name in ("direct_observations.csv", "group_folds.csv", "manifest.json"):
        assert (first.manifest_path.parent / name).read_bytes() == (
            second.manifest_path.parent / name
        ).read_bytes()
    with first.observations_path.open(encoding="utf-8", newline="") as handle:
        observations = list(csv.DictReader(handle))
    assert tuple(observations[0]) == OBSERVATION_COLUMNS
    assert len(observations) == 24
    assert {row["value_state"] for row in observations} == {
        "missing",
        "complete",
        "partial",
        "orphan_auxiliary",
    }
    complete = next(
        row
        for row in observations
        if row["molecule_id"] == "direct-0" and row["endpoint"] == "CYP1A2"
    )
    assert complete["raw_point"] == "5.0"
    assert complete["anchor_eligible"] == "true"
    assert len(complete["observation_id"]) == 64
    with first.folds_path.open(encoding="utf-8", newline="") as handle:
        folds = list(csv.DictReader(handle))
    assert tuple(folds[0]) == FOLD_COLUMNS
    assert len(folds) == 6 * 3 * 5
    members: dict[str, set[str]] = {}
    for row in folds:
        members.setdefault(row["similarity_component_hash"], set()).add(
            row["molecule_id"]
        )
    assert any(len(values) > 1 for values in members.values())
    for repeat in range(3):
        by_molecule: dict[str, set[str]] = {}
        for row in folds:
            if int(row["repeat"]) == repeat:
                by_molecule.setdefault(row["molecule_id"], set()).add(row["outer_fold"])
        assert all(len(values) == 1 for values in by_molecule.values())
        for validation_fold in range(5):
            grouped: dict[str, list[dict[str, str]]] = {}
            for row in folds:
                if (
                    int(row["repeat"]) == repeat
                    and int(row["outer_validation_fold"]) == validation_fold
                ):
                    grouped.setdefault(row["similarity_component_hash"], []).append(row)
            for group_rows in grouped.values():
                assert len({row["outer_fold"] for row in group_rows}) == 1
                assert len({row["inner_fold"] for row in group_rows}) == 1
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["accounting"]["tdi_files_opened"] == 0
    assert manifest["accounting"]["blinded_test_files_opened"] == 0
    assert manifest["authority"]["validation"] is False
    assert manifest["authority"]["fold_assignments"] is False
    assert not any(manifest["authority"].values())


@pytest.mark.parametrize(
    ("column", "value", "match"),
    [
        ("CYP1A2_pIC50_direct_inhibition", "nan", "non-finite point"),
        ("CYP1A2_pIC50_direct_inhibition", "inf", "non-finite point"),
        ("CYP1A2_pIC50_direct_inhibition_std", "-1", "negative std"),
        ("CYP1A2_pIC50_direct_inhibition_conf_low", "5.1", "low bound excludes"),
        ("CYP1A2_pIC50_direct_inhibition_conf_high", "4.9", "high bound excludes"),
    ],
)
def test_invalid_measurement_fails_without_partial_output(
    tmp_path: Path, column: str, value: str, match: str
) -> None:
    chain = _chain(
        tmp_path / "chain", mutate=lambda rows: rows[0].__setitem__(column, value)
    )
    output = tmp_path / "output"
    with pytest.raises(OpenADMETValidationError, match=match):
        _build(chain, output)
    assert not output.exists()


def test_parent_receipt_drift_and_existing_output_fail_closed(tmp_path: Path) -> None:
    chain = _chain(tmp_path / "chain")
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(OpenADMETValidationError, match="already exists"):
        _build(chain, output)
    fresh = tmp_path / "fresh"
    direct = chain["direct_source_path"]
    direct.write_bytes(direct.read_bytes().replace(b"direct-0", b"direct-X", 1))
    with pytest.raises(OpenADMETValidationError, match="SHA-256 mismatch"):
        _build(chain, fresh)
    assert not fresh.exists()


def test_fold_bytes_ignore_direct_values_and_availability(tmp_path: Path) -> None:
    first_chain = _chain(tmp_path / "a")

    def remove_and_shift(rows: list[dict[str, str]]) -> None:
        rows[0]["CYP1A2_pIC50_direct_inhibition"] = ""
        rows[0]["CYP1A2_pIC50_direct_inhibition_conf_low"] = ""
        rows[0]["CYP1A2_pIC50_direct_inhibition_conf_high"] = ""
        rows[0]["CYP1A2_pIC50_direct_inhibition_std"] = ""
        rows[1]["CYP3A4_pIC50_direct_inhibition"] = "7.7"
        rows[1]["CYP3A4_pIC50_direct_inhibition_conf_low"] = "7.5"
        rows[1]["CYP3A4_pIC50_direct_inhibition_conf_high"] = "7.9"

    second_chain = _chain(tmp_path / "b", mutate=remove_and_shift)
    first = _build(first_chain, tmp_path / "first")
    second = _build(second_chain, tmp_path / "second")
    assert first.folds_path.read_bytes() == second.folds_path.read_bytes()
    assert first.observations_path.read_bytes() != second.observations_path.read_bytes()


def test_build_needs_only_direct_raw_file_after_parent_artifacts_exist(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path / "chain")
    for filename in OPENADMET_SOURCE_FILES:
        if filename != DIRECT_FILE:
            (chain["dataset_root"] / filename).unlink()
    result = _build(chain, tmp_path / "output")
    assert result.observation_count == 24


def test_result_affecting_contract_and_authority_drift_fail_closed(
    tmp_path: Path,
) -> None:
    chain = _chain(tmp_path / "chain")
    contract_path = chain["validation_contract_path"]
    original = json.loads(contract_path.read_text(encoding="utf-8"))
    variants = []
    state_drift = json.loads(json.dumps(original))
    state_drift["direct_compiler"]["state_rules"]["complete"] = "changed"
    variants.append(state_drift)
    algorithm_drift = json.loads(json.dumps(original))
    algorithm_drift["folds"]["assignment_algorithm"]["group_order"] = "changed"
    variants.append(algorithm_drift)
    authority_drift = json.loads(json.dumps(original))
    authority_drift["authority"]["models"] = "AUTHORIZED"
    variants.append(authority_drift)
    for index, variant in enumerate(variants):
        contract_path.write_text(json.dumps(variant), encoding="utf-8")
        output = tmp_path / f"output-{index}"
        with pytest.raises(OpenADMETValidationError, match="drift|expansion"):
            _build(chain, output)
        assert not output.exists()
