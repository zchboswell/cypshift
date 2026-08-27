#!/usr/bin/env python3
"""Single formal two-root acceptance for the corrected G2-7G execution path."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
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
import run_global_v2_maplight_robustness_no_fit_acceptance as model_fixture
import run_global_v2_maplight_robustness_scoring_capability_acceptance_v2 as scoring_fixture

SCRIPT: Final = Path(__file__).resolve()
ROOT: Final = SCRIPT.parents[2]
BENCHMARK: Final = ROOT / "benchmarks" / "openadmet_cyp_2026"
ACCEPTANCE: Final = (
    BENCHMARK / "global_v2_maplight_robustness_execution_acceptance_v2.json"
)
REJECTION: Final = (
    BENCHMARK / "global_v2_maplight_robustness_execution_acceptance_rejection_v2.json"
)
FOCUSED_TESTS: Final = (
    ROOT / "tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py"
)
OFFICIAL_ATTEMPT_DRIVER: Final = SCRIPT.with_name(
    "run_global_v2_maplight_robustness_official_v2.py"
)
FIXED_PARENT_ROOT: Final = Path("/tmp/cypshift-g2-7g")
FIXED_WORK_ROOT: Final = FIXED_PARENT_ROOT / "execution-acceptance-attempt-1"
ATTEMPT_ID: Final = "g2-7g-official-shaped-execution-acceptance-attempt-1"
CHILD_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026."
    "global_v2_maplight_robustness_execution_acceptance_child.v2"
)
ACCEPTANCE_SCHEMA: Final = (
    "cypshift.openadmet_cyp_2026."
    "global_v2_maplight_robustness_execution_acceptance.v2"
)
MODEL_PYTHON: Final = SCRIPT.parent / ".venv/bin/python"
MODEL_FIXTURE_SHA256: Final = (
    "9245c76cf5fbd0aa8ed85b830c96e877cb7968568af982471bcbe33a53c409b9"
)
SCORING_FIXTURE_SHA256: Final = (
    "e8895bb93e1363ee6b7d4b514a420f35425d55b39f0214a982ed78e21c84de61"
)
LIMITS: Final = supervisor.ResourceLimits(
    wall_seconds=7.68 * 60 * 60,
    cpu_seconds=128.0 * 60 * 60,
    storage_bytes=51_200_000_000,
    rss_bytes=int(15.36 * 1024**3),
)


class RobustnessExecutionAcceptanceError(RuntimeError):
    """The fixed acceptance chronology or aggregate evidence differed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RobustnessExecutionAcceptanceError(message)


def _relative_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): maplight.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _publish_baseline(
    *,
    root: Path,
    profile: str,
    model_root: Path,
    scoring_root: Path,
) -> Path:
    _model_manifest, _arrays, fold_map, _molecules = runner._model_arrays_and_folds(
        model_root, synthetic=True
    )
    _scoring_manifest, truth = runner._scoring_truth(
        scoring_root,
        synthetic=True,
        model_capability_root=model_root,
        fold_map=fold_map,
    )
    rows: list[dict[str, object]] = []
    for (molecule, endpoint), truth_row in sorted(truth.items()):
        for repeat in compiler.REPEATS:
            _structure, component, fold = fold_map[(molecule, repeat, "PRIMARY_D032")]
            point = float(truth_row["point"])
            if profile == "full_retained":
                prediction = (
                    float(truth_row["high"]) + 0.00001 if truth_row["high"] else point
                )
            else:
                prediction = point + 2.0
            rows.append(
                {
                    "molecule_id": molecule,
                    "endpoint": endpoint,
                    "similarity_component_hash": component,
                    "repeat": repeat,
                    "outer_fold": fold,
                    "system_id": maplight.SYSTEM_ID,
                    "prediction": format(prediction, ".17g"),
                    "model_id": maplight.sha256_bytes(
                        f"synthetic-baseline|{endpoint}|{repeat}|{fold}".encode()
                    ),
                    "split_id": maplight.sha256_bytes(
                        f"synthetic-split|{repeat}|{fold}".encode()
                    ),
                }
            )
    rows.sort(key=lambda row: tuple(row[name] for name in runner.BASELINE_COLUMNS[:5]))
    payload = maplight.csv_bytes(runner.BASELINE_COLUMNS, rows)
    manifest = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026."
            "global_v2_maplight_robustness_synthetic_baseline.v2"
        ),
        "synthetic": True,
        "selection_profile": profile,
        "output_receipts": {
            "development_outer_oof.csv": maplight.sha256_bytes(payload)
        },
        "official_operations": 0,
        "model_quality_authority": False,
        "claim_authority": False,
    }
    return maplight.publish_files(
        root,
        {
            "development_outer_oof.csv": payload,
            "manifest.json": maplight.json_bytes(manifest),
        },
    )


