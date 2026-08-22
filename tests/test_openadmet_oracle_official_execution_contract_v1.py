from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v1.json"
)
CONTRACT_SHA256 = "f8aadef95be8e0d719a14d08bc2a1164a03d2cf5079e9ed2dec749ee048bd700"
SOURCE_ORDER = (
    "direct_observations.csv",
    "group_folds.csv",
    "campaign_episodes_public.csv",
    "campaign_episodes_truth.csv",
    "episode_label_masks.csv",
    "feature_manifest.json",
    "feature_rows.csv",
    "maplight_morgan_count.npy",
    "maplight_avalon_count.npy",
    "maplight_erg.npy",
    "maplight_rdkit_descriptors.npy",
    "morgan_binary.npy",
    "global_oof_predictions.csv",
    "global_inner_oof_predictions.csv",
    "transformation_pairs.csv",
    "episode_transformations.csv",
    "transformation_coverage.json",
)
SOURCE_FILES = set(SOURCE_ORDER)
SOURCE_RECEIPTS = {
    "campaign_episodes_public.csv": (
        "r2b",
        "471804773631623235a7d554a1d8e297c5b098089f96390c85f622a82b619a7a",
    ),
    "campaign_episodes_truth.csv": (
        "r2b",
        "f2ec3ca6c3f48850cf6dedf1f129903d525ec72e8da55566eca66103745bd2a4",
    ),
    "direct_observations.csv": (
        "r2b",
        "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7",
    ),
    "episode_label_masks.csv": (
        "r2b",
        "0b437aa5c43286833f4b2ccbf97c36afbfa6e940dcf20d1e2a2728a324fe3240",
    ),
    "group_folds.csv": (
        "r2b",
        "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774",
    ),
    "feature_manifest.json": (
        "r3a",
        "32a950959ceca0641b56518e2059069a275ced64cf399d095aa5bce522c8026b",
    ),
    "feature_rows.csv": (
        "r3a",
        "14260507a8fc6740e94dab848dc7fc87f1d45a57c2a2c67cfb2142fbea36cb30",
    ),
    "maplight_avalon_count.npy": (
        "r3a",
        "368cb438d02127324f3471d21bf29e75e108bc0021f5fc50bfffb6ab841eed95",
    ),
    "maplight_erg.npy": (
        "r3a",
        "24e70fdf07d1d7bb8bbb3ed54acd95b9734e847908ab5e99d6a454360d5a3504",
    ),
    "maplight_morgan_count.npy": (
        "r3a",
        "24c805df9dc7da5ca7d43e86161aa2862995cd818415ee083b6f6ba5ac493c14",
    ),
    "maplight_rdkit_descriptors.npy": (
        "r3a",
        "4a85afd7340121e175691775b944bcc0c2d4f7765ea729565d0f3c885e8c9905",
    ),
    "morgan_binary.npy": (
        "r3a",
        "7e10e94b9f89c71d0d76951ebc27f9e0a8fd28e6cb7bc499560e759b6fee52f3",
    ),
    "global_inner_oof_predictions.csv": (
        "r3c",
        "17cc5aadf6e109efe13893e9d9364371043f1fc7b1e4e2faa20dae5ab5c3c332",
    ),
    "global_oof_predictions.csv": (
        "r3c",
        "1935b580ec779f2fc08d40e32e9669edae6e166ea70cd964e325df853527af80",
    ),
    "episode_transformations.csv": (
        "r4",
        "8afc1b82e573ede6cb9c52a14a2a21dd73fa561d7829b7faaeda298d7d70cc2a",
    ),
    "transformation_coverage.json": (
        "r4",
        "b134d11c96526c8c3ed282cebfacaae25ce9bf49c324bfe28d8c4f1d4913a84e",
    ),
    "transformation_pairs.csv": (
        "r4",
        "5eadb743e748e50b07d3eb09648400647d5370a97d2d76579bb453ba66f01a76",
    ),
}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "contract_id",
    "gate",
    "status",
    "purpose",
    "resolved_oracle_contract_sha256",
    "official_source_revision",
    "parents",
    "source_bundle",
    "source_order",
    "runtime",
    "execution",
    "attempt_envelope",
    "forbidden_operations",
    "authority",
    "reversal_condition",
}
PARENT_RECEIPTS = {
    "r2b": "08dcf61cded99fae046bff49b57b0c4a12082cd8714c779ac44a351bf1a0c8c8",
    "r3a": "32a950959ceca0641b56518e2059069a275ced64cf399d095aa5bce522c8026b",
    "r3c": "a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c",
    "r4": "8166a89aee5137228a31085e21d36d6f0bf4a28d833cdc7bd1280feff4170043",
}
VERBS = {
    "source": 1,
    "project": 1,
    "support": 1,
    "migrate": 75,
    "episodes": 75,
    "view": 3366,
    "g0": 3366,
    "pair-inner": 960,
    "inner": 1,
    "pair-outer": 120,
    "pair-outer-shared": 15,
    "freezer": 1,
    "accounting": 1,
    "cleanup": 1,
    "outer": 1,
}
AUTHORITY = {
    "contract_only": True,
    "official_attempt": False,
    "oracle_evidence": False,
    "inferred_anchor_contract": False,
    "model_fits": False,
    "predictions": False,
    "internal_metrics": False,
    "official_st_rae": False,
    "test_access": False,
    "tdi": False,
    "submission": False,
    "transduction": False,
}


def _strict_object(data: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    value = json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite token: {token}")
        ),
    )
    assert isinstance(value, dict)
    return value


