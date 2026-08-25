from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = BENCHMARK / "global_v2_g3_single_expert_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g3_contract_binds_terminal_global_v2_evidence() -> None:
    contract = _read(CONTRACT)
    assert contract["status"] == "G2_6R_EXP_G3_CONTRACT_FROZEN"
    assert contract["experiment_id"] == "EXP-G3"
    assert contract["base_commit"] == "5af1cb7fa9a35a36d6076603ddd1244c7f78ab6e"
    assert list(contract["parents"]) == [
        "global_v2_contract",
        "fixed_maplight_reproduction",
        "g1_resource_rejection",
        "m1_resource_rejection",
        "x1_acquisition_failure",
        "t2_not_activated",
    ]
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_g3_is_one_fixed_representation_diverse_expert() -> None:
    contract = _read(CONTRACT)
    features = contract["feature_contract"]
    assert features["morgan_count"] == {
        "generator": "rdkit.Chem.rdFingerprintGenerator.GetMorganGenerator",
        "radius": 2,
        "columns": 2048,
        "use_counts": True,
        "include_chirality": True,
        "use_bond_types": True,
        "count_simulation": False,
        "include_redundant_environments": False,
        "order": "bit index 0 through 2047",
        "storage_dtype": "int32",
    }
    assert features["rdkit_descriptors"]["columns"] == 200
    assert features["matrix"]["total_columns"] == 2248
    assert features["matrix"]["preprocessing"].startswith("None.")
    assert "Avalon" in features["forbidden"]
    assert "external" in features["forbidden"]

    boundary = contract["occam_boundary"]
    for required in (
        "one learner",
        "one fixed 2,248-column representation",
        "one seed",
        "no grid",
        "no inner selection",
        "no fitted stack",
        "no fixed blend",
    ):
        assert required in boundary


def test_g3_lightgbm_runtime_and_parameters_are_exact() -> None:
    contract = _read(CONTRACT)
    runtime = contract["runtime_contract"]
    assert runtime["python"] == "3.12.3"
    assert runtime["lightgbm"] == "4.7.0"
    assert runtime["lightgbm_manylinux_wheel_sha256"] == (
        "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7"
    )
    assert runtime["future_isolated_uv_lock_sha256"] is None

    model = contract["model_contract"]
    assert model["api"] == (
        "lightgbm.train with one Dataset per fit and explicit parameter names"
    )
    assert model["num_boost_round"] == 1500
    parameters = model["parameters"]
    assert parameters == {
        "boosting": "gbdt",
        "objective": "regression_l1",
        "metric": "l1",
        "learning_rate": 0.03,
        "num_leaves": 31,
        "max_depth": -1,
        "min_data_in_leaf": 20,
        "min_sum_hessian_in_leaf": 0.001,
        "min_gain_to_split": 0.0,
        "max_bin": 255,
        "feature_pre_filter": False,
        "feature_fraction": 1.0,
        "feature_fraction_bynode": 1.0,
        "bagging_fraction": 1.0,
        "bagging_freq": 0,
        "lambda_l1": 0.0,
        "lambda_l2": 10.0,
        "use_missing": True,
        "zero_as_missing": False,
        "deterministic": True,
        "force_col_wise": True,
        "seed": 20260825,
        "data_random_seed": 20260825,
        "feature_fraction_seed": 20260825,
        "bagging_seed": 20260825,
        "drop_seed": 20260825,
        "extra_seed": 20260825,
        "num_threads": 16,
        "verbosity": -1,
    }
    assert parameters["bagging_fraction"] == 1.0
    assert parameters["bagging_freq"] == 0
    assert parameters["feature_fraction"] == 1.0
    assert parameters["deterministic"] is True
    assert parameters["force_col_wise"] is True


def test_g3_fit_budget_has_no_selection_or_baseline_refit() -> None:
    contract = _read(CONTRACT)
    splits = contract["population_and_splits"]
    budget = contract["fit_and_prediction_budget"]
    assert splits["repeats"] == 3
    assert splits["outer_folds"] == 5
    assert len(splits["endpoints"]) == 4
    assert budget["outer_contexts"] == 15
    assert budget["endpoints_per_outer_context"] == 4
    assert budget["exact_new_lightgbm_fits"] == 60
    assert budget["inner_selection_fits"] == 0
    assert budget["baseline_refits"] == 0
    assert budget["expected_outer_prediction_rows"] == 3 * 3908 * 4


def test_g3_promotion_is_conjunctive_and_targets_weak_endpoints() -> None:
    contract = _read(CONTRACT)
    acceptance = contract["development_evaluation"]["acceptance"]
    assert acceptance["minimum_relative_primary_improvement"] == 0.03
    assert acceptance["minimum_absolute_component_mae_improvement"] == 0.015
    assert acceptance["paired_component_mae_upper_95_below_zero"] is True
    assert acceptance["minimum_favorable_outer_cells"] == 8
    assert acceptance["total_outer_cells"] == 15
    assert acceptance["maximum_endpoint_mae_degradation"] == 0.015
    assert acceptance["minimum_improved_targeted_endpoints"] == 1
    assert acceptance["targeted_endpoints"] == ["CYP1A2", "CYP2D6"]
    assert acceptance["minimum_targeted_endpoint_component_mae_improvement"] == 0.01
    assert "Every member is conjunctive" in acceptance["logic"]


def test_g3_requires_synthetic_resource_gate_before_claim() -> None:
    contract = _read(CONTRACT)
    ceiling = contract["resource_ceiling"]
    gate = contract["resource_feasibility_gate"]
    assert gate["required_before_claim"] is True
    assert gate["maximum_projected_cpu_core_hours"] == pytest.approx(
        0.8 * ceiling["cpu_core_hours"]
    )
    assert gate["maximum_projected_wall_hours"] == pytest.approx(
        0.8 * ceiling["maximum_wall_hours"]
    )
    assert gate["maximum_projected_restricted_storage_gb"] == pytest.approx(
        0.8 * ceiling["restricted_storage_gb"]
    )
    assert gate["maximum_peak_rss_gib"] == pytest.approx(
        0.8 * ceiling["maximum_peak_rss_gib"]
    )
    assert ceiling["gpu_hours"] == 0
    assert gate["maximum_projected_gpu_hours"] == 0


def test_g3_contract_opens_no_execution_or_submission_capability() -> None:
    contract = _read(CONTRACT)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert all(value == 0 for key, value in accounting.items() if key != "contracts_created")

    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert all(value is False for key, value in authority.items() if key != "contract_and_static_tests")

    terminal = contract["terminal_contract"]
    for prohibited in (
        "confirmatory truth",
        "historical R5D row",
        "blinded-test relation",
        "submission row",
        "leaderboard-driven selection",
        "private portal value",
    ):
        assert prohibited in terminal["forbidden"]


def test_g3_contract_contains_no_private_submission_fields() -> None:
    text = CONTRACT.read_text(encoding="utf-8").lower()
    forbidden = ("submission_name", "leaderboard_score", "leaderboard_rank")
    assert all(value not in text for value in forbidden)
