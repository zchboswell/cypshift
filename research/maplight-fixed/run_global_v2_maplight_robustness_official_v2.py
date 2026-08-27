#!/usr/bin/env python3
"""One-use official driver for the corrected G2-7G robustness battery.

The outer process starts cumulative supervision.  Only the supervised child
may create the fixed attempt root and consume the claim.  The trusted compiler
runs in the root runtime; every model stage is a descendant in the pinned
research runtime.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
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
    "cypshift.openadmet_cyp_2026."
    "global_v2_maplight_robustness_execution_acceptance.v2"
)
ACCEPTANCE_DRIVER: Final = SCRIPT.with_name(
    "run_global_v2_maplight_robustness_execution_acceptance_v2.py"
)
FOCUSED_TESTS: Final = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
)
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
PENDING_TERMINAL_ROOT: Final = OFFICIAL_ATTEMPT_ROOT / "pending-terminal"
FINAL_TERMINAL_ROOT: Final = OFFICIAL_ATTEMPT_ROOT / "terminal"
LIMITS: Final = supervisor.ResourceLimits(
    wall_seconds=7.68 * 60 * 60,
    cpu_seconds=128.0 * 60 * 60,
    storage_bytes=51_200_000_000,
    rss_bytes=int(15.36 * 1024**3),
)


class RobustnessOfficialAttemptError(RuntimeError):
    """The one-use claim, fixed root, execution, or terminal differed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessOfficialAttemptError(message)


def _json(path: Path) -> dict[str, Any]:
    value, _raw = maplight._load_json(path)
    return value


