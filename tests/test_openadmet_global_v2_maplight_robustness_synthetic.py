from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
sys.path.insert(0, str(RESEARCH))
base = importlib.import_module("global_v2_maplight_runner")
robust = importlib.import_module("global_v2_maplight_robustness_runner")
synthetic = importlib.import_module(
    "run_global_v2_maplight_robustness_synthetic"
)


@contextmanager
def _writable(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    os.chmod(root, 0o755)
    yield root


def _reseal(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def _rewrite_source(root: Path, name: str, value: bytes) -> None:
    with _writable(root):
        (root / name).write_bytes(value)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        manifest["source_receipts"][name] = base.sha256_bytes(value)
        (root / "manifest.json").write_bytes(base.json_bytes(manifest))
    _reseal(root)


def _compile(tmp_path: Path, *, reverse: bool = False) -> tuple[Path, Path]:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=reverse)
    return robust.compile_capabilities(
        source_root=source,
        output_root=tmp_path / "capabilities",
        expected_runner_sha256=base.sha256_path(robust.SCRIPT),
    )


@pytest.fixture(scope="module")
def fake_replays(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    root = tmp_path_factory.mktemp("g2-7b-fake-replays")
    terminals = []
    resources = []
    for name, reverse in (("a", False), ("b", True)):
        source = synthetic.publish_source(
            root=root / f"{name}-source", reverse=reverse
        )
        terminal, resource = synthetic.run_replay(
            source_root=source,
            replay_root=root / name,
            reverse_execution_order=reverse,
            probe_runner=robust.publish_fake_runtime_probes,
            allow_test_double=True,
        )
        terminals.append(terminal)
        resources.append(resource)
    return terminals[0], terminals[1], resources[0], resources[1]


def _eligible_metric(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "tutorial_relative_improvement": 0.02,
        "component_mae_improvement": 0.01,
        "paired_upper_95": -0.001,
        "favorable_cells": 10,
        "maximum_endpoint_harm": 0.0,
        "tutorial_primary": 0.5,
        "component_macro_mae": 0.5,
    }
    value.update(changes)
    return value


def test_implementation_binds_exact_contract_parent_lock_and_topology() -> None:
    contract, parent = robust._static_contract()
    assert contract["gate"] == (
        "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_CONTRACT_FROZEN"
    )
    assert base.sha256_path(robust.SCRIPT) != "0" * 64
    assert base.sha256_path(robust.CONTRACT) == robust.CONTRACT_SHA256
    assert base.sha256_path(robust.PARENT) == robust.PARENT_SHA256
    assert base.sha256_path(robust.LOCK) == robust.LOCK_SHA256
    assert parent["workload"]["minimum_new_fits"] == 720
    assert parent["workload"]["maximum_new_fits"] == 1020
    assert len(robust.fit_identities("FULL_RETAINED")) == 720
    assert len(robust.fit_identities("DROP_MORGAN_SELECTED")) == 1020


def test_fixture_has_exact_family_overlay_and_feature_shape(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"] == {
        "molecules": 1200,
        "components": 600,
        "development_molecules": 960,
        "confirmatory_molecules": 240,
        "confirmatory_truth_values": 0,
        "fold_rows": 3600,
        "overlay_rows": 3600,
        "scorer_truth_rows": 7680,
    }
    feature = json.loads((source / "feature_manifest.json").read_text(encoding="utf-8"))
    assert feature["columns"] == 2563
    assert feature["widths"] == robust.FEATURE_WIDTHS
    assert len(feature["views"]) == 5
    assert len(set(feature["widths"].values())) == 4
    assert feature["drop_rule"] == "ordered zero-copy block exclusion"


def test_opposite_source_orders_have_same_canonical_receipt(tmp_path: Path) -> None:
    receipts = []
    physical_receipts = []
    for name, reverse in (("a", False), ("b", True)):
        source = synthetic.publish_source(root=tmp_path / name, reverse=reverse)
        manifest, files = robust._source_files(source)
        receipts.append(robust._canonical_source_receipt(files))
        physical_receipts.append(manifest["source_receipts"])
    assert receipts[0] == receipts[1]
    assert physical_receipts[0] != physical_receipts[1]


def test_compiler_capabilities_are_disjoint_and_truth_sealed(tmp_path: Path) -> None:
    model, scorer = _compile(tmp_path)
    assert {path.name for path in model.iterdir()} == {
        "molecules.csv",
        "folds.csv",
        "overlays.csv",
        "feature_manifest.json",
        "manifest.json",
    }
    assert {path.name for path in scorer.iterdir()} == {
        "scorer_profiles.json",
        "scorer_truth.csv",
        "manifest.json",
    }
    model_manifest = json.loads((model / "manifest.json").read_text(encoding="utf-8"))
    scorer_manifest = json.loads((scorer / "manifest.json").read_text(encoding="utf-8"))
    assert model_manifest["counts"]["truth_rows"] == 0
    assert scorer_manifest["counts"] == {
        "profiles": 2,
        "truth_rows": 7680,
        "finite_central_targets_per_profile_endpoint": 960,
        "confirmatory_truth_values": 0,
    }
    assert model_manifest["authority"]["synthetic_model_double_execution"]
    assert not model_manifest["authority"]["synthetic_metric_evaluation"]
    assert scorer_manifest["authority"]["synthetic_metric_evaluation"]
    assert all(
        not model_manifest["authority"][name]
        and not scorer_manifest["authority"][name]
        for name in robust.OFFICIAL_ZERO_FIELDS
    )


def test_scorer_truth_has_exact_development_support_and_no_confirmatory(
    tmp_path: Path,
) -> None:
    model, scorer = _compile(tmp_path)
    molecules = base._read_csv(model / "molecules.csv", robust.MOLECULE_COLUMNS)
    truth = base._read_csv(scorer / "scorer_truth.csv", robust.TRUTH_COLUMNS)
    development = {
        row["molecule_id"]
        for row in molecules
        if row["partition"] == "development"
    }
    confirmatory = {
        row["molecule_id"]
        for row in molecules
        if row["partition"] == "confirmatory"
    }
    assert len(truth) == 7680
    assert {row["molecule_id"] for row in truth} == development
    assert not ({row["molecule_id"] for row in truth} & confirmatory)
    counts: dict[tuple[str, str], int] = {}
    for profile in robust.PROFILES:
        for endpoint in robust.ENDPOINTS:
            counts[(profile, endpoint)] = sum(
                1
                for row in truth
                if row["profile"] == profile and row["endpoint"] == endpoint
            )
    assert set(counts.values()) == {960}
    assert all(float(row["low"]) <= float(row["point"]) <= float(row["high"]) for row in truth)


def test_model_double_exhausts_both_paths_and_exact_predictions(
    fake_replays: tuple[Path, Path, dict[str, Any], dict[str, Any]],
) -> None:
    terminal = fake_replays[0]
    manifest = json.loads(
        (terminal / robust.TERMINAL_FILES[-1]).read_text(encoding="utf-8")
    )
    assert manifest["counts"]["mechanics_profiles"] == 2
    assert manifest["counts"]["model_double_invocations"] == 1740
    assert manifest["counts"]["model_double_prediction_rows"] == 333216
    assert manifest["counts"]["full_size_prediction_identities"] == 797232
    assert manifest["chronology"] == {
        "stage_a_predictions_frozen_before_truth": True,
        "stage_b_predictions_frozen_before_truth": True,
        "stage_c_predictions_frozen_before_truth": True,
        "diagnostics_after_all_required_prediction_freezes": True,
    }


def test_two_opposite_order_replays_are_byte_identical(
    fake_replays: tuple[Path, Path, dict[str, Any], dict[str, Any]],
) -> None:
    assert robust.relative_byte_map(fake_replays[0]) == robust.relative_byte_map(
        fake_replays[1]
    )


def test_selection_profiles_and_diagnostics_are_exact(
    fake_replays: tuple[Path, Path, dict[str, Any], dict[str, Any]],
) -> None:
    terminal = fake_replays[0]
    tokens = json.loads((terminal / robust.TERMINAL_FILES[3]).read_text(encoding="utf-8"))
    assert {row["profile"]: row["selected_candidate"] for row in tokens} == {
        "FULL_RETAINED": robust.FULL,
        "DROP_MORGAN_SELECTED": robust.DROP_CANDIDATES[0],
    }
    assert {row["profile"]: row["stage_c_invocations"] for row in tokens} == {
        "FULL_RETAINED": 0,
        "DROP_MORGAN_SELECTED": 300,
    }
    diagnostics = json.loads(
        (terminal / robust.TERMINAL_FILES[4]).read_text(encoding="utf-8")
    )
    assert diagnostics["selection_micro_oracles"] == {
        "no_eligible": robust.FULL,
        "equal_1539_lexical": robust.DROP_CANDIDATES[0],
        "fewer_columns": robust.DROP_CANDIDATES[0],
        "diagnostics_cannot_revise": "PASS",
    }
    assert diagnostics["tutorial_metric_calls"] == 80
    assert diagnostics["bootstrap_replicates"] == 8000
    assert all(
        value["source_status"] == "SINGLE_SOURCE_NOT_APPLICABLE"
        and not value["clipped_recipe_adopted"]
        and value["all_required_gates_pass"]
        for value in diagnostics["profiles"].values()
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"tutorial_relative_improvement": 0.0, "component_mae_improvement": 0.0},
        {"paired_upper_95": 0.0},
        {"favorable_cells": 7},
        {"maximum_endpoint_harm": 0.0050001},
    ],
)
def test_each_selection_gate_is_conjunctive(changes: dict[str, object]) -> None:
    metrics = {
        candidate: _eligible_metric(
            tutorial_relative_improvement=0.0,
            component_mae_improvement=0.0,
        )
        for candidate in robust.DROP_CANDIDATES
    }
    metrics[robust.DROP_CANDIDATES[0]] = _eligible_metric(**changes)
    assert robust.select_candidate(metrics) == robust.FULL


