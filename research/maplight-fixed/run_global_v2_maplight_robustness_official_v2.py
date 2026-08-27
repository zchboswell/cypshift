#!/usr/bin/env python3
"""One-use official driver for the corrected G2-7G robustness battery.

The outer process starts cumulative supervision.  Only the supervised child
may create the fixed attempt root and consume the claim.  The trusted compiler
runs in the root runtime; every model stage is a descendant in the pinned
research runtime.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import importlib.metadata
import json
import math
import os
import platform
import resource
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_resource_supervisor as supervisor
import global_v2_maplight_robustness_execution_compiler as compiler
import global_v2_maplight_robustness_execution_wrapper as mechanics
import global_v2_maplight_robustness_scientific_runner as runner
import global_v2_maplight_robustness_scoring_compiler as scoring_compiler
import global_v2_maplight_runner as maplight

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
TRACKED_CLAIM: Final = (
    BENCHMARK / "global_v2_maplight_robustness_execution_claim_v2.json"
)
TRACKED_CLAIM_SHA256: Final = (
    "d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f"
)
ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_execution_acceptance_v2.json"
)
ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_execution_acceptance.v2"
)
ACCEPTANCE_DRIVER: Final = SCRIPT.with_name(
    "run_global_v2_maplight_robustness_execution_acceptance_v2.py"
)
FOCUSED_TESTS: Final = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
)
REPAIR_CONTRACT: Final = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_repair_contract.json"
)
REPAIR_CONTRACT_SHA256: Final = (
    "f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967"
)
SEAL_ERRATUM: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_seal_erratum.json"
)
SEAL_ERRATUM_SHA256: Final = (
    "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33"
)
TEST_TRANSITION_CONTRACT: Final = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_test_transition_contract.json"
)
TEST_TRANSITION_CONTRACT_SHA256: Final = (
    "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
)
SOURCE_SHAPE_TRANSITION_CONTRACT: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_source_shape_"
    "transition_contract.json"
)
SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256: Final = (
    "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
)
PROVENANCE_BRIDGE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
)
PROVENANCE_BRIDGE_SHA256: Final = (
    "2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3"
)
COMPOSITE_ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_acceptance.json"
)
COMPOSITE_ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026."
    "global_v2_maplight_robustness_official_orchestration_acceptance.v1"
)
COMPOSITE_ACCEPTANCE_DRIVER: Final = SCRIPT.with_name(
    "run_global_v2_maplight_robustness_official_orchestration_acceptance.py"
)
ORCHESTRATION_FOCUSED_TESTS: Final = (
    ROOT
    / "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
)
HISTORICAL_OFFICIAL_DRIVER_SHA256: Final = (
    "1675336e449ba9a8327406cb37f82f08e3547076ce6c69fa0ade70c5a3de57fc"
)
HISTORICAL_ACCEPTANCE_DRIVER_SHA256: Final = (
    "7cb471ce6c39e4633b91556cd2c09ee7406dd39912b5d69200fad9372a42e473"
)
HISTORICAL_FOCUSED_TESTS_SHA256: Final = (
    "3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f"
)
IMMUTABLE_SCIENCE_KERNEL_SHA256: Final = {
    "scientific_runner": (
        "dca9b8d1be51a29fa4e2269949d1f3339ecf14d99b91f203aa2cacdd2ca90bde"
    ),
    "robustness_compiler": (
        "029afd827e3a86718e7e2493594bbc6e6ed78e258534221e32acc2027ace72a7"
    ),
    "scoring_compiler": (
        "6f15205fccb4a7c2e1cc2c7244e31acf15d7fd34b285c85145bfde551da6f492"
    ),
    "no_fit_wrapper": (
        "a6e02c244d6bd1b7bcb020dcf9627f68d453ae25827527e6de9acdaa30226c66"
    ),
    "resource_supervisor": (
        "0d7b016b638fb4019eb377328f63a193d23fd6763540a636bd821cbabed63cec"
    ),
    "maplight_runner": (
        "154f8d231c490da7d2af419bfb533ec18a17c2d4ec3938c0373995a3a9acb93f"
    ),
}
SCIENCE_KERNEL_PATHS: Final = {
    "scientific_runner": runner.SCRIPT,
    "robustness_compiler": compiler.SCRIPT,
    "scoring_compiler": scoring_compiler.SCRIPT,
    "no_fit_wrapper": mechanics.SCRIPT,
    "resource_supervisor": supervisor.SCRIPT,
    "maplight_runner": maplight.SCRIPT,
}
MODEL_PYTHON: Final = SCRIPT.parent / ".venv/bin/python"
OFFICIAL_SOURCE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-source-v1"
)
OFFICIAL_BASELINE_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/"
    "g2-2c-maplight-development-attempt-1/terminal"
)
OFFICIAL_ATTEMPT_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/"
    "g2-7g-maplight-robustness-development-attempt-1"
)
RESTRICTED_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/"
    ".g2-7g-maplight-robustness-development-attempt-1-restricted"
)
PUBLICATION_STAGING_ROOT: Final = Path(
    "/home/zbos/cypshift-private/openadmet-2026/"
    ".g2-7h-maplight-robustness-terminal-staging"
)
CLAIM_STAGING_PATH: Final = OFFICIAL_ATTEMPT_ROOT / ".attempt-claim-staging"
FINAL_TERMINAL_ROOT: Final = OFFICIAL_ATTEMPT_ROOT / "terminal"
LIMITS: Final = supervisor.ResourceLimits(
    wall_seconds=7.68 * 60 * 60,
    cpu_seconds=128.0 * 60 * 60,
    storage_bytes=51_200_000_000,
    rss_bytes=int(15.36 * 1024**3),
)
HARD_RESOURCE_REASONS: Final = frozenset(
    {
        "wall limit exceeded",
        "CPU limit exceeded",
        "storage limit exceeded",
        "simultaneous RSS limit exceeded",
    }
)
OBSERVATION_FIELDS: Final = (
    "wall_seconds",
    "cpu_seconds",
    "peak_storage_bytes",
    "peak_simultaneous_rss_bytes",
    "gpu_hours",
    "checkpoints_acknowledged",
    "descendant_processes_observed",
    "return_code",
    "cleanup_complete",
    "network_namespace_isolated",
    "gpu_environment_hidden",
    "detached_children_observed",
    "warnings_observed",
)
SUPERVISOR_OBSERVATION_DELIMITER: Final = "; observation="
MAXIMUM_TERMINAL_BYTES: Final = 16_777_216
MAXIMUM_RECEIPT_BYTES: Final = 1_048_576
MAXIMUM_SEAL_WALL_SECONDS: Final = 5.0
MAXIMUM_SEAL_CPU_SECONDS: Final = 5.0
COMPOSITE_ACCEPTANCE_PARENT: Final = Path("/tmp/cypshift-g2-7h")
SCIENTIFIC_STATUSES: Final = frozenset(
    {"G2_7_PRIMARY_CONTENDER_FROZEN", "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED"}
)
UNDERPOWERED_STATUS: Final = "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED"
RESOURCE_ABORTED_STATUS: Final = "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED"
FAILED_STATUS: Final = "G2_7_MAPLIGHT_ROBUSTNESS_FAILED"


class RobustnessOfficialAttemptError(RuntimeError):
    """The one-use claim, fixed root, execution, or terminal differed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessOfficialAttemptError(message)


def _json(path: Path) -> dict[str, Any]:
    value, _raw = maplight._load_json(path)
    return value


def _authenticate_test_transition_contract() -> str:
    """Authenticate the exact D-139 identity and its frozen parent boundary."""

    _require(
        TEST_TRANSITION_CONTRACT.is_file()
        and not TEST_TRANSITION_CONTRACT.is_symlink()
        and maplight.sha256_path(TEST_TRANSITION_CONTRACT)
        == TEST_TRANSITION_CONTRACT_SHA256,
        "D-139 test-transition contract differs",
    )
    value = _json(TEST_TRANSITION_CONTRACT)
    expected_parents = {
        "d135_science_kernel_acceptance": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_execution_acceptance_v2.json"
            ),
            "sha256": (
                "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390"
            ),
            "integrated_commit": "7450676da651e86bab341c7434dd1b9dd2f19388",
        },
        "d136_test_provenance_bridge": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
            ),
            "sha256": PROVENANCE_BRIDGE_SHA256,
            "integrated_commit": "1c0c5d0f293579a8748e25b3951f9234409bfa39",
        },
        "d137_official_orchestration_repair_contract": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_official_orchestration_"
                "repair_contract.json"
            ),
            "sha256": REPAIR_CONTRACT_SHA256,
            "integrated_commit": "0dbbc7013b5303ef2f1535455d458b87208df1b9",
        },
        "d138_terminal_seal_erratum": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_official_orchestration_"
                "seal_erratum.json"
            ),
            "sha256": SEAL_ERRATUM_SHA256,
            "integrated_commit": "158dffcadfb71305d7de7b84279cfee96a6e8318",
        },
    }
    bindings = value.get("future_transition_bindings")
    _require(
        value.get("schema_version")
        == (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_official_orchestration_"
            "test_transition_contract.v1"
        )
        and value.get("decision_id") == "D-139"
        and value.get("gate")
        == (
            "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_"
            "TEST_TRANSITION_CONTRACT_FROZEN"
        )
        and value.get("contract_id")
        == "G2-7H-MAPLIGHT-ROBUSTNESS-OFFICIAL-ORCHESTRATION-TEST-TRANSITION-V1"
        and value.get("base_commit") == "158dffcadfb71305d7de7b84279cfee96a6e8318"
        and value.get("parent_evidence") == expected_parents
        and isinstance(bindings, Mapping)
        and bindings.get("field_name") == "d139_test_transition_contract_sha256"
        and bindings.get("binding_only_no_behavior_change") is True,
        "D-139 test-transition contract identity differs",
    )
    return TEST_TRANSITION_CONTRACT_SHA256


def _authenticate_source_shape_transition_contract() -> str:
    """Authenticate the exact integrated D-140 provenance boundary."""

    _require(
        SOURCE_SHAPE_TRANSITION_CONTRACT.is_file()
        and not SOURCE_SHAPE_TRANSITION_CONTRACT.is_symlink()
        and maplight.sha256_path(SOURCE_SHAPE_TRANSITION_CONTRACT)
        == SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256,
        "D-140 source-shape transition contract differs",
    )
    value = _json(SOURCE_SHAPE_TRANSITION_CONTRACT)
    bindings = value.get("future_transition_bindings")
    authority = value.get("current_authority")
    _require(
        value.get("schema_version")
        == (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_official_orchestration_"
            "source_shape_transition_contract.v1"
        )
        and value.get("decision_id") == "D-140"
        and value.get("gate")
        == (
            "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_"
            "SOURCE_SHAPE_TRANSITION_CONTRACT_FROZEN"
        )
        and value.get("status")
        == (
            "contract_only_no_source_shape_retirement_or_d141_integration_or_"
            "acceptance_or_official_execution_yet"
        )
        and value.get("contract_id")
        == (
            "G2-7H-MAPLIGHT-ROBUSTNESS-OFFICIAL-ORCHESTRATION-"
            "SOURCE-SHAPE-TRANSITION-V1"
        )
        and value.get("base_commit") == "3b9c251f6875fedb33e51c4420cd8634c6e4cf29"
        and isinstance(bindings, Mapping)
        and bindings.get("field_name") == "d140_source_shape_transition_contract_sha256"
        and bindings.get("binding_only_no_scientific_behavior_change") is True
        and isinstance(authority, Mapping)
        and authority
        == {
            "test_collection_transition": False,
            "implementation": False,
            "model_quality": False,
            "formal_composite_acceptance": False,
            "official_execution": False,
            "official_claim_consumption": False,
            "confirmatory": False,
            "blinded_test": False,
            "submission_generation": False,
            "live_upload": False,
        },
        "D-140 source-shape transition identity differs",
    )
    return SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256


