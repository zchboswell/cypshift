from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))


def _module(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compiler = _module(
    "global_v2_g1_execution_compiler",
    "global_v2_g1_execution_compiler.py",
)
wrapper = _module(
    "global_v2_g1_execution_wrapper",
    "global_v2_g1_execution_wrapper.py",
)
synthetic = _module(
    "run_global_v2_g1_execution_synthetic",
    "run_global_v2_g1_execution_synthetic.py",
)
base = sys.modules["global_v2_maplight_runner"]


def _compile(root: Path, *, reverse: bool = False):  # type: ignore[no-untyped-def]
    source, features, folds = synthetic.publish_source(
        root=root / "source", reverse=reverse
    )
    baseline = synthetic.publish_baseline(
        root=root / "baseline", features=features, folds=folds
    )
    return compiler.compile_capabilities(
        source_root=source,
        baseline_terminal_root=baseline,
        output_root=root / "capabilities",
        expected_compiler_sha256=base.sha256_path(compiler.SCRIPT),
    )


def _byte_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): base.sha256_path(path)
        for path in root.rglob("*")
        if path.is_file()
    }


def _acceptance(path: Path) -> Path:
    accounting = {
        "blinded_test_files_opened": 0,
        "confirmatory_rows_kept_opaque": 352,
        "confirmatory_target_values_parsed": 0,
        "confirmatory_truth_values_opened": 0,
        "development_finite_targets": 999,
        "development_metric_evaluations": 0,
        "development_point_only_rows": 139,
        "development_rows_decoded": 1248,
        "development_tutorial_eligible_rows": 860,
        "development_tutorial_without_std_rows": 424,
        "external_records_acquired": 0,
        "historical_r3c_row_level_artifacts_opened": 0,
        "leaderboard_observations": 0,
        "live_uploads": 0,
        "official_baseline_prediction_rows_opened": 0,
        "official_features_opened": 0,
        "official_metric_evaluations": 0,
        "official_model_fits": 0,
        "official_predictions_generated": 0,
        "official_target_values_opened": 0,
        "submissions_created": 0,
        "synthetic_model_fits": 8820,
        "synthetic_tutorial_ma_st_rae_calls": 888,
        "tdi_files_opened": 0,
        "tutorial_ma_st_rae_calls": 0,
    }
    counts = {
        "future_tokens": 4,
        "inner_catboost_fits": 8640,
        "inner_raw_prediction_rows": 539136,
        "inner_seed_averaged_prediction_rows": 179712,
        "molecules": 312,
        "outer_catboost_fits": 180,
        "outer_raw_prediction_rows": 11232,
        "outer_seed_averaged_prediction_rows": 3744,
        "selection_tokens": 60,
        "tutorial_metric_calls": 888,
    }
    value = {
        "schema_version": (
            "cypshift.openadmet_cyp_2026.global_v2_g1_execution_synthetic_acceptance.v1"
        ),
        "status": "G2_3C_OFFICIAL_SHAPED_SYNTHETIC_ACCEPTED",
        "execution_contract_sha256": compiler.EXECUTION_CONTRACT_SHA256,
        "compiler_source_sha256": base.sha256_path(compiler.SCRIPT),
        "execution_wrapper_source_sha256": base.sha256_path(wrapper.SCRIPT),
        "acceptance_source_sha256": base.sha256_path(synthetic.SCRIPT),
        "accepted_g1_runner_source_sha256": base.sha256_path(wrapper.g1.SCRIPT),
        "runtime_lock_sha256": base.sha256_path(wrapper.g1.LOCK),
        "roots": 2,
        "second_source_physical_order_reversed": True,
        "relative_byte_maps_identical": True,
        "files_compared": 9,
        "combined_terminal_tree_sha256": "a" * 64,
        "runtime_probe_receipt_sha256": "b" * 64,
        "full_topology_model_fits_per_replay": 8820,
        "full_topology_model_fits_total": 17640,
        "real_runtime_probe_fits_total": 28,
        "runtime_probe_fits_per_root": 14,
        "sparse_point_and_tutorial_masks_distinct": True,
        "private_roots_retained": 0,
        "counts_per_replay": counts,
        "accounting_per_replay": accounting,
        "resource_bounds": {
            "maximum_concurrent_catboost_fits": 1,
            "thread_count_per_fit": 16,
            "maximum_wall_seconds": wrapper.MAXIMUM_WALL_SECONDS,
            "maximum_cpu_core_hours": wrapper.MAXIMUM_CPU_CORE_HOURS,
            "maximum_restricted_storage_bytes": (
                wrapper.MAXIMUM_RESTRICTED_STORAGE_BYTES
            ),
            "retry": False,
            "resume": False,
            "move": False,
            "overwrite": False,
        },
        "authority": dict(wrapper.g1.DENIED_AUTHORITY),
    }
    path.write_bytes(base.json_bytes(value))
    return path


