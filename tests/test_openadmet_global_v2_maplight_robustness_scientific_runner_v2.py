from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
import types
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "maplight-fixed"
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
sys.path.insert(0, str(RESEARCH))
maplight = importlib.import_module("global_v2_maplight_runner")
compiler = importlib.import_module("global_v2_maplight_robustness_execution_compiler")
mechanics = importlib.import_module("global_v2_maplight_robustness_execution_wrapper")
scoring_compiler = importlib.import_module(
    "global_v2_maplight_robustness_scoring_compiler"
)
runner = importlib.import_module("global_v2_maplight_robustness_scientific_runner")
acceptance = importlib.import_module(
    "run_global_v2_maplight_robustness_execution_acceptance_v2"
)
official = importlib.import_module("run_global_v2_maplight_robustness_official_v2")
model_fixture = importlib.import_module(
    "run_global_v2_maplight_robustness_no_fit_acceptance"
)
scoring_fixture = importlib.import_module(
    "run_global_v2_maplight_robustness_scoring_capability_acceptance_v2"
)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_static_boundary_binds_corrected_contract_and_accepted_parents() -> None:
    parents = runner.authenticate_static_boundary()
    assert set(parents) == {"compiler", "scorer"}
    assert maplight.sha256_path(runner.CONTRACT) == runner.CONTRACT_SHA256
    assert maplight.sha256_path(runner.SCORING_ACCEPTANCE) == (
        runner.SCORING_ACCEPTANCE_SHA256
    )
    assert scoring_compiler.OUTPUT_COLUMNS == (
        "molecule_id",
        "endpoint",
        "standardized_structure_hash",
        "primary_component_hash",
        "source_file",
        "point",
        "low",
        "high",
    )
    for path, expected in runner.EXPECTED_ACCEPTED_SOURCES.items():
        assert maplight.sha256_path(path) == expected


def test_new_sources_never_import_or_name_rejected_g2_7b_implementation() -> None:
    rejected = {
        "global_v2_maplight_robustness_runner",
        "run_global_v2_maplight_robustness_synthetic",
    }
    for path in (runner.SCRIPT, acceptance.SCRIPT, official.SCRIPT):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert rejected.isdisjoint(imports)
        for rejected_name in rejected:
            assert rejected_name not in source


def test_exact_fit_topology_and_conditional_stage_c_are_unchanged(
    tmp_path: Path,
) -> None:
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
    assert source.index("_terminal_bytes") < source.index("_safe_cleanup(work)")
    assert source.index("_safe_cleanup(work)") < source.index("publish_files")


