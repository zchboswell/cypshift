from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
sys.path.insert(0, str(RESEARCH))
maplight = importlib.import_module("global_v2_maplight_runner")
compiler = importlib.import_module("global_v2_maplight_robustness_execution_compiler")
supervisor = importlib.import_module("global_v2_maplight_resource_supervisor")
wrapper = importlib.import_module("global_v2_maplight_robustness_execution_wrapper")
driver = importlib.import_module("run_global_v2_maplight_robustness_no_fit_acceptance")
LIVE_SUPERVISOR_RUNTIME = (
    sys.version_info[:3] == (3, 12, 3) and os.environ.get("CI") != "true"
)


@pytest.fixture(scope="module")
def compiled(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("g2-7c-compiled")
    source = driver.publish_source(root=root / "source", reverse=False)
    model, scorer, preflight = compiler.compile_capabilities(
        source_root=source,
        output_root=root / "capabilities",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
    )
    return root, source, model, scorer, preflight


def _tree_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): maplight.sha256_path(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _mutable_source(
    source: Path, root: Path
) -> tuple[dict[str, bytes], dict[str, Any]]:
    manifest = compiler._load_json(source / "manifest.json")
    files = {name: (source / name).read_bytes() for name in compiler.SOURCE_FILES}
    return files, manifest


def test_static_boundary_authenticates_only_accepted_primitives() -> None:
    science = compiler.authenticate_static_boundary()
    assert compiler.PARENT_CONTRACT_SHA256 == (
        "ad9aef871ab06e5082568f20a9a6d293897924bdfeda2fb341685cffaa7a45af"
    )
    assert compiler.BOUNDED_CONTRACT_SHA256 == (
        "55fafa1d9806ba3221c26b8cd71d077ad61a0f485e51defbae21cbd4b5806527"
    )
    assert science["workload"]["stage_a_fits"] == 540
    assert science["workload"]["stage_b_fits"] == 180
    assert science["workload"]["stage_c_conditional_fits"] == 300
    for path in (compiler.SCRIPT, wrapper.SCRIPT, supervisor.SCRIPT, driver.SCRIPT):
        assert maplight.sha256_path(path) not in {
            "ded3caa9b6a71d03cf6a1f428a14fee0993317ad2072625b7cfc61ef9a6c5666",
            "6af784962fc0b4d3e48a6df5f763874143a1c157d9bac6ac1aaf8e920ea73aac",
        }


def test_new_sources_do_not_import_rejected_g2_7b_implementation() -> None:
    rejected_modules = {
        "global_v2_maplight_robustness_runner",
        "run_global_v2_maplight_robustness_synthetic",
    }
    for path in (compiler.SCRIPT, wrapper.SCRIPT, supervisor.SCRIPT, driver.SCRIPT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imports.isdisjoint(rejected_modules)


def test_official_shaped_source_is_exact_and_confirmatory_is_opaque() -> None:
    molecules, folds, targets, arrays = driver.fixture(reverse=False)
    assert len(molecules) == 1200
    assert len(folds) == 3600
    assert len(targets) == 4800
    assert sum(int(row["confirmatory"]) for row in molecules) == 240
    assert (
        sum(
            row["point"] == "CONFIRMATORY_SENTINEL_MUST_REMAIN_OPAQUE"
            for row in targets
        )
        == 960
    )
    assert {name: array.shape for name, array in arrays.items()} == {
        "overlay_morgan_4096_packed.npy": (1200, 512),
        "maplight_morgan_count.npy": (1200, 1024),
        "maplight_avalon_count.npy": (1200, 1024),
        "maplight_erg.npy": (1200, 315),
        "maplight_rdkit_descriptors.npy": (1200, 200),
    }


def test_compiler_publishes_disjoint_full_width_capabilities(compiled) -> None:  # type: ignore[no-untyped-def]
    _root, _source, model, scorer, preflight = compiled
    assert preflight["status"] == "G2_7C_NO_FIT_PREFLIGHT_PASS"
    assert preflight["confirmatory_touch_excluded_molecules"] == {
        "PRIMARY_D032": 0,
        "THRESHOLD_0_55": 2,
        "THRESHOLD_0_50": 2,
        "TAUTOMER_MERGED": 2,
    }
    assert len(list((model / "targets").rglob("*.csv"))) == 240
    assert not any("truth" in path.name for path in model.rglob("*"))
    assert not any("target" in path.name for path in scorer.rglob("*"))
    assert {path.name for path in scorer.glob("*_truth.csv")} == {
        "stage_a_truth.csv",
        "stage_b_truth.csv",
        "stage_c_truth.csv",
    }
    model_manifest = compiler._load_json(model / "manifest.json")
    scorer_manifest = compiler._load_json(scorer / "manifest.json")
    assert model_manifest["molecules"] == 960
    assert scorer_manifest["truth_rows"] == 3840
    assert scorer_manifest["confirmatory_target_values_parsed"] == 0
    assert (
        model_manifest["accounting"]
        == scorer_manifest["accounting"]
        == (compiler._zero_accounting())
    )


def test_opposite_physical_orders_compile_byte_identically(tmp_path: Path) -> None:
    maps: list[dict[str, str]] = []
    source_receipts: list[str] = []
    for name, reverse in (("a", False), ("b", True)):
        source = driver.publish_source(root=tmp_path / name / "source", reverse=reverse)
        source_receipts.append(maplight.sha256_path(source / "manifest.json"))
        compiler.compile_capabilities(
            source_root=source,
            output_root=tmp_path / name / "capabilities",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
        )
        maps.append(_tree_map(tmp_path / name / "capabilities"))
    assert source_receipts[0] != source_receipts[1]
    assert maps[0] == maps[1]


def test_exact_duplicate_or_component_crossing_fails_closed(
    tmp_path: Path,
) -> None:
    source = driver.publish_source(root=tmp_path / "original", reverse=False)
    files, manifest = _mutable_source(source, tmp_path)
    rows = maplight._read_csv(source / "molecules.csv", compiler.MOLECULE_COLUMNS)
    assert (
        rows[0]["standardized_structure_hash"] == rows[1]["standardized_structure_hash"]
    )
    rows[1]["threshold_0_55_component_hash"] = "f" * 64
    files["molecules.csv"] = maplight.csv_bytes(compiler.MOLECULE_COLUMNS, rows)
    manifest["source_receipts"] = {
        name: maplight.sha256_bytes(value) for name, value in files.items()
    }
    tampered = maplight.publish_files(
        tmp_path / "tampered",
        {**files, "manifest.json": maplight.json_bytes(manifest)},
    )
    with pytest.raises(
        compiler.RobustnessExecutionCompilerError,
        match="derived overlay component differs|exact duplicate crosses",
    ):
        compiler.compile_capabilities(
            source_root=tampered,
            output_root=tmp_path / "must-not-publish",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
        )
    assert not (tmp_path / "must-not-publish").exists()


def test_overlay_fingerprints_are_reconstructed_not_trusted(tmp_path: Path) -> None:
    source = driver.publish_source(root=tmp_path / "original", reverse=False)
    files, manifest = _mutable_source(source, tmp_path)
    fingerprints = np.load(source / compiler.OVERLAY_FINGERPRINT_FILE)
    fingerprints[0] = 0
    files[compiler.OVERLAY_FINGERPRINT_FILE] = compiler._npy_bytes(fingerprints)
    manifest["source_receipts"] = {
        name: maplight.sha256_bytes(value) for name, value in files.items()
    }
    tampered = maplight.publish_files(
        tmp_path / "tampered-fingerprint",
        {**files, "manifest.json": maplight.json_bytes(manifest)},
    )
    with pytest.raises(
        compiler.RobustnessExecutionCompilerError,
        match="overlay fingerprint is empty|derived overlay component differs",
    ):
        compiler.compile_capabilities(
            source_root=tampered,
            output_root=tmp_path / "must-not-publish",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
        )
    assert not (tmp_path / "must-not-publish").exists()


def test_rdkit_overlay_adapter_uses_exact_4096_chiral_and_tautomer_rules() -> None:
    structures = {
        maplight.sha256_bytes(b"CC(=O)C"): "CC(=O)C",
        maplight.sha256_bytes(b"C=C(C)O"): "C=C(C)O",
        maplight.sha256_bytes(b"c1ccccc1"): "c1ccccc1",
    }
    packed_a, tautomers_a = compiler._rdkit_overlay_inputs(structures)
    packed_b, tautomers_b = compiler._rdkit_overlay_inputs(
        dict(reversed(list(structures.items())))
    )
    assert packed_a.shape == (3, 512)
    assert packed_a.dtype == np.uint8
    assert np.array_equal(packed_a, packed_b)
    assert tautomers_a == tautomers_b
    assert (
        tautomers_a[maplight.sha256_bytes(b"CC(=O)C")]
        == tautomers_a[maplight.sha256_bytes(b"C=C(C)O")]
    )


def test_confirmatory_structure_prefix_never_decodes_target_suffix() -> None:
    prefix = b"obs,molecule,row,file,1," + b"a" * 64 + b",CYP1A2,CCO,"
    values = compiler._csv_prefix(prefix + b"\xff\xfePOISONED_TARGET", 8)
    assert values[1] == "molecule"
    assert values[7] == "CCO"


def test_official_compiler_requires_exact_fixed_source_and_authorization(
    tmp_path: Path,
) -> None:
    source = driver.publish_source(root=tmp_path / "source", reverse=False)
    assert compiler.OFFICIAL_SOURCE_ROOT.name == (
        "g2-2c-maplight-development-source-v1"
    )
    with pytest.raises(
        compiler.RobustnessExecutionCompilerError, match="official source root differs"
    ):
        compiler.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "must-not-publish",
            mode="official",
            authorization=None,
            expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
        )


def test_support_is_endpoint_specific_not_endpoint_averaged(compiled) -> None:  # type: ignore[no-untyped-def]
    _root, _source, model, _scorer, _preflight = compiled
    folds = maplight._read_csv(model / "folds.csv", compiler.CAPABILITY_FOLD_COLUMNS)
    molecules = [
        {
            "molecule_id": row["molecule_id"],
            "confirmatory": "0",
        }
        for row in {row["molecule_id"]: row for row in folds}.values()
    ]
    fold_map = {
        (row["molecule_id"], int(row["repeat"]), row["group_id"]): int(
            row["outer_fold"]
        )
        for row in folds
    }
    targets = {
        (row["molecule_id"], endpoint): 5.0
        for row in molecules
        for endpoint in compiler.ENDPOINTS
        if endpoint != "CYP1A2"
    }
    preflight = compiler._preflight(molecules, targets, fold_map)
    assert "CYP1A2:development" in preflight["failures"]
    assert any(
        failure.startswith("PRIMARY_D032|CYP1A2|") for failure in preflight["failures"]
    )


def test_underpowered_source_publishes_no_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = driver.publish_source(root=tmp_path / "source", reverse=False)
    monkeypatch.setattr(
        compiler,
        "MINIMA",
        {
            "development_finite_targets_per_endpoint": 10_000,
            "outer_validation_targets_per_endpoint_repeat_fold": 75,
            "outer_training_targets_per_endpoint_repeat_fold": 400,
        },
    )
    with pytest.raises(compiler.RobustnessExecutionUnderpowered) as caught:
        compiler.compile_capabilities(
            source_root=source,
            output_root=tmp_path / "must-not-publish",
            mode="synthetic",
            expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
        )
    assert caught.value.preflight["status"] == "G2_7C_NO_FIT_UNDERPOWERED"
    assert not (tmp_path / "must-not-publish").exists()


@pytest.mark.parametrize(
    ("profile", "fits", "candidate", "checkpoints"),
    [
        ("full_retained", 720, "G2-7-M0-FULL", 1444),
        ("deletion_selected", 1020, "G2-7-M1-DROP-MORGAN", 2046),
    ],
)
def test_both_conditional_identity_paths_are_exact(
    compiled,  # type: ignore[no-untyped-def]
    tmp_path: Path,
    profile: str,
    fits: int,
    candidate: str,
    checkpoints: int,
) -> None:
    _root, _source, model, scorer, _preflight = compiled
    recorder = wrapper.LocalCheckpointRecorder()
    terminal = wrapper.run_no_fit_replay(
        model_capability_root=model,
        scorer_capability_root=scorer,
        work_root=tmp_path / "work",
        output_root=tmp_path / "terminal",
        selection_profile=profile,
        checkpoint=recorder,
    )
    manifest = compiler._load_json(terminal / "manifest.json")
    identities = compiler._load_json(terminal / "identity_summary.json")
    chronology = compiler._load_json(terminal / "chronology.json")
    assert manifest["model_double_invocations"] == fits
    assert manifest["selected_candidate"] == candidate
    assert identities["official_future_fit_identities"]["total"] == fits
    assert chronology["checkpoints_acknowledged"] == checkpoints
    assert chronology["numeric_truth_values_parsed"] == 0
    assert chronology["development_metric_evaluations"] == 0
    assert not (tmp_path / "work").exists()
    assert set(_tree_map(terminal)) == set(wrapper.TERMINAL_FILES)


def test_stage_scorer_cannot_open_before_matching_freeze(
    compiled,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    _root, _source, model, scorer, _preflight = compiled
    original = wrapper._open_stage_scorer
    observed: list[str] = []

    def guarded(*, scorer_root: Path, scorer_manifest, stage: str):  # type: ignore[no-untyped-def]
        assert (tmp_path / "work" / f"{stage}-freeze" / "manifest.json").is_file()
        observed.append(stage)
        return original(
            scorer_root=scorer_root,
            scorer_manifest=scorer_manifest,
            stage=stage,
        )

    monkeypatch.setattr(wrapper, "_open_stage_scorer", guarded)
    wrapper.run_no_fit_replay(
        model_capability_root=model,
        scorer_capability_root=scorer,
        work_root=tmp_path / "work",
        output_root=tmp_path / "terminal",
        selection_profile="deletion_selected",
        checkpoint=wrapper.LocalCheckpointRecorder(),
    )
    assert observed == ["stage_a", "stage_b", "stage_c"]


@pytest.mark.skipif(
    not LIVE_SUPERVISOR_RUNTIME,
    reason="requires the exact local G2-7C namespace runtime",
)
def test_supervisor_accepts_isolated_control_and_rejects_faults(tmp_path: Path) -> None:
    evidence = wrapper.exercise_supervisor_acceptance(work_root=tmp_path / "faults")
    success = evidence["success"]
    assert success["network_namespace_isolated"]
    assert success["gpu_environment_hidden"]
    assert success["warnings_observed"] == 0
    assert success["detached_children_observed"] == 0
    assert evidence["fail_stop_scenarios"] == {
        "wall": True,
        "cpu": True,
        "storage": True,
        "warning": True,
        "signal": True,
        "detached": True,
        "nonzero": True,
        "missing_checkpoint": True,
        "rss": True,
        "partial_publication": True,
    }
    assert evidence["restricted_roots_retained"] == 0


@pytest.mark.skipif(
    not LIVE_SUPERVISOR_RUNTIME,
    reason="requires the exact local G2-7C namespace runtime",
)
def test_supervisor_rejects_missing_checkpoint_and_cleans(tmp_path: Path) -> None:
    restricted = tmp_path / "missing-checkpoint" / "restricted"
    with pytest.raises(
        supervisor.ResourceSupervisorError, match="no resource checkpoint"
    ):
        supervisor.run_supervised(
            [sys.executable, "-c", "pass"],
            restricted_root=restricted,
            limits=supervisor.ResourceLimits(5, 5, 10_000_000, 1_000_000_000),
            poll_interval_seconds=0.02,
        )
    assert not restricted.exists()


@pytest.mark.skipif(
    not LIVE_SUPERVISOR_RUNTIME,
    reason="requires the exact local G2-7C namespace runtime",
)
def test_supervisor_rejects_simultaneous_rss_and_cleans(tmp_path: Path) -> None:
    restricted = tmp_path / "rss" / "restricted"
    own = supervisor._process_stat(os.getpid())
    assert own is not None
    command = wrapper._helper_command(
        "import time;m.resource_checkpoint('before:rss');x=bytearray(80000000);time.sleep(1)"
    )
    with pytest.raises(supervisor.ResourceSupervisorError, match="RSS limit"):
        supervisor.run_supervised(
            command,
            restricted_root=restricted,
            limits=supervisor.ResourceLimits(
                5, 5, 10_000_000, own.rss_bytes + 50_000_000
            ),
            poll_interval_seconds=0.02,
        )
    assert not restricted.exists()


def test_supervisor_static_policy_covers_every_frozen_limit() -> None:
    source = supervisor.SCRIPT.read_text(encoding="utf-8")
    for evidence in (
        "--unshare-net",
        "--dev",
        "PR_SET_CHILD_SUBREAPER",
        "os.wait4",
        "os.killpg",
        "st_blocks * 512",
        "simultaneous RSS limit exceeded",
        "warning or stderr output observed",
    ):
        assert evidence in source
    assert supervisor.POLL_INTERVAL_MAXIMUM == 1.0


def test_atomic_terminal_publication_refuses_replacement(
    compiled,
    tmp_path: Path,  # type: ignore[no-untyped-def]
) -> None:
    _root, _source, model, scorer, _preflight = compiled
    terminal = wrapper.run_no_fit_replay(
        model_capability_root=model,
        scorer_capability_root=scorer,
        work_root=tmp_path / "work-a",
        output_root=tmp_path / "terminal",
        selection_profile="full_retained",
        checkpoint=wrapper.LocalCheckpointRecorder(),
    )
    before = _tree_map(terminal)
    with pytest.raises(
        wrapper.RobustnessExecutionWrapperError, match="execution root exists"
    ):
        wrapper.run_no_fit_replay(
            model_capability_root=model,
            scorer_capability_root=scorer,
            work_root=tmp_path / "work-b",
            output_root=tmp_path / "terminal",
            selection_profile="full_retained",
            checkpoint=wrapper.LocalCheckpointRecorder(),
        )
    assert _tree_map(terminal) == before


def test_current_path_has_zero_fit_metric_claim_and_private_portal_authority() -> None:
    for path in (compiler.SCRIPT, wrapper.SCRIPT, supervisor.SCRIPT, driver.SCRIPT):
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in (
            "submission_name",
            "leaderboard_score",
            "leaderboard_rank",
            "remote_submission_id",
        ):
            assert forbidden not in text
    source = driver.SCRIPT.read_text(encoding="utf-8")
    assert '"real_catboost_fits": 0' in source
    assert '"development_metric_evaluations": 0' in source
    assert '"claim_authority": False' in source
