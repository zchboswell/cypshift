from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RESEARCH = ROOT / "research" / "maplight-fixed"
CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_repair_contract.json"
)
CLAIM = BENCHMARK / "global_v2_maplight_robustness_execution_claim_v2.json"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_identity_and_driver_only_repair_surface() -> None:
    contract = _load(CONTRACT)
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v2_maplight_robustness_official_orchestration_repair_contract.v1"
    )
    assert contract["gate"] == (
        "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_REPAIR_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_only_no_repair_implementation_or_acceptance_or_official_execution_yet"
    )
    assert contract["base_commit"] == "1c0c5d0f293579a8748e25b3951f9234409bfa39"

    repair = contract["repair_surface"]
    driver = "research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py"
    assert repair["production_files_that_may_change"] == [driver]
    assert repair["new_acceptance_driver"] == (
        "research/maplight-fixed/"
        "run_global_v2_maplight_robustness_official_orchestration_acceptance.py"
    )
    assert repair["new_focused_tests"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
    )
    immutable_paths = {
        item["path"]
        for item in contract["immutable_science_kernel"].values()
        if isinstance(item, dict)
    }
    assert driver not in immutable_paths
    assert not immutable_paths.intersection(
        {repair["new_acceptance_driver"], repair["new_focused_tests"]}
    )
    assert any(
        "candidate, feature, parameter" in rule
        for rule in repair["forbidden_driver_changes"]
    )
    assert any(
        "claim template mutation" in rule for rule in repair["forbidden_driver_changes"]
    )


def test_every_public_parent_and_science_kernel_hash_is_bound() -> None:
    contract = _load(CONTRACT)
    parent_evidence = contract["immutable_parent_evidence"]
    for name in (
        "corrected_execution_contract_v2",
        "tracked_unconsumed_claim_v2",
        "d135_science_kernel_acceptance",
        "d136_test_provenance_bridge",
    ):
        parent = parent_evidence[name]
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]

    formal_driver = parent_evidence["historical_formal_acceptance_driver"]
    formal_tests = parent_evidence["historical_formal_focused_tests"]
    assert (
        _sha256(RESEARCH / formal_driver["path"].split("/")[-1])
        == formal_driver["sha256"]
    )
    assert _sha256(ROOT / formal_tests["path"]) == formal_tests["sha256"]

    # The live official driver is the sole permitted production repair surface.
    # Its historical bytes remain independently bound by both public receipts.
    historical_driver = parent_evidence["historical_accepted_official_driver"]
    d135 = _load(BENCHMARK / parent_evidence["d135_science_kernel_acceptance"]["path"])
    d136 = _load(BENCHMARK / parent_evidence["d136_test_provenance_bridge"]["path"])
    assert d135["official_attempt_driver_source_sha256"] == historical_driver["sha256"]
    assert d136["official_driver_sha256"] == historical_driver["sha256"]
    assert historical_driver["execution_authority_after_this_contract"] is False

    for evidence in contract["immutable_science_kernel"].values():
        if not isinstance(evidence, dict):
            continue
        path = ROOT / evidence["path"]
        assert path.is_file()
        assert _sha256(path) == evidence["sha256"]