def test_occam_order_uses_columns_metrics_then_lexical() -> None:
    metrics = {
        candidate: _eligible_metric() for candidate in robust.DROP_CANDIDATES
    }
    assert robust.select_candidate(metrics) == robust.DROP_CANDIDATES[0]
    metrics[robust.DROP_CANDIDATES[1]]["tutorial_primary"] = 0.49
    assert robust.select_candidate(metrics) == robust.DROP_CANDIDATES[1]


def test_primary_family_crossing_fails_before_model_stage(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    folds = base._read_csv(source / "folds.csv", robust.FOLD_COLUMNS)
    peer = next(row for row in folds if row["molecule_id"] == "g2-7b-synthetic-0001" and row["repeat"] == "0")
    peer["primary_fold"] = str((int(peer["primary_fold"]) + 1) % 5)
    _rewrite_source(source, "folds.csv", base.csv_bytes(robust.FOLD_COLUMNS, folds))
    with pytest.raises(robust.RobustnessSyntheticError, match="primary component crosses"):
        robust.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(robust.SCRIPT),
        )


def test_confirmatory_touching_overlay_retention_fails(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    rows = base._read_csv(source / "overlays.csv", robust.OVERLAY_COLUMNS)
    row = next(
        value
        for value in rows
        if value["overlay_id"] == "THRESHOLD_0_55"
        and value["molecule_id"] == "g2-7b-synthetic-0000"
    )
    confirmatory = next(
        value
        for value in rows
        if value["overlay_id"] == "THRESHOLD_0_55"
        and value["molecule_id"] == "g2-7b-synthetic-0960"
    )
    row.update(
        {
            "active_component_hash": confirmatory["active_component_hash"],
            "excluded_confirmatory_touch": "false",
            "fold_r0": "0",
            "fold_r1": "1",
            "fold_r2": "2",
        }
    )
    _rewrite_source(
        source, "overlays.csv", base.csv_bytes(robust.OVERLAY_COLUMNS, rows)
    )
    with pytest.raises(robust.RobustnessSyntheticError, match="exclusion counts"):
        robust.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(robust.SCRIPT),
        )


