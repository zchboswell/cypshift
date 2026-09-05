"""Phase 3 primary metric and paired family uncertainty, using released bounds.

ST-RAE follows tutorial 858ae63: mask absent central truth, sort molecule names,
sample each endpoint 1000 times with NumPy seed 0, then average endpoint scores.
The separate family bootstrap is a comparison diagnostic, not the official CI.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")


def interval_distance(prediction: Array | float, low: Array, high: Array) -> Array:
    return np.maximum(prediction - high, 0) + np.maximum(low - prediction, 0)


def st_rae(point: Array, low: Array, high: Array, prediction: Array) -> float:
    denominator = float(interval_distance(float(np.mean(point)), low, high).sum())
    if not np.isfinite(denominator) or denominator <= 0:
        raise ValueError("ST-RAE denominator is nonpositive or nonfinite")
    score = float(interval_distance(prediction, low, high).sum()) / denominator
    if not np.isfinite(score):
        raise ValueError("Nonfinite ST-RAE")
    return score


def _endpoint(
    names: NDArray[Any],
    point: Array,
    low: Array,
    high: Array,
    prediction: Array,
) -> tuple[NDArray[np.int64], Array, Array, Array, Array]:
    if any(value.shape != point.shape for value in (names, low, high, prediction)):
        raise ValueError("Endpoint arrays have different shapes")
    if point.ndim != 1 or len(set(names.tolist())) != len(names):
        raise ValueError("Molecule identities must be unique vectors")
    # The public wrapper masks central NaNs only, never missing predictions/bounds.
    selected = np.argsort(names, kind="stable")
    selected = selected[~np.isnan(point[selected])]
    p, lo, hi, pred = (value[selected] for value in (point, low, high, prediction))
    if not len(p) or any(not np.isfinite(v).all() for v in (p, lo, hi, pred)):
        raise ValueError("Empty endpoint or nonfinite eligible values")
    if np.any(lo > hi):
        raise ValueError("Reversed interval bounds")
    return selected, p, lo, hi, pred


def direct_scores(
    names: NDArray[Any],
    groups: NDArray[Any],
    point: Array,
    low: Array,
    high: Array,
    prediction: Array,
    *,
    samples: int = 1000,
) -> dict[str, Any]:
    """Return released primary bootstrap mean plus component-weighted MAE."""
    if samples < 1 or point.shape != (len(names), 4) or groups.shape != names.shape:
        raise ValueError("Invalid score dimensions or bootstrap count")
    if any(v.shape != point.shape for v in (low, high, prediction)):
        raise ValueError("Prediction/bounds matrix shape differs")
    endpoint_results = {}
    all_bootstraps = []
    for column, endpoint in enumerate(ENDPOINTS):
        idx, p, lo, hi, pred = _endpoint(
            names,
            point[:, column],
            low[:, column],
            high[:, column],
            prediction[:, column],
        )
        rng = np.random.default_rng(seed=0)
        bootstrap = np.empty(samples)
        # Sequential draws equal the tutorial's (samples, n) choice matrix.
        for iteration in range(samples):
            draw = rng.choice(len(p), size=len(p), replace=True)
            bootstrap[iteration] = st_rae(p[draw], lo[draw], hi[draw], pred[draw])
        errors = np.abs(pred - p)
        unique_groups, inverse = np.unique(groups[idx], return_inverse=True)
        group_errors = np.bincount(inverse, weights=errors) / np.bincount(inverse)
        endpoint_results[endpoint] = {
            "rows": len(p),
            "groups": len(unique_groups),
            "st_rae": st_rae(p, lo, hi, pred),
            "bootstrap_mean_st_rae": float(bootstrap.mean()),
            "component_mae": float(group_errors.mean()),
            "mae": float(errors.mean()),
        }
        all_bootstraps.append(bootstrap)
    macro = np.mean(all_bootstraps, axis=0)
    return {
        "tutorial_revision": "858ae63ce79934113bccdb7fc65467de5f7b1935",
        "bootstrap_samples": samples,
        "bootstrap_seed": 0,
        "macro_bootstrap_mean_st_rae": float(macro.mean()),
        "macro_component_mae": float(
            np.mean([v["component_mae"] for v in endpoint_results.values()])
        ),
        "endpoints": endpoint_results,
    }


def paired_family_difference(
    names: NDArray[Any],
    groups: NDArray[Any],
    point: Array,
    low: Array,
    high: Array,
    candidate: Array,
    baseline: Array,
    *,
    samples: int = 2000,
    seed: int = 20260906,
) -> dict[str, Any]:
    """Resample whole pooled OOF families jointly across all four endpoints."""
    if samples < 1 or point.shape != (len(names), 4) or groups.shape != names.shape:
        raise ValueError("Invalid paired score dimensions or bootstrap count")
    if any(v.shape != point.shape for v in (low, high, candidate, baseline)):
        raise ValueError("Paired prediction/bounds matrix shape differs")
    unique, inverse = np.unique(groups, return_inverse=True)
    ingredients = []
    for col in range(4):
        idx, p, lo, hi, pred = _endpoint(
            names,
            point[:, col],
            low[:, col],
            high[:, col],
            candidate[:, col],
        )
        if not np.isfinite(baseline[idx, col]).all():
            raise ValueError("Nonfinite baseline prediction")
        difference = interval_distance(pred, lo, hi) - interval_distance(
            baseline[idx, col],
            lo,
            hi,
        )
        ingredients.append((inverse[idx], p, lo, hi, difference))
    rng = np.random.default_rng(seed)
    differences = []
    unsupported = 0
    for _ in range(samples):
        counts = np.bincount(
            rng.choice(len(unique), len(unique)), minlength=len(unique)
        )
        scores = []
        for group_ids, p, lo, hi, diff in ingredients:
            weights = counts[group_ids]
            if weights.sum() == 0:
                break
            mean = float(np.average(p, weights=weights))
            denominator = np.dot(weights, interval_distance(mean, lo, hi))
            if not np.isfinite(denominator) or denominator <= 0:
                break
            scores.append(float(np.dot(weights, diff) / denominator))
        if len(scores) == 4:
            differences.append(float(np.mean(scores)))
        else:
            unsupported += 1
    if unsupported or not differences:
        raise ValueError(f"Unsupported paired family bootstrap draws: {unsupported}")
    return {
        "samples": samples,
        "seed": seed,
        "families": len(unique),
        "candidate_minus_baseline_mean": float(np.mean(differences)),
        "lower_95": float(np.quantile(differences, 0.025)),
        "upper_95": float(np.quantile(differences, 0.975)),
    }


def release_decision(
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any],
    paired: Mapping[str, Any],
    *,
    second_repeat_supports: bool = False,
) -> dict[str, Any]:
    """Distinguish a non-dominated interim challenger from a final promotion."""
    candidate_primary = float(candidate["macro_bootstrap_mean_st_rae"])
    baseline_primary = float(baseline["macro_bootstrap_mean_st_rae"])
    harms = [
        candidate["endpoints"][e]["component_mae"]
        - baseline["endpoints"][e]["component_mae"]
        for e in ENDPOINTS
    ]
    # Zero is a valid perfect ST-RAE, but relative gain from it is undefined.
    improvement = (
        (baseline_primary - candidate_primary) / baseline_primary
        if baseline_primary > 0
        else None
    )
    eligible = candidate_primary < baseline_primary or (
        candidate["macro_component_mae"] < baseline["macro_component_mae"]
    )
    return {
        "release_eligible_on_paired_metrics": eligible,
        "relative_primary_improvement": improvement,
        "maximum_endpoint_component_mae_harm": max(harms),
        "promotion_metric_gate": (
            improvement is not None
            and improvement >= 0.02
            and paired["upper_95"] < 0
            and max(harms) <= 0.02
        ),
        "second_repeat_supports": second_repeat_supports,
        "final_promotion": False,  # Requires frozen ablations and reserved comparison.
    }
