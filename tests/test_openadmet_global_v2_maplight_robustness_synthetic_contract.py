from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = BENCHMARK / "global_v2_maplight_robustness_synthetic_contract.json"
PARENT = BENCHMARK / "global_v2_maplight_robustness_contract.json"
CONTRACT_SHA256 = "97b982fa2751789042f7650b86f943133529af7af3e19c6af3dde0c441e2abfd"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_robustness_synthetic_contract_binds_green_parent() -> None:
    contract = _read(CONTRACT)
    assert _sha256(CONTRACT) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v2_maplight_robustness_synthetic_contract.v1"
    )
    assert contract["gate"] == (
        "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_only_no_synthetic_or_official_execution_authority"
    )
    assert contract["base_commit"] == (
        "a6225f30322fbc210e3c4b2f3481edf0c2079637"
    )
    assert _sha256(PARENT) == contract["parents"][
        "maplight_robustness_contract"
    ]["sha256"]
    ci = contract["parents"]["post_main_ci"]
    assert ci == {
        "run_id": 32868137658,
        "head_sha": "a6225f30322fbc210e3c4b2f3481edf0c2079637",
        "conclusion": "success",
        "python_jobs_passed": ["3.11", "3.12.3", "3.14"],
    }
    for key, parent in contract["parents"].items():
        if key == "post_main_ci":
            continue
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]


def test_mechanics_fixture_exercises_family_overlays_and_exact_support() -> None:
    fixture = _read(CONTRACT)["synthetic_mechanics_fixture"]
    assert fixture["roots"] == 2
    assert fixture["components"] == 600
    assert fixture["molecules_per_component"] == 2
    assert fixture["molecules"] == 1200
    assert fixture["development_components"] == 480
    assert fixture["development_molecules"] == 960
    assert fixture["confirmatory_components"] == 120
    assert fixture["confirmatory_molecules"] == 240
    assert fixture["finite_development_targets_per_endpoint"] == 960
    assert fixture["features"]["columns"] == 2563
    assert sum(fixture["features"]["blocks"].values()) == 2563
    assert "reverse every physical source row" in fixture["root_b_order"]
    assert "at least 75 finite validation and 400 finite training" in fixture[
        "overlay_support"
    ]

    overlays = fixture["overlay_oracles"]
    expected = {
        "THRESHOLD_0_55": (4, 8, 952),
        "THRESHOLD_0_50": (8, 16, 944),
        "TAUTOMER_MERGED": (6, 12, 948),
    }
    for overlay_id, (touching, excluded, remaining) in expected.items():
        oracle = overlays[overlay_id]
        assert oracle["development_components_touching_confirmatory"] == touching
        assert oracle["development_molecules_excluded"] == excluded
        assert oracle["remaining_development_molecules"] == remaining
        assert excluded + remaining == 960


def test_both_conditional_topologies_are_exact() -> None:
    contract = _read(CONTRACT)
    topology = contract["full_topology_model_double"]
    full = topology["per_root"]["FULL_RETAINED"]
    deletion = topology["per_root"]["DROP_MORGAN_SELECTED"]
    parent = _read(PARENT)

    assert full["stage_a_invocations"] == parent["workload"]["stage_a_fits"] == 540
    assert full["stage_b_invocations"] == parent["workload"]["stage_b_fits"] == 180
    assert full["stage_c_invocations"] == 0
    assert full["total_invocations"] == parent["workload"]["minimum_new_fits"] == 720
    assert deletion["stage_a_invocations"] == 540
    assert deletion["stage_b_invocations"] == 180
    assert deletion["stage_c_invocations"] == (
        parent["workload"]["stage_c_conditional_fits"]
    ) == 300
    assert deletion["total_invocations"] == (
        parent["workload"]["maximum_new_fits"]
    ) == 1020
    assert topology["per_root"]["total_invocations"] == 720 + 1020 == 1740
    assert topology["across_roots"]["model_double_invocations"] == 3480
    assert topology["per_root"]["prediction_rows"] == 137808 + 195408 == 333216
    assert topology["across_roots"]["prediction_rows"] == 666432
    assert "never be reported as CatBoost fits" in topology["fit_accounting"]


def test_selection_oracles_bind_full_default_occam_and_conditional_stage() -> None:
    contract = _read(CONTRACT)
    oracles = contract["selection_oracles"]
    assert oracles["full_retained_profile"]["expected_selected_candidate"] == (
        "G2-7-M0-FULL"
    )
    assert oracles["deletion_selected_profile"]["expected_selected_candidate"] == (
        "G2-7-M1-DROP-MORGAN"
    )
    joined = " ".join(oracles["ordering_micro_oracles"])
    for required in (
        "No eligible deletion returns G2-7-M0-FULL",
        "resolve lexicographically",
        "1,539-column deletion precedes",
        "cannot create or revise the selection token",
    ):
        assert required in joined
    assert "no evidence" in oracles["scientific_boundary"]


