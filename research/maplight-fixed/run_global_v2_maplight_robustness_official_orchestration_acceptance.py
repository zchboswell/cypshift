#!/usr/bin/env python3
"""Sole zero-official acceptance for the repaired G2-7H orchestration.

The acceptance imports the live official driver but never executes its child
command.  A deterministic supervisor double publishes aggregate-only,
official-shaped synthetic fixtures below the fixed ``/tmp`` root.  The real
outer claim-publication, classification, cleanup, bounded-seal, receipt, and
atomic-promotion code is exercised in two opposite six-scenario orders.

This file creates mechanics evidence only.  It opens no official source or
baseline byte, creates or consumes no official claim, fits no model, evaluates
no development metric, and grants no official or model-quality authority.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import json
import os
import stat
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final, cast

import global_v2_maplight_resource_supervisor as supervisor
import global_v2_maplight_robustness_execution_compiler as compiler
import global_v2_maplight_robustness_execution_wrapper as mechanics
import global_v2_maplight_robustness_scientific_runner as runner
import global_v2_maplight_robustness_scoring_compiler as scoring_compiler
import global_v2_maplight_runner as maplight
import run_global_v2_maplight_robustness_official_v2 as official

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_acceptance.json"
)
REJECTION: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_rejection.json"
)
REPAIR_CONTRACT: Final = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_repair_contract.json"
)
SEAL_ERRATUM: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_seal_erratum.json"
)
D135_ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_execution_acceptance_v2.json"
)
D136_BRIDGE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_focused_test_provenance_bridge.json"
)
TEST_TRANSITION_CONTRACT: Final = (
    BENCHMARK
    / "global_v2_maplight_robustness_official_orchestration_test_transition_contract.json"
)
SOURCE_SHAPE_TRANSITION_CONTRACT: Final = (
    BENCHMARK / "global_v2_maplight_robustness_official_orchestration_source_shape_"
    "transition_contract.json"
)
FOCUSED_TESTS: Final = (
    ROOT
    / "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
)
FIXED_PARENT_ROOT: Final = Path("/tmp/cypshift-g2-7h")
FIXED_WORK_ROOT: Final = (
    FIXED_PARENT_ROOT / "official-orchestration-acceptance-attempt-1"
)
ATTEMPT_ID: Final = "g2-7h-official-orchestration-acceptance-attempt-1"
ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026."
    "global_v2_maplight_robustness_official_orchestration_acceptance.v1"
)
ACCEPTED_STATUS: Final = "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_ACCEPTED"
REJECTED_STATUS: Final = (
    "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_ACCEPTANCE_REJECTED"
)

REPAIR_CONTRACT_SHA256: Final = (
    "f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967"
)
SEAL_ERRATUM_SHA256: Final = (
    "a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33"
)
D135_ACCEPTANCE_SHA256: Final = (
    "4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390"
)
D136_BRIDGE_SHA256: Final = (
    "2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3"
)
TEST_TRANSITION_CONTRACT_SHA256: Final = (
    "6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c"
)
SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256: Final = (
    "d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417"
)
HISTORICAL_D136_AUDIT_SHA256: Final = (
    "719c0f71a8a0e403f590e1aced8a38b3c6131ff915a2bc9f8234126761bb4a2f"
)
HISTORICAL_PYTEST_HOOK_SHA256: Final = (
    "e931ec84186da7f06e1ab6ceea909bb01647acb3de01bb60b539e22d5848727a"
)
RETIRED_D136_NODE_IDS: Final = (
    "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::"
    "test_acceptance_binds_exact_contract_and_integrated_implementation",
    "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::"
    "test_provenance_bridge_retires_only_the_obsolete_pre_acceptance_state",
    "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::"
    "test_claim_derivation_is_read_only_and_fills_exactly_five_receipts",
)
REPLACEMENT_D140_NODE_IDS: Final = (
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::"
    "test_historical_lineage_uses_immutable_driver_hash_and_composite_is_required",
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::"
    "test_two_orders_cover_six_scenarios_and_build_one_zero_operation_record",
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::"
    "test_candidate_bytes_prove_all_five_future_claim_fields_before_publication",
)
HISTORICAL_D134_FOCUSED_SHA256: Final = (
    "3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f"
)
RETIRED_D134_SOURCE_SHAPE_NODE_IDS: Final = (
    "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::"
    "test_exact_fit_topology_and_conditional_stage_c_are_unchanged",
    "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::"
    "test_supervisor_starts_before_claim_consumption_and_official_access",
)
REPLACEMENT_D141_SOURCE_SHAPE_NODE_IDS: Final = (
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::"
    "test_corrected_child_preserves_fit_topology_and_cleans_before_terminal_staging",
    "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::"
    "test_supervisor_precedes_claim_consumption_and_common_seal_owns_terminal_"
    "publication",
)
REPLACEMENT_D141_SOURCE_SHAPE_SCOPES: Final = (
    "prove Stage A=540, Stage B=180, and conditional Stage C=300 fit identities; "
    "exact selection feature widths G2-7-M0-FULL=2563, "
    "G2-7-M1-DROP-MORGAN=1539, G2-7-M2-DROP-AVALON=1539, "
    "G2-7-M3-DROP-ERG=2248, and G2-7-M4-DROP-DESCRIPTORS=2363; both "
    "predictor-authority cross rejections for synthetic=True with "
    "real_catboost_predictor and synthetic=False with "
    "deterministic_test_predictor; Stage A -> selection -> Stage B -> "
    'conditional Stage C chronology with exact condition selected != "G2-7-M0-FULL"; '
    "and corrected source chronology _terminal_bytes -> _cleanup_owned_root(work) -> "
    "_stage_payload(files)",
    "prove run_supervised is present in run_official_attempt and _consume_claim is "
    "absent from run_official_attempt; child chronology resource_checkpoint -> "
    "derive_consumed_claim -> _consume_claim -> compile_capabilities -> Stage A; "
    "exact raw_observed = supervisor.run_supervised assignment; exact "
    "publication_root=PUBLICATION_STAGING_ROOT and "
    "writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent supervisor arguments; "
    "official.LIMITS == acceptance.LIMITS; OFFICIAL_ATTEMPT_ROOT == "
    "/home/zbos/cypshift-private/openadmet-2026/"
    "g2-7g-maplight-robustness-development-attempt-1 and that root is absent; "
    "_failure_payload contains accounting_complete and returns aggregate bytes only "
    "with no terminal path or publication; outer chronology run_supervised -> "
    "_seal_with_fallback places the common seal after supervision and makes it the "
    "exclusive terminal publisher; and _finalize_terminal is absent from "
    "run_official_attempt while PENDING_TERMINAL_ROOT is absent from the child",
)
HISTORICAL_OFFICIAL_DRIVER_SHA256: Final = (
    "1675336e449ba9a8327406cb37f82f08e3547076ce6c69fa0ade70c5a3de57fc"
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

SCENARIOS: Final = (
    "scientific_success",
    "clean_underpowered",
    "scientific_rejection",
    "hard_wall_resource_abort",
    "ordinary_nonzero_failure",
    "pre_consumption_supervisor_failure",
)
ORDERS: Final = ("forward", "reverse")
EXPECTED_STATUS_BY_SCENARIO: Final = {
    "scientific_success": "G2_7_PRIMARY_CONTENDER_FROZEN",
    "clean_underpowered": "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED",
    "scientific_rejection": "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED",
    "hard_wall_resource_abort": "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED",
    "ordinary_nonzero_failure": "G2_7_MAPLIGHT_ROBUSTNESS_FAILED",
    "pre_consumption_supervisor_failure": "PRE_CONSUMPTION_FAILURE_PROPAGATED",
}
STATUS_FILE_SETS: Final = {
    "G2_7_PRIMARY_CONTENDER_FROZEN": (
        "attempt_receipt.json",
        "manifest.json",
        "primary_metrics.json",
        "robustness.json",
        "selection.json",
    ),
    "G2_7_MAPLIGHT_ROBUSTNESS_REJECTED": (
        "attempt_receipt.json",
        "manifest.json",
        "primary_metrics.json",
        "robustness.json",
        "selection.json",
    ),
    "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED": (
        "attempt_receipt.json",
        "manifest.json",
        "preflight.json",
    ),
    "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED": (
        "attempt_receipt.json",
        "manifest.json",
    ),
    "G2_7_MAPLIGHT_ROBUSTNESS_FAILED": (
        "attempt_receipt.json",
        "manifest.json",
    ),
}
MECHANICS: Final = (
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
)
FORBIDDEN_OPERATIONS: Final = {
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
DENIED_AUTHORITY: Final = {
    "model_quality": False,
    "official_execution": False,
    "official_claim_consumption": False,
    "confirmatory": False,
    "blinded_test": False,
    "submission_generation": False,
    "live_upload": False,
}
COMPOSITE_LINEAGE_FIXTURE: Final = {
    "synthetic_orchestration_fixture": True,
    "official_operations": 0,
    "authority": dict(DENIED_AUTHORITY),
}


class OfficialOrchestrationAcceptanceError(RuntimeError):
    """The fixed synthetic orchestration chronology or evidence differed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OfficialOrchestrationAcceptanceError(message)