def test_catboost_constructor_is_exact_and_resolved_seed_is_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    class FakeRegressor:
        def __init__(self, **arguments: Any) -> None:
            observed.update(arguments)

        def fit(
            self, training: np.ndarray[Any, Any], targets: np.ndarray[Any, Any]
        ) -> None:
            assert training.shape == (8, 4)
            assert targets.shape == (8,)

        def get_all_params(self) -> dict[str, Any]:
            return {
                "loss_function": "MAE",
                "random_strength": 2,
                "random_seed": 2026082411,
                "task_type": "CPU",
            }

        def predict(self, prediction: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
            return np.arange(len(prediction), dtype=np.float64)

    monkeypatch.setitem(
        sys.modules,
        "catboost",
        types.SimpleNamespace(CatBoostRegressor=FakeRegressor),
    )
    identity = mechanics.FitIdentity(
        "stage_c",
        "G2-7-M1-DROP-MORGAN",
        2026082411,
        "PRIMARY_D032",
        "CYP1A2",
        0,
        0,
    )
    values, receipt = runner.real_catboost_predictor(
        identity,
        np.zeros((8, 4), dtype=np.float64),
        np.arange(8, dtype=np.float64),
        np.ones((3, 4), dtype=np.float64),
    )
    assert observed == {
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": 2026082411,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
    }
    assert values.tolist() == [0.0, 1.0, 2.0]
    assert compiler._is_sha(receipt)


def test_paired_component_bootstrap_is_deterministic_and_favors_lower_error() -> None:
    contexts = [
        (endpoint, repeat)
        for endpoint in compiler.ENDPOINTS
        for repeat in compiler.REPEATS
    ]
    candidate = {
        context: {f"component-{index:02d}": 0.2 + index / 1000 for index in range(20)}
        for context in contexts
    }
    baseline = {
        context: {f"component-{index:02d}": 0.4 + index / 1000 for index in range(20)}
        for context in contexts
    }
    first = runner.paired_component_bootstrap(
        candidate_errors=candidate,
        baseline_errors=baseline,
        accepted_replicates=100,
        maximum_attempts=1000,
    )
    second = runner.paired_component_bootstrap(
        candidate_errors=candidate,
        baseline_errors=baseline,
        accepted_replicates=100,
        maximum_attempts=1000,
    )
    assert first == second
    assert first["point_delta"] == pytest.approx(-0.2)
    assert first["upper_95"] < 0.0
    assert first["accepted_replicates"] == 100
    mismatched = {context: dict(values) for context, values in candidate.items()}
    mismatched[contexts[0]].pop("component-00")
    with pytest.raises(
        runner.RobustnessScientificRunnerError,
        match="paired bootstrap component rows differ",
    ):
        runner.paired_component_bootstrap(
            candidate_errors=mismatched,
            baseline_errors=baseline,
            accepted_replicates=100,
            maximum_attempts=1000,
        )


@pytest.fixture(scope="module")
def synthetic_capabilities(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("g2-7g-runner")
    source = model_fixture.publish_source(root=root / "source", reverse=False)
    model, central, preflight = compiler.compile_capabilities(
        source_root=source,
        output_root=root / "capabilities",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(compiler.SCRIPT),
    )
    direct = scoring_fixture._publish_scoring_source(
        root=root / "direct", reverse=False
    )
    scoring = scoring_compiler.compile_scoring_capability(
        direct_source_root=direct,
        model_capability_root=model,
        scorer_capability_root=central,
        output_root=root / "scoring",
        mode="synthetic",
        expected_compiler_sha256=maplight.sha256_path(scoring_compiler.SCRIPT),
    )
    assert preflight["status"] == "G2_7C_NO_FIT_PREFLIGHT_PASS"
    official_manifest = _load(model / "manifest.json")
    official_manifest["synthetic"] = False
    official_files = {
        path.relative_to(model).as_posix(): path.read_bytes()
        for path in sorted(model.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    official_files["manifest.json"] = maplight.json_bytes(official_manifest)
    official_shaped_model = maplight.publish_files(
        root / "official-shaped-model", official_files
    )
    runner._model_arrays_and_folds(official_shaped_model, synthetic=False)
    assert "_load_model_capability" not in inspect.getsource(
        runner._model_arrays_and_folds
    )
    return {
        "root": root,
        "model": model,
        "scoring": scoring,
        "official_shaped_model": official_shaped_model,
    }


def test_both_conditional_paths_freeze_exact_counts_without_formal_acceptance(
    synthetic_capabilities: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = synthetic_capabilities["root"]
    model = synthetic_capabilities["model"]
    scoring = synthetic_capabilities["scoring"]
    tutorial_calls = 0
    tutorial_metric = runner.tutorial_endpoint_st_rae

    def counted_tutorial_metric(*args: Any, **kwargs: Any) -> Any:
        nonlocal tutorial_calls
        tutorial_calls += 1
        return tutorial_metric(*args, **kwargs)

    monkeypatch.setattr(runner, "tutorial_endpoint_st_rae", counted_tutorial_metric)
    stage_a, stage_a_counts = runner.run_prediction_stage(
        stage="stage_a",
        selected_candidate=None,
        model_capability_root=model,
        output_root=root / "stage-a",
        predictor=runner.deterministic_test_predictor,
        checkpoint=lambda _label: None,
        synthetic=True,
    )
    assert stage_a_counts == {
        "fits": 540,
        "predictions": 103680,
        "training_target_values_opened": 414720,
    }

    full_baseline = acceptance._publish_baseline(
        root=root / "full-baseline",
        profile="full_retained",
        model_root=model,
        scoring_root=scoring,
    )
    full, full_selection = runner.select_stage_a_candidate(
        stage_a_root=stage_a,
        scoring_capability_root=scoring,
        baseline_terminal_root=full_baseline,
        model_capability_root=model,
        synthetic=True,
    )
    assert full == "G2-7-M0-FULL"
    full_stage_b, full_b_counts = runner.run_prediction_stage(
        stage="stage_b",
        selected_candidate=full,
        model_capability_root=model,
        output_root=root / "full-stage-b",
        predictor=runner.deterministic_test_predictor,
        checkpoint=lambda _label: None,
        synthetic=True,
    )
    full_terminal = runner.score_frozen_battery(
        selected_candidate=full,
        selection_evidence=full_selection,
        stage_a_root=stage_a,
        stage_b_root=full_stage_b,
        stage_c_root=None,
        scoring_capability_root=scoring,
        baseline_terminal_root=full_baseline,
        model_capability_root=model,
        output_root=root / "full-terminal",
        synthetic=True,
    )
    assert full_b_counts["fits"] == 180
    full_manifest = _load(full_terminal / "manifest.json")
    assert full_manifest["fit_counts"] == {
        "stage_a": 540,
        "stage_b": 180,
        "stage_c": 0,
    }
    assert tutorial_calls == 56
    assert full_manifest["tutorial_metric_calls"] == 56
    assert full_manifest["maximum_tutorial_metric_calls"] == 80

    tutorial_calls = 0

    deletion_stage_a, deletion_a_counts = runner.run_prediction_stage(
        stage="stage_a",
        selected_candidate=None,
        model_capability_root=model,
        output_root=root / "deletion-stage-a",
        predictor=runner.deterministic_test_predictor,
        checkpoint=lambda _label: None,
        synthetic=True,
        reverse_fit_order=True,
    )
    deletion_baseline = acceptance._publish_baseline(
        root=root / "deletion-baseline",
        profile="deletion_selected",
        model_root=model,
        scoring_root=scoring,
    )
    deletion, deletion_selection = runner.select_stage_a_candidate(
        stage_a_root=deletion_stage_a,
        scoring_capability_root=scoring,
        baseline_terminal_root=deletion_baseline,
        model_capability_root=model,
        synthetic=True,
    )
    assert deletion == "G2-7-M2-DROP-AVALON"
    deletion_stage_b, deletion_b_counts = runner.run_prediction_stage(
        stage="stage_b",
        selected_candidate=deletion,
        model_capability_root=model,
        output_root=root / "deletion-stage-b",
        predictor=runner.deterministic_test_predictor,
        checkpoint=lambda _label: None,
        synthetic=True,
    )
    deletion_stage_c, deletion_c_counts = runner.run_prediction_stage(
        stage="stage_c",
        selected_candidate=deletion,
        model_capability_root=model,
        output_root=root / "deletion-stage-c",
        predictor=runner.deterministic_test_predictor,
        checkpoint=lambda _label: None,
        synthetic=True,
    )
    deletion_terminal = runner.score_frozen_battery(
        selected_candidate=deletion,
        selection_evidence=deletion_selection,
        stage_a_root=deletion_stage_a,
        stage_b_root=deletion_stage_b,
        stage_c_root=deletion_stage_c,
        scoring_capability_root=scoring,
        baseline_terminal_root=deletion_baseline,
        model_capability_root=model,
        output_root=root / "deletion-terminal",
        synthetic=True,
    )
    assert deletion_a_counts["fits"] == 540
    assert deletion_b_counts["fits"] == 180
    assert deletion_c_counts["fits"] == 300
    manifest = _load(deletion_terminal / "manifest.json")
    assert manifest["fit_counts"] == {
        "stage_a": 540,
        "stage_b": 180,
        "stage_c": 300,
    }
    assert manifest["selection_tokens"] == 1
    assert manifest["runner_ups"] == 0
    assert manifest["row_level_values_retained"] == 0
    assert manifest["model_binaries_retained"] == 0
    assert tutorial_calls == 56
    assert manifest["tutorial_metric_calls"] == 56
    assert sum(full_manifest["fit_counts"].values()) + sum(
        manifest["fit_counts"].values()
    ) == 1740
    endpoints = set(compiler.ENDPOINTS)
    robustness = _load(deletion_terminal / "robustness.json")
    assert all(
        set(value["endpoint_component_mae"]) == endpoints
        and set(value["endpoint_component_mae_degradation"]) == endpoints
        for value in robustness["seed"]["values"].values()
    )
    assert all(
        set(value["endpoint_component_mae"]) == endpoints
        and set(value["endpoint_component_mae_degradation"]) == endpoints
        for value in robustness["grouping"]["values"].values()
    )
    assert set(robustness["duplicate"]["selected_endpoint_component_mae"]) == endpoints
    assert set(robustness["duplicate"]["full_endpoint_component_mae"]) == endpoints
    assert set(robustness["duplicate"]["selected_endpoint_change"]) == endpoints
    assert set(robustness["duplicate"]["full_endpoint_change"]) == endpoints
    assert set(robustness["influence"]["selected_endpoint_component_mae"]) == endpoints
    assert set(robustness["influence"]["full_endpoint_component_mae"]) == endpoints
    assert set(robustness["influence"]["selected_endpoint_change"]) == endpoints
    assert set(robustness["influence"]["selected_minus_full_endpoint"]) == endpoints
    assert all(
        set(value["endpoint_component_mae"]) == endpoints
        and set(value["endpoint_component_mae_improvement"]) == endpoints
        for value in robustness["clipping"]["diagnostics"].values()
    )
    missing_predictions = runner._baseline_predictions(
        deletion_baseline, synthetic=True, fold_map=runner._model_arrays_and_folds(
            model, synthetic=True
        )[2]
    )[1]
    missing_predictions.pop(next(iter(missing_predictions)))
    with pytest.raises(
        runner.RobustnessScientificRunnerError, match="paired rows differ"
    ):
        runner._matched_predictions(
            missing_predictions,
            truth=runner._scoring_truth(
                scoring,
                synthetic=True,
                model_capability_root=model,
                fold_map=runner._model_arrays_and_folds(model, synthetic=True)[2],
            )[1],
            fold_map=runner._model_arrays_and_folds(model, synthetic=True)[2],
            group="PRIMARY_D032",
        )
    with pytest.raises(
        runner.RobustnessScientificRunnerError,
        match="scientific terminal or claim authority differs",
    ):
        runner.score_frozen_battery(
            selected_candidate=deletion,
            selection_evidence=deletion_selection,
            stage_a_root=deletion_stage_a,
            stage_b_root=deletion_stage_b,
            stage_c_root=deletion_stage_c,
            scoring_capability_root=scoring,
            baseline_terminal_root=deletion_baseline,
            model_capability_root=model,
            output_root=root / "illegitimate-claim-terminal",
            synthetic=True,
            consumed_claim_sha256="0" * 64,
        )


def test_supervisor_starts_before_claim_consumption_and_official_access() -> None:
    outer = inspect.getsource(official.run_official_attempt)
    child = inspect.getsource(official._child)
    assert "run_supervised" in outer
    assert "_consume_claim" not in outer
    assert child.index("resource_checkpoint") < child.index("derive_consumed_claim")
    assert child.index("derive_consumed_claim") < child.index("_consume_claim")
    assert child.index("_consume_claim") < child.index("compile_capabilities")
    assert child.index("compile_capabilities") < child.index('stage="stage_a"')
    assert "writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent" in outer
    assert outer.index("run_supervised") < outer.index("_finalize_terminal")
    assert "observed = supervisor.run_supervised" in outer
    assert "PENDING_TERMINAL_ROOT" in child
    failure = inspect.getsource(official._failure_terminal)
    assert "accounting_complete" in failure
    assert "return terminal_root" not in failure
    assert official.LIMITS == acceptance.LIMITS
    assert official.OFFICIAL_ATTEMPT_ROOT == Path(
        "/home/zbos/cypshift-private/openadmet-2026/"
        "g2-7g-maplight-robustness-development-attempt-1"
    )
    assert not official.OFFICIAL_ATTEMPT_ROOT.exists()


def test_formal_acceptance_is_fixed_unrun_and_has_zero_authority() -> None:
    assert acceptance.FIXED_PARENT_ROOT == Path("/tmp/cypshift-g2-7g")
    assert acceptance.FIXED_WORK_ROOT == (
        Path("/tmp/cypshift-g2-7g/execution-acceptance-attempt-1")
    )
    assert not acceptance.FIXED_PARENT_ROOT.exists()
    assert not acceptance.ACCEPTANCE.exists()
    assert not acceptance.REJECTION.exists()
    child = inspect.getsource(acceptance._child)
    root = inspect.getsource(acceptance._execute_root)
    assert child.count("_execute_root(") == 2
    source = child + root
    assert '"full_retained"' in source
    assert '"deletion_selected"' in source
    assert "_real_catboost_controls" in source
    assert child.index("resource_checkpoint") < child.index(
        "authenticate_static_boundary"
    )
    assert "runner.runtime_identity()" not in child
    assert 'platform.python_version() == "3.12.3"' in child
    assert 'importlib.metadata.version("rdkit") == "2026.3.5"' in child
    terminal = inspect.getsource(acceptance._terminal)
    assert 'value["model_double_invocations"] == 3480' in terminal
    assert 'value["claims_created"] == 0' in terminal
    assert '"schema_version": ACCEPTANCE_SCHEMA' in terminal
    assert terminal.index("**child_value") < terminal.index(
        '"schema_version": ACCEPTANCE_SCHEMA'
    )
    cleanup = inspect.getsource(acceptance._cleanup_fixed_root)
    assert "_safe_cleanup(FIXED_WORK_ROOT)" in cleanup
    assert "_safe_cleanup(FIXED_PARENT_ROOT)" not in cleanup
    assert "FIXED_PARENT_ROOT.rmdir()" in cleanup
    assert acceptance._main(["alternate-root"]) == 2


def test_public_sources_contain_no_private_portal_result_fields() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (runner.SCRIPT, acceptance.SCRIPT, official.SCRIPT)
    )
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
    ):
        assert forbidden not in text
