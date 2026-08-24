from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_g1_resource_feasibility_contract.json"
CONTRACT_SHA256 = "173273102393794ec345782ad8298d66d675a91d3569301ea3fd3e0297b24a92"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_resource_contract_has_exact_identity_and_parents() -> None:
    contract = _load(CONTRACT_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_g1_resource_feasibility_contract.v1"
    )
    assert contract["gate"] == "G2_3D_EXP_G1_RESOURCE_FEASIBILITY_CONTRACT_FROZEN"
    assert contract["base_commit"] == ("cefc7ddc47c6ecf269f629cc6ccf50782c92e9b5")
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_resource_contract_binds_the_accepted_implementation() -> None:
    contract = _load(CONTRACT_PATH)
    implementation = contract["accepted_implementation"]
    for prefix in (
        "compiler",
        "wrapper",
        "synthetic_driver",
        "focused_tests",
        "research_lock",
    ):
        assert (
            _sha256(ROOT / implementation[f"{prefix}_path"])
            == implementation[f"{prefix}_sha256"]
        )


def test_exactly_one_implementation_equivalent_optimization_is_frozen() -> None:
    optimization = _load(CONTRACT_PATH)["single_optimization"]
    assert optimization["optimization_id"] == "FOLD_LOCAL_QUANTIZED_POOL_REUSE_V1"
    assert "fresh CatBoostRegressor" in optimization["constructor_rule"]
    assert "thread_count=16" in optimization["constructor_rule"]
    assert len(optimization["allowed_source_changes_after_integration"]) == 4
    assert any(
        "second optimization" in item for item in optimization["forbidden_alternatives"]
    )


def test_synthetic_falsifier_is_paired_exact_and_fail_fast() -> None:
    contract = _load(CONTRACT_PATH)
    falsifier = contract["synthetic_falsifier"]
    equivalence = contract["equivalence_acceptance"]
    assert falsifier["roots"] == 2
    assert falsifier["probe_identities_per_mode_per_root"] == 14
    assert falsifier["maximum_real_catboost_fits_per_root"] == 28
    assert falsifier["maximum_real_catboost_fits_total"] == 56
    assert falsifier["modes_per_root"] == [
        "accepted_raw_array_reference",
        "fold_local_quantized_pool_reuse",
    ]
    assert "Stop immediately" in falsifier["fail_fast"]
    assert equivalence["prediction_float64_bytes_exact"]
    assert equivalence["prediction_tolerance"] == 0.0
    assert equivalence["all_members_conjunctive"]


def test_resource_projection_uses_worst_root_and_twenty_percent_margin() -> None:
    resources = _load(CONTRACT_PATH)["resource_measurement"]
    assert resources["official_ceiling_wall_hours"] == 120
    assert resources["official_ceiling_cpu_core_hours"] == 1200
    assert resources["required_margin_fraction"] == 0.2
    assert resources["maximum_projected_wall_hours"] == 96
    assert resources["maximum_projected_cpu_core_hours"] == 960
    assert resources["maximum_concurrent_catboost_fits"] == 1
    assert resources["thread_count_per_fit"] == 16
    assert resources["gpu_hours"] == 0
    assert "worse projected root" in resources["projection"]
    assert "do not average roots" in resources["projection"]


def test_decision_is_conjunctive_and_rejection_consumes_no_claim() -> None:
    decision = _load(CONTRACT_PATH)["decision_rule"]
    assert decision["pass_status"] == "G2_3D_EXP_G1_RESOURCE_FEASIBLE"
    assert decision["reject_status"] == "G2_3D_EXP_G1_RESOURCE_INFEASIBLE"
    assert "every exact-equivalence member" in decision["logic"]
    assert "96 wall-hours" in decision["logic"]
    assert "960 CPU-core-hours" in decision["logic"]
    assert "leave the claim permanently unconsumed" in decision["reject_action"]
    assert "without another G1 optimization" in decision["reject_action"]


def test_contract_freeze_has_zero_operations_and_no_execution_authority() -> None:
    contract = _load(CONTRACT_PATH)
    assert all(
        value == 0 for value in contract["current_milestone_accounting"].values()
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert not any(
        value
        for name, value in authority.items()
        if name != "contract_and_static_tests"
    )
    assert contract["next_gate"].startswith(
        "Review and integrate this exact contract with green post-main CI"
    )
    assert "Do not consume the G2-3C claim" in contract["next_gate"]
