from __future__ import annotations

import hashlib
import json
from pathlib import Path

from test_openadmet_oracle_official_execution_contract_v1 import (
    PARENT_RECEIPTS,
    SOURCE_ORDER,
    VERBS,
)

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v1.json"
V2 = ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v2.json"
V2_SHA256 = "0934e66ac4e0297ff3301651b270f785e926f7303f0ab5034aaf2c541bcad993"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def test_recovery_contract_changes_only_attempt_authority_and_prefit_gate() -> None:
    v1 = _load(V1)
    v2 = _load(V2)
    assert hashlib.sha256(V2.read_bytes()).hexdigest() == V2_SHA256
    assert v2["schema_version"] == (
        "cypshift.openadmet_cyp_2026.oracle_official_execution_contract.v2"
    )
    assert v2["contract_id"] == "R5D-CYP3A4-OFFICIAL-RECOVERY-ATTEMPT-V1"
    assert (
        v2["resolved_oracle_contract_sha256"] == v1["resolved_oracle_contract_sha256"]
    )
    assert v2["official_source_revision"] == v1["official_source_revision"]
    assert v2["parents"] == v1["parents"]
    assert v2["source_bundle"] == v1["source_bundle"]
    assert tuple(v2["source_order"]) == SOURCE_ORDER  # type: ignore[arg-type]
    assert v2["runtime"] == v1["runtime"]
    assert v2["forbidden_operations"] == v1["forbidden_operations"]
    assert v2["authority"] == v1["authority"]

    execution = v2["execution"]
    assert isinstance(execution, dict)
    assert execution["attempt_id"] == "r5d-cyp3a4-official-recovery-attempt-1"
    assert execution["maximum_attempts"] == 1
    assert execution["retry"] is False and execution["resume"] is False
    assert execution["supported_topology"] == v1["execution"]["supported_topology"]  # type: ignore[index]
    assert execution["supported_topology"]["verbs"] == VERBS  # type: ignore[index]
    assert execution["preclaim_executable_gate"] == {
        "root_python": "<checkout>/.venv/bin/python",
        "g0_python": "<checkout>/research/maplight-fixed/.venv/bin/python",
        "root_identity": "The executing sys.executable must resolve to root_python.",
        "timing": "Both regular files and root identity must be verified before recovery root creation.",
    }


def test_recovery_contract_binds_exact_zero_operation_failure() -> None:
    contract = _load(V2)
    parent = contract["recovery_parent"]
    assert isinstance(parent, dict)
    assert parent == {
        "attempt_root": "/home/zbos/cypshift-private/openadmet-2026/r5d-cyp3a4-official-attempt-1",
        "attempt_id": "r5d-cyp3a4-official-attempt-1",
        "execution_contract_sha256": hashlib.sha256(V1.read_bytes()).hexdigest(),
        "claim_sha256": "331c93eb2503001692bcd165b071c003b58d4067a2e31aa995454c626c8587bb",
        "failure_sha256": "79d73d854ffa26cc13c204659096e524750d70e8f5aad578f6e996509566a463",
        "receipt_sha256": "2c1f0c5901a399df31f428420a51ea5d469b2ee9a931304a1a6a612ca711078c",
        "required_status": "R5_ORACLE_FAILED",
        "required_failure": {"stage": "pre_gate", "failure_code": "RUNTIME"},
        "required_processes": [
            {"index": 0, "verb": "cleanup", "returncode": 0},
            {"index": 1, "verb": "failed", "returncode": 0},
        ],
        "required_operation_accounting": "Exact 14-field all-zero vector in both the failed terminal and official attempt receipt.",
        "required_authority": "Every authority value false in both the failed terminal and official attempt receipt.",
        "scientific_visibility": "No source compiler, target parser, model fit, prediction freezer, truth scorer, test, TDI, metric, submission, transduction, or inferred-anchor pool operation occurred.",
    }
    assert set(contract["parents"]) == set(PARENT_RECEIPTS)  # type: ignore[arg-type]
