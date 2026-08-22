from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "benchmarks/openadmet_cyp_2026/inferred_anchor_experiment_contract_v1.json"
V2 = ROOT / "benchmarks/openadmet_cyp_2026/inferred_anchor_experiment_contract_v2.json"
R5D_V2 = (
    ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v2.json"
)


def test_i0_recovery_overlay_changes_only_the_eligible_attempt_parent() -> None:
    contract = json.loads(V2.read_bytes())
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.i0_preregistration.v2"
    )
    assert contract["status"] == "I0_PREREG_ONLY"
    assert (
        contract["inheritance"]["sha256"] == hashlib.sha256(V1.read_bytes()).hexdigest()
    )
    assert "Every v1 system" in contract["inheritance"]["rule"]
    recovery = contract["recovery_execution_parent"]
    assert recovery["sha256"] == hashlib.sha256(R5D_V2.read_bytes()).hexdigest()
    assert recovery["eligible_attempt_id"] == ("r5d-cyp3a4-official-recovery-attempt-1")
    failed = contract["failed_attempt_parent"]
    assert failed["receipt_sha256"] == (
        "2c1f0c5901a399df31f428420a51ea5d469b2ee9a931304a1a6a612ca711078c"
    )
    assert failed["required_operation_accounting"] == (
        "Exact 14-field all-zero vector."
    )
    assert contract["activation"]["required_status"] == "R5_ORACLE_SIGNAL_PASS"
    assert all(
        value is False
        for key, value in contract["authority"].items()
        if key != "contract_only"
    )
