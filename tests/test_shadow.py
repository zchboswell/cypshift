from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
from rdkit import Chem, rdBase

import cypshift.shadow as shadow
from cypshift.shadow import (
    INPUT_COLUMNS,
    SHADOW_COLUMNS,
    ShadowContractError,
    assign_shadow_rows,
    prepare_shadow_input,
    summarize_shadow_rows,
)

ROOT = Path(__file__).resolve().parents[1]
TRACKED_CONTRACT = ROOT / "benchmarks" / "tdc_cyp_shadow_v1_contract.json"
IMPLEMENTATION_CONTRACT = (
    ROOT / "benchmarks" / "tdc_cyp_shadow_v1_implementation_contract.json"
)
LOCK_PATH = ROOT / "uv.lock"
TASKS = ("cyp2c9_veith", "cyp2d6_veith", "cyp3a4_veith")
STRUCTURES = ("CCO", "N", "O", "F", "c1ccccc1")
REVISION = "a" * 40


@dataclass(frozen=True, slots=True)
class Fixture:
    contract: Path
    implementation_contract: Path
    adapter_manifest: Path
    official_split: Path
    canonical_molecules: Path
    canonical_audit: Path
    measurements: Path
    measurement_manifest: Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _fixture(root: Path) -> Fixture:
    source = root / "sources"
    official_split = source / "official_split.csv"
    canonical_molecules = source / "molecules.csv"
    measurements = source / "train_val_measurements.csv"
    adapter_manifest = source / "adapter_manifest.json"
    canonical_audit = source / "audit.json"
    measurement_manifest = source / "prediction_input_manifest.json"

    split_rows: list[dict[str, str]] = []
    molecule_rows: list[dict[str, str]] = []
    measurement_rows: list[dict[str, str]] = []
    for task in TASKS:
        source_row = 2
        for structure_index, structure in enumerate(STRUCTURES):
            structure_hash = hashlib.sha256(structure.encode()).hexdigest()
            for label in (0, 1):
                raw_structure = (
                    f" {structure} "
                    if structure_index == 0 and label == 1
                    else structure
                )
                molecule_id = f"{task}:train:{structure_index}:{label}"
                split_rows.append(
                    {
                        "molecule_id": molecule_id,
                        "task": task,
                        "partition": "train_val",
                        "source_row": str(source_row),
                    }
                )
                molecule_rows.append(
                    {
                        "molecule_id": molecule_id,
                        "raw_structure": raw_structure,
                        "structure_format": "smiles",
                        "standardized_structure": structure,
                        "standardized_structure_hash": structure_hash,
                        "status": "accepted",
                        "stereochemistry_status": "none",
                        "input_fragments": "[]",
                        "standardization_changed": "false",
                        "duplicate_of": "",
                        "warnings": "[]",
                        "standardization_version": (
                            "rdkit-cleanup-fragment-parent-v1"
                        ),
                        "source": "fixture",
                        "provenance": f"DO_NOT_PARSE:source_label_raw={label}",
                    }
                )
                measurement_rows.append(
                    {"molecule_id": molecule_id, "value": f"{label}.0"}
                )
                source_row += 1
        test_id = f"{task}:test:0"
        test_structure = "Br"
        split_rows.append(
            {
                "molecule_id": test_id,
                "task": task,
                "partition": "test",
                "source_row": str(source_row),
            }
        )
        molecule_rows.append(
            {
                "molecule_id": test_id,
                "raw_structure": test_structure,
                "structure_format": "smiles",
                "standardized_structure": test_structure,
                "standardized_structure_hash": hashlib.sha256(
                    test_structure.encode()
                ).hexdigest(),
                "status": "accepted",
                "stereochemistry_status": "none",
                "input_fragments": "[]",
                "standardization_changed": "false",
                "duplicate_of": "",
                "warnings": "[]",
                "standardization_version": "rdkit-cleanup-fragment-parent-v1",
                "source": "fixture",
                "provenance": "DO_NOT_PARSE:source_label_raw=1",
            }
        )

    _write_csv(
        official_split,
        ("molecule_id", "task", "partition", "source_row"),
        list(reversed(split_rows)),
    )
    _write_csv(
        canonical_molecules,
        (
            "molecule_id",
            "raw_structure",
            "structure_format",
            "standardized_structure",
            "standardized_structure_hash",
            "status",
            "stereochemistry_status",
            "input_fragments",
            "standardization_changed",
            "duplicate_of",
            "warnings",
            "standardization_version",
            "source",
            "provenance",
        ),
        list(reversed(molecule_rows)),
    )
    _write_csv(measurements, ("molecule_id", "value"), measurement_rows)
    _write_json(
        adapter_manifest,
        {"outputs": {"official_split.csv": _hash(official_split)}},
    )
    _write_json(
        canonical_audit,
        {"outputs": {"molecules.csv": _hash(canonical_molecules)}},
    )
    _write_json(
        measurement_manifest,
        {"outputs": {"tdc/measurements.csv": _hash(measurements)}},
    )

    contract = copy.deepcopy(
        json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))
    )
    trusted = contract["source_contracts"]["trusted_input_projection_sources"]
    for name, path in {
        "adapter_manifest": adapter_manifest,
        "official_split": official_split,
        "canonical_molecules": canonical_molecules,
        "canonical_audit": canonical_audit,
    }.items():
        trusted[name] = {
            "expected_local_path": f"artifacts/fixture/{path.name}",
            "sha256": _hash(path),
        }
    measurement_contract = contract["source_contracts"][
        "train_val_measurements_for_post_assignment_summary_only"
    ]
    measurement_contract.update(
        {
            "expected_mount_path": str(measurements),
            "sha256": _hash(measurements),
            "rows": 30,
            "public_test_rows": 0,
            "parent_manifest": {
                "expected_local_path": str(measurement_manifest),
                "sha256": _hash(measurement_manifest),
            },
        }
    )
    contract["environment"].update(
        {
            "lock_sha256": _hash(LOCK_PATH),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "rdkit_version": rdBase.rdkitVersion,
            "numpy_version_on_python_3_11": version("numpy"),
        }
    )
    contract["population"].update(
        {
            "source_rows": 30,
            "task_rows": {task: 10 for task in TASKS},
            "unique_standardized_structures": 5,
            "task_unique_standardized_structures": {task: 5 for task in TASKS},
            "task_membership_by_unique_structure": {
                "one_task": 0,
                "two_tasks": 0,
                "three_tasks": 5,
            },
            "global_scaffold_groups": 5,
            "structure_task_cells": 15,
            "structure_task_cells_with_duplicate_rows": 15,
            "duplicate_excess_source_rows": 15,
            "structure_task_cells_with_conflicting_labels": 15,
            "unique_structures_in_conflicting_label_cells": 5,
            "standardized_hashes_with_multiple_distinct_raw_smiles": 1,
            "excess_distinct_raw_smiles_for_those_hashes": 1,
            "maximum_raw_smiles_per_standardized_hash": 2,
        }
    )
    contract["input_projection_contract"]["rows"]["expected_rows"] = 30
    contract["output_contract"]["shadow_rows"]["expected_rows"] = 30
    contract["protocols"]["community"]["pair_distances"] = 10
    contract["protocols"]["community"]["resource_cap"] = {
        "runtime_minutes": 120,
        "peak_rss_gib": 128,
        "failure_rule": "fixture cap",
    }
    contract_path = root / "shadow_contract.json"
    _write_json(contract_path, contract)
    implementation = copy.deepcopy(
        json.loads(IMPLEMENTATION_CONTRACT.read_text(encoding="utf-8"))
    )
    implementation["parent_contract"] = {
        "path": contract_path.name,
        "sha256": _hash(contract_path),
    }
    raw_counts = implementation["trusted_projection"]["raw_count_definitions"]
    raw_counts["expected_unique_raw_structures"] = 6
    raw_counts["expected_unique_standardized_hash_raw_pairs"] = 6
    implementation["assignment_environment"].update(
        {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "rdkit": rdBase.rdkitVersion,
            "numpy": version("numpy"),
            "lock_sha256": _hash(LOCK_PATH),
        }
    )
    implementation_path = root / "shadow_implementation_contract.json"
    _write_json(implementation_path, implementation)
    return Fixture(
        contract_path,
        implementation_path,
        adapter_manifest,
        official_split,
        canonical_molecules,
        canonical_audit,
        measurements,
        measurement_manifest,
    )


