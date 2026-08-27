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
CONFTEST = ROOT / "tests/conftest.py"
D144_CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_post_attempt_test_transition_contract.json"
)
D144_CONTRACT_TEST = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_post_attempt_"
    "test_transition_contract.py"
)
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

D144_REVIEW = {
    "integrated_commit": "5d7ed5db76ec0928ba34e19e72ab839ee556d51e",
    "post_main_ci_run": 33124525495,
    "pr_ci_run": 33123874692,
    "pr_number": 181,
    "signature_verified": True,
}
HISTORICAL_CONFTEST_SHA256 = (
    "03d92bf3a2890a61190a6a4fc7a6bc59fa900ed6ea4b904223b1f2f991699d95"
)
LIVE_CONFTEST_SHA256 = (
    "e92e9114ff874e71e8468320595489bc5d294653d6ff93b347cc3be27f9a01d9"
)
PUBLIC_SHA256 = {
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

EXPECTED_NEW_MARKERS = {
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


class _ProbeItem:
    def __init__(self, nodeid: str) -> None:
        self.nodeid = nodeid
        self.markers: list[Any] = []

    def add_marker(self, marker: Any) -> None:
        self.markers.append(marker)


def test_d145_post_attempt_collection_has_ten_exact_skips_and_complete_replacement_evidence() -> (
    None
):
    contract_raw, contract = _load_canonical(D144_CONTRACT)
    assert hashlib.sha256(contract_raw).hexdigest() == (
        "d5eb773fc2584deaf31c5f3a3a283e365b6540d0c714fd08cb70ec02937b735f"
    )
    assert _sha256(D144_CONTRACT_TEST) == (
        "a654075771d9f42ac3a7dcbf058e8ca4dba879660888c2aa4262d1e4ea60a1fa"
    )
    assert D144_REVIEW == {
        "integrated_commit": "5d7ed5db76ec0928ba34e19e72ab839ee556d51e",
        "post_main_ci_run": 33124525495,
        "pr_ci_run": 33123874692,
        "pr_number": 181,
        "signature_verified": True,
    }
    assert contract["decision_id"] == "D-144"
    assert contract["gate"] == (
        "G2_7G_MAPLIGHT_ROBUSTNESS_POST_ATTEMPT_TEST_TRANSITION_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_only_no_collection_change_or_d145_implementation_yet"
    )
    assert contract["base_commit"] == ("d630702074bfefa4bda4730ba7c1b7519c3c6f1a")
    assert contract["base_commit_signature_verified"] is True
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

    tracked_claim = contract["parent_evidence"]["d133_tracked_public_claim"]
    assert tracked_claim == {
        "path": (
            "benchmarks/openadmet_cyp_2026/"
            "global_v2_maplight_robustness_execution_claim_v2.json"
        ),
        "sha256": ("d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f"),
    }
    assert tracked_claim["path"] not in PUBLIC_SHA256
    assert contract["parent_evidence"]["historical_conftest"] == {
        "path": "tests/conftest.py",
        "sha256": HISTORICAL_CONFTEST_SHA256,
    }
    for relative_path, expected_sha256 in PUBLIC_SHA256.items():
        assert not Path(relative_path).is_absolute()
        assert "research/" not in relative_path
        assert "execution_claim" not in relative_path
        assert _sha256(ROOT / relative_path) == expected_sha256
    assert _sha256(CONFTEST) == LIVE_CONFTEST_SHA256

    transition = contract["future_collection_transition"]
    previous_markers = {
        item["node_id"]: item["reason"] for item in transition["previous_exact_markers"]
    }
    new_markers = {
        item["node_id"]: item["reason"] for item in transition["exact_new_markers"]
    }
    assert new_markers == EXPECTED_NEW_MARKERS
    assert previous_markers.keys().isdisjoint(new_markers)
    assert transition["previous_exact_skip_count"] == len(previous_markers) == 6
    assert (
        transition["expected_total_skip_count_after_transition"]
        == len(previous_markers) + len(new_markers)
        == 10
    )
    assert transition["collection_constant"] == "_PRE_D145_POST_ATTEMPT_STATE_NODES"
    assert transition["marker_kind"] == "pytest.mark.skip"
    assert transition["deselect_or_xfail_allowed"] is False
    assert transition["additional_retired_nodes_allowed"] is False
    assert transition[
        "only_existing_file_with_transition_specific_behavior_change"
    ] == ("tests/conftest.py")

    replacement = transition["future_replacement_audit"]
    own_node = (
        "tests/test_openadmet_global_v2_maplight_robustness_post_attempt_"
        "test_transition.py::test_d145_post_attempt_collection_has_ten_exact_"
        "skips_and_complete_replacement_evidence"
    )
    assert replacement == {
        "future_path": (
            "tests/test_openadmet_global_v2_maplight_robustness_post_attempt_"
            "test_transition.py"
        ),
        "future_sha256": None,
        "node_id": own_node,
        "required_assertions": replacement["required_assertions"],
        "required_at_contract_freeze": False,
        "test_node_count": 1,
    }
    assert len(replacement["required_assertions"]) == 7
    required_scope = "\n".join(replacement["required_assertions"])
    for fragment in (
        "D-133 historical official.attempt_root_absent_at_freeze=true",
        "tracked public claim fixed-root mapping",
        "without any live private-path probe",
        "D-141 binding that D-140 owns the source-shape transition",
        "resource_checkpoint -> derive_consumed_claim -> _consume_claim",
        "raw_observed = supervisor.run_supervised",
        "publication_root=PUBLICATION_STAGING_ROOT",
        "writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent",
        "official.LIMITS == historical_acceptance.LIMITS",
        "aggregate-only _failure_payload",
        "run_supervised -> _seal_with_fallback",
        "parent _finalize_terminal",
        "child PENDING_TERMINAL_ROOT",
        "sole D-145 comprehensive replacement audit remain active",
        "public repository files",
    ):
        assert fragment in required_scope

    namespace = runpy.run_path(str(CONFTEST))
    assert {name for name in namespace if name.startswith("_PRE_")} == {
        "_PRE_ACCEPTANCE_STATE_NODE",
        "_PRE_D140_ORCHESTRATION_STATE_NODES",
        "_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES",
        "_PRE_D145_POST_ATTEMPT_STATE_NODES",
    }
    observed_previous = {
        cast(str, namespace["_PRE_ACCEPTANCE_STATE_NODE"]): previous_markers[
            cast(str, namespace["_PRE_ACCEPTANCE_STATE_NODE"])
        ],
        **cast(dict[str, str], namespace["_PRE_D140_ORCHESTRATION_STATE_NODES"]),
        **cast(
            dict[str, str],
            namespace["_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES"],
        ),
    }
    observed_new = cast(dict[str, str], namespace["_PRE_D145_POST_ATTEMPT_STATE_NODES"])
    assert observed_previous == previous_markers
    assert observed_new == new_markers

    _, d139_contract = _load_strict(
        BENCHMARK / "global_v2_maplight_robustness_official_orchestration_"
        "test_transition_contract.json"
    )
    _, d140_contract = _load_strict(
        BENCHMARK / "global_v2_maplight_robustness_official_orchestration_"
        "source_shape_transition_contract.json"
    )
    prior_replacements = {
        item["replacement_node_id"]
        for item in [
            *d139_contract["d140_replacement_evidence"]["exact_transition_map"],
            *d140_contract["d141_replacement_evidence"]["exact_transition_map"],
        ]
    }
    transitioned_supervisor = list(new_markers)[1]
    assert len(prior_replacements) == 5
    assert transitioned_supervisor in prior_replacements

    unrelated = {
        "tests/alternate.py::test_uncontracted_post_attempt_node",
        "tests/alternate.py::test_new_attempt_root_is_distinct_and_absent_at_freeze",
        "tests/alternate.py::" + ("d" * 64),
    }
    probes = {
        node_id: _ProbeItem(node_id)
        for node_id in {
            *previous_markers,
            *new_markers,
            *prior_replacements,
            own_node,
            *unrelated,
        }
    }
    hook = namespace["pytest_collection_modifyitems"]
    assert callable(hook)
    hook(list(probes.values()))
    expected_markers = {**previous_markers, **new_markers}
    observed_skips = {
        node_id for node_id, probe in probes.items() if len(probe.markers) == 1
    }
    assert observed_skips == expected_markers.keys()
    assert len(observed_skips) == 10
    for node_id, reason in expected_markers.items():
        marker = probes[node_id].markers[0].mark
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": reason}
    assert all(
        not probes[node_id].markers
        for node_id in prior_replacements - {transitioned_supervisor}
    )
    assert not probes[own_node].markers
    assert all(not probes[node_id].markers for node_id in unrelated)

    conftest_source = CONFTEST.read_text(encoding="utf-8")
    conftest_tree = ast.parse(conftest_source, filename=str(CONFTEST))
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name in {"hashlib", "re"} for alias in node.names)
        for node in conftest_tree.body
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"startswith", "endswith", "match", "search"}
        for node in ast.walk(conftest_tree)
    )
    hook_source = _function_source(CONFTEST, "pytest_collection_modifyitems")
    assert hook_source.count(".get(item.nodeid)") == 3
    assert hook_source.count("item.add_marker") == 4
    assert "pytest.mark.xfail" not in hook_source
    assert "deselect" not in hook_source

    d133_source = _function_source(
        D133_TEST, "test_new_attempt_root_is_distinct_and_absent_at_freeze"
    )
    assert d133_source.count(".exists()") == 1
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
    assert d141_source.count(".exists()") == 1
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
        "assert observed_skips == expected_skips",
        "assert len(observed_skips) == 6",
        "assert all(not probes[node_id].markers for node_id in replacements)",
        "assert all(not probes[node_id].markers for node_id in unrelated)",
    ):
        assert fragment in d140_collection_source

    d142_source = D142_TEST.read_text(encoding="utf-8")
    d142_tree = ast.parse(d142_source, filename=str(D142_TEST))
    assert [
        node.value
        for node in ast.walk(d142_tree)
        if isinstance(node, ast.Constant) and node.value == HISTORICAL_CONFTEST_SHA256
    ] == [HISTORICAL_CONFTEST_SHA256]
    d142_audit_source = _function_source(
        D142_TEST, "test_formal_orchestration_acceptance_record_is_exact_and_static"
    )
    assert "for relative_path, expected_sha256 in LIVE_SHA256.items()" in (
        d142_audit_source
    )
    assert "assert _sha256(ROOT / relative_path) == expected_sha256" in (
        d142_audit_source
    )

    record_raw, record = _load_canonical(D143_RECORD)
    assert hashlib.sha256(record_raw).hexdigest() == (
        "d52bee5e4ed4669c6db7e3061fc8aed8f55e81a0e4d3d17aca73e326df184a2d"
    )
    assert record["status"] == "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED"
    assert record["decision"] == (
        "close_g2_7g_underpowered_without_selection_retry_or_model_quality_claim"
    )
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
    terminal = record["terminal"]
    assert terminal["attempt_file_set"] == ["attempt_claim.json", "terminal"]
    assert terminal["terminal_file_set"] == [
        "attempt_receipt.json",
        "manifest.json",
        "preflight.json",
    ]
    assert terminal["selected_candidate"] is None
    assert terminal["selection_tokens"] == 0
    assert terminal["runner_ups"] == 0
    assert terminal["fit_counts"] == {"stage_a": 0, "stage_b": 0, "stage_c": 0}
    assert terminal["prediction_counts"] == {
        "stage_a": 0,
        "stage_b": 0,
        "stage_c": 0,
    }
    assert record["cleanup"]["cleanup_complete"] is True
    assert record["cleanup"]["matching_processes_after_terminal"] == 0
    assert all(value == 0 for value in record["privacy"].values())
    assert all(value is False for value in record["future_authority_created"].values())
    assert record["scientific_result"] == {
        "best_validated_system": "fixed MapLight",
        "best_validated_system_changed": False,
        "full_maplight_selected_by_this_attempt": False,
        "internal_development_component_macro_mae": 0.5837812652150708,
        "model_quality_result": None,
        "robustness_validated": False,
    }
    interpretation = record["contract_interpretation"]
    assert interpretation["confirmatory_authorized"] is False
    assert interpretation["full_maplight_retained_by_default_rule"] is False
    assert interpretation["new_selection_token_issued"] is False
    assert interpretation["retry_or_resume_authorized"] is False
    assert interpretation["scientific_path_terminal"] is True
    assert interpretation["selected_candidate"] is None
    assert "no G2-8" in interpretation["next_gate"]
    absolute_home_prefix = "/" + "home" + "/"
    private_root_label = "cypshift" + "-private"
    assert all(absolute_home_prefix not in value for value in _all_strings(record))
    assert all(private_root_label not in value for value in _all_strings(record))

    audit_source = Path(__file__).read_text(encoding="utf-8")
    audit_tree = ast.parse(audit_source, filename=__file__)
    assert [
        node.name
        for node in audit_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ] == [own_node.rsplit("::", 1)[1]]
    assert absolute_home_prefix not in audit_source
    assert private_root_label not in audit_source
    observed_imports = {
        alias.name
        for node in audit_tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        cast(str, node.module)
        for node in audit_tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert observed_imports == {
        "__future__",
        "ast",
        "collections.abc",
        "hashlib",
        "json",
        "pathlib",
        "runpy",
        "typing",
    }
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            alias.name.startswith(("research", "maplight", "subprocess", "importlib"))
            for alias in node.names
        )
        for node in audit_tree.body
    )
    assert contract["progression_rule"].endswith(
        "D-144 and D-145 grant no G2-8, confirmatory, model-quality, submission, "
        "validator, leaderboard, portal, credential, or upload authority."
    )