def _json(path: Path) -> dict[str, Any]:
    value, _raw = maplight._load_json(path)
    return value


def _canonical_exception(
    reason: str, observation: supervisor.ResourceObservation
) -> supervisor.ResourceSupervisorError:
    payload = json.dumps(
        asdict(observation),
        sort_keys=True,
        allow_nan=False,
    )
    return supervisor.ResourceSupervisorError(f"{reason}; observation={payload}")


def _successful_observation() -> supervisor.ResourceObservation:
    return supervisor.ResourceObservation(
        wall_seconds=1.25,
        cpu_seconds=0.75,
        peak_storage_bytes=4096,
        peak_simultaneous_rss_bytes=64 * 1024 * 1024,
        gpu_hours=0.0,
        checkpoints_acknowledged=3,
        descendant_processes_observed=2,
        return_code=0,
        cleanup_complete=True,
        network_namespace_isolated=True,
        gpu_environment_hidden=True,
        detached_children_observed=0,
        warnings_observed=0,
    )


def _failure_observation(*, hard_wall: bool) -> supervisor.ResourceObservation:
    return supervisor.ResourceObservation(
        wall_seconds=(official.LIMITS.wall_seconds + 0.5 if hard_wall else 2.0),
        cpu_seconds=1.0,
        peak_storage_bytes=8192,
        peak_simultaneous_rss_bytes=64 * 1024 * 1024,
        gpu_hours=0.0,
        checkpoints_acknowledged=2,
        descendant_processes_observed=2,
        return_code=(-15 if hard_wall else 7),
        cleanup_complete=True,
        network_namespace_isolated=True,
        gpu_environment_hidden=True,
        detached_children_observed=0,
        warnings_observed=0,
    )


def _underpowered_preflight() -> dict[str, Any]:
    value = _completed_preflight()
    support = cast(dict[str, dict[str, int]], value["support"])
    failed_key = "PRIMARY_D032|CYP1A2|r0|f0"
    support[failed_key] = {"training": 3000, "validation": 74}
    value.update(
        {
            "status": "G2_7C_NO_FIT_UNDERPOWERED",
            "failures": [f"{failed_key}:validation"],
            "support": support,
        }
    )
    return value


def _completed_preflight() -> dict[str, Any]:
    support: dict[str, dict[str, int]] = {}
    for group in compiler.GROUPS:
        for endpoint in compiler.ENDPOINTS:
            for repeat in compiler.REPEATS:
                for fold in compiler.OUTER_FOLDS:
                    support[f"{group}|{endpoint}|r{repeat}|f{fold}"] = {
                        "training": 3000,
                        "validation": 100,
                    }
    return {
        "status": "G2_7C_NO_FIT_PREFLIGHT_PASS",
        "failures": [],
        "support": support,
        "confirmatory_touch_excluded_molecules": {
            "PRIMARY_D032": 0,
            "THRESHOLD_0_55": 2,
            "THRESHOLD_0_50": 3,
            "TAUTOMER_MERGED": 4,
        },
        "minima": dict(compiler.MINIMA),
        "synthetic_orchestration_fixture": True,
    }


def _stage_manifests(*, deletion: bool) -> dict[str, dict[str, Any]]:
    preflight = _completed_preflight()
    support = cast(Mapping[str, Mapping[str, int]], preflight["support"])
    primary_training = sum(
        row["training"]
        for key, row in support.items()
        if key.startswith("PRIMARY_D032|")
    )
    overlay_training = sum(
        row["training"]
        for key, row in support.items()
        if not key.startswith("PRIMARY_D032|")
    )
    manifests: dict[str, dict[str, Any]] = {
        "stage_a": {
            "stage": "stage_a",
            "fit_identities": 540,
            "prediction_identities": 422064,
            "training_target_values_opened": 9 * primary_training,
            "accounting": {
                "official_model_fits": 540,
                "official_predictions_generated": 422064,
            },
            "synthetic_orchestration_fixture": True,
        },
        "stage_b": {
            "stage": "stage_b",
            "fit_identities": 180,
            "prediction_identities": 140580,
            "training_target_values_opened": overlay_training,
            "accounting": {
                "official_model_fits": 180,
                "official_predictions_generated": 140580,
            },
            "synthetic_orchestration_fixture": True,
        },
    }
    if deletion:
        manifests["stage_c"] = {
            "stage": "stage_c",
            "fit_identities": 300,
            "prediction_identities": 234480,
            "training_target_values_opened": 5 * primary_training,
            "accounting": {
                "official_model_fits": 300,
                "official_predictions_generated": 234480,
            },
            "synthetic_orchestration_fixture": True,
        }
    return manifests


def _completed_accounting(*, deletion: bool) -> dict[str, int]:
    return official._exact_accounting(
        preflight=_completed_preflight(),
        scoring_manifest={
            "counts": {
                "all_endpoint_rows": 19620,
                "development_rows_decoded": 15632,
                "finite_development_point_rows_emitted": 5197,
                "confirmatory_rows_prefix_checked_suffix_opaque": 3988,
                "confirmatory_value_fields_decoded": 0,
                "tutorial_eligible_rows": 5197,
            },
            "synthetic_orchestration_fixture": True,
        },
        stage_manifests=_stage_manifests(deletion=deletion),
        selected_candidate=("G2-7-M2-DROP-AVALON" if deletion else "G2-7-M0-FULL"),
    )


def _fixture_claim(scenario: str) -> dict[str, Any]:
    return {
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
        "authority": dict(DENIED_AUTHORITY),
    }


def _scientific_payload(
    *, status: str, claim_sha256: str, deletion: bool
) -> dict[str, bytes]:
    selected = "G2-7-M2-DROP-AVALON" if deletion else "G2-7-M0-FULL"
    accounting = _completed_accounting(deletion=deletion)
    manifest = {
        "schema_version": runner.TERMINAL_SCHEMA,
        "status": status,
        "synthetic": True,
        "synthetic_orchestration_fixture": True,
        "contract_sha256": runner.CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "selected_candidate": selected,
        "selection_tokens": 1,
        "runner_ups": 0,
        "fit_counts": {
            "stage_a": 540,
            "stage_b": 180,
            "stage_c": 300 if deletion else 0,
        },
        "prediction_counts": {
            "stage_a": 422064,
            "stage_b": 140580,
            "stage_c": 234480 if deletion else 0,
        },
        "tutorial_metric_calls": 56,
        "maximum_tutorial_metric_calls": 80,
        "row_level_values_retained": 0,
        "model_binaries_retained": 0,
        "accounting": accounting,
        "accounting_complete": True,
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    common = {
        "synthetic": True,
        "synthetic_orchestration_fixture": True,
        "aggregate_only": True,
        "status": status,
        "selected_candidate": selected,
        "model_quality_authority": False,
    }
    return {
        "manifest.json": maplight.json_bytes(manifest),
        "primary_metrics.json": maplight.json_bytes(
            {**common, "evidence": "deterministic-mechanics-fixture"}
        ),
        "robustness.json": maplight.json_bytes(
            {**common, "robustness_gate": "synthetic-mechanics-only"}
        ),
        "selection.json": maplight.json_bytes(
            {
                **common,
                "selection_token_count": 1,
                "runner_up": None,
            }
        ),
    }


def _publish_fixture_staging(files: Mapping[str, bytes]) -> None:
    root = official.PUBLICATION_STAGING_ROOT
    _require(
        root.is_relative_to(FIXED_PARENT_ROOT),
        "fixture publication root escaped the fixed parent",
    )
    root.mkdir(mode=0o700)
    for name, payload in sorted(files.items()):
        _require("/" not in name and name not in {"", ".", ".."}, "fixture name")
        descriptor = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _tree_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): maplight.sha256_path(path)
        for path in sorted(root.iterdir())
        if path.is_file() and not path.is_symlink()
    }


