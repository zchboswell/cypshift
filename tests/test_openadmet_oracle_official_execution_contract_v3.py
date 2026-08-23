from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v2.json"
V3 = ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v3.json"
V3_SHA256 = "ee135e7fa450ab05b68f92a46085213f7be574ce218ab9fda01df833e46125cf"


def test_crash_replacement_changes_only_attempt_parent_and_identity() -> None:
    contract = json.loads(V3.read_bytes())
    assert hashlib.sha256(V3.read_bytes()).hexdigest() == V3_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.oracle_official_execution_contract.v3"
    )
    assert (
        contract["parent_contract"]["sha256"]
        == hashlib.sha256(V2.read_bytes()).hexdigest()
    )
    assert contract["execution"] == {
        "attempt_id": "r5d-cyp3a4-official-crash-replacement-1",
        "artifact_root": (
            "/home/zbos/cypshift-private/openadmet-2026/"
            "r5d-cyp3a4-official-crash-replacement-1"
        ),
        "maximum_attempts": 1,
        "retry": False,
        "resume": False,
        "start_from_scratch": True,
        "durable_process_log_required": True,
        "supported_topology": "Inherit the exact v2 7,985-child topology.",
        "attempt_start": (
            "Authenticate the exact v2 contract, original zero-operation parent, "
            "interrupted-parent inventory, clean signed checkout, both runtimes, four "
            "official parents, and 17 source leaves before atomically claiming this "
            "distinct root."
        ),
        "interruption_policy": (
            "A further interruption or failure is terminal and authorizes no additional "
            "attempt."
        ),
    }


def test_crash_replacement_binds_exact_interrupted_inventory() -> None:
    parent = json.loads(V3.read_bytes())["interrupted_parent"]
    assert parent["claim_sha256"] == (
        "be22a0d9fb8879db23b39e74ba19852ebfc9843ae41cc63184dc1a80bf0102bd"
    )
    assert parent["inventory"] == {
        "algorithm": (
            "SHA-256 of canonical compact JSON plus LF over every descendant sorted by "
            "relative POSIX path; each row is [path,type,mode,size,sha256-or-null] and "
            "symlinks/special files are forbidden."
        ),
        "entries": 15907,
        "directories": 5607,
        "files": 10300,
        "sha256": "e948f77559d38c35b020a7d0beb228a066c53690dd5818d267079af6e3889f40",
    }
    assert parent["completed_artifacts"] == {
        "g0_manifests": 3366,
        "inner_candidate_manifests": 960,
        "inner_selection_rows": 240,
        "isolated_selection_tokens": 90,
        "outer_fragment_manifests": 73,
    }
    assert "terminal" in parent["required_absent"]
    assert "receipt" in parent["required_absent"]
