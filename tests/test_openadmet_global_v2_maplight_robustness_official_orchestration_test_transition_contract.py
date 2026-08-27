from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_test_transition_contract.json"
)
CONTRACT_SHA256 = "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
D136_AUDIT = (
    ROOT
    / "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py"
)
D140_FOCUSED_PATH = (
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
)

HISTORICAL_NODES = [
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_acceptance_binds_exact_contract_and_integrated_"
        "implementation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_provenance_bridge_retires_only_the_obsolete_pre_"
        "acceptance_state"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_claim_derivation_is_read_only_and_fills_exactly_"
        "five_receipts"
    ),
]
REPLACEMENT_NODES = [
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_historical_lineage_uses_immutable_driver_hash_and_"
        "composite_is_required"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_two_orders_cover_six_scenarios_and_build_one_zero_"
        "operation_record"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_candidate_bytes_prove_all_five_future_claim_fields_"
        "before_publication"
    ),
]


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _node_function_names(node_ids: list[str]) -> set[str]:
    return {node_id.rsplit("::", 1)[1] for node_id in node_ids}


def test_contract_identity_and_two_file_contract_only_surface() -> None:
    value = _load(CONTRACT)
    assert _sha256(CONTRACT) == CONTRACT_SHA256
    assert value["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_official_"
        "orchestration_test_transition_contract.v1"
    )
    assert value["decision_id"] == "D-139"
    assert value["gate"] == (
        "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_TEST_TRANSITION_"
        "CONTRACT_FROZEN"
    )
    assert value["status"] == (
        "contract_only_no_test_retirement_or_d140_integration_or_acceptance_or_"
        "official_execution_yet"
    )
    assert value["base_commit"] == "158dffcadfb71305d7de7b84279cfee96a6e8318"
    assert value["contract_package"] == {
        "new_files": [
            "benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_"
            "official_orchestration_test_transition_contract.json",
            "tests/test_openadmet_global_v2_maplight_robustness_official_"
            "orchestration_test_transition_contract.py",
        ],
        "existing_production_or_test_collection_files_changed_by_contract_freeze": 0,
    }


def test_d135_through_d138_parent_hashes_and_commits_are_exact() -> None:
    parents = _load(CONTRACT)["parent_evidence"]
    expected = {
        "d135_science_kernel_acceptance": (
            "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390",
            "7450676da651e86bab341c7434dd1b9dd2f19388",
        ),
        "d136_test_provenance_bridge": (
            "2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3",
            "1c0c5d0f293579a8748e25b3951f9234409bfa39",
        ),
        "d137_official_orchestration_repair_contract": (
            "f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967",
            "0dbbc7013b5303ef2f1535455d458b87208df1b9",
        ),
        "d138_terminal_seal_erratum": (
            "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33",
            "158dffcadfb71305d7de7b84279cfee96a6e8318",
        ),
    }
    assert set(parents) == set(expected)
    for name, (digest, commit) in expected.items():
        evidence = parents[name]
        assert _sha256(ROOT / evidence["path"]) == evidence["sha256"] == digest
        assert evidence["integrated_commit"] == commit


def test_immutable_d136_audit_retires_exactly_three_nodes_without_live_hook_hash() -> (
    None
):
    value = _load(CONTRACT)
    provenance = value["historical_test_provenance"]
    bridge = _load(
        BENCHMARK / "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
    )
    audit_tests = _test_names(D136_AUDIT)

    assert provenance["audit_path"] == D136_AUDIT.relative_to(ROOT).as_posix()
    assert (
        _sha256(D136_AUDIT)
        == provenance["audit_sha256"]
        == "719c0f71a8a0e403f590e1aced8a38b3c6131ff915a2bc9f8234126761bb4a2f"
    )
    assert len(audit_tests) == provenance["audit_total_test_nodes"] == 7
    assert provenance["audit_mutation_allowed"] is False
    assert provenance["retired_node_ids"] == HISTORICAL_NODES
    assert provenance["retired_node_count"] == len(HISTORICAL_NODES) == 3
    assert _node_function_names(HISTORICAL_NODES) < audit_tests
    assert len(audit_tests - _node_function_names(HISTORICAL_NODES)) == 4
    assert provenance["retained_active_node_count"] == 4

    assert bridge["post_acceptance_audit_tests_sha256"] == provenance["audit_sha256"]
    assert (
        bridge["pytest_transition_hook_sha256"]
        == provenance["historical_pytest_hook_sha256"]
        == "e931ec84186da7f06e1ab6ceea909bb01647acb3de01bb60b539e22d5848727a"
    )
    # The D-140 hook is authorized to differ. This test deliberately never hashes
    # the live tests/conftest.py, so it is valid before and after the transition.
    assert provenance["live_hook_hash_must_equal_historical_after_transition"] is False