def test_second_source_value_fails_preflight(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    rows = base._read_csv(source / "molecules.csv", robust.MOLECULE_COLUMNS)
    rows[0]["source_file"] = "invented-assay.csv"
    _rewrite_source(
        source, "molecules.csv", base.csv_bytes(robust.MOLECULE_COLUMNS, rows)
    )
    with pytest.raises(robust.RobustnessSyntheticError, match="single source"):
        robust.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(robust.SCRIPT),
        )


def test_feature_view_order_or_width_drift_fails(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    feature = json.loads((source / "feature_manifest.json").read_text(encoding="utf-8"))
    feature["views"][robust.FULL].reverse()
    _rewrite_source(source, "feature_manifest.json", base.json_bytes(feature))
    with pytest.raises(robust.RobustnessSyntheticError, match="feature views"):
        robust.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(robust.SCRIPT),
        )


def test_cross_root_capability_mix_fails(tmp_path: Path) -> None:
    compiled = []
    for name, reverse in (("a", False), ("b", True)):
        source = synthetic.publish_source(
            root=tmp_path / f"{name}-source", reverse=reverse
        )
        compiled.append(
            robust.compile_capabilities(
                source_root=source,
                output_root=tmp_path / f"{name}-capabilities",
                expected_runner_sha256=base.sha256_path(robust.SCRIPT),
            )
        )
    model_double = robust.run_model_double(
        model_capability_root=compiled[0][0],
        output_root=tmp_path / "model-double",
        reverse_execution_order=False,
    )
    with pytest.raises(robust.RobustnessSyntheticError, match="cross-root"):
        robust.score_and_select(
            model_double_root=model_double,
            scorer_capability_root=compiled[1][1],
            output_root=tmp_path / "mixed",
        )