def test_five_statuses_have_disjoint_fail_closed_classification() -> None:
    taxonomy = _load(CONTRACT)["terminal_taxonomy"]
    statuses = {
        taxonomy["scientific_success"],
        taxonomy["clean_support_stop"],
        taxonomy["scientific_rejection"],
        taxonomy["hard_resource_abort"],
        taxonomy["execution_failure"],
    }
    assert statuses == {
        "G2_7_PRIMARY_CONTENDER_FROZEN",
        "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED",
        "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
        "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED",
        "G2_7_MAPLIGHT_ROBUSTNESS_FAILED",
    }
    assert taxonomy["hard_resource_reasons"] == [
        "wall limit exceeded",
        "CPU limit exceeded",
        "storage limit exceeded",
        "simultaneous RSS limit exceeded",
    ]
    assert taxonomy["failed_reasons"] == [
        "warning or stderr output observed",
        "supervised process exited nonzero",
        "no resource checkpoint was acknowledged",
        "resource checkpoint request differs",
        "descendant detached from the supervised process group",
        "supervisor failure",
        "malformed or absent supervisor observation",
        "cleanup, staging, accounting, receipt, or publication failure",
    ]
    protocol = taxonomy["supervisor_exception_protocol"]
    assert protocol["delimiter"] == "; observation="
    assert protocol["required_observation_fields"] == [
        "wall_seconds",
        "cpu_seconds",
        "peak_storage_bytes",
        "peak_simultaneous_rss_bytes",
        "gpu_hours",
        "checkpoints_acknowledged",
        "descendant_processes_observed",
        "return_code",
        "cleanup_complete",
        "network_namespace_isolated",
        "gpu_environment_hidden",
        "detached_children_observed",
        "warnings_observed",
    ]
    assert (
        "exactly the 13 accepted ResourceObservation fields" in protocol["validation"]
    )
    assert (
        "missing or malformed observation after claim consumption is FAILED"
        in (protocol["validation"])
    )
    success = protocol["scientific_or_underpowered_success"]
    assert "integer zero and not a boolean" in success
    assert "checkpoints_acknowledged and descendant_processes_observed" in success
    assert "within the frozen parent hard limits" in success
    assert (
        "Only the compiler's exact RobustnessExecutionUnderpowered"
        in taxonomy["underpowered_rule"]
    )
    assert "before any model fit" in taxonomy["underpowered_rule"]
    assert (
        "Unknown supervisor reasons fail closed as FAILED" in taxonomy["cleanup_rule"]
    )


