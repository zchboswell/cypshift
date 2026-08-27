from __future__ import annotations

import ast
import copy
import errno
import importlib
import inspect
import json
import os
import runpy
import stat
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
TRACKED_CLAIM = BENCHMARK / "global_v2_maplight_robustness_execution_claim_v2.json"
TEST_TRANSITION_CONTRACT = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_test_transition_contract.json"
)
SOURCE_SHAPE_TRANSITION_CONTRACT = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_source_shape_"
    "transition_contract.json"
)
D136_AUDIT = (
    ROOT
    / "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py"
)
D134_FOCUSED_SNAPSHOT = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
)
CONFTEST = ROOT / "tests/conftest.py"
TEST_TRANSITION_CONTRACT_SHA256 = (
    "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
)
D136_AUDIT_SHA256 = "719c0f71a8a0e403f590e1aced8a38b3c6131ff915a2bc9f8234126761bb4a2f"
SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256 = (
    "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
)
D134_FOCUSED_SNAPSHOT_SHA256 = (
    "3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f"
)
D139_TRANSITIONS = (
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_acceptance_binds_exact_contract_and_integrated_"
        "implementation",
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_historical_lineage_uses_immutable_driver_hash_and_"
        "composite_is_required",
        "authenticate immutable D-135 and D-136 historical lineage, the historical "
        "official-driver hash, D-137 and D-138 parents, and the required composite "
        "gate",
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_provenance_bridge_retires_only_the_obsolete_pre_"
        "acceptance_state",
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_two_orders_cover_six_scenarios_and_build_one_zero_"
        "operation_record",
        "validate two opposite orders, all six scenarios, deep normalized composite "
        "evidence, inherited science counts, and zero official operations",
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_claim_derivation_is_read_only_and_fills_exactly_"
        "five_receipts",
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_candidate_bytes_prove_all_five_future_claim_fields_"
        "before_publication",
        "prove the unchanged public template derives exactly five future receipt "
        "fields in memory only after candidate composite validation",
    ),
)
D140_SOURCE_SHAPE_TRANSITIONS = (
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_exact_fit_topology_and_conditional_stage_c_are_unchanged",
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_corrected_child_preserves_fit_topology_and_"
        "cleans_before_terminal_staging",
        (
            "prove Stage A=540, Stage B=180, and conditional Stage C=300 fit "
            "identities; exact selection feature widths G2-7-M0-FULL=2563, "
            "G2-7-M1-DROP-MORGAN=1539, G2-7-M2-DROP-AVALON=1539, "
            "G2-7-M3-DROP-ERG=2248, and G2-7-M4-DROP-DESCRIPTORS=2363; both "
            "predictor-authority cross rejections for synthetic=True with "
            "real_catboost_predictor and synthetic=False with "
            "deterministic_test_predictor; Stage A -> selection -> Stage B -> "
            'conditional Stage C chronology with exact condition selected != "G2-7-'
            'M0-FULL"; and corrected source chronology _terminal_bytes -> '
            "_cleanup_owned_root(work) -> _stage_payload(files)"
        ),
    ),
    (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_supervisor_starts_before_claim_consumption_and_official_"
        "access",
        "tests/test_openadmet_global_v2_maplight_robustness_official_"
        "orchestration.py::test_supervisor_precedes_claim_consumption_and_common_"
        "seal_owns_terminal_publication",
        (
            "prove run_supervised is present in run_official_attempt and "
            "_consume_claim is absent from run_official_attempt; child chronology "
            "resource_checkpoint -> derive_consumed_claim -> _consume_claim -> "
            "compile_capabilities -> Stage A; exact raw_observed = "
            "supervisor.run_supervised assignment; exact publication_root="
            "PUBLICATION_STAGING_ROOT and writable_publication_parent="
            "OFFICIAL_ATTEMPT_ROOT.parent supervisor arguments; official.LIMITS == "
            "acceptance.LIMITS; OFFICIAL_ATTEMPT_ROOT == /home/zbos/cypshift-"
            "private/openadmet-2026/g2-7g-maplight-robustness-development-attempt-1 "
            "and that root is absent; _failure_payload contains "
            "accounting_complete and returns aggregate bytes only with no terminal "
            "path or publication; outer chronology run_supervised -> "
            "_seal_with_fallback places the common seal after supervision and "
            "makes it the exclusive terminal publisher; and _finalize_terminal is "
            "absent from run_official_attempt while PENDING_TERMINAL_ROOT is absent "
            "from the child"
        ),
    ),
)
D140_SOURCE_SHAPE_MARKERS = {
    D140_SOURCE_SHAPE_TRANSITIONS[0][0]: (
        "historical D-134 child terminal-shape assertion; D-141 corrected child "
        "cleanup/staging test owns current-state validation"
    ),
    D140_SOURCE_SHAPE_TRANSITIONS[1][0]: (
        "historical D-134 parent terminal-shape assertion; D-141 supervised "
        "common-seal test owns current-state validation"
    ),
}
sys.path.insert(0, str(RESEARCH))
mechanics = importlib.import_module("global_v2_maplight_robustness_execution_wrapper")
runner = importlib.import_module("global_v2_maplight_robustness_scientific_runner")
official = importlib.import_module("run_global_v2_maplight_robustness_official_v2")
supervisor = importlib.import_module("global_v2_maplight_resource_supervisor")
historical_acceptance = importlib.import_module(
    "run_global_v2_maplight_robustness_execution_acceptance_v2"
)
acceptance = importlib.import_module(
    "run_global_v2_maplight_robustness_official_orchestration_acceptance"
)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _assert_d139_replacement_responsibility(index: int) -> None:
    contract = _load(TEST_TRANSITION_CONTRACT)
    assert official.maplight.sha256_path(TEST_TRANSITION_CONTRACT) == (
        TEST_TRANSITION_CONTRACT_SHA256
    )
    assert official.TEST_TRANSITION_CONTRACT == TEST_TRANSITION_CONTRACT
    assert official.TEST_TRANSITION_CONTRACT_SHA256 == TEST_TRANSITION_CONTRACT_SHA256
    assert acceptance.TEST_TRANSITION_CONTRACT == TEST_TRANSITION_CONTRACT
    assert acceptance.TEST_TRANSITION_CONTRACT_SHA256 == (
        TEST_TRANSITION_CONTRACT_SHA256
    )
    expected = [
        {
            "historical_node_id": historical,
            "replacement_node_id": replacement,
            "replacement_scope": scope,
        }
        for historical, replacement, scope in D139_TRANSITIONS
    ]
    evidence = cast(dict[str, Any], contract["d140_replacement_evidence"])
    assert evidence["exact_transition_map"] == expected
    assert evidence["replacement_node_ids"] == [
        replacement for _historical, replacement, _scope in D139_TRANSITIONS
    ]
    assert evidence["replacement_node_count"] == len(D139_TRANSITIONS) == 3
    assert expected[index] == evidence["exact_transition_map"][index]


def _assert_d140_source_shape_replacement_responsibility(index: int) -> None:
    contract = _load(SOURCE_SHAPE_TRANSITION_CONTRACT)
    assert official.maplight.sha256_path(SOURCE_SHAPE_TRANSITION_CONTRACT) == (
        SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
    )
    assert official.SOURCE_SHAPE_TRANSITION_CONTRACT == SOURCE_SHAPE_TRANSITION_CONTRACT
    assert official.SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256 == (
        SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
    )
    assert (
        acceptance.SOURCE_SHAPE_TRANSITION_CONTRACT == SOURCE_SHAPE_TRANSITION_CONTRACT
    )
    assert acceptance.SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256 == (
        SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
    )
    historical = tuple(item[0] for item in D140_SOURCE_SHAPE_TRANSITIONS)
    replacements = tuple(item[1] for item in D140_SOURCE_SHAPE_TRANSITIONS)
    scopes = tuple(item[2] for item in D140_SOURCE_SHAPE_TRANSITIONS)
    assert acceptance.HISTORICAL_D134_FOCUSED_SHA256 == (D134_FOCUSED_SNAPSHOT_SHA256)
    assert acceptance.RETIRED_D134_SOURCE_SHAPE_NODE_IDS == historical
    assert acceptance.REPLACEMENT_D141_SOURCE_SHAPE_NODE_IDS == replacements
    assert acceptance.REPLACEMENT_D141_SOURCE_SHAPE_SCOPES == scopes
    expected = [
        {
            "historical_node_id": historical_node,
            "replacement_node_id": replacement,
            "replacement_scope": scope,
        }
        for historical_node, replacement, scope in D140_SOURCE_SHAPE_TRANSITIONS
    ]
    evidence = cast(dict[str, Any], contract["d141_replacement_evidence"])
    assert evidence["exact_transition_map"] == expected
    assert evidence["replacement_node_ids"] == list(replacements)
    assert evidence["replacement_node_count"] == len(D140_SOURCE_SHAPE_TRANSITIONS) == 2
    assert expected[index] == evidence["exact_transition_map"][index]


def _identity_map(root: Path, names: dict[str, bytes]) -> dict[str, tuple[int, int]]:
    root_stat = root.stat(follow_symlinks=False)
    result = {".": (root_stat.st_dev, root_stat.st_ino)}
    for name in names:
        item = (root / name).stat(follow_symlinks=False)
        result[name] = (item.st_dev, item.st_ino)
    return result