def _run_model_stage(
    *,
    stage: str,
    selected: str | None,
    model_root: Path,
    output_root: Path,
    reverse: bool,
) -> tuple[Path, dict[str, int]]:
    command = [
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
        "--synthetic-model-double",
    ]
    if reverse:
        command.append("--reverse-fit-order")
    subprocess.run(command, check=True)
    manifest, _raw = maplight._load_json(output_root / "manifest.json")
    return output_root, {
        "fits": int(manifest["fit_identities"]),
        "predictions": int(manifest["prediction_identities"]),
    }


def _execute_profile(
    *,
    root: Path,
    reverse: bool,
    profile: str,
    model: Path,
    scoring: Path,
) -> dict[str, Any]:
    baseline = _publish_baseline(
        root=root / "baseline",
        profile=profile,
        model_root=model,
        scoring_root=scoring,
    )
    stage_a, stage_a_counts = _run_model_stage(
        stage="stage_a",
        selected=None,
        model_root=model,
        output_root=root / "stage-a",
        reverse=reverse,
    )
    selected, selection = runner.select_stage_a_candidate(
        stage_a_root=stage_a,
        scoring_capability_root=scoring,
        baseline_terminal_root=baseline,
        model_capability_root=model,
        synthetic=True,
    )
    _require(
        (profile == "full_retained" and selected == "G2-7-M0-FULL")
        or (profile == "deletion_selected" and selected != "G2-7-M0-FULL"),
        "synthetic conditional path differs",
    )
    stage_b, stage_b_counts = _run_model_stage(
        stage="stage_b",
        selected=selected,
        model_root=model,
        output_root=root / "stage-b",
        reverse=reverse,
    )
    stage_c = None
    stage_c_counts = {"fits": 0, "predictions": 0}
    if selected != "G2-7-M0-FULL":
        stage_c, stage_c_counts = _run_model_stage(
            stage="stage_c",
            selected=selected,
            model_root=model,
            output_root=root / "stage-c",
            reverse=reverse,
        )
    terminal = runner.score_frozen_battery(
        selected_candidate=selected,
        selection_evidence=selection,
        stage_a_root=stage_a,
        stage_b_root=stage_b,
        stage_c_root=stage_c,
        scoring_capability_root=scoring,
        baseline_terminal_root=baseline,
        model_capability_root=model,
        output_root=root / "terminal",
        synthetic=True,
    )
    terminal_manifest, _raw = maplight._load_json(terminal / "manifest.json")
    result = {
        "selection_profile": profile,
        "fit_launch_order_reversed": reverse,
        "selected_candidate": selected,
        "terminal_tree": _relative_map(terminal),
        "fit_counts": {
            "stage_a": stage_a_counts["fits"],
            "stage_b": stage_b_counts["fits"],
            "stage_c": stage_c_counts["fits"],
        },
        "prediction_counts": {
            "stage_a": stage_a_counts["predictions"],
            "stage_b": stage_b_counts["predictions"],
            "stage_c": stage_c_counts["predictions"],
        },
        "terminal_status": terminal_manifest["status"],
        "official_operations": 0,
        "claims_created": 0,
        "claims_consumed": 0,
    }
    return result


