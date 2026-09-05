#!/usr/bin/env python3
"""Matched, development-only RMSE/MAE comparison; never a release command."""

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
from competition_data import DevelopmentData, balanced_nested_folds, load_development
from competition_metrics import (
    ENDPOINTS,
    direct_scores,
    interval_distance,
    paired_family_difference,
)

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "benchmarks/openadmet_cyp_2026"
RECIPE = PUBLIC / "phase3_rmse_ablation_v1.json"
CORRECTED_RECIPE = PUBLIC / "phase3_corrected_counts_ablation_v1.json"
SEEDS = (20260905, 20260906)
VARIANTS = ("baseline", "calibrated")
BANDS = (
    ("lt4.3", -np.inf, 4.3),
    ("4.3to5", 4.3, 5),
    ("5to6", 5, 6),
    ("ge6", 6, np.inf),
)


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _recipe(source: Path) -> tuple[dict[str, Any], str]:
    raw = RECIPE.read_bytes()
    recipe = json.loads(raw)
    expected = {
        "schema": "cypshift.phase3.rmse_ablation.v1",
        "status": "prespecified_before_RMSE_outcomes",
        "seeds": list(SEEDS),
        "data_manifest_sha256": _hash((source / "manifest.json").read_bytes()),
        "new_fits_per_seed": 80,
        "recommendation_gate_each_seed": {
            "max_endpoint_component_mae_harm": 0.02,
            "paired_family_primary_upper95_max_exclusive": 0,
            "relative_macro_primary_gain_over_calibrated_incumbent_min": 0.02,
        },
    }
    if any(recipe.get(key) != value for key, value in expected.items()):
        raise ValueError("Prospective recipe or development manifest differs")
    diagnostics = recipe["potency_diagnostics"]
    if (
        diagnostics["bands"] != ["<4.3", "4.3<=pIC50<5", "5<=pIC50<6", ">=6"]
        or diagnostics["comparator"] != "Same-seed calibrated-MAE incumbent"
        or diagnostics["mechanism_claim_requires_each_seed"]
        != {
            "macro_ge6_interval_mae_improvement_min": 0.1,
            "macro_lt4_3_interval_mae_harm_max": 0.05,
        }
        or recipe["model"]
        != {
            "loss_function": "RMSE",
            "random_strength": 2,
            "random_seed": 1,
            "task_type": "CPU",
            "thread_count": 16,
            "allow_writing_files": False,
            "learning_rate": 0.03,
            "iterations": 1000,
            "depth": 6,
        }
        or recipe["affine"]["slope_bounds"] != [0.8, 1.2]
        or recipe["affine"]["intercept_bounds"] != [-0.25, 0.25]
        or recipe["nested_folds"]["outer"] != 5
        or recipe["nested_folds"]["inner"] != 3
    ):
        raise ValueError("Prospective recipe scientific criteria differ")
    return recipe, _hash(raw)