def _observation(**changes: object) -> Any:
    values: dict[str, object] = {
        "wall_seconds": 1.25,
        "cpu_seconds": 2.5,
        "peak_storage_bytes": 4096,
        "peak_simultaneous_rss_bytes": 8192,
        "gpu_hours": 0.0,
        "checkpoints_acknowledged": 3,
        "descendant_processes_observed": 2,
        "return_code": 0,
        "cleanup_complete": True,
        "network_namespace_isolated": True,
        "gpu_environment_hidden": True,
        "detached_children_observed": 0,
        "warnings_observed": 0,
    }
    values.update(changes)
    return supervisor.ResourceObservation(**values)


def _supervisor_error(reason: str, observation: Any | None = None) -> Exception:
    if observation is None:
        return supervisor.ResourceSupervisorError(reason)
    payload = json.dumps(asdict(observation), sort_keys=True, allow_nan=False)
    return supervisor.ResourceSupervisorError(
        f"{reason}{official.SUPERVISOR_OBSERVATION_DELIMITER}{payload}"
    )


def test_corrected_child_preserves_fit_topology_and_cleans_before_terminal_staging(
    tmp_path: Path,
) -> None:
    _assert_d140_source_shape_replacement_responsibility(0)
    assert len(mechanics._fit_identities("stage_a")) == 540
    assert len(mechanics._fit_identities("stage_b", "G2-7-M0-FULL")) == 180
    assert len(mechanics._fit_identities("stage_c", "G2-7-M1-DROP-MORGAN")) == 300
    assert runner.SELECTION_FEATURE_COLUMNS == {
        "G2-7-M0-FULL": 2563,
        "G2-7-M1-DROP-MORGAN": 1539,
        "G2-7-M2-DROP-AVALON": 1539,
        "G2-7-M3-DROP-ERG": 2248,
        "G2-7-M4-DROP-DESCRIPTORS": 2363,
    }
    for synthetic, predictor in (
        (True, runner.real_catboost_predictor),
        (False, runner.deterministic_test_predictor),
    ):
        with pytest.raises(
            runner.RobustnessScientificRunnerError,
            match="predictor authority differs",
        ):
            runner.run_prediction_stage(
                stage="stage_a",
                selected_candidate=None,
                model_capability_root=tmp_path / "unopened-model",
                output_root=tmp_path / f"crossed-{synthetic}",
                predictor=predictor,
                checkpoint=lambda _label: None,
                synthetic=synthetic,
            )

    source = inspect.getsource(official._child)
    assert source.index('stage="stage_a"') < source.index("select_stage_a_candidate")
    assert source.index("select_stage_a_candidate") < source.index('stage="stage_b"')
    assert 'selected != "G2-7-M0-FULL"' in source
    assert source.index('selected != "G2-7-M0-FULL"') < source.index('stage="stage_c"')
    assert source.index("_terminal_bytes") < source.index("_cleanup_owned_root(work)")
    assert source.index("_cleanup_owned_root(work)") < source.index(
        "_stage_payload(files)"
    )


def test_supervisor_precedes_claim_consumption_and_common_seal_owns_terminal_publication() -> (
    None
):
    _assert_d140_source_shape_replacement_responsibility(1)
    outer = inspect.getsource(official.run_official_attempt)
    child = inspect.getsource(official._child)
    assert "run_supervised" in outer
    assert "_consume_claim" not in outer
    assert child.index("resource_checkpoint") < child.index("derive_consumed_claim")
    assert child.index("derive_consumed_claim") < child.index("_consume_claim")
    assert child.index("_consume_claim") < child.index("compile_capabilities")
    assert child.index("compile_capabilities") < child.index('stage="stage_a"')
    assert "raw_observed = supervisor.run_supervised" in outer
    assert "publication_root=PUBLICATION_STAGING_ROOT" in outer
    assert "writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent" in outer
    assert official.LIMITS == historical_acceptance.LIMITS
    assert official.OFFICIAL_ATTEMPT_ROOT == Path(
        "/home/zbos/cypshift-private/openadmet-2026/"
        "g2-7g-maplight-robustness-development-attempt-1"
    )
    assert not official.OFFICIAL_ATTEMPT_ROOT.exists()

    failure_source = inspect.getsource(official._failure_payload)
    assert "accounting_complete" in failure_source
    assert 'return {"manifest.json": maplight.json_bytes(manifest)}' in failure_source
    assert "terminal_root" not in failure_source
    assert "_stage_payload" not in failure_source
    assert "_seal_with_fallback" not in failure_source
    failure_files = official._failure_payload(
        status=official.FAILED_STATUS,
        claim_sha256="a" * 64,
        failure_category="supervised_execution_failure",
        accounting={"official_model_fits": 17},
        accounting_complete=True,
    )
    assert set(failure_files) == {"manifest.json"}
    assert all(isinstance(payload, bytes) for payload in failure_files.values())
    failure_manifest = json.loads(failure_files["manifest.json"])
    assert failure_manifest["accounting"] == {"official_model_fits": 17}
    assert failure_manifest["accounting_complete"] is True

    assert outer.index("run_supervised") < outer.index("_seal_with_fallback")
    assert "_finalize_terminal" not in outer
    assert "PENDING_TERMINAL_ROOT" not in child


def test_historical_lineage_uses_immutable_driver_hash_and_composite_is_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _assert_d139_replacement_responsibility(0)
    before = TRACKED_CLAIM.read_bytes()
    template = official._authenticate_historical_science_kernel()
    assert template["status"] == "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
    assert official.HISTORICAL_OFFICIAL_DRIVER_SHA256 == (
        "1675336e449ba9a8327406cb37f82f08e3547076ce6c69fa0ade70c5a3de57fc"
    )
    assert official.maplight.sha256_path(official.SEAL_ERRATUM) == (
        "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33"
    )
    erratum = _load(official.SEAL_ERRATUM)
    assert erratum["parents"]["d137_repair_contract_sha256"] == (
        official.REPAIR_CONTRACT_SHA256
    )
    boundary = cast(dict[str, Any], erratum["security_boundary"])
    assert {
        name: boundary[name]
        for name in (
            "final_terminal_read_only",
            "staging_root_before_promotion_mode",
            "staging_leaf_modes_before_promotion",
            "final_terminal_root_mode",
            "concurrent_malicious_same_uid_root_substitution_in_scope",
        )
    } == {
        "final_terminal_read_only": True,
        "staging_root_before_promotion_mode": "0700",
        "staging_leaf_modes_before_promotion": "0444",
        "final_terminal_root_mode": "0555",
        "concurrent_malicious_same_uid_root_substitution_in_scope": False,
    }

    missing = tmp_path / "composite-acceptance.json"
    monkeypatch.setattr(official, "COMPOSITE_ACCEPTANCE", missing)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="composite orchestration acceptance is unavailable",
    ):
        official.derive_consumed_claim()
    assert TRACKED_CLAIM.read_bytes() == before


def test_official_entry_point_accepts_no_path_override() -> None:
    assert official._main(["alternate-root"]) == 2


def test_canonical_supervisor_observation_round_trips_exactly() -> None:
    observed = _observation()
    reason, parsed = official._parse_supervisor_exception(
        _supervisor_error("supervised process exited nonzero", observed)
    )
    assert reason == "supervised process exited nonzero"
    assert parsed == observed
    assert tuple(vars(parsed)) == official.OBSERVATION_FIELDS


@pytest.mark.parametrize(
    "reason",
    [
        "wall limit exceeded",
        "CPU limit exceeded",
        "storage limit exceeded",
        "simultaneous RSS limit exceeded",
    ],
)
def test_only_four_exact_validated_reasons_are_resource_aborted(reason: str) -> None:
    parsed_reason, _parsed = official._parse_supervisor_exception(
        _supervisor_error(reason, _observation(return_code=-15))
    )
    assert official._classify_supervisor_failure(parsed_reason) == (
        official.RESOURCE_ABORTED_STATUS
    )


@pytest.mark.parametrize(
    "reason",
    [
        "wall limit exceeded ",
        "Wall limit exceeded",
        "GPU limit exceeded",
        "supervised process exited nonzero",
        "supervisor failure",
        "warning or stderr output observed",
    ],
)
def test_every_other_canonical_supervisor_reason_is_failed(reason: str) -> None:
    parsed_reason, _parsed = official._parse_supervisor_exception(
        _supervisor_error(reason, _observation(return_code=7))
    )
    assert (
        official._classify_supervisor_failure(parsed_reason) == official.FAILED_STATUS
    )


def _observation_json(**changes: object) -> str:
    payload = asdict(_observation())
    payload.update(changes)
    return json.dumps(payload, sort_keys=True, allow_nan=True)


@pytest.mark.parametrize(
    "detail",
    [
        "",
        "[]",
        "{}",
        _observation_json(extra_field=0),
        json.dumps(
            {
                name: value
                for name, value in asdict(_observation()).items()
                if name != "warnings_observed"
            },
            sort_keys=True,
        ),
        _observation_json(peak_storage_bytes=True),
        _observation_json(return_code=True),
        _observation_json(wall_seconds=1),
        _observation_json(cpu_seconds=2),
        _observation_json(gpu_hours=0),
        _observation_json(wall_seconds=-0.1),
        _observation_json(wall_seconds=-0.0),
        _observation_json(cpu_seconds=float("nan")),
        _observation_json(gpu_hours=float("inf")),
        _observation_json(gpu_hours=1e10000),
        _observation_json(cleanup_complete=1),
        json.dumps(asdict(_observation()), sort_keys=True, separators=(",", ":")),
        (
            '{"cpu_seconds": 2.5, "cpu_seconds": 2.5, '
            + json.dumps(asdict(_observation()), sort_keys=True)[1:]
        ),
    ],
)
def test_malformed_or_noncanonical_observations_fail_closed(detail: str) -> None:
    error = supervisor.ResourceSupervisorError(
        f"wall limit exceeded{official.SUPERVISOR_OBSERVATION_DELIMITER}{detail}"
    )
    with pytest.raises(official.RobustnessOfficialAttemptError):
        official._parse_supervisor_exception(error)


