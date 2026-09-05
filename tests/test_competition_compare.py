"""Meaningful provenance, matched-population and prospective decision checks."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def comparison(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "phase3_compare_test", root / "competition_compare.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture
def experiment_set(
    comparison: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    c = comparison
    n = 60
    point = np.tile(np.linspace(2.1, 7.4, n)[:, None], (1, 4))
    data = SimpleNamespace(
        names=tuple(f"molecule-{i:03}" for i in range(n)),
        molecule_ids=tuple(f"id-{i}" for i in range(n)),
        groups=tuple(f"family-{i}" for i in range(n)),
        point=point,
        low=point - 0.01,
        high=point + 0.01,
        metric_mask=np.ones((n, 4), dtype=bool),
        training_mask=np.ones((n, 4), dtype=bool),
        receipts={"fixture_source": "a" * 64},
    )
    public = tmp_path / "public"
    public.mkdir()
    monkeypatch.setattr(c, "PUBLIC", public)
    # Git commit authentication is separately exercised below; synthetic records
    # cannot claim to have been produced by an actual committed model execution.
    monkeypatch.setattr(c, "_verify_sources", lambda *_: None)
    monkeypatch.setattr(c, "load_development", lambda _: data)
    source = tmp_path / "development"
    source.mkdir()
    (source / "manifest.json").write_text('{"fixture":true}')
    recipe = json.loads(c.RECIPE.read_bytes())
    recipe["data_manifest_sha256"] = c._hash((source / "manifest.json").read_bytes())
    recipe_path = public / "recipe.json"
    _write(recipe_path, recipe)
    monkeypatch.setattr(c, "RECIPE", recipe_path)
    candidates, references = [], []
    for seed in c.SEEDS:
        outer, inner = c.balanced_nested_folds(
            data.groups, data.training_mask, seed=seed
        )
        for reference, destinations in ((False, candidates), (True, references)):
            directory = tmp_path / f"{'reference' if reference else 'candidate'}-{seed}"
            directory.mkdir()
            destinations.append(directory)
            prediction = point - (0.4 if reference else 0.04)
            buffer = io.BytesIO()
            np.savez(
                buffer,
                baseline=prediction,
                calibrated=prediction,
                names=np.asarray(data.names),
                groups=np.asarray(data.groups),
                outer=outer,
                inner=inner,
            )
            (directory / "oof.npz").write_bytes(buffer.getvalue())
            parameters = {
                "loss_function": "RMSE",
                "random_strength": 2,
                "random_seed": 1,
                "task_type": "CPU",
                "thread_count": 16,
                "verbose": 0,
                "allow_writing_files": False,
                "learning_rate": 0.03,
                "iterations": 1000,
                "depth": 6,
            }
            experiment = {
                "objective": "RMSE",
                "parameters": parameters,
                "candidate": "maplight-rmse-inner-oof-affine",
                "runtime": {"fixture": "same"},
                "seed": seed,
                "source_receipts": data.receipts,
                "molecule_ids": list(data.molecule_ids),
                "groups": list(data.groups),
                "outer": outer.tolist(),
                "inner": inner.tolist(),
            }
            _write(directory / "experiment.json", experiment)
            result = {
                "status": "complete",
                "fits": 80,
                "reserved_numeric_targets_opened": 0,
                "objective": "RMSE",
                "parameters": parameters,
                "candidate": "maplight-inner-oof-affine"
                if reference
                else "maplight-rmse-inner-oof-affine",
                "execution_git_commit": "b" * 40,
                "decision": {},
                "baseline": {},
                "candidate_scores": {},
                "paired_family": {},
                "experiment_sha256": c._hash(
                    (directory / "experiment.json").read_bytes()
                ),
                "oof_sha256": c._hash(buffer.getvalue()),
                "outer_calibration": [
                    {"fold": f, "endpoint": e, "slope": 1, "intercept": 0}
                    for f in range(5)
                    for e in range(4)
                ],
            }
            _write(directory / "result.json", result)
    fixture = SimpleNamespace(
        data=data,
        candidates=tuple(candidates),
        references=tuple(references),
        source=source,
        public=public,
    )
    _seal_public(c, fixture)
    return fixture


def _seal_public(c: Any, fixture: Any) -> None:
    _write(
        fixture.public / "phase3_maplight_affine_v1_result.json",
        json.loads((fixture.references[0] / "result.json").read_bytes()),
    )
    hashes = {
        name: c._hash((fixture.references[1] / name).read_bytes())
        for name in ("result.json", "experiment.json", "oof.npz")
    }
    _write(
        fixture.public / "phase3_maplight_affine_repeat2_audit.json",
        {"input_hashes": hashes},
    )


def _reseal(c: Any, directory: Path) -> None:
    result = json.loads((directory / "result.json").read_bytes())
    for name, field in (
        ("experiment.json", "experiment_sha256"),
        ("oof.npz", "oof_sha256"),
    ):
        result[field] = c._hash((directory / name).read_bytes())
    _write(directory / "result.json", result)


@pytest.mark.parametrize(
    "field", ["molecule_ids", "groups", "outer", "inner", "source_receipts"]
)
def test_rehashed_crossed_population_is_rejected(
    comparison: Any, experiment_set: Any, field: str
) -> None:
    directory = experiment_set.candidates[0]
    experiment = json.loads((directory / "experiment.json").read_bytes())
    experiment[field] = []
    _write(directory / "experiment.json", experiment)
    _reseal(comparison, directory)
    with pytest.raises(ValueError, match="population differs"):
        comparison.authenticate(
            directory, experiment_set.data, 20260905, reference=False
        )


def test_rehashed_oof_row_order_is_rejected(
    comparison: Any, experiment_set: Any
) -> None:
    directory = experiment_set.candidates[0]
    with np.load(directory / "oof.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["names"] = arrays["names"][::-1]
    np.savez(directory / "oof.npz", **arrays)
    _reseal(comparison, directory)
    with pytest.raises(ValueError, match="OOF population differs: names"):
        comparison.authenticate(
            directory, experiment_set.data, 20260905, reference=False
        )


@pytest.mark.parametrize("seed_index", [0, 1])
def test_original_reference_result_tampering_is_rejected(
    comparison: Any, experiment_set: Any, seed_index: int
) -> None:
    directory = experiment_set.references[seed_index]
    result = json.loads((directory / "result.json").read_bytes())
    result["baseline"] = {"fabricated": 0.0}
    _write(directory / "result.json", result)
    with pytest.raises(ValueError, match="public reference"):
        comparison.authenticate(
            directory, experiment_set.data, comparison.SEEDS[seed_index], reference=True
        )


def test_candidate_oof_receipt_tampering_is_rejected(
    comparison: Any, experiment_set: Any
) -> None:
    directory = experiment_set.candidates[0]
    (directory / "oof.npz").write_bytes(b"damaged")
    with pytest.raises(ValueError, match="receipt differs: oof"):
        comparison.authenticate(
            directory, experiment_set.data, 20260905, reference=False
        )


def test_altered_candidate_metric_claim_is_recomputed(
    comparison: Any, experiment_set: Any
) -> None:
    with pytest.raises(ValueError, match="Recomputed result metrics differ"):
        comparison.compare_seed(
            experiment_set.data,
            experiment_set.candidates[0],
            experiment_set.references[0],
            20260905,
        )


def test_source_receipt_must_match_execution_commit(
    comparison: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        comparison.subprocess,
        "check_output",
        lambda *_args, **_kwargs: b"actual committed source",
    )
    with pytest.raises(ValueError, match="Execution source hash differs"):
        comparison._verify_sources(
            {
                "implementation": {
                    name: "0" * 64
                    for name in (
                        "competition_runner.py",
                        "competition_data.py",
                        "competition_metrics.py",
                    )
                }
            },
            {"execution_git_commit": "a" * 40},
        )


@pytest.mark.parametrize("second_seed_fails", [False, True])
def test_two_repeat_metrics_publish_readonly_without_release(
    comparison: Any, experiment_set: Any, tmp_path: Path, second_seed_fails: bool
) -> None:
    c, f = comparison, experiment_set
    if second_seed_fails:
        directory = f.candidates[1]
        with np.load(directory / "oof.npz", allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        # A successful first repeat cannot conceal worse predictions in repeat 2.
        arrays["baseline"] = f.data.point - 0.8
        arrays["calibrated"] = arrays["baseline"].copy()
        np.savez(directory / "oof.npz", **arrays)
        _reseal(c, directory)
    args = (
        np.asarray(f.data.names),
        np.asarray(f.data.groups),
        f.data.point,
        f.data.low,
        f.data.high,
    )
    for directory in (*f.candidates, *f.references):
        result = json.loads((directory / "result.json").read_bytes())
        with np.load(directory / "oof.npz", allow_pickle=False) as archive:
            baseline, calibrated = archive["baseline"], archive["calibrated"]
        result["baseline"] = c.direct_scores(*args, baseline)
        result["candidate_scores"] = c.direct_scores(*args, calibrated)
        result["paired_family"] = c.paired_family_difference(
            *args, calibrated, baseline
        )
        _write(directory / "result.json", result)
    _seal_public(c, f)
    output = tmp_path / "private" / "comparison.json"
    report = c.compare(f.source, f.candidates, f.references, output)
    assert (
        report["decisions"]["baseline"]["supported_for_interim_recommendation"]
        is not second_seed_fails
    )
    assert (
        report["decisions"]["calibrated"]["tail_mechanism_supported_both_seeds"]
        is not second_seed_fails
    )
    assert not report["final_promotion"] and not report["release_authorized"]
    assert report["selected_supported_variant"] == (
        None if second_seed_fails else "baseline"
    )
    assert report["prospective_recipe_sha256"] == c._hash(c.RECIPE.read_bytes())
    assert (
        report["repeats"][0]["potency_bands"]["rmse"]["baseline"]["ge6"]["endpoints"][
            "CYP1A2"
        ]["rows"]
        > 0
    )
    assert output.stat().st_mode & 0o222 == 0
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        c.compare(f.source, f.candidates, f.references, output)
    assert output.read_bytes() == before


def test_git_destination_fails_before_loading_data(
    comparison: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        comparison,
        "load_development",
        lambda _: pytest.fail("must reject destination before reading data"),
    )
    with pytest.raises(ValueError, match="outside Git"):
        comparison.compare(
            tmp_path,
            (tmp_path, tmp_path),
            (tmp_path, tmp_path),
            tmp_path / "comparison.json",
        )


def test_empty_potency_band_is_unsupported_not_perfect(
    comparison: Any, experiment_set: Any
) -> None:
    data = experiment_set.data
    data.point[:] = 4.7
    report = comparison.potency_bands(data, data.point.copy())
    assert report["ge6"]["macro_interval_mae"] is None
    assert not report["ge6"]["all_endpoints_supported"]


def test_changed_prospective_gate_is_rejected_before_comparison(
    comparison: Any, experiment_set: Any, tmp_path: Path
) -> None:
    recipe = json.loads(comparison.RECIPE.read_bytes())
    recipe["recommendation_gate_each_seed"]["max_endpoint_component_mae_harm"] = 0.2
    _write(comparison.RECIPE, recipe)
    with pytest.raises(ValueError, match="Prospective recipe"):
        comparison.compare(
            experiment_set.source,
            experiment_set.candidates,
            experiment_set.references,
            tmp_path / "comparison.json",
        )
