from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NoReturn, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RECORD = BENCHMARK / "global_v2_maplight_robustness_official_underpowered.json"
RECORD_SCHEMA = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_official_underpowered.v1"
)
RECORD_SHA256 = "d52bee5e4ed4669c6db7e3061fc8aed8f55e81a0e4d3d17aca73e326df184a2d"

LIVE_SHA256 = {
    "benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_contract.json": (
        "ad9aef871ab06e5082568f20a9a6d293897924bdfeda2fb341685cffaa7a45af"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_bounded_execution_contract.json": (
        "55fafa1d9806ba3221c26b8cd71d077ad61a0f485e51defbae21cbd4b5806527"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_execution_contract_v2.json": (
        "9464b0947255298a8de8836af6178857841bb2a55bc5c0f4897be2ba91151bcf"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_execution_claim_v2.json": (
        "d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_execution_acceptance_v2.json": (
        "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_focused_test_provenance_bridge.json": (
        "2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_repair_contract.json": (
        "f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_seal_erratum.json": (
        "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_"
    "test_transition_contract.json": (
        "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_"
    "source_shape_transition_contract.json": (
        "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_acceptance.json": (
        "92a18f0e6837d70d4bb39560d42a22cfb23acac8ea72a955b9656b392d954596"
    ),
    "research/maplight-fixed/global_v2_maplight_runner.py": (
        "154f8d231c490da7d2af419bfb533ec18a17c2d4ec3938c0373995a3a9acb93f"
    ),
    "research/maplight-fixed/global_v2_maplight_robustness_execution_wrapper.py": (
        "a6e02c244d6bd1b7bcb020dcf9627f68d453ae25827527e6de9acdaa30226c66"
    ),
    "research/maplight-fixed/global_v2_maplight_resource_supervisor.py": (
        "0d7b016b638fb4019eb377328f63a193d23fd6763540a636bd821cbabed63cec"
    ),
    "research/maplight-fixed/global_v2_maplight_robustness_execution_compiler.py": (
        "029afd827e3a86718e7e2493594bbc6e6ed78e258534221e32acc2027ace72a7"
    ),
    "research/maplight-fixed/global_v2_maplight_robustness_scientific_runner.py": (
        "dca9b8d1be51a29fa4e2269949d1f3339ecf14d99b91f203aa2cacdd2ca90bde"
    ),
    "research/maplight-fixed/global_v2_maplight_robustness_scoring_compiler.py": (
        "6f15205fccb4a7c2e1cc2c7244e31acf15d7fd34b285c85145bfde551da6f492"
    ),
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
    "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_acceptance_record.py": (
        "10ebb8f18d38f6d069e35d3994468e6a70dc0de3df6cb5736352721be439a28c"
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


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_official_underpowered_record_is_public_aggregate_and_terminal() -> None:
    raw = RECORD.read_bytes()
    record = cast(
        dict[str, Any],
        json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        ),
    )

    assert hashlib.sha256(raw).hexdigest() == RECORD_SHA256
    assert raw == _canonical_bytes(record)
    assert set(record) == {
        "accounting",
        "artifact_receipts",
        "attempt",
        "cleanup",
        "contract_interpretation",
        "decision",
        "failure",
        "freeze_date",
        "future_authority_created",
        "implementation_lineage",
        "privacy",
        "recorded_at_utc",
        "resource",
        "schema_version",
        "scientific_result",
        "status",
        "support_summary",
        "terminal",
        "terminal_published_at_utc",
        "tracked_public_claim_template",
    }
    assert record["schema_version"] == RECORD_SCHEMA
    assert record["status"] == "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED"
    assert record["decision"] == (
        "close_g2_7g_underpowered_without_selection_retry_or_model_quality_claim"
    )
    assert record["freeze_date"] == "2026-08-27"
    assert record["recorded_at_utc"] == "2026-08-27T21:37:14Z"
    assert record["terminal_published_at_utc"] == "2026-08-27T21:28:05Z"
    assert all("/home/" not in item for item in _strings(record))
    assert all("cypshift-private" not in item for item in _strings(record))

    for relative_path, expected_sha256 in LIVE_SHA256.items():
        assert _sha256(ROOT / relative_path) == expected_sha256

    assert record["tracked_public_claim_template"] == {
        "bytes_unchanged": True,
        "consumptions": 0,
        "maximum_consumptions": 1,
        "sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_claim_v2.json"
        ],
        "status": "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED",
        "usable": False,
    }

    expected_science_kernel = {
        "maplight_runner": LIVE_SHA256[
            "research/maplight-fixed/global_v2_maplight_runner.py"
        ],
        "no_fit_wrapper": LIVE_SHA256[
            "research/maplight-fixed/global_v2_maplight_robustness_execution_wrapper.py"
        ],
        "resource_supervisor": LIVE_SHA256[
            "research/maplight-fixed/global_v2_maplight_resource_supervisor.py"
        ],
        "robustness_compiler": LIVE_SHA256[
            "research/maplight-fixed/"
            "global_v2_maplight_robustness_execution_compiler.py"
        ],
        "scientific_runner": LIVE_SHA256[
            "research/maplight-fixed/global_v2_maplight_robustness_scientific_runner.py"
        ],
        "scoring_compiler": LIVE_SHA256[
            "research/maplight-fixed/global_v2_maplight_robustness_scoring_compiler.py"
        ],
    }
    assert record["implementation_lineage"] == {
        "composite_acceptance_driver_sha256": LIVE_SHA256[
            "research/maplight-fixed/"
            "run_global_v2_maplight_robustness_official_orchestration_acceptance.py"
        ],
        "composite_acceptance_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_acceptance.json"
        ],
        "corrected_execution_contract_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_contract_v2.json"
        ],
        "corrected_official_driver_sha256": LIVE_SHA256[
            "research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py"
        ],
        "d122_scientific_contract_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_contract.json"
        ],
        "d135_science_kernel_acceptance_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_acceptance_v2.json"
        ],
        "d136_focused_test_provenance_bridge_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
        ],
        "d137_repair_contract_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_"
            "repair_contract.json"
        ],
        "d138_seal_erratum_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_"
            "seal_erratum.json"
        ],
        "d139_test_transition_contract_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_"
            "test_transition_contract.json"
        ],
        "d140_source_shape_transition_contract_sha256": LIVE_SHA256[
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_orchestration_"
            "source_shape_transition_contract.json"
        ],
        "d142_post_main_ci_run": 33116954304,
        "d142_signed_commit": "d70d817dd2d7e30f63f6066dfbfdc4cef7e02bd3",
        "d142_standalone_receipt_audit_sha256": LIVE_SHA256[
            "tests/test_openadmet_global_v2_maplight_robustness_"
            "official_orchestration_acceptance_record.py"
        ],
        "historical_official_driver_sha256": (
            "1675336e449ba9a8327406cb37f82f08e3547076ce6c69fa0ade70c5a3de57fc"
        ),
        "immutable_science_kernel_source_sha256": expected_science_kernel,
        "orchestration_focused_tests_sha256": LIVE_SHA256[
            "tests/"
            "test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
        ],
    }

    assert record["artifact_receipts"] == {
        "attempt_claim": {
            "mode": "0444",
            "sha256": (
                "49969b0ed752bde27da5dc267b1562e06ad415d26fb178231caea5099ea0c713"
            ),
            "size_bytes": 5174,
        },
        "attempt_receipt": {
            "mode": "0444",
            "sha256": (
                "2a2955974d51dd1ec733066761dd08cedec343946fae38637fcf1b2a49a26f18"
            ),
            "size_bytes": 5646,
        },
        "manifest": {
            "mode": "0444",
            "sha256": (
                "c0672611c7b8415e2660546804c15e70695443fdfb17221069ddbebbacb1421e"
            ),
            "size_bytes": 3958,
        },
        "preflight": {
            "mode": "0444",
            "sha256": (
                "5d7fb00c90f4637ea3957bbd289a3a731f8dcf75add09f7319e1f2959cd94d79"
            ),
            "size_bytes": 22322,
        },
    }
    assert record["attempt"] == {
        "claim_id": "g2-7g-maplight-robustness-development-attempt-1",
        "consumptions": 1,
        "maximum_consumptions": 1,
        "official_attempts_completed": 1,
        "usable": False,
    }
    assert record["terminal"] == {
        "accounting_complete": True,
        "attempt_file_set": ["attempt_claim.json", "terminal"],
        "attempt_root_mode": "0555",
        "fit_counts": {"stage_a": 0, "stage_b": 0, "stage_c": 0},
        "prediction_counts": {"stage_a": 0, "stage_b": 0, "stage_c": 0},
        "runner_ups": 0,
        "selected_candidate": None,
        "selection_tokens": 0,
        "synthetic": False,
        "terminal_file_set": [
            "attempt_receipt.json",
            "manifest.json",
            "preflight.json",
        ],
        "terminal_root_mode": "0555",
        "tutorial_metric_calls": 0,
    }
    assert record["failure"] == {
        "category": "confirmatory_touch_not_exercised",
        "count": 1,
        "preflight_status": "G2_7C_NO_FIT_UNDERPOWERED",
        "reason": "TAUTOMER_MERGED:confirmatory_touch_not_exercised",
        "stage": "no_fit_support_preflight",
    }
    assert record["support_summary"] == {
        "numeric_minima": {
            "development_finite_targets_per_endpoint": 750,
            "outer_training_targets_per_endpoint_repeat_fold": 400,
            "outer_validation_targets_per_endpoint_repeat_fold": 75,
        },
        "numeric_support_minima_passed": True,
        "support_cells_checked": 240,
    }

    assert record["accounting"] == {
        "blinded_test_rows_opened": 0,
        "claims_consumed": 1,
        "claims_created": 0,
        "confirmatory_truth_values_opened": 0,
        "development_metric_evaluations": 0,
        "external_records_acquired": 0,
        "historical_row_level_artifacts_opened": 0,
        "leaderboard_observations_used_for_selection": 0,
        "live_uploads": 0,
        "maximum_tutorial_metric_calls": 80,
        "model_double_invocations": 0,
        "official_all_feature_rows_opened": 24525,
        "official_all_fold_rows_opened": 73575,
        "official_baseline_rows_opened": 0,
        "official_feature_identity_rows_opened": 4905,
        "official_feature_matrix_rows_opened": 19620,
        "official_feature_rows_opened": 24525,
        "official_generated_model_feature_rows_opened": 0,
        "official_generated_model_fold_rows_opened": 0,
        "official_group_fold_rows_opened": 73575,
        "official_metric_calls": 0,
        "official_model_fits": 0,
        "official_prediction_rows_opened_for_scoring": 0,
        "official_predictions_generated": 0,
        "official_reported_bound_values_opened": 0,
        "official_scoring_truth_values_opened": 0,
        "official_source_rows_opened": 19620,
        "official_source_target_values_opened": 5197,
        "official_target_values_opened": 5197,
        "official_training_target_values_opened": 0,
        "private_portal_observations_recorded": 0,
        "real_catboost_controls": 0,
        "stage_a_predictions_generated": 0,
        "stage_b_predictions_generated": 0,
        "stage_c_predictions_generated": 0,
        "submission_rows_generated": 0,
        "synthetic_model_fits": 0,
        "synthetic_predictions_generated": 0,
        "tdi_rows_opened": 0,
        "tutorial_metric_calls": 0,
    }

    assert record["resource"] == {
        "fallback_used": False,
        "limits": {
            "cpu_seconds": 460800.0,
            "gpu_hours": 0.0,
            "rss_bytes": 16492674416,
            "storage_bytes": 51200000000,
            "wall_seconds": 27647.999999999996,
        },
        "observation": {
            "checkpoints_acknowledged": 3,
            "cleanup_complete": True,
            "cpu_seconds": 33.194318974000005,
            "descendant_processes_observed": 2,
            "detached_children_observed": 0,
            "gpu_environment_hidden": True,
            "gpu_hours": 0.0,
            "network_namespace_isolated": True,
            "peak_simultaneous_rss_bytes": 289660928,
            "peak_storage_bytes": 8192,
            "return_code": 0,
            "wall_seconds": 33.09143570300148,
            "warnings_observed": 0,
        },
        "seal_attempts": 1,
        "within_limits": True,
    }
    resource = cast(dict[str, Any], record["resource"])
    limits = cast(dict[str, float], resource["limits"])
    observation = cast(dict[str, float], resource["observation"])
    assert observation["wall_seconds"] <= limits["wall_seconds"]
    assert observation["cpu_seconds"] <= limits["cpu_seconds"]
    assert observation["peak_storage_bytes"] <= limits["storage_bytes"]
    assert observation["peak_simultaneous_rss_bytes"] <= limits["rss_bytes"]
    assert observation["gpu_hours"] == limits["gpu_hours"] == 0.0

    assert record["cleanup"] == {
        "attempt_root_retained": True,
        "claim_staging_retained": False,
        "cleanup_complete": True,
        "composite_temporary_root_retained": False,
        "final_terminal_retained": True,
        "matching_processes_after_terminal": 0,
        "pending_terminal_retained": False,
        "publication_staging_retained": False,
        "restricted_root_retained": False,
        "supervision_complete_before_publication": True,
    }
    assert record["privacy"] == {
        "absolute_private_paths_retained": 0,
        "model_binaries_retained": 0,
        "official_source_or_baseline_bytes_copied": 0,
        "private_portal_observations_retained": 0,
        "row_level_values_retained": 0,
        "support_table_rows_retained": 0,
        "unrestricted_logs_retained": 0,
    }
    assert record["future_authority_created"] == {
        "blinded_test_access": False,
        "confirmatory_truth_access": False,
        "credential_use": False,
        "external_record_acquisition": False,
        "full_training": False,
        "leaderboard_selection": False,
        "live_upload": False,
        "model_quality": False,
        "official_metric_evaluation": False,
        "portal_access": False,
        "submission_generation": False,
        "tdi_access": False,
        "validator_execution": False,
    }
    assert record["scientific_result"] == {
        "best_validated_system": "fixed MapLight",
        "best_validated_system_changed": False,
        "full_maplight_selected_by_this_attempt": False,
        "internal_development_component_macro_mae": 0.5837812652150708,
        "model_quality_result": None,
        "robustness_validated": False,
    }

    assert record["contract_interpretation"] == {
        "confirmatory_authorized": False,
        "full_maplight_retained_by_default_rule": False,
        "model_quality_evidence_created": False,
        "new_selection_token_issued": False,
        "next_gate": (
            "Integrate D-143 evidence, then stop: no G2-8, confirmatory evaluation, "
            "or submission is authorized. Only a genuinely new prospective "
            "human-authorized hypothesis and contract could reopen planning, never "
            "a retry, repair, relaxation, replacement, or automatic full-MapLight "
            "retention."
        ),
        "no_runner_up": True,
        "official_attempt_consumed": True,
        "outcome_driven_repair_authorized": False,
        "pre_attempt_default_candidate": "G2-7-M0-FULL",
        "retry_or_resume_authorized": False,
        "scientific_path_terminal": True,
        "selected_candidate": None,
        "underpowered_rule": (
            "A support-preflight miss publishes aggregate underpowered evidence, "
            "selects or retains no contender, and cannot move a component or open "
            "confirmatory truth."
        ),
    }

    bounded_contract = cast(
        dict[str, Any],
        json.loads(
            (
                BENCHMARK
                / "global_v2_maplight_robustness_bounded_execution_contract.json"
            ).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        ),
    )
    assert bounded_contract["terminal_contract"]["failure_effect"] == (
        "Any underpowered, scientific rejection, resource abort, or failure closes "
        "this attempt without confirmatory access, runner-up, retry, repair, or "
        "replacement. Fixed MapLight remains historical baseline evidence but is "
        "not automatically promoted through the failed gate."
    )
    scientific_contract = cast(
        dict[str, Any],
        json.loads(
            (BENCHMARK / "global_v2_maplight_robustness_contract.json").read_text(
                encoding="utf-8"
            ),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        ),
    )
    assert (
        scientific_contract["confirmatory_boundary"]["maximum_confirmatory_scores"] == 0
    )