def _execute_root(*, root: Path, reverse: bool) -> dict[str, Any]:
    source = model_fixture.publish_source(root=root / "source", reverse=reverse)
    model, central_scorer, preflight = compiler.compile_capabilities(
        source_root=source,
        output_root=root / "d126-capabilities",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
    )
    direct = scoring_fixture._publish_scoring_source(
        root=root / "direct-source", reverse=reverse
    )
    scoring = scoring_compiler.compile_scoring_capability(
        direct_source_root=direct,
        model_capability_root=model,
        scorer_capability_root=central_scorer,
        output_root=root / "eight-field-scorer",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(scoring_compiler.SCRIPT),
    )
    profiles = {
        profile: _execute_profile(
            root=root / "profiles" / profile,
            reverse=reverse,
            profile=profile,
            model=model,
            scoring=scoring,
        )
        for profile in ("full_retained", "deletion_selected")
    }
    result = {
        "source_physical_order_reversed": reverse,
        "fit_launch_order_reversed": reverse,
        "preflight_status": preflight["status"],
        "model_capability_tree": _relative_map(model),
        "scoring_capability_tree": _relative_map(scoring),
        "terminal_tree": {
            f"{profile}/{name}": receipt
            for profile, summary in profiles.items()
            for name, receipt in summary["terminal_tree"].items()
        },
        "profiles": profiles,
        "fit_counts": {
            stage: sum(summary["fit_counts"][stage] for summary in profiles.values())
            for stage in ("stage_a", "stage_b", "stage_c")
        },
        "prediction_counts": {
            stage: sum(
                summary["prediction_counts"][stage] for summary in profiles.values()
            )
            for stage in ("stage_a", "stage_b", "stage_c")
        },
        "official_operations": 0,
        "claims_created": 0,
        "claims_consumed": 0,
    }
    mechanics._safe_cleanup(root)
    _require(not root.exists(), "synthetic root cleanup is incomplete")
    return result


def _real_catboost_controls(root: Path) -> list[dict[str, Any]]:
    subprocess.run(
        [
            str(MODEL_PYTHON),
            str(runner.SCRIPT),
            "real-controls",
            "--output-root",
            str(root),
        ],
        check=True,
    )
    manifest, _raw = maplight._load_json(root / "manifest.json")
    _require(manifest["real_catboost_fits"] == 2, "real control count differs")
    rows = cast(list[dict[str, Any]], manifest["controls"])
    mechanics._safe_cleanup(root)
    return rows


def _child(restricted_root: Path, publication_root: Path) -> int:
    supervisor.resource_checkpoint("stage:acceptance-child-authorized")
    _require(
        restricted_root == FIXED_WORK_ROOT / "restricted"
        and publication_root == FIXED_WORK_ROOT / "publication" / "child",
        "fixed child paths differ",
    )
    runner.authenticate_static_boundary()
    _require(
        platform.python_version() == "3.12.3"
        and importlib.metadata.version("rdkit") == "2026.3.5",
        "trusted compiler/scorer runtime differs",
    )
    _require(restricted_root.is_dir(), "restricted root is absent")
    roots = [
        _execute_root(
            root=restricted_root / "root-a",
            reverse=False,
        ),
        _execute_root(
            root=restricted_root / "root-b",
            reverse=True,
        ),
    ]
    _require(
        roots[0]["model_capability_tree"] == roots[1]["model_capability_tree"]
        and roots[0]["scoring_capability_tree"] == roots[1]["scoring_capability_tree"],
        "opposite-order capability trees differ",
    )
    _require(
        roots[0]["terminal_tree"] == roots[1]["terminal_tree"],
        "opposite-order aggregate terminal trees differ",
    )
    controls = _real_catboost_controls(restricted_root / "real-controls")
    aggregate = {
        "schema_version": CHILD_SCHEMA,
        "roots": roots,
        "real_catboost_controls": controls,
        "real_catboost_fits": 2,
        "model_double_invocations": sum(
            sum(root["fit_counts"].values()) for root in roots
        ),
        "synthetic_predictions_generated": sum(
            sum(root["prediction_counts"].values()) for root in roots
        ),
        "both_conditional_paths": True,
        "profiles_per_root": ["full_retained", "deletion_selected"],
        "opposite_physical_and_fit_order": True,
        "capability_maps_byte_identical": True,
        "terminal_maps_byte_identical": True,
        "official_operations": 0,
        "claims_created": 0,
        "claims_consumed": 0,
        "private_roots_retained": 0,
    }
    maplight.publish_files(
        publication_root,
        {"child-aggregate.json": maplight.json_bytes(aggregate)},
    )
    return 0