def test_aggregate_accounting_cardinalities_and_formulas_are_exact() -> None:
    accounting = _load(CONTRACT)["aggregate_accounting"]
    assert accounting["official_population"] == {
        "all_molecules": 4905,
        "development_molecules": 3908,
        "confirmatory_molecules": 997,
        "direct_endpoint_rows": 19620,
        "accepted_group_fold_rows": 73575,
        "baseline_outer_prediction_rows_per_open": 46896,
        "finite_development_point_values": 5197,
    }
    assert accounting["underpowered_formula"] == {
        "official_source_rows_opened": "19620",
        "official_group_fold_rows_opened": "73575",
        "official_generated_model_fold_rows_opened": "0",
        "official_all_fold_rows_opened": "73575",
        "official_source_target_values_opened": "5197",
        "official_target_values_opened": "5197 central point values",
        "official_reported_bound_values_opened": "0",
        "official_feature_identity_rows_opened": "4905",
        "official_feature_matrix_rows_opened": "4 * 4905",
        "official_feature_rows_opened": "5 * 4905",
        "official_generated_model_feature_rows_opened": "0",
        "official_all_feature_rows_opened": "5 * 4905",
        "official_baseline_rows_opened": "0",
        "official_scoring_truth_values_opened": "0",
        "official_training_target_values_opened": "0",
        "official_model_fits": "0",
        "official_predictions_generated": "0",
        "official_prediction_rows_opened_for_scoring": "0",
        "development_metric_evaluations": "0",
        "claims_consumed": "1",
    }
    assert accounting["completed_battery_formula"] == {
        "official_source_rows_opened": (
            "2 * 19620 for the robustness and scoring compiler decode passes"
        ),
        "official_group_fold_rows_opened": (
            "73575 for the robustness compiler source crossing; the scoring "
            "compiler does not reopen group_folds.csv"
        ),
        "official_generated_model_fold_rows_opened": (
            "5 * model_fold_rows when full MapLight is retained or 6 * "
            "model_fold_rows when the selected deletion triggers stage C; "
            "model_fold_rows is the exact authenticated D-126 generated "
            "folds-capability count derived from its preflight exclusions and "
            "receipt"
        ),
        "official_all_fold_rows_opened": (
            "73575 plus official_generated_model_fold_rows_opened"
        ),
        "official_source_target_values_opened": (
            "2 * 5197 for the robustness and scoring compiler source decodes"
        ),
        "official_scoring_truth_values_opened": (
            "5 * 5197 for three scoring-compiler capability validations plus "
            "selection and terminal scoring"
        ),
        "official_reported_bound_values_opened": (
            "6 * counts.tutorial_eligible_rows from the authenticated "
            "scoring-capability manifest: two finite bounds during scoring "
            "compilation and two during each of selection and terminal scoring"
        ),
        "official_training_target_values_opened": (
            "sum of the exact completed stage manifests"
        ),
        "official_target_values_opened": (
            "7 * 5197 central point values plus the sum of stage-manifest "
            "training_target_values_opened; finite reported bounds are counted "
            "separately"
        ),
        "official_feature_identity_rows_opened": "4905",
        "official_feature_matrix_rows_opened": "4 * 4905",
        "official_feature_rows_opened": "5 * 4905",
        "official_generated_model_feature_rows_opened": (
            "4 * 4 * 3908 when full MapLight is retained or 5 * 4 * 3908 "
            "when the selected deletion triggers stage C"
        ),
        "official_all_feature_rows_opened": (
            "5 * 4905 plus official_generated_model_feature_rows_opened"
        ),
        "official_baseline_rows_opened": (
            "2 * 46896 for the frozen selection and terminal scoring opens"
        ),
        "official_model_fits": (
            "720 when full MapLight is retained or 1020 when the selected "
            "deletion triggers stage C"
        ),
        "stage_a_predictions_generated": "422064",
        "stage_b_predictions_generated": (
            "the exact authenticated stage-B manifest value, greater than zero "
            "and strictly less than its 140688 upper bound because every "
            "non-primary overlay excludes confirmatory-touching development "
            "molecules"
        ),
        "stage_c_predictions_generated": (
            "0 when full MapLight is retained or 234480 when the selected "
            "deletion triggers stage C"
        ),
        "official_predictions_generated": (
            "the exact sum of completed stage manifests; strictly less than "
            "562752 when full MapLight is retained or strictly less than 797232 "
            "when the selected deletion triggers stage C"
        ),
        "official_prediction_rows_opened_for_scoring": (
            "2 * stage_a_predictions_generated plus "
            "stage_b_predictions_generated plus stage_c_predictions_generated: "
            "Stage A is opened for selection and terminal scoring, while Stage B "
            "and conditional Stage C are opened only for terminal scoring"
        ),
        "development_metric_evaluations": "1 complete frozen battery",
        "tutorial_metric_calls": "56 exactly",
        "maximum_tutorial_metric_calls": "80",
        "claims_consumed": "1",
    }
    assert accounting["prediction_count_erratum"] == {
        "parent_contract_labels": (
            "D-122 and D-133 label 562752 as a minimum total and 797232 as a "
            "maximum total by adding the 140688 stage-B upper bound."
        ),
        "corrected_interpretation": (
            "Both numbers are unattainable branch upper projections, not exact "
            "totals: the frozen active-fold logic requires positive "
            "confirmatory-touch exclusions for every non-primary Stage-B overlay. "
            "Exact official prediction accounting is therefore the authenticated "
            "sum of the completed stage manifests."
        ),
        "science_change": False,
        "mechanics_change": False,
        "selection_change": False,
    }
    assert "marks accounting_complete false" in accounting["failure_rule"]
    assert set(accounting["must_remain_zero"]) == {
        "confirmatory_truth_values_opened",
        "historical_row_level_artifacts_opened",
        "blinded_test_rows_opened",
        "tdi_rows_opened",
        "external_records_acquired",
        "submission_rows_generated",
        "official_metric_calls",
        "leaderboard_observations_used_for_selection",
        "live_uploads",
        "private_portal_observations_recorded",
    }


