"""Synthetic boundary and recovery checks for the bounded SVR evaluator."""

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
    # Shared runner helpers import CatBoost, but these tests execute no CatBoost fits.
    stub = types.ModuleType("catboost")
    stub.CatBoostRegressor = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "catboost", stub)
    spec = importlib.util.spec_from_file_location(
        "svr_runner_test", root / "competition_svr_runner.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data() -> types.SimpleNamespace:
    point = np.tile(np.arange(20, dtype=float)[:, None], (1, 4))
    return types.SimpleNamespace(
        names=tuple(f"molecule-{i}" for i in range(20)),
        molecule_ids=tuple(f"molecule-{i}" for i in range(20)),
        groups=tuple(f"family-{i}" for i in range(20)),
        point=point,
        low=point.copy(),
        high=point.copy(),
        training_mask=np.ones((20, 4), dtype=bool),
        receipts={"synthetic": "source"},
    )


def test_cached_cell_preserves_holdout_and_resumes_only_complete_matching_inputs(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data()
    outer, inner = runner.balanced_nested_folds(data.groups, data.training_mask)
    selected_training = np.flatnonzero(outer != 0)
    fit_calls = []

    def select(
        kernel: np.ndarray,
        point: np.ndarray,
        low: np.ndarray,
        high: np.ndarray,
        mask: np.ndarray,
        folds: np.ndarray,
    ) -> tuple[float, dict[float, np.ndarray]]:
        np.testing.assert_array_equal(point, data.point[selected_training, 0])
        fit_calls.append("inner")
        return 1.0, {1.0: point + 0.1, 10.0: point + 0.2}

    class Estimator:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def fit(self, kernel: np.ndarray, point: np.ndarray) -> None:
            np.testing.assert_array_equal(point, data.point[selected_training, 0])
            fit_calls.append("outer")

        def predict(self, kernel: np.ndarray) -> np.ndarray:
            return np.full(len(kernel), 3.0)

    monkeypatch.setattr(runner, "inner_select_c", select)
    monkeypatch.setattr(runner, "SVR", Estimator)
    output = tmp_path / "experiment"
    first = runner.cached_cell(
        output, np.eye(20), data, outer, inner, 0, 0, {"fixture": 1}
    )
    assert fit_calls == ["inner", "outer"] and first[2]["reused"] is False
    # Held-out numeric targets are absent from both fitting and cache identities.
    data.point[outer == 0, 0] = 99999
    second = runner.cached_cell(
        output, np.eye(20), data, outer, inner, 0, 0, {"fixture": 1}
    )
    np.testing.assert_array_equal(first[0], second[0])
    assert fit_calls == ["inner", "outer"] and second[2]["reused"] is True
    assert len(list(output.rglob("fit-attempt-*.json"))) == 1
    prediction = output / "cells" / first[2]["key"] / "predictions.npz"
    prediction.write_bytes(prediction.read_bytes() + b"damaged")
    with pytest.raises(ValueError, match="Damaged cell"):
        runner.cached_cell(output, np.eye(20), data, outer, inner, 0, 0, {"fixture": 1})
    assert fit_calls == ["inner", "outer"]


@pytest.mark.parametrize("boundary", ["outer", "inner"])
def test_family_crossings_fail_before_any_cell_attempt(
    runner: Any,
    tmp_path: Path,
    boundary: str,
) -> None:
    data = _data()
    outer, inner = runner.balanced_nested_folds(data.groups, data.training_mask)
    groups = list(data.groups)
    train = np.flatnonzero(outer != 0)
    left = int(train[0])
    if boundary == "outer":
        right = int(np.flatnonzero(outer == 0)[0])
    else:
        right = int(next(i for i in train if inner[0, i] != inner[0, left]))
    groups[right] = groups[left]
    data.groups = tuple(groups)
    with pytest.raises(ValueError, match=f"Family crosses {boundary}"):
        runner.cached_cell(
            tmp_path / "experiment", np.eye(20), data, outer, inner, 0, 0, {}
        )
    assert not list(tmp_path.rglob("fit-start-*.json"))


def test_original_baseline_authenticates_population_and_public_receipts(
    runner: Any,
    tmp_path: Path,
) -> None:
    data = _data()
    outer, inner = runner.balanced_nested_folds(data.groups, data.training_mask)
    experiment = {
        "source_receipts": data.receipts,
        "seed": runner.SEED,
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer": outer.tolist(),
        "inner": inner.tolist(),
    }
    experiment_raw = runner.canonical(experiment)
    oof_raw = runner._npz(
        {
            "baseline": data.point + 0.2,
            "calibrated": data.point + 0.1,
            "names": np.asarray(data.names),
            "groups": np.asarray(data.groups),
            "outer": outer,
            "inner": inner,
        }
    )
    public = {
        "experiment_sha256": runner.digest(experiment_raw),
        "oof_sha256": runner.digest(oof_raw),
        "baseline": {"score": 2},
        "candidate_scores": {"score": 1},
        "decision": {"eligible": True},
    }
    (tmp_path / "experiment.json").write_bytes(experiment_raw)
    (tmp_path / "oof.npz").write_bytes(oof_raw)
    (tmp_path / "result.json").write_text(
        json.dumps({**public, "private_calibration": [1, 0]})
    )
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public))
    values, receipt = runner.authenticate_baseline(
        tmp_path, data, outer, inner, public_record=public_path
    )
    np.testing.assert_array_equal(values["calibrated"], data.point + 0.1)
    assert receipt["oof_sha256"] == public["oof_sha256"]
    data.names = tuple(reversed(data.names))
    with pytest.raises(ValueError, match="OOF population differs: names"):
        runner.authenticate_baseline(
            tmp_path, data, outer, inner, public_record=public_path
        )
    (tmp_path / "oof.npz").write_bytes(oof_raw + b"tampered")
    with pytest.raises(ValueError, match="receipt differs: oof"):
        runner.authenticate_baseline(
            tmp_path, data, outer, inner, public_record=public_path
        )