def test_exact_d140_replacement_nodes_are_frozen_for_each_historical_node() -> None:
    value = _load(CONTRACT)["d140_replacement_evidence"]
    transition_map = value["exact_transition_map"]

    # D-139 is independently integrable before the D-140 implementation path
    # exists. The future focused suite must bind this contract and prove these
    # exact definitions when D-140 is packaged.
    assert value["focused_tests_path"] == D140_FOCUSED_PATH
    assert value["replacement_node_ids"] == REPLACEMENT_NODES
    assert value["replacement_node_count"] == len(REPLACEMENT_NODES) == 3
    assert len(_node_function_names(REPLACEMENT_NODES)) == 3
    assert all(
        name.startswith("test_") for name in _node_function_names(REPLACEMENT_NODES)
    )
    assert [item["historical_node_id"] for item in transition_map] == HISTORICAL_NODES
    assert [item["replacement_node_id"] for item in transition_map] == (
        REPLACEMENT_NODES
    )
    assert len({item["historical_node_id"] for item in transition_map}) == 3
    assert len({item["replacement_node_id"] for item in transition_map}) == 3
    assert all(item["replacement_scope"] for item in transition_map)


def test_future_hook_markers_and_lineage_bindings_are_exact_and_narrow() -> None:
    value = _load(CONTRACT)
    transition = value["future_collection_transition"]
    bindings = value["future_transition_bindings"]

    assert transition == {
        "only_existing_file_with_transition_specific_behavior_change": (
            "tests/conftest.py"
        ),
        "collection_constant": "_PRE_D140_ORCHESTRATION_STATE_NODES",
        "marker_kind": "pytest.mark.skip",
        "exact_markers": [
            {
                "node_id": HISTORICAL_NODES[0],
                "reason": (
                    "historical D-136 live-driver binding; D-140 historical/"
                    "composite-lineage test owns current-state validation"
                ),
            },
            {
                "node_id": HISTORICAL_NODES[1],
                "reason": (
                    "historical D-136 live-hook/driver binding; D-140 two-order "
                    "composite test owns current-state validation"
                ),
            },
            {
                "node_id": HISTORICAL_NODES[2],
                "reason": (
                    "historical D-136 pre-composite claim derivation; D-140 "
                    "five-field derivation test owns current-state validation"
                ),
            },
        ],
        "existing_d136_pre_acceptance_skip_is_preserved": True,
        "deselect_or_xfail_allowed": False,
        "additional_retired_nodes_allowed": False,
    }
    assert bindings["field_name"] == "d139_test_transition_contract_sha256"
    assert bindings["binding_only_no_behavior_change"] is True
    assert [item["path"] for item in bindings["locations"]] == [
        "research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py",
        "research/maplight-fixed/run_global_v2_maplight_robustness_official_"
        "orchestration_acceptance.py",
        "benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_official_"
        "orchestration_acceptance.json",
        "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py",
    ]
    assert all(item["required_binding"] for item in bindings["locations"])


def test_claim_science_and_historical_files_remain_immutable_with_zero_authority() -> (
    None
):
    value = _load(CONTRACT)
    immutable = value["immutable_boundary"]
    accounting = value["current_milestone_accounting"]

    # The tracked claim is intentionally not opened by this contract test. Its
    # immutable hash is inherited independently from D-137 and D-138.
    assert immutable["tracked_claim"] == {
        "path": (
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_claim_v2.json"
        ),
        "sha256": "d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f",
        "mutation_allowed": False,
    }
    d137 = _load(
        BENCHMARK
        / "global_v2_maplight_robustness_official_orchestration_repair_contract.json"
    )
    d138 = _load(
        BENCHMARK
        / "global_v2_maplight_robustness_official_orchestration_seal_erratum.json"
    )
    assert (
        d137["immutable_parent_evidence"]["tracked_unconsumed_claim_v2"]["sha256"]
        == d138["parents"]["tracked_claim_sha256"]
        == immutable["tracked_claim"]["sha256"]
    )

    for name in (
        "historical_formal_acceptance_driver",
        "historical_formal_focused_tests",
    ):
        evidence = immutable[name]
        assert evidence["mutation_allowed"] is False
        assert _sha256(ROOT / evidence["path"]) == evidence["sha256"]
    science = immutable["science_kernel"]
    assert science["mutation_allowed"] is False
    for name, evidence in science.items():
        if name == "mutation_allowed":
            continue
        assert _sha256(ROOT / evidence["path"]) == evidence["sha256"]

    assert accounting["pytest_collection_markers_added"] == 0
    assert all(value == 0 for value in accounting.values())
    assert all(authority is False for authority in value["current_authority"].values())