def _terminal_summary(root: Path) -> dict[str, Any]:
    manifest = _json(root / "manifest.json")
    receipt = _json(root / "attempt_receipt.json")
    status_value = manifest.get("status")
    _require(isinstance(status_value, str), "terminal status differs")
    status_name = cast(str, status_value)
    file_set = tuple(sorted(path.name for path in root.iterdir()))
    _require(file_set == STATUS_FILE_SETS[status_name], "terminal file set differs")
    modes = {
        path.name: stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        for path in root.iterdir()
    }
    _require(
        stat.S_IMODE(root.stat(follow_symlinks=False).st_mode) == 0o555
        and all(mode == 0o444 for mode in modes.values()),
        "terminal is not read-only",
    )
    bound_files = receipt.get(
        "terminal_file_sha256",
        receipt.get("output_receipts", receipt.get("files")),
    )
    _require(isinstance(bound_files, Mapping), "receipt file bindings differ")
    bound_file_map = cast(Mapping[str, str], bound_files)
    expected_bound = {
        name: digest
        for name, digest in _tree_map(root).items()
        if name != "attempt_receipt.json"
    }
    _require(dict(bound_file_map) == expected_bound, "receipt hashes differ")
    _require(
        receipt.get("terminal_file_receipts")
        == {
            name: {
                "sha256": digest,
                "size_bytes": (root / name).stat(follow_symlinks=False).st_size,
                "mode": "0444",
            }
            for name, digest in expected_bound.items()
        },
        "receipt file details differ",
    )
    observation = manifest.get("cumulative_supervision")
    if isinstance(observation, Mapping):
        observation = {
            name: observation[name]
            for name in supervisor.ResourceObservation.__dataclass_fields__
        }
    return {
        "status": status_name,
        "file_set": list(file_set),
        "accounting": manifest.get("accounting"),
        "accounting_complete": manifest.get("accounting_complete"),
        "selection_tokens": manifest.get("selection_tokens"),
        "runner_ups": manifest.get("runner_ups"),
        "fit_counts": manifest.get("fit_counts"),
        "prediction_counts": manifest.get("prediction_counts"),
        "tutorial_metric_calls": manifest.get("tutorial_metric_calls"),
        "failure_category": manifest.get("failure_category"),
        "cumulative_supervision": observation,
        "receipt_file_bindings": dict(bound_file_map),
        "receipt_file_receipts": receipt.get("terminal_file_receipts"),
        "receipt_status": receipt.get("status"),
        "receipt_claim_sha256": receipt.get("consumed_claim_sha256"),
        "receipt_implementation_lineage": receipt.get("implementation_lineage"),
        "receipt_resource_limits": receipt.get("resource_limits"),
        "receipt_cleanup_complete": receipt.get("cleanup_complete"),
        "receipt_authority": receipt.get("authority"),
        "receipt_seal_attempts": receipt.get("seal_attempts"),
        "receipt_fallback_used": receipt.get("fallback_used"),
        "cleanup_complete": manifest.get("cleanup_complete", True),
        "terminal_read_only": True,
        "aggregate_only": True,
    }


def _cleanup_owned_root(path: Path) -> None:
    """Remove one synthetic owned root without following any symlink."""

    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        path.unlink()
        return
    os.chmod(path, 0o700, follow_symlinks=False)
    with os.scandir(path) as entries:
        children = [Path(entry.path) for entry in entries]
    for child in children:
        _cleanup_owned_root(child)
    path.rmdir()


@contextlib.contextmanager
def _patched_official(**values: object) -> Iterator[None]:
    prior = {name: getattr(official, name) for name in values}
    try:
        for name, value in values.items():
            setattr(official, name, value)
        yield
    finally:
        for name, value in prior.items():
            setattr(official, name, value)