def test_supervision_staging_receipt_and_status_file_sets_are_frozen() -> None:
    publication = _load(CONTRACT)["supervision_and_publication"]
    assert publication["fixed_publication_staging_root"] == (
        "/home/zbos/cypshift-private/openadmet-2026/"
        ".g2-7h-maplight-robustness-terminal-staging"
    )
    assert publication["fixed_restricted_root"] == (
        "/home/zbos/cypshift-private/openadmet-2026/"
        ".g2-7g-maplight-robustness-development-attempt-1-restricted"
    )
    assert publication["fixed_attempt_root"] == (
        "/home/zbos/cypshift-private/openadmet-2026/"
        "g2-7g-maplight-robustness-development-attempt-1"
    )
    assert publication["fixed_final_terminal"] == (
        f"{publication['fixed_attempt_root']}/terminal"
    )
    assert publication["fixed_claim_staging_path"] == (
        f"{publication['fixed_attempt_root']}/.attempt-claim-staging"
    )
    assert "begins before claim consumption" in publication["supervised_boundary"]
    assert "canonical exception observation" in publication["post_supervision_seal"]
    assert (
        "missing or malformed exception observation after valid claim"
        in (publication["post_supervision_seal"])
    )
    assert "all use this same bounded seal" in publication["post_supervision_seal"]
    assert publication["post_supervision_seal_limits"] == {
        "maximum_terminal_bytes": 16_777_216,
        "maximum_attempt_receipt_bytes": 1_048_576,
        "maximum_wall_seconds": 5.0,
        "maximum_cpu_seconds": 5.0,
        "additional_official_or_baseline_opens": 0,
        "additional_model_fits": 0,
        "additional_predictions": 0,
        "additional_metric_evaluations": 0,
    }
    cumulative = publication["cumulative_resource_rule"]
    assert cumulative["parent_hard_limits"] == {
        "wall_seconds": 27_648.0,
        "cpu_seconds": 460_800.0,
        "storage_bytes": 51_200_000_000,
        "simultaneous_rss_bytes": 16_492_674_416,
        "gpu_hours": 0.0,
    }
    assert "full 5-second seal reservation" in cumulative["success_reservation"]
    assert "without widening D-125" in cumulative["success_reservation"]
    assert "accounting-incomplete FAILED terminal" in cumulative["failure_rule"]
    assert (
        "exactly one same-invocation minimal FAILED seal"
        in cumulative["seal_failure_rule"]
    )
    assert "publish no replacement terminal" in cumulative["seal_failure_rule"]
    assert "attempt_receipt.json" in publication["aggregate_receipt"]
    assert publication["status_specific_file_sets"] == {
        "scientific_success_or_rejection": [
            "attempt_receipt.json",
            "manifest.json",
            "primary_metrics.json",
            "robustness.json",
            "selection.json",
        ],
        "underpowered": [
            "attempt_receipt.json",
            "manifest.json",
            "preflight.json",
        ],
        "resource_or_failed": ["attempt_receipt.json", "manifest.json"],
    }
    assert "unlinked and never followed" in publication["cleanup"]
    assert "before attempt_claim.json" in publication["pre_consumption_failure"]
    assert (
        "require all five paths plus claim, receipt, and terminal absent"
        in (publication["pre_consumption_failure"])
    )
    assert (
        "same fixed claim and driver are never reinvoked"
        in publication["pre_consumption_failure"]
    )
    assert "fixed restricted root" in publication["pre_consumption_failure"]
    assert publication["final_attempt_file_set"] == [
        "attempt_claim.json",
        "terminal",
    ]
    assert (
        "only after a valid attempt_claim.json"
        in publication["final_attempt_file_set_precondition"]
    )
    assert publication["terminal_read_only"] is True
    assert publication["atomic_no_replace"] is True


