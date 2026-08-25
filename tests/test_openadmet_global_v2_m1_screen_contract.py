from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_m1_screen_contract.json"
PARENT_PATH = BENCHMARK / "global_v2_experiment_contract.json"
BASELINE_PATH = BENCHMARK / "global_v2_maplight_official_reproduction.json"
CONTRACT_SHA256 = "63516e0f3b9b87cd24911d39d753de0dabac458413d05a6ac83a27d97b1c2cc0"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m1_contract_has_exact_identity_and_authenticated_parents() -> None:
    contract = _load(CONTRACT_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_m1_screen_contract.v1"
    )
    assert contract["gate"] == "G2_4A_EXP_M1_CONTRACT_FROZEN"
    assert contract["status"] == (
        "contract_only_no_implementation_or_official_execution_authority"
    )
    assert contract["base_commit"] == "080925e13a25748a0d6b8811aa265a8680be59b8"
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_m1_contract_is_an_exact_child_of_parent_hypothesis() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)["experiments"]["EXP-M1"]
    assert contract["hypothesis"] == parent["hypothesis"].replace(
        ".",
        " and the gain disappears when training labels are detached from molecules.",
    )
    assert contract["optimization"]["model_seeds"] == parent["model_seeds"]
    shared = parent["shared_model"]
    assert shared["trunk_widths"] == [512, 256]
    assert "Linear(2248,512)" in contract["systems"]["shared_candidate"]["trunk"]
    assert "Linear(512,256)" in contract["systems"]["shared_candidate"]["trunk"]
    assert shared["dropout"] == 0.1
    assert shared["endpoint_head_width"] == 64
    assert shared["masked_endpoints"] == 4
    optimizer = contract["optimization"]["optimizer"]
    assert optimizer["name"] == shared["optimizer"] == "AdamW"
    assert optimizer["learning_rate"] == shared["learning_rate"] == 0.001
    assert optimizer["weight_decay"] == shared["weight_decay"] == 0.0001
    assert contract["optimization"]["batching"]["batch_size"] == 128
    assert contract["optimization"]["epochs"]["maximum"] == 300
    assert contract["optimization"]["epochs"]["patience"] == 25


def test_m1_inputs_are_target_blind_fold_fitted_and_shared_by_controls() -> None:
    contract = _load(CONTRACT_PATH)
    features = contract["feature_contract"]
    assert features["morgan_count"] == {
        "radius": 2,
        "columns": 2048,
        "use_counts": True,
        "include_chirality": True,
        "use_bond_types": True,
        "include_redundant_environments": False,
        "order": "bit index 0 through 2047",
    }
    assert features["rdkit_descriptors"]["columns"] == 200
    assert features["total_columns"] == 2248
    preprocessing = features["fold_fitted_preprocessing"]
    assert "target availability" in preprocessing["fit_population"]
    assert "float64 median" in preprocessing["descriptor_imputation"]
    assert "ddof=0" in preprocessing["standardization"]
    assert "byte-identical" in preprocessing["sharing"]
    assert "training molecules only" in preprocessing["standardization"]


def test_m1_family_and_mask_boundaries_fail_closed() -> None:
    contract = _load(CONTRACT_PATH)
    population = contract["population_and_splits"]
    assert population["repeats"] == 3
    assert population["outer_folds"] == 5
    assert population["inner_folds"] == 4
    assert len(population["endpoints"]) == 4
    assert "No similarity_component_hash may cross" in population["family_invariant"]
    assert "never imputed" in population["training_masks"]["CENTRAL_MAE"]
    assert (
        "point-only cells remain masked"
        in population["training_masks"]["INTERVAL_DEAD_ZONE"]
    )
    assert "zero fits" in population["failure"]


def test_m1_controls_share_architecture_loss_and_seed_reduction() -> None:
    contract = _load(CONTRACT_PATH)
    systems = contract["systems"]
    assert systems["independent_control"]["networks"] == 4
    assert "exact shared trunk" in systems["independent_control"]["architecture"]
    assert "same transformed rows" in systems["independent_control"]["architecture"]
    assert "Screen both exact losses" in systems["independent_control"]["loss_control"]
    assert "strongest control" in systems["independent_control"]["loss_control"]
    assert systems["permuted_control"]["permutation_seed"] == 20260829
    assert "No label enters or exits" in systems["permuted_control"]["bundle"]
    assert "same scoped permutation" in systems["permuted_control"]["validation"]
    assert "deterministic bijection" in systems["permuted_control"]["identity_check"]


def test_m1_loss_and_epoch_selection_are_strictly_nested() -> None:
    contract = _load(CONTRACT_PATH)
    selection = contract["nested_loss_selection"]
    assert "all four inner folds" in selection["candidate_only_screen"]
    assert "Average the three seed predictions" in selection["candidate_only_screen"]
    assert "tutorial MA-ST-RAE" in selection["selection_population"]
    assert "component-macro central MAE" in selection["selection_population"]
    assert "lexicographically lower loss_id" in selection["selection_population"]
    assert "shared candidate and permuted control" in selection["selected_token"]
    assert "both independent losses" in selection["independent_control_selection"]
    assert "strongest nested independent control" in selection["independent_outer_rule"]
    assert "cannot revise" in selection["permuted_stopping"]
    assert "cannot select" in selection["forbidden_feedback"]
    epochs = contract["optimization"]["epochs"]
    assert "strict decrease" in epochs["inner_checkpoint"]
    assert "floor((second + third)/2)" in epochs["outer_epoch_rule"]
    assert "without outer validation" in epochs["outer_epoch_rule"]


