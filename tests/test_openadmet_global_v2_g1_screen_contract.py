from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_g1_screen_contract.json"
PARENT_PATH = BENCHMARK / "global_v2_experiment_contract.json"
BASELINE_PATH = BENCHMARK / "global_v2_maplight_official_reproduction.json"
CONTRACT_SHA256 = "ce39721f403686dbac67cf72ea3b5996212bb571b08cd1bb7f571d0c2e5d97c3"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g1_contract_has_exact_identity_and_parents() -> None:
    contract = _load(CONTRACT_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_g1_screen_contract.v1"
    )
    assert contract["gate"] == "G2_3A_EXP_G1_CONTRACT_FROZEN"
    assert contract["status"] == "contract_only_no_official_execution_authority"
    assert contract["base_commit"] == ("a0b1fbdc144fef7f7ed1fac9174334ef7252403b")
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_g1_contract_binds_reproduced_baseline_without_refit() -> None:
    contract = _load(CONTRACT_PATH)
    tracked = _load(BASELINE_PATH)
    baseline = contract["reproduced_baseline"]
    assert baseline["aggregate_receipt_sha256"] == _sha256(BASELINE_PATH)
    assert baseline["status"] == tracked["status"] == "G2_2_MAPLIGHT_REPRODUCED"
    assert (
        baseline["attempt_receipt_sha256"]
        == tracked["receipts"]["attempt_receipt_sha256"]
    )
    assert (
        baseline["consumed_claim_sha256"]
        == tracked["receipts"]["consumed_claim_sha256"]
    )
    assert (
        baseline["terminal_manifest_sha256"]
        == tracked["receipts"]["terminal_manifest_sha256"]
    )
    outputs = tracked["receipts"]["outputs"]
    assert (
        baseline["development_outer_oof_sha256"] == outputs["development_outer_oof.csv"]
    )
    assert (
        baseline["development_inner_oof_sha256"] == outputs["development_inner_oof.csv"]
    )
    assert (
        baseline["development_component_metrics_sha256"]
        == outputs["development_component_metrics.csv"]
    )
    assert contract["fit_and_prediction_budget"]["baseline_refits"] == 0
    assert "cannot be retried" in baseline["immutability"]


def test_g1_screen_is_exactly_the_parent_screen() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)["experiments"]["EXP-G1"]
    screen = contract["screen"]
    assert (
        screen["model_seeds"]
        == parent["model_seeds"]
        == [
            20260824,
            20260825,
            20260826,
        ]
    )
    assert screen["common_arguments"] == parent["common_arguments"]
    assert screen["configurations"] == parent["configurations"]
    assert len(screen["configurations"]) == 12
    assert [item["configuration_id"] for item in screen["configurations"]] == [
        f"G1-C{index:02d}" for index in range(12)
    ]
    assert len({item["configuration_id"] for item in screen["configurations"]}) == 12
    assert contract["development_evaluation"]["acceptance"] == {
        **parent["acceptance"],
        "logic": contract["development_evaluation"]["acceptance"]["logic"],
    }
    for field, value in parent["acceptance"].items():
        assert contract["development_evaluation"]["acceptance"][field] == value
    for field, value in parent["resource_ceiling"].items():
        assert contract["resource_ceiling"][field] == value


def test_g1_contract_binds_exact_accepted_runtime_sources() -> None:
    contract = _load(CONTRACT_PATH)
    runtime = contract["runtime"]
    assert runtime["accepted_maplight_runner_sha256"] == _sha256(
        ROOT / "research" / "maplight-fixed" / "global_v2_maplight_runner.py"
    )
    assert runtime["uv_lock_sha256"] == _sha256(
        ROOT / "research" / "maplight-fixed" / "uv.lock"
    )
    assert runtime["accepted_metric_source_sha256"] == _sha256(
        ROOT / "src" / "cypshift" / "openadmet_global_v2_metric.py"
    )
    assert "No eval_set" in runtime["parameter_rule"]


