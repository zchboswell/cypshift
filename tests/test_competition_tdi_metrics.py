"""Independent sklearn parity, missingness, degenerate draws and family resampling."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sklearn.metrics import matthews_corrcoef


@pytest.fixture
def metrics(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "research/maplight-fixed")
    )
    return importlib.import_module("competition_tdi_metrics")


def test_name_sorted_masked_row_bootstrap_matches_sklearn_with_degenerate_draws(
    metrics: Any,
) -> None:
    names = np.array(["z", "b", "q", "a", "n", "m"])
    labels = np.array([[1, 0], [0, 1], [1, 1], [0, 0], [1, 0], [0, 1]], dtype=float)
    mask = np.array([[1, 0], [1, 1], [0, 1], [1, 1], [0, 1], [1, 1]], dtype=bool)
    prediction = np.array([[1, 0], [0, 0], [0, 0], [1, 0], [1, 0], [0, 0]], dtype=float)
    labels[~mask] = np.nan
    prediction[~mask] = np.nan
    actual = metrics.direct_tdi_scores(names, labels, mask, prediction)
    scores = []
    for col, endpoint in enumerate(metrics.ENDPOINTS):
        idx = np.argsort(names)
        idx = idx[mask[idx, col]]
        draws = np.random.default_rng(0).choice(
            len(idx), size=(1000, len(idx)), replace=True
        )
        values = np.array(
            [
                matthews_corrcoef(
                    labels[idx][d, col].astype(bool),
                    prediction[idx][d, col].astype(bool),
                )
                for d in draws
            ]
        )
        assert actual["endpoints"][endpoint]["bootstrap_mean_mcc"] == pytest.approx(
            values.mean(), abs=1e-15
        )
        assert actual["endpoints"][endpoint]["bootstrap_std_mcc"] == pytest.approx(
            values.std(ddof=1), abs=1e-15
        )
        scores.append(values)
    assert actual["macro_bootstrap_mean_mcc"] == pytest.approx(
        np.mean(scores, axis=0).mean(), abs=1e-15
    )
    assert actual["macro_bootstrap_std_mcc"] == pytest.approx(
        np.mean(scores, axis=0).std(ddof=1), abs=1e-15
    )
    assert (
        actual["endpoints"][metrics.ENDPOINTS[1]]["degenerate_bootstrap_draws"] == 1000
    )
    changed = prediction.copy()
    changed[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite binary"):
        metrics.direct_tdi_scores(names, labels, mask, changed)
    changed[0, 0] = 0.2
    with pytest.raises(ValueError, match="finite binary"):
        metrics.direct_tdi_scores(names, labels, mask, changed)


def test_whole_family_joint_bootstrap_matches_explicit_molecule_replication(
    metrics: Any,
) -> None:
    names = np.array(["a", "b", "c", "d", "e", "f", "g"])
    groups = np.array(["x", "x", "x", "y", "z", "z", "empty"])
    labels = np.array(
        [[1, 0], [0, 1], [1, 1], [0, 0], [1, 0], [0, 1], [0, 0]], dtype=float
    )
    mask = np.ones_like(labels, dtype=bool)
    mask[6] = False
    mask[1, 1] = False
    candidate = labels.copy()
    candidate[1, 0] = 1
    reference = np.zeros_like(labels)
    result = metrics.paired_family_mcc(
        names, groups, labels, mask, candidate, reference, samples=120
    )
    unique = np.unique(groups)
    rng = np.random.default_rng(20260906)
    differences = []
    for _ in range(120):
        sampled = rng.choice(len(unique), size=len(unique), replace=True)
        rows = np.concatenate([np.flatnonzero(groups == unique[g]) for g in sampled])
        per_role = []
        for predictions in (candidate, reference):
            per_endpoint = []
            for col in range(2):
                take = rows[mask[rows, col]]
                per_endpoint.append(
                    matthews_corrcoef(labels[take, col], predictions[take, col])
                    if len(take)
                    else 0.0
                )
            per_role.append(np.mean(per_endpoint))
        differences.append(per_role[0] - per_role[1])
    assert result["mean"] == pytest.approx(np.mean(differences), abs=1e-15)
    assert result["lower_95"] == pytest.approx(
        np.quantile(differences, 0.025), abs=1e-15
    )
    assert result["upper_95"] == pytest.approx(
        np.quantile(differences, 0.975), abs=1e-15
    )
    assert all(v == 120 for v in result["degenerate_draws"]["reference"].values())
    reversed_result = metrics.paired_family_mcc(
        names, groups, labels, mask, reference, candidate, samples=120
    )
    assert reversed_result["lower_95"] == pytest.approx(-result["upper_95"])