def test_compiler_keeps_sparse_masks_distinct_and_confirmatory_opaque(
    tmp_path: Path,
) -> None:
    _model, _selector, _scorer, preflight = _compile(tmp_path)
    accounting = preflight["accounting"]
    assert preflight["status"] == "G2_3C_PREFLIGHT_PASS"
    assert accounting["development_finite_targets"] == 999
    assert accounting["development_tutorial_eligible_rows"] == 860
    assert accounting["development_point_only_rows"] == 139
    assert accounting["development_tutorial_without_std_rows"] == 424
    assert accounting["confirmatory_rows_kept_opaque"] == 352
    assert accounting["confirmatory_target_values_parsed"] == 0
    assert accounting["confirmatory_truth_values_opened"] == 0


def test_compiler_canonicalizes_reversed_physical_source_order(tmp_path: Path) -> None:
    _compile(tmp_path / "a", reverse=False)
    _compile(tmp_path / "b", reverse=True)
    assert _byte_map(tmp_path / "a" / "capabilities") == _byte_map(
        tmp_path / "b" / "capabilities"
    )


def test_tutorial_and_component_metrics_use_different_masks() -> None:
    truth = [
        {
            "molecule_id": "a",
            "endpoint": "CYP1A2",
            "similarity_component_hash": "0" * 64,
            "point_eligible": "true",
            "tutorial_eligible": "true",
            "point": "1",
            "low": "0.90000000000000002",
            "high": "1.1000000000000001",
        },
        {
            "molecule_id": "b",
            "endpoint": "CYP1A2",
            "similarity_component_hash": "1" * 64,
            "point_eligible": "true",
            "tutorial_eligible": "false",
            "point": "2",
            "low": "",
            "high": "",
        },
        {
            "molecule_id": "c",
            "endpoint": "CYP1A2",
            "similarity_component_hash": "2" * 64,
            "point_eligible": "true",
            "tutorial_eligible": "true",
            "point": "3",
            "low": "2.8999999999999999",
            "high": "3.1000000000000001",
        },
    ]
    predictions = {"a": 1.5, "b": 4.0, "c": 2.5}
    _tutorial, tutorial_rows = wrapper._tutorial_score(truth, predictions, "CYP1A2")
    _component, point_rows, components = wrapper._component_mae(truth, predictions)
    assert tutorial_rows == 2
    assert point_rows == 3
    assert components == 3


def test_full_model_double_topology_and_gate_enforcement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        wrapper,
        "_runtime_identity",
        lambda: {
            "platform": "Linux x86_64 CPU",
            "python": "3.10.13",
            "numpy": "1.25.2",
            "catboost": "1.2.1",
        },
    )
    model, selector, scorer, _preflight = _compile(tmp_path)
    terminal = wrapper.run_compiled_replay(
        model_capability_root=model,
        selector_capability_root=selector,
        scorer_capability_root=scorer,
        work_root=tmp_path / "execution",
        predictor=wrapper.deterministic_test_predictor,
    )
    manifest, _raw = base._load_json(terminal / "manifest.json")
    counts = manifest["counts"]
    assert manifest["status"] == "G2_3C_OFFICIAL_SHAPED_SYNTHETIC_REPLAY_COMPLETE"
    assert counts["inner_catboost_fits"] == 8640
    assert counts["outer_catboost_fits"] == 180
    assert counts["tutorial_metric_calls"] == 888
    assert manifest["accounting"]["synthetic_model_fits"] == 8820
    assert manifest["result"]["all_five_gates_pass"] is False
    assert all(manifest["accounting"][name] == 0 for name in wrapper.FORBIDDEN_COUNTERS)


