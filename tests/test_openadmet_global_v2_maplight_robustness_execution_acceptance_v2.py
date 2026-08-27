from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RESEARCH = ROOT / "research" / "maplight-fixed"
ACCEPTANCE = BENCHMARK / "global_v2_maplight_robustness_execution_acceptance_v2.json"
CONTRACT = BENCHMARK / "global_v2_maplight_robustness_execution_contract_v2.json"
CLAIM = BENCHMARK / "global_v2_maplight_robustness_execution_claim_v2.json"
BRIDGE = BENCHMARK / "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
FOCUSED_TESTS = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
)
CONFTEST = ROOT / "tests/conftest.py"
ACCEPTANCE_SHA256 = "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390"
CLAIM_SHA256 = "d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_acceptance_binds_exact_contract_and_integrated_implementation() -> None:
    receipt = _load(ACCEPTANCE)
    assert _sha256(ACCEPTANCE) == ACCEPTANCE_SHA256
    assert receipt["schema_version"] == (
        "cypshift.openadmet_cyp_2026."
        "global_v2_maplight_robustness_execution_acceptance.v2"
    )
    assert receipt["status"] == "G2_7G_MAPLIGHT_ROBUSTNESS_EXECUTION_ACCEPTED"
    assert receipt["attempt_id"] == (
        "g2-7g-official-shaped-execution-acceptance-attempt-1"
    )
    assert receipt["contract_sha256"] == _sha256(CONTRACT)
    assert receipt["scientific_runner_source_sha256"] == _sha256(
        RESEARCH / "global_v2_maplight_robustness_scientific_runner.py"
    )
    assert receipt["official_attempt_driver_source_sha256"] == _sha256(
        RESEARCH / "run_global_v2_maplight_robustness_official_v2.py"
    )
    assert receipt["official_shaped_acceptance_driver_source_sha256"] == _sha256(
        RESEARCH / "run_global_v2_maplight_robustness_execution_acceptance_v2.py"
    )
    assert (
        receipt["focused_tests_sha256"]
        == _sha256(FOCUSED_TESTS)
        == ("3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f")
    )


def test_provenance_bridge_retires_only_the_obsolete_pre_acceptance_state() -> None:
    bridge = _load(BRIDGE)
    assert bridge["status"] == "G2_7G_FOCUSED_TEST_PROVENANCE_RECONCILED"
    assert bridge["parent_commit"] == ("7450676da651e86bab341c7434dd1b9dd2f19388")
    assert bridge["contract_sha256"] == _sha256(CONTRACT)
    assert bridge["tracked_claim_sha256"] == _sha256(CLAIM)
    assert bridge["formal_acceptance_sha256"] == _sha256(ACCEPTANCE)
    assert bridge["scientific_runner_sha256"] == _sha256(
        RESEARCH / "global_v2_maplight_robustness_scientific_runner.py"
    )
    assert bridge["official_driver_sha256"] == _sha256(
        RESEARCH / "run_global_v2_maplight_robustness_official_v2.py"
    )
    assert bridge["formal_acceptance_driver_sha256"] == _sha256(
        RESEARCH / "run_global_v2_maplight_robustness_execution_acceptance_v2.py"
    )
    assert bridge["formal_focused_tests_sha256"] == _sha256(FOCUSED_TESTS)
    assert bridge["d135_post_acceptance_state_tests_sha256"] == (
        "625f3ae0c8d61dc76775240606a2662d7b9b80b5ffe0c05344b9a587f0c6ca2b"
    )
    assert bridge["post_acceptance_audit_tests_sha256"] == _sha256(Path(__file__))
    assert bridge["pytest_transition_hook_sha256"] == _sha256(CONFTEST)
    assert bridge["retired_test_nodeid"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::"
        "test_formal_acceptance_is_fixed_unrun_and_has_zero_authority"
    )
    assert bridge["replacement_current_state_test"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::"
        "test_cumulative_supervision_cleanup_and_zero_authority_are_complete"
    )
    assert bridge["production_files_changed"] == 0
    assert bridge["formal_acceptance_attempts"] == 0
    assert bridge["official_operations"] == 0
    assert bridge["claims_created"] == bridge["claims_consumed"] == 0
    assert bridge["model_quality_authority"] is False


def test_claim_derivation_is_read_only_and_fills_exactly_five_receipts() -> None:
    before = CLAIM.read_bytes()
    sys.path.insert(0, str(RESEARCH))
    try:
        import run_global_v2_maplight_robustness_official_v2 as official
    finally:
        sys.path.remove(str(RESEARCH))

    assert not official.OFFICIAL_ATTEMPT_ROOT.exists()
    assert not official.RESTRICTED_ROOT.exists()
    consumed = official.derive_consumed_claim()
    template = cast(dict[str, Any], json.loads(before))
    future = {key for key in template if key.startswith("future_")}
    changed = {key for key in consumed if consumed.get(key) != template.get(key)}
    assert future == {
        "future_scientific_runner_source_sha256",
        "future_official_attempt_driver_source_sha256",
        "future_official_shaped_acceptance_driver_source_sha256",
        "future_official_shaped_execution_acceptance_sha256",
        "future_focused_tests_sha256",
    }
    assert changed == future | {"status", "consumptions"}
    assert consumed["status"] == "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_CONSUMED"
    assert consumed["consumptions"] == 1
    assert consumed["usable"] is False
    assert consumed["future_scientific_runner_source_sha256"] == _sha256(
        RESEARCH / "global_v2_maplight_robustness_scientific_runner.py"
    )
    assert consumed["future_official_attempt_driver_source_sha256"] == _sha256(
        RESEARCH / "run_global_v2_maplight_robustness_official_v2.py"
    )
    assert consumed[
        "future_official_shaped_acceptance_driver_source_sha256"
    ] == _sha256(
        RESEARCH / "run_global_v2_maplight_robustness_execution_acceptance_v2.py"
    )
    assert consumed["future_official_shaped_execution_acceptance_sha256"] == _sha256(
        ACCEPTANCE
    )
    assert consumed["future_focused_tests_sha256"] == _sha256(FOCUSED_TESTS)
    assert CLAIM.read_bytes() == before
    assert not official.OFFICIAL_ATTEMPT_ROOT.exists()
    assert not official.RESTRICTED_ROOT.exists()