def test_finite_overflow_exponent_is_normalized_to_fail_closed_error() -> None:
    detail = json.dumps(asdict(_observation()), sort_keys=True).replace(
        '"gpu_hours": 0.0', '"gpu_hours": 1e10000'
    )
    error = supervisor.ResourceSupervisorError(
        f"wall limit exceeded{official.SUPERVISOR_OBSERVATION_DELIMITER}{detail}"
    )
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="supervisor gpu_hours differs",
    ):
        official._parse_supervisor_exception(error)


@pytest.mark.parametrize(
    "message",
    [
        "wall limit exceeded",
        "wall limit exceeded; observation={}; observation={}",
        "wall limit exceeded\n; observation={}",
    ],
)
def test_missing_duplicate_or_multiline_observation_protocol_is_rejected(
    message: str,
) -> None:
    with pytest.raises(official.RobustnessOfficialAttemptError):
        official._parse_supervisor_exception(
            supervisor.ResourceSupervisorError(message)
        )


def test_oversized_supervisor_exception_is_rejected_before_json_parsing() -> None:
    oversized = "x" * (official.MAXIMUM_RECEIPT_BYTES + 1)
    message = (
        f"wall limit exceeded{official.SUPERVISOR_OBSERVATION_DELIMITER}{oversized}"
    )
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="malformed or absent supervisor observation",
    ):
        official._parse_supervisor_exception(
            supervisor.ResourceSupervisorError(message)
        )


@pytest.mark.parametrize(
    "change",
    [
        {"return_code": True},
        {"return_code": 1},
        {"checkpoints_acknowledged": 0},
        {"descendant_processes_observed": 0},
        {"cleanup_complete": False},
        {"network_namespace_isolated": False},
        {"gpu_environment_hidden": False},
        {"gpu_hours": 0.01},
        {"detached_children_observed": 1},
        {"warnings_observed": 1},
        {"wall_seconds": official.LIMITS.wall_seconds - 4.9},
        {"cpu_seconds": official.LIMITS.cpu_seconds - 4.9},
        {
            "peak_storage_bytes": official.LIMITS.storage_bytes
            - official.MAXIMUM_TERMINAL_BYTES
            + 1
        },
        {"peak_simultaneous_rss_bytes": official.LIMITS.rss_bytes + 1},
    ],
)
def test_scientific_or_underpowered_seal_requires_full_valid_observation(
    change: dict[str, object],
) -> None:
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="successful cumulative supervision differs",
    ):
        official._validate_success_observation(_observation(**change))


def _valid_composite_summary(scenario: str) -> dict[str, object]:
    status_name = acceptance.EXPECTED_STATUS_BY_SCENARIO[scenario]
    if scenario == "pre_consumption_supervisor_failure":
        return {
            "status": status_name,
            "file_set": [],
            "accounting": None,
            "accounting_complete": False,
            "cumulative_supervision": None,
            "receipt_file_bindings": {},
            "receipt_file_receipts": None,
            "receipt_status": None,
            "receipt_claim_sha256": None,
            "receipt_implementation_lineage": None,
            "receipt_resource_limits": None,
            "receipt_cleanup_complete": None,
            "receipt_authority": None,
            "receipt_seal_attempts": None,
            "receipt_fallback_used": None,
            "cleanup_complete": True,
            "terminal_read_only": False,
            "aggregate_only": True,
        }

    payload_names = set(acceptance.STATUS_FILE_SETS[status_name]) - {
        "attempt_receipt.json"
    }
    payloads = {name: f"{scenario}:{name}\n".encode() for name in sorted(payload_names)}
    bindings = {
        name: acceptance.maplight.sha256_bytes(payload)
        for name, payload in payloads.items()
    }
    lineage = {
        "d135_science_kernel_acceptance_sha256": acceptance.D135_ACCEPTANCE_SHA256,
        "d136_focused_test_provenance_bridge_sha256": acceptance.D136_BRIDGE_SHA256,
        "d137_repair_contract_sha256": acceptance.REPAIR_CONTRACT_SHA256,
        "d138_seal_erratum_sha256": acceptance.SEAL_ERRATUM_SHA256,
        "d139_test_transition_contract_sha256": (
            acceptance.TEST_TRANSITION_CONTRACT_SHA256
        ),
        "d140_source_shape_transition_contract_sha256": (
            acceptance.SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
        ),
        "historical_official_driver_sha256": (
            acceptance.HISTORICAL_OFFICIAL_DRIVER_SHA256
        ),
        "corrected_official_driver_sha256": acceptance.maplight.sha256_path(
            official.SCRIPT
        ),
        "composite_acceptance_sha256": acceptance.maplight.sha256_bytes(
            acceptance.maplight.json_bytes(acceptance.COMPOSITE_LINEAGE_FIXTURE)
        ),
        "composite_acceptance_driver_sha256": acceptance.maplight.sha256_path(
            acceptance.SCRIPT
        ),
        "orchestration_focused_tests_sha256": acceptance.maplight.sha256_path(
            acceptance.FOCUSED_TESTS
        ),
        "immutable_science_kernel_source_sha256": dict(
            acceptance.IMMUTABLE_SCIENCE_KERNEL_SHA256
        ),
    }
    scientific = scenario in {"scientific_success", "scientific_rejection"}
    deletion = scenario == "scientific_rejection"
    if scientific:
        accounting: object = acceptance._completed_accounting(deletion=deletion)
        accounting_complete = True
        selection_tokens: object = 1
        runner_ups: object = 0
        fit_counts: object = {
            "stage_a": 540,
            "stage_b": 180,
            "stage_c": 300 if deletion else 0,
        }
        prediction_counts: object = {
            "stage_a": 422_064,
            "stage_b": 140_580,
            "stage_c": 234_480 if deletion else 0,
        }
        tutorial_calls: object = 56
        failure_category: object = None
        observation = asdict(acceptance._successful_observation())
    elif scenario == "clean_underpowered":
        accounting = official._underpowered_accounting()
        accounting_complete = True
        selection_tokens = 0
        runner_ups = 0
        fit_counts = {"stage_a": 0, "stage_b": 0, "stage_c": 0}
        prediction_counts = {"stage_a": 0, "stage_b": 0, "stage_c": 0}
        tutorial_calls = 0
        failure_category = None
        observation = asdict(acceptance._successful_observation())
    else:
        hard = scenario == "hard_wall_resource_abort"
        accounting = None
        accounting_complete = False
        selection_tokens = None
        runner_ups = None
        fit_counts = None
        prediction_counts = None
        tutorial_calls = None
        failure_category = (
            "hard_resource_limit" if hard else "supervised_process_nonzero"
        )
        observation = asdict(acceptance._failure_observation(hard_wall=hard))
    return {
        "status": status_name,
        "file_set": sorted({"attempt_receipt.json", *payload_names}),
        "accounting": accounting,
        "accounting_complete": accounting_complete,
        "selection_tokens": selection_tokens,
        "runner_ups": runner_ups,
        "fit_counts": fit_counts,
        "prediction_counts": prediction_counts,
        "tutorial_metric_calls": tutorial_calls,
        "failure_category": failure_category,
        "cumulative_supervision": observation,
        "receipt_file_bindings": bindings,
        "receipt_file_receipts": {
            name: {
                "sha256": digest,
                "size_bytes": len(payloads[name]),
                "mode": "0444",
            }
            for name, digest in bindings.items()
        },
        "receipt_status": status_name,
        "receipt_claim_sha256": official._composite_fixture_claim_sha256(scenario),
        "receipt_implementation_lineage": lineage,
        "receipt_resource_limits": vars(official.LIMITS),
        "receipt_cleanup_complete": True,
        "receipt_authority": dict(acceptance.maplight.DENIED_AUTHORITY),
        "receipt_seal_attempts": 1,
        "receipt_fallback_used": False,
        "cleanup_complete": True,
        "terminal_read_only": True,
        "aggregate_only": True,
    }


def _normalized_acceptance_roots() -> list[dict[str, object]]:
    results = {
        scenario: _valid_composite_summary(scenario)
        for scenario in acceptance.SCENARIOS
    }
    forward = acceptance._normalized_result_map(results)
    reversed_results = {
        scenario: results[scenario] for scenario in reversed(acceptance.SCENARIOS)
    }
    reverse = acceptance._normalized_result_map(reversed_results)
    assert acceptance.maplight.json_bytes(forward) == acceptance.maplight.json_bytes(
        reverse
    )
    return [
        {
            "order": "forward",
            "scenario_execution_order": list(acceptance.SCENARIOS),
            "normalized_result_map": forward,
        },
        {
            "order": "reverse",
            "scenario_execution_order": list(reversed(acceptance.SCENARIOS)),
            "normalized_result_map": reverse,
        },
    ]