def test_partial_cell_failure_is_charged_and_retried_without_reusing_partial_output(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data()
    outer, inner = runner.balanced_nested_folds(data.groups, data.training_mask)
    real_select = runner.inner_select_c
    calls = 0

    def interrupt_once(*args: Any) -> Any:
        nonlocal calls
        calls += 1
        values = real_select(*args)
        if calls == 1:
            raise RuntimeError("Synthetic interruption after inner fitting")
        return values

    monkeypatch.setattr(runner, "inner_select_c", interrupt_once)
    output = tmp_path / "experiment"
    with pytest.raises(RuntimeError, match="Synthetic interruption"):
        runner.cached_cell(output, np.eye(20), data, outer, inner, 0, 0, {"fixture": 1})
    assert not list(output.rglob("receipt.json"))
    assert not list(output.rglob("predictions.npz"))
    result = runner.cached_cell(
        output, np.eye(20), data, outer, inner, 0, 0, {"fixture": 1}
    )
    assert result[2]["reused"] is False and calls == 2
    attempts = [
        json.loads(path.read_bytes()) for path in output.rglob("fit-attempt-*.json")
    ]
    assert {row["status"] for row in attempts} == {"complete", "failed"}
    assert runner.spent_cpu(output) == pytest.approx(
        sum(row["cpu_core_hours"] for row in attempts)
    )
    accounting = runner.cell_attempt_accounting(output)
    assert accounting["completed_attempts"] == accounting["failed_attempts"] == 1
    assert accounting["known_completed_fit_count"] == 7
    # The failed attempt performed six real inner fits. The seven-fit cell
    # checkpoint does not claim to know that count or silently report zero.
    assert accounting["incomplete_attempt_fit_count"] is None
    assert accounting["interrupted_unknown_attempts"] == 0
    assert accounting["unfinished_attempts"] == 0
    assert runner.freeze_interrupted_fits(output) == 0


def test_orphan_cell_attempt_is_counted_as_unknown_after_recovery(
    runner: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cell = tmp_path / "cells" / "synthetic"
    cell.mkdir(parents=True)
    (cell / "fit-start-1.json").write_text(
        json.dumps(
            {
                "started_epoch_seconds": 100.0,
                "threads": 16,
                "planned_fits": 7,
            }
        )
    )
    assert runner.cell_attempt_accounting(tmp_path)["unfinished_attempts"] == 1
    monkeypatch.setattr(runner.time, "time", lambda: 110.0)
    assert runner.freeze_interrupted_fits(tmp_path) == 1
    accounting = runner.cell_attempt_accounting(tmp_path)
    assert accounting["interrupted_unknown_attempts"] == 1
    assert accounting["unfinished_attempts"] == 0
    assert accounting["known_completed_fit_count"] == 0
    assert accounting["incomplete_attempt_fit_count"] is None
    assert runner.spent_cpu(tmp_path) == pytest.approx(160 / 3600)