def test_g1_fit_and_prediction_arithmetic_is_exact_and_smaller_than_parent() -> None:
    contract = _load(CONTRACT_PATH)
    budget = contract["fit_and_prediction_budget"]
    population = contract["population_and_splits"]
    configurations = len(contract["screen"]["configurations"])
    seeds = len(contract["screen"]["model_seeds"])
    endpoints = len(population["endpoints"])
    inner_contexts = (
        population["repeats"]
        * population["outer_folds"]
        * population["inner_folds"]
        * endpoints
    )
    outer_cells = population["repeats"] * population["outer_folds"] * endpoints
    assert budget["inner_contexts"] == inner_contexts == 240
    assert (
        budget["inner_configuration_seed_fits"]
        == (inner_contexts * configurations * seeds)
        == 8640
    )
    assert budget["outer_endpoint_cells"] == outer_cells == 60
    assert budget["selected_outer_seed_fits"] == outer_cells * seeds == 180
    assert budget["exact_new_catboost_fits"] == 8640 + 180 == 8820
    assert budget["parent_maximum_model_fits"] == 8880
    assert budget["unused_parent_fit_capacity"] == 8880 - 8820 == 60
    assert "cannot fund" in budget["unused_capacity_rule"]

    molecules = population["label_free_assignment"]["development_molecules"]
    repeats = population["repeats"]
    outer_training_contexts_per_molecule = population["outer_folds"] - 1
    per_configuration_seed_inner_rows = (
        molecules * endpoints * repeats * outer_training_contexts_per_molecule
    )
    assert (
        budget["expected_inner_raw_prediction_rows"]
        == (per_configuration_seed_inner_rows * configurations * seeds)
        == 6753024
    )
    assert (
        budget["expected_inner_seed_averaged_rows"]
        == (per_configuration_seed_inner_rows * configurations)
        == 2251008
    )
    assert (
        budget["expected_complete_selection_projection_rows"]
        == (molecules * endpoints * repeats * configurations)
        == 562752
    )
    assert (
        budget["expected_outer_raw_prediction_rows"]
        == (molecules * endpoints * repeats * seeds)
        == 140688
    )
    assert (
        budget["expected_outer_seed_averaged_rows"]
        == (molecules * endpoints * repeats)
        == 46896
    )


def test_g1_selection_is_nested_seed_averaged_and_fail_closed() -> None:
    contract = _load(CONTRACT_PATH)
    stages = contract["capability_and_stage_contract"]
    selection = contract["nested_selection"]
    assert "cannot resolve inner validation truth" in stages["inner_model"]
    assert "cannot read outer-validation truth" in stages["inner_selector"]
    assert "cannot resolve outer-validation truth" in stages["outer_model"]
    assert (
        "Only after all candidate outer predictions are immutable"
        in stages["outer_scorer"]
    )
    assert "average the three seeds before scoring" in selection["outer_cell_rule"]
    assert "configuration_id" in selection["outer_cell_rule"]
    assert "math.fsum" in selection["numeric_policy"]
    assert "without an extra fit" in selection["complete_selection_projection"]
    assert (
        "cannot enter or revise EXP-G1 or EXP-G2"
        in selection["future_endpoint_configuration"]
    )
    assert "fails the attempt" in selection["numeric_policy"]
    assert "cannot change" in selection["forbidden_feedback"]


def test_g1_acceptance_is_conjunctive_and_preserves_endpoint_harm_gate() -> None:
    contract = _load(CONTRACT_PATH)
    evaluation = contract["development_evaluation"]
    acceptance = evaluation["acceptance"]
    assert acceptance["minimum_relative_primary_improvement"] == 0.03
    assert acceptance["minimum_absolute_component_mae_improvement"] == 0.015
    assert acceptance["paired_component_mae_upper_95_below_zero"]
    assert acceptance["maximum_endpoint_mae_degradation"] == 0.015
    assert acceptance["minimum_favorable_outer_cells"] == 8
    assert acceptance["total_outer_cells"] == 15
    assert "Every member is conjunctive" in acceptance["logic"]
    assert "retains fixed MapLight" in evaluation["decision"]
    assert "stops EXP-G1" in evaluation["decision"]
    assert "exact same molecule" in evaluation["paired_identity"]
    assert evaluation["primary_metric"]["id"] == "TUTORIAL_MA_ST_RAE_858AE63_V1"
    assert (
        "no local value may be called an official score"
        in evaluation["primary_metric"]["name_boundary"]
    )


def test_g1_contract_freeze_opens_no_scientific_capability() -> None:
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
    assert contract["runtime"]["future_g1_runner_sha256"] is None
    assert contract["runtime"]["future_g1_synthetic_acceptance_sha256"] is None
    assert "Do not open official inputs" in contract["next_gate"]
    assert "fit an official model" in contract["next_gate"]
    assert "create an execution claim" in contract["next_gate"]


def test_g1_terminals_make_failure_and_clean_rejection_irreversible() -> None:
    contract = _load(CONTRACT_PATH)
    terminal = contract["terminal_contract"]
    assert terminal["statuses"] == [
        "G2_3_G1_FAILED",
        "G2_3_G1_UNDERPOWERED",
        "G2_3_G1_REJECTED",
        "G2_3_G1_ACCEPTED",
    ]
    assert "No retry, resume, move, overwrite" in terminal["failure"]
    assert "authoritative negative evidence" in terminal["rejection"]
    assert "Row-level targets" in terminal["publication"]
    assert contract["resource_ceiling"] == {
        "cpu_core_hours": 1200,
        "gpu_hours": 0,
        "restricted_storage_gb": 40,
        "maximum_wall_hours": 120,
        "concurrency": contract["resource_ceiling"]["concurrency"],
    }