def derive_consumed_claim() -> dict[str, Any]:
    """Derive the sole private consumed claim from the immutable public template."""

    _require(
        maplight.sha256_path(TRACKED_CLAIM) == TRACKED_CLAIM_SHA256,
        "tracked claim differs",
    )
    claim = _json(TRACKED_CLAIM)
    acceptance = _json(ACCEPTANCE)
    roots = cast(list[Mapping[str, Any]], acceptance.get("roots"))
    controls = cast(list[Mapping[str, Any]], acceptance.get("real_catboost_controls"))
    observation = cast(
        Mapping[str, Any], acceptance.get("cumulative_supervision")
    )

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
            and full.get("fit_counts")
            == {"stage_a": 540, "stage_b": 180, "stage_c": 0}
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
        and acceptance.get("status")
        == "G2_7G_MAPLIGHT_ROBUSTNESS_EXECUTION_ACCEPTED"
        and acceptance.get("contract_sha256") == runner.CONTRACT_SHA256
        and acceptance.get("scientific_runner_source_sha256")
        == maplight.sha256_path(runner.SCRIPT)
        and acceptance.get("official_attempt_driver_source_sha256")
        == maplight.sha256_path(SCRIPT)
        and acceptance.get("official_shaped_acceptance_driver_source_sha256")
        == maplight.sha256_path(ACCEPTANCE_DRIVER)
        and acceptance.get("focused_tests_sha256")
        == maplight.sha256_path(FOCUSED_TESTS)
        and isinstance(roots, list)
        and len(roots) == 2
        and [root.get("source_physical_order_reversed") for root in roots]
        == [False, True]
        and [root.get("fit_launch_order_reversed") for root in roots]
        == [False, True]
        and all(
            root.get("fit_counts")
            == {"stage_a": 1080, "stage_b": 360, "stage_c": 300}
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
    future = {
        "future_scientific_runner_source_sha256": maplight.sha256_path(runner.SCRIPT),
        "future_official_attempt_driver_source_sha256": maplight.sha256_path(SCRIPT),
        "future_official_shaped_acceptance_driver_source_sha256": maplight.sha256_path(
            ACCEPTANCE_DRIVER
        ),
        "future_official_shaped_execution_acceptance_sha256": maplight.sha256_path(
            ACCEPTANCE
        ),
        "future_focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
    }
    _require(
        claim.get("status") == "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
        and claim.get("contract_sha256") == runner.CONTRACT_SHA256
        and claim.get("maximum_consumptions") == 1
        and claim.get("consumptions") == 0
        and claim.get("usable") is False
        and all(claim.get(name) is None for name in future),
        "unconsumed claim template differs",
    )
    return {
        **claim,
        **future,
        "status": "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_CONSUMED",
        "consumptions": 1,
        "usable": False,
    }


def _publish_file(path: Path, value: Mapping[str, Any]) -> Path:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(maplight.json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    return path


def _consume_claim(claim: Mapping[str, Any]) -> tuple[Path, str]:
    _require(
        not OFFICIAL_ATTEMPT_ROOT.exists()
        and not OFFICIAL_ATTEMPT_ROOT.is_symlink()
        and OFFICIAL_ATTEMPT_ROOT.parent.resolve(strict=True)
        == Path("/home/zbos/cypshift-private/openadmet-2026"),
        "fixed attempt root is unavailable",
    )
    OFFICIAL_ATTEMPT_ROOT.mkdir(mode=0o700)
    path = _publish_file(OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json", claim)
    supervisor.resource_checkpoint("stage:claim-consumed")
    return path, maplight.sha256_path(path)


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


def _terminal_bytes(root: Path) -> dict[str, bytes]:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
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


def _child() -> int:
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
    try:
        work.mkdir(mode=0o700)
        model, central_scorer, _preflight = compiler.compile_capabilities(
            source_root=OFFICIAL_SOURCE_ROOT,
            output_root=work / "d126-capabilities",
            mode="official",
            authorization=_compiler_authorization(claim, claim_sha256),
            expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
        )
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
    finally:
        if work.exists():
            mechanics._safe_cleanup(work)
    _require(not work.exists(), "private execution cleanup is incomplete")
    published = maplight.publish_files(PENDING_TERMINAL_ROOT, files)
    _require(published.is_dir(), "terminal staging failed")
    supervisor.resource_checkpoint("stage:terminal-staged-after-cleanup")
    return 0


def _observation_payload(
    observed: supervisor.ResourceObservation,
) -> dict[str, Any]:
    return {**vars(observed), "limits": vars(LIMITS)}


def _staged_accounting() -> dict[str, Any] | None:
    for root in (PENDING_TERMINAL_ROOT, FINAL_TERMINAL_ROOT):
        manifest_path = root / "manifest.json"
        if manifest_path.is_file():
            accounting = _json(manifest_path).get("accounting")
            if isinstance(accounting, Mapping):
                return dict(accounting)
    return None


def _cleanup_terminal(root: Path) -> None:
    if root.exists():
        mechanics._safe_cleanup(root)
    _require(not root.exists(), "aggregate terminal cleanup is incomplete")


def _finalize_terminal(observed: supervisor.ResourceObservation) -> Path:
    observation = _observation_payload(observed)
    _require(
        observed.return_code == 0
        and observed.cleanup_complete
        and observed.network_namespace_isolated
        and observed.gpu_environment_hidden
        and observed.detached_children_observed == 0
        and observed.warnings_observed == 0
        and observed.checkpoints_acknowledged > 0
        and not RESTRICTED_ROOT.exists(),
        "cumulative supervision differs",
    )
    files = _terminal_bytes(PENDING_TERMINAL_ROOT)
    manifest = _json(PENDING_TERMINAL_ROOT / "manifest.json")
    claim_path = OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json"
    _require(
        manifest.get("schema_version") == runner.TERMINAL_SCHEMA
        and manifest.get("synthetic") is False
        and manifest.get("contract_sha256") == runner.CONTRACT_SHA256
        and manifest.get("consumed_claim_sha256") == maplight.sha256_path(claim_path)
        and manifest.get("row_level_values_retained") == 0
        and manifest.get("model_binaries_retained") == 0,
        "staged scientific terminal differs",
    )
    manifest["cumulative_supervision"] = observation
    manifest["supervision_complete_before_publication"] = True
    files["manifest.json"] = maplight.json_bytes(manifest)
    published = maplight.publish_files(FINAL_TERMINAL_ROOT, files)
    _cleanup_terminal(PENDING_TERMINAL_ROOT)
    return published


def _failure_terminal(
    category: str,
    claim_sha256: str | None,
    *,
    resource_abort: bool,
    accounting: Mapping[str, Any] | None,
    observation: Mapping[str, Any] | None,
) -> Path:
    _cleanup_terminal(PENDING_TERMINAL_ROOT)
    _cleanup_terminal(FINAL_TERMINAL_ROOT)
    manifest = {
        "schema_version": runner.TERMINAL_SCHEMA,
        "status": (
            "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED"
            if resource_abort
            else "G2_7_MAPLIGHT_ROBUSTNESS_FAILED"
        ),
        "synthetic": False,
        "contract_sha256": runner.CONTRACT_SHA256,
        "consumed_claim_sha256": claim_sha256,
        "failure_category": category,
        "cleanup_complete": not RESTRICTED_ROOT.exists(),
        "accounting": dict(accounting) if accounting is not None else None,
        "accounting_complete": accounting is not None,
        "cumulative_supervision": (
            dict(observation) if observation is not None else None
        ),
        "authority": dict(maplight.DENIED_AUTHORITY),
    }
    return maplight.publish_files(
        FINAL_TERMINAL_ROOT, {"manifest.json": maplight.json_bytes(manifest)}
    )


def _make_readonly(root: Path) -> None:
    for child in sorted(
        root.rglob("*"), key=lambda path: len(path.parts), reverse=True
    ):
        os.chmod(child, 0o555 if child.is_dir() else 0o444, follow_symlinks=False)
    os.chmod(root, 0o555, follow_symlinks=False)


def run_official_attempt() -> Path:
    """Start supervision, consume once inside it, and return the sole terminal."""

    derive_consumed_claim()
    _require(
        not OFFICIAL_ATTEMPT_ROOT.exists()
        and not RESTRICTED_ROOT.exists()
        and OFFICIAL_ATTEMPT_ROOT.parent.resolve(strict=True)
        == RESTRICTED_ROOT.parent.resolve(strict=True)
        and shutil.disk_usage(OFFICIAL_ATTEMPT_ROOT.parent).free
        >= LIMITS.storage_bytes,
        "official preflight differs",
    )
    observed: supervisor.ResourceObservation | None = None
    try:
        observed = supervisor.run_supervised(
            [sys.executable, str(SCRIPT), "--child"],
            restricted_root=RESTRICTED_ROOT,
            limits=LIMITS,
            poll_interval_seconds=1.0,
            writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent,
        )
        terminal = _finalize_terminal(observed)
        _make_readonly(OFFICIAL_ATTEMPT_ROOT)
        return terminal
    except Exception as exc:
        accounting = _staged_accounting()
        claim_path = OFFICIAL_ATTEMPT_ROOT / "attempt_claim.json"
        claim_sha256 = (
            maplight.sha256_path(claim_path) if claim_path.is_file() else None
        )
        if not OFFICIAL_ATTEMPT_ROOT.exists():
            OFFICIAL_ATTEMPT_ROOT.mkdir(mode=0o700)
        else:
            os.chmod(OFFICIAL_ATTEMPT_ROOT, 0o700)
        terminal = _failure_terminal(
            type(exc).__name__,
            claim_sha256,
            resource_abort=isinstance(exc, supervisor.ResourceSupervisorError),
            accounting=accounting,
            observation=_observation_payload(observed) if observed is not None else None,
        )
        _make_readonly(OFFICIAL_ATTEMPT_ROOT)
        return terminal


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