def _digest(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("digest differs")
    return value


def _validate(contract: dict[str, Any]) -> None:
    if set(contract) != TOP_LEVEL_FIELDS:
        raise ValueError("contract fields differ")
    if (
        contract["schema_version"]
        != "cypshift.openadmet_cyp_2026.oracle_official_execution_contract.v1"
        or contract["contract_id"] != "R5D-CYP3A4-OFFICIAL-ATTEMPT-V1"
        or contract["gate"] != "R5D_OFFICIAL_EXECUTION_CONTRACT_FROZEN"
        or contract["status"] != "R5D_OFFICIAL_EXECUTION_CONTRACT_ONLY"
        or contract["resolved_oracle_contract_sha256"]
        != "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
        or contract["official_source_revision"]
        != "85f8b358d0a2056a98b990dd75d3b3ec9247862b"
    ):
        raise ValueError("contract identity differs")
    parents = contract["parents"]
    if set(parents) != set(PARENT_RECEIPTS):
        raise ValueError("parent set differs")
    for name, digest in PARENT_RECEIPTS.items():
        if _digest(parents[name]["manifest_sha256"]) != digest:
            raise ValueError("parent receipt differs")
    sources = contract["source_bundle"]
    if set(sources) != SOURCE_FILES or tuple(contract["source_order"]) != SOURCE_ORDER:
        raise ValueError("source set differs")
    for name, record in sources.items():
        parent, expected_receipt = SOURCE_RECEIPTS[name]
        if (
            set(record) != {"parent", "relative_path", "sha256"}
            or record["parent"] != parent
            or record["relative_path"] != name
            or _digest(record["sha256"]) != expected_receipt
        ):
            raise ValueError("source binding differs")
    execution = contract["execution"]
    if (
        execution["attempt_id"] != "r5d-cyp3a4-official-attempt-1"
        or execution["artifact_root"]
        != "/home/zbos/cypshift-private/openadmet-2026/r5d-cyp3a4-official-attempt-1"
        or execution["maximum_attempts"] != 1
        or execution["retry"] is not False
        or execution["resume"] is not False
        or execution["official_episode_cardinality"]
        != {
            "selected_anchor_episodes": 561,
            "deterministic_random_anchor_stress_episodes": 561,
            "selected_contexts_per_episode": 5,
            "stress_contexts_per_episode": 1,
            "g0_episode_contexts": 3366,
            "derivation": (
                "Each unique selected-anchor episode appears once in its assigned "
                "outer scope and once in each of the four current-outer "
                "inner-validation scopes; each unique stress episode appears only "
                "in its assigned outer scope. Therefore 561*5 + 561*1 = 3366."
            ),
        }
        or execution["supported_topology"]["total_child_processes"] != 7985
        or execution["supported_topology"]["verbs"] != VERBS
        or sum(VERBS.values()) != 7985
        or execution["underpowered_topology"]
        != {
            "total_child_processes": 5,
            "verbs": {
                "cleanup": 1,
                "project": 1,
                "source": 1,
                "support": 1,
                "underpowered": 1,
            },
        }
        or execution["artifact_layout"]
        != {
            "claim_file": "attempt_claim.json",
            "private_root": "private",
            "terminal_root": "terminal",
            "receipt_root": "receipt",
            "final_root_entries": [
                "attempt_claim.json",
                "receipt",
                "terminal",
            ],
        }
        or execution["claim"]["schema_version"]
        != "cypshift.openadmet_cyp_2026.r5d_official_attempt_claim.v1"
    ):
        raise ValueError("execution topology differs")
    envelope = contract["attempt_envelope"]
    if (
        envelope["schema_version"]
        != "cypshift.openadmet_cyp_2026.r5d_official_attempt_receipt.v1"
        or envelope["file_set"] != ["official_attempt_receipt.json"]
        or envelope["process_fields"] != ["index", "verb", "pid", "returncode"]
        or "processes" not in envelope["fields"]
        or "claim_sha256" not in envelope["fields"]
        or "parent_receipts" not in envelope["fields"]
        or "source_receipts" not in envelope["fields"]
        or "terminal_receipts" not in envelope["fields"]
    ):
        raise ValueError("attempt envelope differs")
    if contract["forbidden_operations"] != {
        "blinded_test_files_opened": 0,
        "tdi_files_opened": 0,
        "official_metric_calls": 0,
        "submissions_created": 0,
        "transductive_relationships": 0,
        "inferred_anchor_candidate_pools": 0,
    }:
        raise ValueError("forbidden operations differ")
    if contract["authority"] != AUTHORITY:
        raise ValueError("contract authority differs")


def _contract() -> dict[str, Any]:
    data = CONTRACT_PATH.read_bytes()
    assert hashlib.sha256(data).hexdigest() == CONTRACT_SHA256
    return _strict_object(data)


def test_official_execution_contract_is_exact_and_self_consistent() -> None:
    contract = _contract()
    _validate(contract)
    assert set(contract["execution"]["terminal_statuses"]) == {
        "R5_ORACLE_FAILED",
        "R5_ORACLE_UNDERPOWERED",
        "R5_ORACLE_NO_SIGNAL",
        "R5_ORACLE_SIGNAL_PASS",
    }


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("parents", "r2b", "manifest_sha256"), "0" * 64),
        (("source_bundle", "direct_observations.csv", "parent"), "r3a"),
        (("execution", "maximum_attempts"), 2),
        (("execution", "supported_topology", "verbs", "g0"), 3365),
        (("forbidden_operations", "blinded_test_files_opened"), 1),
        (("authority", "test_access"), True),
    ],
)
def test_official_execution_contract_rejects_authority_drift(
    path: tuple[str, ...], value: object
) -> None:
    contract = copy.deepcopy(_contract())
    target: dict[str, Any] = contract
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        _validate(contract)