def test_truth_cannot_open_before_complete_prediction_freeze(tmp_path: Path) -> None:
    model, scorer = _compile(tmp_path)
    model_double = robust.run_model_double(
        model_capability_root=model,
        output_root=tmp_path / "model-double",
        reverse_execution_order=False,
    )
    with _writable(model_double):
        manifest = json.loads(
            (model_double / "manifest.json").read_text(encoding="utf-8")
        )
        manifest["stage_a_prediction_freeze_complete"] = False
        (model_double / "manifest.json").write_bytes(base.json_bytes(manifest))
    _reseal(model_double)
    with pytest.raises(robust.RobustnessSyntheticError, match="chronology"):
        robust.score_and_select(
            model_double_root=model_double,
            scorer_capability_root=scorer,
            output_root=tmp_path / "scored",
        )


def test_probe_identity_coverage_is_exact() -> None:
    identities = robust.probe_identities()
    assert len(identities) == len(set(identities)) == 13
    assert {value[0] for value in identities} == set(robust.FEATURE_VIEWS)
    assert {value[1] for value in identities} == {1, *robust.ALT_SEEDS}
    assert {value[2] for value in identities} == {
        robust.PRIMARY,
        *robust.OVERLAYS,
    }


def test_incomplete_or_wrong_probe_coverage_fails() -> None:
    rows = []
    for candidate, seed, index_form in robust.probe_identities():
        rows.append(
            {
                "candidate_id": candidate,
                "model_seed": seed,
                "index_form": index_form,
                "feature_columns": robust.FEATURE_WIDTHS[candidate],
            }
        )
    robust._validate_probe_coverage(rows)
    with pytest.raises(robust.RobustnessSyntheticError, match="fit count"):
        robust._validate_probe_coverage(rows[:-1])
    rows[0]["feature_columns"] = 999
    with pytest.raises(robust.RobustnessSyntheticError, match="column"):
        robust._validate_probe_coverage(rows)