def _authenticate_historical_science_kernel() -> dict[str, Any]:
    """Authenticate the D-135 science evidence without trusting repaired bytes."""

    _require(
        maplight.sha256_path(TRACKED_CLAIM) == TRACKED_CLAIM_SHA256,
        "tracked claim differs",
    )
    _require(
        maplight.sha256_path(ACCEPTANCE)
        == "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390"
        and maplight.sha256_path(PROVENANCE_BRIDGE) == PROVENANCE_BRIDGE_SHA256
        and maplight.sha256_path(REPAIR_CONTRACT) == REPAIR_CONTRACT_SHA256
        and maplight.sha256_path(SEAL_ERRATUM) == SEAL_ERRATUM_SHA256
        and maplight.sha256_path(ACCEPTANCE_DRIVER)
        == HISTORICAL_ACCEPTANCE_DRIVER_SHA256
        and maplight.sha256_path(FOCUSED_TESTS) == HISTORICAL_FOCUSED_TESTS_SHA256
        and all(
            maplight.sha256_path(SCIENCE_KERNEL_PATHS[name]) == expected
            for name, expected in IMMUTABLE_SCIENCE_KERNEL_SHA256.items()
        ),
        "historical science-kernel lineage differs",
    )
    claim = _json(TRACKED_CLAIM)
    acceptance = _json(ACCEPTANCE)
    bridge = _json(PROVENANCE_BRIDGE)
    roots = cast(list[Mapping[str, Any]], acceptance.get("roots"))
    controls = cast(list[Mapping[str, Any]], acceptance.get("real_catboost_controls"))
    observation = cast(Mapping[str, Any], acceptance.get("cumulative_supervision"))

    def accepted_profiles(root: Mapping[str, Any]) -> bool:
        profiles = root.get("profiles")
        if not isinstance(profiles, Mapping) or set(profiles) != {
            "full_retained",
            "deletion_selected",
        }:
            return False
        full = profiles["full_retained"]
        deletion = profiles["deletion_selected"]
        if not isinstance(full, Mapping) or not isinstance(deletion, Mapping):
            return False
        return bool(
            full.get("selection_profile") == "full_retained"
            and full.get("selected_candidate") == "G2-7-M0-FULL"
            and full.get("fit_counts") == {"stage_a": 540, "stage_b": 180, "stage_c": 0}
            and deletion.get("selection_profile") == "deletion_selected"
            and deletion.get("selected_candidate") == "G2-7-M2-DROP-AVALON"
            and deletion.get("fit_counts")
            == {"stage_a": 540, "stage_b": 180, "stage_c": 300}
            and all(
                profile.get("terminal_status")
                == "G2_7G_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
                and profile.get("official_operations") == 0
                and profile.get("claims_created") == 0
                and profile.get("claims_consumed") == 0
                for profile in (full, deletion)
            )
        )

    expected_controls = (
        mechanics.FitIdentity(
            "control", "G2-7-M0-FULL", 1, "PRIMARY_D032", "CYP1A2", 0, 0
        ),
        mechanics.FitIdentity(
            "control",
            "G2-7-M1-DROP-MORGAN",
            2026082411,
            "THRESHOLD_0_55",
            "CYP2D6",
            2,
            4,
        ),
    )
    control_fields = {
        "identity_sha256",
        "candidate_id",
        "random_seed",
        "feature_columns",
        "prediction_rows",
        "resolved_parameter_sha256",
        "finite",
    }

    _require(
        acceptance.get("schema_version") == ACCEPTANCE_SCHEMA
        and acceptance.get("status") == "G2_7G_MAPLIGHT_ROBUSTNESS_EXECUTION_ACCEPTED"
        and acceptance.get("contract_sha256") == runner.CONTRACT_SHA256
        and acceptance.get("scientific_runner_source_sha256")
        == IMMUTABLE_SCIENCE_KERNEL_SHA256["scientific_runner"]
        and acceptance.get("official_attempt_driver_source_sha256")
        == HISTORICAL_OFFICIAL_DRIVER_SHA256
        and acceptance.get("official_shaped_acceptance_driver_source_sha256")
        == HISTORICAL_ACCEPTANCE_DRIVER_SHA256
        and acceptance.get("focused_tests_sha256") == HISTORICAL_FOCUSED_TESTS_SHA256
        and isinstance(roots, list)
        and len(roots) == 2
        and [root.get("source_physical_order_reversed") for root in roots]
        == [False, True]
        and [root.get("fit_launch_order_reversed") for root in roots] == [False, True]
        and all(
            root.get("fit_counts") == {"stage_a": 1080, "stage_b": 360, "stage_c": 300}
            and accepted_profiles(root)
            and root.get("official_operations") == 0
            and root.get("claims_created") == 0
            and root.get("claims_consumed") == 0
            for root in roots
        )
        and roots[0].get("model_capability_tree")
        == roots[1].get("model_capability_tree")
        and roots[0].get("scoring_capability_tree")
        == roots[1].get("scoring_capability_tree")
        and roots[0].get("terminal_tree") == roots[1].get("terminal_tree")
        and isinstance(controls, list)
        and len(controls) == 2
        and all(
            set(control) == control_fields
            and control.get("identity_sha256")
            == maplight.sha256_bytes(identity.token.encode())
            and control.get("candidate_id") == identity.candidate_id
            and control.get("random_seed") == identity.random_seed
            and control.get("feature_columns")
            == runner.SELECTION_FEATURE_COLUMNS[identity.candidate_id]
            and control.get("prediction_rows") == 8
            and compiler._is_sha(control.get("resolved_parameter_sha256"))
            and control.get("finite") is True
            for control, identity in zip(controls, expected_controls, strict=True)
        )
        and acceptance.get("real_catboost_fits") == 2
        and acceptance.get("model_double_invocations") == 3480
        and acceptance.get("both_conditional_paths") is True
        and acceptance.get("profiles_per_root")
        == ["full_retained", "deletion_selected"]
        and acceptance.get("opposite_physical_and_fit_order") is True
        and acceptance.get("capability_maps_byte_identical") is True
        and acceptance.get("terminal_maps_byte_identical") is True
        and acceptance.get("official_operations") == 0
        and acceptance.get("claims_created") == 0
        and acceptance.get("claims_consumed") == 0
        and acceptance.get("private_roots_retained") == 0
        and isinstance(observation, Mapping)
        and observation.get("return_code") == 0
        and observation.get("cleanup_complete") is True
        and observation.get("network_namespace_isolated") is True
        and observation.get("gpu_environment_hidden") is True
        and observation.get("detached_children_observed") == 0
        and observation.get("warnings_observed") == 0
        and int(observation.get("checkpoints_acknowledged", 0)) > 0
        and int(observation.get("descendant_processes_observed", 0)) > 0
        and observation.get("limits") == vars(LIMITS)
        and acceptance.get("cleanup_complete_before_publication") is True
        and acceptance.get("model_quality_authority") is False
        and acceptance.get("claim_authority") is False,
        "official-shaped acceptance differs",
    )
    _require(
        bridge.get("status") == "G2_7G_FOCUSED_TEST_PROVENANCE_RECONCILED"
        and bridge.get("contract_sha256") == runner.CONTRACT_SHA256
        and bridge.get("tracked_claim_sha256") == TRACKED_CLAIM_SHA256
        and bridge.get("formal_acceptance_sha256") == maplight.sha256_path(ACCEPTANCE)
        and bridge.get("scientific_runner_sha256")
        == IMMUTABLE_SCIENCE_KERNEL_SHA256["scientific_runner"]
        and bridge.get("official_driver_sha256") == HISTORICAL_OFFICIAL_DRIVER_SHA256
        and bridge.get("formal_acceptance_driver_sha256")
        == HISTORICAL_ACCEPTANCE_DRIVER_SHA256
        and bridge.get("formal_focused_tests_sha256") == HISTORICAL_FOCUSED_TESTS_SHA256
        and bridge.get("production_files_changed") == 0
        and bridge.get("formal_acceptance_attempts") == 0
        and bridge.get("official_operations") == 0
        and bridge.get("claims_created") == 0
        and bridge.get("claims_consumed") == 0
        and bridge.get("model_quality_authority") is False
        and bridge.get("claim_authority") is False,
        "focused-test provenance bridge differs",
    )
    future_names = {
        "future_scientific_runner_source_sha256",
        "future_official_attempt_driver_source_sha256",
        "future_official_shaped_acceptance_driver_source_sha256",
        "future_official_shaped_execution_acceptance_sha256",
        "future_focused_tests_sha256",
    }
    _require(
        claim.get("status") == "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
        and claim.get("contract_sha256") == runner.CONTRACT_SHA256
        and claim.get("maximum_consumptions") == 1
        and claim.get("consumptions") == 0
        and claim.get("usable") is False
        and all(claim.get(name) is None for name in future_names),
        "unconsumed claim template differs",
    )
    return claim


def _composite_fixture_claim_sha256(scenario: str) -> str:
    denied = {
        "model_quality": False,
        "official_execution": False,
        "official_claim_consumption": False,
        "confirmatory": False,
        "blinded_test": False,
        "submission_generation": False,
        "live_upload": False,
    }
    return maplight.sha256_bytes(
        maplight.json_bytes(
            {
                "schema_version": (
                    "cypshift.openadmet_cyp_2026."
                    "global_v2_maplight_robustness_orchestration_fixture_claim.v1"
                ),
                "status": "G2_7H_SYNTHETIC_FIXTURE_CLAIM_CONSUMED",
                "scenario": scenario,
                "maximum_consumptions": 1,
                "consumptions": 1,
                "usable": False,
                "synthetic_orchestration_fixture": True,
                "official_claim": False,
                "authority": denied,
            }
        )
    )


def _composite_completed_accounting(*, deletion: bool) -> dict[str, int]:
    """Return the exact aggregate-only accounting used by the fixed fixture."""

    return {
        **_base_accounting(),
        "official_source_rows_opened": 39_240,
        "official_group_fold_rows_opened": 73_575,
        "official_generated_model_fold_rows_opened": (281_214 if deletion else 234_345),
        "official_all_fold_rows_opened": 354_789 if deletion else 307_920,
        "official_source_target_values_opened": 10_394,
        "official_scoring_truth_values_opened": 25_985,
        "official_reported_bound_values_opened": 31_182,
        "official_training_target_values_opened": (
            3_060_000 if deletion else 2_160_000
        ),
        "official_target_values_opened": 3_096_379 if deletion else 2_196_379,
        "official_feature_identity_rows_opened": 4_905,
        "official_feature_matrix_rows_opened": 19_620,
        "official_feature_rows_opened": 24_525,
        "official_generated_model_feature_rows_opened": (
            78_160 if deletion else 62_528
        ),
        "official_all_feature_rows_opened": 102_685 if deletion else 87_053,
        "official_baseline_rows_opened": 93_792,
        "official_model_fits": 1_020 if deletion else 720,
        "stage_a_predictions_generated": 422_064,
        "stage_b_predictions_generated": 140_580,
        "stage_c_predictions_generated": 234_480 if deletion else 0,
        "official_predictions_generated": 797_124 if deletion else 562_644,
        "official_prediction_rows_opened_for_scoring": (
            1_219_188 if deletion else 984_708
        ),
        "development_metric_evaluations": 1,
        "tutorial_metric_calls": 56,
        "maximum_tutorial_metric_calls": 80,
        "claims_consumed": 1,
    }


def _validate_composite_file_receipts(
    result: Mapping[str, Any], *, expected_payload_files: set[str]
) -> None:
    bindings = result.get("receipt_file_bindings")
    details = result.get("receipt_file_receipts")
    _require(
        isinstance(bindings, Mapping)
        and set(bindings) == expected_payload_files
        and isinstance(details, Mapping)
        and set(details) == expected_payload_files,
        "composite terminal receipt file set differs",
    )
    binding_map = cast(Mapping[str, Any], bindings)
    detail_map = cast(Mapping[str, Any], details)
    for name in expected_payload_files:
        digest = binding_map.get(name)
        detail = detail_map.get(name)
        _require(
            compiler._is_sha(digest)
            and isinstance(detail, Mapping)
            and set(detail) == {"sha256", "size_bytes", "mode"}
            and detail.get("sha256") == digest
            and isinstance(detail.get("size_bytes"), int)
            and not isinstance(detail.get("size_bytes"), bool)
            and cast(int, detail.get("size_bytes")) > 0
            and detail.get("mode") == "0444",
            "composite terminal receipt binding differs",
        )


