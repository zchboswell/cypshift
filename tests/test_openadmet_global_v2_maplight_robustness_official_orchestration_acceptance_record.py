from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, NoReturn, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
ACCEPTANCE = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_acceptance.json"
)
ACCEPTANCE_SHA256 = "92a18f0e6837d70d4bb39560d42a22cfb23acac8ea72a955b9656b392d954596"

LIVE_SHA256 = {
    # D-141 implementation and collection transition.
    "research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py": (
        "feab960a54dd5ff818e29d062ad8eba48538658fe38a75d01f7c76f3d2daf103"
    ),
    "research/maplight-fixed/"
    "run_global_v2_maplight_robustness_official_orchestration_acceptance.py": (
        "3e209b88df7634f47884ce45653673a5407310575146392a77811fb4ed67ba9f"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py": (
        "f17b5b2f39b92892b046f289d6ebdb1888d705ea7a27ea24b3ca3013d39289b0"
    ),
    "tests/conftest.py": (
        "03d92bf3a2890a61190a6a4fc7a6bc59fa900ed6ea4b904223b1f2f991699d95"
    ),
    # D-137 through D-140 frozen parent contracts and their tests.
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_repair_contract.json": (
        "f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_contract.py": (
        "814675f28c637b30a7d8eea3bf275ee28e39694f1b33127403e95f261490f9c9"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_seal_erratum.json": (
        "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_seal_erratum.py": (
        "de7aafde522d0c9c61cc2e6f9747a0a577cd9c4b7b8e2b5896b0a6e32ba3f13b"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_"
    "test_transition_contract.json": (
        "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_test_transition_contract.py": (
        "185555b254acdbd13d0b6424ca074b8ba9096e877bcd636a2f0b22b1a0df90a0"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_"
    "source_shape_transition_contract.json": (
        "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_source_shape_transition_contract.py": (
        "35bcb0958bc66c386b82ab13171b453c6f60fde81dcb40d329a2f9b659c67da6"
    ),
    # D-135 immutable science acceptance and D-136 provenance bridge.
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_execution_acceptance_v2.json": (
        "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_focused_test_provenance_bridge.json": (
        "2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3"
    ),
}

SCIENCE_KERNEL_SHA256 = {
    "maplight_runner": (
        "research/maplight-fixed/global_v2_maplight_runner.py",
        "154f8d231c490da7d2af419bfb533ec18a17c2d4ec3938c0373995a3a9acb93f",
    ),
    "no_fit_wrapper": (
        "research/maplight-fixed/global_v2_maplight_robustness_execution_wrapper.py",
        "a6e02c244d6bd1b7bcb020dcf9627f68d453ae25827527e6de9acdaa30226c66",
    ),
    "resource_supervisor": (
        "research/maplight-fixed/global_v2_maplight_resource_supervisor.py",
        "0d7b016b638fb4019eb377328f63a193d23fd6763540a636bd821cbabed63cec",
    ),
    "robustness_compiler": (
        "research/maplight-fixed/global_v2_maplight_robustness_execution_compiler.py",
        "029afd827e3a86718e7e2493594bbc6e6ed78e258534221e32acc2027ace72a7",
    ),
    "scientific_runner": (
        "research/maplight-fixed/global_v2_maplight_robustness_scientific_runner.py",
        "dca9b8d1be51a29fa4e2269949d1f3339ecf14d99b91f203aa2cacdd2ca90bde",
    ),
    "scoring_compiler": (
        "research/maplight-fixed/global_v2_maplight_robustness_scoring_compiler.py",
        "6f15205fccb4a7c2e1cc2c7244e31acf15d7fd34b285c85145bfde551da6f492",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_nonfinite(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def test_formal_orchestration_acceptance_record_is_exact_and_static() -> None:
    raw = ACCEPTANCE.read_bytes()
    receipt = cast(
        dict[str, Any],
        json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        ),
    )
    assert hashlib.sha256(raw).hexdigest() == ACCEPTANCE_SHA256
    assert raw == _canonical_bytes(receipt)

    for relative_path, expected_sha256 in LIVE_SHA256.items():
        assert _sha256(ROOT / relative_path) == expected_sha256

    expected_science_kernel = {
        name: expected_sha256
        for name, (_relative_path, expected_sha256) in SCIENCE_KERNEL_SHA256.items()
    }
    for relative_path, expected_sha256 in SCIENCE_KERNEL_SHA256.values():
        assert _sha256(ROOT / relative_path) == expected_sha256

    assert receipt["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v2_maplight_robustness_official_orchestration_acceptance.v1"
    )
    assert receipt["status"] == (
        "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_ACCEPTED"
    )
    assert receipt["attempt_id"] == (
        "g2-7h-official-orchestration-acceptance-attempt-1"
    )
    assert (
        receipt["repair_contract_sha256"]
        == LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_repair_contract.json"
        ]
    )
    assert (
        receipt["seal_erratum_sha256"]
        == LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_seal_erratum.json"
        ]
    )
    assert (
        receipt["d139_test_transition_contract_sha256"]
        == LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_"
            "test_transition_contract.json"
        ]
    )
    assert (
        receipt["d140_source_shape_transition_contract_sha256"]
        == LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_"
            "source_shape_transition_contract.json"
        ]
    )
    assert (
        receipt["d135_science_kernel_acceptance_sha256"]
        == LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_acceptance_v2.json"
        ]
    )
    assert (
        receipt["d136_focused_test_provenance_bridge_sha256"]
        == LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
        ]
    )
    assert (
        receipt["corrected_official_attempt_driver_source_sha256"]
        == LIVE_SHA256[
            "research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py"
        ]
    )
    assert (
        receipt["official_orchestration_acceptance_driver_source_sha256"]
        == LIVE_SHA256[
            "research/maplight-fixed/"
            "run_global_v2_maplight_robustness_official_orchestration_acceptance.py"
        ]
    )
    assert (
        receipt["focused_tests_sha256"]
        == LIVE_SHA256[
            "tests/"
            "test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
        ]
    )
    assert receipt["immutable_science_kernel_source_sha256"] == (
        expected_science_kernel
    )
    assert receipt["d135_science_kernel_evidence"] == {
        "model_double_invocations": 3480,
        "real_catboost_fits": 2,
        "reexecuted": False,
        "synthetic_predictions_generated": 667872,
    }

    scenarios = [
        "scientific_success",
        "clean_underpowered",
        "scientific_rejection",
        "hard_wall_resource_abort",
        "ordinary_nonzero_failure",
        "pre_consumption_supervisor_failure",
    ]
    assert receipt["scenario_orders"] == ["forward", "reverse"]
    assert receipt["required_scenarios"] == scenarios
    assert receipt["scenario_invocations"] == 12
    assert receipt["supervisor_invocations"] == 12
    assert receipt["statuses_reached"] == [
        "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED",
        "G2_7_MAPLIGHT_ROBUSTNESS_FAILED",
        "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
        "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED",
        "G2_7_PRIMARY_CONTENDER_FROZEN",
    ]

    roots = cast(list[dict[str, Any]], receipt["roots"])
    assert len(roots) == 2
    assert [root["order"] for root in roots] == ["forward", "reverse"]
    assert roots[0]["scenario_execution_order"] == scenarios
    assert roots[1]["scenario_execution_order"] == list(reversed(scenarios))
    first_map = cast(dict[str, dict[str, Any]], roots[0]["normalized_result_map"])
    second_map = cast(dict[str, dict[str, Any]], roots[1]["normalized_result_map"])
    assert set(first_map) == set(scenarios)
    assert receipt["opposite_order_maps_byte_identical"] is True
    assert first_map == second_map
    assert _canonical_bytes(first_map) == _canonical_bytes(second_map)

    expected_scenario_shape = {
        "scientific_success": {
            "status": "G2_7_PRIMARY_CONTENDER_FROZEN",
            "accounting_complete": True,
            "file_set": [
                "attempt_receipt.json",
                "manifest.json",
                "primary_metrics.json",
                "robustness.json",
                "selection.json",
            ],
            "terminal_read_only": True,
            "failure_category": None,
            "fit_counts": {"stage_a": 540, "stage_b": 180, "stage_c": 0},
            "prediction_counts": {
                "stage_a": 422064,
                "stage_b": 140580,
                "stage_c": 0,
            },
            "selection_tokens": 1,
            "runner_ups": 0,
            "tutorial_metric_calls": 56,
        },
        "clean_underpowered": {
            "status": "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED",
            "accounting_complete": True,
            "file_set": [
                "attempt_receipt.json",
                "manifest.json",
                "preflight.json",
            ],
            "terminal_read_only": True,
            "failure_category": None,
            "fit_counts": {"stage_a": 0, "stage_b": 0, "stage_c": 0},
            "prediction_counts": {"stage_a": 0, "stage_b": 0, "stage_c": 0},
            "selection_tokens": 0,
            "runner_ups": 0,
            "tutorial_metric_calls": 0,
        },
        "scientific_rejection": {
            "status": "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
            "accounting_complete": True,
            "file_set": [
                "attempt_receipt.json",
                "manifest.json",
                "primary_metrics.json",
                "robustness.json",
                "selection.json",
            ],
            "terminal_read_only": True,
            "failure_category": None,
            "fit_counts": {"stage_a": 540, "stage_b": 180, "stage_c": 300},
            "prediction_counts": {
                "stage_a": 422064,
                "stage_b": 140580,
                "stage_c": 234480,
            },
            "selection_tokens": 1,
            "runner_ups": 0,
            "tutorial_metric_calls": 56,
        },
        "hard_wall_resource_abort": {
            "status": "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED",
            "accounting_complete": False,
            "file_set": ["attempt_receipt.json", "manifest.json"],
            "terminal_read_only": True,
            "failure_category": "hard_resource_limit",
            "fit_counts": None,
            "prediction_counts": None,
            "selection_tokens": None,
            "runner_ups": None,
            "tutorial_metric_calls": None,
        },
        "ordinary_nonzero_failure": {
            "status": "G2_7_MAPLIGHT_ROBUSTNESS_FAILED",
            "accounting_complete": False,
            "file_set": ["attempt_receipt.json", "manifest.json"],
            "terminal_read_only": True,
            "failure_category": "supervised_process_nonzero",
            "fit_counts": None,
            "prediction_counts": None,
            "selection_tokens": None,
            "runner_ups": None,
            "tutorial_metric_calls": None,
        },
        "pre_consumption_supervisor_failure": {
            "status": "PRE_CONSUMPTION_FAILURE_PROPAGATED",
            "accounting_complete": False,
            "file_set": [],
            "terminal_read_only": False,
            "failure_category": None,
            "fit_counts": None,
            "prediction_counts": None,
            "selection_tokens": None,
            "runner_ups": None,
            "tutorial_metric_calls": None,
        },
    }
    shape_fields = tuple(next(iter(expected_scenario_shape.values())))
    for scenario, expected in expected_scenario_shape.items():
        observed = first_map[scenario]
        assert observed["aggregate_only"] is True
        assert observed["cleanup_complete"] is True
        assert {field: observed.get(field) for field in shape_fields} == expected

    expected_accounting = {
        "scientific_success": {
            "claims_consumed": 1,
            "development_metric_evaluations": 1,
            "official_model_fits": 720,
            "official_predictions_generated": 562644,
            "stage_a_predictions_generated": 422064,
            "stage_b_predictions_generated": 140580,
            "stage_c_predictions_generated": 0,
            "tutorial_metric_calls": 56,
        },
        "clean_underpowered": {
            "claims_consumed": 1,
            "development_metric_evaluations": 0,
            "official_model_fits": 0,
            "official_predictions_generated": 0,
            "stage_a_predictions_generated": 0,
            "stage_b_predictions_generated": 0,
            "stage_c_predictions_generated": 0,
            "tutorial_metric_calls": 0,
        },
        "scientific_rejection": {
            "claims_consumed": 1,
            "development_metric_evaluations": 1,
            "official_model_fits": 1020,
            "official_predictions_generated": 797124,
            "stage_a_predictions_generated": 422064,
            "stage_b_predictions_generated": 140580,
            "stage_c_predictions_generated": 234480,
            "tutorial_metric_calls": 56,
        },
    }
    privacy_accounting_fields = {
        "blinded_test_rows_opened",
        "claims_created",
        "confirmatory_truth_values_opened",
        "external_records_acquired",
        "historical_row_level_artifacts_opened",
        "leaderboard_observations_used_for_selection",
        "live_uploads",
        "model_double_invocations",
        "official_metric_calls",
        "private_portal_observations_recorded",
        "real_catboost_controls",
        "submission_rows_generated",
        "synthetic_model_fits",
        "synthetic_predictions_generated",
        "tdi_rows_opened",
    }
    for scenario, expected in expected_accounting.items():
        accounting = cast(dict[str, Any], first_map[scenario]["accounting"])
        assert {key: accounting[key] for key in expected} == expected
        assert all(accounting[key] == 0 for key in privacy_accounting_fields)
    for scenario in (
        "hard_wall_resource_abort",
        "ordinary_nonzero_failure",
        "pre_consumption_supervisor_failure",
    ):
        assert first_map[scenario].get("accounting") is None

    receipt_authority = {
        "blinded_test_access": False,
        "confirmatory_truth_access": False,
        "external_record_acquisition": False,
        "leaderboard_observation": False,
        "live_upload": False,
        "official_feature_access": False,
        "official_metric_evaluation": False,
        "official_model_fitting": False,
        "official_prediction_generation": False,
        "official_target_access": False,
        "submission_generation": False,
        "tdi_access": False,
    }
    expected_lineage = {
        "composite_acceptance_driver_sha256": receipt[
            "official_orchestration_acceptance_driver_source_sha256"
        ],
        "composite_acceptance_sha256": receipt[
            "synthetic_composite_lineage_fixture_sha256"
        ],
        "corrected_official_driver_sha256": receipt[
            "corrected_official_attempt_driver_source_sha256"
        ],
        "d135_science_kernel_acceptance_sha256": receipt[
            "d135_science_kernel_acceptance_sha256"
        ],
        "d136_focused_test_provenance_bridge_sha256": receipt[
            "d136_focused_test_provenance_bridge_sha256"
        ],
        "d137_repair_contract_sha256": receipt["repair_contract_sha256"],
        "d138_seal_erratum_sha256": receipt["seal_erratum_sha256"],
        "d139_test_transition_contract_sha256": receipt[
            "d139_test_transition_contract_sha256"
        ],
        "d140_source_shape_transition_contract_sha256": receipt[
            "d140_source_shape_transition_contract_sha256"
        ],
        "historical_official_driver_sha256": receipt[
            "historical_official_attempt_driver_source_sha256"
        ],
        "immutable_science_kernel_source_sha256": expected_science_kernel,
        "orchestration_focused_tests_sha256": receipt["focused_tests_sha256"],
    }
    consumed_scenarios = set(scenarios) - {"pre_consumption_supervisor_failure"}
    expected_return_codes = {
        "scientific_success": 0,
        "clean_underpowered": 0,
        "scientific_rejection": 0,
        "hard_wall_resource_abort": -15,
        "ordinary_nonzero_failure": 7,
    }
    observation_fields = {
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
    }
    for scenario in consumed_scenarios:
        observed = first_map[scenario]
        assert observed["receipt_status"] == observed["status"]
        assert observed["receipt_cleanup_complete"] is True
        assert observed["receipt_fallback_used"] is False
        assert observed["receipt_seal_attempts"] == 1
        assert observed["receipt_authority"] == receipt_authority
        assert observed["receipt_implementation_lineage"] == expected_lineage
        supervision = observed["cumulative_supervision"]
        assert set(supervision) == observation_fields
        assert supervision["return_code"] == expected_return_codes[scenario]
        assert supervision["cleanup_complete"] is True
        assert supervision["network_namespace_isolated"] is True
        assert supervision["gpu_environment_hidden"] is True
        assert supervision["gpu_hours"] == 0.0
        assert supervision["detached_children_observed"] == 0
        assert supervision["warnings_observed"] == 0
    pre_consumption = first_map["pre_consumption_supervisor_failure"]
    assert pre_consumption["cumulative_supervision"] is None
    assert pre_consumption["receipt_authority"] is None
    assert pre_consumption["receipt_status"] is None

    assert receipt["mechanics"] == {
        "atomic_claim_publication": True,
        "atomic_promote_then_readonly_root": True,
        "bounded_common_seal_and_collision_fail_closed": True,
        "five_status_taxonomy": True,
        "hard_resource_vs_ordinary_failure": True,
        "inherited_scientific_payload_semantics": True,
        "opposite_order_map_identity": True,
        "pre_consumption_fail_closed": True,
        "strict_observation_round_trip": True,
        "symlink_safe_owned_root_cleanup": True,
        "underpowered_zero_science": True,
    }
    assert receipt["mechanics_probe_counts"] == {
        "atomic_claim_interruptions": 1,
        "exact_underpowered_catches": 1,
        "final_terminal_collisions": 1,
        "ordinary_compiler_failure_propagations": 1,
        "ordinary_seal_fallbacks": 1,
        "post_promotion_identity_substitutions": 1,
        "promotion_errors": 1,
        "resource_seal_fallbacks": 1,
        "shared_budget_exhaustions": 1,
        "underpowered_subclass_propagations": 1,
    }
    assert receipt["synthetic_fixture_claim_publications"] == 10
    assert receipt["synthetic_scenario_claim_publications"] == 10
    assert receipt["synthetic_probe_claim_publications"] == 6
    assert receipt["synthetic_interrupted_claim_stagings"] == 1
    assert receipt["exact_underpowered_catch_verified"] is True
    assert receipt["five_field_prepublication_derivation_verified"] is True

    assert receipt["cleanup_complete_before_publication"] is True
    assert receipt["private_roots_retained"] == 0
    assert receipt["forbidden_operations"] == {
        "blinded_test_rows_opened": 0,
        "claims_consumed": 0,
        "claims_created": 0,
        "confirmatory_truth_values_opened": 0,
        "development_metric_evaluations": 0,
        "external_records_acquired": 0,
        "historical_row_level_artifacts_opened": 0,
        "leaderboard_observations_used_for_selection": 0,
        "live_uploads": 0,
        "model_double_invocations": 0,
        "official_metric_calls": 0,
        "official_source_or_baseline_bytes_opened": 0,
        "predictions_generated": 0,
        "private_portal_observations_recorded": 0,
        "real_catboost_fits": 0,
        "submission_rows_generated": 0,
        "tdi_rows_opened": 0,
    }
    assert receipt["authority"] == {
        "blinded_test": False,
        "confirmatory": False,
        "live_upload": False,
        "model_quality": False,
        "official_claim_consumption": False,
        "official_execution": False,
        "submission_generation": False,
    }
    assert receipt["model_quality_authority"] is False
    assert receipt["official_execution_authority"] is False
    assert receipt["claim_authority"] is False