def test_full_size_resource_traversal_is_exact_and_order_invariant() -> None:
    canonical = robust.traverse_full_size_resource(reverse_execution_order=False)
    reversed_order = robust.traverse_full_size_resource(reverse_execution_order=True)
    assert canonical["fit_identities"] == reversed_order["fit_identities"] == 1020
    assert (
        canonical["prediction_identities"]
        == reversed_order["prediction_identities"]
        == 797232
    )
    assert canonical["traversal_sha256"] == reversed_order["traversal_sha256"]
    assert canonical["bootstrap_replicates"] == 8000


def test_resource_projection_uses_worst_fit_and_is_conjunctive() -> None:
    passing = robust.resource_projection(
        probe_timing={
            "maximum_fit_wall_seconds": 10.0,
            "maximum_fit_cpu_seconds": 100.0,
            "peak_rss_kib": 1024,
        },
        traversal={
            "nonfit_wall_seconds": 1.0,
            "nonfit_cpu_seconds": 1.0,
            "peak_rss_kib": 1024,
        },
        restricted_bytes=1_000_000,
    )
    assert passing["all_gates_pass"]
    assert passing["projected_wall_hours"] == pytest.approx(10201 / 3600)
    failing = robust.resource_projection(
        probe_timing={
            "maximum_fit_wall_seconds": 28.0,
            "maximum_fit_cpu_seconds": 500.0,
            "peak_rss_kib": 20 * 1024 * 1024,
        },
        traversal={
            "nonfit_wall_seconds": 1.0,
            "nonfit_cpu_seconds": 1.0,
            "peak_rss_kib": 1024,
        },
        restricted_bytes=60_000_000_000,
    )
    assert not failing["all_gates_pass"]
    assert not all(failing["gates"].values())


def test_test_double_cannot_publish_aggregate_acceptance(
    fake_replays: tuple[Path, Path, dict[str, Any], dict[str, Any]], tmp_path: Path
) -> None:
    with pytest.raises(robust.RobustnessSyntheticError, match="test-double"):
        synthetic.accept_replays(
            terminal_a=fake_replays[0],
            terminal_b=fake_replays[1],
            resource_a=fake_replays[2],
            resource_b=fake_replays[3],
            output_root=tmp_path / "acceptance",
            focused_tests_passed=24,
        )


def test_terminal_has_exact_eight_files_and_zero_forbidden_counters(
    fake_replays: tuple[Path, Path, dict[str, Any], dict[str, Any]],
) -> None:
    terminal = fake_replays[0]
    assert {path.name for path in terminal.iterdir()} == set(robust.TERMINAL_FILES)
    manifest = json.loads(
        (terminal / robust.TERMINAL_FILES[-1]).read_text(encoding="utf-8")
    )
    assert manifest["counts"]["terminal_files"] == 8
    assert manifest["private_roots_retained"] == 0
    assert all(
        manifest["accounting"][name] == 0 for name in robust.OFFICIAL_ZERO_FIELDS
    )
    assert "no synthetic value can select or rank" in manifest[
        "scientific_interpretation"
    ]


def test_retry_resume_overwrite_and_wrong_runner_fail(
    fake_replays: tuple[Path, Path, dict[str, Any], dict[str, Any]], tmp_path: Path
) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    with pytest.raises(robust.RobustnessSyntheticError, match="replay root exists"):
        synthetic.run_replay(
            source_root=source,
            replay_root=fake_replays[0],
            reverse_execution_order=False,
            probe_runner=robust.publish_fake_runtime_probes,
            allow_test_double=True,
        )
    with pytest.raises(robust.RobustnessSyntheticError, match="runner source"):
        robust.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "wrong-runner",
            expected_runner_sha256="0" * 64,
        )


