from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I0_V2 = (
    ROOT / "benchmarks/openadmet_cyp_2026/inferred_anchor_experiment_contract_v2.json"
)
I0_V3 = (
    ROOT / "benchmarks/openadmet_cyp_2026/inferred_anchor_experiment_contract_v3.json"
)
R5D_V3 = (
    ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v3.json"
)


def test_i0_crash_overlay_changes_only_eligible_attempt_parent() -> None:
    contract = json.loads(I0_V3.read_bytes())
    assert (
        contract["parent_i0_contract"]["sha256"]
        == hashlib.sha256(I0_V2.read_bytes()).hexdigest()
    )
    parent = contract["official_attempt_parent"]
    assert parent["contract_sha256"] == hashlib.sha256(R5D_V3.read_bytes()).hexdigest()
    assert parent["eligible_attempt_id"] == ("r5d-cyp3a4-official-crash-replacement-1")
    assert parent["required_status"] == "R5_ORACLE_SIGNAL_PASS"
    assert all(
        value is False
        for key, value in contract["authority"].items()
        if key != "contract_only"
    )