def test_composite_acceptance_is_fixed_one_use_and_zero_official() -> None:
    contract = _load(CONTRACT)
    acceptance = contract["composite_acceptance"]
    assert (
        "fixed no-argument zero-official composite acceptance"
        in contract["acceptance_criterion"]
    )
    assert acceptance["driver_path"] == (
        "research/maplight-fixed/"
        "run_global_v2_maplight_robustness_official_orchestration_acceptance.py"
    )
    assert acceptance["focused_tests_path"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
    )
    assert acceptance["fixed_parent_root"] == "/tmp/cypshift-g2-7h"
    assert acceptance["fixed_work_root"] == (
        "/tmp/cypshift-g2-7h/official-orchestration-acceptance-attempt-1"
    )
    assert acceptance["attempts"] == 1
    for operation in ("retry", "resume", "move", "overwrite", "replacement"):
        assert acceptance[operation] is False
    assert acceptance["required_scenarios_per_order"] == [
        "scientific_success",
        "clean_underpowered",
        "scientific_rejection",
        "hard_wall_resource_abort",
        "ordinary_nonzero_failure",
        "pre_consumption_supervisor_failure",
    ]
    assert acceptance["scenario_orders"] == ["forward", "reverse"]
    assert len(acceptance["required_mechanics"]) == 11
    assert all(value == 0 for value in acceptance["forbidden_operations"].values())
    assert "creates no model-quality result" in acceptance["authority"]
    assert "no official execution authority" in acceptance["authority"]


def test_tracked_claim_remains_unmodified_unusable_and_authority_free() -> None:
    contract = _load(CONTRACT)
    claim = _load(CLAIM)
    parent = contract["immutable_parent_evidence"]["tracked_unconsumed_claim_v2"]
    assert _sha256(CLAIM) == parent["sha256"]
    assert claim["status"] == parent["required_status"]
    assert claim["maximum_consumptions"] == 1
    assert claim["consumptions"] == parent["required_consumptions"] == 0
    assert claim["usable"] is False
    future = {key: value for key, value in claim.items() if key.startswith("future_")}
    assert set(future) == set(
        contract["future_claim_derivation"]["fields_filled_in_one_private_derivative"]
    )
    assert len(future) == parent["required_future_null_fields"] == 5
    assert all(value is None for value in future.values())
    assert contract["future_claim_derivation"]["tracked_template_mutation"] is False
    assert all(value is False for value in claim["authority"].values())


def test_contract_milestone_has_zero_operations_and_no_execution_authority() -> None:
    contract = _load(CONTRACT)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert accounting["contract_tests_created"] == 1
    assert all(
        value == 0
        for key, value in accounting.items()
        if key not in {"contracts_created", "contract_tests_created"}
    )
    assert contract["current_authority"] == {
        "repair_contract_frozen": True,
        "repair_implementation": False,
        "composite_acceptance": False,
        "official_claim_consumption": False,
        "official_source_or_baseline_access": False,
        "development_fitting_or_scoring": False,
        "confirmatory_access": False,
        "blinded_test_access": False,
        "submission_generation": False,
        "live_upload": False,
    }


def test_fixed_roots_and_receipt_paths_are_disjoint_and_transition_safe() -> None:
    contract = _load(CONTRACT)
    acceptance = contract["composite_acceptance"]
    publication = contract["supervision_and_publication"]
    claim = _load(CLAIM)
    assert claim["fixed_roots"]["attempt_root"] == publication["fixed_attempt_root"]

    repair = contract["repair_surface"]
    assert Path(acceptance["fixed_parent_root"]).is_absolute()
    assert Path(acceptance["fixed_work_root"]).parent == Path(
        acceptance["fixed_parent_root"]
    )
    private_paths = {
        Path(publication["fixed_publication_staging_root"]),
        Path(publication["fixed_restricted_root"]),
        Path(publication["fixed_attempt_root"]),
        Path(publication["fixed_final_terminal"]),
        Path(publication["fixed_claim_staging_path"]),
    }
    assert all(path.is_absolute() for path in private_paths)
    assert Path(publication["fixed_final_terminal"]).parent == Path(
        publication["fixed_attempt_root"]
    )
    assert Path(publication["fixed_claim_staging_path"]).parent == Path(
        publication["fixed_attempt_root"]
    )
    assert Path(acceptance["acceptance_path"]) != Path(acceptance["rejection_path"])
    assert repair["new_acceptance_driver"] == acceptance["driver_path"]
    assert repair["new_focused_tests"] == acceptance["focused_tests_path"]