def test_underpowered_source_fails_before_capability_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, features, folds = synthetic.publish_source(
        root=tmp_path / "source", reverse=False
    )
    baseline = synthetic.publish_baseline(
        root=tmp_path / "baseline", features=features, folds=folds
    )
    monkeypatch.setattr(
        compiler,
        "SYNTHETIC_MINIMA",
        {
            "development_finite_targets_per_endpoint": 10_000,
            "outer_validation_targets_per_endpoint_repeat_fold": 24,
            "inner_training_targets_per_endpoint_repeat_outer_inner": 120,
        },
    )
    output = tmp_path / "capabilities"
    with pytest.raises(compiler.MapLightExecutionUnderpowered) as raised:
        compiler.compile_capabilities(
            source_root=source,
            baseline_terminal_root=baseline,
            output_root=output,
            expected_compiler_sha256=base.sha256_path(compiler.SCRIPT),
        )
    assert raised.value.preflight["status"] == "G2_3_G1_UNDERPOWERED"
    assert not output.exists()


def test_consumed_claim_binds_exact_integrated_implementation() -> None:
    acceptance = wrapper.TRACKED_ACCEPTANCE
    assert base.sha256_path(acceptance) == (
        "87065e0cd15bbdccb0d1e8bafc1e0b3869988be6f18ad8cbc4bc23b0e2965f9e"
    )
    consumed = wrapper.derive_consumed_claim(
        tracked_claim_path=compiler.TRACKED_CLAIM,
        acceptance_path=acceptance,
    )
    assert consumed["status"] == "G2_3C_CLAIM_CONSUMED"
    assert consumed["future_official_compiler_source_sha256"] == base.sha256_path(
        compiler.SCRIPT
    )
    assert consumed["future_attempt_wrapper_source_sha256"] == base.sha256_path(
        wrapper.SCRIPT
    )
    assert consumed["future_official_shaped_synthetic_acceptance_sha256"] == (
        base.sha256_path(acceptance)
    )
    receipts = compiler._validate_consumed_claim(
        consumed, base.sha256_path(compiler.SCRIPT)
    )
    assert receipts["dataset_revision"] == "85f8b358d0a2056a98b990dd75d3b3ec9247862b"


def test_consumed_claim_rejects_relaxed_resource_bound(tmp_path: Path) -> None:
    acceptance = _acceptance(tmp_path / "acceptance.json")
    value, _raw = base._load_json(acceptance)
    value["resource_bounds"]["maximum_concurrent_catboost_fits"] = 2
    acceptance.write_bytes(base.json_bytes(value))
    with pytest.raises(wrapper.G1ExecutionWrapperError, match="acceptance differs"):
        wrapper.derive_consumed_claim(
            tracked_claim_path=compiler.TRACKED_CLAIM,
            acceptance_path=acceptance,
        )


def test_consumed_attempt_failure_is_terminal_and_non_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    acceptance = _acceptance(tmp_path / "acceptance.json")
    source = tmp_path / "source"
    baseline = tmp_path / "baseline"
    attempt = tmp_path / "attempt"
    source.mkdir()
    baseline.mkdir()
    monkeypatch.setattr(wrapper, "OFFICIAL_ATTEMPT_ROOT", attempt)
    monkeypatch.setattr(compiler, "OFFICIAL_SOURCE_ROOT", source)
    monkeypatch.setattr(compiler, "OFFICIAL_BASELINE_ROOT", baseline)
    monkeypatch.setattr(
        wrapper,
        "_runtime_identity",
        lambda: {
            "platform": "Linux x86_64 CPU",
            "python": "3.10.13",
            "numpy": "1.25.2",
            "catboost": "1.2.1",
        },
    )
    monkeypatch.setattr(
        wrapper.shutil,
        "disk_usage",
        lambda _path: type(
            "Usage", (), {"total": 100_000_000_000, "used": 0, "free": 100_000_000_000}
        )(),
    )

    def fail_compile(**_kwargs):  # type: ignore[no-untyped-def]
        raise wrapper.G1ExecutionWrapperError("injected terminal failure")

    monkeypatch.setattr(compiler, "compile_capabilities", fail_compile)
    terminal = wrapper.run_official_attempt(
        source_root=source,
        baseline_terminal_root=baseline,
        attempt_root=attempt,
        acceptance_path=acceptance,
    )
    manifest, _raw = base._load_json(terminal / "manifest.json")
    assert manifest["status"] == "G2_3_G1_FAILED"
    assert {path.name for path in attempt.iterdir()} == {
        "attempt_claim.json",
        "receipt",
        "terminal",
    }
    with pytest.raises(wrapper.G1ExecutionWrapperError, match="unavailable"):
        wrapper.run_official_attempt(
            source_root=source,
            baseline_terminal_root=baseline,
            attempt_root=attempt,
            acceptance_path=acceptance,
        )