def _validate_composite_result_map(
    value: Mapping[str, Any],
    *,
    corrected_driver_sha256: str,
    acceptance_driver_sha256: str,
    focused_tests_sha256: str,
    fixture_lineage_sha256: str,
) -> None:
    """Validate every retained scenario receipt, not only its status label."""

    scenarios = {
        "scientific_success": "G2_7_PRIMARY_CONTENDER_FROZEN",
        "clean_underpowered": UNDERPOWERED_STATUS,
        "scientific_rejection": "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
        "hard_wall_resource_abort": RESOURCE_ABORTED_STATUS,
        "ordinary_nonzero_failure": FAILED_STATUS,
        "pre_consumption_supervisor_failure": ("PRE_CONSUMPTION_FAILURE_PROPAGATED"),
    }
    common_keys = {
        "status",
        "file_set",
        "accounting",
        "accounting_complete",
        "selection_tokens",
        "runner_ups",
        "fit_counts",
        "prediction_counts",
        "tutorial_metric_calls",
        "failure_category",
        "cumulative_supervision",
        "receipt_file_bindings",
        "receipt_file_receipts",
        "receipt_status",
        "receipt_claim_sha256",
        "receipt_implementation_lineage",
        "receipt_resource_limits",
        "receipt_cleanup_complete",
        "receipt_authority",
        "receipt_seal_attempts",
        "receipt_fallback_used",
        "cleanup_complete",
        "terminal_read_only",
        "aggregate_only",
    }
    preconsumption_keys = {
        "status",
        "file_set",
        "accounting",
        "accounting_complete",
        "cumulative_supervision",
        "receipt_file_bindings",
        "receipt_file_receipts",
        "receipt_status",
        "receipt_claim_sha256",
        "receipt_implementation_lineage",
        "receipt_resource_limits",
        "receipt_cleanup_complete",
        "receipt_authority",
        "receipt_seal_attempts",
        "receipt_fallback_used",
        "cleanup_complete",
        "terminal_read_only",
        "aggregate_only",
    }
    _require(set(value) == set(scenarios), "composite scenario map differs")
    expected_lineage = {
        "d135_science_kernel_acceptance_sha256": maplight.sha256_path(ACCEPTANCE),
        "d136_focused_test_provenance_bridge_sha256": PROVENANCE_BRIDGE_SHA256,
        "d137_repair_contract_sha256": REPAIR_CONTRACT_SHA256,
        "d138_seal_erratum_sha256": SEAL_ERRATUM_SHA256,
        "d139_test_transition_contract_sha256": (TEST_TRANSITION_CONTRACT_SHA256),
        "d140_source_shape_transition_contract_sha256": (
            SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
        ),
        "historical_official_driver_sha256": HISTORICAL_OFFICIAL_DRIVER_SHA256,
        "corrected_official_driver_sha256": corrected_driver_sha256,
        "composite_acceptance_sha256": fixture_lineage_sha256,
        "composite_acceptance_driver_sha256": acceptance_driver_sha256,
        "orchestration_focused_tests_sha256": focused_tests_sha256,
        "immutable_science_kernel_source_sha256": dict(IMMUTABLE_SCIENCE_KERNEL_SHA256),
    }
    successful_observation = {
        "wall_seconds": 1.25,
        "cpu_seconds": 0.75,
        "peak_storage_bytes": 4_096,
        "peak_simultaneous_rss_bytes": 64 * 1_024 * 1_024,
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
    for scenario, expected_status in scenarios.items():
        result = value.get(scenario)
        _require(isinstance(result, Mapping), "composite scenario evidence differs")
        result_map = cast(Mapping[str, Any], result)
        if scenario == "pre_consumption_supervisor_failure":
            _require(
                set(result_map) == preconsumption_keys
                and result_map
                == {
                    "status": expected_status,
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
                },
                "pre-consumption composite evidence differs",
            )
            continue

        _require(
            set(result_map) == common_keys
            and result_map.get("status") == expected_status
            and result_map.get("receipt_status") == expected_status
            and result_map.get("receipt_claim_sha256")
            == _composite_fixture_claim_sha256(scenario)
            and result_map.get("receipt_implementation_lineage") == expected_lineage
            and result_map.get("receipt_resource_limits") == vars(LIMITS)
            and result_map.get("receipt_cleanup_complete") is True
            and result_map.get("receipt_authority") == dict(maplight.DENIED_AUTHORITY)
            and result_map.get("receipt_seal_attempts") == 1
            and result_map.get("receipt_fallback_used") is False
            and result_map.get("cleanup_complete") is True
            and result_map.get("terminal_read_only") is True
            and result_map.get("aggregate_only") is True,
            "composite scenario receipt differs",
        )

        scientific = scenario in {"scientific_success", "scientific_rejection"}
        deletion = scenario == "scientific_rejection"
        if scientific:
            expected_files = {
                "manifest.json",
                "primary_metrics.json",
                "robustness.json",
                "selection.json",
            }
            _require(
                result_map.get("accounting")
                == _composite_completed_accounting(deletion=deletion)
                and result_map.get("accounting_complete") is True
                and result_map.get("selection_tokens") == 1
                and result_map.get("runner_ups") == 0
                and result_map.get("fit_counts")
                == {
                    "stage_a": 540,
                    "stage_b": 180,
                    "stage_c": 300 if deletion else 0,
                }
                and result_map.get("prediction_counts")
                == {
                    "stage_a": 422_064,
                    "stage_b": 140_580,
                    "stage_c": 234_480 if deletion else 0,
                }
                and result_map.get("tutorial_metric_calls") == 56
                and result_map.get("failure_category") is None
                and result_map.get("cumulative_supervision") == successful_observation,
                "composite scientific scenario differs",
            )
        elif scenario == "clean_underpowered":
            expected_files = {"manifest.json", "preflight.json"}
            _require(
                result_map.get("accounting") == _underpowered_accounting()
                and result_map.get("accounting_complete") is True
                and result_map.get("selection_tokens") == 0
                and result_map.get("runner_ups") == 0
                and result_map.get("fit_counts")
                == {"stage_a": 0, "stage_b": 0, "stage_c": 0}
                and result_map.get("prediction_counts")
                == {"stage_a": 0, "stage_b": 0, "stage_c": 0}
                and result_map.get("tutorial_metric_calls") == 0
                and result_map.get("failure_category") is None
                and result_map.get("cumulative_supervision") == successful_observation,
                "composite underpowered scenario differs",
            )
        else:
            expected_files = {"manifest.json"}
            hard = scenario == "hard_wall_resource_abort"
            expected_observation = {
                "wall_seconds": LIMITS.wall_seconds + 0.5 if hard else 2.0,
                "cpu_seconds": 1.0,
                "peak_storage_bytes": 8_192,
                "peak_simultaneous_rss_bytes": 64 * 1_024 * 1_024,
                "gpu_hours": 0.0,
                "checkpoints_acknowledged": 2,
                "descendant_processes_observed": 2,
                "return_code": -15 if hard else 7,
                "cleanup_complete": True,
                "network_namespace_isolated": True,
                "gpu_environment_hidden": True,
                "detached_children_observed": 0,
                "warnings_observed": 0,
            }
            _require(
                result_map.get("accounting") is None
                and result_map.get("accounting_complete") is False
                and result_map.get("selection_tokens") is None
                and result_map.get("runner_ups") is None
                and result_map.get("fit_counts") is None
                and result_map.get("prediction_counts") is None
                and result_map.get("tutorial_metric_calls") is None
                and result_map.get("failure_category")
                == ("hard_resource_limit" if hard else "supervised_process_nonzero")
                and result_map.get("cumulative_supervision") == expected_observation,
                "composite failure scenario differs",
            )

        _require(
            result_map.get("file_set")
            == sorted({"attempt_receipt.json", *expected_files}),
            "composite terminal file set differs",
        )
        _validate_composite_file_receipts(
            result_map, expected_payload_files=expected_files
        )


def _validate_composite_acceptance(
    value: Mapping[str, Any],
    *,
    acceptance_sha256: str,
    corrected_driver_sha256: str,
    acceptance_driver_sha256: str,
    focused_tests_sha256: str,
) -> None:
    """Validate the zero-official D-139/D-140 composite acceptance record."""

    _authenticate_test_transition_contract()
    _authenticate_source_shape_transition_contract()

    forbidden = {
        "official_source_or_baseline_bytes_opened": 0,
        "claims_created": 0,
        "claims_consumed": 0,
        "model_double_invocations": 0,
        "real_catboost_fits": 0,
        "predictions_generated": 0,
        "development_metric_evaluations": 0,
        "confirmatory_truth_values_opened": 0,
        "historical_row_level_artifacts_opened": 0,
        "blinded_test_rows_opened": 0,
        "tdi_rows_opened": 0,
        "external_records_acquired": 0,
        "submission_rows_generated": 0,
        "official_metric_calls": 0,
        "leaderboard_observations_used_for_selection": 0,
        "private_portal_observations_recorded": 0,
        "live_uploads": 0,
    }
    required_scenarios = [
        "scientific_success",
        "clean_underpowered",
        "scientific_rejection",
        "hard_wall_resource_abort",
        "ordinary_nonzero_failure",
        "pre_consumption_supervisor_failure",
    ]
    expected_top_level_keys = {
        "schema_version",
        "status",
        "attempt_id",
        "repair_contract_sha256",
        "seal_erratum_sha256",
        "d135_science_kernel_acceptance_sha256",
        "d136_focused_test_provenance_bridge_sha256",
        "d139_test_transition_contract_sha256",
        "d140_source_shape_transition_contract_sha256",
        "historical_official_attempt_driver_source_sha256",
        "corrected_official_attempt_driver_source_sha256",
        "official_orchestration_acceptance_driver_source_sha256",
        "focused_tests_sha256",
        "immutable_science_kernel_source_sha256",
        "scenario_orders",
        "required_scenarios",
        "roots",
        "scenario_invocations",
        "supervisor_invocations",
        "synthetic_scenario_claim_publications",
        "synthetic_fixture_claim_publications",
        "synthetic_probe_claim_publications",
        "synthetic_interrupted_claim_stagings",
        "synthetic_composite_lineage_fixture_sha256",
        "mechanics_probe_counts",
        "statuses_reached",
        "mechanics",
        "opposite_order_maps_byte_identical",
        "exact_underpowered_catch_verified",
        "five_field_prepublication_derivation_verified",
        "d135_science_kernel_evidence",
        "forbidden_operations",
        "cleanup_complete_before_publication",
        "private_roots_retained",
        "model_quality_authority",
        "official_execution_authority",
        "claim_authority",
        "authority",
    }
    inherited = value.get("d135_science_kernel_evidence")
    roots = value.get("roots")
    mechanics_evidence = value.get("mechanics")
    mechanics_names = {
        "five_status_taxonomy",
        "strict_observation_round_trip",
        "opposite_order_map_identity",
        "inherited_scientific_payload_semantics",
        "underpowered_zero_science",
        "hard_resource_vs_ordinary_failure",
        "pre_consumption_fail_closed",
        "atomic_claim_publication",
        "bounded_common_seal_and_collision_fail_closed",
        "symlink_safe_owned_root_cleanup",
        "atomic_promote_then_readonly_root",
    }
    expected_scenario_status = {
        "scientific_success": "G2_7_PRIMARY_CONTENDER_FROZEN",
        "clean_underpowered": UNDERPOWERED_STATUS,
        "scientific_rejection": "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
        "hard_wall_resource_abort": RESOURCE_ABORTED_STATUS,
        "ordinary_nonzero_failure": FAILED_STATUS,
        "pre_consumption_supervisor_failure": ("PRE_CONSUMPTION_FAILURE_PROPAGATED"),
    }
    denied_acceptance_authority = {
        "model_quality": False,
        "official_execution": False,
        "official_claim_consumption": False,
        "confirmatory": False,
        "blinded_test": False,
        "submission_generation": False,
        "live_upload": False,
    }
    fixture_lineage_sha256 = maplight.sha256_bytes(
        maplight.json_bytes(
            {
                "synthetic_orchestration_fixture": True,
                "official_operations": 0,
                "authority": denied_acceptance_authority,
            }
        )
    )
    normalized_result_map: Mapping[str, Any] | None = None
    if isinstance(roots, list) and roots and isinstance(roots[0], Mapping):
        candidate_map = cast(Mapping[str, Any], roots[0]).get("normalized_result_map")
        if isinstance(candidate_map, Mapping):
            normalized_result_map = cast(Mapping[str, Any], candidate_map)
    _require(compiler._is_sha(acceptance_sha256), "composite acceptance hash differs")
    _require(
        set(value) == expected_top_level_keys
        and value.get("schema_version") == COMPOSITE_ACCEPTANCE_SCHEMA
        and value.get("status")
        == "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_ACCEPTED"
        and value.get("attempt_id")
        == "g2-7h-official-orchestration-acceptance-attempt-1"
        and value.get("repair_contract_sha256") == REPAIR_CONTRACT_SHA256
        and value.get("seal_erratum_sha256") == SEAL_ERRATUM_SHA256
        and value.get("d135_science_kernel_acceptance_sha256")
        == maplight.sha256_path(ACCEPTANCE)
        and value.get("d136_focused_test_provenance_bridge_sha256")
        == PROVENANCE_BRIDGE_SHA256
        and value.get("d139_test_transition_contract_sha256")
        == TEST_TRANSITION_CONTRACT_SHA256
        and value.get("d140_source_shape_transition_contract_sha256")
        == SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
        and value.get("historical_official_attempt_driver_source_sha256")
        == HISTORICAL_OFFICIAL_DRIVER_SHA256
        and value.get("corrected_official_attempt_driver_source_sha256")
        == corrected_driver_sha256
        and value.get("official_orchestration_acceptance_driver_source_sha256")
        == acceptance_driver_sha256
        and value.get("focused_tests_sha256") == focused_tests_sha256
        and value.get("immutable_science_kernel_source_sha256")
        == dict(IMMUTABLE_SCIENCE_KERNEL_SHA256)
        and value.get("scenario_orders") == ["forward", "reverse"]
        and value.get("required_scenarios") == required_scenarios
        and value.get("scenario_invocations") == 12
        and value.get("supervisor_invocations") == 12
        and value.get("synthetic_scenario_claim_publications") == 10
        and value.get("synthetic_fixture_claim_publications") == 10
        and value.get("synthetic_probe_claim_publications") == 6
        and value.get("synthetic_interrupted_claim_stagings") == 1
        and value.get("synthetic_composite_lineage_fixture_sha256")
        == fixture_lineage_sha256
        and value.get("mechanics_probe_counts")
        == {
            "exact_underpowered_catches": 1,
            "underpowered_subclass_propagations": 1,
            "ordinary_compiler_failure_propagations": 1,
            "atomic_claim_interruptions": 1,
            "ordinary_seal_fallbacks": 1,
            "resource_seal_fallbacks": 1,
            "final_terminal_collisions": 1,
            "promotion_errors": 1,
            "post_promotion_identity_substitutions": 1,
            "shared_budget_exhaustions": 1,
        }
        and value.get("statuses_reached")
        == sorted(
            (
                *SCIENTIFIC_STATUSES,
                UNDERPOWERED_STATUS,
                RESOURCE_ABORTED_STATUS,
                FAILED_STATUS,
            )
        )
        and isinstance(roots, list)
        and len(roots) == 2
        and [root.get("order") for root in roots if isinstance(root, Mapping)]
        == ["forward", "reverse"]
        and all(
            isinstance(root, Mapping)
            and set(cast(Mapping[str, Any], root))
            == {"order", "scenario_execution_order", "normalized_result_map"}
            and cast(Mapping[str, Any], root).get("scenario_execution_order")
            == (
                required_scenarios if index == 0 else list(reversed(required_scenarios))
            )
            and isinstance(
                cast(Mapping[str, Any], root).get("normalized_result_map"), Mapping
            )
            and set(
                cast(
                    Mapping[str, Any],
                    cast(Mapping[str, Any], root).get("normalized_result_map"),
                )
            )
            == set(required_scenarios)
            for index, root in enumerate(roots)
        )
        and cast(Mapping[str, Any], roots[0]).get("normalized_result_map")
        == cast(Mapping[str, Any], roots[1]).get("normalized_result_map")
        and normalized_result_map is not None
        and all(
            isinstance(normalized_result_map.get(scenario), Mapping)
            and normalized_result_map.get(scenario, {}).get("status")
            == expected_scenario_status[scenario]
            for scenario in required_scenarios
        )
        and isinstance(mechanics_evidence, Mapping)
        and set(mechanics_evidence) == mechanics_names
        and all(item is True for item in mechanics_evidence.values())
        and value.get("opposite_order_maps_byte_identical") is True
        and value.get("exact_underpowered_catch_verified") is True
        and value.get("five_field_prepublication_derivation_verified") is True
        and value.get("cleanup_complete_before_publication") is True
        and value.get("private_roots_retained") == 0
        and inherited
        == {
            "model_double_invocations": 3480,
            "synthetic_predictions_generated": 667872,
            "real_catboost_fits": 2,
            "reexecuted": False,
        }
        and value.get("forbidden_operations") == forbidden
        and value.get("model_quality_authority") is False
        and value.get("official_execution_authority") is False
        and value.get("claim_authority") is False
        and value.get("authority") == denied_acceptance_authority,
        "composite orchestration acceptance differs",
    )
    _validate_composite_result_map(
        cast(Mapping[str, Any], normalized_result_map),
        corrected_driver_sha256=corrected_driver_sha256,
        acceptance_driver_sha256=acceptance_driver_sha256,
        focused_tests_sha256=focused_tests_sha256,
        fixture_lineage_sha256=fixture_lineage_sha256,
    )


def _authenticate_composite_acceptance() -> str:
    _require(
        COMPOSITE_ACCEPTANCE.is_file()
        and not COMPOSITE_ACCEPTANCE.is_symlink()
        and COMPOSITE_ACCEPTANCE_DRIVER.is_file()
        and not COMPOSITE_ACCEPTANCE_DRIVER.is_symlink()
        and ORCHESTRATION_FOCUSED_TESTS.is_file()
        and not ORCHESTRATION_FOCUSED_TESTS.is_symlink(),
        "composite orchestration acceptance is unavailable",
    )
    acceptance_sha256 = maplight.sha256_path(COMPOSITE_ACCEPTANCE)
    _validate_composite_acceptance(
        _json(COMPOSITE_ACCEPTANCE),
        acceptance_sha256=acceptance_sha256,
        corrected_driver_sha256=maplight.sha256_path(SCRIPT),
        acceptance_driver_sha256=maplight.sha256_path(COMPOSITE_ACCEPTANCE_DRIVER),
        focused_tests_sha256=maplight.sha256_path(ORCHESTRATION_FOCUSED_TESTS),
    )
    return acceptance_sha256


def derive_consumed_claim() -> dict[str, Any]:
    """Derive the sole private claim only after both public gates authenticate."""

    claim = _authenticate_historical_science_kernel()
    composite_sha256 = _authenticate_composite_acceptance()
    future = {
        "future_scientific_runner_source_sha256": maplight.sha256_path(runner.SCRIPT),
        "future_official_attempt_driver_source_sha256": maplight.sha256_path(SCRIPT),
        "future_official_shaped_acceptance_driver_source_sha256": maplight.sha256_path(
            COMPOSITE_ACCEPTANCE_DRIVER
        ),
        "future_official_shaped_execution_acceptance_sha256": composite_sha256,
        "future_focused_tests_sha256": maplight.sha256_path(
            ORCHESTRATION_FOCUSED_TESTS
        ),
    }
    return {
        **claim,
        **future,
        "status": "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_CONSUMED",
        "consumptions": 1,
        "usable": False,
    }


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _require_fixed_parent(path: Path, label: str) -> None:
    """Require an absolute, non-symlinked existing parent without resolving target."""

    _require(path.is_absolute() and ".." not in path.parts, f"{label} differs")
    _require(len(path.parts) >= 4, f"{label} is too broad")
    current = Path(path.anchor)
    for part in path.parent.parts[1:]:
        current /= part
        observed = _lstat(current)
        _require(
            observed is not None
            and stat.S_ISDIR(observed.st_mode)
            and not stat.S_ISLNK(observed.st_mode),
            f"{label} parent differs",
        )


def _require_absent(path: Path, label: str) -> None:
    _require(_lstat(path) is None, f"{label} exists")


def _open_directory(path: Path) -> int:
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def _fsync_directory(path: Path) -> None:
    descriptor = _open_directory(path)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_regular_bytes(path: Path, *, maximum_bytes: int | None = None) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        observed = os.fstat(descriptor)
        _require(
            stat.S_ISREG(observed.st_mode)
            and observed.st_uid == os.getuid()
            and observed.st_nlink == 1
            and stat.S_IMODE(observed.st_mode) in {0o400, 0o444, 0o600, 0o644},
            "aggregate file identity differs",
        )
        if maximum_bytes is not None:
            _require(observed.st_size <= maximum_bytes, "aggregate file is too large")
        chunks: list[bytes] = []
        remaining = observed.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            _require(bool(chunk), "aggregate file was truncated")
            chunks.append(chunk)
            remaining -= len(chunk)
        _require(not os.read(descriptor, 1), "aggregate file grew while reading")
        after = os.fstat(descriptor)
        _require(
            (
                observed.st_dev,
                observed.st_ino,
                observed.st_uid,
                observed.st_nlink,
                observed.st_mode,
                observed.st_size,
                observed.st_mtime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_uid,
                after.st_nlink,
                after.st_mode,
                after.st_size,
                after.st_mtime_ns,
            ),
            "aggregate file changed while reading",
        )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_exclusive_bytes(path: Path, value: bytes, *, mode: int = 0o600) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode,
    )
    try:
        written = 0
        while written < len(value):
            count = os.write(descriptor, value[written:])
            _require(count > 0, "aggregate file write made no progress")
            written += count
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically rename one owned entry without replacing a visible target."""

    _require(source.name not in {"", ".", ".."}, "source name differs")
    _require(destination.name not in {"", ".", ".."}, "destination name differs")
    source_parent = _open_directory(source.parent)
    destination_parent = _open_directory(destination.parent)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = cast(Any, getattr(libc, "renameat2", None))
        _require(renameat2 is not None, "renameat2 is unavailable")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            source_parent,
            os.fsencode(source.name),
            destination_parent,
            os.fsencode(destination.name),
            1,  # RENAME_NOREPLACE
        )
        if result != 0:
            observed = ctypes.get_errno()
            if observed == errno.EEXIST:
                raise FileExistsError(observed, os.strerror(observed), destination)
            raise OSError(observed, os.strerror(observed), destination)
    finally:
        os.close(source_parent)
        os.close(destination_parent)


def _cleanup_owned_root(path: Path, *, allow_regular_file: bool = False) -> None:
    """Remove exactly one owned tree; unlink symlinks and never follow them."""

    observed = _lstat(path)
    if observed is None:
        return
    if stat.S_ISLNK(observed.st_mode):
        os.unlink(path)
        return
    if not stat.S_ISDIR(observed.st_mode):
        _require(allow_regular_file, "owned cleanup root is not a directory")
        os.unlink(path)
        return
    try:
        os.chmod(path, 0o700, follow_symlinks=False)
    except OSError:
        pass
    with os.scandir(path) as entries:
        children = [Path(entry.path) for entry in entries]
    for child in children:
        child_stat = _lstat(child)
        if child_stat is None:
            continue
        if stat.S_ISDIR(child_stat.st_mode) and not stat.S_ISLNK(child_stat.st_mode):
            _cleanup_owned_root(child)
        else:
            if not stat.S_ISLNK(child_stat.st_mode):
                try:
                    os.chmod(child, 0o600, follow_symlinks=False)
                except (OSError, NotImplementedError):
                    pass
            os.unlink(child)
    os.rmdir(path)


def _consume_claim(claim: Mapping[str, Any]) -> tuple[Path, str]:
    """Publish the consumed claim through one fixed, fsynced no-replace path."""

    _require_fixed_parent(OFFICIAL_ATTEMPT_ROOT, "fixed attempt root")
    _require_absent(OFFICIAL_ATTEMPT_ROOT, "fixed attempt root")
    os.mkdir(OFFICIAL_ATTEMPT_ROOT, mode=0o700)
    _fsync_directory(OFFICIAL_ATTEMPT_ROOT.parent)
    path = OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json"
    staging = OFFICIAL_ATTEMPT_ROOT / ".attempt-claim-staging"
    _require(staging == CLAIM_STAGING_PATH, "fixed claim staging path differs")
    claim_bytes = maplight.json_bytes(claim)
    try:
        _write_exclusive_bytes(staging, claim_bytes, mode=0o444)
        _fsync_directory(OFFICIAL_ATTEMPT_ROOT)
        _rename_noreplace(staging, path)
        _fsync_directory(OFFICIAL_ATTEMPT_ROOT)
    except BaseException:
        # The outer pre/post-consumption path owns interruption cleanup.  Never
        # remove a visible final claim here and never replace it.
        raise
    supervisor.resource_checkpoint("stage:claim-consumed")
    return path, maplight.sha256_bytes(claim_bytes)


def _compiler_authorization(
    claim: Mapping[str, Any], claim_sha256: str
) -> dict[str, Any]:
    return {
        "schema_version": compiler.OFFICIAL_AUTHORIZATION_SCHEMA,
        "status": "G2_7C_OFFICIAL_AUTHORIZED",
        "bounded_contract_sha256": compiler.BOUNDED_CONTRACT_SHA256,
        "compiler_source_sha256": maplight.sha256_path(compiler.SCRIPT),
        "claim_sha256": claim_sha256,
        "claim_contract_sha256": runner.CONTRACT_SHA256,
        "maximum_consumptions": 1,
        "official_input_receipts": claim["official_input_receipts"],
    }


def _scoring_authorization(claim_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": scoring_compiler.OFFICIAL_AUTHORIZATION_SCHEMA,
        "status": "G2_7F_SCORING_AUTHORIZED",
        "scoring_contract_sha256": scoring_compiler.CONTRACT_SHA256,
        "permanently_unusable_d127_claim_sha256": scoring_compiler.D127_CLAIM_SHA256,
        "corrected_consumed_claim_sha256": claim_sha256,
        "corrected_execution_contract_sha256": runner.CONTRACT_SHA256,
        "official_source_root": str(OFFICIAL_SOURCE_ROOT),
        "direct_observations_sha256": (
            "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7"
        ),
    }


def _run_model_stage(
    *, stage: str, selected: str | None, model_root: Path, output_root: Path
) -> Path:
    subprocess.run(
        [
            str(MODEL_PYTHON),
            str(runner.SCRIPT),
            "prediction-stage",
            "--stage",
            stage,
            "--selected-candidate",
            selected or "-",
            "--model-root",
            str(model_root),
            "--output-root",
            str(output_root),
        ],
        check=True,
    )
    return output_root


def _strict_nonnegative_int(value: object, label: str) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{label} differs",
    )
    return cast(int, value)


def _base_accounting() -> dict[str, int]:
    granular = (
        "official_group_fold_rows_opened",
        "official_generated_model_fold_rows_opened",
        "official_all_fold_rows_opened",
        "official_source_target_values_opened",
        "official_reported_bound_values_opened",
        "official_feature_identity_rows_opened",
        "official_feature_matrix_rows_opened",
        "official_generated_model_feature_rows_opened",
        "official_all_feature_rows_opened",
        "official_baseline_rows_opened",
        "official_scoring_truth_values_opened",
        "official_training_target_values_opened",
        "official_prediction_rows_opened_for_scoring",
        "stage_a_predictions_generated",
        "stage_b_predictions_generated",
        "stage_c_predictions_generated",
        "tutorial_metric_calls",
        "maximum_tutorial_metric_calls",
        "synthetic_model_fits",
        "synthetic_predictions_generated",
        "model_double_invocations",
        "real_catboost_controls",
    )
    return {name: 0 for name in (*compiler.DENIED_ACCOUNTING, *granular)}


def _underpowered_accounting() -> dict[str, int]:
    return {
        **_base_accounting(),
        "official_source_rows_opened": 19_620,
        "official_group_fold_rows_opened": 73_575,
        "official_all_fold_rows_opened": 73_575,
        "official_source_target_values_opened": 5_197,
        "official_target_values_opened": 5_197,
        "official_feature_identity_rows_opened": 4_905,
        "official_feature_matrix_rows_opened": 19_620,
        "official_feature_rows_opened": 24_525,
        "official_all_feature_rows_opened": 24_525,
        "claims_consumed": 1,
        "maximum_tutorial_metric_calls": 80,
    }


def _support_training_sums(preflight: Mapping[str, Any]) -> tuple[int, int, int]:
    _require(
        preflight.get("status") == "G2_7C_NO_FIT_PREFLIGHT_PASS"
        and preflight.get("failures") == []
        and preflight.get("minima") == dict(compiler.MINIMA),
        "completed preflight status differs",
    )
    support = preflight.get("support")
    exclusions = preflight.get("confirmatory_touch_excluded_molecules")
    _require(isinstance(support, Mapping), "preflight support differs")
    _require(
        isinstance(exclusions, Mapping) and set(exclusions) == set(compiler.GROUPS),
        "preflight exclusions differ",
    )
    support_map = cast(Mapping[str, Any], support)
    exclusion_map = cast(Mapping[str, Any], exclusions)
    expected_keys = {
        f"{group}|{endpoint}|r{repeat}|f{fold}"
        for group in compiler.GROUPS
        for endpoint in compiler.ENDPOINTS
        for repeat in compiler.REPEATS
        for fold in compiler.OUTER_FOLDS
    }
    _require(set(support_map) == expected_keys, "preflight support keys differ")
    primary = 0
    overlays = 0
    for key, item in support_map.items():
        _require(
            isinstance(item, Mapping) and set(item) == {"training", "validation"},
            "preflight support item differs",
        )
        training = _strict_nonnegative_int(item.get("training"), "training support")
        validation = _strict_nonnegative_int(
            item.get("validation"), "validation support"
        )
        _require(
            training
            >= compiler.MINIMA["outer_training_targets_per_endpoint_repeat_fold"]
            and validation
            >= compiler.MINIMA["outer_validation_targets_per_endpoint_repeat_fold"],
            "completed preflight support is underpowered",
        )
        if str(key).startswith("PRIMARY_D032|"):
            primary += training
        else:
            overlays += training
    excluded: dict[str, int] = {
        str(group): _strict_nonnegative_int(value, "preflight exclusion")
        for group, value in exclusion_map.items()
    }
    _require(
        excluded["PRIMARY_D032"] == 0
        and all(
            excluded[group] > 0 for group in compiler.GROUPS if group != "PRIMARY_D032"
        )
        and all(value < 3_908 for value in excluded.values()),
        "preflight exclusion semantics differ",
    )
    model_fold_rows = 3 * sum(3_908 - excluded[group] for group in compiler.GROUPS)
    return primary, overlays, model_fold_rows


def _exact_accounting(
    *,
    preflight: Mapping[str, Any],
    scoring_manifest: Mapping[str, Any],
    stage_manifests: Mapping[str, Mapping[str, Any]],
    selected_candidate: str,
) -> dict[str, int]:
    """Reconstruct exact completed-battery accounting from aggregate manifests."""

    _require(
        selected_candidate in runner.SELECTION_FEATURE_COLUMNS,
        "selected candidate differs",
    )
    deletion_selected = selected_candidate != "G2-7-M0-FULL"
    _require(
        set(stage_manifests)
        == (
            {"stage_a", "stage_b", "stage_c"}
            if deletion_selected
            else {"stage_a", "stage_b"}
        ),
        "completed stage set differs",
    )
    primary_training, overlay_training, model_fold_rows = _support_training_sums(
        preflight
    )
    expected: dict[str, tuple[int, int | None, int]] = {
        "stage_a": (540, 422_064, 9 * primary_training),
        "stage_b": (180, None, overlay_training),
    }
    if deletion_selected:
        expected["stage_c"] = (300, 234_480, 5 * primary_training)

    predictions: dict[str, int] = {}
    total_training = 0
    for stage, manifest in stage_manifests.items():
        fits_expected, predictions_expected, training_expected = expected[stage]
        fits = _strict_nonnegative_int(manifest.get("fit_identities"), "stage fits")
        prediction_rows = _strict_nonnegative_int(
            manifest.get("prediction_identities"), "stage predictions"
        )
        training = _strict_nonnegative_int(
            manifest.get("training_target_values_opened"), "stage training targets"
        )
        _require(
            manifest.get("stage") == stage
            and fits == fits_expected
            and training == training_expected
            and (
                prediction_rows == predictions_expected
                if predictions_expected is not None
                else 0 < prediction_rows < 140_688
            ),
            f"{stage} aggregate accounting differs",
        )
        stage_accounting = manifest.get("accounting")
        _require(
            isinstance(stage_accounting, Mapping)
            and stage_accounting.get("official_model_fits") == fits
            and stage_accounting.get("official_predictions_generated")
            == prediction_rows,
            f"{stage} embedded accounting differs",
        )
        predictions[stage] = prediction_rows
        total_training += training

    counts = scoring_manifest.get("counts")
    _require(isinstance(counts, Mapping), "scoring counts differ")
    counts_map = cast(Mapping[str, Any], counts)
    _require(
        all(
            counts_map.get(name) == expected_count
            for name, expected_count in {
                "all_endpoint_rows": 19_620,
                "development_rows_decoded": 15_632,
                "finite_development_point_rows_emitted": 5_197,
                "confirmatory_rows_prefix_checked_suffix_opaque": 3_988,
                "confirmatory_value_fields_decoded": 0,
            }.items()
        ),
        "scoring population counts differ",
    )
    tutorial_eligible = _strict_nonnegative_int(
        counts_map.get("tutorial_eligible_rows"), "tutorial eligible rows"
    )
    _require(tutorial_eligible <= 5_197, "tutorial eligible rows differ")
    stage_a_predictions = predictions["stage_a"]
    stage_b_predictions = predictions["stage_b"]
    stage_c_predictions = predictions.get("stage_c", 0)
    _require(
        stage_b_predictions % 12 == 0
        and model_fold_rows == 11_724 + stage_b_predictions // 4,
        "stage-B prediction/fold identity differs",
    )
    total_predictions = sum(predictions.values())
    upper_projection = 797_232 if deletion_selected else 562_752
    _require(total_predictions < upper_projection, "prediction projection differs")
    generated_folds = (6 if deletion_selected else 5) * model_fold_rows
    generated_features = (5 if deletion_selected else 4) * 4 * 3_908
    return {
        **_base_accounting(),
        "official_source_rows_opened": 39_240,
        "official_group_fold_rows_opened": 73_575,
        "official_generated_model_fold_rows_opened": generated_folds,
        "official_all_fold_rows_opened": 73_575 + generated_folds,
        "official_source_target_values_opened": 10_394,
        "official_scoring_truth_values_opened": 25_985,
        "official_reported_bound_values_opened": 6 * tutorial_eligible,
        "official_training_target_values_opened": total_training,
        "official_target_values_opened": 36_379 + total_training,
        "official_feature_identity_rows_opened": 4_905,
        "official_feature_matrix_rows_opened": 19_620,
        "official_feature_rows_opened": 24_525,
        "official_generated_model_feature_rows_opened": generated_features,
        "official_all_feature_rows_opened": 24_525 + generated_features,
        "official_baseline_rows_opened": 93_792,
        "official_model_fits": 1_020 if deletion_selected else 720,
        "stage_a_predictions_generated": stage_a_predictions,
        "stage_b_predictions_generated": stage_b_predictions,
        "stage_c_predictions_generated": stage_c_predictions,
        "official_predictions_generated": total_predictions,
        "official_prediction_rows_opened_for_scoring": (
            2 * stage_a_predictions + stage_b_predictions + stage_c_predictions
        ),
        "development_metric_evaluations": 1,
        "tutorial_metric_calls": 56,
        "maximum_tutorial_metric_calls": 80,
        "claims_consumed": 1,
    }


def _underpowered_payload(
    *,
    preflight: Mapping[str, Any],
    claim_sha256: str,
    synthetic_orchestration_fixture: bool = False,
) -> dict[str, bytes]:
    _require(
        preflight.get("status") == "G2_7C_NO_FIT_UNDERPOWERED"
        and isinstance(preflight.get("failures"), list)
        and bool(preflight.get("failures")),
        "underpowered preflight differs",
    )
    preflight_bytes = maplight.json_bytes(dict(preflight))
    manifest: dict[str, Any] = {
        "schema_version": runner.TERMINAL_SCHEMA,
        "status": UNDERPOWERED_STATUS,
        "synthetic": synthetic_orchestration_fixture,
        "contract_sha256": runner.CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "selected_candidate": None,
        "selection_tokens": 0,
        "runner_ups": 0,
        "fit_counts": {"stage_a": 0, "stage_b": 0, "stage_c": 0},
        "prediction_counts": {"stage_a": 0, "stage_b": 0, "stage_c": 0},
        "tutorial_metric_calls": 0,
        "maximum_tutorial_metric_calls": 80,
        "row_level_values_retained": 0,
        "model_binaries_retained": 0,
        "accounting": _underpowered_accounting(),
        "accounting_complete": True,
        "output_receipts": {"preflight.json": maplight.sha256_bytes(preflight_bytes)},
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    if synthetic_orchestration_fixture:
        manifest["synthetic_orchestration_fixture"] = True
    return {
        "manifest.json": maplight.json_bytes(manifest),
        "preflight.json": preflight_bytes,
    }


def _read_flat_files(root: Path) -> dict[str, bytes]:
    observed = _lstat(root)
    _require(
        observed is not None
        and stat.S_ISDIR(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode),
        "aggregate root differs",
    )
    root_stat = cast(os.stat_result, observed)
    _require(
        root_stat.st_uid == os.getuid()
        and stat.S_IMODE(root_stat.st_mode) in {0o555, 0o700, 0o755},
        "aggregate root differs",
    )
    files: dict[str, bytes] = {}
    with os.scandir(root) as entries:
        for entry in entries:
            entry_stat = entry.stat(follow_symlinks=False)
            _require(
                stat.S_ISREG(entry_stat.st_mode) and not entry.is_symlink(),
                "aggregate root is not flat and regular",
            )
            files[entry.name] = _read_regular_bytes(
                Path(entry.path), maximum_bytes=MAXIMUM_TERMINAL_BYTES
            )
    after = _lstat(root)
    _require(after is not None, "aggregate root disappeared while reading")
    after_stat = cast(os.stat_result, after)
    _require(
        (
            root_stat.st_dev,
            root_stat.st_ino,
            root_stat.st_uid,
            root_stat.st_mode,
            root_stat.st_mtime_ns,
        )
        == (
            after_stat.st_dev,
            after_stat.st_ino,
            after_stat.st_uid,
            after_stat.st_mode,
            after_stat.st_mtime_ns,
        ),
        "aggregate root changed while reading",
    )
    return files


def _terminal_bytes(root: Path) -> dict[str, bytes]:
    files = _read_flat_files(root)
    _require(
        set(files)
        == {
            "manifest.json",
            "primary_metrics.json",
            "robustness.json",
            "selection.json",
        },
        "aggregate terminal files differ",
    )
    return files


def _stage_payload(files: Mapping[str, bytes]) -> Path:
    _require_fixed_parent(PUBLICATION_STAGING_ROOT, "publication staging root")
    _require_absent(PUBLICATION_STAGING_ROOT, "publication staging root")
    os.mkdir(PUBLICATION_STAGING_ROOT, mode=0o700)
    try:
        for name, value in sorted(files.items()):
            _require(
                name == Path(name).name and name not in {"", ".", ".."},
                "aggregate filename differs",
            )
            _write_exclusive_bytes(PUBLICATION_STAGING_ROOT / name, value)
        _fsync_directory(PUBLICATION_STAGING_ROOT)
    except BaseException:
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        raise
    return PUBLICATION_STAGING_ROOT


def _compile_capabilities_or_underpowered(
    *,
    compile_call: Callable[[], tuple[Path, Path, dict[str, Any]]],
    claim_sha256: str,
    synthetic_orchestration_fixture: bool = False,
) -> tuple[
    tuple[Path, Path, dict[str, Any]] | None,
    dict[str, bytes] | None,
]:
    """Catch only the compiler's exact frozen support-stop exception."""

    try:
        compiled = compile_call()
    except compiler.RobustnessExecutionUnderpowered as exc:
        if type(exc) is not compiler.RobustnessExecutionUnderpowered:
            raise
        return None, _underpowered_payload(
            preflight=exc.preflight,
            claim_sha256=claim_sha256,
            synthetic_orchestration_fixture=synthetic_orchestration_fixture,
        )
    return compiled, None


