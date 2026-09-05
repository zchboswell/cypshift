"""Verify real calibration optimization and recovery with a cheap estimator double."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
    monkeypatch.syspath_prepend(str(root))
    # The model double tests checkpoint lifecycle, never model quality. Genuine
    # scipy.optimize.linprog remains in place for calibration tests in every CI.
    stub = types.ModuleType("catboost")

    class Estimator:
        fits = 0

        def __init__(self, **parameters: Any):
            self.parameters = parameters

        def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
            type(self).fits += 1
            self.mean = float(targets.mean())

        def predict(self, features: np.ndarray) -> np.ndarray:
            return self.mean + features[:, 0]

        def get_all_params(self) -> dict[str, Any]:
            return self.parameters

    stub.CatBoostRegressor = Estimator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "catboost", stub)
    spec = importlib.util.spec_from_file_location(
        "phase3_runner_test", root / "competition_runner.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs() -> tuple[Any, ...]:
    features = np.arange(16, dtype=float).reshape(8, 2)
    targets = np.linspace(1, 8, 8)
    return (
        features,
        targets,
        np.array([0, 1, 2, 3]),
        np.array([4, 5]),
        {
            "seed": 1,
            "runtime": "test-double",
            "implementation": "synthetic-v1",
            "molecule_ids": [f"fixture-{i}" for i in range(8)],
        },
    )


def test_affine_recovers_known_map_and_enforces_parameter_bounds(runner: Any) -> None:
    prediction = np.array([1.0, 2.0, 3.0, 6.0])
    truth = 1.1 * prediction + 0.1
    slope, intercept = runner.affine_fit(prediction, truth, truth)
    assert (slope, intercept) == pytest.approx((1.1, 0.1), abs=1e-8)
    unattainable = 2 * prediction + 1
    assert runner.affine_fit(prediction, unattainable, unattainable) == pytest.approx(
        (1.2, 0.25)
    )
    assert runner.affine_fit(prediction, -unattainable, -unattainable) == pytest.approx(
        (0.8, -0.25)
    )


def test_affine_uses_interval_loss_and_identity_wins_ties(runner: Any) -> None:
    prediction = np.array([1.0, 2.0, 3.0, 6.0])
    assert runner.affine_fit(prediction, prediction - 0.5, prediction + 0.5) == (1, 0)
    with pytest.raises(ValueError, match="Invalid"):
        runner.affine_fit(prediction, prediction + 1, prediction)
    with pytest.raises(ValueError, match="Invalid"):
        runner.affine_fit(prediction, prediction, np.full(4, np.nan))


def test_identical_checkpoint_reuses_fit_but_does_not_read_heldout_targets(
    runner: Any, tmp_path: Path
) -> None:
    args = list(_inputs())
    first, receipt = runner.cached_fit(tmp_path, *args)
    assert not receipt["reused"]
    args[1][4:] = np.nan  # Predictions cannot depend on non-training labels.
    second, reused = runner.cached_fit(tmp_path, *args)
    np.testing.assert_array_equal(first, second)
    assert reused["reused"]
    assert runner.CatBoostRegressor.fits == 1


@pytest.mark.parametrize(
    "changed", ["features", "targets", "train", "predict", "identity"]
)
def test_incompatible_fit_inputs_never_reuse_checkpoint(
    runner: Any, tmp_path: Path, changed: str
) -> None:
    args = list(_inputs())
    _, receipt = runner.cached_fit(tmp_path, *args)
    if changed == "features":
        args[0][0, 0] += 1
    elif changed == "targets":
        args[1][0] += 1
    elif changed == "train":
        args[2] = np.array([0, 1, 2])
    elif changed == "predict":
        args[3] = np.array([5, 4])
    else:
        args[4] = {**args[4], "runtime": "other-runtime"}
    _, changed_receipt = runner.cached_fit(tmp_path, *args)
    assert changed_receipt["key"] != receipt["key"]
    assert not changed_receipt["reused"]
    assert runner.CatBoostRegressor.fits == 2


def test_damaged_checkpoint_fails_without_fitting_or_overwriting(
    runner: Any, tmp_path: Path
) -> None:
    args = _inputs()
    _, receipt = runner.cached_fit(tmp_path, *args)
    prediction = tmp_path / receipt["key"] / "prediction.npy"
    prediction.write_bytes(b"damaged checkpoint")
    with pytest.raises(ValueError, match="Damaged"):
        runner.cached_fit(tmp_path, *args)
    assert prediction.read_bytes() == b"damaged checkpoint"
    assert runner.CatBoostRegressor.fits == 1


def test_interruption_before_receipt_publication_can_finish_same_fit(
    runner: Any, tmp_path: Path
) -> None:
    args = _inputs()
    expected, receipt = runner.cached_fit(tmp_path, *args)
    directory = tmp_path / receipt["key"]
    (directory / "receipt.json").unlink()
    (directory / "prediction.partial").write_bytes(b"incomplete write")
    resumed, resumed_receipt = runner.cached_fit(tmp_path, *args)
    np.testing.assert_array_equal(expected, resumed)
    assert not resumed_receipt["reused"]
    assert json.loads((directory / "receipt.json").read_text())["key"] == receipt["key"]
    assert runner.CatBoostRegressor.fits == 2


@pytest.mark.parametrize(
    "train,predict",
    [
        ([-1], [7]),  # Python aliases these rows; raw index intersection misses it.
        ([0, 0], [4]),
        ([0, 1], [1, 4]),
        ([0, 1], [8]),
    ],
)
def test_invalid_fit_membership_is_rejected_before_model_fit(
    runner: Any, tmp_path: Path, train: list[int], predict: list[int]
) -> None:
    args = list(_inputs())
    args[2], args[3] = np.array(train), np.array(predict)
    with pytest.raises(ValueError, match="indices|membership"):
        runner.cached_fit(tmp_path, *args)
    assert runner.CatBoostRegressor.fits == 0


def test_altered_receipt_input_identity_is_rejected(
    runner: Any, tmp_path: Path
) -> None:
    args = _inputs()
    _, receipt = runner.cached_fit(tmp_path, *args)
    path = tmp_path / receipt["key"] / "receipt.json"
    saved = json.loads(path.read_text())
    saved["inputs"]["runtime"] = "altered-runtime"
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="Damaged"):
        runner.cached_fit(tmp_path, *args)
    assert runner.CatBoostRegressor.fits == 1


def test_orphan_charge_is_frozen_once_and_finished_attempts_are_preserved(
    runner: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orphan = tmp_path / "fits" / "orphan"
    complete = tmp_path / "fits" / "complete"
    orphan.mkdir(parents=True)
    complete.mkdir()
    start = {"started_epoch_seconds": 100.0, "threads": 4}
    for directory in (orphan, complete):
        (directory / "fit-start-1.json").write_text(json.dumps(start))
    finished = complete / "fit-attempt-1.json"
    finished.write_text(json.dumps({"status": "complete", "cpu_core_hours": 0.25}))
    before = finished.read_bytes()
    monkeypatch.setattr(runner.time, "time", lambda: 1000.0)
    assert runner.freeze_interrupted_fits(tmp_path) == 1
    charged = orphan / "fit-attempt-1.json"
    frozen = charged.read_bytes()
    record = json.loads(frozen)
    assert record["status"] == "interrupted_unknown"
    assert record["cpu_core_hours"] == 1.0  # 900 seconds times four threads.
    assert runner.spent_cpu(tmp_path) == 1.25
    monkeypatch.setattr(runner.time, "time", lambda: 1000000.0)
    assert runner.freeze_interrupted_fits(tmp_path) == 0
    assert runner.spent_cpu(tmp_path) == 1.25
    assert charged.read_bytes() == frozen
    assert finished.read_bytes() == before


def test_recovery_cannot_freeze_a_fit_while_another_evaluator_holds_compute_lock(
    runner: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "compiled"
    source.mkdir()
    (source / "manifest.json").write_bytes(b"synthetic manifest")
    root = tmp_path / "program"
    orphan = root / "prior" / "fits" / "orphan"
    orphan.mkdir(parents=True)
    (orphan / "fit-start-1.json").write_text(
        json.dumps(
            {
                "started_epoch_seconds": 100.0,
                "threads": 4,
            }
        )
    )
    attempt = orphan / "fit-attempt-1.json"
    monkeypatch.setattr(runner.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        runner, "_evaluate_locked", lambda *args: {"frozen": attempt.exists()}
    )
    kwargs = {"expected_compiled_sha256": runner.digest(b"synthetic manifest")}
    with (root / "compute.lock").open("a") as other:
        runner.fcntl.flock(other, runner.fcntl.LOCK_EX | runner.fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            runner.evaluate(source, root / "next", **kwargs)
        assert not attempt.exists()
    assert runner.evaluate(source, root / "next", **kwargs) == {"frozen": True}
    assert runner.spent_cpu(root) == 1.0


def test_objective_change_cannot_reuse_mae_fit_or_automatic_rmse_parameters(
    runner: Any,
    tmp_path: Path,
) -> None:
    args = _inputs()
    _, mae = runner.cached_fit(tmp_path, *args)
    _, rmse = runner.cached_fit(tmp_path, *args, loss="RMSE")
    _, repeated = runner.cached_fit(tmp_path, *args, loss="RMSE")
    assert mae["key"] != rmse["key"]
    assert repeated["reused"] and runner.CatBoostRegressor.fits == 2
    assert mae["inputs"]["parameters"] == runner.PARAMETERS
    assert "learning_rate" not in mae["resolved_parameters"]
    assert rmse["inputs"]["parameters"] == rmse["resolved_parameters"]
    for name, value in {
        "loss_function": "RMSE",
        "learning_rate": 0.03,
        "iterations": 1000,
        "depth": 6,
    }.items():
        assert rmse["resolved_parameters"][name] == value
    with pytest.raises(ValueError, match="frozen"):
        runner.cached_fit(tmp_path, *args, loss="unexpected-objective")
    assert runner.CatBoostRegressor.fits == 2


def test_rmse_evaluation_cannot_claim_incumbent_eligibility_or_use_mae_csv_builder(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exercise the complete 80-cell orchestration with cheap estimators, while
    # isolating scoring: even a favorable within-objective result cannot grant release.
    source, output = tmp_path / "compiled", tmp_path / "rmse"
    source.mkdir()
    output.mkdir()
    (source / "manifest.json").write_bytes(b"synthetic compiled manifest")
    point = np.linspace(1, 2, 20)[:, None] + np.arange(4)[None, :] * 0.1
    data = types.SimpleNamespace(
        names=tuple(f"fixture-{i}" for i in range(20)),
        molecule_ids=tuple(f"fixture-{i}" for i in range(20)),
        groups=tuple(f"family-{i}" for i in range(20)),
        point=point,
        low=point.copy(),
        high=point.copy(),
        training_mask=np.ones((20, 4), dtype=bool),
        metric_mask=np.ones((20, 4), dtype=bool),
        legacy_features=np.arange(40).reshape(20, 2),
        receipts={"fixture": "synthetic"},
        report={"metric_targets_missing_bounds": [0] * 4},
    )
    monkeypatch.setattr(runner, "load_development", lambda path: data)
    monkeypatch.setattr(runner.platform, "python_version", lambda: "3.10.13")
    versions = {
        "catboost": "1.2.1",
        "numpy": "1.25.2",
        "rdkit": "2023.3.3",
        "scipy": "1.11.2",
    }
    monkeypatch.setattr(
        runner.importlib.metadata, "version", lambda name: versions[name]
    )
    monkeypatch.setattr(
        runner.subprocess, "check_output", lambda *args, **kwargs: "fixture-commit"
    )
    monkeypatch.setattr(
        runner, "direct_scores", lambda *args: {"synthetic": "not-science"}
    )
    monkeypatch.setattr(
        runner, "paired_family_difference", lambda *args: {"synthetic": "not-science"}
    )
    monkeypatch.setattr(
        runner,
        "release_decision",
        lambda *args: {"release_eligible_on_paired_metrics": True},
    )
    report = runner._evaluate_locked(source, output, 20260905, "RMSE", 10)
    assert report["candidate"] == "maplight-rmse-inner-oof-affine"
    assert report["fits"] == runner.CatBoostRegressor.fits == 80
    assert report["decision"]["within_objective_calibration"][
        "release_eligible_on_paired_metrics"
    ]
    assert not report["decision"]["release_eligible_on_paired_metrics"]
    assert not report["decision"]["promotion_metric_gate"]
    assert not report["decision"]["final_promotion"]
    assert "Never apply" in report["release_scope"]
    frozen = json.loads((output / "experiment.json").read_bytes())
    assert frozen["objective"] == frozen["parameters"]["loss_function"] == "RMSE"
    assert report["max_cpu_core_hours"] == 10
    assert {
        p["loss_function"] for p in report["resolved_parameter_variants"].values()
    } == {"RMSE"}
    with np.load(output / "oof.npz", allow_pickle=False) as archive:
        assert np.isfinite(archive["baseline"]).all()
        assert np.isfinite(archive["calibrated"]).all()
    # Even if a later comparison marks eligibility, candidate identity must stop
    # the legacy builder from applying RMSE calibration to historical MAE bytes.
    report["decision"]["release_eligible_on_paired_metrics"] = True
    (output / "result.json").write_text(json.dumps(report))
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "rmse_release_guard_test", scripts / "build_calibrated_competition_release.py"
    )
    assert spec is not None and spec.loader is not None
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    with pytest.raises(ValueError, match="complete eligible interim challenger"):
        release._validated_experiment(output)


def test_nonfit_cpu_and_interrupted_overhead_are_charged_once_without_double_count(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "run"
    output.mkdir()
    for attempt, cost in ((1, 1.0), (2, 0.5)):
        (output / f"fit-start-{attempt}.json").write_text(
            json.dumps({"started_epoch_seconds": 1000, "threads": 4})
        )
        (output / f"fit-attempt-{attempt}.json").write_text(
            json.dumps({"cpu_core_hours": cost})
        )
    (output / "run-overhead-start-3.json").write_text(
        json.dumps(
            {
                "pid": runner.os.getpid(),
                "started_epoch_seconds": 1000,
                "process_cpu_at_start": 100,
                "threads": 4,
                "fit_cpu_at_start": 1.0,
            }
        )
    )
    monkeypatch.setattr(runner.time, "process_time", lambda: 4600)
    monkeypatch.setattr(runner.time, "time", lambda: 2800)
    # Invocation CPU1.25 includes its .5 fit CPU; previous fit cost1 is separate.
    assert runner.spent_cpu(output) == 2.25
    assert runner.freeze_interrupted_fits(output) == 1
    frozen = output / "run-overhead-attempt-3.json"
    raw = frozen.read_bytes()
    # Conservative invocation wall1800*4=2 hours, less .5 already charged fit CPU.
    assert json.loads(raw)["cpu_core_hours"] == 1.5
    assert runner.spent_cpu(output) == 3.0
    monkeypatch.setattr(runner.time, "time", lambda: 1000000)
    assert runner.freeze_interrupted_fits(output) == 0
    assert frozen.read_bytes() == raw and runner.spent_cpu(output) == 3.0


def test_failed_and_resumed_nonfit_work_remains_in_budget(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [10.0]
    calls = [0]
    monkeypatch.setattr(runner.time, "process_time", lambda: clock[0])

    def scientific(*args: Any) -> dict[str, Any]:
        calls[0] += 1
        clock[0] += 3600 if calls[0] == 1 else 1800
        if calls[0] == 1:
            raise ValueError("Synthetic scoring failure without model fits")
        return {}

    monkeypatch.setattr(runner, "_evaluate_scientific", scientific)
    with pytest.raises(ValueError, match="scoring failure"):
        runner._evaluate_locked(tmp_path, tmp_path, 20260905, "RMSE", 10)
    assert runner.spent_cpu(tmp_path) == 1.0
    report = runner._evaluate_locked(tmp_path, tmp_path, 20260905, "RMSE", 10)
    assert report["invocation_cpu_core_hours"] == 0.5
    assert report["budget_accounted_fit_cpu_core_hours"] == 0
    assert report["budget_accounted_cpu_core_hours"] == 1.5
    assert runner.spent_cpu(tmp_path) == 1.5


def test_rmse_hard_limit_uses_remaining_cpu_under_shared_lock(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, output = tmp_path / "compiled", tmp_path / "run"
    source.mkdir()
    (source / "manifest.json").write_bytes(b"fixture")
    cap_calls = []
    monkeypatch.setattr(runner.time, "process_time", lambda: 3600.0)
    monkeypatch.setattr(runner.resource, "getrlimit", lambda key: (20000, 20000))

    def capture(key: int, limits: tuple[int, int]) -> None:
        # Observe lock exclusion while capturing the setter; never alter pytest limits.
        with (tmp_path / "compute.lock").open("a") as other:
            with pytest.raises(BlockingIOError):
                runner.fcntl.flock(other, runner.fcntl.LOCK_EX | runner.fcntl.LOCK_NB)
        cap_calls.append((key, limits))

    monkeypatch.setattr(runner.resource, "setrlimit", capture)
    monkeypatch.setattr(runner, "spent_cpu", lambda root: 8 if root == output else 995)
    monkeypatch.setattr(runner, "_evaluate_locked", lambda *args: {})
    runner.evaluate(
        source,
        output,
        expected_compiled_sha256=runner.digest(b"fixture"),
        loss="RMSE",
        max_cpu_core_hours=10,
    )
    assert cap_calls == [(runner.resource.RLIMIT_CPU, (10800, 10800))]
    with pytest.raises(RuntimeError, match="exhausted"):
        runner._limit_remaining_cpu(0)
    assert len(cap_calls) == 1
