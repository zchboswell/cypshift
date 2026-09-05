"""Scientific regression tests using an independently executed public oracle.

Golden ST-RAE means were produced by the unmodified evaluation/config.py,
custom_scoring_functions.py, evaluate_predictions.py and utils.py at tutorial
858ae63ce79934113bccdb7fc65467de5f7b1935. The full upstream scoring, macro
and averaging functions ran in NumPy 1.25.2 / pandas 2.0.3; only logging was
stubbed because loguru is absent from our locked research environment. No
network access, pandas dependency or official challenge data is needed here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_PATH = (
    Path(__file__).resolve().parents[1]
    / "research/maplight-fixed/competition_metrics.py"
)
_SPEC = importlib.util.spec_from_file_location("phase3_competition_metrics", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
metrics = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(metrics)


def _fixture() -> tuple[Any, ...]:
    row = np.arange(60, dtype=float)
    names = np.array([f"synthetic-{i:03}" for i in range(59, -1, -1)])
    groups = np.array([f"family-{i // 3:02}" for i in range(60)])
    point = np.stack(
        [1 + row / 10 + col * 0.7 + np.sin(row * 0.3 + col) * 0.2 for col in range(4)],
        axis=1,
    )
    low = point - np.array([0.05, 0.1, 0.15, 0.2])
    high = point + np.array([0.2, 0.15, 0.1, 0.05])
    prediction = point + np.stack(
        [np.cos(row * 0.4 + col) * (0.4 + col * 0.2) + 0.15 for col in range(4)],
        axis=1,
    )
    for col in range(4):
        for values in (point, low, high, prediction):
            values[col :: (17 - col * 2), col] = np.nan
    return names, groups, point, low, high, prediction


def test_complete_bootstrap_wrapper_matches_pinned_official_oracle() -> None:
    result = metrics.direct_scores(*_fixture())
    expected = [
        0.10704174988637022,
        0.19467520523520676,
        0.3061879504937976,
        0.4074256003865766,
    ]
    for endpoint, value, count in zip(
        metrics.ENDPOINTS, expected, [56, 56, 55, 54], strict=True
    ):
        actual = result["endpoints"][endpoint]
        assert actual["rows"] == count
        assert actual["bootstrap_mean_st_rae"] == pytest.approx(value, rel=0, abs=1e-13)
    assert result["macro_bootstrap_mean_st_rae"] == pytest.approx(
        0.2538326265004878, rel=0, abs=1e-13
    )
    # A point-score-only implementation must not pass as the official mean.
    pooled = np.mean([v["st_rae"] for v in result["endpoints"].values()])
    assert abs(pooled - result["macro_bootstrap_mean_st_rae"]) > 0.005
    perm = np.random.default_rng(8).permutation(60)
    assert metrics.direct_scores(*(v[perm] for v in _fixture())) == result


def test_hand_calculated_error_preserves_reported_bounds() -> None:
    point = np.array([2.0, 8.0])
    low = np.array([1.0, 7.0])
    high = np.array([3.0, 9.0])
    assert metrics.st_rae(point, low, high, np.array([0.0, 10.0])) == 0.5
    assert metrics.st_rae(point, low, high, np.array([3.0, 7.0])) == 0
    # Point estimates need not be the midpoint of asymmetric released bounds.
    assert metrics.st_rae(point, low, np.array([4.0, 9.0]), np.array([0.0, 10.0])) == (
        2 / 3
    )


@pytest.mark.parametrize("column", [3, 4, 5])
def test_missing_or_nonfinite_eligible_bounds_and_predictions_fail(column: int) -> None:
    values = list(_fixture())
    values[column][5, 0] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        metrics.direct_scores(*values)


def test_missing_central_truth_is_the_only_row_mask() -> None:
    values = list(_fixture())
    values[3][0, 0] = -np.inf
    values[4][0, 0] = np.inf
    values[5][0, 0] = np.inf
    assert metrics.direct_scores(*values) == metrics.direct_scores(*_fixture())


def test_reversed_bounds_and_duplicate_molecule_identities_fail() -> None:
    values = list(_fixture())
    values[3][5, 0] = values[4][5, 0] + 1
    with pytest.raises(ValueError, match="Reversed"):
        metrics.direct_scores(*values)
    values = list(_fixture())
    values[0][1] = values[0][0]
    with pytest.raises(ValueError, match="unique"):
        metrics.direct_scores(*values)


def test_undefined_bootstrap_sample_is_not_dropped_or_assigned_perfect_score() -> None:
    names = np.array(["a", "b"])
    groups = names.copy()
    point = np.tile([0.0, 1.0], (4, 1)).T
    # Pooled score exists, but the first seed-0 resample is [1, 1].
    assert metrics.st_rae(point[:, 0], point[:, 0], point[:, 0], point[:, 0]) == 0
    with pytest.raises(ValueError, match="denominator"):
        metrics.direct_scores(names, groups, point, point, point, point)
    with pytest.raises(ValueError, match="Unsupported"):
        metrics.paired_family_difference(
            names, groups, point, point, point, point, point, samples=20, seed=0
        )


def test_family_bootstrap_matches_explicit_replicated_population_oracle() -> None:
    names, groups, point, low, high, candidate = _fixture()
    baseline = point + 0.9
    actual = metrics.paired_family_difference(
        names, groups, point, low, high, candidate, baseline, samples=100, seed=42
    )
    # Independently materialize whole repeated families, rather than using
    # production's group counts/weighted sufficient-statistic calculation.
    family_ids = sorted(set(groups))
    draws = np.random.default_rng(42).choice(family_ids, (100, len(family_ids)))
    differences = []
    for draw in draws:
        rows = np.concatenate([np.flatnonzero(groups == family) for family in draw])
        endpoint_differences = []
        for col in range(4):
            selected = rows[~np.isnan(point[rows, col])]
            y, lower, upper = (v[selected, col] for v in (point, low, high))
            denominator = np.abs(y.mean() - np.clip(y.mean(), lower, upper)).sum()
            errors = [
                np.abs(v[selected, col] - np.clip(v[selected, col], lower, upper)).sum()
                for v in (candidate, baseline)
            ]
            endpoint_differences.append((errors[0] - errors[1]) / denominator)
        differences.append(np.mean(endpoint_differences))
    assert actual["candidate_minus_baseline_mean"] == pytest.approx(
        np.mean(differences)
    )
    assert actual["lower_95"] == pytest.approx(np.quantile(differences, 0.025))
    assert actual["upper_95"] == pytest.approx(np.quantile(differences, 0.975))
    assert actual["upper_95"] < 0
    identical = metrics.paired_family_difference(
        names, groups, point, low, high, candidate, candidate, samples=100, seed=42
    )
    assert identical["lower_95"] == identical["upper_95"] == 0
    swapped = metrics.paired_family_difference(
        names, groups, point, low, high, baseline, candidate, samples=100, seed=42
    )
    assert swapped["upper_95"] == pytest.approx(-actual["lower_95"])


def test_paired_comparison_rejects_misaligned_inputs() -> None:
    names, groups, point, low, high, candidate = _fixture()
    with pytest.raises(ValueError, match="matrix shape"):
        metrics.paired_family_difference(
            names, groups, point, low, high, candidate, candidate[:-1]
        )
    with pytest.raises(ValueError, match="dimensions"):
        metrics.paired_family_difference(
            names, groups[:-1], point, low, high, candidate, candidate
        )


def test_perfect_baseline_is_valid_without_undefined_relative_promotion() -> None:
    names, groups, point, low, high, prediction = _fixture()
    baseline = metrics.direct_scores(names, groups, point, low, high, point)
    candidate = metrics.direct_scores(names, groups, point, low, high, prediction)
    decision = metrics.release_decision(candidate, baseline, {"upper_95": -0.1})
    assert decision["relative_primary_improvement"] is None
    assert not decision["release_eligible_on_paired_metrics"]
    assert not decision["promotion_metric_gate"]