def _prepare(fixture: Fixture, output: Path) -> Any:
    return prepare_shadow_input(
        fixture.contract,
        fixture.implementation_contract,
        fixture.adapter_manifest,
        fixture.official_split,
        fixture.canonical_molecules,
        fixture.canonical_audit,
        output,
        source_revision=REVISION,
    )


def _assign(fixture: Fixture, input_root: Path, output: Path) -> Any:
    return assign_shadow_rows(
        fixture.contract,
        fixture.implementation_contract,
        input_root / "shadow_input_rows.csv",
        input_root / "shadow_input_manifest.json",
        LOCK_PATH,
        output,
        source_revision=REVISION,
    )


def _rebind_implementation_parent(fixture: Fixture) -> None:
    implementation = json.loads(
        fixture.implementation_contract.read_text(encoding="utf-8")
    )
    implementation["parent_contract"]["sha256"] = _hash(fixture.contract)
    _write_json(fixture.implementation_contract, implementation)


def test_shadow_input_is_stripped_deterministic_and_immutable(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path / "fixture")
    first = _prepare(fixture, tmp_path / "input-one")
    second = _prepare(fixture, tmp_path / "input-two")

    assert first.rows_path.read_bytes() == second.rows_path.read_bytes()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    assert b"DO_NOT_PARSE" not in first.rows_path.read_bytes()
    assert b"DO_NOT_PARSE" not in first.manifest_path.read_bytes()
    rows = _read_csv(first.rows_path)
    assert tuple(rows[0]) == INPUT_COLUMNS
    assert len(rows) == 30
    assert all(":test:" not in row["molecule_id"] for row in rows)
    assert all("provenance" not in row and "value" not in row for row in rows)
    assert all(
        row["raw_structure_sha256"]
        == hashlib.sha256(row["raw_structure"].encode()).hexdigest()
        for row in rows
    )
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    implementation = json.loads(IMPLEMENTATION_CONTRACT.read_text(encoding="utf-8"))
    assert sorted(manifest) == implementation["artifact_schemas"][
        "shadow_input_manifest"
    ]["top_level_fields"]
    assert manifest["target_columns"] == 0
    assert manifest["provenance_columns"] == 0
    assert manifest["public_test_rows"] == 0
    assert manifest["population"]["task_rows"] == {task: 10 for task in TASKS}
    assert manifest["population"]["unique_raw_structures"] == 6
    assert manifest["population"]["unique_standardized_hash_raw_pairs"] == 6
    spaced = next(row for row in rows if row["raw_structure"] == " CCO ")
    assert spaced["raw_structure_sha256"] == hashlib.sha256(b" CCO ").hexdigest()
    assert all(
        not value["path"].startswith(str(tmp_path))
        for value in manifest["inputs"].values()
    )

    with pytest.raises(ShadowContractError, match="already exists"):
        _prepare(fixture, tmp_path / "input-one")

    fixture.canonical_molecules.write_text(
        fixture.canonical_molecules.read_text(encoding="utf-8") + "tamper\n",
        encoding="utf-8",
    )
    with pytest.raises(ShadowContractError, match="canonical_molecules hash mismatch"):
        _prepare(fixture, tmp_path / "tampered")