def test_two_orders_cover_six_scenarios_and_build_one_zero_operation_record() -> None:
    _assert_d139_replacement_responsibility(1)
    assert acceptance.ORDERS == ("forward", "reverse")
    assert acceptance.SCENARIOS == (
        "scientific_success",
        "clean_underpowered",
        "scientific_rejection",
        "hard_wall_resource_abort",
        "ordinary_nonzero_failure",
        "pre_consumption_supervisor_failure",
    )
    record = acceptance._build_acceptance_record(
        _normalized_acceptance_roots(),
        exact_underpowered_catch_verified=True,
        five_field_prepublication_derivation_verified=True,
    )
    assert record["scenario_invocations"] == 12
    assert record["supervisor_invocations"] == 12
    assert record["statuses_reached"] == sorted(acceptance.STATUS_FILE_SETS)
    assert len(cast(dict[str, bool], record["mechanics"])) == 11
    assert all(cast(dict[str, bool], record["mechanics"]).values())
    assert all(
        value == 0
        for value in cast(dict[str, int], record["forbidden_operations"]).values()
    )
    assert record["d135_science_kernel_evidence"] == {
        "model_double_invocations": 3480,
        "synthetic_predictions_generated": 667872,
        "real_catboost_fits": 2,
        "reexecuted": False,
    }
    assert record["d139_test_transition_contract_sha256"] == (
        TEST_TRANSITION_CONTRACT_SHA256
    )
    assert record["d140_source_shape_transition_contract_sha256"] == (
        SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
    )
    acceptance._validate_candidate_acceptance(
        record,
        acceptance_sha256="a" * 64,
        corrected_driver_sha256=cast(
            str, record["corrected_official_attempt_driver_source_sha256"]
        ),
        acceptance_driver_sha256=cast(
            str,
            record["official_orchestration_acceptance_driver_source_sha256"],
        ),
        focused_tests_sha256=cast(str, record["focused_tests_sha256"]),
    )


def test_candidate_bytes_prove_all_five_future_claim_fields_before_publication(
    tmp_path: Path,
) -> None:
    _assert_d139_replacement_responsibility(2)
    before = TRACKED_CLAIM.read_bytes()
    record = acceptance._build_acceptance_record(
        _normalized_acceptance_roots(),
        exact_underpowered_catch_verified=True,
        five_field_prepublication_derivation_verified=True,
    )
    candidate = tmp_path / "candidate-acceptance.json"
    candidate.write_bytes(acceptance.maplight.json_bytes(record))
    assert acceptance._five_field_candidate_derivation(candidate) is True
    assert TRACKED_CLAIM.read_bytes() == before


def test_d139_collection_transition_is_exact_narrow_and_fully_replaced() -> None:
    contract = _load(TEST_TRANSITION_CONTRACT)
    transition = cast(dict[str, Any], contract["future_collection_transition"])
    exact_markers = {
        marker["node_id"]: marker["reason"]
        for marker in cast(list[dict[str, str]], transition["exact_markers"])
    }
    retired = {historical for historical, _replacement, _scope in D139_TRANSITIONS}
    replacements = {
        replacement for _historical, replacement, _scope in D139_TRANSITIONS
    }
    assert exact_markers.keys() == retired
    assert transition["collection_constant"] == ("_PRE_D140_ORCHESTRATION_STATE_NODES")
    assert transition["marker_kind"] == "pytest.mark.skip"
    assert transition["deselect_or_xfail_allowed"] is False
    assert transition["additional_retired_nodes_allowed"] is False

    assert official.maplight.sha256_path(D136_AUDIT) == D136_AUDIT_SHA256
    audit_tree = ast.parse(
        D136_AUDIT.read_text(encoding="utf-8"), filename=str(D136_AUDIT)
    )
    audit_names = {
        node.name
        for node in audit_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    audit_prefix = D136_AUDIT.relative_to(ROOT).as_posix()
    audit_node_ids = {f"{audit_prefix}::{name}" for name in audit_names}
    assert len(audit_node_ids) == 7
    assert retired < audit_node_ids
    retained = audit_node_ids - retired
    assert len(retired) == 3
    assert len(retained) == 4

    focused_tree = ast.parse(
        Path(__file__).read_text(encoding="utf-8"), filename=__file__
    )
    focused_functions = {
        node.name: node
        for node in focused_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node_id in replacements:
        name = node_id.rsplit("::", 1)[1]
        assert name in focused_functions
        assert focused_functions[name].decorator_list == []

    namespace = runpy.run_path(str(CONFTEST))
    assert namespace["_PRE_D140_ORCHESTRATION_STATE_NODES"] == exact_markers
    assert namespace["_PRE_ACCEPTANCE_STATE_NODE"] == (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::"
        "test_formal_acceptance_is_fixed_unrun_and_has_zero_authority"
    )
    hook = namespace["pytest_collection_modifyitems"]
    assert callable(hook)

    class ProbeItem:
        def __init__(self, nodeid: str) -> None:
            self.nodeid = nodeid
            self.markers: list[Any] = []

        def add_marker(self, marker: Any) -> None:
            self.markers.append(marker)

    unrelated = {
        "tests/test_openadmet_global_v2_maplight_robustness_execution_"
        "acceptance_v2.py::test_uncontracted_sibling",
        "tests/alternate.py::test_acceptance_binds_exact_contract_and_integrated_"
        "implementation",
        "tests/alternate.py::" + ("a" * 64),
    }
    probes = {
        node_id: ProbeItem(node_id)
        for node_id in audit_node_ids | replacements | unrelated
    }
    pre_acceptance = ProbeItem(namespace["_PRE_ACCEPTANCE_STATE_NODE"])
    hook([*probes.values(), pre_acceptance])

    assert {
        node_id for node_id in audit_node_ids if len(probes[node_id].markers) == 1
    } == retired
    assert all(not probes[node_id].markers for node_id in retained)
    assert all(not probes[node_id].markers for node_id in replacements)
    assert all(not probes[node_id].markers for node_id in unrelated)
    for node_id, reason in exact_markers.items():
        marker = probes[node_id].markers[0].mark
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": reason}
    assert len(pre_acceptance.markers) == 1
    assert pre_acceptance.markers[0].mark.name == "skip"
    assert "D-134 pre-acceptance" in pre_acceptance.markers[0].mark.kwargs["reason"]

    hook_tree = ast.parse(CONFTEST.read_text(encoding="utf-8"), filename=str(CONFTEST))
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name in {"hashlib", "re"} for alias in node.names)
        for node in hook_tree.body
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"startswith", "endswith", "match", "search"}
        for node in ast.walk(hook_tree)
    )


