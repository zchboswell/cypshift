from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_maplight_robustness_execution_contract.json"
CLAIM_PATH = BENCHMARK / "global_v2_maplight_robustness_execution_claim.json"
PARENT_PATH = BENCHMARK / "global_v2_maplight_robustness_contract.json"
BOUNDED_PATH = (
    BENCHMARK / "global_v2_maplight_robustness_bounded_execution_contract.json"
)
REPRODUCTION_PATH = BENCHMARK / "global_v2_maplight_official_reproduction.json"
EXECUTION_PATH = BENCHMARK / "global_v2_maplight_execution_contract.json"
CONTRACT_SHA256 = "65934b0acdd509138a05a01f8c727fca9dd762023f4d3f90c0401f9e8a91f488"
CLAIM_SHA256 = "da0104bc8d297904fc26e019f1717fee38411d9aa741c774f2185090bcceb334"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_and_claim_have_exact_frozen_identity() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert _sha(CONTRACT_PATH) == CONTRACT_SHA256
    assert _sha(CLAIM_PATH) == CLAIM_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v2_maplight_robustness_execution_contract.v1"
    )
    assert contract["gate"] == ("G2_7D_MAPLIGHT_ROBUSTNESS_EXECUTION_CONTRACT_FROZEN")
    assert contract["status"] == (
        "contract_and_unconsumed_claim_only_no_official_execution_yet"
    )
    assert contract["base_commit"] == "15db9fb0cdee6a2497a2d468d8208b81e1fb7c85"
    assert claim["status"] == "G2_7D_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
    assert claim["contract_sha256"] == CONTRACT_SHA256
    assert claim["claim_id"] == contract["claim_contract"]["claim_id"]
    assert contract["claim_contract"]["claim_path"] == CLAIM_PATH.name


def test_every_parent_and_accepted_source_is_receipt_bound() -> None:
    contract = _load(CONTRACT_PATH)
    for name, parent in contract["parents"].items():
        if name == "post_main_ci":
            assert parent == {
                "run_id": 32892466738,
                "head_sha": "15db9fb0cdee6a2497a2d468d8208b81e1fb7c85",
                "conclusion": "success",
                "python_jobs_passed": ["3.11", "3.12.3", "3.14"],
            }
            continue
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha(path) == parent["sha256"]

    implementation = contract["accepted_implementation"]
    pairs = (
        ("robustness_compiler_path", "robustness_compiler_sha256"),
        ("no_fit_wrapper_path", "no_fit_wrapper_sha256"),
        ("resource_supervisor_path", "resource_supervisor_sha256"),
        ("no_fit_acceptance_driver_path", "no_fit_acceptance_driver_sha256"),
        ("no_fit_focused_tests_path", "no_fit_focused_tests_sha256"),
        ("no_fit_acceptance_tests_path", "no_fit_acceptance_tests_sha256"),
        ("maplight_runner_path", "maplight_runner_sha256"),
        ("accepted_official_compiler_path", "accepted_official_compiler_sha256"),
        ("accepted_official_wrapper_path", "accepted_official_wrapper_sha256"),
        ("tutorial_metric_source_path", "tutorial_metric_source_sha256"),
        ("chemistry_source_path", "chemistry_source_sha256"),
        ("research_lock_path", "research_lock_sha256"),
        ("root_lock_path", "root_lock_sha256"),
    )
    for path_key, hash_key in pairs:
        assert _sha(ROOT / implementation[path_key]) == implementation[hash_key]


def test_claim_is_single_use_and_deliberately_unusable() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert contract["claim_contract"]["maximum_consumptions"] == 1
    assert claim["maximum_consumptions"] == 1
    assert claim["consumptions"] == 0
    assert claim["usable"] is False
    for field in contract["claim_contract"]["future_receipt_fields"]:
        assert claim[field] is None
    assert all(value is False for value in claim["authority"].values())
    assert (
        "starts before atomic no-replace creation"
        in contract["claim_contract"]["consumption"]
    )
    assert "permits no retry" in contract["claim_contract"]["consumption"]


def test_fixed_roots_and_official_receipts_are_exact_without_source_access() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    official = contract["official_inputs"]
    assert official["attempt_root_absent_at_freeze"] is True
    assert official["development_source_root"].endswith(
        "g2-2c-maplight-development-source-v1"
    )
    assert official["fixed_baseline_terminal_root"].endswith(
        "g2-2c-maplight-development-attempt-1/terminal"
    )
    assert official["attempt_root"].endswith(
        "g2-7d-maplight-robustness-development-attempt-1"
    )
    assert claim["fixed_roots"] == {
        key: official[key]
        for key in (
            "development_source_root",
            "fixed_baseline_terminal_root",
            "attempt_root",
        )
    }
    expected_receipts = {
        "dataset_revision": official["dataset_revision"],
        **{name: value for name, value in official.items() if name.endswith("_sha256")},
    }
    assert claim["official_input_receipts"] == expected_receipts
    assert "does not list, parse, copy, link, hash" in official["read_boundary"]