def _child() -> int:
    """Trusted child: descendants may create only validated private artifacts.

    Same-UID concurrent root substitution is outside the frozen threat model;
    every preexisting or descendant-created symlink is nevertheless unlinked
    without following it during cleanup.
    """

    supervisor.resource_checkpoint("stage:official-child-authorized")
    _require(
        platform.python_version() == "3.12.3"
        and importlib.metadata.version("rdkit") == "2026.3.5",
        "trusted compiler/scorer runtime differs",
    )
    claim = derive_consumed_claim()
    runner.authenticate_static_boundary()
    _require(
        OFFICIAL_SOURCE_ROOT == compiler.OFFICIAL_SOURCE_ROOT
        and OFFICIAL_SOURCE_ROOT.resolve(strict=True) == compiler.OFFICIAL_SOURCE_ROOT
        and OFFICIAL_BASELINE_ROOT.resolve(strict=True) == OFFICIAL_BASELINE_ROOT
        and MODEL_PYTHON.is_symlink(),
        "fixed official roots or model runtime differ",
    )
    _claim_path, claim_sha256 = _consume_claim(claim)
    work = RESTRICTED_ROOT / "work"
    files: dict[str, bytes]
    try:
        work.mkdir(mode=0o700)
        compiled, underpowered_files = _compile_capabilities_or_underpowered(
            compile_call=lambda: compiler.compile_capabilities(
                source_root=OFFICIAL_SOURCE_ROOT,
                output_root=work / "d126-capabilities",
                mode="official",
                authorization=_compiler_authorization(claim, claim_sha256),
                expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
            ),
            claim_sha256=claim_sha256,
        )
        if compiled is None:
            _require(underpowered_files is not None, "underpowered payload is absent")
            files = cast(dict[str, bytes], underpowered_files)
        else:
            _require(underpowered_files is None, "unexpected underpowered payload")
            model, central_scorer, preflight = compiled
            scoring = scoring_compiler.compile_scoring_capability(
                direct_source_root=OFFICIAL_SOURCE_ROOT,
                model_capability_root=model,
                scorer_capability_root=central_scorer,
                output_root=work / "eight-field-scorer",
                mode="official",
                authorization=_scoring_authorization(claim_sha256),
                expected_compiler_sha256=maplight.sha256_path(scoring_compiler.SCRIPT),
            )
            stage_a = _run_model_stage(
                stage="stage_a",
                selected=None,
                model_root=model,
                output_root=work / "stage-a",
            )
            selected, selection = runner.select_stage_a_candidate(
                stage_a_root=stage_a,
                scoring_capability_root=scoring,
                baseline_terminal_root=OFFICIAL_BASELINE_ROOT,
                model_capability_root=model,
                synthetic=False,
            )
            stage_b = _run_model_stage(
                stage="stage_b",
                selected=selected,
                model_root=model,
                output_root=work / "stage-b",
            )
            stage_c = None
            if selected != "G2-7-M0-FULL":
                stage_c = _run_model_stage(
                    stage="stage_c",
                    selected=selected,
                    model_root=model,
                    output_root=work / "stage-c",
                )
            terminal = runner.score_frozen_battery(
                selected_candidate=selected,
                selection_evidence=selection,
                stage_a_root=stage_a,
                stage_b_root=stage_b,
                stage_c_root=stage_c,
                scoring_capability_root=scoring,
                baseline_terminal_root=OFFICIAL_BASELINE_ROOT,
                model_capability_root=model,
                output_root=work / "aggregate-terminal",
                synthetic=False,
                consumed_claim_sha256=claim_sha256,
            )
            files = _terminal_bytes(terminal)
            stage_manifests: dict[str, Mapping[str, Any]] = {
                "stage_a": _json(stage_a / "manifest.json"),
                "stage_b": _json(stage_b / "manifest.json"),
            }
            if stage_c is not None:
                stage_manifests["stage_c"] = _json(stage_c / "manifest.json")
            accounting = _exact_accounting(
                preflight=preflight,
                scoring_manifest=_json(scoring / "manifest.json"),
                stage_manifests=stage_manifests,
                selected_candidate=selected,
            )
            manifest = cast(dict[str, Any], json.loads(files["manifest.json"]))
            _require(
                manifest.get("selected_candidate") == selected
                and manifest.get("selection_tokens") == 1
                and manifest.get("runner_ups") == 0
                and manifest.get("fit_counts")
                == {
                    "stage_a": 540,
                    "stage_b": 180,
                    "stage_c": 300 if stage_c is not None else 0,
                }
                and manifest.get("prediction_counts")
                == {
                    "stage_a": accounting["stage_a_predictions_generated"],
                    "stage_b": accounting["stage_b_predictions_generated"],
                    "stage_c": accounting["stage_c_predictions_generated"],
                }
                and manifest.get("tutorial_metric_calls") == 56
                and manifest.get("maximum_tutorial_metric_calls") == 80
                and manifest.get("accounting", {}).get("official_model_fits")
                == accounting["official_model_fits"]
                and manifest.get("accounting", {}).get("official_predictions_generated")
                == accounting["official_predictions_generated"]
                and manifest.get("accounting", {}).get("development_metric_evaluations")
                == 1,
                "scientific terminal accounting differs",
            )
            manifest["accounting"] = accounting
            manifest["accounting_complete"] = True
            files["manifest.json"] = maplight.json_bytes(manifest)
    finally:
        _cleanup_owned_root(work)
    _require(_lstat(work) is None, "private execution cleanup is incomplete")
    published = _stage_payload(files)
    _require(_lstat(published) is not None, "terminal staging failed")
    supervisor.resource_checkpoint("stage:terminal-staged-after-cleanup")
    return 0


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _validate_observation(
    value: Mapping[str, Any],
) -> supervisor.ResourceObservation:
    """Validate exactly the accepted 13-field supervisor observation."""

    _require(
        set(value) == set(OBSERVATION_FIELDS),
        "supervisor observation fields differ",
    )
    numbers: dict[str, float] = {}
    for name in ("wall_seconds", "cpu_seconds", "gpu_hours"):
        item = value.get(name)
        _require(
            isinstance(item, float)
            and math.isfinite(item)
            and item >= 0.0
            and not (item == 0.0 and math.copysign(1.0, item) < 0.0),
            f"supervisor {name} differs",
        )
        numbers[name] = cast(float, item)
    integers = {
        name: _strict_nonnegative_int(value.get(name), f"supervisor {name}")
        for name in (
            "peak_storage_bytes",
            "peak_simultaneous_rss_bytes",
            "checkpoints_acknowledged",
            "descendant_processes_observed",
            "detached_children_observed",
            "warnings_observed",
        )
    }
    return_code = value.get("return_code")
    _require(
        return_code is None
        or (isinstance(return_code, int) and not isinstance(return_code, bool)),
        "supervisor return code differs",
    )
    booleans: dict[str, bool] = {}
    for name in (
        "cleanup_complete",
        "network_namespace_isolated",
        "gpu_environment_hidden",
    ):
        item = value.get(name)
        _require(isinstance(item, bool), f"supervisor {name} differs")
        booleans[name] = cast(bool, item)
    return supervisor.ResourceObservation(
        wall_seconds=numbers["wall_seconds"],
        cpu_seconds=numbers["cpu_seconds"],
        peak_storage_bytes=integers["peak_storage_bytes"],
        peak_simultaneous_rss_bytes=integers["peak_simultaneous_rss_bytes"],
        gpu_hours=numbers["gpu_hours"],
        checkpoints_acknowledged=integers["checkpoints_acknowledged"],
        descendant_processes_observed=integers["descendant_processes_observed"],
        return_code=cast(int | None, return_code),
        cleanup_complete=booleans["cleanup_complete"],
        network_namespace_isolated=booleans["network_namespace_isolated"],
        gpu_environment_hidden=booleans["gpu_environment_hidden"],
        detached_children_observed=integers["detached_children_observed"],
        warnings_observed=integers["warnings_observed"],
    )