def test_d140_source_shape_collection_has_six_exact_skips_and_active_replacements() -> (
    None
):
    contract = _load(SOURCE_SHAPE_TRANSITION_CONTRACT)
    transition = cast(dict[str, Any], contract["future_collection_transition"])
    exact_markers = {
        marker["node_id"]: marker["reason"]
        for marker in cast(list[dict[str, str]], transition["exact_new_markers"])
    }
    retired = {
        historical for historical, _replacement, _scope in D140_SOURCE_SHAPE_TRANSITIONS
    }
    replacements = {
        replacement
        for _historical, replacement, _scope in D140_SOURCE_SHAPE_TRANSITIONS
    }
    assert exact_markers == D140_SOURCE_SHAPE_MARKERS
    assert exact_markers.keys() == retired
    assert transition["collection_constant"] == (
        "_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES"
    )
    assert transition["marker_kind"] == "pytest.mark.skip"
    assert transition["previously_frozen_skip_count"] == 4
    assert transition["expected_total_skip_count_after_transition"] == 6
    assert transition["deselect_or_xfail_allowed"] is False
    assert transition["additional_retired_nodes_allowed"] is False

    assert official.maplight.sha256_path(D134_FOCUSED_SNAPSHOT) == (
        D134_FOCUSED_SNAPSHOT_SHA256
    )
    snapshot_tree = ast.parse(
        D134_FOCUSED_SNAPSHOT.read_text(encoding="utf-8"),
        filename=str(D134_FOCUSED_SNAPSHOT),
    )
    snapshot_names = {
        node.name
        for node in snapshot_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    snapshot_prefix = D134_FOCUSED_SNAPSHOT.relative_to(ROOT).as_posix()
    snapshot_node_ids = {f"{snapshot_prefix}::{name}" for name in snapshot_names}
    pre_acceptance = (
        "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_"
        "v2.py::test_formal_acceptance_is_fixed_unrun_and_has_zero_authority"
    )
    historical_retired = {pre_acceptance, *retired}
    assert len(snapshot_node_ids) == 9
    assert historical_retired < snapshot_node_ids
    assert len(historical_retired) == 3
    assert len(snapshot_node_ids - historical_retired) == 6

    focused_tree = ast.parse(
        Path(__file__).read_text(encoding="utf-8"), filename=__file__
    )
    focused_functions = {
        node.name: node
        for node in focused_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node_id in replacements:
        name = node_id.rsplit("::", 1)[1]
        assert name in focused_functions
        assert focused_functions[name].decorator_list == []

    namespace = runpy.run_path(str(CONFTEST))
    assert namespace["_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES"] == (exact_markers)
    prior_markers = cast(
        dict[str, str], namespace["_PRE_D140_ORCHESTRATION_STATE_NODES"]
    )
    assert prior_markers.keys() == {
        historical for historical, _replacement, _scope in D139_TRANSITIONS
    }
    assert namespace["_PRE_ACCEPTANCE_STATE_NODE"] == pre_acceptance
    assert 1 + len(prior_markers) + len(exact_markers) == 6
    hook = namespace["pytest_collection_modifyitems"]

    class ProbeItem:
        def __init__(self, nodeid: str) -> None:
            self.nodeid = nodeid
            self.markers: list[Any] = []

        def add_marker(self, marker: Any) -> None:
            self.markers.append(marker)

    unrelated = {
        "tests/alternate.py::test_exact_fit_topology_and_conditional_stage_c_are_"
        "unchanged",
        "tests/alternate.py::test_supervisor_starts_before_claim_consumption_and_"
        "official_access",
        "tests/alternate.py::" + ("b" * 64),
    }
    probe_node_ids = {
        *snapshot_node_ids,
        *prior_markers,
        *replacements,
        *unrelated,
    }
    probes = {node_id: ProbeItem(node_id) for node_id in probe_node_ids}
    hook(list(probes.values()))

    expected_skips = {pre_acceptance, *prior_markers, *exact_markers}
    observed_skips = {
        node_id for node_id, probe in probes.items() if len(probe.markers) == 1
    }
    assert observed_skips == expected_skips
    assert len(observed_skips) == 6
    assert all(not probes[node_id].markers for node_id in replacements)
    assert all(not probes[node_id].markers for node_id in unrelated)
    for node_id, reason in exact_markers.items():
        marker = probes[node_id].markers[0].mark
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": reason}


@pytest.mark.parametrize(
    "evidence_family",
    [
        "top-level-schema",
        "probe-count",
        "file-set",
        "accounting",
        "observation",
        "receipt-binding",
        "receipt-lineage",
        "cleanup",
        "failure-cause",
        "seal-attempts",
        "fixture-claim",
    ],
)
def test_live_composite_validator_rejects_each_tampered_evidence_family(
    evidence_family: str,
) -> None:
    record = acceptance._build_acceptance_record(
        _normalized_acceptance_roots(),
        exact_underpowered_catch_verified=True,
        five_field_prepublication_derivation_verified=True,
    )
    tampered = copy.deepcopy(record)
    roots = cast(list[dict[str, Any]], tampered["roots"])
    maps = [
        cast(dict[str, dict[str, Any]], root["normalized_result_map"]) for root in roots
    ]
    if evidence_family == "top-level-schema":
        tampered["uncontracted_field"] = True
    elif evidence_family == "probe-count":
        tampered["mechanics_probe_counts"]["atomic_claim_interruptions"] = 2
    elif evidence_family == "file-set":
        for result_map in maps:
            result_map["clean_underpowered"]["file_set"].append("extra.json")
    elif evidence_family == "accounting":
        for result_map in maps:
            result_map["scientific_success"]["accounting"]["official_model_fits"] = 721
    elif evidence_family == "observation":
        for result_map in maps:
            result_map["scientific_success"]["cumulative_supervision"][
                "wall_seconds"
            ] = 1.5
    elif evidence_family == "receipt-binding":
        for result_map in maps:
            result_map["clean_underpowered"]["receipt_file_bindings"][
                "manifest.json"
            ] = "f" * 64
    elif evidence_family == "receipt-lineage":
        for result_map in maps:
            result_map["scientific_rejection"]["receipt_implementation_lineage"][
                "corrected_official_driver_sha256"
            ] = "e" * 64
    elif evidence_family == "cleanup":
        for result_map in maps:
            result_map["ordinary_nonzero_failure"]["cleanup_complete"] = False
    elif evidence_family == "failure-cause":
        for result_map in maps:
            result_map["hard_wall_resource_abort"]["failure_category"] = (
                "supervised_process_nonzero"
            )
    elif evidence_family == "seal-attempts":
        for result_map in maps:
            result_map["clean_underpowered"]["receipt_seal_attempts"] = 2
    else:
        for result_map in maps:
            result_map["scientific_success"]["receipt_claim_sha256"] = "d" * 64
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="composite",
    ):
        official._validate_composite_acceptance(
            tampered,
            acceptance_sha256="a" * 64,
            corrected_driver_sha256=cast(
                str, record["corrected_official_attempt_driver_source_sha256"]
            ),
            acceptance_driver_sha256=cast(
                str,
                record["official_orchestration_acceptance_driver_source_sha256"],
            ),
            focused_tests_sha256=cast(str, record["focused_tests_sha256"]),
        )


def test_underpowered_payload_has_exact_support_only_accounting() -> None:
    payload = official._underpowered_payload(
        preflight=acceptance._underpowered_preflight(),
        claim_sha256="b" * 64,
        synthetic_orchestration_fixture=True,
    )
    assert set(payload) == {"manifest.json", "preflight.json"}
    manifest = cast(dict[str, Any], json.loads(payload["manifest.json"]))
    assert manifest["status"] == official.UNDERPOWERED_STATUS
    assert manifest["selection_tokens"] == 0
    assert manifest["runner_ups"] == 0
    assert manifest["fit_counts"] == {"stage_a": 0, "stage_b": 0, "stage_c": 0}
    assert manifest["prediction_counts"] == {
        "stage_a": 0,
        "stage_b": 0,
        "stage_c": 0,
    }
    accounting = cast(dict[str, int], manifest["accounting"])
    assert accounting["official_source_rows_opened"] == 19_620
    assert accounting["official_group_fold_rows_opened"] == 73_575
    assert accounting["official_all_fold_rows_opened"] == 73_575
    assert accounting["official_source_target_values_opened"] == 5_197
    assert accounting["official_target_values_opened"] == 5_197
    assert accounting["official_feature_identity_rows_opened"] == 4_905
    assert accounting["official_feature_matrix_rows_opened"] == 19_620
    assert accounting["official_feature_rows_opened"] == 24_525
    assert accounting["official_all_feature_rows_opened"] == 24_525
    assert accounting["claims_consumed"] == 1
    for name in (
        "official_generated_model_fold_rows_opened",
        "official_generated_model_feature_rows_opened",
        "official_baseline_rows_opened",
        "official_scoring_truth_values_opened",
        "official_training_target_values_opened",
        "official_model_fits",
        "official_predictions_generated",
        "official_prediction_rows_opened_for_scoring",
        "development_metric_evaluations",
        "tutorial_metric_calls",
    ):
        assert accounting[name] == 0


def test_recovered_failure_accounting_requires_exact_staged_claim_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, _final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "recover-accounting-lineage"
    )
    _stage_underpowered(claim_sha256)
    assert official._recover_staged_accounting(claim_sha256="e" * 64) == (
        None,
        False,
    )
    accounting, complete = official._recover_staged_accounting(
        claim_sha256=claim_sha256
    )
    assert accounting == official._underpowered_accounting()
    assert complete is True
    official._cleanup_owned_root(attempt.parent)


def test_shared_compiler_boundary_catches_only_the_exact_underpowered_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    preflight = acceptance._underpowered_preflight()

    def exact_stop() -> tuple[Path, Path, dict[str, Any]]:
        raise official.compiler.RobustnessExecutionUnderpowered(preflight)

    compiled, payload = official._compile_capabilities_or_underpowered(
        compile_call=exact_stop,
        claim_sha256="c" * 64,
        synthetic_orchestration_fixture=True,
    )
    assert compiled is None
    assert payload is not None
    assert set(payload) == {"manifest.json", "preflight.json"}

    class DerivedUnderpowered(official.compiler.RobustnessExecutionUnderpowered):
        pass

    def derived_stop() -> tuple[Path, Path, dict[str, Any]]:
        raise DerivedUnderpowered(preflight)

    with pytest.raises(DerivedUnderpowered):
        official._compile_capabilities_or_underpowered(
            compile_call=derived_stop,
            claim_sha256="c" * 64,
            synthetic_orchestration_fixture=True,
        )

    def other_compiler_failure() -> tuple[Path, Path, dict[str, Any]]:
        raise official.compiler.RobustnessExecutionCompilerError("not support")

    with pytest.raises(
        official.compiler.RobustnessExecutionCompilerError, match="not support"
    ):
        official._compile_capabilities_or_underpowered(
            compile_call=other_compiler_failure,
            claim_sha256="c" * 64,
            synthetic_orchestration_fixture=True,
        )

    calls = 0
    shared = official._compile_capabilities_or_underpowered

    def tracked(**kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return shared(**kwargs)

    monkeypatch.setattr(official, "_compile_capabilities_or_underpowered", tracked)
    assert acceptance._probe_exact_underpowered_helper(tmp_path / "shared-probe")
    assert calls > 0


def test_fixed_acceptance_probe_covers_claim_fallback_promotion_and_budget_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = TRACKED_CLAIM.read_bytes()
    monkeypatch.setattr(official, "COMPOSITE_ACCEPTANCE_PARENT", tmp_path)
    assert acceptance._probe_atomic_claim_and_seal_failures(
        tmp_path / "fixed-acceptance-probes"
    )
    assert TRACKED_CLAIM.read_bytes() == before
    assert not acceptance.FIXED_PARENT_ROOT.exists()


@pytest.mark.parametrize(
    ("deletion", "expected"),
    [
        (
            False,
            {
                "official_generated_model_fold_rows_opened": 234_345,
                "official_all_fold_rows_opened": 307_920,
                "official_generated_model_feature_rows_opened": 62_528,
                "official_all_feature_rows_opened": 87_053,
                "official_training_target_values_opened": 2_160_000,
                "official_target_values_opened": 2_196_379,
                "official_model_fits": 720,
                "stage_a_predictions_generated": 422_064,
                "stage_b_predictions_generated": 140_580,
                "stage_c_predictions_generated": 0,
                "official_predictions_generated": 562_644,
                "official_prediction_rows_opened_for_scoring": 984_708,
            },
        ),
        (
            True,
            {
                "official_generated_model_fold_rows_opened": 281_214,
                "official_all_fold_rows_opened": 354_789,
                "official_generated_model_feature_rows_opened": 78_160,
                "official_all_feature_rows_opened": 102_685,
                "official_training_target_values_opened": 3_060_000,
                "official_target_values_opened": 3_096_379,
                "official_model_fits": 1_020,
                "stage_a_predictions_generated": 422_064,
                "stage_b_predictions_generated": 140_580,
                "stage_c_predictions_generated": 234_480,
                "official_predictions_generated": 797_124,
                "official_prediction_rows_opened_for_scoring": 1_219_188,
            },
        ),
    ],
)
def test_completed_accounting_is_exact_for_both_frozen_branches(
    deletion: bool,
    expected: dict[str, int],
) -> None:
    accounting = official._exact_accounting(
        preflight=acceptance._completed_preflight(),
        scoring_manifest={
            "counts": {
                "all_endpoint_rows": 19_620,
                "development_rows_decoded": 15_632,
                "finite_development_point_rows_emitted": 5_197,
                "confirmatory_rows_prefix_checked_suffix_opaque": 3_988,
                "confirmatory_value_fields_decoded": 0,
                "tutorial_eligible_rows": 5_197,
            }
        },
        stage_manifests=acceptance._stage_manifests(deletion=deletion),
        selected_candidate=("G2-7-M2-DROP-AVALON" if deletion else "G2-7-M0-FULL"),
    )
    assert {name: accounting[name] for name in expected} == expected
    assert accounting["official_source_rows_opened"] == 39_240
    assert accounting["official_group_fold_rows_opened"] == 73_575
    assert accounting["official_source_target_values_opened"] == 10_394
    assert accounting["official_scoring_truth_values_opened"] == 25_985
    assert accounting["official_reported_bound_values_opened"] == 31_182
    assert accounting["official_feature_identity_rows_opened"] == 4_905
    assert accounting["official_feature_matrix_rows_opened"] == 19_620
    assert accounting["official_feature_rows_opened"] == 24_525
    assert accounting["official_baseline_rows_opened"] == 93_792
    assert accounting["development_metric_evaluations"] == 1
    assert accounting["tutorial_metric_calls"] == 56
    assert accounting["maximum_tutorial_metric_calls"] == 80
    assert accounting["claims_consumed"] == 1
    projection = 797_232 if deletion else 562_752
    assert accounting["official_predictions_generated"] < projection
    for name in (
        "confirmatory_truth_values_opened",
        "historical_row_level_artifacts_opened",
        "blinded_test_rows_opened",
        "tdi_rows_opened",
        "external_records_acquired",
        "submission_rows_generated",
        "official_metric_calls",
        "leaderboard_observations_used_for_selection",
        "live_uploads",
        "claims_created",
        "private_portal_observations_recorded",
    ):
        assert accounting[name] == 0


def _patch_attempt_paths(monkeypatch: pytest.MonkeyPatch, attempt: Path) -> None:
    monkeypatch.setattr(official, "OFFICIAL_ATTEMPT_ROOT", attempt)
    monkeypatch.setattr(
        official, "CLAIM_STAGING_PATH", attempt / ".attempt-claim-staging"
    )
    monkeypatch.setattr(official.supervisor, "resource_checkpoint", lambda _label: None)


def test_claim_publication_is_fsynced_atomic_read_only_and_no_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "claim-case" / "attempt"
    attempt.parent.mkdir()
    _patch_attempt_paths(monkeypatch, attempt)
    claim = {"fixture": True, "consumptions": 1}
    path, digest = official._consume_claim(claim)
    assert path == attempt / "attempt_claim.json"
    assert digest == official.maplight.sha256_bytes(official.maplight.json_bytes(claim))
    assert path.read_bytes() == official.maplight.json_bytes(claim)
    assert stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) == 0o444
    assert not (attempt / ".attempt-claim-staging").exists()

    with pytest.raises(
        official.RobustnessOfficialAttemptError, match="fixed attempt root exists"
    ):
        official._consume_claim({"fixture": False})
    assert path.read_bytes() == official.maplight.json_bytes(claim)
    official._cleanup_owned_root(attempt.parent)


