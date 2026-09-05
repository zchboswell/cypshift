"""Synthetic family, payload, matched-control and subprocess budget boundaries."""

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
    stub = types.ModuleType("catboost")
    stub.CatBoostRegressor = object
    monkeypatch.setitem(sys.modules, "catboost", stub)
    spec = importlib.util.spec_from_file_location(
        "mlp_runner_test", root / "competition_mlp_runner.py"
    )
    module = importlib.util.module_from_spec(spec)
    before = {
        name: value
        for name, value in sys.modules.items()
        if name.startswith("competition_")
    }
    spec.loader.exec_module(module)
    try:
        yield module
    finally:
        for name in list(sys.modules):
            if name.startswith("competition_") and name not in before:
                sys.modules.pop(name, None)
        sys.modules.update(before)


def fixture_data(n: int = 100) -> types.SimpleNamespace:
    point = np.tile(np.linspace(3, 7, n)[:, None], (1, 4))
    return types.SimpleNamespace(
        point=point,
        low=point - 0.1,
        high=point + 0.1,
        training_mask=np.ones((n, 4), dtype=bool),
        metric_mask=np.ones((n, 4), dtype=bool),
        names=tuple(f"molecule-{i}" for i in range(n)),
        molecule_ids=tuple(f"id-{i}" for i in range(n)),
        groups=tuple(f"family-{i // 2}" for i in range(n)),
    )


def test_training_only_transforms_and_whole_bundle_donors(runner: Any) -> None:
    n = 12
    x = np.zeros((n, 4296))
    x[:, 4096:] = np.arange(n)[:, None]
    x[:8, -1] = np.nan  # All-missing TRAINING column has explicit neutral transform.
    point = np.arange(n * 4, dtype=float).reshape(n, 4)
    mask = np.ones_like(point, dtype=bool)
    aux_mask = mask.copy()
    aux_mask[np.arange(n), np.arange(n) % 4] = False
    auxiliary = point + 100
    auxiliary[~aux_mask] = np.nan
    train, predict, stop = np.arange(8), np.arange(10, 12), np.arange(8, 10)
    args = (
        x,
        point,
        mask,
        auxiliary,
        aux_mask,
        train,
        predict,
        stop,
        "shuffled_aux",
        44,
    )
    arrays, stats = runner.prepare_arrays(*args)
    assert np.isfinite(arrays["train_aux_y"]).all()
    donors = np.asarray(stats["auxiliary_donor_indices"])
    assert set(donors) == set(train)
    np.testing.assert_array_equal(arrays["train_aux_mask"], aux_mask[donors])
    assert stats["descriptor_center"][-1] == 0 and stats["descriptor_scale"][-1] == 1
    # Poison all held-out response and descriptor values; training payload stays exact.
    x[8:, 4096:] = 1e20
    point[8:] = -999
    auxiliary[8:] = 1e15
    changed, changed_stats = runner.prepare_arrays(*args)
    assert stats == changed_stats
    for key in ("train_x", "train_direct_y", "train_aux_y", "train_aux_mask"):
        np.testing.assert_array_equal(arrays[key], changed[key])
    # The permutation does not independently move direct targets.
    np.testing.assert_array_equal(
        arrays["train_direct_y"], point[train].astype(np.float32)
    )


