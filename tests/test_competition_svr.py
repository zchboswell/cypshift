from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research/maplight-fixed"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
SPEC = importlib.util.spec_from_file_location(
    "competition_svr", RESEARCH / "competition_svr.py"
)
assert SPEC is not None and SPEC.loader is not None
svr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = svr
SPEC.loader.exec_module(svr)


def test_dense_binary_kernel_avoids_uint8_overflow_and_supports_cross_rows() -> None:
    left = np.zeros((3, 4096), dtype=np.uint8)
    left[0, :1024] = 1
    left[1, 512:2048] = 1
    right = left[[1, 2]].astype(bool)
    actual = svr.tanimoto_kernel(left, right, block_rows=1)
    expected = np.array([[512 / 2048, 0], [1, 0], [0, 1]])
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == np.dtype("float64")
    full = svr.tanimoto_kernel(left)
    np.testing.assert_array_equal(full, full.T)
    np.testing.assert_array_equal(np.diag(full), np.ones(3))
    np.testing.assert_array_equal(actual, full[:, [1, 2]])


def test_invalid_counts_cannot_silently_be_used_as_binary_features() -> None:
    with pytest.raises(ValueError, match="Nonbinary"):
        svr.tanimoto_kernel(np.array([[0, 2]], dtype=np.uint8))


def test_inner_oof_does_not_fit_on_heldout_labels_and_excludes_ineligible() -> None:
    pytest.importorskip("sklearn")
    # Identity kernel gives unrelated molecules; modifying one fold's targets
    # cannot change predictions for that fold, for either fixed C candidate.
    kernel = np.eye(12, dtype=np.float64)
    folds = np.tile(np.arange(3, dtype=np.int64), 4)
    point = np.arange(12, dtype=float) / 3
    eligibility = np.ones(12, dtype=bool)
    eligibility[-1] = False
    _, original = svr.inner_select_c(kernel, point, point, point, eligibility, folds)
    changed = point.copy()
    changed[folds == 0] += 100
    _, altered = svr.inner_select_c(
        kernel, changed, changed, changed, eligibility, folds
    )
    for c in svr.CS:
        np.testing.assert_array_equal(original[c][folds == 0], altered[c][folds == 0])
        assert np.isfinite(original[c]).all()
    changed = point.copy()
    changed[-1] = 1000
    _, altered = svr.inner_select_c(
        kernel, changed, changed, changed, eligibility, folds
    )
    for c in svr.CS:
        np.testing.assert_array_equal(original[c], altered[c])


def test_inner_score_tie_prefers_smaller_c_and_undefined_metric_fails() -> None:
    pytest.importorskip("sklearn")
    # All fingerprints identical: C cannot change the balanced median prediction.
    kernel = np.ones((12, 12), dtype=float)
    point = np.tile(np.array([0.0, 1.0]), 6)
    folds = np.repeat(np.arange(3, dtype=np.int64), 4)
    mask = np.ones(12, dtype=bool)
    chosen, oof = svr.inner_select_c(kernel, point, point, point, mask, folds)
    np.testing.assert_array_equal(oof[1.0], oof[10.0])
    assert chosen == 1.0
    with pytest.raises(ValueError, match="denominator"):
        svr.inner_select_c(
            kernel, point, np.full(12, -1.0), np.full(12, 2.0), mask, folds
        )