def test_injected_stage_failure_cleans_private_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)

    def fail(**_kwargs: object) -> Path:
        raise robust.RobustnessSyntheticError("injected stage failure")

    monkeypatch.setattr(robust, "run_model_double", fail)
    terminal = tmp_path / "terminal"
    with pytest.raises(robust.RobustnessSyntheticError, match="injected"):
        synthetic.run_replay(
            source_root=source,
            replay_root=terminal,
            reverse_execution_order=False,
            probe_runner=robust.publish_fake_runtime_probes,
            allow_test_double=True,
        )
    assert not terminal.exists()
    assert not terminal.with_name(".terminal-private").exists()


def test_symlink_source_and_parent_traversal_fail(tmp_path: Path) -> None:
    source = synthetic.publish_source(root=tmp_path / "source", reverse=False)
    with _writable(source):
        target = source / "molecules.csv"
        backup = source / "molecules-real.csv"
        target.rename(backup)
        target.symlink_to(backup.name)
    _reseal(source)
    with pytest.raises(base.GlobalV2MapLightError, match="symlink"):
        robust.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "compiled",
            expected_runner_sha256=base.sha256_path(robust.SCRIPT),
        )
    with pytest.raises(base.GlobalV2MapLightError, match="parent traversal"):
        base.publish_files(Path("..") / "forbidden-g2-7b", {"x": b"x"})


def test_implementation_contains_no_private_submission_result_fields() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (robust.SCRIPT, synthetic.SCRIPT)
    )
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text


def test_tracked_rejection_binds_the_one_shot_audit_failure() -> None:
    rejection_path = (
        robust.ROOT
        / "benchmarks"
        / "openadmet_cyp_2026"
        / "global_v2_maplight_robustness_synthetic_rejection.json"
    )
    rejection = json.loads(rejection_path.read_text(encoding="utf-8"))
    assert rejection["status"] == "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_REJECTED"
    assert rejection["contract_sha256"] == robust.CONTRACT_SHA256
    assert rejection["formal_attempt"] == {
        "maximum_attempts": 1,
        "attempts_completed": 1,
        "retry_authorized": False,
        "resume_authorized": False,
        "replacement_authorized": False,
        "untracked_generated_receipt_sha256": (
            "a2c722a8d432dcc2c8e4e8725cc6a5b9c13b7a37578fee229894fc8de1846235"
        ),
        "generated_status": "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_ACCEPTED",
        "generated_status_accepted_as_scientific_evidence": False,
    }
    audit = rejection["audit_rejection"]
    assert audit["feature_columns"] == 2563
    assert audit["varying_feature_columns"] == 47
    assert audit["constant_feature_columns"] == 2516
    assert rejection["implementation_receipts"] == {
        "runner_source_sha256": base.sha256_path(robust.SCRIPT),
        "driver_source_sha256": base.sha256_path(synthetic.SCRIPT),
        "focused_test_source_sha256": (
            "f81490a17e17d988562b3022e8c93b9d83105599e7a1bad658818babb5e6b8e0"
        ),
        "focused_tests_passed": 29,
    }
    assert not any(rejection["authority"].values())
    assert all(
        rejection["accounting"][name] == 0 for name in robust.OFFICIAL_ZERO_FIELDS
    )


def test_resource_fixture_exposes_the_tracked_constant_column_defect() -> None:
    matrix, _targets = robust._resource_matrix()
    varying = np.nanmax(matrix, axis=0) != np.nanmin(matrix, axis=0)
    assert int(varying.sum()) == 47
    assert int((~varying).sum()) == 2516