def test_shadow_assignment_is_global_deterministic_and_label_free(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "fixture")
    _prepare(fixture, tmp_path / "input")
    first = _assign(fixture, tmp_path / "input", tmp_path / "assignment-one")
    second = _assign(fixture, tmp_path / "input", tmp_path / "assignment-two")

    assert first.rows_path.read_bytes() == second.rows_path.read_bytes()
    assert first.scaffold_group_count == 5
    assert first.community_group_count == 5
    rows = _read_csv(first.rows_path)
    assert tuple(rows[0]) == SHADOW_COLUMNS
    by_structure: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_structure.setdefault(row["standardized_structure_hash"], []).append(row)
    for structure_rows in by_structure.values():
        for protocol in ("scaffold", "community"):
            assert len({row[f"{protocol}_group_hash"] for row in structure_rows}) == 1
            for repeat in range(3):
                outer = {
                    row[f"{protocol}_repeat_{repeat}_outer_fold"]
                    for row in structure_rows
                }
                inner = {
                    row[f"{protocol}_repeat_{repeat}_inner_fold"]
                    for row in structure_rows
                }
                assert len(outer) == len(inner) == 1
                outer_value = next(iter(outer))
                assert next(iter(inner)) == (
                    "" if outer_value == "0" else str(int(outer_value) - 1)
                )
    for protocol in ("scaffold", "community"):
        for repeat in range(3):
            assert {
                row[f"{protocol}_repeat_{repeat}_outer_fold"] for row in rows
            } == {"0", "1", "2", "3", "4"}
    receipt = json.loads(first.receipt_path.read_text(encoding="utf-8"))
    implementation = json.loads(IMPLEMENTATION_CONTRACT.read_text(encoding="utf-8"))
    assert sorted(receipt) == implementation["artifact_schemas"][
        "shadow_assignment_receipt"
    ]["top_level_fields"]
    assert receipt["accounting"] == {
        "feature_matrices_generated": 0,
        "metric_evaluations": 0,
        "model_fits": 0,
        "predictions": 0,
        "public_test_labels_parsed": 0,
        "public_test_rows_emitted": 0,
        "target_values_used_for_assignment": 0,
    }
    assert receipt["community_distance_count"] == 10
    assert receipt["community_distance_dtype"] == "numpy.float64"

    expected_fallback = hashlib.sha256(
        b"acyclic_exact_structure:CCO"
    ).hexdigest()
    expected_scaffold = hashlib.sha256(
        b"bemis_murcko_scaffold:c1ccccc1"
    ).hexdigest()
    acyclic = next(row for row in rows if row["standardized_structure"] == "CCO")
    benzene = next(
        row for row in rows if row["standardized_structure"] == "c1ccccc1"
    )
    assert acyclic["scaffold_group_hash"] == expected_fallback
    assert benzene["scaffold_group_hash"] == expected_scaffold
    first_task_rows = [row for row in rows if row["task"] == TASKS[0]]
    assert [int(row["source_row"]) for row in first_task_rows] == list(range(2, 12))
    assert b",0,," in first.rows_path.read_bytes()

    tampered_rows = _read_csv(tmp_path / "input" / "shadow_input_rows.csv")
    tampered_path = tmp_path / "input-with-target.csv"
    _write_csv(
        tampered_path,
        (*INPUT_COLUMNS, "target"),
        [{**row, "target": "1"} for row in tampered_rows],
    )
    tampered_manifest = json.loads(
        (tmp_path / "input" / "shadow_input_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    tampered_manifest["output"]["sha256"] = _hash(tampered_path)
    tampered_manifest_path = tmp_path / "input-with-target-manifest.json"
    _write_json(tampered_manifest_path, tampered_manifest)
    with pytest.raises(ShadowContractError, match="unexpected CSV columns"):
        assign_shadow_rows(
            fixture.contract,
            fixture.implementation_contract,
            tampered_path,
            tampered_manifest_path,
            LOCK_PATH,
            tmp_path / "forbidden-target-assignment",
            source_revision=REVISION,
        )


def test_shadow_mechanics_freeze_distance_order_chirality_and_folds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path / "fixture")
    contract = json.loads(fixture.contract.read_text(encoding="utf-8"))
    contract["protocols"]["community"]["pair_distances"] = 3
    ordered = ("a", "b", "c")
    molecules = {
        "a": Chem.MolFromSmiles("C"),
        "b": Chem.MolFromSmiles("N"),
        "c": Chem.MolFromSmiles("O"),
    }
    assert all(molecule is not None for molecule in molecules.values())
    chirality: dict[str, bool] = {}
    captured: dict[str, Any] = {}
    real_generator = shadow.rdFingerprintGenerator.GetMorganGenerator

    def generator(**kwargs: Any) -> Any:
        chirality["value"] = bool(kwargs["includeChirality"])
        return real_generator(**kwargs)

    similarities = iter(([0.6], [0.2, 0.7]))

    def bulk(*_args: Any, **_kwargs: Any) -> list[float]:
        return list(next(similarities))

    def cluster(
        distances: Any,
        count: int,
        cutoff: float,
        *,
        isDistData: bool,
        reordering: bool,
    ) -> tuple[tuple[int, ...], ...]:
        captured.update(
            {
                "distances": distances.tolist(),
                "count": count,
                "cutoff": cutoff,
                "is_dist": isDistData,
                "reordering": reordering,
            }
        )
        assert distances[0] <= cutoff
        return ((0, 1), (2,))

    monkeypatch.setattr(shadow.rdFingerprintGenerator, "GetMorganGenerator", generator)
    monkeypatch.setattr(shadow.DataStructs, "BulkTanimotoSimilarity", bulk)
    monkeypatch.setattr(shadow.Butina, "ClusterData", cluster)
    communities, count = shadow._communities(contract, ordered, molecules)

    assert count == 3
    assert chirality == {"value": True}
    assert captured == {
        "distances": pytest.approx([0.4, 0.8, 0.3]),
        "count": 3,
        "cutoff": 0.4,
        "is_dist": True,
        "reordering": True,
    }
    assert communities["a"] == communities["b"]
    assert communities["a"] != communities["c"]
    fold_result = shadow._folds(
        {
            "a" * 64: 5,
            "b" * 64: 4,
            "c" * 64: 3,
            "d" * 64: 2,
            "e" * 64: 1,
            "f" * 64: 1,
        },
        20260810,
        "scaffold",
    )
    assert {group[0]: fold for group, fold in fold_result.items()} == {
        "a": 3,
        "b": 4,
        "c": 1,
        "d": 2,
        "e": 0,
        "f": 0,
    }


def test_projection_rejects_noncanonical_rows_headers_and_identity_sets(
    tmp_path: Path,
) -> None:
    short_revision = _fixture(tmp_path / "short-revision")
    with pytest.raises(ShadowContractError, match="full lowercase Git SHA"):
        prepare_shadow_input(
            short_revision.contract,
            short_revision.implementation_contract,
            short_revision.adapter_manifest,
            short_revision.official_split,
            short_revision.canonical_molecules,
            short_revision.canonical_audit,
            tmp_path / "short-output",
            source_revision="abc",
        )

    noncanonical = _fixture(tmp_path / "noncanonical")
    split_rows = _read_csv(noncanonical.official_split)
    split_rows[0]["source_row"] = "02"
    _write_csv(
        noncanonical.official_split,
        ("molecule_id", "task", "partition", "source_row"),
        split_rows,
    )
    contract = json.loads(noncanonical.contract.read_text(encoding="utf-8"))
    contract["source_contracts"]["trusted_input_projection_sources"][
        "official_split"
    ]["sha256"] = _hash(noncanonical.official_split)
    _write_json(noncanonical.contract, contract)
    _rebind_implementation_parent(noncanonical)
    with pytest.raises(ShadowContractError, match="canonical positive decimal"):
        _prepare(noncanonical, tmp_path / "noncanonical-output")

    missing = _fixture(tmp_path / "missing")
    canonical_rows = _read_csv(missing.canonical_molecules)
    _write_csv(
        missing.canonical_molecules,
        tuple(canonical_rows[0]),
        canonical_rows[:-1],
    )
    contract = json.loads(missing.contract.read_text(encoding="utf-8"))
    contract["source_contracts"]["trusted_input_projection_sources"][
        "canonical_molecules"
    ]["sha256"] = _hash(missing.canonical_molecules)
    _write_json(missing.contract, contract)
    _rebind_implementation_parent(missing)
    with pytest.raises(ShadowContractError, match="identity sets differ"):
        _prepare(missing, tmp_path / "missing-output")

    reordered = _fixture(tmp_path / "reordered")
    canonical_rows = _read_csv(reordered.canonical_molecules)
    columns = tuple(canonical_rows[0])
    reordered_columns = (columns[1], columns[0], *columns[2:])
    _write_csv(reordered.canonical_molecules, reordered_columns, canonical_rows)
    contract = json.loads(reordered.contract.read_text(encoding="utf-8"))
    contract["source_contracts"]["trusted_input_projection_sources"][
        "canonical_molecules"
    ]["sha256"] = _hash(reordered.canonical_molecules)
    _write_json(reordered.contract, contract)
    _rebind_implementation_parent(reordered)
    with pytest.raises(ShadowContractError, match="unexpected CSV columns"):
        _prepare(reordered, tmp_path / "reordered-output")


def test_shadow_summary_validates_support_and_preserves_duplicate_rows(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "fixture")
    _prepare(fixture, tmp_path / "input")
    assignment = _assign(fixture, tmp_path / "input", tmp_path / "assignment")
    result = summarize_shadow_rows(
        fixture.contract,
        fixture.implementation_contract,
        assignment.rows_path,
        assignment.receipt_path,
        fixture.measurements,
        fixture.measurement_manifest,
        source_revision=REVISION,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    implementation = json.loads(IMPLEMENTATION_CONTRACT.read_text(encoding="utf-8"))
    assert sorted(manifest) == implementation["artifact_schemas"][
        "shadow_manifest"
    ]["top_level_fields"]
    assert result.row_count == result.label_count == 30
    assert manifest["accounting"] == {
        "feature_matrices_generated": 0,
        "metric_evaluations": 0,
        "model_fits": 0,
        "predictions": 0,
        "public_test_labels_parsed": 0,
        "train_val_labels_parsed": 30,
    }
    assert manifest["duplicate_and_conflicting_labels"] == {
        "duplicate_excess_source_rows": 15,
        "structure_task_cells": 15,
        "structure_task_cells_with_conflicting_labels": 15,
        "structure_task_cells_with_duplicate_rows": 15,
        "unique_structures_in_conflicting_label_cells": 5,
    }
    for task in TASKS:
        for protocol in ("scaffold", "community"):
            for repeat in range(3):
                summary = manifest["validation"][task][protocol][str(repeat)]
                assert summary["outer_folds"][0]["positive"] == 1
                assert summary["outer_folds"][0]["negative"] == 1
                assert all(item["positive"] == 1 for item in summary["inner_folds"])
                assert all(item["negative"] == 1 for item in summary["inner_folds"])
    with pytest.raises(ShadowContractError, match="refusing to overwrite"):
        summarize_shadow_rows(
            fixture.contract,
            fixture.implementation_contract,
            assignment.rows_path,
            assignment.receipt_path,
            fixture.measurements,
            fixture.measurement_manifest,
            source_revision=REVISION,
        )


def test_summary_rejects_unknown_identity_before_parsing_target_and_no_repair(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "fixture")
    _prepare(fixture, tmp_path / "input")
    assignment = _assign(fixture, tmp_path / "input", tmp_path / "assignment")
    original_contract = json.loads(fixture.contract.read_text(encoding="utf-8"))
    original_rows = _read_csv(fixture.measurements)

    def rebind(
        rows: list[dict[str, str]], name: str
    ) -> tuple[Path, Path, Path, Path]:
        measurements = tmp_path / f"{name}-measurements.csv"
        parent = tmp_path / f"{name}-parent.json"
        contract_path = tmp_path / f"{name}-contract.json"
        implementation_path = tmp_path / f"{name}-implementation.json"
        _write_csv(measurements, ("molecule_id", "value"), rows)
        _write_json(parent, {"outputs": {"tdc/measurements.csv": _hash(measurements)}})
        contract = copy.deepcopy(original_contract)
        source = contract["source_contracts"][
            "train_val_measurements_for_post_assignment_summary_only"
        ]
        source["sha256"] = _hash(measurements)
        source["parent_manifest"]["sha256"] = _hash(parent)
        _write_json(contract_path, contract)
        implementation = json.loads(
            fixture.implementation_contract.read_text(encoding="utf-8")
        )
        implementation["parent_contract"]["sha256"] = _hash(contract_path)
        _write_json(implementation_path, implementation)
        receipt = json.loads(assignment.receipt_path.read_text(encoding="utf-8"))
        receipt["contract"]["sha256"] = _hash(contract_path)
        receipt["implementation_contract"]["sha256"] = _hash(implementation_path)
        _write_json(assignment.receipt_path, receipt)
        return contract_path, implementation_path, measurements, parent

    unknown_rows = copy.deepcopy(original_rows)
    unknown_rows[-1] = {"molecule_id": "unknown:test:identity", "value": "invalid"}
    contract_path, implementation_path, measurements, parent = rebind(
        unknown_rows, "unknown"
    )
    with pytest.raises(ShadowContractError, match="identity absent"):
        summarize_shadow_rows(
            contract_path,
            implementation_path,
            assignment.rows_path,
            assignment.receipt_path,
            measurements,
            parent,
            source_revision=REVISION,
        )
    assert not (assignment.rows_path.parent / "shadow_manifest.json").exists()

    zero_rows = [
        {"molecule_id": row["molecule_id"], "value": "0.0"} for row in original_rows
    ]
    contract_path, implementation_path, measurements, parent = rebind(
        zero_rows, "degenerate"
    )
    with pytest.raises(ShadowContractError, match="degenerate class support"):
        summarize_shadow_rows(
            contract_path,
            implementation_path,
            assignment.rows_path,
            assignment.receipt_path,
            measurements,
            parent,
            source_revision=REVISION,
        )
    assert not (assignment.rows_path.parent / "shadow_manifest.json").exists()
