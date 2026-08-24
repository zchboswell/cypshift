from __future__ import annotations

import math

import pytest

from cypshift.openadmet_global_v2_metric import (
    ENDPOINTS,
    GlobalV2MetricError,
    PredictionRow,
    TruthRow,
    tutorial_endpoint_st_rae,
    tutorial_macro_st_rae,
)


def _truth() -> tuple[TruthRow, ...]:
    return tuple(
        row
        for endpoint in ENDPOINTS
        for row in (
            TruthRow("synthetic-mol-a", endpoint, 2.0, 1.0, 3.0),
            TruthRow("synthetic-mol-b", endpoint, 8.0, 7.0, 9.0),
        )
    )


def _macro_predictions() -> tuple[PredictionRow, ...]:
    values = {
        "CYP1A2": (0.0, 10.0),
        "CYP2C9": (1.0, 9.0),
        "CYP2D6": (5.0, 5.0),
        "CYP3A4": (-1.0, 12.0),
    }
    return tuple(
        row
        for endpoint in ENDPOINTS
        for row in (
            PredictionRow("synthetic-mol-a", endpoint, values[endpoint][0]),
            PredictionRow("synthetic-mol-b", endpoint, values[endpoint][1]),
        )
    )


def test_clean_room_endpoint_matches_pinned_tutorial_fixture() -> None:
    truth = _truth()
    predictions = _macro_predictions()
    score = tutorial_endpoint_st_rae(truth, predictions, "CYP1A2")
    assert score.eligible_rows == 2
    assert score.numerator == 2.0
    assert score.denominator == 4.0
    assert score.value == 0.5

    inside = tuple(
        PredictionRow(row.molecule_id, "CYP2C9", prediction)
        for row, prediction in zip(
            [item for item in truth if item.endpoint == "CYP2C9"],
            (1.0, 9.0),
            strict=True,
        )
    )
    assert tutorial_endpoint_st_rae(truth, inside, "CYP2C9").value == 0.0


def test_clean_room_macro_matches_plain_endpoint_arithmetic() -> None:
    score = tutorial_macro_st_rae(_truth(), _macro_predictions())
    assert [item.endpoint for item in score.endpoint_scores] == list(ENDPOINTS)
    assert [item.value for item in score.endpoint_scores] == [0.5, 0.0, 1.0, 1.25]
    assert score.value == 0.6875


def test_metric_is_order_independent_and_ignores_prediction_only_keys() -> None:
    truth = _truth()
    predictions = _macro_predictions() + (
        PredictionRow("synthetic-mol-extra", "CYP1A2", 123.0),
    )
    first = tutorial_macro_st_rae(truth, predictions)
    second = tutorial_macro_st_rae(tuple(reversed(truth)), tuple(reversed(predictions)))
    assert first == second


@pytest.mark.parametrize(
    ("truth", "predictions", "message"),
    [
        (
            (TruthRow("synthetic-mol-a", "CYP1A2", 2.0, 1.0, 3.0),),
            (),
            "missing eligible",
        ),
        (
            (
                TruthRow("synthetic-mol-a", "CYP1A2", 2.0, 1.0, 3.0),
                TruthRow("synthetic-mol-a", "CYP1A2", 2.0, 1.0, 3.0),
            ),
            (PredictionRow("synthetic-mol-a", "CYP1A2", 2.0),),
            "duplicated",
        ),
        (
            (
                TruthRow("synthetic-mol-a", "CYP1A2", 2.0, 1.0, 3.0),
                TruthRow("synthetic-mol-b", "CYP1A2", 8.0, 7.0, 9.0),
            ),
            (
                PredictionRow("synthetic-mol-a", "CYP1A2", math.nan),
                PredictionRow("synthetic-mol-b", "CYP1A2", 8.0),
            ),
            "nonfinite",
        ),
        (
            (
                TruthRow("synthetic-mol-a", "CYP1A2", 2.0, 2.0, 2.0),
                TruthRow("synthetic-mol-b", "CYP1A2", 2.0, 2.0, 2.0),
            ),
            (
                PredictionRow("synthetic-mol-a", "CYP1A2", 2.0),
                PredictionRow("synthetic-mol-b", "CYP1A2", 2.0),
            ),
            "denominator is nonpositive",
        ),
    ],
)
def test_metric_fails_closed_on_invalid_or_degenerate_inputs(
    truth: tuple[TruthRow, ...],
    predictions: tuple[PredictionRow, ...],
    message: str,
) -> None:
    with pytest.raises(GlobalV2MetricError, match=message):
        tutorial_endpoint_st_rae(truth, predictions, "CYP1A2")


def test_macro_requires_every_endpoint() -> None:
    truth = tuple(row for row in _truth() if row.endpoint != "CYP3A4")
    with pytest.raises(GlobalV2MetricError, match="no eligible truth"):
        tutorial_macro_st_rae(truth, _macro_predictions())