def _parse_supervisor_exception(
    exc: supervisor.ResourceSupervisorError,
) -> tuple[str, supervisor.ResourceObservation]:
    raw = str(exc)
    _require(
        len(raw.encode("utf-8")) <= MAXIMUM_RECEIPT_BYTES
        and raw.count(SUPERVISOR_OBSERVATION_DELIMITER) == 1,
        "malformed or absent supervisor observation",
    )
    reason, detail = raw.split(SUPERVISOR_OBSERVATION_DELIMITER, 1)
    _require(bool(reason) and "\n" not in reason, "supervisor reason differs")
    try:
        decoded = json.loads(
            detail,
            object_pairs_hook=_no_duplicate_object,
            parse_constant=_reject_json_constant,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RobustnessOfficialAttemptError(
            "malformed or absent supervisor observation"
        ) from error
    _require(isinstance(decoded, Mapping), "supervisor observation differs")
    observed = _validate_observation(decoded)
    canonical = json.dumps(vars(observed), sort_keys=True, allow_nan=False)
    _require(canonical == detail, "supervisor observation is not canonical")
    return reason, observed


def _classify_supervisor_failure(reason: str) -> str:
    return RESOURCE_ABORTED_STATUS if reason in HARD_RESOURCE_REASONS else FAILED_STATUS


def _normalized_failure_category(reason: str) -> str:
    if reason in HARD_RESOURCE_REASONS:
        return "hard_resource_limit"
    if reason.startswith("supervised process exited"):
        return "supervised_process_nonzero"
    known = {
        "warning or stderr output observed": "warning_or_stderr",
        "no resource checkpoint was acknowledged": "missing_checkpoint",
        "resource checkpoint request differs": "checkpoint_request",
        "descendant detached from the supervised process group": "detached_descendant",
    }
    if reason in known:
        return known[reason]
    if reason.startswith("supervisor failure"):
        return "supervisor_failure"
    return "supervised_execution_failure"


def _validate_success_observation(observed: supervisor.ResourceObservation) -> None:
    _require(
        observed.return_code == 0
        and not isinstance(observed.return_code, bool)
        and observed.checkpoints_acknowledged > 0
        and observed.descendant_processes_observed > 0
        and observed.cleanup_complete
        and observed.network_namespace_isolated
        and observed.gpu_environment_hidden
        and observed.gpu_hours == 0.0
        and observed.detached_children_observed == 0
        and observed.warnings_observed == 0
        and observed.wall_seconds + MAXIMUM_SEAL_WALL_SECONDS <= LIMITS.wall_seconds
        and observed.cpu_seconds + MAXIMUM_SEAL_CPU_SECONDS <= LIMITS.cpu_seconds
        and observed.peak_storage_bytes + MAXIMUM_TERMINAL_BYTES <= LIMITS.storage_bytes
        and observed.peak_simultaneous_rss_bytes <= LIMITS.rss_bytes,
        "successful cumulative supervision differs",
    )


def _is_orchestration_fixture() -> bool:
    parent_parts = COMPOSITE_ACCEPTANCE_PARENT.parts
    return OFFICIAL_ATTEMPT_ROOT.parts[: len(parent_parts)] == parent_parts


def _json_from_bytes(value: bytes, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(
            value,
            object_pairs_hook=_no_duplicate_object,
            parse_constant=_reject_json_constant,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RobustnessOfficialAttemptError(f"{label} JSON differs") from error
    _require(isinstance(decoded, dict), f"{label} JSON differs")
    result = cast(dict[str, Any], decoded)
    _require(maplight.json_bytes(result) == value, f"{label} JSON is not canonical")
    return result


def _validate_accounting(
    accounting: object, *, complete: bool
) -> dict[str, int] | None:
    if accounting is None:
        _require(not complete, "absent accounting is marked complete")
        return None
    _require(isinstance(accounting, Mapping), "aggregate accounting differs")
    accounting_map = cast(Mapping[str, object], accounting)
    result = {
        str(name): _strict_nonnegative_int(item, f"accounting {name}")
        for name, item in accounting_map.items()
    }
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
        "private_portal_observations_recorded",
        "claims_created",
        "synthetic_model_fits",
        "synthetic_predictions_generated",
        "model_double_invocations",
        "real_catboost_controls",
    ):
        _require(result.get(name, 0) == 0, f"forbidden accounting {name} differs")
    if complete:
        _require(
            set(result) == set(_base_accounting())
            and result.get("claims_consumed") == 1,
            "complete accounting field set differs",
        )
    return result


def _validate_staged_payload(
    files: Mapping[str, bytes], *, claim_sha256: str
) -> tuple[dict[str, Any], str]:
    _require("manifest.json" in files, "staged manifest is absent")
    manifest = _json_from_bytes(files["manifest.json"], "staged manifest")
    status = manifest.get("status")
    _require(
        isinstance(status, str)
        and status
        in {
            *SCIENTIFIC_STATUSES,
            UNDERPOWERED_STATUS,
            RESOURCE_ABORTED_STATUS,
            FAILED_STATUS,
        },
        "staged status differs",
    )
    expected_files = (
        {"manifest.json", "primary_metrics.json", "robustness.json", "selection.json"}
        if status in SCIENTIFIC_STATUSES
        else {"manifest.json", "preflight.json"}
        if status == UNDERPOWERED_STATUS
        else {"manifest.json"}
    )
    _require(set(files) == expected_files, "status-specific staged files differ")
    fixture = manifest.get("synthetic_orchestration_fixture") is True
    _require(
        manifest.get("schema_version") == runner.TERMINAL_SCHEMA
        and manifest.get("contract_sha256") == runner.CONTRACT_SHA256
        and manifest.get("consumed_claim_sha256") == claim_sha256
        and manifest.get("authority") == dict(maplight.DENIED_AUTHORITY)
        and (
            manifest.get("synthetic") is False
            if not fixture
            else manifest.get("synthetic") is True and _is_orchestration_fixture()
        ),
        "staged terminal lineage differs",
    )
    complete = manifest.get("accounting_complete") is True
    accounting = _validate_accounting(manifest.get("accounting"), complete=complete)
    if status in SCIENTIFIC_STATUSES:
        _require(
            complete
            and accounting is not None
            and manifest.get("selected_candidate") in runner.SELECTION_FEATURE_COLUMNS
            and manifest.get("selection_tokens") == 1
            and manifest.get("runner_ups") == 0
            and manifest.get("tutorial_metric_calls") == 56
            and manifest.get("maximum_tutorial_metric_calls") == 80
            and manifest.get("row_level_values_retained") == 0
            and manifest.get("model_binaries_retained") == 0
            and accounting["development_metric_evaluations"] == 1,
            "staged scientific terminal differs",
        )
    elif status == UNDERPOWERED_STATUS:
        _require(
            complete
            and accounting == _underpowered_accounting()
            and manifest.get("selected_candidate") is None
            and manifest.get("selection_tokens") == 0
            and manifest.get("runner_ups") == 0
            and manifest.get("fit_counts") == {"stage_a": 0, "stage_b": 0, "stage_c": 0}
            and manifest.get("prediction_counts")
            == {"stage_a": 0, "stage_b": 0, "stage_c": 0}
            and manifest.get("tutorial_metric_calls") == 0
            and manifest.get("row_level_values_retained") == 0
            and manifest.get("model_binaries_retained") == 0
            and manifest.get("output_receipts", {}).get("preflight.json")
            == maplight.sha256_bytes(files["preflight.json"]),
            "staged underpowered terminal differs",
        )
    else:
        _require(
            isinstance(manifest.get("failure_category"), str)
            and bool(manifest.get("failure_category"))
            and manifest.get("accounting_complete") is complete,
            "staged failure terminal differs",
        )
    return manifest, cast(str, status)


def _failure_payload(
    *,
    status: str,
    claim_sha256: str,
    failure_category: str,
    accounting: Mapping[str, int] | None,
    accounting_complete: bool,
) -> dict[str, bytes]:
    _require(
        status in {RESOURCE_ABORTED_STATUS, FAILED_STATUS}, "failure status differs"
    )
    fixture = _is_orchestration_fixture()
    manifest: dict[str, Any] = {
        "schema_version": runner.TERMINAL_SCHEMA,
        "status": status,
        "synthetic": fixture,
        "contract_sha256": runner.CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "failure_category": failure_category,
        "accounting": dict(accounting) if accounting is not None else None,
        "accounting_complete": accounting_complete,
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    if fixture:
        manifest["synthetic_orchestration_fixture"] = True
    return {"manifest.json": maplight.json_bytes(manifest)}


def _recover_staged_accounting(
    *, claim_sha256: str
) -> tuple[dict[str, int] | None, bool]:
    try:
        files = _read_flat_files(PUBLICATION_STAGING_ROOT)
        manifest, _status = _validate_staged_payload(files, claim_sha256=claim_sha256)
        complete = manifest.get("accounting_complete") is True
        return _validate_accounting(
            manifest.get("accounting"), complete=complete
        ), complete
    except (OSError, KeyError, RobustnessOfficialAttemptError):
        return None, False


def _current_rss_bytes() -> int:
    # Linux reports ru_maxrss in KiB.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


class _SealPrePromotionError(RobustnessOfficialAttemptError):
    """A controlled pre-promotion defect may use the one bounded fallback."""


class _SealResourceError(_SealPrePromotionError):
    """The bounded post-supervision seal exceeded its fixed envelope."""


class _TerminalPromotionError(RobustnessOfficialAttemptError):
    """Atomic promotion failed; no fallback or replacement is permitted."""


class _PostPromotionValidationError(RobustnessOfficialAttemptError):
    """A promoted terminal failed validation and is a terminal blocker."""


def _make_staging_leaves_readonly(root: Path) -> None:
    files = _read_flat_files(root)
    for name in files:
        os.chmod(root / name, 0o444, follow_symlinks=False)
    # This host rejects renameat2 for a 0555 source directory.  The fixed
    # executable chronology therefore keeps the staging root 0700, promotes
    # atomically, then immediately makes the final root 0555 before fsync and
    # validation.  Every leaf is already immutable at the promotion boundary.
    os.chmod(root, 0o700, follow_symlinks=False)


def _attempt_receipt(
    *,
    files: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    status: str,
    claim_sha256: str,
    observed: supervisor.ResourceObservation | None,
    seal_attempts: int,
    fallback_used: bool,
) -> dict[str, Any]:
    file_sha256 = {
        name: maplight.sha256_bytes(value) for name, value in sorted(files.items())
    }
    return {
        "schema_version": (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_official_attempt_receipt.v1"
        ),
        "status": status,
        "consumed_claim_sha256": claim_sha256,
        "terminal_file_sha256": file_sha256,
        "terminal_file_receipts": {
            name: {
                "sha256": digest,
                "size_bytes": len(files[name]),
                "mode": "0444",
            }
            for name, digest in file_sha256.items()
        },
        "implementation_lineage": {
            "d135_science_kernel_acceptance_sha256": maplight.sha256_path(ACCEPTANCE),
            "d136_focused_test_provenance_bridge_sha256": PROVENANCE_BRIDGE_SHA256,
            "d137_repair_contract_sha256": REPAIR_CONTRACT_SHA256,
            "d138_seal_erratum_sha256": SEAL_ERRATUM_SHA256,
            "d139_test_transition_contract_sha256": (TEST_TRANSITION_CONTRACT_SHA256),
            "d140_source_shape_transition_contract_sha256": (
                SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
            ),
            "historical_official_driver_sha256": HISTORICAL_OFFICIAL_DRIVER_SHA256,
            "corrected_official_driver_sha256": maplight.sha256_path(SCRIPT),
            "composite_acceptance_sha256": maplight.sha256_path(COMPOSITE_ACCEPTANCE),
            "composite_acceptance_driver_sha256": maplight.sha256_path(
                COMPOSITE_ACCEPTANCE_DRIVER
            ),
            "orchestration_focused_tests_sha256": maplight.sha256_path(
                ORCHESTRATION_FOCUSED_TESTS
            ),
            "immutable_science_kernel_source_sha256": dict(
                IMMUTABLE_SCIENCE_KERNEL_SHA256
            ),
        },
        "accounting": manifest.get("accounting"),
        "accounting_complete": manifest.get("accounting_complete") is True,
        "cumulative_supervision": vars(observed) if observed is not None else None,
        "resource_limits": vars(LIMITS),
        "cleanup_complete": _lstat(RESTRICTED_ROOT) is None
        and _lstat(CLAIM_STAGING_PATH) is None,
        "row_level_values_retained": 0,
        "model_binaries_retained": 0,
        "seal_attempts": seal_attempts,
        "fallback_used": fallback_used,
        "authority": dict(maplight.DENIED_AUTHORITY),
    }


def _terminal_identity_snapshot(
    root: Path, *, expected_files: Mapping[str, bytes]
) -> dict[str, tuple[int, int]]:
    """Capture the directory and leaf identities that atomic rename must preserve."""

    root_stat = _lstat(root)
    _require(
        root_stat is not None
        and stat.S_ISDIR(root_stat.st_mode)
        and not stat.S_ISLNK(root_stat.st_mode)
        and root_stat.st_uid == os.getuid()
        and root_stat.st_nlink == 2
        and stat.S_IMODE(root_stat.st_mode) == 0o700,
        "terminal identity root differs",
    )
    observed = _read_flat_files(root)
    _require(
        set(observed) == set(expected_files)
        and all(observed[name] == expected_files[name] for name in expected_files),
        "terminal identity bytes differ",
    )
    result = {".": (root_stat.st_dev, root_stat.st_ino)}
    for name in expected_files:
        item = _lstat(root / name)
        _require(
            item is not None
            and stat.S_ISREG(item.st_mode)
            and not stat.S_ISLNK(item.st_mode)
            and item.st_uid == os.getuid()
            and item.st_nlink == 1
            and stat.S_IMODE(item.st_mode) == 0o444
            and item.st_size == len(expected_files[name]),
            "terminal identity leaf differs",
        )
        result[name] = (item.st_dev, item.st_ino)
    return result


def _seal_budget_exhausted(started: float, cpu_started: float) -> bool:
    return (
        time.monotonic() - started >= MAXIMUM_SEAL_WALL_SECONDS
        or time.process_time() - cpu_started >= MAXIMUM_SEAL_CPU_SECONDS
    )


def _validate_promoted_terminal(
    *,
    expected_files: Mapping[str, bytes],
    expected_identity: Mapping[str, tuple[int, int]],
    claim_sha256: str,
    status: str,
) -> None:
    root_stat = _lstat(FINAL_TERMINAL_ROOT)
    _require(
        root_stat is not None
        and stat.S_ISDIR(root_stat.st_mode)
        and not stat.S_ISLNK(root_stat.st_mode)
        and root_stat.st_uid == os.getuid()
        and root_stat.st_nlink == 2
        and stat.S_IMODE(root_stat.st_mode) == 0o555,
        "promoted terminal root differs",
    )
    _require(
        set(expected_identity) == {".", *expected_files}
        and expected_identity.get(".") == (root_stat.st_dev, root_stat.st_ino),
        "promoted terminal root identity differs",
    )
    observed_files = _read_flat_files(FINAL_TERMINAL_ROOT)
    _require(
        set(observed_files) == set(expected_files)
        and all(
            observed_files[name] == expected_files[name] for name in expected_files
        ),
        "promoted terminal bytes differ",
    )
    for name in expected_files:
        item = _lstat(FINAL_TERMINAL_ROOT / name)
        _require(
            item is not None
            and stat.S_ISREG(item.st_mode)
            and not stat.S_ISLNK(item.st_mode)
            and item.st_uid == os.getuid()
            and item.st_nlink == 1
            and stat.S_IMODE(item.st_mode) == 0o444
            and item.st_size == len(expected_files[name]),
            "promoted terminal leaf differs",
        )
        _require(
            expected_identity.get(name) == (item.st_dev, item.st_ino),
            "promoted terminal leaf identity differs",
        )
    receipt = _json_from_bytes(
        observed_files["attempt_receipt.json"], "promoted attempt receipt"
    )
    bound_files = {
        name: value
        for name, value in observed_files.items()
        if name != "attempt_receipt.json"
    }
    _require(
        receipt.get("status") == status
        and receipt.get("consumed_claim_sha256") == claim_sha256
        and receipt.get("terminal_file_sha256")
        == {
            name: maplight.sha256_bytes(value)
            for name, value in sorted(bound_files.items())
        }
        and receipt.get("terminal_file_receipts")
        == {
            name: {
                "sha256": maplight.sha256_bytes(value),
                "size_bytes": len(value),
                "mode": "0444",
            }
            for name, value in sorted(bound_files.items())
        },
        "promoted attempt receipt bindings differ",
    )
    manifest = _json_from_bytes(observed_files["manifest.json"], "promoted manifest")
    _require(
        manifest.get("status") == status
        and manifest.get("consumed_claim_sha256") == claim_sha256,
        "promoted manifest binding differs",
    )


def _seal_terminal(
    *,
    claim_sha256: str,
    observed: supervisor.ResourceObservation | None,
    seal_started: float | None = None,
    seal_cpu_started: float | None = None,
    seal_attempts: int = 1,
    fallback_used: bool = False,
) -> Path:
    """Perform the common bounded, aggregate-only, atomic no-replace seal."""

    started = time.monotonic() if seal_started is None else seal_started
    cpu_started = time.process_time() if seal_cpu_started is None else seal_cpu_started
    _require(
        seal_attempts in {1, 2} and fallback_used is (seal_attempts == 2),
        "seal chronology differs",
    )
    promoted = False
    try:
        files = _read_flat_files(PUBLICATION_STAGING_ROOT)
        manifest, status = _validate_staged_payload(files, claim_sha256=claim_sha256)
        if status in {*SCIENTIFIC_STATUSES, UNDERPOWERED_STATUS}:
            _require(observed is not None, "successful observation is absent")
            _validate_success_observation(
                cast(supervisor.ResourceObservation, observed)
            )
        if observed is not None:
            observed = _validate_observation(vars(observed))
            _require(observed.gpu_hours == 0.0, "supervised GPU use differs")
        else:
            _require(
                (
                    status == FAILED_STATUS
                    and manifest.get("accounting_complete") is False
                )
                or (
                    status == RESOURCE_ABORTED_STATUS
                    and manifest.get("failure_category") == "seal_resource_limit"
                ),
                "absent observation terminal differs",
            )
        _require(
            _lstat(RESTRICTED_ROOT) is None and _lstat(CLAIM_STAGING_PATH) is None,
            "private cleanup is incomplete",
        )
        if _lstat(FINAL_TERMINAL_ROOT) is not None:
            raise _TerminalPromotionError("final terminal exists")
        manifest["cumulative_supervision"] = (
            vars(observed) if observed is not None else None
        )
        manifest["resource_limits"] = vars(LIMITS)
        manifest["supervision_complete_before_publication"] = observed is not None
        manifest["cleanup_complete"] = True
        manifest["trusted_child_invariant"] = (
            "the supervised trusted child alone creates private scientific "
            "artifacts; concurrent malicious same-UID root substitution is outside "
            "scope; preexisting and descendant symlinks are never followed"
        )
        files["manifest.json"] = maplight.json_bytes(manifest)
        receipt = _attempt_receipt(
            files=files,
            manifest=manifest,
            status=status,
            claim_sha256=claim_sha256,
            observed=observed,
            seal_attempts=seal_attempts,
            fallback_used=fallback_used,
        )
        receipt_bytes = maplight.json_bytes(receipt)
        if len(receipt_bytes) > MAXIMUM_RECEIPT_BYTES:
            raise _SealResourceError("attempt receipt exceeded its fixed limit")
        files["attempt_receipt.json"] = receipt_bytes
        total_bytes = sum(len(value) for value in files.values())
        if total_bytes > MAXIMUM_TERMINAL_BYTES:
            raise _SealResourceError("terminal exceeded its fixed limit")
        if _current_rss_bytes() > LIMITS.rss_bytes:
            raise _SealResourceError("seal RSS exceeded its fixed limit")
        if _seal_budget_exhausted(started, cpu_started):
            raise _SealResourceError("seal time exceeded its fixed limit")
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        _stage_payload(files)
        _make_staging_leaves_readonly(PUBLICATION_STAGING_ROOT)
        _fsync_directory(PUBLICATION_STAGING_ROOT)
        pre_promotion_identity = _terminal_identity_snapshot(
            PUBLICATION_STAGING_ROOT, expected_files=files
        )
        if _current_rss_bytes() > LIMITS.rss_bytes:
            raise _SealResourceError("seal RSS exceeded before promotion")
        # Reserve a small fixed slice for chmod/fsync/validation after promotion.
        if (
            time.monotonic() - started > MAXIMUM_SEAL_WALL_SECONDS - 0.25
            or time.process_time() - cpu_started > MAXIMUM_SEAL_CPU_SECONDS - 0.25
        ):
            raise _SealResourceError("seal promotion reservation is exhausted")
        try:
            _rename_noreplace(PUBLICATION_STAGING_ROOT, FINAL_TERMINAL_ROOT)
        except (OSError, RobustnessOfficialAttemptError) as error:
            raise _TerminalPromotionError("atomic terminal promotion failed") from error
        promoted = True
        try:
            os.chmod(FINAL_TERMINAL_ROOT, 0o555, follow_symlinks=False)
            _fsync_directory(FINAL_TERMINAL_ROOT)
            _fsync_directory(FINAL_TERMINAL_ROOT.parent)
            _fsync_directory(PUBLICATION_STAGING_ROOT.parent)
            _validate_promoted_terminal(
                expected_files=files,
                expected_identity=pre_promotion_identity,
                claim_sha256=claim_sha256,
                status=status,
            )
            if _current_rss_bytes() > LIMITS.rss_bytes:
                raise _PostPromotionValidationError("seal RSS exceeded after promotion")
            if _seal_budget_exhausted(started, cpu_started):
                raise _PostPromotionValidationError(
                    "seal time exceeded after promotion"
                )
        except _PostPromotionValidationError:
            raise
        except Exception as error:
            raise _PostPromotionValidationError(
                "promoted terminal validation failed"
            ) from error
        return FINAL_TERMINAL_ROOT
    except (
        _SealResourceError,
        _SealPrePromotionError,
        _TerminalPromotionError,
        _PostPromotionValidationError,
    ):
        raise
    except Exception as error:
        if promoted:
            raise _PostPromotionValidationError(
                "post-promotion terminal failure"
            ) from error
        raise _SealPrePromotionError("pre-promotion seal failure") from error


def _make_attempt_readonly() -> None:
    claim = OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json"
    observed = _lstat(OFFICIAL_ATTEMPT_ROOT)
    _require(
        observed is not None
        and stat.S_ISDIR(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode),
        "attempt root differs",
    )
    attempt_stat = cast(os.stat_result, observed)
    _require(
        attempt_stat.st_uid == os.getuid() and attempt_stat.st_nlink == 3,
        "attempt root identity differs",
    )
    with os.scandir(OFFICIAL_ATTEMPT_ROOT) as entries:
        _require(
            {entry.name for entry in entries} == {"attempt_claim.json", "terminal"},
            "final attempt file set differs",
        )
    claim_stat = _lstat(claim)
    terminal_stat = _lstat(FINAL_TERMINAL_ROOT)
    _require(
        claim_stat is not None
        and stat.S_ISREG(claim_stat.st_mode)
        and claim_stat.st_uid == os.getuid()
        and claim_stat.st_nlink == 1
        and stat.S_IMODE(claim_stat.st_mode) == 0o444
        and terminal_stat is not None
        and stat.S_ISDIR(terminal_stat.st_mode)
        and terminal_stat.st_uid == os.getuid()
        and terminal_stat.st_nlink == 2
        and stat.S_IMODE(terminal_stat.st_mode) == 0o555
        and not stat.S_ISLNK(terminal_stat.st_mode),
        "final attempt entries differ",
    )
    os.chmod(claim, 0o444, follow_symlinks=False)
    os.chmod(OFFICIAL_ATTEMPT_ROOT, 0o555, follow_symlinks=False)
    _fsync_directory(OFFICIAL_ATTEMPT_ROOT)
    _fsync_directory(OFFICIAL_ATTEMPT_ROOT.parent)


def _valid_consumed_claim_sha256(expected: Mapping[str, Any]) -> str | None:
    attempt_stat = _lstat(OFFICIAL_ATTEMPT_ROOT)
    claim_path = OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json"
    claim_stat = _lstat(claim_path)
    if (
        attempt_stat is None
        or not stat.S_ISDIR(attempt_stat.st_mode)
        or stat.S_ISLNK(attempt_stat.st_mode)
        or claim_stat is None
        or not stat.S_ISREG(claim_stat.st_mode)
        or stat.S_ISLNK(claim_stat.st_mode)
    ):
        return None
    expected_bytes = maplight.json_bytes(expected)
    try:
        observed = _read_regular_bytes(claim_path, maximum_bytes=MAXIMUM_RECEIPT_BYTES)
    except (OSError, RobustnessOfficialAttemptError):
        return None
    if observed != expected_bytes:
        return None
    return maplight.sha256_bytes(observed)


def _claim_path_present() -> bool:
    root = _lstat(OFFICIAL_ATTEMPT_ROOT)
    return bool(
        root is not None
        and stat.S_ISDIR(root.st_mode)
        and not stat.S_ISLNK(root.st_mode)
        and _lstat(OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json") is not None
    )


def _cleanup_claim_staging_if_owned() -> None:
    root = _lstat(OFFICIAL_ATTEMPT_ROOT)
    if (
        root is not None
        and stat.S_ISDIR(root.st_mode)
        and not stat.S_ISLNK(root.st_mode)
    ):
        _cleanup_owned_root(CLAIM_STAGING_PATH, allow_regular_file=True)


def _cleanup_preconsumption() -> None:
    _cleanup_owned_root(RESTRICTED_ROOT)
    _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
    _cleanup_owned_root(OFFICIAL_ATTEMPT_ROOT)
    for path in (
        RESTRICTED_ROOT,
        PUBLICATION_STAGING_ROOT,
        OFFICIAL_ATTEMPT_ROOT,
        CLAIM_STAGING_PATH,
        OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json",
        FINAL_TERMINAL_ROOT,
    ):
        _require(_lstat(path) is None, "pre-consumption cleanup is incomplete")


def _seal_with_fallback(
    *,
    claim_sha256: str,
    observed: supervisor.ResourceObservation | None,
    seal_started: float | None = None,
    seal_cpu_started: float | None = None,
) -> Path:
    seal_started = time.monotonic() if seal_started is None else seal_started
    seal_cpu_started = (
        time.process_time() if seal_cpu_started is None else seal_cpu_started
    )
    if _seal_budget_exhausted(seal_started, seal_cpu_started):
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        raise RobustnessOfficialAttemptError(
            "shared terminal seal budget is exhausted before sealing"
        )
    accounting, accounting_complete = _recover_staged_accounting(
        claim_sha256=claim_sha256
    )
    try:
        terminal = _seal_terminal(
            claim_sha256=claim_sha256,
            observed=observed,
            seal_started=seal_started,
            seal_cpu_started=seal_cpu_started,
            seal_attempts=1,
            fallback_used=False,
        )
    except (_TerminalPromotionError, _PostPromotionValidationError) as exc:
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        raise RobustnessOfficialAttemptError(
            "terminal promotion or post-promotion validation failed"
        ) from exc
    except _SealPrePromotionError as exc:
        if _seal_budget_exhausted(seal_started, seal_cpu_started):
            _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
            raise RobustnessOfficialAttemptError(
                "shared terminal seal budget is exhausted"
            ) from exc
        resource_abort = isinstance(exc, _SealResourceError)
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        try:
            _stage_payload(
                _failure_payload(
                    status=(
                        RESOURCE_ABORTED_STATUS if resource_abort else FAILED_STATUS
                    ),
                    claim_sha256=claim_sha256,
                    failure_category=(
                        "seal_resource_limit" if resource_abort else "seal_failure"
                    ),
                    accounting=accounting,
                    accounting_complete=accounting_complete,
                )
            )
        except Exception as staging_exc:
            _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
            raise RobustnessOfficialAttemptError(
                "minimal terminal staging failed"
            ) from staging_exc
        if _seal_budget_exhausted(seal_started, seal_cpu_started):
            _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
            raise RobustnessOfficialAttemptError(
                "shared terminal seal budget is exhausted"
            ) from exc
        try:
            terminal = _seal_terminal(
                claim_sha256=claim_sha256,
                observed=observed,
                seal_started=seal_started,
                seal_cpu_started=seal_cpu_started,
                seal_attempts=2,
                fallback_used=True,
            )
        except Exception as fallback_exc:
            _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
            raise RobustnessOfficialAttemptError(
                "minimal terminal seal failed"
            ) from fallback_exc
    try:
        _make_attempt_readonly()
    except Exception as exc:
        raise RobustnessOfficialAttemptError(
            "post-promotion attempt finalization failed"
        ) from exc
    if _current_rss_bytes() > LIMITS.rss_bytes or _seal_budget_exhausted(
        seal_started, seal_cpu_started
    ):
        raise RobustnessOfficialAttemptError(
            "post-promotion attempt finalization exceeded the shared seal envelope"
        )
    return terminal


def _official_preflight() -> None:
    _require(
        OFFICIAL_ATTEMPT_ROOT.parent
        == RESTRICTED_ROOT.parent
        == PUBLICATION_STAGING_ROOT.parent
        and FINAL_TERMINAL_ROOT == OFFICIAL_ATTEMPT_ROOT / "terminal"
        and CLAIM_STAGING_PATH == OFFICIAL_ATTEMPT_ROOT / ".attempt-claim-staging",
        "fixed root relationship differs",
    )
    for path, label in (
        (OFFICIAL_ATTEMPT_ROOT, "fixed attempt root"),
        (RESTRICTED_ROOT, "fixed restricted root"),
        (PUBLICATION_STAGING_ROOT, "fixed publication staging root"),
    ):
        _require_fixed_parent(path, label)
        _require_absent(path, label)
    _require(
        shutil.disk_usage(OFFICIAL_ATTEMPT_ROOT.parent).free >= LIMITS.storage_bytes,
        "official free disk differs",
    )


def run_official_attempt() -> Path:
    """Run the fixed supervised attempt once and seal exactly one public status."""

    claim = derive_consumed_claim()
    _official_preflight()
    try:
        raw_observed = supervisor.run_supervised(
            [sys.executable, str(SCRIPT), "--child"],
            restricted_root=RESTRICTED_ROOT,
            limits=LIMITS,
            poll_interval_seconds=1.0,
            writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent,
            publication_root=PUBLICATION_STAGING_ROOT,
        )
    except Exception as exc:
        seal_started = time.monotonic()
        seal_cpu_started = time.process_time()
        claim_sha256 = _valid_consumed_claim_sha256(claim)
        if claim_sha256 is None:
            if _claim_path_present():
                _cleanup_owned_root(RESTRICTED_ROOT)
                _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
                _cleanup_claim_staging_if_owned()
                raise RobustnessOfficialAttemptError(
                    "malformed visible claim is a terminal blocker"
                ) from exc
            _cleanup_preconsumption()
            raise RobustnessOfficialAttemptError(
                "official attempt failed before claim consumption"
            ) from exc

        accounting, accounting_complete = _recover_staged_accounting(
            claim_sha256=claim_sha256
        )
        _cleanup_owned_root(RESTRICTED_ROOT)
        _cleanup_claim_staging_if_owned()
        parsed_observation: supervisor.ResourceObservation | None = None
        status = FAILED_STATUS
        category = "supervised_execution_failure"
        if isinstance(exc, supervisor.ResourceSupervisorError):
            try:
                reason, parsed_observation = _parse_supervisor_exception(exc)
            except RobustnessOfficialAttemptError:
                parsed_observation = None
                accounting_complete = False
                category = "malformed_supervisor_observation"
            else:
                status = _classify_supervisor_failure(reason)
                category = _normalized_failure_category(reason)
        else:
            parsed_observation = None
            accounting_complete = False
            category = "supervisor_failure"
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        _stage_payload(
            _failure_payload(
                status=status,
                claim_sha256=claim_sha256,
                failure_category=category,
                accounting=accounting,
                accounting_complete=accounting_complete and accounting is not None,
            )
        )
        return _seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=parsed_observation,
            seal_started=seal_started,
            seal_cpu_started=seal_cpu_started,
        )

    seal_started = time.monotonic()
    seal_cpu_started = time.process_time()
    claim_sha256 = _valid_consumed_claim_sha256(claim)
    if claim_sha256 is None:
        if _claim_path_present():
            _cleanup_owned_root(RESTRICTED_ROOT)
            _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
            _cleanup_claim_staging_if_owned()
            raise RobustnessOfficialAttemptError(
                "malformed visible claim is a terminal blocker"
            )
        _cleanup_preconsumption()
        raise RobustnessOfficialAttemptError(
            "supervision returned before atomic claim consumption"
        )

    _cleanup_claim_staging_if_owned()
    try:
        observed = _validate_observation(vars(raw_observed))
    except (TypeError, RobustnessOfficialAttemptError):
        accounting, _accounting_complete = _recover_staged_accounting(
            claim_sha256=claim_sha256
        )
        _cleanup_owned_root(RESTRICTED_ROOT)
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        _stage_payload(
            _failure_payload(
                status=FAILED_STATUS,
                claim_sha256=claim_sha256,
                failure_category="malformed_supervisor_observation",
                accounting=accounting,
                accounting_complete=False,
            )
        )
        return _seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=None,
            seal_started=seal_started,
            seal_cpu_started=seal_cpu_started,
        )

    if _lstat(RESTRICTED_ROOT) is not None or not observed.cleanup_complete:
        accounting, accounting_complete = _recover_staged_accounting(
            claim_sha256=claim_sha256
        )
        _cleanup_owned_root(RESTRICTED_ROOT)
        _cleanup_owned_root(PUBLICATION_STAGING_ROOT)
        _stage_payload(
            _failure_payload(
                status=FAILED_STATUS,
                claim_sha256=claim_sha256,
                failure_category="cleanup_failure",
                accounting=accounting,
                accounting_complete=accounting_complete and accounting is not None,
            )
        )
        return _seal_with_fallback(
            claim_sha256=claim_sha256,
            observed=observed,
            seal_started=seal_started,
            seal_cpu_started=seal_cpu_started,
        )

    return _seal_with_fallback(
        claim_sha256=claim_sha256,
        observed=observed,
        seal_started=seal_started,
        seal_cpu_started=seal_cpu_started,
    )


def _main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("paths", nargs="*")
    parsed = parser.parse_args(arguments)
    if parsed.paths:
        print("official execution accepts no root or output arguments", file=sys.stderr)
        return 2
    if parsed.child:
        return _child()
    run_official_attempt()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