def test_exact_catboost_probe_is_minimal_but_covers_all_forms() -> None:
    probe = _read(CONTRACT)["exact_catboost_probe"]
    fits = probe["fits_per_root"]
    assert fits["five_candidate_shapes_at_random_seed_1_on_primary_indices"] == 5
    assert fits["full_shape_at_each_of_five_frozen_alternative_seeds"] == 5
    assert fits["full_shape_at_random_seed_1_on_three_overlay_index_forms"] == 3
    assert fits["total"] == 13
    assert probe["roots"] == 2
    assert probe["exact_total_real_catboost_fits"] == 26
    assert probe["resource_matrix"]["rows"] == 3908
    assert probe["resource_matrix"]["full_columns"] == 2563
    assert probe["resource_matrix"]["training_rows"] == 3120
    assert probe["resource_matrix"]["prediction_rows"] == 788
    assert probe["prediction_rows_per_root"] == 13 * 788 == 10244
    assert probe["prediction_rows_across_roots"] == 20488
    assert "No fast mode" in probe["model_api"]
    assert "five ordered feature views, four unique column counts" in probe[
        "acceptance"
    ]
    assert "six total seed values" in probe["acceptance"]
    assert "any model-quality claim" in probe["scientific_boundary"]


def test_stage_graph_freezes_predictions_before_truth_and_tokens_once() -> None:
    stages = _read(CONTRACT)["stage_graph"]
    assert "before target parsing" in stages["trusted_compiler"]
    assert "cannot resolve validation truth" in stages["stage_a_model"]
    assert "complete 540 fit/prediction identity set" in stages["stage_a_freezer"]
    assert "exactly one immutable selection token" in stages[
        "stage_a_scorer_and_selector"
    ]
    assert "Freeze all 180 perturbation predictions" in stages[
        "stage_b_freezer_and_scorer"
    ]
    assert "exactly zero stage-C identities" in stages["stage_c_conditional"]
    assert "exactly 300 selected-deletion seed identities" in stages[
        "stage_c_conditional"
    ]
    assert "A clip can reject but never replace" in stages["no_fit_diagnostics"]
    assert "no-replace semantics" in stages["terminal_publisher"]


def test_resource_projection_uses_worst_fit_and_twenty_percent_margin() -> None:
    contract = _read(CONTRACT)
    falsifier = contract["full_size_resource_falsifier"]
    parent_ceiling = _read(PARENT)["resource_ceiling"]
    population = falsifier["official_shaped_synthetic_population"]
    assert population["development_molecules"] == 3908
    assert population["confirmatory_identities_without_truth"] == 997
    assert population["maximum_branch_fit_identities"] == 1020
    assert population["maximum_branch_prediction_identities"] == 797232
    projection = falsifier["projection"]
    assert projection["scientific_fits"] == 1020
    assert projection["wall_formula"].startswith(
        "1020 * worse_root_max_individual_exact_fit_wall_seconds"
    )
    assert projection["cpu_formula"].startswith(
        "1020 * worse_root_max_individual_exact_fit_cpu_seconds"
    )
    maxima = falsifier["acceptance_maxima"]
    assert maxima["projected_cpu_core_hours"] == pytest.approx(
        0.8 * parent_ceiling["cpu_core_hours"]
    )
    assert maxima["projected_wall_hours"] == pytest.approx(
        0.8 * parent_ceiling["maximum_wall_hours"]
    )
    assert maxima["projected_restricted_storage_gb"] == pytest.approx(
        0.8 * parent_ceiling["restricted_storage_gb"]
    )
    assert maxima["peak_rss_gib"] == pytest.approx(
        0.8 * parent_ceiling["peak_rss_gib"]
    )
    assert maxima["gpu_hours"] == 0
    assert "never the mean" in falsifier["logic"]


def test_terminals_adversaries_and_acceptance_are_conjunctive() -> None:
    contract = _read(CONTRACT)
    terminal = contract["deterministic_terminal_contract"]
    assert len(terminal["relative_files"]) == 8
    assert "byte-identical" in terminal["comparison"]
    assert terminal["success"] == (
        "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_ACCEPTED"
    )
    assert terminal["failure"] == (
        "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_REJECTED"
    )
    assert not any(
        terminal[key] for key in ("retry", "resume", "overwrite", "replacement")
    )

    adversaries = "\n".join(contract["required_adversarial_tests"])
    assert len(contract["required_adversarial_tests"]) == 15
    for required in (
        "confirmatory identity is excluded",
        "exactly 720 invocations",
        "exactly 1,020 invocations",
        "cannot revise the selected token",
        "all 26 real CatBoost fits",
        "worse maximum individual fit",
        "private-portal counters remain exactly zero",
    ):
        assert required in adversaries

    acceptance = contract["acceptance"]
    assert acceptance["fresh_sequential_roots"] == 2
    assert acceptance["mechanics_profiles_per_root"] == 2
    assert acceptance["model_double_invocations_total"] == 3480
    assert acceptance["real_catboost_fits_total"] == 26
    assert acceptance["full_size_maximum_branch_prediction_identities_per_root"] == (
        797232
    )
    assert "no model-quality meaning" in acceptance["scientific_interpretation"]


def test_contract_freeze_opens_no_execution_or_claim_authority() -> None:
    contract = _read(CONTRACT)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert all(value == 0 for key, value in accounting.items() if key != "contracts_created")
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key != "contract_and_static_tests"
    )
    assert all(
        value is None
        for value in contract["runtime_contract"]["future_source_receipts"].values()
    )
    assert "Do not create an official claim" in contract["next_gate"]
    assert "open an official byte" in contract["next_gate"]


def test_contract_records_no_private_submission_identity_or_result() -> None:
    text = CONTRACT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text