def _normalized_result_map(
    results: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return the root- and order-free scenario evidence map."""

    _require(set(results) == set(SCENARIOS), "scenario result set differs")
    return {scenario: dict(results[scenario]) for scenario in SCENARIOS}


def _validate_scenario_summary(scenario: str, result: Mapping[str, Any]) -> None:
    _require(
        result.get("status") == EXPECTED_STATUS_BY_SCENARIO[scenario],
        "scenario status differs",
    )
    if scenario == "pre_consumption_supervisor_failure":
        _require(
            result.get("file_set") == []
            and result.get("accounting") is None
            and result.get("accounting_complete") is False
            and result.get("receipt_file_bindings") == {}
            and result.get("cleanup_complete") is True,
            "pre-consumption evidence differs",
        )
        return
    accounting = result.get("accounting")
    observation = result.get("cumulative_supervision")
    receipt_lineage = result.get("receipt_implementation_lineage")
    _require(
        isinstance(observation, Mapping)
        and result.get("receipt_status") == result.get("status")
        and compiler._is_sha(result.get("receipt_claim_sha256"))
        and isinstance(receipt_lineage, Mapping)
        and receipt_lineage.get("d139_test_transition_contract_sha256")
        == TEST_TRANSITION_CONTRACT_SHA256
        and receipt_lineage.get("d140_source_shape_transition_contract_sha256")
        == SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
        and result.get("receipt_resource_limits") == vars(official.LIMITS)
        and result.get("receipt_cleanup_complete") is True
        and result.get("receipt_authority") == dict(maplight.DENIED_AUTHORITY)
        and result.get("receipt_seal_attempts") == 1
        and result.get("receipt_fallback_used") is False,
        "scenario receipt or observation differs",
    )
    if scenario in {
        "scientific_success",
        "clean_underpowered",
        "scientific_rejection",
    }:
        _require(
            observation.get("return_code") == 0
            and observation.get("cleanup_complete") is True
            and observation.get("network_namespace_isolated") is True
            and observation.get("gpu_environment_hidden") is True
            and observation.get("gpu_hours") == 0.0
            and observation.get("detached_children_observed") == 0
            and observation.get("warnings_observed") == 0,
            "successful observation differs",
        )
    if scenario == "clean_underpowered":
        _require(
            isinstance(accounting, Mapping)
            and accounting.get("official_model_fits") == 0
            and accounting.get("official_predictions_generated") == 0
            and accounting.get("official_baseline_rows_opened") == 0
            and accounting.get("development_metric_evaluations") == 0
            and result.get("selection_tokens") == 0
            and result.get("runner_ups") == 0
            and result.get("tutorial_metric_calls") == 0,
            "underpowered scenario differs",
        )
    elif scenario in {"scientific_success", "scientific_rejection"}:
        deletion = scenario == "scientific_rejection"
        _require(
            isinstance(accounting, Mapping)
            and accounting.get("official_model_fits") == (1020 if deletion else 720)
            and accounting.get("official_predictions_generated")
            == (797124 if deletion else 562644)
            and accounting.get("development_metric_evaluations") == 1
            and accounting.get("tutorial_metric_calls") == 56
            and accounting.get("maximum_tutorial_metric_calls") == 80
            and result.get("selection_tokens") == 1
            and result.get("runner_ups") == 0
            and result.get("tutorial_metric_calls") == 56,
            "completed scenario accounting differs",
        )
    elif scenario == "hard_wall_resource_abort":
        _require(
            result.get("accounting_complete") is False
            and observation.get("wall_seconds", 0) > official.LIMITS.wall_seconds
            and observation.get("return_code") == -15,
            "hard-resource scenario differs",
        )
    elif scenario == "ordinary_nonzero_failure":
        _require(
            result.get("accounting_complete") is False
            and observation.get("wall_seconds", 0) < official.LIMITS.wall_seconds
            and observation.get("return_code") == 7,
            "ordinary-failure scenario differs",
        )


def _execute_scenario(*, order_root: Path, scenario: str) -> dict[str, Any]:
    scenario_root = order_root / scenario
    scenario_root.mkdir(mode=0o700)
    attempt_root = scenario_root / "attempt"
    restricted_root = scenario_root / "restricted"
    publication_root = scenario_root / "publication-staging"
    final_root = attempt_root / "terminal"
    claim_staging = attempt_root / ".attempt-claim-staging"
    fixture_claim = _fixture_claim(scenario)
    invocations = 0
    fixture_claim_publications = 0
    sentinel_root = order_root / f"{scenario}-external-sentinel"
    composite_fixture = order_root / "composite-acceptance-fixture.json"
    if not composite_fixture.exists():
        composite_fixture.write_bytes(maplight.json_bytes(COMPOSITE_LINEAGE_FIXTURE))

    def forbidden(*_args: object, **_kwargs: object) -> Any:
        raise OfficialOrchestrationAcceptanceError(
            "a forbidden scientific or official boundary was invoked"
        )

    def derive_fixture() -> dict[str, Any]:
        return dict(fixture_claim)

    def run_supervised_double(
        command: Sequence[str],
        *,
        restricted_root: Path,
        limits: supervisor.ResourceLimits,
        poll_interval_seconds: float,
        writable_publication_parent: Path | None = None,
        publication_root: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> supervisor.ResourceObservation:
        nonlocal invocations, fixture_claim_publications
        invocations += 1
        _require(invocations == 1, "supervisor was reinvoked")
        _require(
            list(command) == [sys.executable, str(official.SCRIPT), "--child"]
            and restricted_root == official.RESTRICTED_ROOT
            and limits == official.LIMITS
            and poll_interval_seconds == 1.0
            and writable_publication_parent == official.PUBLICATION_STAGING_ROOT.parent
            and publication_root == official.PUBLICATION_STAGING_ROOT
            and environment is None,
            "supervisor call differs",
        )
        if scenario == "pre_consumption_supervisor_failure":
            sentinel_root.mkdir(mode=0o700)
            sentinel = sentinel_root / "sentinel"
            sentinel.write_bytes(b"do-not-touch\n")
            official.RESTRICTED_ROOT.symlink_to(sentinel_root, target_is_directory=True)
            official.PUBLICATION_STAGING_ROOT.symlink_to(
                sentinel_root, target_is_directory=True
            )
            raise _canonical_exception(
                "supervisor failure", _failure_observation(hard_wall=False)
            )

        previous_checkpoint = supervisor.resource_checkpoint
        supervisor.resource_checkpoint = lambda _label: None
        try:
            _claim_path, claim_sha256 = official._consume_claim(fixture_claim)
        finally:
            supervisor.resource_checkpoint = previous_checkpoint
        fixture_claim_publications += 1

        if scenario == "scientific_success":
            _publish_fixture_staging(
                _scientific_payload(
                    status=EXPECTED_STATUS_BY_SCENARIO[scenario],
                    claim_sha256=claim_sha256,
                    deletion=False,
                )
            )
            return _successful_observation()
        if scenario == "clean_underpowered":
            payload = official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
            _publish_fixture_staging(payload)
            return _successful_observation()
        if scenario == "scientific_rejection":
            _publish_fixture_staging(
                _scientific_payload(
                    status=EXPECTED_STATUS_BY_SCENARIO[scenario],
                    claim_sha256=claim_sha256,
                    deletion=True,
                )
            )
            return _successful_observation()
        if scenario == "hard_wall_resource_abort":
            raise _canonical_exception(
                "wall limit exceeded", _failure_observation(hard_wall=True)
            )
        if scenario == "ordinary_nonzero_failure":
            raise _canonical_exception(
                "supervised process exited 7",
                _failure_observation(hard_wall=False),
            )
        raise OfficialOrchestrationAcceptanceError("unknown scenario")

    patch = {
        "OFFICIAL_ATTEMPT_ROOT": attempt_root,
        "RESTRICTED_ROOT": restricted_root,
        "PUBLICATION_STAGING_ROOT": publication_root,
        "FINAL_TERMINAL_ROOT": final_root,
        "CLAIM_STAGING_PATH": claim_staging,
        "COMPOSITE_ACCEPTANCE": composite_fixture,
        "derive_consumed_claim": derive_fixture,
        "_run_model_stage": forbidden,
    }
    prior_supervisor = supervisor.run_supervised
    prior_compile = compiler.compile_capabilities
    prior_scoring = scoring_compiler.compile_scoring_capability
    prior_selection = runner.select_stage_a_candidate
    prior_terminal = runner.score_frozen_battery
    try:
        supervisor.run_supervised = run_supervised_double
        compiler.compile_capabilities = forbidden
        scoring_compiler.compile_scoring_capability = forbidden
        runner.select_stage_a_candidate = forbidden
        runner.score_frozen_battery = forbidden
        with _patched_official(**patch):
            result: dict[str, Any]
            if scenario == "pre_consumption_supervisor_failure":
                try:
                    official.run_official_attempt()
                except official.RobustnessOfficialAttemptError:
                    pass
                else:
                    raise OfficialOrchestrationAcceptanceError(
                        "pre-consumption failure did not propagate"
                    )
                _require(
                    not attempt_root.exists()
                    and not attempt_root.is_symlink()
                    and not restricted_root.exists()
                    and not restricted_root.is_symlink()
                    and not publication_root.exists()
                    and not publication_root.is_symlink()
                    and sentinel_root.joinpath("sentinel").read_bytes()
                    == b"do-not-touch\n",
                    "pre-consumption cleanup differs",
                )
                result = {
                    "status": EXPECTED_STATUS_BY_SCENARIO[scenario],
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
            else:
                returned = official.run_official_attempt()
                _require(returned == final_root, "official outer return path differs")
                result = _terminal_summary(final_root)
                claim_path = attempt_root / "attempt_claim.json"
                _require(
                    claim_path.is_file()
                    and not claim_path.is_symlink()
                    and stat.S_IMODE(claim_path.stat(follow_symlinks=False).st_mode)
                    == 0o444
                    and not claim_staging.exists()
                    and not restricted_root.exists()
                    and not publication_root.exists(),
                    "claim or private cleanup differs",
                )
            _validate_scenario_summary(scenario, result)
    finally:
        supervisor.run_supervised = prior_supervisor
        compiler.compile_capabilities = prior_compile
        scoring_compiler.compile_scoring_capability = prior_scoring
        runner.select_stage_a_candidate = prior_selection
        runner.score_frozen_battery = prior_terminal

    _require(invocations == 1, "scenario supervisor count differs")
    _require(
        fixture_claim_publications
        == (0 if scenario == "pre_consumption_supervisor_failure" else 1),
        "fixture claim publication count differs",
    )
    _cleanup_owned_root(scenario_root)
    if sentinel_root.exists() or sentinel_root.is_symlink():
        _cleanup_owned_root(sentinel_root)
    _require(
        not scenario_root.exists() and not sentinel_root.exists(),
        "scenario cleanup is incomplete",
    )
    return result


def _execute_order(*, root: Path, order: str) -> dict[str, Any]:
    _require(order in ORDERS, "order differs")
    root.mkdir(mode=0o700)
    execution_order = list(SCENARIOS if order == "forward" else reversed(SCENARIOS))
    results = {
        scenario: _execute_scenario(order_root=root, scenario=scenario)
        for scenario in execution_order
    }
    normalized = _normalized_result_map(results)
    _cleanup_owned_root(root)
    _require(not root.exists(), "order root cleanup is incomplete")
    return {
        "order": order,
        "scenario_execution_order": execution_order,
        "normalized_result_map": normalized,
    }


def _probe_exact_underpowered_helper(root: Path) -> bool:
    """Exercise the live exact catch boundary without running a child."""

    root.mkdir(mode=0o700)
    claim_sha256 = "a" * 64

    def raise_exact() -> tuple[Path, Path, dict[str, Any]]:
        raise compiler.RobustnessExecutionUnderpowered(_underpowered_preflight())

    compiled, payload = official._compile_capabilities_or_underpowered(
        compile_call=raise_exact,
        claim_sha256=claim_sha256,
        synthetic_orchestration_fixture=True,
    )
    _require(compiled is None and payload is not None, "exact catch result differs")

    class UnderpoweredSubclass(compiler.RobustnessExecutionUnderpowered):
        pass

    subclass_error = UnderpoweredSubclass(_underpowered_preflight())

    def raise_subclass() -> tuple[Path, Path, dict[str, Any]]:
        raise subclass_error

    try:
        official._compile_capabilities_or_underpowered(
            compile_call=raise_subclass,
            claim_sha256=claim_sha256,
            synthetic_orchestration_fixture=True,
        )
    except UnderpoweredSubclass as exc:
        _require(exc is subclass_error, "underpowered subclass identity differs")
    else:
        raise OfficialOrchestrationAcceptanceError(
            "underpowered subclass was misclassified"
        )

    ordinary_error = compiler.RobustnessExecutionCompilerError(
        "synthetic ordinary compiler failure"
    )

    def raise_ordinary() -> tuple[Path, Path, dict[str, Any]]:
        raise ordinary_error

    try:
        official._compile_capabilities_or_underpowered(
            compile_call=raise_ordinary,
            claim_sha256=claim_sha256,
            synthetic_orchestration_fixture=True,
        )
    except compiler.RobustnessExecutionCompilerError as exc:
        _require(exc is ordinary_error, "ordinary compiler error identity differs")
    else:
        raise OfficialOrchestrationAcceptanceError(
            "ordinary compiler failure was misclassified"
        )

    _require(
        set(payload) == {"manifest.json", "preflight.json"},
        "underpowered payload files differ",
    )
    for name, value in payload.items():
        (root / name).write_bytes(value)
    manifest = _json(root / "manifest.json")
    accounting = cast(Mapping[str, Any], manifest["accounting"])
    _require(
        manifest.get("status") == "G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED"
        and manifest.get("synthetic_orchestration_fixture") is True
        and manifest.get("selection_tokens") == 0
        and manifest.get("runner_ups") == 0
        and sum(cast(Mapping[str, int], manifest["fit_counts"]).values()) == 0
        and sum(cast(Mapping[str, int], manifest["prediction_counts"]).values()) == 0
        and accounting.get("official_model_fits") == 0
        and accounting.get("official_predictions_generated") == 0
        and accounting.get("official_baseline_rows_opened") == 0
        and accounting.get("development_metric_evaluations") == 0,
        "underpowered zero-science evidence differs",
    )
    _cleanup_owned_root(root)
    return not root.exists()


def _probe_atomic_claim_and_seal_failures(root: Path) -> bool:
    """Prove interruption, one-shot fallback, and no-replace collision behavior."""

    root.mkdir(mode=0o700)
    composite_fixture = root / "composite-acceptance-fixture.json"
    composite_fixture.write_bytes(maplight.json_bytes(COMPOSITE_LINEAGE_FIXTURE))

    def paths(case: str) -> tuple[Path, Path, Path, Path, Path]:
        case_root = root / case
        case_root.mkdir(mode=0o700)
        attempt = case_root / "attempt"
        restricted = case_root / "restricted"
        publication = case_root / "publication-staging"
        final = attempt / "terminal"
        staging = attempt / ".attempt-claim-staging"
        return attempt, restricted, publication, final, staging

    def constants(
        values: tuple[Path, Path, Path, Path, Path],
    ) -> dict[str, object]:
        attempt, restricted, publication, final, staging = values
        return {
            "OFFICIAL_ATTEMPT_ROOT": attempt,
            "RESTRICTED_ROOT": restricted,
            "PUBLICATION_STAGING_ROOT": publication,
            "FINAL_TERMINAL_ROOT": final,
            "CLAIM_STAGING_PATH": staging,
            "COMPOSITE_ACCEPTANCE": composite_fixture,
        }

    def consume(claim: Mapping[str, Any]) -> str:
        checkpoint = supervisor.resource_checkpoint
        supervisor.resource_checkpoint = lambda _label: None
        try:
            _path, digest = official._consume_claim(claim)
        finally:
            supervisor.resource_checkpoint = checkpoint
        return digest

    # An interruption before no-replace promotion leaves no partial claim after
    # the real pre-consumption cleanup path and never creates a final claim.
    interrupted_paths = paths("claim-interruption")
    original_rename = official._rename_noreplace

    def interrupted_rename(source: Path, destination: Path) -> None:
        if source == interrupted_paths[4]:
            raise OSError("injected pre-promotion interruption")
        original_rename(source, destination)

    with _patched_official(
        **constants(interrupted_paths), _rename_noreplace=interrupted_rename
    ):
        checkpoint = supervisor.resource_checkpoint
        supervisor.resource_checkpoint = lambda _label: None
        try:
            try:
                official._consume_claim(_fixture_claim("claim_interruption_probe"))
            except OSError:
                pass
            else:
                raise OfficialOrchestrationAcceptanceError(
                    "claim interruption did not propagate"
                )
        finally:
            supervisor.resource_checkpoint = checkpoint
        _require(
            official._lstat(interrupted_paths[4]) is not None
            and official._lstat(interrupted_paths[0] / "attempt_claim.json") is None,
            "claim interruption state differs",
        )
        official._cleanup_preconsumption()
        _require(
            all(official._lstat(path) is None for path in interrupted_paths),
            "interrupted claim cleanup differs",
        )

    # A non-resource seal defect permits one minimal FAILED seal in the same
    # invocation.  The live common seal and receipt path perform both attempts.
    ordinary_paths = paths("ordinary-seal-fallback")
    with _patched_official(**constants(ordinary_paths)):
        claim_sha256 = consume(_fixture_claim("ordinary_seal_fallback_probe"))
        official._stage_payload(
            official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
        )
        original_readonly = official._make_staging_leaves_readonly
        readonly_calls = 0

        def fail_readonly_once(staging_root: Path) -> None:
            nonlocal readonly_calls
            readonly_calls += 1
            if readonly_calls == 1:
                raise OSError("injected seal defect")
            original_readonly(staging_root)

        with _patched_official(_make_staging_leaves_readonly=fail_readonly_once):
            terminal = official._seal_with_fallback(
                claim_sha256=claim_sha256,
                observed=_successful_observation(),
            )
        ordinary_receipt = _json(terminal / "attempt_receipt.json")
        _require(
            readonly_calls == 2
            and _json(terminal / "manifest.json").get("status")
            == "G2_7_MAPLIGHT_ROBUSTNESS_FAILED"
            and set(_tree_map(terminal)) == {"attempt_receipt.json", "manifest.json"}
            and ordinary_receipt.get("seal_attempts") == 2
            and ordinary_receipt.get("fallback_used") is True,
            "ordinary minimal seal fallback differs",
        )

    # A hard seal-resource defect maps only to RESOURCE_ABORTED and likewise
    # permits exactly one minimal fallback.
    resource_paths = paths("resource-seal-fallback")
    with _patched_official(**constants(resource_paths)):
        claim_sha256 = consume(_fixture_claim("resource_seal_fallback_probe"))
        official._stage_payload(
            official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
        )
        rss_calls = 0

        def breach_rss_once() -> int:
            nonlocal rss_calls
            rss_calls += 1
            return official.LIMITS.rss_bytes + 1 if rss_calls == 1 else 0

        with _patched_official(_current_rss_bytes=breach_rss_once):
            terminal = official._seal_with_fallback(
                claim_sha256=claim_sha256,
                observed=_successful_observation(),
            )
        resource_receipt = _json(terminal / "attempt_receipt.json")
        _require(
            rss_calls == 5
            and _json(terminal / "manifest.json").get("status")
            == "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED"
            and set(_tree_map(terminal)) == {"attempt_receipt.json", "manifest.json"}
            and resource_receipt.get("seal_attempts") == 2
            and resource_receipt.get("fallback_used") is True,
            "resource minimal seal fallback differs",
        )

    # A preexisting final terminal is never read, removed, or overwritten and
    # authorizes no fallback publication.
    collision_paths = paths("final-collision")
    with _patched_official(**constants(collision_paths)):
        claim_sha256 = consume(_fixture_claim("final_collision_probe"))
        official._stage_payload(
            official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
        )
        collision_paths[3].mkdir(mode=0o700)
        sentinel = collision_paths[3] / "sentinel"
        sentinel.write_bytes(b"immutable-collision\n")
        collision_stages = 0
        original_stage_payload = official._stage_payload

        def track_collision_stage(files: Mapping[str, bytes]) -> Path:
            nonlocal collision_stages
            collision_stages += 1
            return original_stage_payload(files)

        with _patched_official(_stage_payload=track_collision_stage):
            try:
                official._seal_with_fallback(
                    claim_sha256=claim_sha256,
                    observed=_successful_observation(),
                )
            except official.RobustnessOfficialAttemptError:
                pass
            else:
                raise OfficialOrchestrationAcceptanceError(
                    "final collision did not block publication"
                )
        _require(
            collision_stages == 0
            and sentinel.read_bytes() == b"immutable-collision\n"
            and official._lstat(collision_paths[2]) is None,
            "final collision was mutated",
        )

    # A promotion failure is a permanent blocker and never enters the bounded
    # pre-promotion fallback path.
    promotion_paths = paths("promotion-error")
    with _patched_official(**constants(promotion_paths)):
        claim_sha256 = consume(_fixture_claim("promotion_error_probe"))
        official._stage_payload(
            official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
        )
        promotion_calls = 0
        promotion_stages = 0

        def fail_promotion(_source: Path, _destination: Path) -> None:
            nonlocal promotion_calls
            promotion_calls += 1
            raise OSError(errno.EXDEV, "injected cross-device promotion")

        def track_promotion_stage(files: Mapping[str, bytes]) -> Path:
            nonlocal promotion_stages
            promotion_stages += 1
            return original_stage_payload(files)

        with _patched_official(
            _rename_noreplace=fail_promotion,
            _stage_payload=track_promotion_stage,
        ):
            try:
                official._seal_with_fallback(
                    claim_sha256=claim_sha256,
                    observed=_successful_observation(),
                )
            except official.RobustnessOfficialAttemptError:
                pass
            else:
                raise OfficialOrchestrationAcceptanceError(
                    "promotion error did not block publication"
                )
        _require(
            promotion_calls == 1
            and promotion_stages == 1
            and official._lstat(promotion_paths[2]) is None
            and official._lstat(promotion_paths[3]) is None,
            "promotion failure cleanup or retry differs",
        )

    # Replacing one 0444 leaf with byte-identical content between the identity
    # snapshot and rename must be detected after the visibility commit.  The
    # visible terminal is preserved and no fallback or second rename occurs.
    identity_paths = paths("post-promotion-identity")
    with _patched_official(**constants(identity_paths)):
        claim_sha256 = consume(_fixture_claim("post_promotion_identity_probe"))
        official._stage_payload(
            official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
        )
        identity_renames = 0
        identity_stages = 0

        def substitute_then_promote(source: Path, destination: Path) -> None:
            nonlocal identity_renames
            identity_renames += 1
            leaf = source / "manifest.json"
            replacement = source / ".identity-replacement"
            replacement.write_bytes(leaf.read_bytes())
            os.chmod(replacement, 0o444, follow_symlinks=False)
            leaf.unlink()
            replacement.rename(leaf)
            original_rename(source, destination)

        def track_identity_stage(files: Mapping[str, bytes]) -> Path:
            nonlocal identity_stages
            identity_stages += 1
            return original_stage_payload(files)

        with _patched_official(
            _rename_noreplace=substitute_then_promote,
            _stage_payload=track_identity_stage,
        ):
            try:
                official._seal_with_fallback(
                    claim_sha256=claim_sha256,
                    observed=_successful_observation(),
                )
            except official.RobustnessOfficialAttemptError:
                pass
            else:
                raise OfficialOrchestrationAcceptanceError(
                    "post-promotion identity change was accepted"
                )
        _require(
            identity_renames == 1
            and identity_stages == 1
            and official._lstat(identity_paths[2]) is None
            and official._lstat(identity_paths[3]) is not None,
            "post-promotion blocker or visibility differs",
        )

    # Actual exhaustion of the one shared wall-clock seal budget cannot create
    # the otherwise permitted minimal resource fallback.
    budget_paths = paths("shared-budget-exhaustion")
    with _patched_official(**constants(budget_paths)):
        claim_sha256 = consume(_fixture_claim("shared_budget_exhaustion_probe"))
        official._stage_payload(
            official._underpowered_payload(
                preflight=_underpowered_preflight(),
                claim_sha256=claim_sha256,
                synthetic_orchestration_fixture=True,
            )
        )
        monotonic_calls = 0
        budget_stages = 0
        prior_monotonic = official.time.monotonic
        prior_process_time = official.time.process_time

        def exhausted_clock() -> float:
            nonlocal monotonic_calls
            monotonic_calls += 1
            return 0.0 if monotonic_calls == 1 else 6.0

        def track_budget_stage(files: Mapping[str, bytes]) -> Path:
            nonlocal budget_stages
            budget_stages += 1
            return original_stage_payload(files)

        official.time.monotonic = exhausted_clock
        official.time.process_time = lambda: 0.0
        try:
            with _patched_official(_stage_payload=track_budget_stage):
                try:
                    official._seal_with_fallback(
                        claim_sha256=claim_sha256,
                        observed=_successful_observation(),
                    )
                except official.RobustnessOfficialAttemptError as exc:
                    _require(
                        "shared terminal seal budget is exhausted" in str(exc),
                        "shared budget failure category differs",
                    )
                else:
                    raise OfficialOrchestrationAcceptanceError(
                        "shared budget exhaustion did not block fallback"
                    )
        finally:
            official.time.monotonic = prior_monotonic
            official.time.process_time = prior_process_time
        _require(
            monotonic_calls == 2
            and budget_stages == 0
            and official._lstat(budget_paths[2]) is None
            and official._lstat(budget_paths[3]) is None,
            "shared budget cleanup or fallback differs",
        )

    _cleanup_owned_root(root)
    return not root.exists()


def _build_acceptance_record(
    roots: Sequence[Mapping[str, Any]],
    *,
    exact_underpowered_catch_verified: bool,
    five_field_prepublication_derivation_verified: bool,
) -> dict[str, Any]:
    """Build the candidate aggregate accepted by the live driver validator."""

    _require(len(roots) == 2, "acceptance roots differ")
    normalized = [root.get("normalized_result_map") for root in roots]
    identical = maplight.json_bytes(
        cast(Mapping[str, Any], normalized[0])
    ) == maplight.json_bytes(cast(Mapping[str, Any], normalized[1]))
    return {
        "schema_version": ACCEPTANCE_SCHEMA,
        "status": ACCEPTED_STATUS,
        "attempt_id": ATTEMPT_ID,
        "repair_contract_sha256": REPAIR_CONTRACT_SHA256,
        "seal_erratum_sha256": SEAL_ERRATUM_SHA256,
        "d135_science_kernel_acceptance_sha256": D135_ACCEPTANCE_SHA256,
        "d136_focused_test_provenance_bridge_sha256": D136_BRIDGE_SHA256,
        "d139_test_transition_contract_sha256": (TEST_TRANSITION_CONTRACT_SHA256),
        "d140_source_shape_transition_contract_sha256": (
            SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256
        ),
        "historical_official_attempt_driver_source_sha256": (
            HISTORICAL_OFFICIAL_DRIVER_SHA256
        ),
        "corrected_official_attempt_driver_source_sha256": maplight.sha256_path(
            official.SCRIPT
        ),
        "official_orchestration_acceptance_driver_source_sha256": (
            maplight.sha256_path(SCRIPT)
        ),
        "focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
        "immutable_science_kernel_source_sha256": dict(IMMUTABLE_SCIENCE_KERNEL_SHA256),
        "scenario_orders": list(ORDERS),
        "required_scenarios": list(SCENARIOS),
        "roots": [dict(root) for root in roots],
        "scenario_invocations": 12,
        "supervisor_invocations": 12,
        "synthetic_scenario_claim_publications": 10,
        "synthetic_fixture_claim_publications": 10,
        "synthetic_probe_claim_publications": 6,
        "synthetic_interrupted_claim_stagings": 1,
        "synthetic_composite_lineage_fixture_sha256": maplight.sha256_bytes(
            maplight.json_bytes(COMPOSITE_LINEAGE_FIXTURE)
        ),
        "mechanics_probe_counts": {
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
        },
        "statuses_reached": sorted(STATUS_FILE_SETS),
        "mechanics": {name: True for name in MECHANICS},
        "opposite_order_maps_byte_identical": identical,
        "exact_underpowered_catch_verified": exact_underpowered_catch_verified,
        "five_field_prepublication_derivation_verified": (
            five_field_prepublication_derivation_verified
        ),
        "d135_science_kernel_evidence": {
            "model_double_invocations": 3480,
            "synthetic_predictions_generated": 667872,
            "real_catboost_fits": 2,
            "reexecuted": False,
        },
        "forbidden_operations": dict(FORBIDDEN_OPERATIONS),
        "cleanup_complete_before_publication": True,
        "private_roots_retained": 0,
        "model_quality_authority": False,
        "official_execution_authority": False,
        "claim_authority": False,
        "authority": dict(DENIED_AUTHORITY),
    }


def _validate_candidate_acceptance(
    value: Mapping[str, Any],
    *,
    acceptance_sha256: str,
    corrected_driver_sha256: str,
    acceptance_driver_sha256: str,
    focused_tests_sha256: str,
) -> None:
    """Validate the candidate through both local and live driver boundaries."""

    _authenticate_test_transition_contract()
    _authenticate_source_shape_transition_contract()
    roots = cast(Sequence[Mapping[str, Any]], value.get("roots"))
    _require(
        value.get("schema_version") == ACCEPTANCE_SCHEMA
        and value.get("status") == ACCEPTED_STATUS
        and value.get("attempt_id") == ATTEMPT_ID
        and value.get("repair_contract_sha256") == REPAIR_CONTRACT_SHA256
        and value.get("seal_erratum_sha256") == SEAL_ERRATUM_SHA256
        and value.get("d135_science_kernel_acceptance_sha256") == D135_ACCEPTANCE_SHA256
        and value.get("d136_focused_test_provenance_bridge_sha256")
        == D136_BRIDGE_SHA256
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
        == IMMUTABLE_SCIENCE_KERNEL_SHA256
        and value.get("scenario_orders") == list(ORDERS)
        and value.get("required_scenarios") == list(SCENARIOS)
        and isinstance(roots, Sequence)
        and len(roots) == 2
        and [root.get("order") for root in roots] == list(ORDERS)
        and roots[0].get("scenario_execution_order") == list(SCENARIOS)
        and roots[1].get("scenario_execution_order") == list(reversed(SCENARIOS))
        and roots[0].get("normalized_result_map")
        == roots[1].get("normalized_result_map")
        and value.get("scenario_invocations") == 12
        and value.get("supervisor_invocations") == 12
        and value.get("synthetic_scenario_claim_publications") == 10
        and value.get("synthetic_fixture_claim_publications") == 10
        and value.get("synthetic_probe_claim_publications") == 6
        and value.get("synthetic_interrupted_claim_stagings") == 1
        and value.get("synthetic_composite_lineage_fixture_sha256")
        == maplight.sha256_bytes(maplight.json_bytes(COMPOSITE_LINEAGE_FIXTURE))
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
        and value.get("statuses_reached") == sorted(STATUS_FILE_SETS)
        and value.get("mechanics") == {name: True for name in MECHANICS}
        and value.get("opposite_order_maps_byte_identical") is True
        and value.get("exact_underpowered_catch_verified") is True
        and value.get("five_field_prepublication_derivation_verified") is True
        and value.get("d135_science_kernel_evidence")
        == {
            "model_double_invocations": 3480,
            "synthetic_predictions_generated": 667872,
            "real_catboost_fits": 2,
            "reexecuted": False,
        }
        and value.get("forbidden_operations") == FORBIDDEN_OPERATIONS
        and value.get("cleanup_complete_before_publication") is True
        and value.get("private_roots_retained") == 0
        and value.get("model_quality_authority") is False
        and value.get("official_execution_authority") is False
        and value.get("claim_authority") is False
        and value.get("authority") == DENIED_AUTHORITY,
        "candidate aggregate differs",
    )
    official._validate_composite_acceptance(
        value,
        acceptance_sha256=acceptance_sha256,
        corrected_driver_sha256=corrected_driver_sha256,
        acceptance_driver_sha256=acceptance_driver_sha256,
        focused_tests_sha256=focused_tests_sha256,
    )


def _five_field_candidate_derivation(candidate_path: Path) -> bool:
    """Prove all five future fields before publishing the unchanged bytes."""

    candidate_sha256 = maplight.sha256_path(candidate_path)
    corrected_driver_sha256 = maplight.sha256_path(official.SCRIPT)
    acceptance_driver_sha256 = maplight.sha256_path(SCRIPT)
    focused_tests_sha256 = maplight.sha256_path(FOCUSED_TESTS)
    candidate = _json(candidate_path)
    _validate_candidate_acceptance(
        candidate,
        acceptance_sha256=candidate_sha256,
        corrected_driver_sha256=corrected_driver_sha256,
        acceptance_driver_sha256=acceptance_driver_sha256,
        focused_tests_sha256=focused_tests_sha256,
    )
    with _patched_official(COMPOSITE_ACCEPTANCE=candidate_path):
        derived = official.derive_consumed_claim()
    expected = {
        "future_scientific_runner_source_sha256": maplight.sha256_path(runner.SCRIPT),
        "future_official_attempt_driver_source_sha256": corrected_driver_sha256,
        "future_official_shaped_acceptance_driver_source_sha256": (
            acceptance_driver_sha256
        ),
        "future_official_shaped_execution_acceptance_sha256": candidate_sha256,
        "future_focused_tests_sha256": focused_tests_sha256,
    }
    return all(derived.get(name) == digest for name, digest in expected.items())


def _authenticate_test_transition_contract() -> None:
    """Authenticate the exact D-139 test-provenance transition boundary."""

    _require(
        TEST_TRANSITION_CONTRACT.is_file()
        and not TEST_TRANSITION_CONTRACT.is_symlink()
        and maplight.sha256_path(TEST_TRANSITION_CONTRACT)
        == TEST_TRANSITION_CONTRACT_SHA256,
        "D-139 test-transition contract differs",
    )
    contract = _json(TEST_TRANSITION_CONTRACT)
    historical = contract.get("historical_test_provenance")
    replacements = contract.get("d140_replacement_evidence")
    transition = contract.get("future_collection_transition")
    bindings = contract.get("future_transition_bindings")
    _require(
        contract.get("schema_version")
        == (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_official_orchestration_"
            "test_transition_contract.v1"
        )
        and contract.get("decision_id") == "D-139"
        and contract.get("gate")
        == (
            "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_"
            "TEST_TRANSITION_CONTRACT_FROZEN"
        )
        and isinstance(historical, Mapping)
        and historical.get("audit_path")
        == "tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py"
        and historical.get("audit_sha256") == HISTORICAL_D136_AUDIT_SHA256
        and historical.get("audit_total_test_nodes") == 7
        and historical.get("audit_mutation_allowed") is False
        and historical.get("historical_pytest_hook_sha256")
        == HISTORICAL_PYTEST_HOOK_SHA256
        and historical.get("retired_node_count") == len(RETIRED_D136_NODE_IDS)
        and historical.get("retained_active_node_count") == 4
        and historical.get("retired_node_ids") == list(RETIRED_D136_NODE_IDS)
        and isinstance(replacements, Mapping)
        and replacements.get("focused_tests_path")
        == "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
        and replacements.get("replacement_node_count") == len(REPLACEMENT_D140_NODE_IDS)
        and replacements.get("replacement_node_ids") == list(REPLACEMENT_D140_NODE_IDS)
        and isinstance(transition, Mapping)
        and transition.get("collection_constant")
        == "_PRE_D140_ORCHESTRATION_STATE_NODES"
        and transition.get("marker_kind") == "pytest.mark.skip"
        and transition.get("additional_retired_nodes_allowed") is False
        and [
            marker.get("node_id")
            for marker in cast(
                Sequence[Mapping[str, Any]], transition.get("exact_markers")
            )
        ]
        == list(RETIRED_D136_NODE_IDS)
        and isinstance(bindings, Mapping)
        and bindings.get("field_name") == "d139_test_transition_contract_sha256"
        and bindings.get("binding_only_no_behavior_change") is True,
        "D-139 test-transition identity differs",
    )
    transition_map = replacements.get("exact_transition_map")
    _require(
        isinstance(transition_map, list)
        and [
            (row.get("historical_node_id"), row.get("replacement_node_id"))
            for row in transition_map
            if isinstance(row, Mapping)
        ]
        == list(zip(RETIRED_D136_NODE_IDS, REPLACEMENT_D140_NODE_IDS, strict=True)),
        "D-139 test-transition map differs",
    )


def _authenticate_source_shape_transition_contract() -> None:
    """Authenticate the exact integrated D-140 source-shape boundary."""

    _require(
        SOURCE_SHAPE_TRANSITION_CONTRACT.is_file()
        and not SOURCE_SHAPE_TRANSITION_CONTRACT.is_symlink()
        and maplight.sha256_path(SOURCE_SHAPE_TRANSITION_CONTRACT)
        == SOURCE_SHAPE_TRANSITION_CONTRACT_SHA256,
        "D-140 source-shape transition contract differs",
    )
    contract = _json(SOURCE_SHAPE_TRANSITION_CONTRACT)
    historical = contract.get("historical_source_shape_provenance")
    replacements = contract.get("d141_replacement_evidence")
    transition = contract.get("future_collection_transition")
    bindings = contract.get("future_transition_bindings")
    expected_parents = {
        "d137_official_orchestration_repair_contract": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_official_orchestration_repair_"
                "contract.json"
            ),
            "sha256": REPAIR_CONTRACT_SHA256,
            "integrated_commit": "0dbbc7013b5303ef2f1535455d458b87208df1b9",
        },
        "d138_terminal_seal_erratum": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_official_orchestration_seal_"
                "erratum.json"
            ),
            "sha256": SEAL_ERRATUM_SHA256,
            "integrated_commit": "158dffcadfb71305d7de7b84279cfee96a6e8318",
        },
        "d139_test_provenance_transition_contract": {
            "path": (
                "benchmarks/openadmet_cyp_2026/"
                "global_v2_maplight_robustness_official_orchestration_test_"
                "transition_contract.json"
            ),
            "sha256": TEST_TRANSITION_CONTRACT_SHA256,
            "integrated_commit": "3b9c251f6875fedb33e51c4420cd8634c6e4cf29",
        },
    }
    _require(
        contract.get("schema_version")
        == (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_official_orchestration_"
            "source_shape_transition_contract.v1"
        )
        and contract.get("decision_id") == "D-140"
        and contract.get("gate")
        == (
            "G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_"
            "SOURCE_SHAPE_TRANSITION_CONTRACT_FROZEN"
        )
        and contract.get("contract_id")
        == (
            "G2-7H-MAPLIGHT-ROBUSTNESS-OFFICIAL-ORCHESTRATION-"
            "SOURCE-SHAPE-TRANSITION-V1"
        )
        and contract.get("base_commit") == "3b9c251f6875fedb33e51c4420cd8634c6e4cf29"
        and contract.get("parent_evidence") == expected_parents
        and isinstance(historical, Mapping)
        and historical.get("focused_snapshot_path")
        == "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
        and historical.get("focused_snapshot_sha256") == HISTORICAL_D134_FOCUSED_SHA256
        and historical.get("focused_snapshot_test_function_count") == 9
        and historical.get("focused_snapshot_mutation_allowed") is False
        and historical.get("previously_retired_node_count_in_snapshot") == 1
        and historical.get("newly_retired_node_count")
        == len(RETIRED_D134_SOURCE_SHAPE_NODE_IDS)
        and historical.get("retained_active_node_count_after_transition") == 6
        and historical.get("newly_retired_node_ids")
        == list(RETIRED_D134_SOURCE_SHAPE_NODE_IDS)
        and isinstance(replacements, Mapping)
        and replacements.get("focused_tests_path")
        == "tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py"
        and replacements.get("replacement_node_count")
        == len(REPLACEMENT_D141_SOURCE_SHAPE_NODE_IDS)
        and replacements.get("replacement_node_ids")
        == list(REPLACEMENT_D141_SOURCE_SHAPE_NODE_IDS)
        and replacements.get("future_nodes_may_be_absent_during_contract_freeze")
        is True
        and isinstance(transition, Mapping)
        and transition.get(
            "only_existing_file_with_transition_specific_behavior_change"
        )
        == "tests/conftest.py"
        and transition.get("collection_constant")
        == "_PRE_D141_ORCHESTRATION_SOURCE_SHAPE_NODES"
        and transition.get("marker_kind") == "pytest.mark.skip"
        and transition.get("previously_frozen_skip_count") == 4
        and transition.get("expected_total_skip_count_after_transition") == 6
        and transition.get("previous_d134_pre_acceptance_skip_is_preserved") is True
        and transition.get("previous_d139_three_node_transition_is_preserved") is True
        and transition.get("deselect_or_xfail_allowed") is False
        and transition.get("additional_retired_nodes_allowed") is False
        and isinstance(bindings, Mapping)
        and bindings.get("field_name") == "d140_source_shape_transition_contract_sha256"
        and bindings.get("binding_only_no_scientific_behavior_change") is True,
        "D-140 source-shape transition identity differs",
    )
    transition_map = replacements.get("exact_transition_map")
    _require(
        isinstance(transition_map, list)
        and len(transition_map) == len(RETIRED_D134_SOURCE_SHAPE_NODE_IDS)
        and all(isinstance(row, Mapping) for row in transition_map)
        and [
            (
                row.get("historical_node_id"),
                row.get("replacement_node_id"),
                row.get("replacement_scope"),
            )
            for row in cast(Sequence[Mapping[str, Any]], transition_map)
        ]
        == list(
            zip(
                RETIRED_D134_SOURCE_SHAPE_NODE_IDS,
                REPLACEMENT_D141_SOURCE_SHAPE_NODE_IDS,
                REPLACEMENT_D141_SOURCE_SHAPE_SCOPES,
                strict=True,
            )
        ),
        "D-140 source-shape transition map differs",
    )
    exact_markers = transition.get("exact_new_markers")
    _require(
        isinstance(exact_markers, list)
        and len(exact_markers) == len(RETIRED_D134_SOURCE_SHAPE_NODE_IDS)
        and all(isinstance(marker, Mapping) for marker in exact_markers)
        and [
            marker.get("node_id")
            for marker in cast(Sequence[Mapping[str, Any]], exact_markers)
        ]
        == list(RETIRED_D134_SOURCE_SHAPE_NODE_IDS),
        "D-140 source-shape collection markers differ",
    )


def _preflight() -> None:
    _authenticate_test_transition_contract()
    _authenticate_source_shape_transition_contract()
    _require(
        maplight.sha256_path(REPAIR_CONTRACT) == REPAIR_CONTRACT_SHA256
        and maplight.sha256_path(SEAL_ERRATUM) == SEAL_ERRATUM_SHA256
        and maplight.sha256_path(D135_ACCEPTANCE) == D135_ACCEPTANCE_SHA256
        and maplight.sha256_path(D136_BRIDGE) == D136_BRIDGE_SHA256
        and all(
            maplight.sha256_path(SCIENCE_KERNEL_PATHS[name]) == digest
            for name, digest in IMMUTABLE_SCIENCE_KERNEL_SHA256.items()
        )
        and FOCUSED_TESTS.is_file()
        and official.SCRIPT.is_file()
        and not FIXED_PARENT_ROOT.exists()
        and not FIXED_PARENT_ROOT.is_symlink()
        and not FIXED_WORK_ROOT.exists()
        and not FIXED_WORK_ROOT.is_symlink()
        and not ACCEPTANCE.exists()
        and not REJECTION.exists()
        and official._lstat(official.OFFICIAL_ATTEMPT_ROOT) is None
        and official._lstat(official.RESTRICTED_ROOT) is None
        and official._lstat(official.PUBLICATION_STAGING_ROOT) is None
        and official._lstat(official.FINAL_TERMINAL_ROOT) is None
        and official._lstat(official.CLAIM_STAGING_PATH) is None,
        "formal composite acceptance precondition differs",
    )
    official._authenticate_historical_science_kernel()


def _publish_record(path: Path, value: Mapping[str, Any]) -> Path:
    _require(not ACCEPTANCE.exists() and not REJECTION.exists(), "terminal exists")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(maplight.json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return path


def run_formal_acceptance() -> tuple[Path, bool]:
    """Run the fixed one-use composite acceptance and publish one record."""

    creation_started = False
    try:
        _preflight()
        FIXED_PARENT_ROOT.mkdir(mode=0o700)
        creation_started = True
        FIXED_WORK_ROOT.mkdir(mode=0o700)
        roots = [
            _execute_order(root=FIXED_WORK_ROOT / f"order-{order}", order=order)
            for order in ORDERS
        ]
        underpowered = _probe_exact_underpowered_helper(
            FIXED_WORK_ROOT / "exact-underpowered-probe"
        )
        _require(
            _probe_atomic_claim_and_seal_failures(
                FIXED_WORK_ROOT / "atomic-claim-and-seal-probes"
            ),
            "atomic claim or seal probe differs",
        )
        candidate = _build_acceptance_record(
            roots,
            exact_underpowered_catch_verified=underpowered,
            five_field_prepublication_derivation_verified=True,
        )
        candidate_path = FIXED_WORK_ROOT / "candidate-acceptance.json"
        candidate_path.write_bytes(maplight.json_bytes(candidate))
        _require(
            _five_field_candidate_derivation(candidate_path),
            "five-field derivation differs",
        )
        candidate_bytes = candidate_path.read_bytes()
        candidate_sha256 = maplight.sha256_bytes(candidate_bytes)
        _cleanup_owned_root(FIXED_WORK_ROOT)
        FIXED_PARENT_ROOT.rmdir()
        _require(not FIXED_PARENT_ROOT.exists(), "fixed acceptance cleanup differs")
        descriptor = os.open(ACCEPTANCE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(candidate_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(ACCEPTANCE.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        _require(
            maplight.sha256_path(ACCEPTANCE) == candidate_sha256,
            "published acceptance bytes differ",
        )
        return ACCEPTANCE, True
    except Exception as exc:
        cleanup_complete = False
        if creation_started:
            try:
                _cleanup_owned_root(FIXED_WORK_ROOT)
                if FIXED_PARENT_ROOT.exists() and not FIXED_PARENT_ROOT.is_symlink():
                    FIXED_PARENT_ROOT.rmdir()
                cleanup_complete = not FIXED_PARENT_ROOT.exists()
            except Exception:
                cleanup_complete = False
        rejection = {
            "schema_version": ACCEPTANCE_SCHEMA,
            "status": REJECTED_STATUS,
            "attempt_id": ATTEMPT_ID,
            "creation_started": creation_started,
            "failure_category": type(exc).__name__,
            "cleanup_complete_before_publication": cleanup_complete,
            "forbidden_operations": dict(FORBIDDEN_OPERATIONS),
            "model_quality_authority": False,
            "official_execution_authority": False,
            "claim_authority": False,
        }
        return _publish_record(REJECTION, rejection), False


def _main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("paths", nargs="*")
    parsed = parser.parse_args(arguments)
    if parsed.paths:
        print("formal acceptance accepts no root or output arguments", file=sys.stderr)
        return 2
    _path, success = run_formal_acceptance()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(_main())