def test_interrupted_claim_promotion_never_exposes_a_partial_final_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "interrupted-claim" / "attempt"
    attempt.parent.mkdir()
    _patch_attempt_paths(monkeypatch, attempt)

    def interrupted(_source: Path, _destination: Path) -> None:
        raise OSError("injected interruption")

    monkeypatch.setattr(official, "_rename_noreplace", interrupted)
    with pytest.raises(OSError, match="injected interruption"):
        official._consume_claim({"fixture": True})
    assert not (attempt / "attempt_claim.json").exists()
    assert (attempt / ".attempt-claim-staging").is_file()
    official._cleanup_owned_root(attempt)
    assert not attempt.exists()


def test_claim_target_collision_is_never_replaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "claim-collision" / "attempt"
    attempt.parent.mkdir()
    _patch_attempt_paths(monkeypatch, attempt)
    collision = b"preexisting collision sentinel\n"
    real_rename = official._rename_noreplace

    def collide(source: Path, destination: Path) -> None:
        destination.write_bytes(collision)
        os.chmod(destination, 0o444)
        real_rename(source, destination)

    monkeypatch.setattr(official, "_rename_noreplace", collide)
    with pytest.raises(FileExistsError):
        official._consume_claim({"fixture": True})
    final_claim = attempt / "attempt_claim.json"
    assert final_claim.read_bytes() == collision
    assert (attempt / ".attempt-claim-staging").is_file()
    official._cleanup_owned_root(attempt.parent)


def test_owned_root_cleanup_unlinks_symlinks_without_touching_external_sentinel(
    tmp_path: Path,
) -> None:
    sentinel_root = tmp_path / "external-sentinel"
    sentinel_root.mkdir()
    sentinel = sentinel_root / "sentinel"
    sentinel.write_bytes(b"preserve\n")
    owned = tmp_path / "owned" / "nested"
    owned.mkdir(parents=True)
    (owned / "orphan").write_bytes(b"discard\n")
    (owned / "linked").symlink_to(sentinel_root, target_is_directory=True)
    official._cleanup_owned_root(tmp_path / "owned")
    assert not (tmp_path / "owned").exists()
    assert sentinel.read_bytes() == b"preserve\n"

    top_level_link = tmp_path / "owned-link"
    top_level_link.symlink_to(sentinel_root, target_is_directory=True)
    official._cleanup_owned_root(top_level_link)
    assert not os.path.lexists(top_level_link)
    assert sentinel.read_bytes() == b"preserve\n"


def _patch_outer_attempt_paths(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> tuple[Path, Path, Path, Path]:
    root.mkdir()
    attempt = root / "attempt"
    restricted = root / "restricted"
    publication = root / "publication-staging"
    final = attempt / "terminal"
    composite = root / "synthetic-composite-lineage.json"
    composite.write_bytes(b"{}\n")
    monkeypatch.setattr(official, "COMPOSITE_ACCEPTANCE_PARENT", root)
    monkeypatch.setattr(official, "COMPOSITE_ACCEPTANCE", composite)
    monkeypatch.setattr(official, "OFFICIAL_ATTEMPT_ROOT", attempt)
    monkeypatch.setattr(official, "RESTRICTED_ROOT", restricted)
    monkeypatch.setattr(official, "PUBLICATION_STAGING_ROOT", publication)
    monkeypatch.setattr(official, "FINAL_TERMINAL_ROOT", final)
    monkeypatch.setattr(
        official,
        "CLAIM_STAGING_PATH",
        attempt / ".attempt-claim-staging",
    )
    disk_usage = official.shutil.disk_usage(root)._replace(
        free=official.LIMITS.storage_bytes
    )
    monkeypatch.setattr(
        official.shutil,
        "disk_usage",
        lambda _path: disk_usage,
    )
    return attempt, restricted, publication, final


def test_preclaim_supervisor_failure_leaves_no_terminal_and_is_not_reinvoked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "outer-preclaim"
    attempt, restricted, publication, final = _patch_outer_attempt_paths(
        monkeypatch,
        root,
    )
    claim = {"synthetic_orchestration_fixture": True, "consumptions": 1}
    monkeypatch.setattr(official, "derive_consumed_claim", lambda: claim)
    invocations = 0

    def fail_before_claim(*_args: object, **_kwargs: object) -> Any:
        nonlocal invocations
        invocations += 1
        raise supervisor.ResourceSupervisorError("injected preclaim failure")

    monkeypatch.setattr(official.supervisor, "run_supervised", fail_before_claim)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="official attempt failed before claim consumption",
    ):
        official.run_official_attempt()
    assert invocations == 1
    assert not attempt.exists()
    assert not restricted.exists()
    assert not publication.exists()
    assert not final.exists()
    assert not (attempt / "attempt_claim.json").exists()
    official._cleanup_owned_root(root)


def test_postclaim_malformed_observation_seals_one_incomplete_failed_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "outer-postclaim"
    attempt, restricted, publication, final = _patch_outer_attempt_paths(
        monkeypatch,
        root,
    )
    claim = {"synthetic_orchestration_fixture": True, "consumptions": 1}
    monkeypatch.setattr(official, "derive_consumed_claim", lambda: claim)
    monkeypatch.setattr(
        official.supervisor,
        "resource_checkpoint",
        lambda _label: None,
    )
    invocations = 0

    def fail_after_claim(*_args: object, **_kwargs: object) -> Any:
        nonlocal invocations
        invocations += 1
        official._consume_claim(claim)
        raise supervisor.ResourceSupervisorError("wall limit exceeded")

    monkeypatch.setattr(official.supervisor, "run_supervised", fail_after_claim)
    assert official.run_official_attempt() == final
    assert invocations == 1
    files = official._read_flat_files(final)
    assert set(files) == set(acceptance.STATUS_FILE_SETS[official.FAILED_STATUS])
    manifest = cast(dict[str, Any], json.loads(files["manifest.json"]))
    receipt = cast(dict[str, Any], json.loads(files["attempt_receipt.json"]))
    assert manifest["status"] == official.FAILED_STATUS
    assert manifest["failure_category"] == "malformed_supervisor_observation"
    assert manifest["accounting"] is None
    assert manifest["accounting_complete"] is False
    assert manifest["cumulative_supervision"] is None
    assert receipt["accounting_complete"] is False
    assert receipt["cumulative_supervision"] is None
    assert not restricted.exists()
    assert not publication.exists()
    assert not (attempt / ".attempt-claim-staging").exists()
    official._cleanup_owned_root(root)


