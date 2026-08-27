from __future__ import annotations

import ast
import hashlib
import json
import runpy
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_post_attempt_test_transition_contract.json"
)
CONTRACT_SHA256 = "d5eb773fc2584deaf31c5f3a3a283e365b6540d0c714fd08cb70ec02937b735f"
CONFTEST = ROOT / "tests/conftest.py"

D133_TEST = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_execution_contract_v2.py"
)
D141_TEST = (
    ROOT
    / "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
)
D142_TEST = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_acceptance_record.py"
)
D143_RECORD = BENCHMARK / "global_v2_maplight_robustness_official_underpowered.json"
HISTORICAL_CONFTEST_SHA256 = (
    "03d92bf3a2890a61190a6a4fc7a6bc59fa900ed6ea4b904223b1f2f991699d95"
)

HISTORICAL_SHA256 = {
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_execution_contract_v2.json": (
        "9464b0947255298a8de8836af6178857841bb2a55bc5c0f4897be2ba91151bcf"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_"
    "test_transition_contract.json": (
        "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_"
    "source_shape_transition_contract.json": (
        "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_orchestration_acceptance.json": (
        "92a18f0e6837d70d4bb39560d42a22cfb23acac8ea72a955b9656b392d954596"
    ),
    "benchmarks/openadmet_cyp_2026/"
    "global_v2_maplight_robustness_official_underpowered.json": (
        "d52bee5e4ed4669c6db7e3061fc8aed8f55e81a0e4d3d17aca73e326df184a2d"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_execution_contract_v2.py": (
        "b499097be50618d119eceaf2e92d18ff737872b565ed9b18474541e9ee439f7a"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py": (
        "f17b5b2f39b92892b046f289d6ebdb1888d705ea7a27ea24b3ca3013d39289b0"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_"
    "official_orchestration_acceptance_record.py": (
        "10ebb8f18d38f6d069e35d3994468e6a70dc0de3df6cb5736352721be439a28c"
    ),
    "tests/test_openadmet_global_v2_maplight_robustness_official_underpowered.py": (
        "e5d65bf32a9185ea3c3c63bb658d5418e8393ec534488f50cbeb4dad1a8354ce"
    ),
}

PREVIOUS_MARKERS = {
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_formal_acceptance_is_fixed_unrun_and_has_zero_authority"
    ): (
        "historical D-134 pre-acceptance state assertion; D-135 receipt audits "
        "now own current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_acceptance_binds_exact_contract_and_integrated_"
        "implementation"
    ): (
        "historical D-136 live-driver binding; D-140 historical/"
        "composite-lineage test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_provenance_bridge_retires_only_the_obsolete_pre_"
        "acceptance_state"
    ): (
        "historical D-136 live-hook/driver binding; D-140 two-order composite "
        "test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_claim_derivation_is_read_only_and_fills_exactly_"
        "five_receipts"
    ): (
        "historical D-136 pre-composite claim derivation; D-140 five-field "
        "derivation test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_exact_fit_topology_and_conditional_stage_c_are_unchanged"
    ): (
        "historical D-134 child terminal-shape assertion; D-141 corrected child "
        "cleanup/staging test owns current-state validation"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_supervisor_starts_before_claim_consumption_and_official_"
        "access"
    ): (
        "historical D-134 parent terminal-shape assertion; D-141 supervised "
        "common-seal test owns current-state validation"
    ),
}

NEW_MARKERS = {
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_contract_"
        "v2.py::test_new_attempt_root_is_distinct_and_absent_at_freeze"
    ): (
        "historical D-133 pre-attempt root-absence node; D-143 terminal and "
        "D-145 public transition audit own current post-attempt state"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_supervisor_precedes_claim_consumption_and_common_"
        "seal_owns_terminal_publication"
    ): (
        "historical D-141 pre-attempt root-absence node; D-142 mechanics and "
        "D-143 terminal plus D-145 public transition audit own surviving semantics"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_d140_source_shape_collection_has_six_exact_skips_"
        "and_active_replacements"
    ): (
        "historical D-140 six-marker collection node; D-145 public transition "
        "audit owns the exact ten-marker state"
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration_acceptance_record.py::test_formal_orchestration_"
        "acceptance_record_is_exact_and_static"
    ): (
        "historical D-142 live-conftest-hash node; D-145 public transition audit "
        "preserves D-142 receipt provenance and owns the new live hook"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_nonfinite(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _load_strict(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    value = cast(
        dict[str, Any],
        json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        ),
    )
    return raw, value


def _load_canonical(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw, value = _load_strict(path)
    assert raw == _canonical_bytes(value)
    return raw, value


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1
    segment = ast.get_source_segment(source, matches[0])
    assert segment is not None
    return segment


def _all_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [
            string
            for key, item in value.items()
            for string in [str(key), *_all_strings(item)]
        ]
    if isinstance(value, list):
        return [string for item in value for string in _all_strings(item)]
    return []


def test_post_attempt_test_transition_contract_is_exact_and_static() -> None:
    raw, contract = _load_canonical(CONTRACT)
    assert hashlib.sha256(raw).hexdigest() == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_post_attempt_"
        "test_transition_contract.v1"
    )
    assert contract["decision_id"] == "D-144"
    assert contract["gate"] == (
        "G2_7G_MAPLIGHT_ROBUSTNESS_POST_ATTEMPT_TEST_TRANSITION_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_only_no_collection_change_or_d145_implementation_yet"
    )
    assert contract["base_commit"] == ("d630702074bfefa4bda4730ba7c1b7519c3c6f1a")
    assert contract["base_commit_signature_verified"] is True
    assert contract["base_commit_signer"] == (
        "261114960+zchboswell@users.noreply.github.com"
    )

    package = contract["contract_package"]
    assert package == {
        "contract_core_new_files": [
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_post_attempt_test_transition_contract.json",
            "tests/test_openadmet_global_v2_maplight_robustness_post_attempt_"
            "test_transition_contract.py",
        ],
        "existing_collection_or_historical_test_files_changed": 0,
        "knowledgebase_and_ledger_files": [
            "benchmarks/openadmet_cyp_2026/README.md",
            "docs/phases/README.md",
            "docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md",
            "docs/strategy/DECISIONS.md",
            "docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md",
            "docs/strategy/PROJECT_STATE.md",
            "runs/experiment_ledger.csv",
        ],
        "total_milestone_files": 9,
    }

    d143 = contract["parent_evidence"]["d143_underpowered_evidence"]
    assert d143 == {
        "audit_path": (
            "tests/test_openadmet_global_v2_maplight_robustness_official_"
            "underpowered.py"
        ),
        "audit_sha256": (
            "e5d65bf32a9185ea3c3c63bb658d5418e8393ec534488f50cbeb4dad1a8354ce"
        ),
        "integrated_commit": "d630702074bfefa4bda4730ba7c1b7519c3c6f1a",
        "post_main_ci_run": 33122070763,
        "pr_ci_run": 33121287357,
        "pr_number": 180,
        "record_path": (
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_official_underpowered.json"
        ),
        "record_sha256": (
            "d52bee5e4ed4669c6db7e3061fc8aed8f55e81a0e4d3d17aca73e326df184a2d"
        ),
        "signature_verified": True,
    }
    assert contract["safe_suite_evidence"] == {
        "command": (
            "uv run --locked pytest "
            "--ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py"
        ),
        "failed": 2,
        "passed": 1425,
        "permanently_barred_test_ignored": (
            "tests/test_openadmet_global_v2_maplight_robustness_synthetic.py"
        ),
        "pytest_seconds": 357.51,
        "skipped": 10,
    }
    assert all(
        value == 0 for value in contract["current_milestone_accounting"].values()
    )
    assert all(value is False for value in contract["current_authority"].values())
    assert contract["privacy_boundary"] == {
        "absolute_private_paths_allowed": False,
        "driver_import_or_execution_allowed": False,
        "protected_root_lstat_listing_or_hashing_allowed": False,
        "public_repository_files_only": True,
        "row_level_values_allowed": False,
    }
    assert contract["immutable_boundary"] == {
        "d143_evidence_mutation_allowed": False,
        "driver_mutation_allowed": False,
        "historical_test_mutation_allowed": False,
        "one_use_gate_mutation_or_reexecution_allowed": False,
        "science_kernel_mutation_allowed": False,
        "tracked_claim_mutation_allowed": False,
    }
    tracked_claim = contract["parent_evidence"]["d133_tracked_public_claim"]
    assert tracked_claim == {
        "path": (
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_claim_v2.json"
        ),
        "sha256": ("d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f"),
    }
    assert contract["parent_evidence"]["historical_conftest"] == {
        "path": "tests/conftest.py",
        "sha256": HISTORICAL_CONFTEST_SHA256,
    }

    for relative_path, expected_sha256 in HISTORICAL_SHA256.items():
        assert _sha256(ROOT / relative_path) == expected_sha256

    provenance = contract["historical_test_provenance"]
    assert provenance["current_failure_node_ids"] == list(NEW_MARKERS)[:2]
    assert provenance["future_transition_node_ids"] == list(NEW_MARKERS)
    assert provenance["pass_now_future_transition_node_ids"] == list(NEW_MARKERS)[2:]
    assert provenance["retired_node_count"] == 4
    assert provenance["historical_files"] == [
        {
            "mutation_allowed": False,
            "path": D133_TEST.relative_to(ROOT).as_posix(),
            "sha256": HISTORICAL_SHA256[D133_TEST.relative_to(ROOT).as_posix()],
        },
        {
            "mutation_allowed": False,
            "path": D141_TEST.relative_to(ROOT).as_posix(),
            "sha256": HISTORICAL_SHA256[D141_TEST.relative_to(ROOT).as_posix()],
        },
        {
            "mutation_allowed": False,
            "path": D142_TEST.relative_to(ROOT).as_posix(),
            "sha256": HISTORICAL_SHA256[D142_TEST.relative_to(ROOT).as_posix()],
        },
    ]
    assert provenance["node_responsibilities"] == [
        {
            "node_id": list(NEW_MARKERS)[0],
            "stale_responsibility": (
                "live absence after a contract that accurately recorded absence "
                "at freeze"
            ),
            "state": "fails_now",
        },
        {
            "node_id": list(NEW_MARKERS)[1],
            "stale_responsibility": (
                "live pre-attempt root absence inside otherwise valid supervision "
                "and common-seal mechanics"
            ),
            "state": "fails_now",
        },
        {
            "node_id": list(NEW_MARKERS)[2],
            "stale_responsibility": (
                "six-marker total and active status of the pre-attempt replacement node"
            ),
            "state": "passes_now_becomes_historical_after_d145",
        },
        {
            "node_id": list(NEW_MARKERS)[3],
            "stale_responsibility": (
                "live equality to the historical D-141 conftest hash"
            ),
            "state": "passes_now_becomes_historical_after_d145",
        },
    ]

    d133_source = _function_source(
        D133_TEST, "test_new_attempt_root_is_distinct_and_absent_at_freeze"
    )
    for fragment in (
        "old_root = _load(D127_CLAIM_PATH)",
        'official["attempt_root_absent_at_freeze"] is True',
        'official["attempt_root"].endswith(',
        '"g2-7g-maplight-robustness-development-attempt-1"',
        'official["attempt_root"] != old_root',
        'claim["fixed_roots"] == {',
        '"development_source_root"',
        '"fixed_baseline_terminal_root"',
        '"attempt_root"',
        'Path(official["attempt_root"]).exists()',
        '"does not list, parse, copy, link, hash" in official["read_boundary"]',
    ):
        assert fragment in d133_source

    d141_source = _function_source(
        D141_TEST,
        "test_supervisor_precedes_claim_consumption_and_common_seal_owns_"
        "terminal_publication",
    )
    for fragment in (
        "_assert_d140_source_shape_replacement_responsibility(1)",
        'assert "run_supervised" in outer',
        'assert "_consume_claim" not in outer',
        'child.index("resource_checkpoint") < child.index("derive_consumed_claim")',
        'child.index("derive_consumed_claim") < child.index("_consume_claim")',
        'child.index("_consume_claim") < child.index("compile_capabilities")',
        'child.index("compile_capabilities") < child.index(\'stage="stage_a"\')',
        'assert "raw_observed = supervisor.run_supervised" in outer',
        'assert "publication_root=PUBLICATION_STAGING_ROOT" in outer',
        'assert "writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent" in outer',
        "assert official.LIMITS == historical_acceptance.LIMITS",
        "assert official.OFFICIAL_ATTEMPT_ROOT == Path(",
        '"g2-7g-maplight-robustness-development-attempt-1"',
        "assert not official.OFFICIAL_ATTEMPT_ROOT.exists()",
        'assert "accounting_complete" in failure_source',
        "assert 'return {\"manifest.json\": maplight.json_bytes(manifest)}' in "
        "failure_source",
        'assert "terminal_root" not in failure_source',
        'assert "_stage_payload" not in failure_source',
        'assert "_seal_with_fallback" not in failure_source',
        'assert set(failure_files) == {"manifest.json"}',
        "assert all(isinstance(payload, bytes) for payload in failure_files.values())",
        'outer.index("run_supervised") < outer.index("_seal_with_fallback")',
        'assert "_finalize_terminal" not in outer',
        'assert "PENDING_TERMINAL_ROOT" not in child',
    ):
        assert fragment in d141_source

    d140_collection_source = _function_source(
        D141_TEST,
        "test_d140_source_shape_collection_has_six_exact_skips_and_active_replacements",
    )
    for fragment in (
        'transition["expected_total_skip_count_after_transition"] == 6',
        'namespace["_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES"]',
        "assert observed_skips == expected_skips",
        "assert len(observed_skips) == 6",
        "assert all(not probes[node_id].markers for node_id in replacements)",
        "assert all(not probes[node_id].markers for node_id in unrelated)",
    ):
        assert fragment in d140_collection_source

    d142_source = D142_TEST.read_text(encoding="utf-8")
    d142_tree = ast.parse(d142_source, filename=str(D142_TEST))
    conftest_hashes = [
        node.value
        for node in ast.walk(d142_tree)
        if isinstance(node, ast.Constant) and node.value == HISTORICAL_CONFTEST_SHA256
    ]
    assert conftest_hashes == [HISTORICAL_CONFTEST_SHA256]
    d142_audit_source = _function_source(
        D142_TEST, "test_formal_orchestration_acceptance_record_is_exact_and_static"
    )
    assert "for relative_path, expected_sha256 in LIVE_SHA256.items()" in (
        d142_audit_source
    )
    assert "assert _sha256(ROOT / relative_path) == expected_sha256" in (
        d142_audit_source
    )

    transition = contract["future_collection_transition"]
    prior = {
        item["node_id"]: item["reason"] for item in transition["previous_exact_markers"]
    }
    future = {
        item["node_id"]: item["reason"] for item in transition["exact_new_markers"]
    }
    assert prior == PREVIOUS_MARKERS
    assert future == NEW_MARKERS
    assert prior.keys().isdisjoint(future)
    assert transition["previous_exact_skip_count"] == len(prior) == 6
    assert (
        transition["expected_total_skip_count_after_transition"]
        == (len(prior) + len(future))
        == 10
    )
    assert transition["collection_constant"] == "_PRE_D145_POST_ATTEMPT_STATE_NODES"
    assert transition["marker_kind"] == "pytest.mark.skip"
    assert transition["deselect_or_xfail_allowed"] is False
    assert transition["additional_retired_nodes_allowed"] is False
    assert transition["future_conftest_sha256"] is None

    replacement = transition["future_replacement_audit"]
    assert replacement["future_path"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_post_attempt_"
        "test_transition.py"
    )
    assert replacement["node_id"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_post_attempt_"
        "test_transition.py::test_d145_post_attempt_collection_has_ten_exact_"
        "skips_and_complete_replacement_evidence"
    )
    assert replacement["future_sha256"] is None
    assert replacement["required_at_contract_freeze"] is False
    assert replacement["test_node_count"] == 1
    assert replacement["required_assertions"] == [
        (
            "authenticate the exact integrated D-144 contract and immutable D-133 "
            "D-140 D-141 D-142 and D-143 public hashes without importing or "
            "executing a driver"
        ),
        (
            "preserve the D-133 historical official.attempt_root_absent_at_"
            "freeze=true field as frozen provenance while statically proving the "
            "corrected attempt-root suffix g2-7g-maplight-robustness-development-"
            "attempt-1 its exact distinction from the barred D-127 root the "
            "tracked public claim fixed-root mapping for development_source_root "
            "fixed_baseline_terminal_root and attempt_root and the frozen read "
            "boundary text does not list parse copy link or hash without any live "
            "private-path probe"
        ),
        (
            "preserve the D-141 binding that D-140 owns the source-shape transition "
            "and statically prove outer run_supervised with no outer _consume_claim "
            "child resource_checkpoint -> derive_consumed_claim -> _consume_claim "
            "-> compile_capabilities -> Stage A chronology exact raw_observed = "
            "supervisor.run_supervised assignment exact publication_root="
            "PUBLICATION_STAGING_ROOT and writable_publication_parent="
            "OFFICIAL_ATTEMPT_ROOT.parent arguments official.LIMITS == "
            "historical_acceptance.LIMITS fixed OFFICIAL_ATTEMPT_ROOT identity "
            "aggregate-only _failure_payload accounting and accounting_complete "
            "run_supervised -> _seal_with_fallback common-seal exclusivity and "
            "absence of obsolete parent _finalize_terminal and child "
            "PENDING_TERMINAL_ROOT symbols without any live private-path probe"
        ),
        (
            "prove the six prior markers remain exact and the four new markers are "
            "exact disjoint one-time skips for ten total; unrelated nodes and the "
            "sole D-145 comprehensive replacement audit remain active; all prior "
            "replacement nodes remain active except the exact D-141 supervisor "
            "node explicitly transitioned here"
        ),
        (
            "preserve every historical test byte and treat the D-142 conftest hash "
            "as historical while binding the new live conftest independently"
        ),
        (
            "prove the D-143 public terminal remains one consumed private attempt "
            "one unchanged unconsumed public template exact two-entry and three-"
            "entry terminal shapes complete cleanup null candidate zero token and "
            "zero downstream authority"
        ),
        (
            "use only public repository files and perform no protected-path "
            "existence listing hashing import execution or row-level access"
        ),
    ]

    _, d139_contract = _load_strict(
        BENCHMARK / "global_v2_maplight_robustness_official_orchestration_"
        "test_transition_contract.json"
    )
    _, d140_contract = _load_strict(
        BENCHMARK / "global_v2_maplight_robustness_official_orchestration_"
        "source_shape_transition_contract.json"
    )
    prior_replacement_nodes = {
        item["replacement_node_id"]
        for item in [
            *d139_contract["d140_replacement_evidence"]["exact_transition_map"],
            *d140_contract["d141_replacement_evidence"]["exact_transition_map"],
        ]
    }
    transitioned_supervisor_node = list(NEW_MARKERS)[1]
    assert len(prior_replacement_nodes) == 5
    assert transitioned_supervisor_node in prior_replacement_nodes

    namespace = runpy.run_path(str(CONFTEST))
    d145_constant = transition["collection_constant"]
    post_d145 = d145_constant in namespace
    expected_constant_names = {
        "_PRE_ACCEPTANCE_STATE_NODE",
        "_PRE_D140_ORCHESTRATION_STATE_NODES",
        "_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES",
        *({d145_constant} if post_d145 else set()),
    }
    assert {
        name for name in namespace if name.startswith("_PRE_")
    } == expected_constant_names
    observed_constants = {
        cast(str, namespace["_PRE_ACCEPTANCE_STATE_NODE"]): PREVIOUS_MARKERS[
            cast(str, namespace["_PRE_ACCEPTANCE_STATE_NODE"])
        ],
        **cast(dict[str, str], namespace["_PRE_D140_ORCHESTRATION_STATE_NODES"]),
        **cast(
            dict[str, str],
            namespace["_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES"],
        ),
    }
    if post_d145:
        observed_future = cast(dict[str, str], namespace[d145_constant])
        assert observed_future == NEW_MARKERS
        observed_constants.update(observed_future)
        assert observed_constants == {**PREVIOUS_MARKERS, **NEW_MARKERS}
    else:
        assert _sha256(CONFTEST) == HISTORICAL_CONFTEST_SHA256
        assert observed_constants == PREVIOUS_MARKERS

    class ProbeItem:
        def __init__(self, nodeid: str) -> None:
            self.nodeid = nodeid
            self.markers: list[Any] = []

        def add_marker(self, marker: Any) -> None:
            self.markers.append(marker)

    unrelated = "tests/alternate.py::test_uncontracted_post_attempt_node"
    d145_audit_node = cast(str, replacement["node_id"])
    probes = {
        node_id: ProbeItem(node_id)
        for node_id in {
            *PREVIOUS_MARKERS,
            *NEW_MARKERS,
            *prior_replacement_nodes,
            d145_audit_node,
            unrelated,
        }
    }
    hook = namespace["pytest_collection_modifyitems"]
    assert callable(hook)
    hook(list(probes.values()))
    observed_skips = {
        node_id for node_id, probe in probes.items() if len(probe.markers) == 1
    }
    expected_markers = {
        **PREVIOUS_MARKERS,
        **(NEW_MARKERS if post_d145 else {}),
    }
    assert observed_skips == expected_markers.keys()
    for node_id, reason in expected_markers.items():
        marker = probes[node_id].markers[0].mark
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": reason}

    if post_d145:
        assert len(observed_skips) == 10
        d145_audit_path = ROOT / cast(str, replacement["future_path"])
        assert d145_audit_path.is_file()
        d145_source = d145_audit_path.read_text(encoding="utf-8")
        d145_tree = ast.parse(d145_source, filename=str(d145_audit_path))
        d145_tests = [
            node
            for node in d145_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        assert [node.name for node in d145_tests] == [
            d145_audit_node.rsplit("::", 1)[1]
        ]
        assert d145_tests[0].decorator_list == []
    else:
        assert len(observed_skips) == 6
        assert all(not probes[node_id].markers for node_id in NEW_MARKERS)

    active_prior_replacements = prior_replacement_nodes - (
        {transitioned_supervisor_node} if post_d145 else set()
    )
    assert all(not probes[node_id].markers for node_id in active_prior_replacements)
    assert not probes[d145_audit_node].markers
    assert not probes[unrelated].markers

    record_raw, record = _load_canonical(D143_RECORD)
    assert (
        hashlib.sha256(record_raw).hexdigest()
        == (HISTORICAL_SHA256[D143_RECORD.relative_to(ROOT).as_posix()])
    )
    assert record["status"] == "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED"
    assert record["attempt"] == {
        "claim_id": "g2-7g-maplight-robustness-development-attempt-1",
        "consumptions": 1,
        "maximum_consumptions": 1,
        "official_attempts_completed": 1,
        "usable": False,
    }
    assert record["tracked_public_claim_template"] == {
        "bytes_unchanged": True,
        "consumptions": 0,
        "maximum_consumptions": 1,
        "sha256": tracked_claim["sha256"],
        "status": "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED",
        "usable": False,
    }
    assert record["terminal"]["attempt_file_set"] == [
        "attempt_claim.json",
        "terminal",
    ]
    assert record["terminal"]["terminal_file_set"] == [
        "attempt_receipt.json",
        "manifest.json",
        "preflight.json",
    ]
    assert record["terminal"]["selected_candidate"] is None
    assert record["terminal"]["selection_tokens"] == 0
    assert record["cleanup"]["cleanup_complete"] is True
    assert record["scientific_result"]["full_maplight_selected_by_this_attempt"] is (
        False
    )
    assert record["scientific_result"]["model_quality_result"] is None
    assert record["contract_interpretation"]["confirmatory_authorized"] is False
    assert record["contract_interpretation"][
        "full_maplight_retained_by_default_rule"
    ] is (False)
    assert record["contract_interpretation"]["scientific_path_terminal"] is True
    assert all(value is False for value in record["future_authority_created"].values())
    assert all(value == 0 for value in record["privacy"].values())
    assert all("/home/" not in value for value in _all_strings(record))
    assert all("cypshift-private" not in value for value in _all_strings(record))

    progression = contract["progression_rule"]
    assert "green exact-SHA post-main CI before D-145" in progression
    assert "change only tests/conftest.py" in progression
    assert "grant no G2-8" in progression
    assert "submission" in progression
    assert "upload authority" in progression
