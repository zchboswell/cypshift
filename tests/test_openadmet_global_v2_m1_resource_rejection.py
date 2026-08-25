from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
REJECTION_PATH = BENCHMARK / "global_v2_m1_resource_rejection.json"
CLAIM_PATH = BENCHMARK / "global_v2_m1_formal_attempt_claim.json"
REJECTION_SHA256 = "3222856dfde449e616fe13cf02942abca5d4c78ad775a7d6035729d7bfa54297"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rejection_is_exact_and_consumes_only_the_frozen_formal_claim() -> None:
    result = _load(REJECTION_PATH)
    claim = _load(CLAIM_PATH)
    assert _sha256(REJECTION_PATH) == REJECTION_SHA256
    assert result["status"] == "G2_4_M1_RESOURCE_REJECTED"
    assert result["decision"] == "reject_exp_m1_without_official_access"
    assert result["contract_sha256"] == claim["contract_sha256"]
    assert result["claim"] == {
        "attempt_id": claim["attempt_id"],
        "claim_sha256": _sha256(CLAIM_PATH),
        "consumed": True,
        "maximum_attempts": 1,
        "replacement_authorized": False,
    }
    assert claim["consumed"] is False


def test_probe_completed_exact_full_width_two_root_topology() -> None:
    probe = _load(REJECTION_PATH)["formal_probe"]
    assert probe["roots_completed"] == 2
    assert probe["fits_per_root"] == 16
    assert probe["fits_completed"] == 32
    assert probe["epochs_per_fit"] == 300
    assert probe["training_rows_per_fit"] == 3908
    assert probe["prediction_rows_per_fit"] == 997
    assert probe["input_columns"] == 2248
    assert probe["maximum_concurrent_fits"] == 4
    assert probe["threads_per_fit"] == 4
    assert probe["network_isolated"] is True


def test_cpu_alone_terminally_rejects_while_other_resource_gates_pass() -> None:
    projection = _load(REJECTION_PATH)["resource_projection"]
    assert projection["accepted"] is False
    assert projection["gates"] == {
        "cpu": False,
        "gpu": True,
        "rss": True,
        "storage": True,
        "wall": True,
    }
    assert projection["projected_cpu_core_hours"] == 266.7373089008778
    assert projection["maximum_cpu_core_hours"] == 240.0
    assert projection["projected_cpu_excess_core_hours"] == 26.7373089008778
    assert projection["projected_cpu_excess_percent"] == 11.14054537536575
    assert projection["projected_wall_hours"] == 17.206805174399165
    assert projection["projected_peak_rss_gib"] == 2.16412353515625
    assert projection["projected_restricted_storage_gb"] == 4.304410385
    assert projection["projected_gpu_hours"] == 0


def test_opposite_order_roots_match_scientific_receipts_and_cleanup() -> None:
    result = _load(REJECTION_PATH)
    determinism = result["determinism"]
    assert determinism["root_b_physical_and_launch_order_reversed"] is True
    assert determinism["cross_root_runtime_identity_equal"] is True
    assert determinism["within_root_repeat_identity_equal"] is True
    assert len(determinism["scientific_terminal_sha256"]) == 5
    assert all(len(value) == 64 for value in result["private_receipt_sha256"].values())
    assert all(result["cleanup"].values())
    assert result["runtime_warning_observation"]["count"] == 32


def test_rejection_has_no_model_quality_or_official_authority() -> None:
    result = _load(REJECTION_PATH)
    accounting = result["accounting"]
    assert accounting["formal_claims_created"] == 1
    assert accounting["formal_claims_consumed"] == 1
    assert accounting["formal_probe_fits"] == 32
    assert all(
        value == 0
        for name, value in accounting.items()
        if name not in {"formal_claims_created", "formal_claims_consumed", "formal_probe_fits"}
    )
    assert not any(result["authority"].values())
    interpretation = result["scientific_interpretation"].lower()
    assert "no model-quality evidence" in interpretation
    assert "not fitted or scored on official development data" in interpretation
