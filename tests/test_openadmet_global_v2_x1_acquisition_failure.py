from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RECEIPT = BENCHMARK / "global_v2_x1_acquisition_failure.json"
CLAIM = BENCHMARK / "global_v2_x1_acquisition_claim.json"
ACCEPTANCE = BENCHMARK / "global_v2_x1_real_source_adapter_acceptance.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_x1_failure_receipt_closes_consumed_claim_without_modeling() -> None:
    receipt = _read_json(RECEIPT)
    assert receipt["status"] == "G2_5C_X1_ACQUISITION_FAILED"
    assert receipt["decision"] == "reject_exp_x1_without_retry_or_model_fit"
    assert receipt["parents"]["acquisition_claim"]["sha256"] == _sha256(CLAIM)
    assert receipt["parents"]["real_source_adapter_acceptance"]["sha256"] == _sha256(
        ACCEPTANCE
    )

    acquisition = receipt["acquisition"]
    assert acquisition["downloads_attempted"] == 1
    assert acquisition["downloads_completed"] == 1
    assert acquisition["archive_sha256_verified_before_listing"] is True
    assert acquisition["sqlite_integrity_check_passed"] is True

    failure = receipt["failure"]
    assert failure["stage"] == "sqlite_schema_preflight"
    assert failure["support_falsifier_reached"] is False
    assert failure["model_fit_reached"] is False
    assert failure["retry_authorized"] is False
    assert failure["replacement_source_authorized"] is False

    assert all(receipt["cleanup"].values())
    accounting = receipt["accounting"]
    assert accounting["acquisition_claims_consumed"] == 1
    assert accounting["external_dataset_files_downloaded"] == 1
    assert accounting["external_activity_rows_opened"] == 0
    zero_fields = {
        key
        for key in accounting
        if key
        not in {
            "acquisition_claims_created",
            "acquisition_claims_consumed",
            "external_dataset_files_downloaded",
            "external_dataset_bytes_downloaded",
        }
    }
    assert all(accounting[key] == 0 for key in zero_fields)
    assert receipt["scientific_result"]["external_transfer_model_quality"] is None
    assert receipt["scientific_result"]["best_validated_system_changed"] is False


def test_x1_failure_receipt_contains_no_private_portal_observation() -> None:
    text = RECEIPT.read_text(encoding="utf-8").lower()
    assert "private portal" in text
    forbidden = ("submission_name", "leaderboard_score", "leaderboard_rank")
    assert all(value not in text for value in forbidden)
