from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import cypshift.series_residual as series_residual
from cypshift.native_selection import NativeSelectionError
from cypshift.series_residual import run_series_residual

TASKS = (
    ("octant_cyp", "cyp3a4_active_preincubation_pIC50", "regression"),
    ("tdc_admet_group", "cyp2c9_veith", "classification"),
    ("tdc_admet_group", "cyp2d6_veith", "classification"),
    ("tdc_admet_group", "cyp3a4_veith", "classification"),
)


def _write_csv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _aggregate(outputs: dict[str, str]) -> str:
    material = "\n".join(f"{name}={outputs[name]}" for name in sorted(outputs))
    return hashlib.sha256(material.encode()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _fixture(
    root: Path, *, misalign_target: bool = False
) -> tuple[Path, Path, Path, str]:
    combination_root = root / "combinations"
    research_root = root / "research"
    combination_path = combination_root / "combination_oof_predictions.csv"
    research_path = research_root / "retained_oof_observations.csv"
    combination_rows: list[dict[str, str]] = []
    research_rows: list[dict[str, str]] = []
    for benchmark, task, problem_type in TASKS:
        for fold in range(4):
            specifications = (
                ("supported-a-positive", 1.0, 1.0, "supported-a"),
                ("supported-a-negative", 0.0, 0.75, "supported-a"),
                ("supported-b-positive", 1.0, 0.5, "supported-b"),
                ("supported-b-negative", 0.0, 0.75, "supported-b"),
                ("remote-positive", 1.0, 0.25, "remote"),
                ("remote-negative", 0.0, 0.25, "remote"),
            )
            for name, target, similarity, group in specifications:
                molecule_id = f"{task}-f{fold}-{name}"
                common = {
                    "benchmark": benchmark,
                    "task": task,
                    "problem_type": problem_type,
                    "molecule_id": molecule_id,
                    "inner_fold": str(fold),
                    "target": str(target),
                    "standardized_structure_hash": hashlib.sha256(
                        molecule_id.encode()
                    ).hexdigest(),
                }
                combination_rows.append(
                    {
                        **common,
                        "candidate": "unweighted_mean",
                        "prediction": "0.5",
                    }
                )
                research_rows.append(
                    {
                        **common,
                        "family": "similarity_knn",
                        "configuration_id": "tanimoto-k50-p2",
                        "prediction": str(target),
                        "nearest_neighbor_similarity": str(similarity),
                        "scaffold_group_hash": f"{task}-f{fold}-{group}",
                    }
                )
    if misalign_target:
        research_rows[0]["target"] = "0.25"
    _write_csv(
        combination_path,
        (
            "benchmark",
            "task",
            "problem_type",
            "molecule_id",
            "inner_fold",
            "candidate",
            "prediction",
            "target",
            "standardized_structure_hash",
        ),
        combination_rows,
    )
    _write_csv(
        research_path,
        (
            "benchmark",
            "task",
            "problem_type",
            "molecule_id",
            "inner_fold",
            "family",
            "configuration_id",
            "prediction",
            "nearest_neighbor_similarity",
            "scaffold_group_hash",
            "target",
            "standardized_structure_hash",
        ),
        research_rows,
    )
    combination_outputs = {combination_path.name: _file_hash(combination_path)}
    research_outputs = {research_path.name: _file_hash(research_path)}
    combination_manifest = {
        "schema_version": "cypshift.native_combinations.v3",
        "outputs": combination_outputs,
        "aggregate_sha256": _aggregate(combination_outputs),
    }
    research_manifest = {
        "schema_version": "cypshift.research_observations.v1",
        "outputs": research_outputs,
        "aggregate_sha256": _aggregate(research_outputs),
    }
    combination_manifest_path = combination_root / "combination_manifest.json"
    research_manifest_path = research_root / "research_observation_manifest.json"
    _write_json(combination_manifest_path, combination_manifest)
    _write_json(research_manifest_path, research_manifest)

    contract = json.loads(
        Path("benchmarks/series_residual_contract.json").read_text(encoding="utf-8")
    )
    contract["inputs"]["native_combinations"].update(
        {
            "manifest_sha256": _file_hash(combination_manifest_path),
            "aggregate_sha256": combination_manifest["aggregate_sha256"],
            "prediction_sha256": combination_outputs[combination_path.name],
        }
    )
    contract["inputs"]["research_observations"].update(
        {
            "manifest_sha256": _file_hash(research_manifest_path),
            "aggregate_sha256": research_manifest["aggregate_sha256"],
            "observation_sha256": research_outputs[research_path.name],
        }
    )
    contract["join_and_preflight"]["expected_base_rows"] = len(combination_rows)
    contract["join_and_preflight"]["expected_local_rows"] = len(research_rows)
    contract["topology_audit"].update(
        {
            "selection_rows": len(combination_rows),
            "rows_at_exact_threshold": {task: 4 for _, task, _ in TASKS},
            "task_counts": {
                task: {
                    "rows": 24,
                    "supported_rows": 16,
                    "supported_by_fold": [4, 4, 4, 4],
                    "all_scaffold_groups_by_fold": [3, 3, 3, 3],
                    "supported_scaffold_groups_by_fold": [2, 2, 2, 2],
                }
                for _, task, _ in TASKS
            },
        }
    )
    contract_path = root / "contract.json"
    _write_json(contract_path, contract)
    return combination_root, research_root, contract_path, _file_hash(contract_path)


def test_series_residual_is_byte_identical_and_abstains(tmp_path: Path) -> None:
    combinations, research, contract, contract_hash = _fixture(tmp_path / "inputs")
    first = tmp_path / "first"
    second = tmp_path / "second"
    result = run_series_residual(
        combinations,
        research,
        contract,
        first,
        source_revision="fixture-revision",
        expected_contract_sha256=contract_hash,
    )
    repeat = run_series_residual(
        combinations,
        research,
        contract,
        second,
        source_revision="fixture-revision",
        expected_contract_sha256=contract_hash,
    )

    assert result.rows == repeat.rows == 96
    assert result.retained == repeat.retained
    assert [path.name for path in sorted(first.iterdir())] == [
        path.name for path in sorted(second.iterdir())
    ]
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()

    predictions = _read_csv(first / "series_residual_predictions.csv")
    remote = [row for row in predictions if row["population"] == "remote_abstained"]
    threshold = [
        row for row in predictions if row["nearest_neighbor_similarity"] == "0.5"
    ]
    assert len(remote) == 32
    assert len(threshold) == 16
    assert all(row["valid_prediction"] == row["base_prediction"] for row in remote)
    assert all(row["weight"] == "0" for row in threshold)
    assert all(row["valid_prediction"] == row["base_prediction"] for row in threshold)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["point_metric_evaluations"] == 300
    assert manifest["bootstrap_metric_evaluations"] == 80000
    assert manifest["model_fits"] == 0
    assert manifest["heldout_labels_parsed"] == 0
    assert manifest["heldout_evaluations"] == 0


def test_series_residual_verifies_receipts_before_csv_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    combinations, research, contract, contract_hash = _fixture(tmp_path / "inputs")
    prediction_path = combinations / "combination_oof_predictions.csv"
    prediction_path.write_text(
        prediction_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8"
    )

    def fail_if_called(path: Path) -> list[dict[str, str]]:
        raise AssertionError(f"CSV parsed before receipt failure: {path}")

    monkeypatch.setattr(series_residual, "_read_csv", fail_if_called)
    with pytest.raises(NativeSelectionError, match="input output hash mismatch"):
        run_series_residual(
            combinations,
            research,
            contract,
            tmp_path / "out",
            source_revision="fixture-revision",
            expected_contract_sha256=contract_hash,
        )


def test_series_residual_rejects_join_mismatch(tmp_path: Path) -> None:
    combinations, research, contract, contract_hash = _fixture(
        tmp_path / "inputs", misalign_target=True
    )
    with pytest.raises(NativeSelectionError, match="base and local OOF fields differ"):
        run_series_residual(
            combinations,
            research,
            contract,
            tmp_path / "out",
            source_revision="fixture-revision",
            expected_contract_sha256=contract_hash,
        )


def test_series_residual_rejects_topology_mismatch(tmp_path: Path) -> None:
    combinations, research, contract, _ = _fixture(tmp_path / "inputs")
    value = json.loads(contract.read_text(encoding="utf-8"))
    value["topology_audit"]["task_counts"][TASKS[0][1]]["supported_rows"] = 15
    _write_json(contract, value)
    with pytest.raises(NativeSelectionError, match="topology mismatch"):
        run_series_residual(
            combinations,
            research,
            contract,
            tmp_path / "out",
            source_revision="fixture-revision",
            expected_contract_sha256=_file_hash(contract),
        )


def test_series_residual_rejects_contract_hash_mismatch(tmp_path: Path) -> None:
    combinations, research, contract, _ = _fixture(tmp_path / "inputs")
    with pytest.raises(NativeSelectionError, match="contract hash mismatch"):
        run_series_residual(
            combinations,
            research,
            contract,
            tmp_path / "out",
            source_revision="fixture-revision",
            expected_contract_sha256="0" * 64,
        )


def test_series_residual_refuses_existing_output(tmp_path: Path) -> None:
    combinations, research, contract, contract_hash = _fixture(tmp_path / "inputs")
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(NativeSelectionError, match="output path already exists"):
        run_series_residual(
            combinations,
            research,
            contract,
            output,
            source_revision="fixture-revision",
            expected_contract_sha256=contract_hash,
        )
