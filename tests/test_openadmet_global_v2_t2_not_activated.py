from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
RECEIPT = BENCHMARK / "global_v2_t2_not_activated.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_t2_nonactivation_is_bound_to_terminal_global_evidence() -> None:
    receipt = _read(RECEIPT)
    assert receipt["status"] == "G2_6_TRACE_V2_NOT_ACTIVATED"
    assert receipt["decision"] == "do_not_contract_or_execute_exp_t2"
    for parent in receipt["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]

    inventory = receipt["evidence_inventory"]
    assert inventory["accepted_stronger_global_successors"] == 0
    assert inventory["accepted_stronger_global_successor_oof_receipts"] == 0
    assert inventory["positive_improvement_versus_coverage_receipts"] == 0
    assert inventory["maplight_is_stable_baseline"] is True
    assert inventory["maplight_is_stronger_successor"] is False
    assert all(
        inventory[key] == 0
        for key in (
            "g1_scientific_oof_predictions",
            "g2_scientific_oof_predictions",
            "m1_scientific_oof_predictions",
            "x1_scientific_oof_predictions",
        )
    )


def test_t2_nonactivation_opens_no_scientific_or_submission_capability() -> None:
    receipt = _read(RECEIPT)
    decision = receipt["activation_decision"]
    assert decision["activation_pass"] is False
    assert decision["exp_t2_contract_authorized"] is False
    assert decision["exp_t2_implementation_authorized"] is False
    assert decision["exp_t2_execution_authorized"] is False
    assert all(value == 0 for value in receipt["accounting"].values())
    assert "no model-quality result" in receipt["scientific_interpretation"]


def test_t2_nonactivation_contains_no_private_submission_fields() -> None:
    text = RECEIPT.read_text(encoding="utf-8").lower()
    forbidden = ("submission_name", "leaderboard_score", "leaderboard_rank")
    assert all(value not in text for value in forbidden)