def _preflight() -> None:
    runner.authenticate_static_boundary()
    _require(
        maplight.sha256_path(model_fixture.SCRIPT) == MODEL_FIXTURE_SHA256,
        "model fixture differs",
    )
    _require(
        maplight.sha256_path(scoring_fixture.SCRIPT) == SCORING_FIXTURE_SHA256,
        "scoring fixture differs",
    )
    _require(
        FOCUSED_TESTS.is_file()
        and OFFICIAL_ATTEMPT_DRIVER.is_file()
        and MODEL_PYTHON.is_symlink()
        and MODEL_PYTHON.resolve(strict=True).is_file()
        and not FIXED_PARENT_ROOT.exists()
        and not FIXED_PARENT_ROOT.is_symlink()
        and not FIXED_WORK_ROOT.exists()
        and not FIXED_WORK_ROOT.is_symlink()
        and not ACCEPTANCE.exists()
        and not REJECTION.exists(),
        "formal acceptance precondition differs",
    )


def _cleanup_fixed_root(*, work_owned: bool, parent_owned: bool) -> None:
    if work_owned and FIXED_WORK_ROOT.exists():
        mechanics._safe_cleanup(FIXED_WORK_ROOT)
    if parent_owned and FIXED_PARENT_ROOT.exists():
        FIXED_PARENT_ROOT.rmdir()
    _require(
        (not work_owned or not FIXED_WORK_ROOT.exists())
        and (not parent_owned or not FIXED_PARENT_ROOT.exists()),
        "formal root cleanup is incomplete",
    )


def _publish_record(path: Path, value: Mapping[str, Any]) -> Path:
    _require(not ACCEPTANCE.exists() and not REJECTION.exists(), "terminal exists")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(maplight.json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    return path


def _terminal(
    value: Mapping[str, Any], observation: Mapping[str, Any]
) -> dict[str, Any]:
    roots = cast(list[Mapping[str, Any]], value["roots"])
    controls = cast(list[Mapping[str, Any]], value["real_catboost_controls"])
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

    def profile_evidence(root: Mapping[str, Any]) -> bool:
        profiles = cast(Mapping[str, Mapping[str, Any]], root["profiles"])
        if set(profiles) != {"full_retained", "deletion_selected"}:
            return False
        full = profiles["full_retained"]
        deletion = profiles["deletion_selected"]
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
                for profile in profiles.values()
            )
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
        value.get("schema_version") == CHILD_SCHEMA
        and len(roots) == 2
        and [root["source_physical_order_reversed"] for root in roots]
        == [False, True]
        and [root["fit_launch_order_reversed"] for root in roots] == [False, True]
        and all(
            profile_evidence(root)
            and root["fit_counts"]
            == {"stage_a": 1080, "stage_b": 360, "stage_c": 300}
            and root["official_operations"] == 0
            and root["claims_created"] == 0
            and root["claims_consumed"] == 0
            for root in roots
        )
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
        and value["real_catboost_fits"] == 2
        and value["model_double_invocations"] == 3480
        and value["both_conditional_paths"] is True
        and value["profiles_per_root"] == ["full_retained", "deletion_selected"]
        and value["opposite_physical_and_fit_order"] is True
        and value["capability_maps_byte_identical"] is True
        and value["terminal_maps_byte_identical"] is True
        and value["official_operations"] == 0
        and value["claims_created"] == 0
        and value["claims_consumed"] == 0
        and value["private_roots_retained"] == 0
        and roots[0]["model_capability_tree"]
        == roots[1]["model_capability_tree"]
        and roots[0]["scoring_capability_tree"]
        == roots[1]["scoring_capability_tree"]
        and roots[0]["terminal_tree"] == roots[1]["terminal_tree"]
        and observation.get("return_code") == 0
        and observation.get("cleanup_complete") is True
        and observation.get("network_namespace_isolated") is True
        and observation.get("gpu_environment_hidden") is True
        and observation.get("detached_children_observed") == 0
        and observation.get("warnings_observed") == 0
        and int(observation.get("checkpoints_acknowledged", 0)) > 0
        and int(observation.get("descendant_processes_observed", 0)) > 0
        and observation.get("limits") == vars(LIMITS),
        "acceptance aggregate differs",
    )
    child_value = dict(value)
    child_value.pop("schema_version")
    return {
        **child_value,
        "status": "G2_7G_MAPLIGHT_ROBUSTNESS_EXECUTION_ACCEPTED",
        "attempt_id": ATTEMPT_ID,
        "contract_sha256": runner.CONTRACT_SHA256,
        "scientific_runner_source_sha256": maplight.sha256_path(runner.SCRIPT),
        "official_attempt_driver_source_sha256": maplight.sha256_path(
            OFFICIAL_ATTEMPT_DRIVER
        ),
        "official_shaped_acceptance_driver_source_sha256": maplight.sha256_path(SCRIPT),
        "focused_tests_sha256": maplight.sha256_path(FOCUSED_TESTS),
        "cumulative_supervision": dict(observation),
        "cleanup_complete_before_publication": True,
        "model_quality_authority": False,
        "claim_authority": False,
        "schema_version": ACCEPTANCE_SCHEMA,
    }