def test_morgan_only_ignores_extreme_descriptor_poison_and_preserves_default(
    runner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture_data(12)
    data.raw_smiles = tuple("CC" for _ in range(12))
    data.legacy_features = np.zeros((12, 2563), dtype=np.float64)
    data.legacy_features[:, 2363:] = np.arange(12)[:, None]
    bits = np.zeros((12, 4096), dtype=np.uint8)
    bits[np.arange(12), np.arange(12)] = 1
    monkeypatch.setattr(runner, "featurize_binary_morgan", lambda _: bits.copy())
    legacy = runner.build_features(data)
    np.testing.assert_array_equal(legacy[:, :4096], bits)
    np.testing.assert_array_equal(legacy[:, 4096:], data.legacy_features[:, 2363:])
    before = runner.build_features(data, "morgan_only")
    data.legacy_features[:, 2396] = 1e300  # Ipc's original descriptor index33.
    data.legacy_features[0, 2363:] = np.nan
    after = runner.build_features(data, "morgan_only")
    np.testing.assert_array_equal(before, after)
    np.testing.assert_array_equal(after[:, :4096], bits)
    assert after.shape == (12, 4296) and np.all(after[:, 4096:] == 0)
    prepared, transforms = runner.prepare_arrays(
        after,
        data.point,
        data.training_mask,
        data.point,
        data.training_mask,
        np.arange(8),
        np.arange(8, 12),
        None,
        "direct",
        1,
    )
    assert np.all(prepared["train_x"][:, 4096:] == 0)
    assert np.all(prepared["predict_x"][:, 4096:] == 0)
    assert transforms["descriptor_center"] == [0.0] * 200
    assert transforms["descriptor_scale"] == [1.0] * 200
    assert runner.build_features(data)[1, 4129] == 1e300
    assert runner.recipe_path() != runner.recipe_path("morgan_only")


def test_exact_105_joint_fits_family_containment_and_fresh_refits(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = fixture_data()
    outer, inner = runner.balanced_nested_folds(data.groups, data.training_mask)
    calls = []

    def fit(**kw: Any) -> tuple[np.ndarray, dict[str, Any]]:
        calls.append(kw)
        train, held = kw["train"], kw["predict"]
        assert not {data.groups[i] for i in train} & {data.groups[i] for i in held}
        assert np.all(outer[train] != kw["outer"])
        if kw["role"] == "outer":
            np.testing.assert_array_equal(train, np.flatnonzero(outer != kw["outer"]))
            assert kw["epochs"] == 2
        elif kw["role"] == "refit":
            np.testing.assert_array_equal(
                train,
                np.flatnonzero(
                    (outer != kw["outer"]) & (inner[kw["outer"]] != kw["inner"])
                ),
            )
            assert kw["identity"]["stopping_receipt"]["selected_epoch"] == 2
        else:
            assert kw["epochs"] == 200
            assert np.all(inner[kw["outer"], train] != kw["inner"])
            assert np.all(inner[kw["outer"], held] != kw["inner"])
        return np.full((len(held), 4), 4.5), {
            "selected_epoch": 2,
            "initial_state_sha256": "same-init",
            "batch_order_epoch_sha256": ["epoch1", "epoch2"],
            "path": "/synthetic/receipt",
            "sha256": "fixture",
        }

    monkeypatch.setattr(runner, "affine_fit", lambda *args: (1.0, 0.0))
    monkeypatch.setattr(runner, "direct_scores", lambda *args: {"fixture": True})
    monkeypatch.setattr(
        runner, "paired_family_difference", lambda *args: {"fixture": True}
    )
    result = runner.evaluate_arrays(
        data,
        np.zeros((100, 4296)),
        data.point,
        data.training_mask,
        tmp_path,
        20260905,
        fit,
    )
    assert len(calls) == result["completed_fits"] == 105
    assert sum(c["role"] == "stop" for c in calls) == 45
    assert sum(c["role"] == "refit" for c in calls) == 45
    assert sum(c["role"] == "outer" for c in calls) == 15
    assert len(result["calibrations"]) == 60
    assert not result["release_eligible"]
    for spec in result["oof"].values():
        assert runner.read_array(spec).shape == (100, 4)


def test_matched_initialization_is_enforced(
    runner: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture_data()
    monkeypatch.setattr(runner, "affine_fit", lambda *args: (1.0, 0.0))

    def bad_fit(**kw: Any) -> tuple[np.ndarray, dict[str, Any]]:
        return np.full((len(kw["predict"]), 4), 4.0), {
            "selected_epoch": 1,
            "initial_state_sha256": kw["arm"],
            "batch_order_epoch_sha256": ["same"],
        }

    with pytest.raises(ValueError, match="Matched initialization"):
        runner.evaluate_arrays(
            data,
            np.zeros((100, 4296)),
            data.point,
            data.training_mask,
            tmp_path,
            20260905,
            bad_fit,
        )


def test_array_receipt_rejects_tampering(runner: Any, tmp_path: Path) -> None:
    spec = runner.array_file(tmp_path / "array.npy", np.ones((2, 4), np.float32))
    with open(spec["path"], "ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ValueError, match="hash differs"):
        runner.read_array(spec)


def test_failed_child_cpu_and_parent_overhead_are_charged_once(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, output = tmp_path, tmp_path / "run"
    output.mkdir()
    monkeypatch.setattr(runner.Budget, "limit_parent", lambda self: None)
    # A real short child checks accounting, but no hard limits change in pytest.
    with (root / "compute.lock").open("w") as lock:
        budget = runner.Budget(root, output, lock.fileno())
        cell = output / "fits" / "failed"
        cell.mkdir(parents=True)
        command = [
            sys.executable,
            "-c",
            "import time; until=time.process_time()+.06\nwhile time.process_time()<until: pass\nraise SystemExit(4)",
        ]
        with pytest.raises(RuntimeError, match="exited 4"):
            budget.run(command, cell)
        report = budget.finish("failed")
    fit = json.loads((cell / "fit-attempt-0.json").read_bytes())
    assert fit["status"] == "failed" and fit["cpu_core_hours"] * 3600 >= 0.05
    overhead = json.loads((output / "run-overhead-attempt-0.json").read_bytes())
    assert runner.spent_cpu(root) == pytest.approx(
        fit["cpu_core_hours"] + overhead["cpu_core_hours"]
    )
    assert report["invocation_cpu_core_hours"] == pytest.approx(runner.spent_cpu(root))
    assert runner.freeze_interrupted_fits(root) == 0


def test_parent_limit_uses_remaining_cumulative_budget_without_real_limit(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "run"
    output.mkdir()
    budget = runner.Budget(tmp_path, output, 0)
    calls = []
    monkeypatch.setattr(budget, "remaining", lambda: (100.0, 20.0))
    monkeypatch.setattr(runner.resource, "getrlimit", lambda key: (-1, -1))
    monkeypatch.setattr(runner.resource, "setrlimit", lambda *args: calls.append(args))
    budget.limit_parent()
    assert len(calls) == 1 and calls[0][1][0] == calls[0][1][1]
    assert abs(calls[0][1][0] - (runner.time.process_time() + 20)) < 2
    budget.finish("synthetic")


def test_timeout_kills_and_reaps_child_and_preserves_attempt(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "run"
    output.mkdir()
    monkeypatch.setattr(runner.Budget, "limit_parent", lambda self: None)
    with (tmp_path / "lock").open("w") as lock:
        budget = runner.Budget(tmp_path, output, lock.fileno())
        monkeypatch.setattr(budget, "remaining", lambda: (0.08, 10.0))
        cell = output / "cell"
        cell.mkdir()
        with pytest.raises((RuntimeError, runner.subprocess.TimeoutExpired)):
            budget.run([sys.executable, "-c", "import time; time.sleep(5)"], cell)
        report = budget.finish("failed")
    attempt = json.loads((cell / "fit-attempt-0.json").read_bytes())
    assert attempt["status"] == "failed"
    assert report["occupied_wall_seconds"] < 2
    assert runner.freeze_interrupted_fits(tmp_path) == 0


@pytest.mark.parametrize("parity_error", [0.0, 0.001])
def test_primitive_worker_receipt_boundary(
    runner: Any,
    tmp_path: Path,
    parity_error: float,
) -> None:
    data = fixture_data(12)
    worker = tmp_path / "worker.py"
    worker.write_text("# synthetic worker artifact\n")
    hyper = json.loads(runner.RECIPE.read_bytes())["hyperparameters"]
    observed = []

    class FakeBudget:
        def run(self, command: list[str], directory: Path) -> None:
            request_path = Path(command[3])
            request = json.loads(request_path.read_bytes())
            observed.append(request)
            assert request["schema"] == "cypshift.mlp.fit.v1"
            assert request["hyperparameters"]["output_dim"] == 8
            assert request["hyperparameters"]["aux_weight"] == 0
            assert set(request["files"]) == {
                "train_x",
                "train_direct_y",
                "train_direct_mask",
                "train_aux_y",
                "train_aux_mask",
                "predict_x",
            }
            out = Path(command[-1])
            out.mkdir()
            checkpoint = out / "checkpoint.pt"
            checkpoint.write_bytes(b"synthetic checkpoint")
            spec = runner.array_file(
                out / "predictions.npy", np.full((2, 4), 4.0, np.float32)
            )
            receipt = {
                "schema": "cypshift.mlp.fit_receipt.v1",
                "status": "complete",
                "worker_sha256": request["worker_sha256"],
                "runtime_receipt_sha256": request["runtime_receipt"]["sha256"],
                "identity": request["identity"],
                "arm": request["arm"],
                "mode": request["mode"],
                "hyperparameters": request["hyperparameters"],
                "request_sha256": runner.file_sha(request_path),
                "selected_epoch": 2,
                "finite_loss": True,
                "checkpoint": {
                    "path": str(checkpoint),
                    "sha256": runner.file_sha(checkpoint),
                },
                "predictions": spec,
                "initial_state_sha256": "same",
                "batch_order_epoch_sha256": ["e1", "e2"],
                "reload_parity": {
                    "maximum_absolute_error": parity_error,
                    "atol": 1e-6,
                    "rtol": 1e-6,
                    "model_and_optimizer_state_exact": True,
                },
            }
            (out / "receipt.json").write_bytes(runner.canonical(receipt))

    def call() -> Any:
        return runner.run_fit(
            tmp_path / "run",
            worker,
            Path(sys.executable),
            {"path": "/synthetic/runtime", "sha256": "synthetic"},
            data,
            np.zeros((12, 4296)),
            data.point,
            data.training_mask,
            np.arange(8),
            np.arange(10, 12),
            None,
            "direct",
            20260905,
            0,
            0,
            "refit",
            2,
            {"fixture": True},
            hyper,
            FakeBudget(),
        )

    if parity_error:
        with pytest.raises(ValueError, match="authentication/fit check"):
            call()
    else:
        prediction, receipt = call()
        assert prediction.dtype == np.float64 and receipt["selected_epoch"] == 2
    assert len(observed) == 1


def test_failed_attempt_retries_share_seed_allowance(
    runner: Any, tmp_path: Path
) -> None:
    first = tmp_path / "first"
    first.mkdir()
    (first / "run-overhead-start-0.json").write_bytes(
        runner.canonical(
            {
                "mlp_seed": 20260905,
                "started_epoch_seconds": 1,
                "threads": 24,
                "pid": -1,
                "process_cpu_at_start": 0,
                "fit_cpu_at_start": 0,
            }
        )
    )
    (first / "run-overhead-attempt-0.json").write_bytes(
        runner.canonical({"cpu_core_hours": 2.0})
    )
    (first / "resources.json").write_bytes(
        runner.canonical({"occupied_wall_seconds": 300.0})
    )
    second = tmp_path / "second"
    second.mkdir()
    budget = runner.Budget(tmp_path, second, 0, seed=20260905)
    assert budget.allowance == 8 and budget.wall_allowance == 3300
    budget.finish("synthetic")


def test_representation_retry_allowances_are_distinct_but_program_cost_is_shared(
    runner: Any, tmp_path: Path
) -> None:
    for name, mode, cost, wall in (
        ("legacy", None, 2.0, 300.0),
        ("morgan", "morgan_only", 1.0, 120.0),
    ):
        directory = tmp_path / name
        directory.mkdir()
        identity = {"mlp_seed": 20260905}
        if mode is not None:
            identity["mlp_feature_mode"] = mode
        (directory / "run-overhead-start-0.json").write_bytes(
            runner.canonical(identity)
        )
        (directory / "run-overhead-attempt-0.json").write_bytes(
            runner.canonical({"cpu_core_hours": cost})
        )
        (directory / "resources.json").write_bytes(
            runner.canonical({"occupied_wall_seconds": wall})
        )
    output = tmp_path / "morgan-retry"
    output.mkdir()
    budget = runner.Budget(tmp_path, output, 0, 20260905, "morgan_only")
    assert (
        budget.previous == 3 and budget.allowance == 9 and budget.wall_allowance == 3480
    )
    assert json.loads(budget.start.read_bytes())["mlp_feature_mode"] == "morgan_only"
    budget.finish("synthetic")


def test_busy_descendant_timeout_charges_unknown_cpu_and_releases_group_lock(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "run"
    output.mkdir()
    monkeypatch.setattr(runner.Budget, "limit_parent", lambda self: None)
    lock_path = tmp_path / "compute.lock"
    # The worker inherits the lock and spawns a CPU-busy descendant. If the
    # timeout wrapper dies first, that descendant's CPU need not reach wait4.
    script = tmp_path / "busy_parent.py"
    script.write_text(
        "import os, subprocess, sys\n"
        "print(os.getpgrp(), flush=True)\n"
        'child = subprocess.Popen([sys.executable, "-c", "while True: pass"])\n'
        "child.wait()\n"
    )
    with lock_path.open("w") as lock:
        runner.fcntl.flock(lock, runner.fcntl.LOCK_EX)
        budget = runner.Budget(tmp_path, output, lock.fileno(), seed=20260905)
        budget.wall_allowance = 0.3
        cell = output / "cell"
        cell.mkdir()
        with pytest.raises((RuntimeError, runner.subprocess.TimeoutExpired)):
            budget.run([sys.executable, str(script)], cell)
        attempt = json.loads((cell / "fit-attempt-0.json").read_bytes())
        assert attempt["uncertain_termination"]
        assert attempt["cpu_core_hours"] * 3600 >= attempt["wall_seconds"] * 24
        assert budget.uncertain_cpu_surcharge > 0
        # Restore only synthetic wall allowance to inspect remaining CPU charge.
        budget.wall_allowance = 3600
        remaining = budget.remaining()[1]
        actual_delta = runner.cpu_seconds() - budget.cpu_start
        assert remaining == pytest.approx(
            36000 - actual_delta - budget.uncertain_cpu_surcharge, abs=0.01
        )
        report = budget.finish("failed")
    group = int((cell / "worker.log").read_text().splitlines()[0])
    # SIGKILL can briefly leave orphan zombies, which consume no CPU and hold no
    # file descriptors. No live process in the worker group may survive.
    live = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if int(fields[2]) == group and fields[0] != "Z":
                live.append(entry.name)
    assert live == []
    with lock_path.open("a") as lock:
        runner.fcntl.flock(lock, runner.fcntl.LOCK_EX | runner.fcntl.LOCK_NB)
    assert runner.spent_cpu(tmp_path) == pytest.approx(
        report["invocation_cpu_core_hours"]
    )
    assert (
        report["uncertainty_surcharge_cpu_seconds"]
        == attempt["uncertainty_surcharge_cpu_seconds"]
    )
    retry = tmp_path / "retry"
    retry.mkdir()
    retry_budget = runner.Budget(tmp_path, retry, 0, seed=20260905)
    assert retry_budget.allowance == pytest.approx(
        10 - report["invocation_cpu_core_hours"]
    )
    retry_budget.finish("synthetic")
