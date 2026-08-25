from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RESEARCH = ROOT / "research" / "maplight-fixed"
ACCEPTANCE = BENCHMARK / "global_v2_maplight_robustness_no_fit_acceptance.json"
REJECTION = BENCHMARK / "global_v2_maplight_robustness_no_fit_acceptance_rejection.json"
AUDIT_REJECTION = (
    BENCHMARK / "global_v2_maplight_robustness_no_fit_acceptance_audit_rejection.json"
)
CI_REJECTION = (
    BENCHMARK / "global_v2_maplight_robustness_no_fit_acceptance_ci_rejection.json"
)
CI_HOST_REJECTION = (
    BENCHMARK
    / "global_v2_maplight_robustness_no_fit_acceptance_ci_host_rejection.json"
)
EXPECTED_ACCEPTANCE_SHA256 = (
    "ca722b265f751ad6efe58017b0106fbca35be4ee04e46d129ed7e8a51c231e0e"
)
EXPECTED_REJECTION_SHA256 = (
    "8fb6aba95cae2aa93b1fa78fbdb998bf0b8e7b6f47dda6adfe4c54d2c85d0ce3"
)
EXPECTED_AUDIT_REJECTION_SHA256 = (
    "4e4c45ae722e06806295cf74a8e690e40ac71e6d580223106c8bbd73f563ec28"
)
EXPECTED_CI_REJECTION_SHA256 = (
    "93a8adeb9db9c2bb280d0cce862a7a570009d0dc8096161f195b5c0260e7669e"
)
EXPECTED_CI_HOST_REJECTION_SHA256 = (
    "37429202c0d7622fd51ade26e121c6fce6e6a0647f85ae19e7f06bce99e8f5b1"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_acceptance_and_prior_cleanup_rejection_are_exact() -> None:
    acceptance = _load(ACCEPTANCE)
    rejection = _load(REJECTION)
    audit_rejection = _load(AUDIT_REJECTION)
    ci_rejection = _load(CI_REJECTION)
    ci_host_rejection = _load(CI_HOST_REJECTION)
    assert _sha(ACCEPTANCE) == EXPECTED_ACCEPTANCE_SHA256
    assert _sha(REJECTION) == EXPECTED_REJECTION_SHA256
    assert _sha(AUDIT_REJECTION) == EXPECTED_AUDIT_REJECTION_SHA256
    assert _sha(CI_REJECTION) == EXPECTED_CI_REJECTION_SHA256
    assert _sha(CI_HOST_REJECTION) == EXPECTED_CI_HOST_REJECTION_SHA256
    assert acceptance["status"] == "G2_7C_MAPLIGHT_ROBUSTNESS_NO_FIT_ACCEPTED"
    assert acceptance["prior_cleanup_rejection_sha256"] == _sha(REJECTION)
    assert acceptance["prior_adapter_audit_rejection_sha256"] == _sha(AUDIT_REJECTION)
    assert acceptance["prior_integration_ci_rejection_sha256"] == _sha(CI_REJECTION)
    assert acceptance["prior_integration_ci_host_rejection_sha256"] == _sha(
        CI_HOST_REJECTION
    )
    assert rejection["status"] == (
        "G2_7C_MAPLIGHT_ROBUSTNESS_NO_FIT_ACCEPTANCE_REJECTED"
    )
    assert rejection["failure_stage"] == "POST_TERMINAL_CLEANUP"
    assert rejection["cleanup"]["private_roots_retained"] == 0
    assert audit_rejection["official_compiler_evidence_valid"] is False
    assert audit_rejection["generated_acceptance_authority"] is False
    assert ci_rejection["superseded_acceptance_sha256"] == (
        "5698f8781f21c95d226d300b02d893fe164773ade209925fbf215a8fe61f5683"
    )
    assert ci_host_rejection["superseded_acceptance_sha256"] == (
        "587eca16c911bdd96491b0bb8356f60b2217566fc7b139f2ac0ddc865c5f5b63"
    )


def test_acceptance_binds_every_final_implementation_source() -> None:
    acceptance = _load(ACCEPTANCE)
    paths = {
        "compiler_source_sha256": (
            RESEARCH / "global_v2_maplight_robustness_execution_compiler.py"
        ),
        "wrapper_source_sha256": (
            RESEARCH / "global_v2_maplight_robustness_execution_wrapper.py"
        ),
        "supervisor_source_sha256": (
            RESEARCH / "global_v2_maplight_resource_supervisor.py"
        ),
        "acceptance_driver_source_sha256": (
            RESEARCH / "run_global_v2_maplight_robustness_no_fit_acceptance.py"
        ),
        "focused_tests_sha256": (
            ROOT
            / "tests"
            / "test_openadmet_global_v2_maplight_robustness_bounded_execution.py"
        ),
    }
    for key, path in paths.items():
        assert acceptance[key] == _sha(path)
    assert acceptance["bounded_contract_sha256"] == _sha(
        BENCHMARK / "global_v2_maplight_robustness_bounded_execution_contract.json"
    )
    assert acceptance["parent_contract_sha256"] == _sha(
        BENCHMARK / "global_v2_maplight_robustness_contract.json"
    )


def test_opposite_order_roots_match_every_capability_and_terminal() -> None:
    acceptance = _load(ACCEPTANCE)
    roots = acceptance["roots"]
    assert len(roots) == 2
    assert roots[0]["source_physical_order_reversed"] is False
    assert roots[1]["source_physical_order_reversed"] is True
    assert roots[0]["source_manifest_sha256"] != roots[1]["source_manifest_sha256"]
    assert roots[0]["capability_tree_sha256"] == roots[1]["capability_tree_sha256"]
    assert roots[0]["terminal_tree_sha256"] == roots[1]["terminal_tree_sha256"]
    assert acceptance["capability_maps_byte_identical"] is True
    assert acceptance["terminal_maps_byte_identical"] is True
    assert acceptance["capability_files_compared"] == 252
    assert acceptance["terminal_files_compared"] == 8


def test_both_exact_future_identity_branches_are_proved_without_fits() -> None:
    acceptance = _load(ACCEPTANCE)
    assert acceptance["model_double_invocations_total"] == 3480
    assert acceptance["synthetic_prediction_identities_total"] == 667872
    assert acceptance["fit_and_stage_checkpoints_total"] == 6980
    for root in acceptance["roots"]:
        full = root["profiles"]["full_retained"]["identities"]
        deletion = root["profiles"]["deletion_selected"]["identities"]
        assert full["official_future_fit_identities"] == {
            "stage_a": 540,
            "stage_b": 180,
            "stage_c": 0,
            "total": 720,
        }
        assert deletion["official_future_fit_identities"] == {
            "stage_a": 540,
            "stage_b": 180,
            "stage_c": 300,
            "total": 1020,
        }
        assert full["official_future_prediction_identities"]["minimum_total"] == (
            562752
        )
        assert deletion["official_future_prediction_identities"]["maximum_total"] == (
            797232
        )
        assert full["runner_ups"] == deletion["runner_ups"] == 0
        assert full["deployable_clips"] == deletion["deployable_clips"] == 0


def test_supervisor_passes_control_and_rejects_every_fault_class() -> None:
    evidence = _load(ACCEPTANCE)["supervisor_evidence"]
    assert evidence["success"]["network_namespace_isolated"] is True
    assert evidence["success"]["gpu_environment_hidden"] is True
    assert evidence["success"]["cleanup_complete"] is True
    assert evidence["success"]["warnings_observed"] == 0
    assert evidence["success"]["detached_children_observed"] == 0
    assert evidence["fail_stop_scenarios"] == {
        "cpu": True,
        "detached": True,
        "missing_checkpoint": True,
        "nonzero": True,
        "partial_publication": True,
        "rss": True,
        "signal": True,
        "storage": True,
        "wall": True,
        "warning": True,
    }
    assert evidence["restricted_roots_retained"] == 0
    assert evidence["resource_projection_authority"] is False


def test_acceptance_opens_no_scientific_or_forbidden_authority() -> None:
    acceptance = _load(ACCEPTANCE)
    assert acceptance["real_catboost_fits"] == 0
    assert acceptance["resource_projections"] == 0
    assert acceptance["development_metric_evaluations"] == 0
    assert acceptance["confirmatory_target_values_parsed"] == 0
    assert acceptance["private_roots_retained"] == 0
    assert acceptance["model_quality_authority"] is False
    assert acceptance["claim_authority"] is False
    accounting = acceptance["accounting"]
    allowed_nonzero = {
        "synthetic_source_rows_opened": 19200,
        "synthetic_model_double_invocations": 3480,
        "synthetic_prediction_identities": 667872,
    }
    assert {
        key: value for key, value in accounting.items() if value != 0
    } == allowed_nonzero
    text = ACCEPTANCE.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text


def test_formal_mutable_roots_and_invalid_publication_are_absent() -> None:
    assert not Path("/tmp/cypshift-g2-7c-no-fit-formal-attempt-1").exists()
    assert not Path("/tmp/cypshift-g2-7c/no-fit-formal-attempt-2").exists()
    assert not Path("/tmp/cypshift-g2-7c/no-fit-formal-attempt-3").exists()
    assert not Path("/tmp/cypshift-g2-7c/no-fit-formal-attempt-4").exists()
    assert not Path("/tmp/cypshift-g2-7c/no-fit-formal-attempt-5").exists()
    assert ACCEPTANCE.is_file()
