"""Count-repair semantics, both fit paths, and evidence authentication."""

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
def modules(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
    monkeypatch.syspath_prepend(str(root))
    stub = types.ModuleType("catboost")

    class Estimator:
        fits: list[np.ndarray] = []

        def __init__(self, **parameters: Any) -> None:
            self.parameters = parameters

        def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
            self.fits.append(features[:, :2048].copy())
            self.mean = float(targets.mean())

        def predict(self, features: np.ndarray) -> np.ndarray:
            return np.full(len(features), self.mean)

        def get_all_params(self) -> dict[str, Any]:
            return {
                **self.parameters,
                "depth": 6,
                "iterations": 1000,
                "learning_rate": 0.03,
            }

    stub.CatBoostRegressor = Estimator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "catboost", stub)
    loaded = []
    for name in ("competition_runner", "competition_compare"):
        spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        loaded.append(module)
    return types.SimpleNamespace(
        runner=loaded[0], comparison=loaded[1], estimator=Estimator
    )


@pytest.fixture
def inputs(modules: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    import competition_features

    smiles = ("CO" * 140, *("C" * i for i in range(1, 20)))
    corrected = competition_features.featurize_corrected_counts(smiles)
    legacy = corrected.copy()
    legacy[:, :2048] = (corrected[:, :2048].astype(np.int64) + 128) % 256 - 128
    n = len(smiles)
    point = np.linspace(2, 7, n)[:, None] + np.arange(4)[None, :] * 0.1
    data = types.SimpleNamespace(
        names=tuple(f"molecule-{i:03}" for i in range(n)),
        molecule_ids=tuple(f"identity-{i}" for i in range(n)),
        raw_smiles=smiles,
        groups=tuple(f"family-{i}" for i in range(n)),
        point=point,
        low=point.copy(),
        high=point.copy(),
        training_mask=np.ones((n, 4), dtype=bool),
        metric_mask=np.ones((n, 4), dtype=bool),
        legacy_features=legacy,
        receipts={"fixture": "synthetic"},
        report={"metric_targets_missing_bounds": [0] * 4},
    )
    source, output = tmp_path / "development", tmp_path / "corrected"
    source.mkdir()
    output.mkdir()
    (source / "manifest.json").write_bytes(b"synthetic compiled manifest")
    recipe = json.loads(modules.runner.CORRECTED_RECIPE.read_bytes())
    recipe["data_manifest_sha256"] = modules.runner.digest(
        (source / "manifest.json").read_bytes()
    )
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps(recipe))
    monkeypatch.setattr(modules.runner, "CORRECTED_RECIPE", recipe_path)
    monkeypatch.setattr(modules.comparison, "CORRECTED_RECIPE", recipe_path)
    monkeypatch.setattr(modules.runner, "load_development", lambda _: data)
    return types.SimpleNamespace(
        data=data, source=source, output=output, corrected=corrected, recipe=recipe_path
    )


def test_real_count_repair_preserves_legacy_matrix_and_noncount_values(
    modules: Any, inputs: Any
) -> None:
    before = inputs.data.legacy_features.copy()
    matrix, receipt = modules.runner.corrected_feature_matrix(inputs.data)
    assert np.any(before[:, :2048] < 0) and np.any(matrix[:, :2048] > 127)
    np.testing.assert_array_equal(matrix, inputs.corrected)
    np.testing.assert_array_equal(inputs.data.legacy_features, before)
    assert receipt["changed_count_cells"] > 0
    assert receipt["ordered_raw_identity_sha256"]