def test_source_and_baseline_allowlists_are_least_privilege() -> None:
    official = _load(CONTRACT_PATH)["official_inputs"]
    assert official["source_file_allowlist"] == [
        "manifest.json",
        "direct_observations.csv",
        "group_folds.csv",
        "feature_rows.csv",
        "maplight_morgan_count.npy",
        "maplight_avalon_count.npy",
        "maplight_erg.npy",
        "maplight_rdkit_descriptors.npy",
    ]
    assert official["baseline_file_allowlist"] == [
        "manifest.json",
        "development_outer_oof.csv",
        "development_component_metrics.csv",
    ]
    assert official["denied_baseline_files"] == [
        "development_inner_oof.csv",
        "development_residuals.csv",
        "development_uncertainty.csv",
    ]
    reproduction = _load(REPRODUCTION_PATH)
    output_receipts = reproduction["receipts"]["outputs"]
    assert (
        official["baseline_outer_oof_sha256"]
        == output_receipts["development_outer_oof.csv"]
    )
    assert (
        official["baseline_component_metrics_sha256"]
        == output_receipts["development_component_metrics.csv"]
    )


def test_official_receipts_match_accepted_maplight_contract() -> None:
    official = _load(CONTRACT_PATH)["official_inputs"]
    accepted = _load(EXECUTION_PATH)["official_inputs"]
    for name in (
        "dataset_revision",
        "r2b_manifest_sha256",
        "r3a_feature_manifest_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "feature_rows_sha256",
        "maplight_morgan_count_sha256",
        "maplight_avalon_count_sha256",
        "maplight_erg_sha256",
        "maplight_rdkit_descriptors_sha256",
    ):
        assert official[name] == accepted[name]


def test_population_support_and_capabilities_freeze_truth_chronology() -> None:
    boundary = _load(CONTRACT_PATH)["source_and_capability_boundary"]
    assert boundary["population"] == {
        "all_molecules": 4905,
        "all_components": 4553,
        "development_molecules": 3908,
        "development_components": 3640,
        "confirmatory_molecules_excluded": 997,
        "confirmatory_components_excluded": 913,
        "finite_development_truth_rows": 5197,
    }
    assert boundary["support_minima"] == {
        "development_finite_targets_per_endpoint": 750,
        "outer_validation_targets_per_endpoint_repeat_fold": 75,
        "outer_training_targets_per_endpoint_repeat_fold": 400,
    }
    assert "cannot resolve validation truth" in boundary["model_capability"]
    assert "until every required prediction" in boundary["scorer_capability"]
    assert "Stage A alone" in boundary["scorer_capability"]


def test_scientific_topology_exactly_inherits_d122() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)
    execution = contract["scientific_execution"]
    assert execution["default_candidate"] == parent["fixed_maplight"]["candidate_id"]
    assert execution["drop_one_candidates"] == [
        item["candidate_id"] for item in parent["drop_one_candidates"]
    ]
    assert (
        execution["seed_perturbation_values"]
        == parent["stage_a_selection"]["seed_perturbation_values"]
    )
    assert execution["group_perturbations"] == [
        item["id"]
        for item in parent["stage_b_selected_robustness"]["group_perturbations"]
    ]
    fits = execution["fit_counts"]
    assert fits == {
        "stage_a_drop_one": 240,
        "stage_a_full_seed_perturbations": 300,
        "stage_a_total": 540,
        "stage_b_selected_group_perturbations": 180,
        "stage_c_if_deletion_selected": 300,
        "minimum_total": 720,
        "maximum_total": 1020,
        "baseline_refits": 0,
        "inner_fits": 0,
    }
    predictions = execution["prediction_counts"]
    assert predictions["stage_a"] == 422_064
    assert predictions["stage_b_upper_bound"] == 140_688
    assert predictions["stage_c_if_deletion_selected"] == 234_480
    assert predictions["minimum_total"] == 562_752
    assert predictions["maximum_total"] == 797_232
    assert all(
        execution[name] is False
        for name in ("retry", "resume", "move", "overwrite", "replacement")
    )


def test_constructor_and_stage_a_selection_are_immutable() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)
    constructor = contract["scientific_execution"]["constructor"]
    fixed = parent["fixed_maplight"]["constructor_arguments"]
    for name in (
        "loss_function",
        "random_strength",
        "task_type",
        "thread_count",
        "verbose",
        "allow_writing_files",
    ):
        assert constructor[name] == fixed[name]
    assert (
        constructor["omitted_arguments"]
        == parent["fixed_maplight"]["omitted_arguments"]
    )
    stage_a = contract["stage_a_selection"]
    assert stage_a["full_is_default"] is True
    assert "relative improvement is at least 0.01" in stage_a["drop_one_material_gate"]
    assert "MAE improvement is at least 0.005" in stage_a["drop_one_material_gate"]
    assert "strictly below zero" in stage_a["paired_gate"]
    assert "8 of 15" in stage_a["cell_gate"]
    assert "0.005" in stage_a["endpoint_gate"]
    assert stage_a["selection_tokens"] == 1
    assert stage_a["runner_ups"] == 0