def test_m1_fit_and_prediction_arithmetic_is_exact() -> None:
    contract = _load(CONTRACT_PATH)
    population = contract["population_and_splits"]
    budget = contract["fit_and_prediction_budget"]
    repeats = population["repeats"]
    outer = population["outer_folds"]
    inner = population["inner_folds"]
    endpoints = len(population["endpoints"])
    seeds = len(contract["optimization"]["model_seeds"])
    losses = len(contract["optimization"]["losses"])
    molecules = population["label_free_assignment"]["development_molecules"]

    assert budget["inner_fold_contexts"] == repeats * outer * inner == 60
    assert budget["outer_contexts"] == repeats * outer == 15
    assert budget["shared_two_loss_inner_fits"] == 60 * losses * seeds == 360
    assert budget["shared_selected_outer_fits"] == 15 * seeds == 45
    assert (
        budget["independent_two_loss_inner_fits"]
        == (60 * endpoints * seeds * losses)
        == 1440
    )
    assert (
        budget["independent_two_loss_outer_fits"]
        == (15 * endpoints * seeds * losses)
        == 360
    )
    assert budget["permuted_selected_loss_inner_fits"] == 60 * seeds == 180
    assert budget["permuted_selected_outer_fits"] == 15 * seeds == 45
    assert budget["exact_new_neural_fits"] == 2430
    assert budget["baseline_refits"] == 0

    one_system_inner = molecules * endpoints * repeats * (outer - 1)
    assert (
        budget["expected_inner_raw_prediction_rows"]
        == (one_system_inner * seeds * (losses + losses + 1))
        == 2813760
    )
    assert (
        budget["expected_inner_seed_averaged_rows"]
        == (one_system_inner * (losses + losses + 1))
        == 937920
    )
    one_system_outer = molecules * endpoints * repeats
    assert (
        budget["expected_outer_raw_prediction_rows"]
        == (one_system_outer * seeds * 4)
        == 562752
    )
    assert (
        budget["expected_outer_seed_averaged_rows"] == (one_system_outer * 4) == 187584
    )
    assert "cannot fund" in budget["budget_rule"]


def test_m1_acceptance_requires_baseline_gain_and_both_controls() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)["experiments"]["EXP-M1"]["acceptance"]
    acceptance = contract["development_evaluation"]["acceptance"]
    assert (
        acceptance["minimum_absolute_component_mae_improvement_vs_fixed_maplight"]
        == (parent["minimum_absolute_component_mae_improvement"])
        == 0.02
    )
    assert (
        acceptance["minimum_materially_improved_endpoints_vs_fixed_maplight"]
        == (parent["minimum_materially_improved_endpoints"])
        == 2
    )
    assert (
        acceptance["maximum_endpoint_mae_degradation_vs_fixed_maplight"]
        == (parent["maximum_endpoint_mae_degradation"])
        == 0.02
    )
    assert acceptance["shared_must_strictly_beat_matching_independent_component_mae"]
    assert acceptance["shared_vs_matching_independent_paired_upper_95_below_zero"]
    assert acceptance["shared_must_strictly_beat_selected_independent_component_mae"]
    assert acceptance["shared_vs_selected_independent_paired_upper_95_below_zero"]
    assert acceptance["shared_must_strictly_beat_permuted_component_mae"]
    assert acceptance["shared_vs_permuted_paired_upper_95_below_zero"]
    assert acceptance["permuted_must_not_pass_fixed_maplight_promotion"]
    assert "Every member is conjunctive" in acceptance["logic"]
    assert "permanently stops EXP-M1" in contract["development_evaluation"]["decision"]


def test_m1_resource_gate_keeps_twenty_percent_margin() -> None:
    contract = _load(CONTRACT_PATH)
    ceiling = contract["resource_ceiling"]
    gate = contract["resource_feasibility_gate"]
    assert ceiling["cpu_core_hours"] == 300
    assert ceiling["gpu_hours"] == 80
    assert ceiling["restricted_storage_gb"] == 80
    assert ceiling["maximum_wall_hours"] == 48
    assert gate["maximum_projected_cpu_core_hours"] == 0.8 * ceiling["cpu_core_hours"]
    assert gate["maximum_projected_gpu_hours"] == 0.8 * ceiling["gpu_hours"]
    assert gate["maximum_projected_restricted_storage_gb"] == (
        0.8 * ceiling["restricted_storage_gb"]
    )
    assert round(gate["maximum_projected_wall_hours"] * 10) == (
        ceiling["maximum_wall_hours"] * 8
    )
    assert "worse root" in gate["method"]
    assert "no second optimization" in gate["margin"]


def test_m1_contract_freeze_opens_no_scientific_capability() -> None:
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
    assert "deterministic neural runtime" in contract["next_gate"]
    assert "before opening any official input" in contract["next_gate"]
    assert "creating an execution claim" in contract["next_gate"]


def test_m1_terminal_is_one_shot_and_private_by_construction() -> None:
    contract = _load(CONTRACT_PATH)
    terminal = contract["terminal_contract"]
    assert terminal["statuses"] == [
        "G2_4_M1_FAILED",
        "G2_4_M1_UNDERPOWERED",
        "G2_4_M1_RESOURCE_REJECTED",
        "G2_4_M1_REJECTED",
        "G2_4_M1_ACCEPTED",
    ]
    assert "private leaderboard observation remain private" in terminal["publication"]
    assert "No retry, resume, move, overwrite" in terminal["failure"]
    assert "cannot authorize a wider MLP" in terminal["rejection"]
    baseline = _load(BASELINE_PATH)
    assert contract["accepted_baseline"]["aggregate_receipt_sha256"] == _sha256(
        BASELINE_PATH
    )
    assert contract["accepted_baseline"]["status"] == baseline["status"]
    assert contract["accepted_baseline"]["baseline_refits"] == 0