def run_formal_attempt() -> tuple[Path, bool]:
    """Run the only fixed acceptance attempt and publish one aggregate record."""

    parent_owned = False
    work_owned = False
    try:
        _preflight()
        FIXED_PARENT_ROOT.mkdir(mode=0o700)
        parent_owned = True
        FIXED_WORK_ROOT.mkdir(mode=0o700)
        work_owned = True
        publication_parent = FIXED_WORK_ROOT / "publication"
        publication_parent.mkdir(mode=0o700)
        publication_root = publication_parent / "child"
        restricted_root = FIXED_WORK_ROOT / "restricted"
        command = [
            sys.executable,
            str(SCRIPT),
            "--child",
            str(restricted_root),
            str(publication_root),
        ]
        observed = supervisor.run_supervised(
            command,
            restricted_root=restricted_root,
            limits=LIMITS,
            poll_interval_seconds=1.0,
            writable_publication_parent=publication_parent,
            publication_root=publication_root,
        )
        value, _raw = maplight._load_json(publication_root / "child-aggregate.json")
        observation = {
            **vars(observed),
            "limits": vars(LIMITS),
        }
        _cleanup_fixed_root(work_owned=work_owned, parent_owned=parent_owned)
        terminal = _terminal(value, observation)
        return _publish_record(ACCEPTANCE, terminal), True
    except Exception as exc:
        cleanup_complete = False
        if parent_owned or work_owned:
            try:
                _cleanup_fixed_root(
                    work_owned=work_owned, parent_owned=parent_owned
                )
                cleanup_complete = True
            except Exception:
                cleanup_complete = False
        rejection = {
            "status": "G2_7G_MAPLIGHT_ROBUSTNESS_EXECUTION_ACCEPTANCE_REJECTED",
            "attempt_id": ATTEMPT_ID,
            "creation_started": parent_owned or work_owned,
            "failure_category": type(exc).__name__,
            "official_operations": 0,
            "claims_consumed": 0,
            "cleanup_complete_before_publication": cleanup_complete,
        }
        return _publish_record(REJECTION, rejection), False


def _main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("paths", nargs="*")
    parsed = parser.parse_args(arguments)
    if parsed.child:
        _require(len(parsed.paths) == 2, "child paths differ")
        return _child(Path(parsed.paths[0]), Path(parsed.paths[1]))
    if parsed.paths:
        print("formal acceptance accepts no root or output arguments", file=sys.stderr)
        return 2
    _path, success = run_formal_attempt()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(_main())
