from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_source_shape_"
    "transition_contract.json"
)
CONTRACT_SHA256 = "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
D134_FOCUSED = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
)
D141_FOCUSED_PATH = (
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
)

HISTORICAL_NODES = [
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_exact_fit_topology_and_conditional_stage_c_are_unchanged"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_supervisor_starts_before_claim_consumption_and_official_"
        "access"
    ),
]
REPLACEMENT_NODES = [
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_corrected_child_preserves_fit_topology_and_"
        "cleans_before_terminal_staging"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_supervisor_precedes_claim_consumption_and_common_"
        "seal_owns_terminal_publication"
    ),
]
REPLACEMENT_SCOPES = [
    (
        "prove Stage A=540, Stage B=180, and conditional Stage C=300 fit "
        "identities; exact selection feature widths G2-7-M0-FULL=2563, "
        "G2-7-M1-DROP-MORGAN=1539, G2-7-M2-DROP-AVALON=1539, "
        "G2-7-M3-DROP-ERG=2248, and G2-7-M4-DROP-DESCRIPTORS=2363; both "
        "predictor-authority cross rejections for synthetic=True with "
        "real_catboost_predictor and synthetic=False with "
        "deterministic_test_predictor; Stage A -> selection -> Stage B -> "
        'conditional Stage C chronology with exact condition selected != "G2-7-'
        'M0-FULL"; and corrected source chronology '
        "_terminal_bytes -> _cleanup_owned_root(work) -> _stage_payload(files)"
    ),
    (
        "prove run_supervised is present in run_official_attempt and "
        "_consume_claim is absent from run_official_attempt; child chronology "
        "resource_checkpoint -> "
        "derive_consumed_claim -> _consume_claim -> compile_capabilities -> "
        "Stage A; exact raw_observed = supervisor.run_supervised assignment; "
        "exact publication_root=PUBLICATION_STAGING_ROOT and "
        "writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent supervisor "
        "arguments; "
        "official.LIMITS == acceptance.LIMITS; OFFICIAL_ATTEMPT_ROOT == "
        "/home/zbos/cypshift-private/openadmet-2026/g2-7g-maplight-robustness-"
        "development-attempt-1 and that root is absent; _failure_payload "
        "contains accounting_complete and returns aggregate bytes only with no "
        "terminal path or publication; outer "
        "chronology run_supervised -> _seal_with_fallback places the common seal "
        "after supervision and makes it the exclusive terminal publisher; and "
        "_finalize_terminal is absent from run_official_attempt while "
        "PENDING_TERMINAL_ROOT is absent from the child"
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


def test_contract_identity_signed_base_and_exact_two_file_surface() -> None:
    value = _load(CONTRACT)
    assert _sha256(CONTRACT) == CONTRACT_SHA256
    assert value["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_official_"
        "orchestration_source_shape_transition_contract.v1"
    )
    assert value["decision_id"] == "D-140"
    assert value["gate"] == (
        "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_SOURCE_SHAPE_"
        "TRANSITION_CONTRACT_FROZEN"
    )
    assert value["status"] == (
        "contract_only_no_source_shape_retirement_or_d141_integration_or_"
        "acceptance_or_official_execution_yet"
    )
    assert value["base_commit"] == "3b9c251f6875fedb33e51c4420cd8634c6e4cf29"
    assert value["base_commit_signature_verified"] is True
    assert value["base_commit_signer"] == (
        "261114960+zchboswell@users.noreply.github.com"
    )
    assert value["contract_package"] == {
        "new_files": [
            "benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_"
            "official_orchestration_source_shape_transition_contract.json",
            "tests/test_openadmet_global_v2_maplight_robustness_official_"
            "orchestration_source_shape_transition_contract.py",
        ],
        "existing_production_or_test_collection_files_changed_by_contract_freeze": 0,
    }


def test_d137_through_d139_parent_hashes_and_commits_are_exact() -> None:
    parents = _load(CONTRACT)["parent_evidence"]
    expected = {
        "d137_official_orchestration_repair_contract": (
            "f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967",
            "0dbbc7013b5303ef2f1535455d458b87208df1b9",
        ),
        "d138_terminal_seal_erratum": (
            "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33",
            "158dffcadfb71305d7de7b84279cfee96a6e8318",
        ),
        "d139_test_provenance_transition_contract": (
            "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c",
            "3b9c251f6875fedb33e51c4420cd8634c6e4cf29",
        ),
    }
    assert set(parents) == set(expected)
    for name, (digest, commit) in expected.items():
        evidence = parents[name]
        assert _sha256(ROOT / evidence["path"]) == evidence["sha256"] == digest
        assert evidence["integrated_commit"] == commit


def test_immutable_d134_snapshot_retires_exactly_two_source_shape_nodes() -> None:
    provenance = _load(CONTRACT)["historical_source_shape_provenance"]
    snapshot_tests = _test_names(D134_FOCUSED)

    assert (
        provenance["focused_snapshot_path"] == D134_FOCUSED.relative_to(ROOT).as_posix()
    )
    assert (
        _sha256(D134_FOCUSED)
        == provenance["focused_snapshot_sha256"]
        == "3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f"
    )
    assert (
        len(snapshot_tests) == provenance["focused_snapshot_test_function_count"] == 9
    )
    assert provenance["focused_snapshot_mutation_allowed"] is False
    assert provenance["newly_retired_node_ids"] == HISTORICAL_NODES
    assert provenance["newly_retired_node_count"] == len(HISTORICAL_NODES) == 2
    assert _node_function_names(HISTORICAL_NODES) < snapshot_tests
    assert provenance["previously_retired_node_count_in_snapshot"] == 1
    assert provenance["retained_active_node_count_after_transition"] == 6
    assert 9 - 1 - len(HISTORICAL_NODES) == 6


def test_exact_d141_replacements_are_frozen_but_need_not_exist_yet() -> None:
    value = _load(CONTRACT)["d141_replacement_evidence"]
    transition_map = value["exact_transition_map"]

    # D-140 must remain independently integrable before the future D-141
    # implementation nodes or path exist. This test therefore validates only
    # the frozen identifiers and never reads the live future focused file.
    assert value["focused_tests_path"] == D141_FOCUSED_PATH
    assert value["replacement_node_ids"] == REPLACEMENT_NODES
    assert value["replacement_node_count"] == len(REPLACEMENT_NODES) == 2
    assert value["future_nodes_may_be_absent_during_contract_freeze"] is True
    assert len(_node_function_names(REPLACEMENT_NODES)) == 2
    assert all(
        name.startswith("test_") for name in _node_function_names(REPLACEMENT_NODES)
    )
    assert [item["historical_node_id"] for item in transition_map] == (HISTORICAL_NODES)
    assert [item["replacement_node_id"] for item in transition_map] == (
        REPLACEMENT_NODES
    )
    assert len({item["historical_node_id"] for item in transition_map}) == 2
    assert len({item["replacement_node_id"] for item in transition_map}) == 2
    assert [item["replacement_scope"] for item in transition_map] == (
        REPLACEMENT_SCOPES
    )


def test_future_hook_adds_only_two_markers_and_preserves_prior_four() -> None:
    value = _load(CONTRACT)
    transition = value["future_collection_transition"]
    d139 = _load(
        BENCHMARK / "global_v2_maplight_robustness_official_orchestration_test_"
        "transition_contract.json"
    )

    assert transition == {
        "only_existing_file_with_transition_specific_behavior_change": (
            "tests/conftest.py"
        ),
        "collection_constant": "_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES",
        "marker_kind": "pytest.mark.skip",
        "exact_new_markers": [
            {
                "node_id": HISTORICAL_NODES[0],
                "reason": (
                    "historical D-134 child terminal-shape assertion; D-141 "
                    "corrected child cleanup/staging test owns current-state "
                    "validation"
                ),
            },
            {
                "node_id": HISTORICAL_NODES[1],
                "reason": (
                    "historical D-134 parent terminal-shape assertion; D-141 "
                    "supervised common-seal test owns current-state validation"
                ),
            },
        ],
        "previously_frozen_skip_count": 4,
        "expected_total_skip_count_after_transition": 6,
        "previous_d134_pre_acceptance_skip_is_preserved": True,
        "previous_d139_three_node_transition_is_preserved": True,
        "deselect_or_xfail_allowed": False,
        "additional_retired_nodes_allowed": False,
    }
    assert d139["historical_test_provenance"]["retired_node_count"] == 3
    assert (
        d139["future_collection_transition"][
            "existing_d136_pre_acceptance_skip_is_preserved"
        ]
        is True
    )
    assert 1 + d139["historical_test_provenance"]["retired_node_count"] == 4
    # Do not hash or parse live conftest.py: the contract is valid both before
    # and after D-141 applies the exact six-marker collection state.


def test_future_provenance_bindings_are_exact_and_non_scientific() -> None:
    bindings = _load(CONTRACT)["future_transition_bindings"]
    assert bindings["field_name"] == ("d140_source_shape_transition_contract_sha256")
    assert bindings["binding_only_no_scientific_behavior_change"] is True
    assert [item["path"] for item in bindings["locations"]] == [
        "research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py",
        "research/maplight-fixed/run_global_v2_maplight_robustness_official_"
        "orchestration_acceptance.py",
        "benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_official_"
        "orchestration_acceptance.json",
        "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py",
    ]
    assert all(item["required_binding"] for item in bindings["locations"])


def test_contract_has_zero_collection_science_claim_gate_or_run_authority() -> None:
    value = _load(CONTRACT)
    immutable = value["immutable_boundary"]
    accounting = value["current_milestone_accounting"]

    # The tracked claim is deliberately not opened. Its immutable digest is
    # inherited from the independently accepted D-137 through D-139 lineage.
    assert immutable["tracked_claim"] == {
        "path": (
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_claim_v2.json"
        ),
        "sha256": "d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f",
        "mutation_allowed": False,
    }
    assert immutable["historical_focused_snapshot"] == {
        "path": (
            "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
        ),
        "sha256": "3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f",
        "mutation_allowed": False,
    }
    assert immutable["science_kernel_mutation_allowed"] is False
    assert immutable["claim_mutation_allowed"] is False
    assert immutable["gate_mutation_allowed"] is False
    assert accounting["pytest_collection_markers_added"] == 0
    assert accounting["implementation_files_changed"] == 0
    assert all(count == 0 for count in accounting.values())
    assert all(authority is False for authority in value["current_authority"].values())