@pytest.mark.parametrize("corruption", ["negative", "fractional", "wrap", "descriptor"])
def test_feature_recipe_drift_stops_before_any_fit(
    modules: Any, inputs: Any, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    import competition_features

    changed = inputs.corrected.copy()
    if corruption == "descriptor":
        changed[0, 2200] += 1
    elif corruption == "negative":
        changed[0, 0] = -256
    elif corruption == "fractional":
        changed[0, 0] = 0.5
    else:
        changed[0, 0] += 1
    monkeypatch.setattr(
        competition_features, "featurize_corrected_counts", lambda _: changed
    )
    with pytest.raises(ValueError, match="Corrected"):
        modules.runner.corrected_feature_matrix(inputs.data)
    assert not modules.estimator.fits


def test_every_inner_and_outer_fit_uses_corrected_features_and_is_authenticated(
    modules: Any, inputs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, comparison = modules.runner, modules.comparison
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
        runner.subprocess, "check_output", lambda *_args, **_kwargs: "a" * 40
    )
    report = runner._evaluate_locked(
        inputs.source, inputs.output, 20260905, "MAE", 5, "corrected_counts"
    )
    assert len(modules.estimator.fits) == 80
    assert all(np.all(matrix >= 0) for matrix in modules.estimator.fits)
    assert any(np.any(matrix > 127) for matrix in modules.estimator.fits)
    assert report["candidate"] == "maplight-corrected-counts-inner-oof-affine"
    assert report["objective"] == "MAE"
    assert not report["decision"]["release_eligible_on_paired_metrics"]
    assert not report["decision"]["final_promotion"]
    assert "Never apply" in report["release_scope"]
    experiment = json.loads((inputs.output / "experiment.json").read_bytes())
    assert set(experiment["implementation"]) == {
        "competition_runner.py",
        "competition_data.py",
        "competition_metrics.py",
        "competition_features.py",
        "maplight_fixed_features.py",
    }
    # Synthetic fits cannot claim a real committed execution; the existing source
    # tests check Git authentication, while this test exercises all 80 cache cells.
    monkeypatch.setattr(comparison, "_verify_sources", lambda *_: None)
    monkeypatch.setattr(
        comparison.subprocess,
        "check_output",
        lambda *_args, **_kwargs: inputs.recipe.read_bytes(),
    )
    authenticated, arrays, _ = comparison.authenticate(
        inputs.output,
        inputs.data,
        20260905,
        reference=False,
        ablation="corrected_counts",
    )
    # Bounded coefficients applied consistently to outer OOF are insufficient:
    # they must be the solution from the authenticated inner OOF predictions.
    original_oof = (inputs.output / "oof.npz").read_bytes()
    original_result = (inputs.output / "result.json").read_bytes()
    altered = json.loads(original_result)
    cell = altered["outer_calibration"][0]
    cell["slope"] = 1.1 if cell["slope"] != 1.1 else 0.9
    cell["intercept"] = 0.01
    changed_arrays = {key: values.copy() for key, values in arrays.items()}
    take, col = changed_arrays["outer"] == cell["fold"], cell["endpoint"]
    changed_arrays["calibrated"][take, col] = (
        cell["slope"] * changed_arrays["baseline"][take, col] + cell["intercept"]
    )
    np.savez(inputs.output / "oof.npz", **changed_arrays)
    altered["oof_sha256"] = runner.digest((inputs.output / "oof.npz").read_bytes())
    (inputs.output / "result.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="authenticated inner OOF"):
        comparison.authenticate(
            inputs.output,
            inputs.data,
            20260905,
            reference=False,
            ablation="corrected_counts",
        )
    (inputs.output / "oof.npz").write_bytes(original_oof)
    (inputs.output / "result.json").write_bytes(original_result)
    monkeypatch.setattr(
        comparison,
        "authenticate",
        lambda *_args, **_kwargs: (authenticated, arrays, {}),
    )
    matched = comparison.compare_seed(
        inputs.data, inputs.output, inputs.output, 20260905, ablation="corrected_counts"
    )
    assert set(matched["scores"]) == {"corrected_counts", "mae"}
    assert (
        matched["comparisons"]["baseline"]["calibrated"][
            "tail_mechanism_gate_this_seed"
        ]
        is None
    )
    # A claimed corrected experiment cannot surround a legacy-feature fit receipt.
    fit_path = next((inputs.output / "fits").glob("*/receipt.json"))
    receipt = json.loads(fit_path.read_bytes())
    receipt["inputs"]["features_sha256"] = runner.digest(
        inputs.data.legacy_features.tobytes()
    )
    fit_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="Corrected fit receipt"):
        comparison._corrected_fit_evidence(
            inputs.output, inputs.data, experiment, report
        )
    # The historical CSV builder still rejects the distinct estimator identity.
    report["decision"]["release_eligible_on_paired_metrics"] = True
    (inputs.output / "result.json").write_text(json.dumps(report))
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "corrected_release_guard", scripts / "build_calibrated_competition_release.py"
    )
    assert spec and spec.loader
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    with pytest.raises(ValueError, match="complete eligible interim challenger"):
        release._validated_experiment(inputs.output)


def test_unfrozen_objective_or_budget_rejected_before_output(
    modules: Any, tmp_path: Path
) -> None:
    for loss, budget in (("RMSE", 5), ("MAE", 100)):
        output = tmp_path / f"{loss}-{budget}"
        with pytest.raises(ValueError, match="frozen MAE"):
            modules.runner.evaluate(
                tmp_path,
                output,
                expected_compiled_sha256="unused",
                loss=loss,
                max_cpu_core_hours=budget,
                feature_mode="corrected_counts",
            )
        assert not output.exists()


def test_feature_construction_is_inside_shared_lock_and_cpu_cap(
    modules: Any, inputs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = modules.runner
    calls = []
    monkeypatch.setattr(
        runner, "_limit_remaining_cpu", lambda value: calls.append(value)
    )

    def evaluate_under_lock(*args: Any) -> dict[str, Any]:
        assert calls == [5]
        with (inputs.source.parent / "compute.lock").open("a") as handle:
            with pytest.raises(BlockingIOError):
                runner.fcntl.flock(handle, runner.fcntl.LOCK_EX | runner.fcntl.LOCK_NB)
        return {}

    monkeypatch.setattr(runner, "_evaluate_locked", evaluate_under_lock)
    runner.evaluate(
        inputs.source,
        inputs.output,
        expected_compiled_sha256=runner.digest(
            (inputs.source / "manifest.json").read_bytes()
        ),
        max_cpu_core_hours=5,
        feature_mode="corrected_counts",
    )


def test_corrected_recipe_cannot_silently_relax_metric_gate(
    modules: Any, inputs: Any
) -> None:
    recipe = json.loads(inputs.recipe.read_bytes())
    recipe["recommendation_gate_each_seed"]["max_endpoint_component_mae_harm"] = 0.2
    inputs.recipe.write_text(json.dumps(recipe))
    with pytest.raises(ValueError, match="prospective recipe"):
        modules.runner.corrected_recipe(inputs.source)
