"""Synthetic TDI threshold, family, model replay and compute-budget boundaries."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sklearn.metrics import matthews_corrcoef


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
    monkeypatch.syspath_prepend(str(root))
    before = {
        name: value
        for name, value in sys.modules.items()
        if name.startswith("competition_")
    }
    stub = types.ModuleType("catboost")
    stub.CatBoostRegressor = object
    stub.CatBoostClassifier = object
    monkeypatch.setitem(sys.modules, "catboost", stub)
    spec = importlib.util.spec_from_file_location(
        "tdi_runner_fixture", root / "competition_tdi_runner.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        yield module
    finally:
        for name in list(sys.modules):
            if name.startswith("competition_") and name not in before:
                sys.modules.pop(name, None)
        sys.modules.update(before)


def fixture_data(n: int = 100) -> tuple[types.SimpleNamespace, np.ndarray]:
    labels = np.column_stack((np.arange(n) % 2, 1 - np.arange(n) % 2)).astype(float)
    bits = np.zeros((n, 4096), dtype=np.uint8)
    bits[:, :2] = labels
    return types.SimpleNamespace(
        names=tuple(f"name{i}" for i in range(n)),
        molecule_ids=tuple(f"id{i}" for i in range(n)),
        groups=tuple(f"family{i // 2}" for i in range(n)),
        labels=labels,
        mask=np.ones_like(labels, dtype=bool),
        original_direct_training_mask=np.ones((n, 4), dtype=bool),
    ), bits


def test_threshold_matches_all_empirical_partitions_and_ties(runner: Any) -> None:
    rng = np.random.default_rng(321)
    for _ in range(12):
        p = rng.integers(0, 11, 100) / 10
        y = rng.integers(0, 2, 100)
        candidates = []
        for t in np.unique(np.r_[0.5, p]):
            pred = p >= t
            if len(np.unique(pred)) == 2:
                candidates.append((-matthews_corrcoef(y, pred), abs(t - 0.5), t))
        expected = min(candidates)
        actual = runner.select_threshold(p, y)
        assert actual["supported"] and actual["mcc"] == -expected[0]
        assert actual["threshold"] == expected[2]
    # This table differs by one ULP under the algebraically equivalent binary
    # product formula; exact score ties must use the organizer covariance form.
    y = np.r_[np.zeros(43), np.ones(568), np.zeros(341), np.ones(915)]
    p = np.r_[np.full(611, 0.25), np.full(1256, 0.75)]
    exact = runner.select_threshold(p, y)
    assert exact["threshold"] == 0.5
    assert exact["mcc"] == matthews_corrcoef(y, p >= 0.5)
    tied = runner.select_threshold(
        np.array([0.2, 0.4, 0.6, 0.8]), np.array([0, 1, 0, 1])
    )
    assert tied["threshold"] == 0.4
    unsupported = runner.select_threshold(np.full(4, 0.5), np.array([0, 1, 0, 1]))
    assert unsupported == {"threshold": 0.5, "mcc": None, "supported": False}
    assert runner.choose_learner({"logistic": tied, "catboost": tied}) == "logistic"
    with pytest.raises(ValueError, match="Both learners unsupported"):
        runner.choose_learner({"logistic": unsupported, "catboost": unsupported})


def test_exact_80fits_keep_families_and_missing_labels_out_of_training(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, bits = fixture_data()
    data.mask[0, 0] = False
    data.labels[0, 0] = 99999  # Never enters the corresponding fit or threshold.
    outer, inner = runner.balanced_nested_folds(
        data.groups, data.original_direct_training_mask
    )
    calls = []

    def fit(**kw: Any) -> tuple[np.ndarray, dict[str, Any]]:
        calls.append(kw)
        train, held, col = kw["train"], kw["predict"], kw["endpoint"]
        assert data.mask[train, col].all()
        assert set(data.labels[train, col]) == {0.0, 1.0}
        assert not {data.groups[i] for i in train} & {data.groups[i] for i in held}
        fold = kw["identity"]["outer"]
        assert np.all(outer[train] != fold)
        if kw["identity"]["role"] == "inner":
            assert np.all(inner[fold, train] != kw["identity"]["inner"])
        else:
            assert len(kw["identity"]["inner_fit_receipts"]) == 3
        return 0.2 + 0.6 * bits[held, col], {
            "path": "/synthetic/receipt",
            "sha256": "fixture",
        }

    monkeypatch.setattr(
        runner, "seed_evidence", lambda *args: {"repeat2_required": True}
    )
    result = runner.evaluate_arrays(data, bits, tmp_path, 20260905, fit)
    assert result["completed_fits"] == len(calls) == 80
    assert sum(v["identity"]["role"] == "inner" for v in calls) == 60
    assert sum(v["identity"]["role"] == "outer" for v in calls) == 20
    assert all(v["chosen_learner"] == "logistic" for v in result["decisions"])
    assert not result["release_eligible"]
    np.testing.assert_array_equal(
        runner.read_array(result["classes"]["selected"]), bits[:, :2]
    )


def test_logistic_saved_model_reloads_and_rejects_tampered_checkpoint(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, bits = fixture_data(32)
    output = tmp_path / "run"
    output.mkdir()
    budget = runner.Budget(tmp_path, output, 20260905)
    monkeypatch.setattr(budget, "limit", lambda: None)
    probability, receipt = runner.fit_estimator(
        output,
        bits,
        data,
        "logistic",
        0,
        np.arange(20),
        np.arange(20, 32),
        {"fixture": "only synthetic"},
        budget,
    )
    budget.finish("complete")
    assert np.isfinite(probability).all() and probability.shape == (12,)
    record = json.loads(Path(receipt["path"]).read_bytes())
    assert record["maximum_reload_absolute_error"] == 0
    assert record["resolved_parameters"]["class_weight"] is None
    assert record["classes"] == [0, 1]
    checkpoint = Path(record["checkpoint"]["path"])
    checkpoint.write_bytes(checkpoint.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="before loading"):
        runner.load_model(record["checkpoint"], "logistic")


def test_reversed_estimator_class_order_is_not_silently_inverted(runner: Any) -> None:
    model = types.SimpleNamespace(
        classes_=np.array([1, 0]),
        predict_proba=lambda x: np.array([[0.8, 0.2], [0.1, 0.9]]),
    )
    np.testing.assert_array_equal(
        runner.positive_probability(model, np.zeros((2, 3))), [0.8, 0.1]
    )


def test_superiority_and_usefulness_recompute_metrics_not_release_flags(
    runner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, _ = fixture_data(8)
    classes = {
        "logistic": np.ones((8, 2), dtype=np.int8),
        "catboost": np.zeros((8, 2), dtype=np.int8),
        "selected": np.full((8, 2), 2, dtype=np.int8),
    }

    # Distinct sentinels only reach these fakes, never public metric code.
    def score(names: Any, labels: Any, mask: Any, pred: Any) -> Any:
        return {
            "macro_bootstrap_mean_mcc": 0.1 + 0.03 * int(pred[0, 0]),
            "endpoints": {ep: {"mcc": 0.1} for ep in runner.ENDPOINTS},
        }

    monkeypatch.setattr(runner, "direct_tdi_scores", score)
    monkeypatch.setattr(
        runner, "paired_family_mcc", lambda *args: {"lower_95": 0.01, "upper_95": 0.1}
    )
    evidence = runner.seed_evidence(data, classes)
    assert (
        evidence["logistic_qualifies_this_seed"]
        and evidence["selected_qualifies_this_seed"]
    )
    first = {"seed": 20260905, "status": "complete", "completed_fits": 80, **evidence}
    second = {**first, "seed": 20260906, "selected_qualifies_this_seed": False}
    assert runner.combine_evidence(first, second)["recommended_procedure"] == "logistic"
    second["logistic_qualifies_this_seed"] = False
    assert runner.combine_evidence(first, second)["recommended_procedure"] is None
    assert not runner.combine_evidence(first, second)["release_eligible"]
    with pytest.raises(ValueError, match="Both frozen repeats"):
        runner.combine_evidence(second, first)


def test_unpinned_intake_cannot_start_official_fits(runner: Any) -> None:
    recipe = json.loads(runner.RECIPE.read_bytes())
    runner.validate_recipe(recipe)
    recipe["tdi_bundle_manifest_sha256"] = None
    with pytest.raises(ValueError, match="intake manifest"):
        runner.validate_recipe(recipe)
    recipe["tdi_bundle_manifest_sha256"] = "a" * 64
    runner.validate_recipe(recipe)
    recipe["learners"]["catboost"]["learning_rate"] = 0.1
    with pytest.raises(ValueError, match="frozen learner"):
        runner.validate_recipe(recipe)


def test_budget_retains_failed_work_and_reduces_retry_allowance(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "attempt1"
    output.mkdir()
    budget = runner.Budget(tmp_path, output, 20260905)
    monkeypatch.setattr(budget, "limit", lambda: None)
    cell = output / "cell"
    cell.mkdir()
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with budget.fit(cell):
            end = runner.time.process_time() + 0.015
            while runner.time.process_time() < end:
                pass
            raise RuntimeError("synthetic failure")
    budget.finish("failed")
    cost = runner.spent_cpu(tmp_path)
    assert cost > 0 and runner.freeze_interrupted_fits(tmp_path) == 0
    second = tmp_path / "attempt2"
    second.mkdir()
    retry = runner.Budget(tmp_path, second, 20260905)
    assert retry.cpu_allowance == pytest.approx((5 - cost) * 3600)
    retry.finish("synthetic")


def test_repeat2_requires_receipt_and_recomputed_continuation(
    runner: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="Repeat2 requires"):
        runner.evaluate(tmp_path, tmp_path, "unused", tmp_path, 20260906)
    data, bits = fixture_data(8)
    identity = {
        key: "same"
        for key in (
            "recipe_sha256",
            "implementation_sha256",
            "runtime",
            "data_manifest_sha256",
            "tdi_manifest_sha256",
            "source_receipts",
            "support_sha256",
            "names",
            "molecule_ids",
            "groups",
        )
    }
    identity["features"] = {"sha256": "same"}
    (tmp_path / "experiment.json").write_bytes(runner.canonical(identity))
    specs = {
        name: runner.array_receipt(tmp_path / f"{name}.npy", bits[:, :2])
        for name in ("logistic", "catboost", "selected")
    }
    result = {
        "seed": 20260905,
        "status": "complete",
        "completed_fits": 80,
        "experiment_sha256": runner.file_hash(tmp_path / "experiment.json"),
        "classes": specs,
        "repeat2_required": True,
    }
    path = tmp_path / "result.json"
    path.write_bytes(runner.canonical(result))
    monkeypatch.setattr(
        runner, "seed_evidence", lambda *args: {"repeat2_required": False}
    )
    with pytest.raises(ValueError, match="flags differ"):
        runner.first_repeat_authority(data, path, runner.file_hash(path), identity)
    result["repeat2_required"] = False
    path.write_bytes(runner.canonical(result))
    with pytest.raises(ValueError, match="futility rule"):
        runner.first_repeat_authority(data, path, runner.file_hash(path), identity)


def test_alternate_output_root_cannot_bypass_shared_lock_or_program_budget(
    runner: Any, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="phase3 accounting root"):
        runner.evaluate(
            tmp_path / "phase3" / "development",
            tmp_path / "phase3" / "tdi",
            "a" * 64,
            tmp_path / "elsewhere" / "run",
            20260905,
        )
    assert not (tmp_path / "elsewhere").exists()
