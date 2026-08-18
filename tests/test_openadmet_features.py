from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rdkit import rdBase

import cypshift.openadmet_features as feature_module
from cypshift.chemistry import STANDARDIZATION_VERSION, standardize_molecule
from cypshift.openadmet_features import (
    FEATURE_INPUT_COLUMNS,
    OpenADMETFeatureProjectionError,
    project_openadmet_feature_input,
)
from cypshift.openadmet_topology import TOPOLOGY_COLUMNS
from cypshift.openadmet_validation import FOLD_COLUMNS, OBSERVATION_COLUMNS
from cypshift.schema import MoleculeInput, MoleculeStatus


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _csv_bytes(columns: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _fixture(
    root: Path,
    *,
    raw_smiles: tuple[str, str] = ("CCO", "c1ccccc1"),
    suffix_value: str = "5.0",
) -> tuple[dict[str, Path], dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    direct_rows: list[dict[str, str]] = []
    topology_rows: list[dict[str, str]] = []
    fold_rows: list[dict[str, str]] = []
    for index, (molecule_id, smiles) in enumerate(
        zip(("mol-a", "mol-b"), raw_smiles, strict=True)
    ):
        if smiles == "C,C":
            standardized = smiles
        else:
            standardized = standardize_molecule(
                MoleculeInput(molecule_id, smiles, "smiles", "fixture", "{}")
            ).standardized_structure
        assert standardized is not None
        component = _digest(f"component-{molecule_id}".encode())
        topology_rows.append(
            {
                "molecule_id": molecule_id,
                "standardized_structure_hash": _digest(standardized.encode()),
                "similarity_component_hash": component,
                "scaffold_group_hash": _digest(f"scaffold-{molecule_id}".encode()),
            }
        )
        for extra in range(2):
            topology_rows.append(
                {
                    "molecule_id": f"extra-{index}-{extra}",
                    "standardized_structure_hash": _digest(b"CC"),
                    "similarity_component_hash": _digest(
                        f"extra-component-{index}-{extra}".encode()
                    ),
                    "scaffold_group_hash": _digest(b"extra-scaffold"),
                }
            )
        for repeat in range(3):
            for outer_fold in range(5):
                fold_rows.append(
                    {
                        "molecule_id": molecule_id,
                        "similarity_component_hash": component,
                        "repeat": str(repeat),
                        "seed": str(20260810 + repeat),
                        "outer_fold": str(outer_fold),
                        "outer_validation_fold": str(outer_fold),
                        "inner_fold": "",
                    }
                )
        for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"):
            direct_rows.append(
                {
                    "observation_id": _digest(
                        f"obs-{molecule_id}-{endpoint}".encode()
                    ),
                    "molecule_id": molecule_id,
                    "source_row_id": f"cyp-challenge-TRAIN_inhibition.csv:{index + 2}",
                    "source_file": "cyp-challenge-TRAIN_inhibition.csv",
                    "source_row": str(index + 2),
                    "source_sha256": _digest(b"synthetic-direct-source"),
                    "endpoint": endpoint,
                    "raw_smiles": smiles,
                    **{
                        column: suffix_value
                        for column in OBSERVATION_COLUMNS[8:]
                    },
                }
            )
    direct_data = _csv_bytes(OBSERVATION_COLUMNS, direct_rows)
    topology_data = _csv_bytes(TOPOLOGY_COLUMNS, topology_rows)
    folds_data = _csv_bytes(FOLD_COLUMNS, fold_rows)
    direct_path = root / "direct_observations.csv"
    topology_path = root / "training_topology.csv"
    folds_path = root / "group_folds.csv"
    direct_path.write_bytes(direct_data)
    topology_path.write_bytes(topology_data)
    folds_path.write_bytes(folds_data)
    chemistry_path = Path(feature_module.__file__).with_name("chemistry.py")
    lock_path = Path(feature_module.__file__).parents[2] / "uv.lock"
    hashes = {
        "direct_observations": _digest(direct_data),
        "group_folds": _digest(folds_data),
        "training_topology": _digest(topology_data),
    }
    contract: dict[str, Any] = {
        "schema_version": "cypshift.openadmet_cyp_2026.global_experiment_contract.v3",
        "scope": {"population": {"molecule_endpoint_cells": 8}},
        "inputs": {
            "direct_observations": {"sha256": hashes["direct_observations"]},
            "group_folds": {"sha256": hashes["group_folds"]},
            "training_topology": {"sha256": hashes["training_topology"]},
            "core_chemistry": {
                "standardization_policy_id": STANDARDIZATION_VERSION,
                "standardizer_source_sha256": _digest(chemistry_path.read_bytes()),
                "uv_lock_sha256": _digest(lock_path.read_bytes()),
                "python_version": __import__("platform").python_version(),
                "rdkit_version": rdBase.rdkitVersion,
            },
        },
        "r3a_chemistry_projection": {
            "direct_observation_prefix": list(OBSERVATION_COLUMNS[:8]),
            "inputs": {
                "direct_observations_sha256": hashes["direct_observations"],
                "group_folds_sha256": hashes["group_folds"],
                "training_topology_sha256": hashes["training_topology"],
            },
            "output": {
                "rows": 2,
                "columns": list(FEATURE_INPUT_COLUMNS),
                "serialization": "RFC4180 CSV with LF line endings and one terminal newline",
            },
            "expected_counts": {
                "molecules": 2,
                "direct_observations": 8,
                "topology_rows": 6,
                "group_fold_rows": 30,
                "ignored_topology_rows": 4,
            },
            "manifest": {"schema_version": "cypshift.openadmet_cyp_2026.feature_input.v1"},
        },
    }
    contract_path = root / "contract.json"
    contract_path.write_text(json.dumps(contract, sort_keys=True, indent=2) + "\n")
    return (
        {
            "direct": direct_path,
            "folds": folds_path,
            "topology": topology_path,
            "contract": contract_path,
        },
        contract,
    )


def _project(paths: dict[str, Path], output: Path) -> None:
    project_openadmet_feature_input(
        paths["direct"],
        paths["folds"],
        paths["topology"],
        output,
        contract_path=paths["contract"],
        expected_contract_sha256=_digest(paths["contract"].read_bytes()),
    )


def test_projection_is_deterministic_and_excludes_target_schema(tmp_path: Path) -> None:
    paths, _ = _fixture(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    _project(paths, first)
    _project(paths, second)
    assert (first / "feature_input.csv").read_bytes() == (second / "feature_input.csv").read_bytes()
    assert (first / "feature_input_manifest.json").read_bytes() == (second / "feature_input_manifest.json").read_bytes()
    output = (first / "feature_input.csv").read_text()
    assert output.splitlines()[0].split(",") == list(FEATURE_INPUT_COLUMNS)
    assert "point" not in output.splitlines()[0]
    manifest = json.loads((first / "feature_input_manifest.json").read_text())
    assert manifest["accounting"]["target_values_parsed"] == 0
    assert manifest["accounting"]["blinded_test_rows_opened"] == 0
    assert (first / "feature_input.csv").stat().st_mode & 0o222 == 0
    assert (first / "feature_input_manifest.json").stat().st_mode & 0o222 == 0
    assert first.stat().st_mode & 0o222 == 0
    with pytest.raises(OpenADMETFeatureProjectionError, match="refusing overwrite"):
        _project(paths, first)


def test_contract_receipt_is_verified_before_json_parse(tmp_path: Path) -> None:
    paths, _ = _fixture(tmp_path)
    expected = _digest(paths["contract"].read_bytes())
    paths["contract"].write_bytes(b"{not-json")
    with pytest.raises(OpenADMETFeatureProjectionError, match="SHA-256 mismatch"):
        project_openadmet_feature_input(
            paths["direct"],
            paths["folds"],
            paths["topology"],
            tmp_path / "out",
            contract_path=paths["contract"],
            expected_contract_sha256=expected,
        )


def test_quoted_comma_prefix_and_opaque_suffix_mutation_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, contract = _fixture(
        tmp_path,
        raw_smiles=("C,C", "CCO"),
        suffix_value='target,"quoted",9.9',
    )

    def fake_standardize(molecule: MoleculeInput) -> Any:
        return SimpleNamespace(
            status=MoleculeStatus.ACCEPTED,
            standardized_structure=molecule.structure,
        )

    monkeypatch.setattr(feature_module, "standardize_molecule", fake_standardize)
    # Rebind the first topology receipt to the fake standardizer's exact output.
    topology_rows = list(csv.DictReader(paths["topology"].open(newline="")))
    topology_rows[0]["standardized_structure_hash"] = _digest(b"C,C")
    topology_data = _csv_bytes(TOPOLOGY_COLUMNS, topology_rows)
    paths["topology"].write_bytes(topology_data)
    _rebind_hashes(paths, contract, "training_topology", topology_data)
    first = tmp_path / "first"
    _project(paths, first)

    mutated = tmp_path / "mutated"
    direct_data = paths["direct"].read_bytes().replace(
        b'target,""quoted"",9.9', b'changed,""suffix"",8.8', 1
    )
    paths["direct"].write_bytes(direct_data)
    _rebind_hashes(paths, contract, "direct_observations", direct_data)
    _project(paths, mutated)
    assert (first / "feature_input.csv").read_bytes() == (mutated / "feature_input.csv").read_bytes()


def _rebind_hashes(
    paths: dict[str, Path], contract: dict[str, Any], key: str, data: bytes
) -> None:
    contract["inputs"][key]["sha256"] = _digest(data)
    contract["r3a_chemistry_projection"]["inputs"][f"{key}_sha256"] = _digest(data)
    paths["contract"].write_text(json.dumps(contract, sort_keys=True, indent=2) + "\n")


def test_receipt_drift_cardinality_and_standardization_mismatch_fail_closed(
    tmp_path: Path,
) -> None:
    paths, contract = _fixture(tmp_path)
    paths["direct"].write_bytes(paths["direct"].read_bytes().replace(b"mol-a", b"mol-x", 1))
    with pytest.raises(OpenADMETFeatureProjectionError, match="SHA-256 mismatch"):
        _project(paths, tmp_path / "drift")

    paths, contract = _fixture(tmp_path / "topology")
    topology_rows = list(csv.DictReader(paths["topology"].open(newline="")))
    topology_rows[0]["standardized_structure_hash"] = _digest(b"wrong")
    topology_data = _csv_bytes(TOPOLOGY_COLUMNS, topology_rows)
    paths["topology"].write_bytes(topology_data)
    _rebind_hashes(paths, contract, "training_topology", topology_data)
    with pytest.raises(OpenADMETFeatureProjectionError, match="standardization receipt mismatch"):
        _project(paths, tmp_path / "chemistry")

    paths, contract = _fixture(tmp_path / "cardinality")
    topology_rows = list(csv.DictReader(paths["topology"].open(newline="")))[:-1]
    topology_data = _csv_bytes(TOPOLOGY_COLUMNS, topology_rows)
    paths["topology"].write_bytes(topology_data)
    _rebind_hashes(paths, contract, "training_topology", topology_data)
    with pytest.raises(OpenADMETFeatureProjectionError, match="row-count mismatch"):
        _project(paths, tmp_path / "cardinality-out")


@pytest.mark.parametrize(
    ("endpoint_mode", "replacement", "message"),
    [
        ("missing", "", "endpoint must be non-empty"),
        ("duplicate", "CYP2C9", "endpoint cardinality|duplicate endpoint"),
    ],
)
def test_endpoint_cardinality_fail_closed(
    tmp_path: Path, endpoint_mode: str, replacement: str, message: str
) -> None:
    paths, contract = _fixture(tmp_path / endpoint_mode)
    rows = list(csv.DictReader(paths["direct"].open(newline="")))
    rows[-1]["endpoint"] = replacement
    direct_data = _csv_bytes(OBSERVATION_COLUMNS, rows)
    paths["direct"].write_bytes(direct_data)
    _rebind_hashes(paths, contract, "direct_observations", direct_data)
    with pytest.raises(OpenADMETFeatureProjectionError, match=message):
        _project(paths, tmp_path / f"{endpoint_mode}-out")


def test_fold_component_and_cardinality_fail_closed(tmp_path: Path) -> None:
    paths, contract = _fixture(tmp_path / "component")
    rows = list(csv.DictReader(paths["folds"].open(newline="")))
    rows[0]["similarity_component_hash"] = _digest(b"wrong-component")
    fold_data = _csv_bytes(FOLD_COLUMNS, rows)
    paths["folds"].write_bytes(fold_data)
    _rebind_hashes(paths, contract, "group_folds", fold_data)
    with pytest.raises(OpenADMETFeatureProjectionError, match="topology mismatch"):
        _project(paths, tmp_path / "component-out")

    paths, contract = _fixture(tmp_path / "fold-count")
    rows = list(csv.DictReader(paths["folds"].open(newline="")))[:-1]
    fold_data = _csv_bytes(FOLD_COLUMNS, rows)
    paths["folds"].write_bytes(fold_data)
    _rebind_hashes(paths, contract, "group_folds", fold_data)
    with pytest.raises(OpenADMETFeatureProjectionError, match="row-count mismatch"):
        _project(paths, tmp_path / "fold-count-out")


@pytest.mark.parametrize(
    ("receipt", "expected_message"),
    [
        ("standardizer_source_sha256", "standardizer source hash mismatch"),
        ("uv_lock_sha256", "core uv.lock hash mismatch"),
        ("python_version", "core Python version mismatch"),
        ("rdkit_version", "core RDKit version mismatch"),
    ],
)
def test_core_receipt_drift_fails_before_standardization(
    tmp_path: Path,
    receipt: str,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, contract = _fixture(tmp_path / receipt)
    core = contract["inputs"]["core_chemistry"]
    core[receipt] = "0" * 64 if receipt.endswith("sha256") else "0.0.0"
    paths["contract"].write_text(json.dumps(contract, sort_keys=True, indent=2) + "\n")
    calls = 0

    def unexpected_standardization(molecule: MoleculeInput) -> Any:
        nonlocal calls
        calls += 1
        return standardize_molecule(molecule)

    monkeypatch.setattr(feature_module, "standardize_molecule", unexpected_standardization)
    with pytest.raises(OpenADMETFeatureProjectionError, match=expected_message):
        _project(paths, tmp_path / f"{receipt}-out")
    assert calls == 0


def test_atomic_output_cleanup_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _ = _fixture(tmp_path)
    original_write = feature_module._write_new
    calls = 0

    def fail_second_write(path: Path, data: bytes) -> None:
        nonlocal calls
        calls += 1
        original_write(path, data)
        if calls == 2:
            raise RuntimeError("synthetic write failure")

    monkeypatch.setattr(feature_module, "_write_new", fail_second_write)
    with pytest.raises(RuntimeError, match="synthetic write failure"):
        _project(paths, tmp_path / "atomic-out")
    assert not (tmp_path / "atomic-out").exists()
    assert not list(tmp_path.glob(".r3a-feature-input-*"))


def test_atomic_promotion_rejects_dangling_symlink_and_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, _ = _fixture(tmp_path / "symlink")
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(OpenADMETFeatureProjectionError, match="refusing overwrite"):
        _project(paths, dangling)
    assert dangling.is_symlink()

    race_paths, _ = _fixture(tmp_path / "race")
    destination = tmp_path / "race-out"
    original_rename = feature_module._rename_noreplace

    def create_destination(source: Path, target: Path) -> None:
        target.mkdir()
        original_rename(source, target)

    monkeypatch.setattr(feature_module, "_rename_noreplace", create_destination)
    with pytest.raises(OpenADMETFeatureProjectionError, match="refusing overwrite"):
        _project(race_paths, destination)
    assert destination.is_dir()
    assert not list(destination.iterdir())