def _close(actual: Any, expected: Any) -> bool:
    """Allow only declared 1e-12 numerical portability, never missing fields."""
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_close(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and bool(
            np.isclose(actual, expected, rtol=1e-12, atol=1e-12)
        )
    return actual == expected


def corrected_recipe(source: Path) -> tuple[dict[str, Any], str]:
    from competition_runner import corrected_recipe as validate

    return validate(source)


def _corrected_fit_evidence(
    directory: Path,
    data: DevelopmentData,
    experiment: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Rebuild features independently and bind every expected fit/prediction receipt."""
    from competition_features import featurize_corrected_counts
    from competition_runner import affine_fit

    matrix = featurize_corrected_counts(data.raw_smiles)
    counts = matrix[:, :2048]
    if (
        matrix.shape != data.legacy_features.shape
        or matrix.dtype != np.float64
        or not np.isfinite(counts).all()
        or np.any(counts < 0)
        or np.any(counts > 2**31 - 1)
        or np.any(counts != counts.astype(np.int64))
    ):
        raise ValueError("Invalid regenerated corrected count matrix")
    if not np.array_equal(
        (counts.astype(np.int64) + 128) % 256 - 128, data.legacy_features[:, :2048]
    ) or not np.array_equal(
        matrix[:, 2048:], data.legacy_features[:, 2048:], equal_nan=True
    ):
        raise ValueError("Regenerated correction changes legacy feature semantics")

    def canonical(value: Any) -> bytes:
        return (
            json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
        ).encode()

    changed = counts != data.legacy_features[:, :2048]
    receipt = {
        "mode": "corrected_counts",
        "matrix_sha256": _hash(matrix.tobytes()),
        "shape": list(matrix.shape),
        "dtype": str(matrix.dtype),
        "ordered_raw_identity_sha256": _hash(
            canonical(list(zip(data.molecule_ids, data.raw_smiles, strict=True)))
        ),
        "all_legacy_count_bytes_reproduced": True,
        "erg_descriptors_equal_including_nan": True,
        "changed_count_cells": int(changed.sum()),
        "changed_molecules": int(np.any(changed, axis=1).sum()),
    }
    if (
        experiment.get("feature_receipt") != receipt
        or result.get("feature_receipt") != receipt
    ):
        raise ValueError("Corrected feature receipt differs from regeneration")
    outer, inner = np.asarray(experiment["outer"]), np.asarray(experiment["inner"])
    calibration = {
        (cell["fold"], cell["endpoint"]): cell for cell in result["outer_calibration"]
    }
    for fold in range(5):
        for col in range(4):
            inner_predictions = np.full(len(data.names), np.nan)
            for stage in range(4):
                train = np.flatnonzero(
                    (outer != fold)
                    & data.training_mask[:, col]
                    & ((inner[fold] != stage) if stage < 3 else True)
                )
                predict = np.flatnonzero(
                    ((outer != fold) & (inner[fold] == stage))
                    if stage < 3
                    else outer == fold
                )
                material = {
                    "experiment_sha256": result["experiment_sha256"],
                    "parameters": experiment["parameters"],
                    "features_sha256": receipt["matrix_sha256"],
                    "features_shape": list(matrix.shape),
                    "features_dtype": str(matrix.dtype),
                    "training_indices": train.tolist(),
                    "prediction_indices": predict.tolist(),
                    "training_targets_sha256": _hash(
                        np.ascontiguousarray(data.point[train, col]).tobytes()
                    ),
                }
                key = _hash(canonical(material))
                cell = directory / "fits" / key
                fit = json.loads((cell / "receipt.json").read_bytes())
                prediction_bytes = (cell / "prediction.npy").read_bytes()
                if (
                    fit.get("key") != key
                    or fit.get("inputs") != material
                    or fit.get("prediction_sha256") != _hash(prediction_bytes)
                ):
                    raise ValueError(
                        "Corrected fit receipt differs from regenerated feature identity"
                    )
                resolved = fit.get("resolved_parameters", {})
                if (
                    resolved.get("loss_function") != "MAE"
                    or resolved.get("depth") != 6
                    or resolved.get("iterations") != 1000
                    or resolved.get("random_seed") != 1
                    or resolved.get("random_strength") != 2
                    or resolved.get("task_type") != "CPU"
                    or not np.isclose(
                        resolved.get("learning_rate", np.nan), 0.03, atol=1e-8, rtol=0
                    )
                ):
                    raise ValueError("Corrected fit resolved learner settings differ")
                predictions = np.load(io.BytesIO(prediction_bytes), allow_pickle=False)
                if (
                    predictions.shape != (len(predict),)
                    or not np.isfinite(predictions).all()
                ):
                    raise ValueError("Invalid corrected fit predictions")
                if stage == 3:
                    with np.load(directory / "oof.npz", allow_pickle=False) as oof:
                        if not np.array_equal(
                            predictions, oof["baseline"][predict, col]
                        ):
                            raise ValueError(
                                "Corrected OOF differs from outer fit receipt"
                            )
                    eligible = (outer != fold) & np.isfinite(data.point[:, col])
                    expected_affine = affine_fit(
                        inner_predictions[eligible],
                        data.low[eligible, col],
                        data.high[eligible, col],
                    )
                    actual_affine = calibration[fold, col]
                    if not np.allclose(
                        expected_affine,
                        [actual_affine["slope"], actual_affine["intercept"]],
                        rtol=1e-12,
                        atol=1e-12,
                    ):
                        raise ValueError(
                            "Corrected affine differs from authenticated inner OOF calibration"
                        )
                else:
                    inner_predictions[predict] = predictions


def _verify_sources(experiment: dict[str, Any], result: dict[str, Any]) -> None:
    commit = result.get("execution_git_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid execution source commit")
    expected_names = {
        "competition_runner.py",
        "competition_data.py",
        "competition_metrics.py",
    }
    if experiment.get("candidate") == "maplight-corrected-counts-inner-oof-affine":
        expected_names |= {"competition_features.py", "maplight_fixed_features.py"}
    if set(experiment.get("implementation", {})) != expected_names:
        raise ValueError("Incomplete experiment implementation receipts")
    for name, expected in experiment["implementation"].items():
        raw = subprocess.check_output(
            ["git", "show", f"{commit}:research/maplight-fixed/{name}"], cwd=ROOT
        )
        if _hash(raw) != expected:
            raise ValueError(f"Execution source hash differs: {name}")
        if (
            name != "competition_runner.py"
            and _hash(Path(__file__).with_name(name).read_bytes()) != expected
        ):
            raise ValueError(f"Comparison scientific source differs: {name}")


def authenticate(
    directory: Path,
    data: DevelopmentData,
    seed: int,
    *,
    reference: bool,
    ablation: str = "rmse",
) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, str]]:
    """Authenticate one completed experiment before any comparison or scoring."""
    if seed not in SEEDS:
        raise ValueError("Only the two frozen seeds are supported")
    if ablation not in {"rmse", "corrected_counts"}:
        raise ValueError("Unknown frozen ablation")
    raw = {
        name: (directory / name).read_bytes()
        for name in ("result.json", "experiment.json", "oof.npz")
    }
    hashes = {name: _hash(value) for name, value in raw.items()}
    result, experiment = (
        json.loads(raw[name]) for name in ("result.json", "experiment.json")
    )
    if (
        result.get("status") != "complete"
        or result.get("reserved_numeric_targets_opened") != 0
        or result.get("fits") != 80
    ):
        raise ValueError("Incomplete or invalid development experiment")
    for name, field in (
        ("experiment.json", "experiment_sha256"),
        ("oof.npz", "oof_sha256"),
    ):
        if result.get(field) != hashes[name]:
            raise ValueError(f"Experiment receipt differs: {name}")
    if reference:
        record = PUBLIC / (
            "phase3_maplight_affine_v1_result.json"
            if seed == SEEDS[0]
            else "phase3_maplight_affine_repeat2_audit.json"
        )
        public_raw = record.read_bytes()
        expected = json.loads(public_raw)
        hashes["public_record_sha256"] = _hash(public_raw)
        if seed == SEEDS[0]:
            for key in (
                "baseline",
                "candidate_scores",
                "decision",
                "paired_family",
                "experiment_sha256",
                "oof_sha256",
                "execution_git_commit",
                "candidate",
                "status",
                "fits",
            ):
                if result.get(key) != expected.get(key):
                    raise ValueError(f"Original MAE public reference differs: {key}")
        elif any(
            hashes.get(name) != value
            for name, value in expected["input_hashes"].items()
        ) or set(expected["input_hashes"]) != set(raw):
            raise ValueError("Original MAE public reference hashes differ")
        if result.get("candidate") != "maplight-inner-oof-affine":
            raise ValueError("Original MAE candidate differs")
    elif ablation == "corrected_counts":
        parameters = {
            "loss_function": "MAE",
            "random_strength": 2,
            "random_seed": 1,
            "task_type": "CPU",
            "thread_count": 16,
            "verbose": 0,
            "allow_writing_files": False,
        }
        for record in (experiment, result):
            if (
                record.get("objective") != "MAE"
                or record.get("parameters") != parameters
                or record.get("candidate")
                != "maplight-corrected-counts-inner-oof-affine"
            ):
                raise ValueError(
                    "Candidate is not the frozen corrected-count MAE ablation"
                )
        recipe_raw = CORRECTED_RECIPE.read_bytes()
        recipe = json.loads(recipe_raw)
        if (
            experiment.get("prospective_recipe_sha256") != _hash(recipe_raw)
            or result.get("prospective_recipe_sha256") != _hash(recipe_raw)
            or experiment.get("compiled_manifest_sha256")
            != recipe["data_manifest_sha256"]
            or result.get("max_cpu_core_hours") != 5
        ):
            raise ValueError("Corrected experiment recipe or budget differs")
        if not 0 <= result.get("budget_accounted_cpu_core_hours", float("inf")) <= 5:
            raise ValueError("Corrected experiment exceeded its accounted CPU budget")
        if not re.fullmatch(r"[0-9a-f]{40}", result.get("execution_git_commit", "")):
            raise ValueError("Invalid execution source commit")
        committed = subprocess.check_output(
            [
                "git",
                "show",
                f"{result['execution_git_commit']}:benchmarks/openadmet_cyp_2026/phase3_corrected_counts_ablation_v1.json",
            ],
            cwd=ROOT,
        )
        if _hash(committed) != _hash(recipe_raw):
            raise ValueError("Corrected recipe differs from execution commit")
    else:
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
        for record in (experiment, result):
            if (
                record.get("objective") != "RMSE"
                or record.get("parameters") != parameters
                or record.get("candidate") != "maplight-rmse-inner-oof-affine"
            ):
                raise ValueError("Candidate is not the frozen RMSE objective ablation")
    outer, inner = balanced_nested_folds(data.groups, data.training_mask, seed=seed)
    for key, value in {
        "seed": seed,
        "source_receipts": data.receipts,
        "molecule_ids": list(data.molecule_ids),
        "groups": list(data.groups),
        "outer": outer.tolist(),
        "inner": inner.tolist(),
    }.items():
        if experiment.get(key) != value:
            raise ValueError(f"Experiment population differs: {key}")
    with np.load(io.BytesIO(raw["oof.npz"]), allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    for key, value in {
        "names": np.asarray(data.names),
        "groups": np.asarray(data.groups),
        "outer": outer,
        "inner": inner,
    }.items():
        if key not in arrays or not np.array_equal(arrays[key], value):
            raise ValueError(f"OOF population differs: {key}")
    for key in VARIANTS:
        if (
            key not in arrays
            or arrays[key].shape != data.point.shape
            or not np.isfinite(arrays[key]).all()
        ):
            raise ValueError("OOF predictions invalid")
    calibrations = result.get("outer_calibration", [])
    if len(calibrations) != 20 or {
        (c["fold"], c["endpoint"]) for c in calibrations
    } != {(f, e) for f in range(5) for e in range(4)}:
        raise ValueError("Outer calibration cells differ")
    for cell in calibrations:
        slope, intercept = cell["slope"], cell["intercept"]
        if not 0.8 <= slope <= 1.2 or not -0.25 <= intercept <= 0.25:
            raise ValueError("Outer calibration parameters invalid")
        take, col = outer == cell["fold"], cell["endpoint"]
        if not np.array_equal(
            arrays["calibrated"][take, col],
            slope * arrays["baseline"][take, col] + intercept,
        ):
            raise ValueError("Outer calibration predictions differ")
    _verify_sources(experiment, result)
    if not reference and ablation == "corrected_counts":
        _corrected_fit_evidence(directory, data, experiment, result)
    return {"experiment": experiment, "result": result}, arrays, hashes


def potency_bands(data: DevelopmentData, prediction: np.ndarray) -> dict[str, Any]:
    """Fixed central-potency strata; endpoint means then equal-endpoint macro."""
    report = {}
    for name, lower, upper in BANDS:
        endpoints = {}
        for col, endpoint in enumerate(ENDPOINTS):
            take = (
                data.metric_mask[:, col]
                & (data.point[:, col] >= lower)
                & (data.point[:, col] < upper)
            )
            errors = interval_distance(
                prediction[take, col], data.low[take, col], data.high[take, col]
            )
            endpoints[endpoint] = {
                "rows": int(take.sum()),
                "families": len(set(np.asarray(data.groups)[take])),
                "interval_mae": float(errors.mean())
                if len(errors) and np.isfinite(errors).all()
                else None,
            }
        supported = all(v["interval_mae"] is not None for v in endpoints.values())
        report[name] = {
            "endpoints": endpoints,
            "macro_interval_mae": float(
                np.mean([v["interval_mae"] for v in endpoints.values()])
            )
            if supported
            else None,
            "all_endpoints_supported": bool(supported),
        }
    return report


def compare_seed(
    data: DevelopmentData,
    candidate: Path,
    reference: Path,
    seed: int,
    *,
    ablation: str = "rmse",
) -> dict[str, Any]:
    candidate_meta, candidate_arrays, candidate_hashes = authenticate(
        candidate, data, seed, reference=False, ablation=ablation
    )
    reference_meta, reference_arrays, reference_hashes = authenticate(
        reference, data, seed, reference=True
    )
    if (
        candidate_meta["experiment"]["runtime"]
        != reference_meta["experiment"]["runtime"]
    ):
        raise ValueError("Matched comparison runtime differs")
    args = (
        np.asarray(data.names),
        np.asarray(data.groups),
        data.point,
        data.low,
        data.high,
    )
    scores, bands = {}, {}
    for role, arrays, meta in (
        (ablation, candidate_arrays, candidate_meta),
        ("mae", reference_arrays, reference_meta),
    ):
        scores[role], bands[role] = {}, {}
        for variant, field in (
            ("baseline", "baseline"),
            ("calibrated", "candidate_scores"),
        ):
            scores[role][variant] = direct_scores(*args, arrays[variant])
            if not _close(meta["result"][field], scores[role][variant]):
                raise ValueError(f"Recomputed result metrics differ: {role}/{variant}")
            bands[role][variant] = potency_bands(data, arrays[variant])
        paired = paired_family_difference(
            *args, arrays["calibrated"], arrays["baseline"]
        )
        if not _close(meta["result"]["paired_family"], paired):
            raise ValueError(f"Recomputed result paired metrics differ: {role}")
    comparisons = {}
    for variant in VARIANTS:
        comparisons[variant] = {}
        for baseline in VARIANTS:
            a, b = scores[ablation][variant], scores["mae"][baseline]
            primary = b["macro_bootstrap_mean_st_rae"]
            if primary <= 0:
                raise ValueError("Nonpositive incumbent primary denominator")
            gain = (primary - a["macro_bootstrap_mean_st_rae"]) / primary
            harms = {
                endpoint: a["endpoints"][endpoint]["component_mae"]
                - b["endpoints"][endpoint]["component_mae"]
                for endpoint in ENDPOINTS
            }
            paired = paired_family_difference(
                *args, candidate_arrays[variant], reference_arrays[baseline]
            )
            changes = {}
            for band, _, _ in BANDS:
                av, bv = (
                    bands[ablation][variant][band]["macro_interval_mae"],
                    bands["mae"][baseline][band]["macro_interval_mae"],
                )
                changes[band] = av - bv if av is not None and bv is not None else None
            comparisons[variant][baseline] = {
                "relative_primary_gain": gain,
                "endpoint_component_mae_harms": harms,
                "maximum_endpoint_component_mae_harm": max(harms.values()),
                "paired_family": paired,
                "macro_interval_mae_changes_by_band": changes,
                "recommendation_gate_this_seed": bool(
                    gain >= 0.02
                    and paired["upper_95"] < 0
                    and max(harms.values()) <= 0.02
                ),
                "tail_mechanism_gate_this_seed": None
                if ablation == "corrected_counts"
                else bool(
                    changes["ge6"] is not None
                    and changes["lt4.3"] is not None
                    and changes["ge6"] <= -0.10
                    and changes["lt4.3"] <= 0.05
                ),
            }
    return {
        "seed": seed,
        "input_hashes": {"candidate": candidate_hashes, "reference": reference_hashes},
        "scores": scores,
        "potency_bands": bands,
        "comparisons": comparisons,
    }


def compare(
    source: Path,
    candidates: tuple[Path, Path],
    references: tuple[Path, Path],
    output: Path,
    *,
    ablation: str = "rmse",
) -> dict[str, Any]:
    """Require both repeats and atomically publish a new readonly private JSON."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Comparison output already exists")
    if any((parent / ".git").exists() for parent in (output.parent, *output.parents)):
        raise ValueError("Comparison output must be outside Git")
    if ablation not in {"rmse", "corrected_counts"}:
        raise ValueError("Unknown frozen ablation")
    recipe, recipe_hash = (
        corrected_recipe(source) if ablation == "corrected_counts" else _recipe(source)
    )
    data = load_development(source)
    repeats = [
        compare_seed(data, candidates[i], references[i], seed, ablation=ablation)
        for i, seed in enumerate(SEEDS)
    ]
    decisions = {}
    for variant in VARIANTS:
        evidence = [repeat["comparisons"][variant]["calibrated"] for repeat in repeats]
        decisions[variant] = {
            "supported_for_interim_recommendation": all(
                v["recommendation_gate_this_seed"] for v in evidence
            ),
            "same_primary_improvement_direction_both_seeds": all(
                v["relative_primary_gain"] > 0 for v in evidence
            ),
            "tail_mechanism_supported_both_seeds": None
            if ablation == "corrected_counts"
            else all(v["tail_mechanism_gate_this_seed"] for v in evidence),
        }
    qualified = [
        v for v in VARIANTS if decisions[v]["supported_for_interim_recommendation"]
    ]
    selected = (
        min(
            qualified,
            key=lambda v: repeats[0]["scores"][ablation][v][
                "macro_bootstrap_mean_st_rae"
            ],
        )
        if qualified
        else None
    )  # Stable VARIANTS order gives an exact tie to raw.
    report = {
        "schema": "cypshift.phase3.matched_objective_comparison.v1",
        "status": "complete",
        "scope": "Internal development evidence, not an official score; no model fits or releases",
        "development_manifest_sha256": _hash((source / "manifest.json").read_bytes()),
        "comparison_implementation_sha256": _hash(Path(__file__).read_bytes()),
        "prospective_recipe_sha256": recipe_hash,
        "prospective_recipe": recipe,
        "development_molecules": len(data.names),
        "families": len(set(data.groups)),
        "source_receipts": data.receipts,
        "repeats": repeats,
        "decisions": decisions,
        "selected_supported_variant": selected,
        "incumbent_reference": "mae/calibrated",
        "tail_mechanism_reference": "mae/calibrated",
        "recommendation_criteria": {
            "minimum_relative_primary_gain_each_seed": 0.02,
            "paired_upper_95_strictly_below": 0,
            "maximum_endpoint_component_mae_harm_each_seed": 0.02,
        },
        "tail_criteria": {
            "minimum_macro_ge6_interval_mae_improvement_each_seed": 0.10,
            "maximum_macro_lt4_3_interval_mae_harm_each_seed": 0.05,
        },
        "final_promotion": False,
        "release_authorized": False,
        "reserved_numeric_targets_opened": 0,
    }
    if ablation == "corrected_counts":
        report.update(
            schema="cypshift.phase3.matched_count_comparison.v1",
            tail_criteria=None,
            tail_mechanism_reference=None,
            ablation=ablation,
        )
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
        os.link(temporary, output)  # Atomic no-clobber publication, including races.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--candidate-first", type=Path, required=True)
    parser.add_argument("--candidate-second", type=Path, required=True)
    parser.add_argument("--reference-first", type=Path, required=True)
    parser.add_argument("--reference-second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ablation", choices=("rmse", "corrected_counts"), default="rmse"
    )
    args = parser.parse_args()
    result = compare(
        args.development,
        (args.candidate_first, args.candidate_second),
        (args.reference_first, args.reference_second),
        args.output,
        ablation=args.ablation,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "decisions": result["decisions"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
