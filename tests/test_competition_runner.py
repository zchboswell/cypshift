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