def test_all_robustness_gates_and_bootstrap_are_conjunctive() -> None:
    evaluation = _load(CONTRACT_PATH)["robustness_evaluation"]
    assert evaluation["primary_metric"]["id"] == "TUTORIAL_MA_ST_RAE_858AE63_V1"
    bootstrap = evaluation["paired_bootstrap"]
    assert bootstrap["seed"] == 20260827
    assert bootstrap["accepted_replicates_per_drop_one_comparison"] == 2000
    assert bootstrap["drop_one_comparisons"] == 4
    assert bootstrap["total_accepted_drop_one_replicates"] == 8000
    assert bootstrap["maximum_attempts_per_comparison"] == 20000
    assert evaluation["selected_seed_gate"] == {
        "maximum_primary_relative_degradation": 0.03,
        "maximum_component_macro_mae_degradation": 0.015,
        "maximum_endpoint_component_mae_degradation": 0.025,
    }
    assert evaluation["selected_group_gate"] == {
        "maximum_component_macro_mae_degradation": 0.03,
        "maximum_endpoint_component_mae_degradation": 0.05,
        "support_and_containment_required": True,
    }
    assert (
        evaluation["duplicate_gate"]["maximum_absolute_component_macro_mae_change"]
        == 0.01
    )
    assert evaluation["influence_gate"] == {
        "components_removed": 10,
        "maximum_absolute_selected_component_macro_mae_change": 0.02,
        "maximum_selected_disadvantage_versus_full": 0.005,
    }
    assert evaluation["clipping_rejection_trigger"]["deployable_clips"] == 0
    assert "are conjunctive" in evaluation["logic"]


def test_resources_begin_before_consumption_and_match_d125() -> None:
    contract = _load(CONTRACT_PATH)
    bounded = _load(BOUNDED_PATH)
    resources = contract["runtime_and_resources"]
    assert resources["hard_maxima"] == {
        "cpu_core_hours": 128.0,
        "wall_hours": 7.68,
        "restricted_storage_gb": 51.2,
        "peak_simultaneous_rss_gib": 15.36,
        "gpu_hours": 0,
    }
    bounded_limits = bounded["cumulative_resource_envelope"]["hard_limits"]
    assert resources["hard_maxima"] == {
        "cpu_core_hours": bounded_limits["cpu_core_hours"],
        "wall_hours": bounded_limits["wall_hours"],
        "restricted_storage_gb": bounded_limits["restricted_storage_gb"],
        "peak_simultaneous_rss_gib": bounded_limits["peak_rss_gib"],
        "gpu_hours": bounded_limits["gpu_hours"],
    }
    assert "starts before claim consumption" in resources["measurement"]
    assert "every model child" in resources["measurement"]
    assert "Any limit, warning, fallback" in resources["acceptance"]
    assert resources["model"]["thread_count_per_fit"] == 16
    assert resources["model"]["maximum_concurrent_fits"] == 1


def test_terminal_publication_is_aggregate_only_and_fail_closed() -> None:
    terminal = _load(CONTRACT_PATH)["terminal_contract"]
    assert terminal["statuses"] == [
        "G2_7_PRIMARY_CONTENDER_FROZEN",
        "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED",
        "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
        "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED",
        "G2_7_MAPLIGHT_ROBUSTNESS_FAILED",
    ]
    assert len(terminal["required_aggregate_outputs"]) == 8
    assert len(terminal["private_row_level_outputs"]) == 4
    assert terminal["attempt_root_file_set"] == [
        "attempt_claim.json",
        "receipt",
        "terminal",
    ]
    assert "remain private" in terminal["publication"]
    assert "Cleanup failure changes" in terminal["cleanup"]
    assert "no retry, resume, move, overwrite" in terminal["failure"]


def test_contract_freeze_opens_zero_scientific_or_external_authority() -> None:
    contract = _load(CONTRACT_PATH)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert accounting["tracked_unconsumed_claims_created"] == 1
    assert all(
        value == 0
        for name, value in accounting.items()
        if name not in {"contracts_created", "tracked_unconsumed_claims_created"}
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert authority["tracked_unconsumed_claim"] is True
    assert all(
        value is False
        for name, value in authority.items()
        if name not in {"contract_and_static_tests", "tracked_unconsumed_claim"}
    )
    text = (CONTRACT_PATH.read_text() + CLAIM_PATH.read_text()).lower()
    for private_result_field in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
    ):
        assert private_result_field not in text
    assert contract["next_gate"].startswith("Implement only the additive")
    assert "Do not consume the claim" in contract["next_gate"]