def test_opposite_roots_cover_both_frozen_conditional_profiles() -> None:
    receipt = _load(ACCEPTANCE)
    assert receipt["opposite_physical_and_fit_order"] is True
    assert receipt["both_conditional_paths"] is True
    assert receipt["profiles_per_root"] == ["full_retained", "deletion_selected"]
    roots = receipt["roots"]
    assert len(roots) == 2
    assert [root["source_physical_order_reversed"] for root in roots] == [
        False,
        True,
    ]
    assert [root["fit_launch_order_reversed"] for root in roots] == [False, True]
    for root in roots:
        assert root["fit_counts"] == {
            "stage_a": 1080,
            "stage_b": 360,
            "stage_c": 300,
        }
        assert root["prediction_counts"] == {
            "stage_a": 207360,
            "stage_b": 68976,
            "stage_c": 57600,
        }
        full = root["profiles"]["full_retained"]
        deletion = root["profiles"]["deletion_selected"]
        assert full["selected_candidate"] == "G2-7-M0-FULL"
        assert full["fit_counts"] == {
            "stage_a": 540,
            "stage_b": 180,
            "stage_c": 0,
        }
        assert deletion["selected_candidate"] == "G2-7-M2-DROP-AVALON"
        assert deletion["fit_counts"] == {
            "stage_a": 540,
            "stage_b": 180,
            "stage_c": 300,
        }
    assert receipt["model_double_invocations"] == 3480
    assert receipt["synthetic_predictions_generated"] == 667872


def test_capability_and_aggregate_terminal_maps_are_order_invariant() -> None:
    receipt = _load(ACCEPTANCE)
    first, second = receipt["roots"]
    assert receipt["capability_maps_byte_identical"] is True
    assert receipt["terminal_maps_byte_identical"] is True
    assert first["model_capability_tree"] == second["model_capability_tree"]
    assert first["scoring_capability_tree"] == second["scoring_capability_tree"]
    assert first["terminal_tree"] == second["terminal_tree"]


def test_exactly_two_bounded_real_catboost_controls_are_finite() -> None:
    receipt = _load(ACCEPTANCE)
    assert receipt["real_catboost_fits"] == 2
    controls = receipt["real_catboost_controls"]
    assert controls == [
        {
            "candidate_id": "G2-7-M0-FULL",
            "feature_columns": 2563,
            "finite": True,
            "identity_sha256": (
                "5eead34d52a5e27e8d55d0f2fcee276ac0d603b0cb5cf12db4406cfc80be2e5f"
            ),
            "prediction_rows": 8,
            "random_seed": 1,
            "resolved_parameter_sha256": (
                "4708fb141bb465748f5fbb2dfcc39c7a107c870758a17ef3536a64e86d378493"
            ),
        },
        {
            "candidate_id": "G2-7-M1-DROP-MORGAN",
            "feature_columns": 1539,
            "finite": True,
            "identity_sha256": (
                "b0a80c2465d657533fa9c250f7155e04f8944574a4f9a82912003df975938cc5"
            ),
            "prediction_rows": 8,
            "random_seed": 2026082411,
            "resolved_parameter_sha256": (
                "3a67611f580af4790d66db0b0fd712af35a87b1a6e253064eb1178c5500cba02"
            ),
        },
    ]


def test_cumulative_supervision_cleanup_and_zero_authority_are_complete() -> None:
    receipt = _load(ACCEPTANCE)
    supervision = receipt["cumulative_supervision"]
    assert supervision["return_code"] == 0
    assert supervision["checkpoints_acknowledged"] == 6985
    assert supervision["descendant_processes_observed"] == 13
    assert supervision["cleanup_complete"] is True
    assert supervision["detached_children_observed"] == 0
    assert supervision["warnings_observed"] == 0
    assert supervision["network_namespace_isolated"] is True
    assert supervision["gpu_environment_hidden"] is True
    assert supervision["gpu_hours"] == 0.0
    assert supervision["wall_seconds"] < supervision["limits"]["wall_seconds"]
    assert supervision["cpu_seconds"] < supervision["limits"]["cpu_seconds"]
    assert (
        supervision["peak_simultaneous_rss_bytes"] < supervision["limits"]["rss_bytes"]
    )
    assert supervision["peak_storage_bytes"] < supervision["limits"]["storage_bytes"]
    assert receipt["cleanup_complete_before_publication"] is True
    assert receipt["private_roots_retained"] == 0
    assert receipt["official_operations"] == 0
    assert receipt["claims_created"] == receipt["claims_consumed"] == 0
    assert receipt["claim_authority"] is False
    assert receipt["model_quality_authority"] is False
    claim = _load(CLAIM)
    assert _sha256(CLAIM) == CLAIM_SHA256
    assert claim["status"] == "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
    assert claim["usable"] is False
    assert claim["consumptions"] == 0
    future_receipts = {
        key: value for key, value in claim.items() if key.startswith("future_")
    }
    assert len(future_receipts) == 5
    assert all(value is None for value in future_receipts.values())
