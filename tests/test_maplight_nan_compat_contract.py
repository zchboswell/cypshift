from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmarks/maplight_fixed_nan_compat_contract.json"
DIAGNOSIS_PATH = ROOT / "benchmarks/receipts/maplight_fixed_nan_diagnosis.json"
RUNNER_PATH = ROOT / "research/maplight-fixed/run_nan_compat.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_nan_contract_binds_prior_evidence_without_replacing_it() -> None:
    contract = _json(CONTRACT_PATH)

    assert contract["schema_version"] == (
        "cypshift.maplight_fixed_nan_compat_contract.v1"
    )
    assert contract["status"] == "pre_result_frozen"
    assert contract["authorization"]["preserves_prior_experiments_and_blockers"]

    for name, record in contract["parents"].items():
        path = ROOT / record["path"]
        if name in {"int8_compat_contract", "nan_diagnosis"}:
            assert path.is_file()
        if path.exists():
            assert _sha256(path) == record["sha256"]

    assert contract["parents"]["nan_diagnosis"]["sha256"] == _sha256(DIAGNOSIS_PATH)
    assert set(contract["inheritance"]["overrides"]) == {
        "/unchanged_rules/nonfinite_policy",
        "/acceptance/1",
        "/stopping_rules/0",
        "/stopping_rules/2",
    }


def test_nan_contract_allows_only_four_charge_descriptor_columns() -> None:
    contract = _json(CONTRACT_PATH)
    change = contract["sole_scientific_change"]

    assert change["block"] == "rdkit_descriptors"
    assert change["allowed_nonfinite_kind"] == "NaN"
    assert change["allowed_columns"] == [
        {"index": 39, "name": "MaxAbsPartialCharge"},
        {"index": 41, "name": "MaxPartialCharge"},
        {"index": 43, "name": "MinAbsPartialCharge"},
        {"index": 45, "name": "MinPartialCharge"},
    ]
    assert change["expected_label_free_diagnostic"] == {
        "unique_exact_raw_structures_with_allowed_nan": 41,
        "expanded_rows_with_allowed_nan": 82,
        "unique_nan_cells": 164,
        "expanded_nan_cells": 328,
        "first_unique_exact_raw_index": 1563,
        "first_raw_structure_sha256": (
            "6911fe92c06813b83b17a3d974db2dce21df47361283acf185d91d5468a7966a"
        ),
    }
    assert contract["consumer_rule"]["learner"] == "CatBoostClassifier 1.2.1"
    assert contract["execution"]["build_ids"] == [1, 2]
    assert len(set(contract["execution"]["output_roots"])) == 2
    assert len(set(contract["execution"]["failure_roots"])) == 2
    assert contract["accounting_before_execution"] and all(
        type(value) is int and value == 0
        for value in contract["accounting_before_execution"].values()
    )


def test_nan_diagnosis_arithmetic_and_claim_boundary_are_exact() -> None:
    diagnosis = _json(DIAGNOSIS_PATH)
    evidence = diagnosis["nonfinite_descriptor_policy_evidence"]

    assert evidence["unique_exact_raw_structures_affected"] == 41
    assert sum(evidence["rare_element_counts"].values()) == 41
    assert sum(evidence["affected_rows_by_task"].values()) == 82
    assert evidence["unique_nonfinite_cells"] == 41 * 4
    assert evidence["expanded_nonfinite_cells"] == 82 * 4
    assert evidence["infinities_observed"] == 0
    assert evidence["other_frozen_rdkit_descriptors_with_nonfinite_values"] == 0

    assert diagnosis["consumer_probes"]["catboost"] == {
        "synthetic_rows": 6,
        "fits_attempted": 1,
        "fits_completed": 1,
        "nan_input_accepted": True,
        "predictions_finite": True,
        "resolved_nan_mode": "Min",
    }
    accounting = diagnosis["accounting"]
    for name in (
        "target_values_parsed",
        "public_test_rows_used",
        "public_test_labels_parsed",
        "scientific_model_fits",
        "scientific_predictions",
        "metric_evaluations",
        "public_test_family_task_slots_consumed",
    ):
        assert type(accounting[name]) is int and accounting[name] == 0


def test_nan_runner_is_one_direct_label_free_overlay() -> None:
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(functions) >= {
        "build_nan_compat_features",
        "_verify_frozen_parity",
        "_nonfinite_record",
        "_catboost_probe",
        "_validate_build",
    }
    assert [
        argument.arg for argument in functions["build_nan_compat_features"].args.args
    ] == ["build_id"]
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any("measurements.csv" in value for value in literals)
    assert not any("http://" in value or "https://" in value for value in literals)


def test_nan_runner_array_gate_allows_only_exact_columns_and_no_infinity(
    tmp_path: Path,
) -> None:
    research_root = str(RUNNER_PATH.parent)
    sys.path.insert(0, research_root)
    try:
        runner = _load_module("maplight_nan_runner_test", RUNNER_PATH)
    finally:
        sys.path.remove(research_root)

    descriptors = np.zeros((2, 200), dtype="<f8")
    descriptors[0, list(runner.ALLOWED_INDICES)] = np.nan
    path = tmp_path / "rdkit_descriptors.npy"
    runner.features.write_npy_v1(path, descriptors)
    record = runner._array_record(
        path,
        descriptors.shape,
        descriptors.dtype,
        allowed_nan_columns=runner.ALLOWED_INDICES,
    )
    assert record["nonfinite_count"] == 4

    outside = descriptors.copy()
    outside[0, 40] = np.nan
    outside_path = tmp_path / "outside.npy"
    runner.features.write_npy_v1(outside_path, outside)
    with pytest.raises(runner.base.CompatError):
        runner._array_record(
            outside_path,
            outside.shape,
            outside.dtype,
            allowed_nan_columns=runner.ALLOWED_INDICES,
        )

    infinity = descriptors.copy()
    infinity[0, 39] = np.inf
    infinity_path = tmp_path / "infinity.npy"
    runner.features.write_npy_v1(infinity_path, infinity)
    with pytest.raises(runner.base.CompatError):
        runner._array_record(
            infinity_path,
            infinity.shape,
            infinity.dtype,
            allowed_nan_columns=runner.ALLOWED_INDICES,
        )
