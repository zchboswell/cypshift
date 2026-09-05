"""Bounded Tanimoto SVR candidate and outer-training-only inner selection."""

from __future__ import annotations

from typing import Any

import numpy as np
from competition_metrics import st_rae
from numpy.typing import NDArray

Array = NDArray[np.float64]
CS = (1.0, 10.0)
EPSILON = 0.1


def tanimoto_kernel(
    left: NDArray[Any], right: NDArray[Any] | None = None, *, block_rows: int = 256
) -> Array:
    """Compute binary Tanimoto without overflowing dot products or 3D broadcasts.

    Both empty fingerprints have similarity one, including off-diagonal pairs;
    empty versus nonempty has similarity zero. The caller supplies the frozen
    radius-2/4096 Morgan features. Other positive widths are accepted for tests.
    """
    if block_rows < 1:
        raise ValueError("Kernel row block must be positive")
    if right is None:
        right = left
    for bits in (left, right):
        if (
            bits.ndim != 2
            or bits.shape[1] == 0
            or bits.dtype not in (np.dtype("uint8"), np.dtype("bool"))
        ):
            raise ValueError("Fingerprints must be binary uint8 or bool matrices")
        if np.any((bits != 0) & (bits != 1)):
            raise ValueError("Nonbinary fingerprint values")
    if left.shape[1] != right.shape[1]:
        raise ValueError("Fingerprint widths differ")
    lhs = np.asarray(left, dtype=np.float64)
    rhs = lhs if right is left else np.asarray(right, dtype=np.float64)
    left_mass, right_mass = lhs.sum(axis=1), rhs.sum(axis=1)
    result = np.empty((len(left), len(right)), dtype=np.float64)
    for start in range(0, len(left), block_rows):
        stop = min(start + block_rows, len(left))
        intersection = lhs[start:stop] @ rhs.T
        union = left_mass[start:stop, None] + right_mass[None, :] - intersection
        result[start:stop] = np.divide(
            intersection, union, out=np.ones_like(intersection), where=union > 0
        )
    return result


def inner_select_c(
    kernel: Array,
    point: Array,
    low: Array,
    high: Array,
    training_mask: NDArray[np.bool_],
    inner_folds: NDArray[np.int64],
) -> tuple[float, dict[float, Array]]:
    """Select fixed C values on pooled inner OOF interval loss; ties choose C=1.

    Inputs contain one outer-training population only, in identical row order.
    The caller owns family assignment. Each inner fold withholds every label of
    its members. Both C values predict all rows, with metric selection using the
    same finite-central population, independent of training eligibility.
    """
    from sklearn.svm import SVR

    n = len(point)
    if point.shape != (n,) or any(
        vector.shape != (n,) for vector in (low, high, training_mask, inner_folds)
    ):
        raise ValueError("Inner selection vectors differ")
    if (
        kernel.shape != (n, n)
        or not np.isfinite(kernel).all()
        or np.any(kernel < 0)
        or np.any(kernel > 1)
        or not np.allclose(kernel, kernel.T, rtol=0, atol=1e-12)
    ):
        raise ValueError("Invalid inner training kernel")
    if (
        training_mask.dtype != np.dtype("bool")
        or inner_folds.dtype.kind not in "iu"
        or set(inner_folds.tolist()) != {0, 1, 2}
    ):
        raise ValueError("Expected boolean eligibility and three inner folds")
    metric_mask = np.isfinite(point)
    if (
        not metric_mask.any()
        or np.isinf(point).any()
        or np.any(training_mask & ~metric_mask)
        or not np.isfinite(low[metric_mask]).all()
        or not np.isfinite(high[metric_mask]).all()
        or np.any(low[metric_mask] > high[metric_mask])
    ):
        raise ValueError("Invalid inner selection target population")
    # Fail before any fit on unsupported denominator or missing training support.
    st_rae(point[metric_mask], low[metric_mask], high[metric_mask], point[metric_mask])
    cells = []
    for fold in range(3):
        train = np.flatnonzero(training_mask & (inner_folds != fold))
        valid = np.flatnonzero(inner_folds == fold)
        if len(train) < 2:
            raise ValueError("Inner training support is below two targets")
        cells.append((train, valid))
    oof = {c: np.full(n, np.nan) for c in CS}
    scores = {}
    for c in CS:
        for train, valid in cells:
            model = SVR(C=c, epsilon=EPSILON, kernel="precomputed", cache_size=256)
            model.fit(kernel[np.ix_(train, train)], point[train])
            oof[c][valid] = model.predict(kernel[np.ix_(valid, train)])
        if not np.isfinite(oof[c]).all():
            raise ValueError("Nonfinite SVR inner OOF prediction")
        scores[c] = st_rae(
            point[metric_mask], low[metric_mask], high[metric_mask], oof[c][metric_mask]
        )
    chosen = min(CS, key=lambda c: (scores[c], c))
    return chosen, oof
