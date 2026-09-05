"""Prospective two-repeat/control decisions and coherent artifact tamper rejection."""

from __future__ import annotations

import copy
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest


@pytest.fixture
def comparison(monkeypatch: pytest.MonkeyPatch) -> Any:
    root = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
    monkeypatch.syspath_prepend(str(root))
    stub = types.ModuleType("catboost")
    stub.CatBoostRegressor = object
    monkeypatch.setitem(sys.modules, "catboost", stub)
    return importlib.import_module("competition_mlp_compare")


def score(primary: float, component: float = 0.2) -> dict[str, Any]:
    return {
        "macro_bootstrap_mean_st_rae": primary,
        "endpoints": {
            e: {"component_mae": component}
            for e in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
        },
    }


def repeats(c: Any) -> list[dict[str, Any]]:
    return [
        {
            "seed": seed,
            "scores": {arm: {v: score(0.8) for v in c.VARIANTS} for arm in c.ARMS},
            "comparisons": {
                arm: {
                    v: {
                        reference: {"gate_this_seed": True}
                        for reference in ("incumbent", "direct", "shuffled_aux")
                    }
                    for v in c.VARIANTS
                }
                for arm in c.ARMS[:2]
            },
        }
        for seed in c.SEEDS
    ]


def test_auxiliary_must_beat_both_same_variant_controls_in_each_repeat(
    comparison: Any,
) -> None:
    c = comparison
    evidence = repeats(c)
    for repeat in evidence:
        for v in c.VARIANTS:
            repeat["comparisons"]["direct"][v]["incumbent"]["gate_this_seed"] = False
        repeat["scores"]["real_aux"]["raw"] = score(0.4)
        repeat["scores"]["real_aux"]["affine"] = score(0.5)
        repeat["scores"]["shuffled_aux"]["raw"] = score(0.01)
    # A strong first repeat or a better opposite variant cannot rescue this failure.
    evidence[1]["comparisons"]["real_aux"]["raw"]["shuffled_aux"]["gate_this_seed"] = (
        False
    )
    decisions, chosen = c.decide(evidence)
    assert chosen == {"arm": "real_aux", "variant": "affine"}
    assert decisions["real_aux_raw"]["supported_for_interim_recommendation"] is False
    assert not any("shuffled" in key for key in decisions)
    evidence[1]["comparisons"]["real_aux"]["affine"]["direct"]["gate_this_seed"] = False
    assert c.decide(evidence)[1] is None


def test_exact_tie_and_first_repeat_order_are_prespecified(comparison: Any) -> None:
    c = comparison
    evidence = repeats(c)
    assert c.decide(evidence)[1] == {"arm": "direct", "variant": "raw"}
    evidence[0]["scores"]["real_aux"]["affine"] = score(0.799)
    evidence[1]["scores"]["direct"]["raw"] = score(0.01)
    assert c.decide(evidence)[1] == {"arm": "real_aux", "variant": "affine"}
    with pytest.raises(ValueError, match="Both prescribed seeds"):
        c.decide([evidence[0], evidence[0]])


def test_morgan_futility_requires_all_applicable_gates_and_never_selects(
    comparison: Any,
) -> None:
    c = comparison
    first = repeats(c)[0]
    first["feature_mode"] = "morgan_only"
    for arm in c.ARMS[:2]:
        for variant in c.VARIANTS:
            first["comparisons"][arm][variant]["incumbent"]["gate_this_seed"] = False
    assert c.first_seed_futility(first)["stop_repeat_two_for_futility"]
    first["comparisons"]["real_aux"]["raw"]["incumbent"]["gate_this_seed"] = True
    first["comparisons"]["real_aux"]["raw"]["shuffled_aux"]["gate_this_seed"] = False
    assert c.first_seed_futility(first)["stop_repeat_two_for_futility"]
    first["comparisons"]["real_aux"]["raw"]["shuffled_aux"]["gate_this_seed"] = True
    decision = c.first_seed_futility(first)
    assert not decision["stop_repeat_two_for_futility"]
    assert (
        decision["selected_supported_variant"] is None
        and not decision["release_authorized"]
    )
    first["feature_mode"] = "morgan_descriptors"
    with pytest.raises(ValueError, match="first Morgan-only"):
        c.first_seed_futility(first)


