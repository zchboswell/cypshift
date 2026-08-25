from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
ACCEPTANCE_PATH = BENCHMARK / "global_v2_g3_synthetic_acceptance.json"
CONTRACT_PATH = BENCHMARK / "global_v2_g3_synthetic_contract.json"
PARENT_PATH = BENCHMARK / "global_v2_g3_single_expert_contract.json"
RESEARCH = ROOT / "research" / "lightgbm-global"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_acceptance_binds_exact_contract_implementation_and_runtime() -> None:
    receipt = _load(ACCEPTANCE_PATH)
    assert receipt["status"] == "G2_6S_G3_SYNTHETIC_ACCEPTED"
    assert receipt["attempt_id"] == "EXP-G3-SYNTHETIC-ATTEMPT-1"
    assert receipt["implementation_commit"] == (
        "bde26d0f81af420d8efaeeb436bfc10d18f84fbd"
    )
    assert receipt["contract_sha256"] == _sha256(CONTRACT_PATH)
    assert receipt["parent_contract_sha256"] == _sha256(PARENT_PATH)
    bindings = receipt["source_bindings"]
    assert bindings == {
        "focused_test_sha256": _sha256(
            ROOT / "tests" / "test_openadmet_global_v2_g3_synthetic_implementation.py"
        ),
        "g3_runner_sha256": _sha256(RESEARCH / "g3_runner.py"),
        "g3_single_expert_contract_sha256": _sha256(PARENT_PATH),
        "g3_synthetic_contract_sha256": _sha256(CONTRACT_PATH),
        "g3_synthetic_driver_sha256": _sha256(RESEARCH / "run_g3_synthetic.py"),
        "research_pyproject_sha256": _sha256(RESEARCH / "pyproject.toml"),
        "research_python_pin_sha256": _sha256(RESEARCH / ".python-version"),
        "research_uv_lock_sha256": _sha256(RESEARCH / "uv.lock"),
    }
    environment = receipt["environment"]
    assert environment["python"] == "3.12.3"
    assert environment["lightgbm"] == "4.7.0"
    assert environment["network_isolated"] is True


def test_two_smokes_and_both_formal_roots_are_complete_and_deterministic() -> None:
    receipt = _load(ACCEPTANCE_PATH)
    smokes = receipt["bounded_api_smokes"]
    assert smokes["completed"] == 2
    assert smokes["maximum_rows"] == 64
    assert smokes["num_boost_round"] == 16
    assert smokes["num_threads"] == 1
    assert smokes["finite_predictions"] == 32
    assert smokes["resource_timing_authority"] is False
    assert smokes["model_quality_authority"] is False
    mechanics = receipt["mechanics"]
    assert mechanics == {
        "roots_completed": 2,
        "opposite_physical_order": True,
        "cross_root_byte_identical": True,
        "deterministic_terminal_files": 7,
        "deterministic_tree_sha256": (
            "5e4edc473e85d7ae909a415810cb3dae2b4c9599b00813da6d3f4a73ba3df8e8"
        ),
        "model_double_fits": 120,
        "model_double_outer_predictions": 1920,
        "real_lightgbm_fits": 8,
        "real_lightgbm_predictions": 6304,
        "resolved_parameter_hashes": 1,
        "component_crossings": 0,
        "confirmatory_truth_values_parsed": 0,
        "warnings": 0,
        "fallbacks": 0,
        "nonzero_exits": 0,
    }
    assert len(receipt["deterministic_terminal_receipts"]) == 7
    assert all(
        len(value) == 64
        for value in receipt["deterministic_terminal_receipts"].values()
    )


def test_every_conservative_resource_gate_passes_with_large_margin() -> None:
    projection = _load(ACCEPTANCE_PATH)["resource_projection"]
    assert projection["accepted"] is True
    assert all(projection["gates"].values())
    assert projection["projected_cpu_core_hours"] == 1.1709157071152776
    assert (
        projection["projected_cpu_core_hours"]
        < projection["maximum_projected_cpu_core_hours"]
    )
    assert projection["projected_wall_hours"] == 0.07931188166511371
    assert (
        projection["projected_wall_hours"] < projection["maximum_projected_wall_hours"]
    )
    assert projection["restricted_storage_gb"] == 6.612240404
    assert (
        projection["restricted_storage_gb"]
        < projection["maximum_restricted_storage_gb"]
    )
    assert projection["peak_rss_gib"] == 0.3101158142089844
    assert projection["peak_rss_gib"] < projection["maximum_peak_rss_gib"]
    assert projection["gpu_hours"] == projection["maximum_gpu_hours"] == 0


def test_cleanup_is_complete_and_receipt_opens_no_scientific_authority() -> None:
    receipt = _load(ACCEPTANCE_PATH)
    assert all(receipt["cleanup"].values())
    accounting = receipt["accounting"]
    assert accounting["runtime_environments_created"] == 1
    assert accounting["bounded_api_smokes"] == 2
    assert accounting["formal_synthetic_roots"] == 2
    assert accounting["synthetic_model_double_fits"] == 120
    assert accounting["synthetic_real_lightgbm_fits"] == 8
    assert accounting["synthetic_predictions"] == 8224
    for name, value in accounting.items():
        if name not in {
            "runtime_environments_created",
            "bounded_api_smokes",
            "formal_synthetic_roots",
            "synthetic_model_double_fits",
            "synthetic_real_lightgbm_fits",
            "synthetic_predictions",
        }:
            assert value == 0
    assert (
        "No value in this receipt measures or predicts EXP-G3 model quality"
        in receipt["scientific_interpretation"]
    )
    assert (
        "separately reviewed single-use official development execution contract"
        in receipt["decision"]
    )
