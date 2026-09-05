"""Authenticate two development MLP repeats and their matched controls; never release."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
from competition_compare import SEEDS, _close
from competition_compare import authenticate as authenticate_mae
from competition_data import balanced_nested_folds, load_development
from competition_metrics import ENDPOINTS, direct_scores, paired_family_difference

ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "benchmarks/openadmet_cyp_2026/phase3_mlp_auxiliary_v1.json"
ARMS = ("direct", "real_aux", "shuffled_aux")
VARIANTS = ("raw", "affine")
CANDIDATES = tuple((arm, variant) for arm in ARMS[:2] for variant in VARIANTS)
IMPLEMENTATIONS = {
    "competition_mlp_runner.py",
    "competition_mlp_worker.py",
    "competition_data.py",
    "competition_features.py",
    "competition_metrics.py",
    "competition_runner.py",
    "maplight_fixed_features.py",
}
ORIGINAL_EXECUTION_COMMIT = "5a2769021b66fbe09569afea88d9522e5da4ab17"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def read_array(spec: dict[str, Any], directory: Path | None = None) -> np.ndarray:
    if directory is not None and not Path(spec["path"]).resolve().is_relative_to(
        directory.resolve()
    ):
        raise ValueError("MLP artifact path escapes candidate directory")
    raw = Path(spec["path"]).read_bytes()
    if digest(raw) != spec["sha256"]:
        raise ValueError("Array receipt hash differs")
    value = np.load(io.BytesIO(raw), allow_pickle=False)
    if list(value.shape) != spec["shape"] or str(value.dtype) != spec["dtype"]:
        raise ValueError("Array receipt shape/dtype differs")
    return value


def recipe_for(
    source: Path, feature_mode: str = "morgan_descriptors"
) -> tuple[dict[str, Any], str]:
    from competition_mlp_runner import recipe_path

    raw = recipe_path(feature_mode).read_bytes()
    recipe = json.loads(raw)
    expected = {
        "schema": (
            "cypshift.phase3.mlp_auxiliary_recipe.v1"
            if feature_mode == "morgan_descriptors"
            else "cypshift.phase3.mlp_morgan_only_recipe.v1"
        ),
        "status": (
            "prespecified_before_official_MLP_outcomes"
            if feature_mode == "morgan_descriptors"
            else "prespecified_before_official_Morgan_only_outcomes"
        ),
        "seeds": list(SEEDS),
        "arms": list(ARMS),
        "new_fits_per_seed": 105,
        "data_manifest_sha256": digest((source / "manifest.json").read_bytes()),
        "recommendation_gate_each_seed": {
            "max_endpoint_component_mae_harm": 0.02,
            "paired_family_primary_upper95_max_exclusive": 0,
            "relative_macro_primary_gain_over_calibrated_incumbent_min": 0.02,
        },
        "auxiliary_retention_each_seed": {
            "max_endpoint_component_mae_harm": 0.02,
            "minimum_relative_gain": None,
            "paired_family_primary_upper95_max_exclusive": 0,
            "references": [
                "matched direct same variant",
                "matched shuffled same variant",
            ],
        },
    }
    if recipe.get("feature_mode", "morgan_descriptors") != feature_mode:
        raise ValueError("Recipe and requested MLP representation differ")
    if feature_mode == "morgan_only":
        expected["first_seed_futility"] = {
            "enabled": True,
            "seed": 20260905,
            "stop_repeat_two_if": "No direct/real raw/affine variant passes every applicable first-seed incumbent and auxiliary-control gate.",
            "otherwise": "Run all105 joint fits on20260906 unchanged; require both-seed gates.",
            "preliminary_release_or_selection": False,
        }
    if any(recipe.get(key) != value for key, value in expected.items()):
        raise ValueError("Prospective MLP recipe/population/gates differ")
    return recipe, digest(raw)


def verify_sources(experiment: dict[str, Any], recipe_hash: str) -> None:
    from competition_mlp_runner import recipe_path

    feature_mode = experiment.get("feature_mode", "morgan_descriptors")
    selected_recipe = recipe_path(feature_mode)
    commit = experiment.get("execution_git_commit", "")
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("MLP execution source commit missing")
    sources = experiment.get("implementation_sha256", {})
    if set(sources) != IMPLEMENTATIONS:
        raise ValueError("MLP implementation receipts incomplete")
    current = {
        name: digest(Path(__file__).with_name(name).read_bytes()) for name in sources
    }
    allowed = sources == current
    if not allowed and feature_mode == "morgan_descriptors":
        # Exact original source vector remains replayable after an additive mode.
        original = {
            name: digest(
                subprocess.check_output(
                    [
                        "git",
                        "show",
                        f"{ORIGINAL_EXECUTION_COMMIT}:research/maplight-fixed/{name}",
                    ],
                    cwd=ROOT,
                )
            )
            for name in sources
        }
        original_recipe = subprocess.check_output(
            ["git", "show", f"{ORIGINAL_EXECUTION_COMMIT}:{RECIPE.relative_to(ROOT)}"],
            cwd=ROOT,
        )
        allowed = sources == original and digest(original_recipe) == recipe_hash
    if not allowed:
        raise ValueError("MLP current or explicitly frozen source vector differs")
    for name, expected in sources.items():
        committed = subprocess.check_output(
            ["git", "show", f"{commit}:research/maplight-fixed/{name}"], cwd=ROOT
        )
        if digest(committed) != expected:
            raise ValueError(f"MLP execution/current scientific source differs: {name}")
    committed = subprocess.check_output(
        ["git", "show", f"{commit}:{selected_recipe.relative_to(ROOT)}"], cwd=ROOT
    )
    if digest(committed) != recipe_hash:
        raise ValueError("MLP execution recipe differs")


def contrast(
    candidate: dict[str, Any],
    reference: dict[str, Any],
    paired: dict[str, Any],
    *,
    incumbent: bool,
) -> dict[str, Any]:
    denominator = reference["macro_bootstrap_mean_st_rae"]
    numerator = candidate["macro_bootstrap_mean_st_rae"]
    harms = {
        endpoint: candidate["endpoints"][endpoint]["component_mae"]
        - reference["endpoints"][endpoint]["component_mae"]
        for endpoint in ENDPOINTS
    }
    if (
        not np.isfinite(
            [
                denominator,
                numerator,
                *harms.values(),
                paired["lower_95"],
                paired["upper_95"],
            ]
        ).all()
        or denominator <= 0
        or numerator < 0
        or paired["lower_95"] > paired["upper_95"]
    ):
        raise ValueError("Invalid comparison denominator, harms or paired interval")
    gain = (denominator - numerator) / denominator
    return {
        "relative_primary_gain": gain,
        "endpoint_component_mae_harms": harms,
        "maximum_endpoint_component_mae_harm": max(harms.values()),
        "paired_family": paired,
        "gate_this_seed": bool(
            (not incumbent or gain >= 0.02)
            and paired["upper_95"] < 0
            and max(harms.values()) <= 0.02
        ),
    }


def decide(
    repeats: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str] | None]:
    if [repeat["seed"] for repeat in repeats] != list(SEEDS):
        raise ValueError("Both prescribed seeds required in order")
    decisions = {}
    qualified = []
    for arm, variant in CANDIDATES:
        eligible = all(passes_seed(repeat, arm, variant) for repeat in repeats)
        decisions[f"{arm}_{variant}"] = {
            "supported_for_interim_recommendation": eligible
        }
        if eligible:
            qualified.append((arm, variant))
    # Stable enumeration gives exact ties to direct before real, then raw before affine.
    chosen = (
        min(
            qualified,
            key=lambda item: repeats[0]["scores"][item[0]][item[1]][
                "macro_bootstrap_mean_st_rae"
            ],
        )
        if qualified
        else None
    )
    return decisions, None if chosen is None else {
        "arm": chosen[0],
        "variant": chosen[1],
    }


def passes_seed(repeat: dict[str, Any], arm: str, variant: str) -> bool:
    return bool(
        repeat["comparisons"][arm][variant]["incumbent"]["gate_this_seed"]
        and (
            arm == "direct"
            or all(
                repeat["comparisons"][arm][variant][control]["gate_this_seed"]
                for control in ("direct", "shuffled_aux")
            )
        )
    )


def first_seed_futility(repeat: dict[str, Any]) -> dict[str, Any]:
    """Prespecified stop/continue evidence only; never select or release a model."""
    if repeat.get("seed") != SEEDS[0] or repeat.get("feature_mode") != "morgan_only":
        raise ValueError("Futility applies only to the first Morgan-only repeat")
    return {
        "stop_repeat_two_for_futility": not any(
            passes_seed(repeat, arm, variant) for arm, variant in CANDIDATES
        ),
        "selected_supported_variant": None,
        "release_authorized": False,
        "final_promotion": False,
        "scope": "Preliminary first-seed decision; any continuation requires all105 second-seed fits and both-seed gates.",
    }


def authenticate_mlp(
    directory: Path,
    data: Any,
    features: np.ndarray,
    auxiliary: np.ndarray,
    auxiliary_mask: np.ndarray,
    seed: int,
    recipe: dict[str, Any],
    recipe_hash: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Reconstruct all requested populations/payloads and saved OOF without network fits."""
    from competition_mlp_runner import prepare_arrays, seed_for, stopping_split
    from competition_runner import affine_fit

    raw = {
        name: (directory / name).read_bytes()
        for name in ("experiment.json", "result.json", "resources.json")
    }
    experiment, result, resources = (json.loads(raw[name]) for name in raw)
    hashes = {name: digest(value) for name, value in raw.items()}
    if (
        result.get("schema") != "cypshift.phase3.mlp_auxiliary_result.v1"
        or result.get("status") != "complete"
        or result.get("completed_fits") != 105
        or result.get("reserved_numeric_targets_opened") != 0
        or result.get("experiment_sha256") != hashes["experiment.json"]
        or result.get("release_eligible") is not False
        or result.get("final_promotion") is not False
    ):
        raise ValueError("Incomplete or invalid MLP result")
    resource_fields = (
        "occupied_wall_seconds",
        "invocation_cpu_core_hours",
        "prior_seed_occupied_wall_seconds",
        "prior_seed_cpu_core_hours",
        "prior_program_cpu_core_hours",
    )
    if any(
        not np.isfinite(resources.get(key, np.nan)) or resources[key] < 0
        for key in resource_fields
    ):
        raise ValueError("MLP resource accounting is negative or nonfinite")
    if (
        resources.get("status") != "complete"
        or not 0
        <= resources.get("occupied_wall_seconds", np.inf)
        + resources.get("prior_seed_occupied_wall_seconds", np.inf)
        <= recipe["budgets"]["occupied_job_wall_seconds_per_seed"]
        or not 0
        <= resources.get("invocation_cpu_core_hours", np.inf)
        + resources.get("prior_seed_cpu_core_hours", np.inf)
        <= recipe["budgets"]["CPU_core_hours_per_seed"]
        or not 0
        <= resources.get("prior_program_cpu_core_hours", np.inf)
        + resources.get("invocation_cpu_core_hours", np.inf)
        <= recipe["budgets"]["CPU_core_hours_program"]
    ):
        raise ValueError("MLP resource completion/budget differs")
    outer, inner = balanced_nested_folds(data.groups, data.training_mask, seed)
    common = {
        "seed": seed,
        "names": list(data.names),
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
    }
    for key, expected in common.items():
        if result.get(key) != expected or experiment.get(key) != expected:
            raise ValueError(f"MLP population differs: {key}")
    if (
        result.get("outer_fold") != outer.tolist()
        or result.get("inner_fold") != inner.tolist()
    ):
        raise ValueError("MLP family folds differ")
    for key, expected in {
        "recipe_sha256": recipe_hash,
        "source_receipts": data.receipts,
        "data_manifest_sha256": recipe["data_manifest_sha256"],
        "auxiliary_records_sha256": recipe["auxiliary_records_sha256"],
        "cpu_runtime": recipe["cpu_runtime_versions"],
    }.items():
        if experiment.get(key) != expected:
            raise ValueError(f"MLP scientific identity differs: {key}")
    feature_mode = recipe.get("feature_mode", "morgan_descriptors")
    if any(
        record.get("feature_mode", "morgan_descriptors") != feature_mode
        for record in (experiment, result)
    ):
        raise ValueError("MLP representation identity differs")
    if feature_mode == "morgan_only" and np.any(features[:, 4096:] != 0):
        raise ValueError("Morgan-only representation contains descriptor values")
    if not np.array_equal(
        read_array(experiment["features"], directory), features, equal_nan=True
    ):
        raise ValueError("MLP regenerated raw features differ")
    runtime = experiment["gpu_runtime_receipt"]
    if (
        runtime["sha256"] != recipe["gpu_runtime_receipt_sha256"]
        or digest(Path(runtime["path"]).read_bytes()) != runtime["sha256"]
    ):
        raise ValueError("MLP GPU runtime authentication differs")
    verify_sources(experiment, recipe_hash)
    entries = result["fit_receipts"]
    receipts = {(r["arm"], r["outer"], r["inner"], r["role"]): r for r in entries}
    expected_keys = {
        (a, f, i, role)
        for a in ARMS
        for f in range(5)
        for i in range(3)
        for role in ("stop", "refit")
    }
    expected_keys |= {(a, f, -1, "outer") for a in ARMS for f in range(5)}
    if len(entries) != 105 or set(receipts) != expected_keys:
        raise ValueError("MLP requires exactly 105 distinct fit requests")
    if len({r["path"] for r in entries}) != 105:
        raise ValueError("MLP fit receipt path reused")
    all_calibrations = result["calibrations"]
    calibrations = {(r["arm"], r["outer"], r["endpoint"]): r for r in all_calibrations}
    if len(all_calibrations) != 60 or set(calibrations) != {
        (a, f, c) for a in ARMS for f in range(5) for c in range(4)
    }:
        raise ValueError("MLP calibration cells differ")
    predictions = {arm: {} for arm in ARMS}
    if set(result["oof"]) != {f"{a}_{v}" for a in ARMS for v in VARIANTS}:
        raise ValueError("MLP OOF variants differ")
    for arm in ARMS:
        for variant in VARIANTS:
            value = read_array(result["oof"][f"{arm}_{variant}"], directory)
            if (
                value.shape != data.point.shape
                or value.dtype != np.float64
                or not np.isfinite(value).all()
            ):
                raise ValueError("MLP OOF shape/dtype/finiteness differs")
            predictions[arm][variant] = value
    paired_streams = {}

    def fit_evidence(
        arm: str,
        fold: int,
        stage: int,
        role: str,
        train: np.ndarray,
        predict: np.ndarray,
        stop: np.ndarray | None,
        epochs: int,
        lineage: dict[str, Any],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        entry = receipts[arm, fold, stage, role]
        receipt_path = Path(entry["path"])
        if not receipt_path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("MLP worker receipt escapes candidate directory")
        receipt_raw = receipt_path.read_bytes()
        if digest(receipt_raw) != entry["sha256"]:
            raise ValueError("MLP worker receipt hash differs")
        receipt = json.loads(receipt_raw)
        request_path = receipt_path.parent.parent / "request.json"
        request_raw = request_path.read_bytes()
        request = json.loads(request_raw)
        if (
            digest(request_raw) != entry["request_sha256"]
            or receipt["request_sha256"] != entry["request_sha256"]
        ):
            raise ValueError("MLP worker request hash differs")
        payloads, transforms = prepare_arrays(
            features,
            data.point,
            data.training_mask,
            auxiliary,
            auxiliary_mask,
            train,
            predict,
            stop,
            arm,
            seed_for(seed, fold, stage, role + "-shuffle"),
        )
        expected_identity = {
            **experiment,
            **lineage,
            "train": train.tolist(),
            "predict": predict.tolist(),
            "stop": None if stop is None else stop.tolist(),
            "transforms": transforms,
            "outer": fold,
            "inner": stage,
            "role": role,
        }
        expected_fields = {
            "schema": "cypshift.mlp.fit.v1",
            "identity": expected_identity,
            "arm": arm,
            "mode": "fixed" if stop is None else "stopped",
            "epochs": epochs,
            "hyperparameters": dict(
                recipe["hyperparameters"], aux_weight=0.0 if arm == "direct" else 0.25
            ),
            "worker_sha256": experiment["implementation_sha256"][
                "competition_mlp_worker.py"
            ],
            "runtime_receipt": runtime,
            **{
                key: seed_for(seed, fold, stage, role + "-" + key)
                for key in ("model_seed", "batch_seed", "dropout_seed")
            },
        }
        if any(
            request.get(key) != expected for key, expected in expected_fields.items()
        ):
            raise ValueError(
                "MLP requested population, preprocessing, lineage or learner differs"
            )
        if set(request["files"]) != set(payloads):
            raise ValueError("MLP fit payload fields differ")
        for name, expected in payloads.items():
            actual = read_array(request["files"][name], directory)
            if actual.dtype != expected.dtype or not np.array_equal(actual, expected):
                raise ValueError(
                    f"MLP fit payload differs from training-only reconstruction: {name}"
                )
        if (
            receipt.get("schema") != "cypshift.mlp.fit_receipt.v1"
            or receipt.get("finite_loss") is not True
            or not 0
            <= receipt.get("reload_parity", {}).get("maximum_absolute_error", np.inf)
            <= 1e-6
            or receipt["reload_parity"].get("model_and_optimizer_state_exact")
            is not True
            or type(receipt.get("selected_epoch")) is not int
            or not 1 <= receipt["selected_epoch"] <= epochs
            or (stop is None and receipt["selected_epoch"] != epochs)
        ):
            raise ValueError("MLP worker completion/epoch/reload evidence invalid")
        for key in (
            "selected_epoch",
            "initial_state_sha256",
            "batch_order_epoch_sha256",
        ):
            if entry.get(key) != receipt.get(key):
                raise ValueError("MLP summarized worker evidence differs")
        if (
            not Path(receipt["checkpoint"]["path"])
            .resolve()
            .is_relative_to(directory.resolve())
            or digest(Path(receipt["checkpoint"]["path"]).read_bytes())
            != receipt["checkpoint"]["sha256"]
        ):
            raise ValueError("MLP saved checkpoint differs")
        for key in ("identity", "arm", "mode", "hyperparameters", "worker_sha256"):
            if receipt.get(key) != request[key]:
                raise ValueError("MLP worker executed request identity differs")
        if (
            receipt.get("status") != "complete"
            or receipt.get("runtime_receipt_sha256") != runtime["sha256"]
        ):
            raise ValueError("MLP worker execution/runtime incomplete")
        epochs_run = receipt.get("epochs_run")
        steps_per_epoch = (len(train) + 127) // 128
        if (
            type(epochs_run) is not int
            or not receipt["selected_epoch"] <= epochs_run <= epochs
            or receipt.get("optimizer_steps") != epochs_run * steps_per_epoch
            or receipt.get("checkpoint_optimizer_steps")
            != receipt["selected_epoch"] * steps_per_epoch
        ):
            raise ValueError("MLP optimizer work/epoch count differs")
        history = receipt.get("direct_stopping_mae_by_epoch")
        if stop is None:
            if (
                history != []
                or receipt.get("selected_stopping_mae") is not None
                or epochs_run != epochs
            ):
                raise ValueError("Fixed MLP fit used stopping assessment")
        else:
            if len(history) != epochs_run or not np.isfinite(history).all():
                raise ValueError("MLP stopping history invalid")
            best, best_epoch, stale = np.inf, 0, 0
            for epoch, score in enumerate(history, 1):
                if score < best:
                    best, best_epoch, stale = score, epoch, 0
                else:
                    stale += 1
                if stale == 20 and epoch != epochs_run:
                    raise ValueError("MLP continued beyond frozen patience")
            if (
                best_epoch != receipt["selected_epoch"]
                or best != receipt["selected_stopping_mae"]
                or (epochs_run < epochs and stale != 20)
            ):
                raise ValueError(
                    "MLP stopping choice differs from earliest strict improvement"
                )
        if receipt.get("seeds") != {
            key: request[key] for key in ("model_seed", "batch_seed", "dropout_seed")
        }:
            raise ValueError("MLP worker RNG seeds differ")
        actual_runtime = receipt.get("runtime", {})
        if (
            any(
                actual_runtime.get(k) != v
                for k, v in {
                    "python": "3.12.3",
                    "numpy": "1.26.4",
                    "torch": "2.12.0+rocm7.14.0",
                    "hip": "7.14.60850",
                    "closure_sha256": json.loads(Path(runtime["path"]).read_bytes())[
                        "artifact_hashes"
                    ]["resolved-closure.json"],
                }.items()
            )
            or actual_runtime.get("architecture", "").split(":")[0] != "gfx1100"
        ):
            raise ValueError("MLP actual GPU runtime differs")
        if (
            receipt.get("cpu_threads") != 1
            or receipt.get("gpu_allocator_cap_bytes") != 2147483648
            or not 0 <= receipt.get("peak_reserved_bytes", np.inf) <= 2147483648
        ):
            raise ValueError("MLP worker resource attestation differs")
        batches = receipt["batch_order_epoch_sha256"]
        rng = np.random.default_rng(request["batch_seed"])
        expected_batches = [
            digest(rng.permutation(len(train)).astype("int64").tobytes())
            for _ in range(epochs_run)
        ]
        if batches != expected_batches:
            raise ValueError("MLP batch streams differ from requested seed/population")
        if not batches or any(
            not re.fullmatch("[0-9a-f]{64}", h)
            for h in [receipt["initial_state_sha256"], *batches]
        ):
            raise ValueError("MLP RNG stream evidence invalid")
        stream_key = (fold, stage, role)
        if stream_key in paired_streams:
            init, other = paired_streams[stream_key]
            common_prefix = min(len(batches), len(other))
            if (
                init != receipt["initial_state_sha256"]
                or batches[:common_prefix] != other[:common_prefix]
            ):
                raise ValueError("MLP matched arm initialization/batch streams differ")
        else:
            paired_streams[stream_key] = (receipt["initial_state_sha256"], batches)
        prediction = read_array(receipt["predictions"], directory)
        if (
            prediction.shape != (len(predict), 4)
            or prediction.dtype != np.float32
            or not np.isfinite(prediction).all()
        ):
            raise ValueError("MLP saved fit prediction invalid")
        if stop is not None:
            # The worker scores all stopping rows in float32. Reduction order can
            # differ on GPU, so this prediction-to-history check uses the declared
            # 1e-6 absolute/relative portability tolerance.
            errors = np.abs(prediction - payloads["stop_direct_y"])
            mask = payloads["stop_direct_mask"]
            selected_mae = float(
                np.mean([errors[mask[:, col], col].mean() for col in range(4)])
            )
            if not np.allclose(
                selected_mae,
                [receipt["selected_stopping_mae"], min(history)],
                atol=1e-6,
                rtol=1e-6,
            ):
                raise ValueError(
                    "MLP selected stopping score differs from saved predictions"
                )
        summary = {
            key: entry[key]
            for key in (
                "path",
                "sha256",
                "request_sha256",
                "selected_epoch",
                "initial_state_sha256",
                "batch_order_epoch_sha256",
            )
        }
        return prediction.astype(np.float64), summary

    for arm in ARMS:
        for fold in range(5):
            train_outer, held_outer = (
                np.flatnonzero(outer != fold),
                np.flatnonzero(outer == fold),
            )
            inner_oof = np.full(data.point.shape, np.nan)
            stopped = []
            for stage in range(3):
                train = np.flatnonzero((outer != fold) & (inner[fold] != stage))
                held = np.flatnonzero((outer != fold) & (inner[fold] == stage))
                fitting, stopping = stopping_split(
                    data.groups,
                    data.training_mask,
                    train,
                    seed_for(seed, fold, stage, "stopping"),
                )
                _, receipt = fit_evidence(
                    arm, fold, stage, "stop", fitting, stopping, stopping, 200, {}
                )
                stopped.append(receipt)
                prediction, _ = fit_evidence(
                    arm,
                    fold,
                    stage,
                    "refit",
                    train,
                    held,
                    None,
                    receipt["selected_epoch"],
                    {"stopping_receipt": receipt},
                )
                inner_oof[held] = prediction
            prediction, _ = fit_evidence(
                arm,
                fold,
                -1,
                "outer",
                train_outer,
                held_outer,
                None,
                int(np.median([r["selected_epoch"] for r in stopped])),
                {"stopping_receipts": stopped},
            )
            if not np.array_equal(prediction, predictions[arm]["raw"][held_outer]):
                raise ValueError("MLP raw OOF differs from authenticated outer fits")
            for col in range(4):
                cell = calibrations[arm, fold, col]
                if not np.array_equal(
                    read_array(cell["inner_oof"], directory), inner_oof[train_outer]
                ):
                    raise ValueError(
                        "MLP calibration OOF differs from authenticated inner refits"
                    )
                eligible = (outer != fold) & data.metric_mask[:, col]
                expected = affine_fit(
                    inner_oof[eligible, col],
                    data.low[eligible, col],
                    data.high[eligible, col],
                )
                if not np.allclose(
                    expected, [cell["slope"], cell["intercept"]], atol=1e-12, rtol=1e-12
                ):
                    raise ValueError(
                        "MLP calibration differs from inner-only reconstruction"
                    )
                if not np.array_equal(
                    cell["slope"] * prediction[:, col] + cell["intercept"],
                    predictions[arm]["affine"][held_outer, col],
                ):
                    raise ValueError(
                        "MLP affine OOF differs from authenticated calibration"
                    )
    return (
        {"experiment": experiment, "result": result, "resources": resources},
        predictions,
        hashes,
    )


def compare_seed(
    data: Any,
    features: np.ndarray,
    auxiliary: np.ndarray,
    auxiliary_mask: np.ndarray,
    candidate: Path,
    reference: Path,
    seed: int,
    recipe: dict[str, Any],
    recipe_hash: str,
) -> dict[str, Any]:
    meta, predictions, hashes = authenticate_mlp(
        candidate, data, features, auxiliary, auxiliary_mask, seed, recipe, recipe_hash
    )
    incumbent_meta, incumbent_arrays, incumbent_hashes = authenticate_mae(
        reference, data, seed, reference=True
    )
    if meta["experiment"]["cpu_runtime"] != incumbent_meta["experiment"]["runtime"]:
        raise ValueError("MLP CPU science runtime differs from matched MAE")
    args = (
        np.asarray(data.names),
        np.asarray(data.groups),
        data.point,
        data.low,
        data.high,
    )
    incumbent_scores = {}
    for variant, field in (
        ("baseline", "baseline"),
        ("calibrated", "candidate_scores"),
    ):
        score = direct_scores(*args, incumbent_arrays[variant])
        if not _close(score, incumbent_meta["result"][field]):
            raise ValueError("Recomputed incumbent score differs")
        incumbent_scores[variant] = score
    scores = {
        arm: {
            variant: direct_scores(*args, predictions[arm][variant])
            for variant in VARIANTS
        }
        for arm in ARMS
    }
    if not _close(scores, meta["result"]["scores"]):
        raise ValueError("Recomputed MLP scores differ")
    comparisons = {arm: {} for arm in ARMS[:2]}
    paired_controls = {}
    for variant in VARIANTS:
        paired_controls[variant] = {}
        for arm in ARMS[:2]:
            paired = paired_family_difference(
                *args, predictions[arm][variant], incumbent_arrays["calibrated"]
            )
            comparisons[arm][variant] = {
                "incumbent": contrast(
                    scores[arm][variant],
                    incumbent_scores["calibrated"],
                    paired,
                    incumbent=True,
                )
            }
        for control in ("direct", "shuffled_aux"):
            paired = paired_family_difference(
                *args, predictions["real_aux"][variant], predictions[control][variant]
            )
            paired_controls[variant][control] = paired
            comparisons["real_aux"][variant][control] = contrast(
                scores["real_aux"][variant],
                scores[control][variant],
                paired,
                incumbent=False,
            )
    if not _close(paired_controls, meta["result"]["paired_auxiliary_controls"]):
        raise ValueError("Recomputed MLP paired control evidence differs")
    return {
        "seed": seed,
        "feature_mode": recipe.get("feature_mode", "morgan_descriptors"),
        "input_hashes": {"mlp": hashes, "incumbent": incumbent_hashes},
        "scores": scores,
        "incumbent_scores": incumbent_scores,
        "comparisons": comparisons,
        "authenticated_joint_fits": 105,
        "calibrations_reconstructed": 60,
    }


def compare(
    source: Path,
    auxiliary_path: Path,
    candidates: tuple[Path, Path],
    references: tuple[Path, Path],
    output: Path,
    feature_mode: str = "morgan_descriptors",
) -> dict[str, Any]:
    from competition_mlp_runner import build_features, load_auxiliary

    output = output.resolve()
    if output.exists():
        raise FileExistsError("Comparison output already exists")
    if any((parent / ".git").exists() for parent in output.parents):
        raise ValueError("Comparison output must be outside Git")
    recipe, recipe_hash = recipe_for(source, feature_mode)
    data = load_development(source)
    auxiliary, mask = load_auxiliary(
        auxiliary_path, data, recipe["auxiliary_records_sha256"]
    )
    features = build_features(data, feature_mode)
    repeats = [
        compare_seed(
            data,
            features,
            auxiliary,
            mask,
            candidates[i],
            references[i],
            seed,
            recipe,
            recipe_hash,
        )
        for i, seed in enumerate(SEEDS)
    ]
    decisions, selected = decide(repeats)
    report = {
        "schema": "cypshift.phase3.mlp_auxiliary_comparison.v1",
        "status": "complete",
        "scope": "Internal development comparison; no network refits or release. Paired intervals are unadjusted across prespecified comparisons.",
        "prospective_recipe_sha256": recipe_hash,
        "feature_mode": feature_mode,
        "comparison_implementation_sha256": digest(Path(__file__).read_bytes()),
        "development_manifest_sha256": recipe["data_manifest_sha256"],
        "source_receipts": data.receipts,
        "development_molecules": len(data.names),
        "families": len(set(data.groups)),
        "repeats": repeats,
        "decisions": decisions,
        "selected_supported_variant": selected,
        "incumbent_reference": "same-seed MAE/calibrated",
        "shuffled_control_eligible": False,
        "final_promotion": False,
        "release_authorized": False,
        "reserved_numeric_targets_opened": 0,
    }
    raw = (
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o444)
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return report


def main() -> None:
    from competition_mlp_runner import FEATURE_MODES

    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "development",
        "auxiliary-records",
        "candidate-first",
        "candidate-second",
        "reference-first",
        "reference-second",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--feature-mode", choices=FEATURE_MODES, default=FEATURE_MODES[0]
    )
    args = parser.parse_args()
    report = compare(
        args.development,
        args.auxiliary_records,
        (args.candidate_first, args.candidate_second),
        (args.reference_first, args.reference_second),
        args.output,
        args.feature_mode,
    )
    print(
        json.dumps(
            {
                "decisions": report["decisions"],
                "selected_supported_variant": report["selected_supported_variant"],
            }
        )
    )


if __name__ == "__main__":
    main()