def test_postclaim_failure_preparation_uses_the_same_five_second_seal_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "outer-postclaim-shared-budget"
    attempt, _restricted, publication, final = _patch_outer_attempt_paths(
        monkeypatch,
        root,
    )
    claim = {"synthetic_orchestration_fixture": True, "consumptions": 1}
    monkeypatch.setattr(official, "derive_consumed_claim", lambda: claim)
    monkeypatch.setattr(
        official.supervisor,
        "resource_checkpoint",
        lambda _label: None,
    )

    def fail_after_claim(*_args: object, **_kwargs: object) -> Any:
        official._consume_claim(claim)
        raise supervisor.ResourceSupervisorError("malformed postclaim observation")

    advanced = False
    real_cleanup = official._cleanup_owned_root

    def cleanup_then_advance(path: Path, *, allow_regular_file: bool = False) -> None:
        nonlocal advanced
        real_cleanup(path, allow_regular_file=allow_regular_file)
        advanced = True

    monkeypatch.setattr(official.supervisor, "run_supervised", fail_after_claim)
    monkeypatch.setattr(official, "_cleanup_owned_root", cleanup_then_advance)
    monkeypatch.setattr(official.time, "monotonic", lambda: 6.0 if advanced else 0.0)
    monkeypatch.setattr(official.time, "process_time", lambda: 0.0)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="shared terminal seal budget is exhausted before sealing",
    ):
        official.run_official_attempt()
    assert (attempt / "attempt_claim.json").is_file()
    assert not final.exists()
    assert not publication.exists()
    real_cleanup(root)


def _prepare_seal_case(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> tuple[Path, Path, str]:
    root.mkdir()
    attempt = root / "attempt"
    attempt.mkdir()
    publication = root / "publication-staging"
    final = attempt / "terminal"
    claim_staging = attempt / ".attempt-claim-staging"
    claim_sha256 = "d" * 64
    claim_path = attempt / "attempt_claim.json"
    claim_path.write_bytes(b"synthetic fixture claim\n")
    os.chmod(claim_path, 0o444)
    composite = root / "synthetic-composite-lineage.json"
    composite.write_bytes(b"{}\n")
    monkeypatch.setattr(official, "COMPOSITE_ACCEPTANCE_PARENT", root)
    monkeypatch.setattr(official, "COMPOSITE_ACCEPTANCE", composite)
    monkeypatch.setattr(official, "OFFICIAL_ATTEMPT_ROOT", attempt)
    monkeypatch.setattr(official, "RESTRICTED_ROOT", root / "restricted")
    monkeypatch.setattr(official, "PUBLICATION_STAGING_ROOT", publication)
    monkeypatch.setattr(official, "FINAL_TERMINAL_ROOT", final)
    monkeypatch.setattr(official, "CLAIM_STAGING_PATH", claim_staging)
    return attempt, final, claim_sha256


def _stage_underpowered(claim_sha256: str) -> None:
    official._stage_payload(
        official._underpowered_payload(
            preflight=acceptance._underpowered_preflight(),
            claim_sha256=claim_sha256,
            synthetic_orchestration_fixture=True,
        )
    )


def _payload_for_status(status_name: str, claim_sha256: str) -> dict[str, bytes]:
    if status_name == "G2_7_PRIMARY_CONTENDER_FROZEN":
        return acceptance._scientific_payload(
            status=status_name,
            claim_sha256=claim_sha256,
            deletion=False,
        )
    if status_name == "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED":
        return acceptance._scientific_payload(
            status=status_name,
            claim_sha256=claim_sha256,
            deletion=True,
        )
    if status_name == official.UNDERPOWERED_STATUS:
        return official._underpowered_payload(
            preflight=acceptance._underpowered_preflight(),
            claim_sha256=claim_sha256,
            synthetic_orchestration_fixture=True,
        )
    return official._failure_payload(
        status=status_name,
        claim_sha256=claim_sha256,
        failure_category=(
            "hard_resource_limit"
            if status_name == official.RESOURCE_ABORTED_STATUS
            else "supervised_process_nonzero"
        ),
        accounting=None,
        accounting_complete=False,
    )


def _observation_for_status(status_name: str) -> Any:
    if status_name == official.RESOURCE_ABORTED_STATUS:
        return _observation(
            wall_seconds=official.LIMITS.wall_seconds,
            return_code=-15,
        )
    if status_name == official.FAILED_STATUS:
        return _observation(return_code=7)
    return _observation()


@pytest.mark.parametrize("status_name", sorted(acceptance.STATUS_FILE_SETS))
def test_every_terminal_status_has_its_exact_files_receipts_and_modes(
    status_name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch,
        tmp_path / f"status-{status_name.lower()}",
    )
    official._stage_payload(_payload_for_status(status_name, claim_sha256))
    observed = _observation_for_status(status_name)
    official._seal_terminal(claim_sha256=claim_sha256, observed=observed)
    files = official._read_flat_files(final)
    assert set(files) == set(acceptance.STATUS_FILE_SETS[status_name])
    assert stat.S_IMODE(final.stat(follow_symlinks=False).st_mode) == 0o555
    for name in files:
        metadata = (final / name).stat(follow_symlinks=False)
        assert stat.S_ISREG(metadata.st_mode)
        assert metadata.st_uid == os.getuid()
        assert metadata.st_nlink == 1
        assert stat.S_IMODE(metadata.st_mode) == 0o444
        assert metadata.st_size == len(files[name])
    receipt = cast(dict[str, Any], json.loads(files["attempt_receipt.json"]))
    bound = {
        name: value for name, value in files.items() if name != "attempt_receipt.json"
    }
    assert receipt["status"] == status_name
    assert receipt["consumed_claim_sha256"] == claim_sha256
    assert receipt["cumulative_supervision"] == vars(observed)
    assert receipt["terminal_file_sha256"] == {
        name: official.maplight.sha256_bytes(value)
        for name, value in sorted(bound.items())
    }
    assert receipt["terminal_file_receipts"] == {
        name: {
            "sha256": official.maplight.sha256_bytes(value),
            "size_bytes": len(value),
            "mode": "0444",
        }
        for name, value in sorted(bound.items())
    }
    official._cleanup_owned_root(attempt.parent)


def test_common_seal_promotes_with_executable_mode_order_and_exact_receipts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "successful-seal"
    )
    _stage_underpowered(claim_sha256)
    real_rename = official._rename_noreplace
    promotion_modes: list[int] = []

    def checked_rename(source: Path, destination: Path) -> None:
        promotion_modes.append(stat.S_IMODE(source.stat(follow_symlinks=False).st_mode))
        assert promotion_modes[-1] == 0o700
        assert all(
            stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) == 0o444
            for path in source.iterdir()
        )
        real_rename(source, destination)

    monkeypatch.setattr(official, "_rename_noreplace", checked_rename)
    returned = official._seal_terminal(
        claim_sha256=claim_sha256,
        observed=_observation(),
    )
    assert returned == final
    assert promotion_modes == [0o700]
    expected = official._read_flat_files(final)
    assert set(expected) == {
        "attempt_receipt.json",
        "manifest.json",
        "preflight.json",
    }
    assert stat.S_IMODE(final.stat(follow_symlinks=False).st_mode) == 0o555
    for name, value in expected.items():
        leaf = final / name
        metadata = leaf.stat(follow_symlinks=False)
        assert stat.S_ISREG(metadata.st_mode)
        assert stat.S_IMODE(metadata.st_mode) == 0o444
        assert metadata.st_uid == os.getuid()
        assert metadata.st_nlink == 1
        assert metadata.st_size == len(value)
    receipt = cast(dict[str, Any], json.loads(expected["attempt_receipt.json"]))
    bound = {
        name: value
        for name, value in expected.items()
        if name != "attempt_receipt.json"
    }
    assert receipt["terminal_file_sha256"] == {
        name: official.maplight.sha256_bytes(value)
        for name, value in sorted(bound.items())
    }
    assert receipt["terminal_file_receipts"] == {
        name: {
            "sha256": official.maplight.sha256_bytes(value),
            "size_bytes": len(value),
            "mode": "0444",
        }
        for name, value in sorted(bound.items())
    }
    assert receipt["seal_attempts"] == 1
    assert receipt["fallback_used"] is False
    assert receipt["implementation_lineage"]["d137_repair_contract_sha256"] == (
        official.REPAIR_CONTRACT_SHA256
    )
    assert receipt["implementation_lineage"]["d138_seal_erratum_sha256"] == (
        official.SEAL_ERRATUM_SHA256
    )
    assert (
        receipt["implementation_lineage"]["d139_test_transition_contract_sha256"]
        == official.TEST_TRANSITION_CONTRACT_SHA256
    )
    identity = _identity_map(final, expected)
    official._validate_promoted_terminal(
        expected_files=expected,
        expected_identity=identity,
        claim_sha256=claim_sha256,
        status=official.UNDERPOWERED_STATUS,
    )
    official._cleanup_owned_root(attempt.parent)


