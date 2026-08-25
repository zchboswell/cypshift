from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RECEIPT = BENCHMARK / "global_v2_g3_official_failure.json"
CONTRACT = BENCHMARK / "global_v2_g3_execution_contract.json"
CLAIM = BENCHMARK / "global_v2_g3_execution_claim.json"
ACCEPTANCE = BENCHMARK / "global_v2_g3_execution_synthetic_acceptance.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g3_failure_consumes_one_claim_without_model_quality() -> None:
    receipt = _read(RECEIPT)
    assert receipt["status"] == "G2_6R_G3_FAILED"
    assert receipt["decision"] == "reject_exp_g3_without_retry_or_model_quality_claim"
    assert receipt["parents"]["execution_contract"]["sha256"] == _sha256(CONTRACT)
    assert receipt["parents"]["unconsumed_claim_template"]["sha256"] == _sha256(CLAIM)
    assert receipt["parents"]["official_shaped_synthetic_acceptance"][
        "sha256"
    ] == _sha256(ACCEPTANCE)
    assert receipt["parents"]["post_main_ci"] == {
        "run_id": 32860509984,
        "head_sha": "cfb3bd47695fbadc168c9cbdf0e329d8084ace71",
        "conclusion": "success",
    }

    execution = receipt["execution"]
    assert execution["claim_consumptions"] == execution["attempts"] == 1
    assert execution["completed_lightgbm_fits"] == 0
    assert execution["candidate_predictions"] == 0
    assert execution["baseline_prediction_rows_opened"] == 0
    assert execution["tutorial_metric_calls"] == 0
    assert execution["bootstrap_replicates"] == 0
    assert receipt["scientific_result"]["exp_g3_model_quality"] is None
    assert receipt["scientific_result"]["promotion_gate_result"] is None
    assert receipt["scientific_result"]["best_validated_system"] == "fixed MapLight"


def test_first_failure_and_latent_source_shape_mismatches_are_exact() -> None:
    receipt = _read(RECEIPT)
    failure = receipt["failure"]
    assert failure["stage"] == "official_source_manifest_identity"
    assert failure["first_failing_predicate"] == (
        "source_manifest_authority_exact_equality"
    )
    assert len(failure["expected_authority_keys"]) == 15
    assert len(failure["observed_authority_keys"]) == 12
    assert set(failure["expected_authority_keys"]) != set(
        failure["observed_authority_keys"]
    )
    assert failure["shared_authority_values_agree"] is True
    assert failure["source_manifest_opened"] is True
    assert failure["source_leaf_files_opened"] == 0
    assert failure["source_rows_parsed"] == 0
    assert failure["model_fit_reached"] is False
    assert failure["scorer_reached"] is False
    assert failure["retry_authorized"] is False
    assert failure["resume_authorized"] is False
    assert failure["repair_authorized"] is False

    latent = receipt["latent_adapter_mismatch"]
    assert latent["reached"] is False
    assert latent["compiler_required_exact_source_receipt_keys"] == [
        "direct_observations.csv",
        "feature_rows.csv",
        "group_folds.csv",
        "maplight_rdkit_descriptors.npy",
    ]
    assert latent["accepted_manifest_additional_receipt_keys"] == [
        "maplight_avalon_count.npy",
        "maplight_erg.npy",
        "maplight_morgan_count.npy",
    ]


def test_failure_accounting_is_aggregate_only_and_forbidden_operations_are_zero() -> (
    None
):
    receipt = _read(RECEIPT)
    accounting = receipt["accounting"]
    assert accounting["official_source_manifests_opened"] == 1
    zero_fields = set(accounting) - {"official_source_manifests_opened"}
    assert all(accounting[name] == 0 for name in zero_fields)
    private = receipt["private_aggregate_receipts"]
    assert private["cleanup_complete"] is True
    assert private["attempt_root_mode"] == "0555"
    assert private["attempt_file_mode"] == "0444"
    assert all(
        len(private[name]) == 64
        for name in (
            "consumed_claim_sha256",
            "attempt_receipt_sha256",
            "terminal_manifest_sha256",
            "terminal_result_sha256",
            "accepted_source_manifest_sha256",
        )
    )


def test_failure_receipt_contains_no_private_submission_observation() -> None:
    text = RECEIPT.read_text(encoding="utf-8").lower()
    forbidden = (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
    )
    assert all(value not in text for value in forbidden)