def test_gate_inclusive_gain_harm_but_strict_interval_and_no_aux_gain_floor(
    comparison: Any,
) -> None:
    c = comparison
    pair = {"lower_95": -0.1, "upper_95": -0.001}
    assert c.contrast(score(0.97, 0.21), score(1.0), pair, incumbent=True)[
        "gate_this_seed"
    ]
    assert not c.contrast(score(0.99), score(1.0), pair, incumbent=True)[
        "gate_this_seed"
    ]
    assert c.contrast(score(0.99), score(1.0), pair, incumbent=False)["gate_this_seed"]
    assert not c.contrast(
        score(0.9), score(1.0), dict(pair, upper_95=0), incumbent=True
    )["gate_this_seed"]
    assert not c.contrast(score(0.9, 0.221), score(1.0), pair, incumbent=True)[
        "gate_this_seed"
    ]
    for bad in (
        {"lower_95": 0, "upper_95": -0.1},
        {"lower_95": -0.1, "upper_95": float("nan")},
    ):
        with pytest.raises(ValueError, match="Invalid comparison"):
            c.contrast(score(0.9), score(1.0), bad, incumbent=True)


def write(path: Path, value: Any) -> None:
    path.chmod(0o644) if path.exists() else None
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture(params=("morgan_descriptors", "morgan_only"))
def artifacts(
    comparison: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Any:
    """Run real CPU orchestration with a deterministic synthetic worker stand-in."""
    c = comparison
    runner = importlib.import_module("competition_mlp_runner")
    n = 60
    point = np.tile(np.linspace(3, 7, n)[:, None], (1, 4))
    data = types.SimpleNamespace(
        point=point,
        low=point - 0.1,
        high=point + 0.1,
        training_mask=np.ones_like(point, dtype=bool),
        metric_mask=np.ones_like(point, dtype=bool),
        names=tuple(f"molecule-{i}" for i in range(n)),
        molecule_ids=tuple(f"id-{i}" for i in range(n)),
        groups=tuple(f"family-{i // 2}" for i in range(n)),
        receipts={"synthetic": "source"},
    )
    features = np.zeros((n, 4296))
    if request.param == "morgan_descriptors":
        features[:, 4096:] = np.arange(n)[:, None]
    auxiliary, mask = point - 5, np.ones_like(point, dtype=bool)
    output = tmp_path / "candidate"
    output.mkdir()
    runtime_path = tmp_path / "runtime.json"
    write(runtime_path, {"artifact_hashes": {"resolved-closure.json": "f" * 64}})
    runtime = {"path": str(runtime_path), "sha256": c.digest(runtime_path.read_bytes())}
    recipe = json.loads(runner.recipe_path(request.param).read_bytes())
    recipe["gpu_runtime_receipt_sha256"] = runtime["sha256"]
    feature_spec = runner.array_file(output / "features.npy", features)
    worker = tmp_path / "synthetic-worker.py"
    worker.write_text("# Explicit synthetic stand-in; no Torch or network fits.\n")
    identity = {
        "feature_mode": request.param,
        "seed": c.SEEDS[0],
        "names": list(data.names),
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "source_receipts": data.receipts,
        "features": feature_spec,
        "recipe_sha256": "a" * 64,
        "cpu_runtime": recipe["cpu_runtime_versions"],
        "gpu_runtime_receipt": runtime,
        "data_manifest_sha256": recipe["data_manifest_sha256"],
        "auxiliary_records_sha256": recipe["auxiliary_records_sha256"],
        "execution_git_commit": "b" * 40,
        "implementation_sha256": {
            name: c.digest(worker.read_bytes()) for name in c.IMPLEMENTATIONS
        },
    }
    write(output / "experiment.json", identity)

    class SyntheticWorker:
        def run(self, command: list[str], directory: Path) -> None:
            request_path = Path(command[command.index("--request") + 1])
            request = json.loads(request_path.read_bytes())
            destination = Path(command[command.index("--output") + 1])
            destination.mkdir()
            count = request["files"]["predict_x"]["shape"][0]
            prediction = np.tile(
                np.asarray([4.1, 4.2, 4.3, 4.4], dtype="float32"), (count, 1)
            )
            checkpoint = destination / "checkpoint.pt"
            checkpoint.write_bytes(b"synthetic checkpoint: no model execution")
            stopped = request["mode"] == "stopped"
            if stopped:
                prediction = c.read_array(
                    request["files"]["stop_direct_y"]
                ) + np.float32(1)
            selected, epochs = (
                (2, 22) if stopped else (request["epochs"], request["epochs"])
            )
            train_n = request["files"]["train_x"]["shape"][0]
            rng = np.random.default_rng(request["batch_seed"])
            batch_hashes = [
                c.digest(rng.permutation(train_n).astype("int64").tobytes())
                for _ in range(epochs)
            ]
            receipt = {
                "schema": "cypshift.mlp.fit_receipt.v1",
                "status": "complete",
                "request_sha256": c.digest(request_path.read_bytes()),
                "runtime_receipt_sha256": runtime["sha256"],
                **{
                    k: request[k]
                    for k in (
                        "identity",
                        "arm",
                        "mode",
                        "hyperparameters",
                        "worker_sha256",
                    )
                },
                "selected_epoch": selected,
                "epochs_run": epochs,
                "optimizer_steps": epochs * ((train_n + 127) // 128),
                "checkpoint_optimizer_steps": selected * ((train_n + 127) // 128),
                "seeds": {
                    k: request[k] for k in ("model_seed", "batch_seed", "dropout_seed")
                },
                "initial_state_sha256": "c" * 64,
                "batch_order_epoch_sha256": batch_hashes,
                "finite_loss": True,
                "direct_stopping_mae_by_epoch": [2.0, 1.0] + [1.0] * 20
                if stopped
                else [],
                "selected_stopping_mae": 1.0 if stopped else None,
                "reload_parity": {
                    "maximum_absolute_error": 0.0,
                    "model_and_optimizer_state_exact": True,
                },
                "checkpoint": {
                    "path": str(checkpoint),
                    "sha256": c.digest(checkpoint.read_bytes()),
                },
                "predictions": runner.array_file(
                    destination / "predictions.npy", prediction
                ),
                "runtime": {
                    "python": "3.12.3",
                    "numpy": "1.26.4",
                    "torch": "2.12.0+rocm7.14.0",
                    "hip": "7.14.60850",
                    "architecture": "gfx1100",
                    "closure_sha256": "f" * 64,
                },
                "cpu_threads": 1,
                "gpu_allocator_cap_bytes": 2147483648,
                "peak_reserved_bytes": 1024,
            }
            write(destination / "receipt.json", receipt)

    def fit(**kwargs: Any) -> Any:
        lineage = kwargs.pop("identity")
        return runner.run_fit(
            output,
            worker,
            Path(sys.executable),
            runtime,
            data,
            features,
            auxiliary,
            mask,
            seed=c.SEEDS[0],
            identity={**identity, **lineage},
            hyperparameters=recipe["hyperparameters"],
            budget=SyntheticWorker(),
            **kwargs,
        )

    monkeypatch.setattr(runner, "direct_scores", lambda *a, **k: {})
    monkeypatch.setattr(runner, "paired_family_difference", lambda *a, **k: {})
    # Synthetic artifacts make no source-commit claim; source verification is not bypassed in production.
    monkeypatch.setattr(c, "verify_sources", lambda *_: None)
    result = runner.evaluate_arrays(
        data, features, auxiliary, mask, output, c.SEEDS[0], fit
    )
    result["experiment_sha256"] = c.digest((output / "experiment.json").read_bytes())
    result["feature_mode"] = request.param
    write(output / "result.json", result)
    write(
        output / "resources.json",
        {
            "status": "complete",
            "occupied_wall_seconds": 1.0,
            "invocation_cpu_core_hours": 0.001,
            "prior_program_cpu_core_hours": 0.0,
            "prior_seed_cpu_core_hours": 0.0,
            "prior_seed_occupied_wall_seconds": 0.0,
        },
    )
    return types.SimpleNamespace(
        c=c,
        output=output,
        data=data,
        features=features,
        auxiliary=auxiliary,
        mask=mask,
        recipe=recipe,
        result=result,
    )


def authenticate(fixture: Any) -> Any:
    return fixture.c.authenticate_mlp(
        fixture.output,
        fixture.data,
        fixture.features,
        fixture.auxiliary,
        fixture.mask,
        fixture.c.SEEDS[0],
        fixture.recipe,
        "a" * 64,
    )


def test_all_105_requests_and_inner_calibrations_authenticate_then_reject_coherent_tampering(
    artifacts: Any,
) -> None:
    f = artifacts
    metadata, _, _ = authenticate(f)
    assert metadata["result"]["completed_fits"] == 105
    original_result = copy.deepcopy(f.result)
    # Rehash an invalid selected epoch and matching optimizer count: hash checks alone pass.
    entry = next(e for e in f.result["fit_receipts"] if e["role"] == "stop")
    path = Path(entry["path"])
    original_receipt = path.read_bytes()
    receipt = json.loads(original_receipt)
    # Coherently rehash stopping predictions that no longer support the score.
    prediction_path = Path(receipt["predictions"]["path"])
    original_prediction = prediction_path.read_bytes()
    prediction_path.chmod(0o644)
    np.save(prediction_path, f.c.read_array(receipt["predictions"]) + np.float32(0.3))
    receipt["predictions"]["sha256"] = f.c.digest(prediction_path.read_bytes())
    write(path, receipt)
    entry["sha256"] = f.c.digest(path.read_bytes())
    write(f.output / "result.json", f.result)
    with pytest.raises(
        ValueError, match="stopping score differs from saved predictions"
    ):
        authenticate(f)
    prediction_path.write_bytes(original_prediction)
    path.write_bytes(original_receipt)
    receipt = json.loads(original_receipt)
    receipt["selected_epoch"] = 3  # Same minimum, but earliest tie was epoch 2.
    receipt["checkpoint_optimizer_steps"] = 3
    write(path, receipt)
    entry["selected_epoch"] = 3
    entry["sha256"] = f.c.digest(path.read_bytes())
    write(f.output / "result.json", f.result)
    with pytest.raises(ValueError, match="stopping choice"):
        authenticate(f)
    path.write_bytes(original_receipt)
    write(f.output / "result.json", original_result)
    # Rehash both worker request and receipt after adding an outer-held row to training.
    entry = next(e for e in original_result["fit_receipts"] if e["role"] == "outer")
    path = Path(entry["path"])
    receipt = json.loads(path.read_bytes())
    request_path = path.parent.parent / "request.json"
    request = json.loads(request_path.read_bytes())
    request["identity"]["train"][0] = request["identity"]["predict"][0]
    write(request_path, request)
    receipt["request_sha256"] = f.c.digest(request_path.read_bytes())
    receipt["identity"] = request["identity"]
    write(path, receipt)
    entry["request_sha256"] = receipt["request_sha256"]
    entry["sha256"] = f.c.digest(path.read_bytes())
    write(f.output / "result.json", original_result)
    with pytest.raises(ValueError, match="requested population"):
        authenticate(f)


def test_representation_identity_rejects_cross_mode_reuse(artifacts: Any) -> None:
    f = artifacts
    original = f.recipe.get("feature_mode", "morgan_descriptors")
    f.recipe["feature_mode"] = (
        "morgan_only" if original == "morgan_descriptors" else "morgan_descriptors"
    )
    with pytest.raises(ValueError, match="representation identity"):
        authenticate(f)
    f.recipe["feature_mode"] = original
    if original == "morgan_only":
        f.features[0, 4129] = 1e12
        with pytest.raises(ValueError, match="contains descriptor"):
            authenticate(f)


def test_original_source_vector_remains_pinned_and_cannot_claim_morgan_only(
    comparison: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = comparison
    frozen = {name: ("original:" + name).encode() for name in c.IMPLEMENTATIONS}
    frozen[c.RECIPE.name] = b"original-recipe"
    monkeypatch.setattr(
        c.subprocess, "check_output", lambda command, **_: frozen[Path(command[2]).name]
    )
    experiment = {
        "execution_git_commit": "a" * 40,
        "implementation_sha256": {
            name: c.digest(raw)
            for name, raw in frozen.items()
            if name in c.IMPLEMENTATIONS
        },
    }
    c.verify_sources(experiment, c.digest(b"original-recipe"))
    experiment["feature_mode"] = "morgan_only"
    with pytest.raises(ValueError, match="source vector"):
        c.verify_sources(experiment, c.digest(b"original-recipe"))
    experiment.pop("feature_mode")
    experiment["implementation_sha256"]["competition_mlp_runner.py"] = "0" * 64
    with pytest.raises(ValueError, match="source vector"):
        c.verify_sources(experiment, c.digest(b"original-recipe"))


def test_recipe_hash_and_representation_must_agree(
    comparison: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import competition_mlp_runner as runner

    c = comparison
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(b"synthetic development manifest")
    paths = {}
    for mode in runner.FEATURE_MODES:
        recipe = json.loads(runner.recipe_path(mode).read_bytes())
        recipe["data_manifest_sha256"] = c.digest(manifest.read_bytes())
        paths[mode] = tmp_path / (mode + ".json")
        write(paths[mode], recipe)
    monkeypatch.setattr(runner, "recipe_path", lambda mode: paths[mode])
    _, original_hash = c.recipe_for(tmp_path)
    _, ablation_hash = c.recipe_for(tmp_path, "morgan_only")
    assert original_hash != ablation_hash
    changed = json.loads(paths["morgan_only"].read_bytes())
    changed["feature_mode"] = "morgan_descriptors"
    write(paths["morgan_only"], changed)
    with pytest.raises(ValueError, match="representation differ"):
        c.recipe_for(tmp_path, "morgan_only")


def test_score_recomputation_uses_calibrated_incumbent_and_same_variant_controls(
    comparison: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = comparison
    n = 60
    point = np.tile(np.linspace(2, 8, n)[:, None], (1, 4))
    data = types.SimpleNamespace(
        names=tuple(f"n{i}" for i in range(n)),
        groups=tuple(f"g{i // 2}" for i in range(n)),
        point=point,
        low=point - 0.01,
        high=point + 0.01,
    )
    args = (
        np.asarray(data.names),
        np.asarray(data.groups),
        data.point,
        data.low,
        data.high,
    )
    arrays = {
        "direct": {"raw": point + 0.12, "affine": point + 0.10},
        "real_aux": {"raw": point + 0.06, "affine": point + 0.03},
        "shuffled_aux": {"raw": point + 0.05, "affine": point + 0.08},
    }
    result = {
        "scores": {
            a: {v: c.direct_scores(*args, p) for v, p in variants.items()}
            for a, variants in arrays.items()
        },
        "paired_auxiliary_controls": {
            v: {
                a: c.paired_family_difference(
                    *args, arrays["real_aux"][v], arrays[a][v]
                )
                for a in ("direct", "shuffled_aux")
            }
            for v in c.VARIANTS
        },
    }
    reference = {"baseline": point + 0.40, "calibrated": point + 0.20}
    reference_result = {
        "baseline": c.direct_scores(*args, reference["baseline"]),
        "candidate_scores": c.direct_scores(*args, reference["calibrated"]),
    }
    monkeypatch.setattr(
        c,
        "authenticate_mlp",
        lambda *a: (
            {"result": result, "experiment": {"cpu_runtime": {"fixture": "same"}}},
            arrays,
            {},
        ),
    )
    monkeypatch.setattr(
        c,
        "authenticate_mae",
        lambda *a, **k: (
            {
                "result": reference_result,
                "experiment": {"runtime": {"fixture": "same"}},
            },
            reference,
            {},
        ),
    )
    evidence = c.compare_seed(
        data,
        np.zeros((n, 1)),
        point,
        np.ones_like(point, dtype=bool),
        Path("candidate"),
        Path("reference"),
        c.SEEDS[0],
        {},
        "fixture",
    )
    assert evidence["comparisons"]["real_aux"]["raw"]["incumbent"]["gate_this_seed"]
    assert not evidence["comparisons"]["real_aux"]["raw"]["shuffled_aux"][
        "gate_this_seed"
    ]
    assert evidence["comparisons"]["real_aux"]["affine"]["shuffled_aux"][
        "gate_this_seed"
    ]
    expected_gain = (
        evidence["incumbent_scores"]["calibrated"]["macro_bootstrap_mean_st_rae"]
        - evidence["scores"]["direct"]["raw"]["macro_bootstrap_mean_st_rae"]
    ) / evidence["incumbent_scores"]["calibrated"]["macro_bootstrap_mean_st_rae"]
    assert (
        evidence["comparisons"]["direct"]["raw"]["incumbent"]["relative_primary_gain"]
        == expected_gain
    )
    result["scores"]["real_aux"]["raw"]["macro_bootstrap_mean_st_rae"] = 0.0
    with pytest.raises(ValueError, match="Recomputed MLP scores"):
        c.compare_seed(
            data,
            np.zeros((n, 1)),
            point,
            np.ones_like(point, dtype=bool),
            Path("candidate"),
            Path("reference"),
            c.SEEDS[0],
            {},
            "fixture",
        )
