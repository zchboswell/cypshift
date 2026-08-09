from __future__ import annotations

import math

import pytest

from cypshift.metrics import AUPRC_DIRECTION, MetricError, average_precision


def test_average_precision_has_correct_tdc_polarity() -> None:
    labels = [0, 1, 0, 1]

    perfect = average_precision(labels, [0.1, 0.9, 0.2, 0.8])
    inverted = average_precision(labels, [0.9, 0.1, 0.8, 0.2])

    assert perfect == 1.0
    assert inverted == pytest.approx(5 / 12)
    assert perfect > inverted
    assert AUPRC_DIRECTION == "higher_is_better"


def test_average_precision_ties_equal_prevalence() -> None:
    assert average_precision([1, 0, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5


@pytest.mark.parametrize(
    ("labels", "scores", "message"),
    [
        ([], [], "at least one row"),
        ([0, 1], [0.5], "same length"),
        ([0, 2], [0.5, 0.6], "binary"),
        ([0, 0], [0.5, 0.6], "positive"),
        ([0, 1], [0.5, math.nan], "finite"),
    ],
)
def test_average_precision_rejects_invalid_inputs(
    labels: list[int], scores: list[float], message: str
) -> None:
    with pytest.raises(MetricError, match=message):
        average_precision(labels, scores)