@pytest.mark.parametrize(
    "error_number",
    [
        errno.EXDEV,
        errno.ENOSYS,
        errno.EINVAL,
        errno.EACCES,
        errno.EIO,
    ],
)
def test_any_atomic_promotion_failure_blocks_without_fallback(
    error_number: int,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / f"promotion-{error_number}"
    )
    _stage_underpowered(claim_sha256)
    stage_calls = 0
    rename_calls = 0
    real_stage = official._stage_payload

    def tracked_stage(files: dict[str, bytes]) -> Path:
        nonlocal stage_calls
        stage_calls += 1
        return real_stage(files)

    def failed_promotion(_source: Path, _destination: Path) -> None:
        nonlocal rename_calls
        rename_calls += 1
        raise OSError(error_number, "injected promotion failure")

    monkeypatch.setattr(official, "_stage_payload", tracked_stage)
    monkeypatch.setattr(official, "_rename_noreplace", failed_promotion)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="terminal promotion or post-promotion validation failed",
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert stage_calls == 1
    assert rename_calls == 1
    assert not final.exists()
    assert not official.PUBLICATION_STAGING_ROOT.exists()
    official._cleanup_owned_root(attempt.parent)


def test_final_collision_is_preserved_and_never_uses_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "final-collision"
    )
    _stage_underpowered(claim_sha256)
    final.mkdir()
    sentinel = final / "sentinel"
    sentinel.write_bytes(b"preserve\n")
    stage_calls = 0
    real_stage = official._stage_payload

    def tracked_stage(files: dict[str, bytes]) -> Path:
        nonlocal stage_calls
        stage_calls += 1
        return real_stage(files)

    monkeypatch.setattr(official, "_stage_payload", tracked_stage)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="terminal promotion or post-promotion validation failed",
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert stage_calls == 0
    assert sentinel.read_bytes() == b"preserve\n"
    assert not official.PUBLICATION_STAGING_ROOT.exists()
    official._cleanup_owned_root(attempt.parent)


def test_post_promotion_validation_failure_preserves_terminal_and_never_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch,
        tmp_path / "post-promotion-no-fallback",
    )
    _stage_underpowered(claim_sha256)
    real_stage = official._stage_payload
    real_validate = official._validate_promoted_terminal
    stage_calls = 0
    validation_calls = 0

    def tracked_stage(files: dict[str, bytes]) -> Path:
        nonlocal stage_calls
        stage_calls += 1
        return real_stage(files)

    def mutate_then_validate(**kwargs: object) -> None:
        nonlocal validation_calls
        validation_calls += 1
        leaf = final / "manifest.json"
        os.chmod(final, 0o700)
        os.chmod(leaf, 0o600)
        leaf.write_bytes(leaf.read_bytes() + b" ")
        os.chmod(leaf, 0o444)
        os.chmod(final, 0o555)
        real_validate(**kwargs)

    monkeypatch.setattr(official, "_stage_payload", tracked_stage)
    monkeypatch.setattr(official, "_validate_promoted_terminal", mutate_then_validate)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="terminal promotion or post-promotion validation failed",
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert stage_calls == 1
    assert validation_calls == 1
    assert final.is_dir()
    assert not official.PUBLICATION_STAGING_ROOT.exists()
    official._cleanup_owned_root(attempt.parent)


def test_late_prepromotion_rss_breach_uses_one_resource_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "late-prepromotion-rss"
    )
    _stage_underpowered(claim_sha256)
    rss_values = iter(
        (
            0,
            official.LIMITS.rss_bytes + 1,
            0,
            0,
            0,
            0,
        )
    )
    rss_calls = 0

    def observed_rss() -> int:
        nonlocal rss_calls
        rss_calls += 1
        return next(rss_values)

    monkeypatch.setattr(official, "_current_rss_bytes", observed_rss)
    returned = official._seal_with_fallback(
        claim_sha256=claim_sha256,
        observed=_observation(),
    )
    assert returned == final
    assert rss_calls == 6
    assert _load(final / "manifest.json")["status"] == official.RESOURCE_ABORTED_STATUS
    receipt = _load(final / "attempt_receipt.json")
    assert receipt["seal_attempts"] == 2
    assert receipt["fallback_used"] is True
    official._cleanup_owned_root(attempt.parent)


def test_postpromotion_rss_breach_preserves_visible_terminal_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "postpromotion-rss"
    )
    _stage_underpowered(claim_sha256)
    rss_values = iter((0, 0, official.LIMITS.rss_bytes + 1))
    stage_calls = 0
    real_stage = official._stage_payload

    def tracked_stage(files: dict[str, bytes]) -> Path:
        nonlocal stage_calls
        stage_calls += 1
        return real_stage(files)

    monkeypatch.setattr(official, "_stage_payload", tracked_stage)
    monkeypatch.setattr(official, "_current_rss_bytes", lambda: next(rss_values))
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="terminal promotion or post-promotion validation failed",
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert stage_calls == 1
    assert final.is_dir()
    assert not official.PUBLICATION_STAGING_ROOT.exists()
    official._cleanup_owned_root(attempt.parent)


def test_attempt_readonly_fsync_time_is_inside_shared_seal_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "attempt-readonly-envelope"
    )
    _stage_underpowered(claim_sha256)
    advanced = False
    real_finalize = official._make_attempt_readonly

    def finish_then_advance() -> None:
        nonlocal advanced
        real_finalize()
        advanced = True

    monkeypatch.setattr(official, "_make_attempt_readonly", finish_then_advance)
    monkeypatch.setattr(official.time, "monotonic", lambda: 6.0 if advanced else 0.0)
    monkeypatch.setattr(official.time, "process_time", lambda: 0.0)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="post-promotion attempt finalization exceeded",
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert final.is_dir()
    assert stat.S_IMODE(attempt.stat(follow_symlinks=False).st_mode) == 0o555
    assert not official.PUBLICATION_STAGING_ROOT.exists()
    official._cleanup_owned_root(attempt.parent)


def test_primary_and_fallback_share_one_exhaustible_wall_and_cpu_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "shared-budget"
    )
    _stage_underpowered(claim_sha256)
    calls: list[dict[str, object]] = []
    wall_values = iter((100.0, 100.0, 105.1))
    monkeypatch.setattr(official.time, "monotonic", lambda: next(wall_values))
    monkeypatch.setattr(official.time, "process_time", lambda: 20.0)

    def primary_defect(**kwargs: object) -> Path:
        calls.append(dict(kwargs))
        raise official._SealPrePromotionError("injected pre-promotion defect")

    monkeypatch.setattr(official, "_seal_terminal", primary_defect)
    with pytest.raises(
        official.RobustnessOfficialAttemptError,
        match="shared terminal seal budget is exhausted",
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert len(calls) == 1
    assert calls[0]["seal_started"] == 100.0
    assert calls[0]["seal_cpu_started"] == 20.0
    assert calls[0]["seal_attempts"] == 1
    assert calls[0]["fallback_used"] is False
    assert not final.exists()
    assert not official.PUBLICATION_STAGING_ROOT.exists()
    official._cleanup_owned_root(attempt.parent)


def test_fallback_receives_the_same_budget_origin_and_exact_second_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, _final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / "shared-budget-origin"
    )
    _stage_underpowered(claim_sha256)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(official.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(official.time, "process_time", lambda: 20.0)

    def both_attempts(**kwargs: object) -> Path:
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise official._SealPrePromotionError("primary defect")
        raise official._SealPrePromotionError("fallback defect")

    monkeypatch.setattr(official, "_seal_terminal", both_attempts)
    with pytest.raises(
        official.RobustnessOfficialAttemptError, match="minimal terminal seal failed"
    ):
        official._seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=_observation(),
        )
    assert len(calls) == 2
    assert calls[0]["seal_started"] == calls[1]["seal_started"] == 100.0
    assert calls[0]["seal_cpu_started"] == calls[1]["seal_cpu_started"] == 20.0
    assert calls[0]["seal_attempts"] == 1
    assert calls[0]["fallback_used"] is False
    assert calls[1]["seal_attempts"] == 2
    assert calls[1]["fallback_used"] is True
    official._cleanup_owned_root(attempt.parent)


@pytest.mark.parametrize(
    "mutation", ["bytes", "same-bytes-replacement", "hardlink", "fifo", "extra"]
)
def test_promoted_terminal_rejects_mutated_hardlinked_special_or_extra_leaves(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt, final, claim_sha256 = _prepare_seal_case(
        monkeypatch, tmp_path / f"post-promotion-{mutation}"
    )
    _stage_underpowered(claim_sha256)
    official._seal_terminal(claim_sha256=claim_sha256, observed=_observation())
    expected = official._read_flat_files(final)
    identity = _identity_map(final, expected)
    external_hardlink = final.parent.parent / "external-hardlink"
    if mutation == "bytes":
        leaf = final / "manifest.json"
        os.chmod(leaf, 0o600)
        leaf.write_bytes(leaf.read_bytes() + b" ")
        os.chmod(leaf, 0o444)
    elif mutation == "same-bytes-replacement":
        os.chmod(final, 0o700)
        leaf = final / "manifest.json"
        payload = leaf.read_bytes()
        replacement = final / ".replacement"
        replacement.write_bytes(payload)
        os.chmod(replacement, 0o444)
        leaf.unlink()
        replacement.rename(leaf)
        os.chmod(final, 0o555)
    elif mutation == "hardlink":
        os.link(final / "manifest.json", external_hardlink)
    else:
        os.chmod(final, 0o700)
        if mutation == "fifo":
            leaf = final / "preflight.json"
            leaf.unlink()
            os.mkfifo(leaf, mode=0o444)
        else:
            extra = final / "extra.json"
            extra.write_bytes(b"{}\n")
            os.chmod(extra, 0o444)
        os.chmod(final, 0o555)
    with pytest.raises(official.RobustnessOfficialAttemptError):
        official._validate_promoted_terminal(
            expected_files=expected,
            expected_identity=identity,
            claim_sha256=claim_sha256,
            status=official.UNDERPOWERED_STATUS,
        )
    if external_hardlink.exists():
        external_hardlink.unlink()
    official._cleanup_owned_root(attempt.parent)
