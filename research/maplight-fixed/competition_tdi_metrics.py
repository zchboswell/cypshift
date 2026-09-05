"""Released TDI endpoint-row MCC bootstrap and separate paired-family evidence."""

from __future__ import annotations

from typing import Any

import numpy as np

ENDPOINTS = ("CYP2D6_is_TDI", "CYP3A4_is_TDI")
TUTORIAL_REVISION = "858ae63ce79934113bccdb7fc65467de5f7b1935"


def confusion_mcc(counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized sklearn binary-MCC algebra; degenerate margins return zero."""
    tn, fp, fn, tp = np.moveaxis(np.asarray(counts, dtype=np.float64), -1, 0)
    # Match sklearn's covariance expression rather than changing its convention.
    total = tn + fp + fn + tp
    true0, true1, pred0, pred1 = tn + fp, fn + tp, tn + fn, fp + tp
    numerator = (tn + tp) * total - (true0 * pred0 + true1 * pred1)
    denominator = (total**2 - pred0**2 - pred1**2) * (total**2 - true0**2 - true1**2)
    degenerate = denominator <= 0
    score = np.divide(
        numerator,
        np.sqrt(np.maximum(denominator, 0)),
        out=np.zeros_like(numerator),
        where=~degenerate,
    )
    return score, degenerate


def _validate(
    names: np.ndarray,
    labels: np.ndarray,
    mask: np.ndarray,
    predictions: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    names, labels, mask = np.asarray(names), np.asarray(labels), np.asarray(mask)
    if names.ndim != 1 or len(set(names.tolist())) != len(names) or not len(names):
        raise ValueError("TDI names must be a nonempty unique vector")
    if (
        labels.shape != (len(names), 2)
        or mask.shape != labels.shape
        or mask.dtype != bool
    ):
        raise ValueError("TDI label/mask dimensions or dtype differ")
    if any(p.shape != labels.shape for p in predictions):
        raise ValueError("TDI prediction dimensions differ")
    for value in (labels, *predictions):
        if not np.isfinite(value[mask]).all() or not np.isin(value[mask], [0, 1]).all():
            raise ValueError(
                "TDI eligible labels/predictions must be finite binary values"
            )
    if not mask.any(axis=0).all():
        raise ValueError("TDI endpoint has no eligible truth")
    return names, labels, mask


def _counts(truth: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    return np.bincount(
        2 * truth.astype(np.int64) + prediction.astype(np.int64), minlength=4
    )


def _pooled(counts: np.ndarray) -> dict[str, Any]:
    tn, fp, fn, tp = counts.tolist()

    def ratio(a: float, b: float) -> float:
        return a / b if b else 0.0

    return {
        "mcc": float(confusion_mcc(counts)[0]),
        "accuracy": ratio(tp + tn, tp + tn + fp + fn),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def direct_tdi_scores(
    names: np.ndarray,
    labels: np.ndarray,
    mask: np.ndarray,
    prediction: np.ndarray,
    *,
    samples: int = 1000,
) -> dict[str, Any]:
    """Name-sort, mask per endpoint, RNG0 row bootstrap; public MCC mean and SD."""
    names, labels, mask = _validate(names, labels, mask, (np.asarray(prediction),))
    if samples < 2:
        raise ValueError("At least two TDI bootstrap samples required")
    order = np.argsort(names, kind="stable")
    endpoint_scores, bootstraps = {}, []
    for col, endpoint in enumerate(ENDPOINTS):
        selected = order[mask[order, col]]
        truth, pred = labels[selected, col], prediction[selected, col]
        rng = np.random.default_rng(0)
        counts = np.asarray(
            [
                _counts(truth[draw], pred[draw])
                for draw in (
                    rng.choice(len(selected), size=len(selected), replace=True)
                    for _ in range(samples)
                )
            ]
        )
        scores, degenerate = confusion_mcc(counts)
        endpoint_scores[endpoint] = dict(
            _pooled(_counts(truth, pred)),
            rows=len(selected),
            bootstrap_mean_mcc=float(scores.mean()),
            bootstrap_std_mcc=float(scores.std(ddof=1)),
            degenerate_bootstrap_draws=int(degenerate.sum()),
            degenerate_bootstrap_fraction=float(degenerate.mean()),
        )
        bootstraps.append(scores)
    macro = np.mean(bootstraps, axis=0)
    return {
        "tutorial_revision": TUTORIAL_REVISION,
        "bootstrap_samples": samples,
        "bootstrap_seed": 0,
        "macro_bootstrap_mean_mcc": float(macro.mean()),
        "macro_bootstrap_std_mcc": float(macro.std(ddof=1)),
        "macro_mcc": float(np.mean([v["mcc"] for v in endpoint_scores.values()])),
        **{
            f"macro_{metric}": float(
                np.mean([v[metric] for v in endpoint_scores.values()])
            )
            for metric in ("accuracy", "precision", "recall", "f1")
        },
        "endpoints": endpoint_scores,
    }


def paired_family_mcc(
    names: np.ndarray,
    groups: np.ndarray,
    labels: np.ndarray,
    mask: np.ndarray,
    candidate: np.ndarray,
    reference: np.ndarray,
    *,
    samples: int = 2000,
    seed: int = 20260906,
) -> dict[str, Any]:
    """Whole-family joint resampling; positive candidate-minus-reference favors candidate."""
    names, labels, mask = _validate(
        names, labels, mask, (np.asarray(candidate), np.asarray(reference))
    )
    groups = np.asarray(groups)
    if groups.shape != names.shape or samples < 2:
        raise ValueError("TDI family dimensions/bootstrap count differ")
    unique, inverse = np.unique(groups, return_inverse=True)
    # Families without either endpoint remain in the resampling frame, as frozen.
    tables = np.zeros((2, 2, len(unique), 4), dtype=np.int64)
    for role, pred in enumerate((candidate, reference)):
        for col in range(2):
            rows = np.flatnonzero(mask[:, col])
            categories = 2 * labels[rows, col].astype(np.int64) + pred[
                rows, col
            ].astype(np.int64)
            np.add.at(tables[role, col], (inverse[rows], categories), 1)
    rng = np.random.default_rng(seed)
    differences = np.empty(samples)
    degeneracy = np.zeros((2, 2), dtype=np.int64)
    for iteration in range(samples):
        selected = rng.choice(len(unique), size=len(unique), replace=True)
        weights = np.bincount(selected, minlength=len(unique))
        counts = np.einsum("g,rcgk->rck", weights, tables)
        scores, degenerate = confusion_mcc(counts)
        differences[iteration] = scores[0].mean() - scores[1].mean()
        degeneracy += degenerate
    pooled, _ = confusion_mcc(tables.sum(axis=2))
    return {
        "samples": samples,
        "seed": seed,
        "families": len(unique),
        "direction": "candidate_minus_reference_positive_is_improvement",
        "pooled_macro_difference": float(pooled[0].mean() - pooled[1].mean()),
        "mean": float(differences.mean()),
        "lower_95": float(np.quantile(differences, 0.025)),
        "upper_95": float(np.quantile(differences, 0.975)),
        "degenerate_draws": {
            role: {
                endpoint: int(degeneracy[r, col])
                for col, endpoint in enumerate(ENDPOINTS)
            }
            for r, role in enumerate(("candidate", "reference"))
        },
        "degenerate_fraction": {
            role: {
                endpoint: float(degeneracy[r, col] / samples)
                for col, endpoint in enumerate(ENDPOINTS)
            }
            for r, role in enumerate(("candidate", "reference"))
        },
    }
