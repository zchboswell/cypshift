"""Clean-room tutorial MA-ST-RAE kernel for the Global-v2 synthetic gate."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

ENDPOINTS: Final = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
METRIC_ID: Final = "TUTORIAL_MA_ST_RAE_858AE63_V1"


class GlobalV2MetricError(ValueError):
    """Metric inputs violate the frozen tutorial-kernel contract."""


@dataclass(frozen=True, slots=True)
class TruthRow:
    """One complete synthetic truth row with reported bounds."""

    molecule_id: str
    endpoint: str
    point: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class PredictionRow:
    """One synthetic prediction keyed by molecule and endpoint."""

    molecule_id: str
    endpoint: str
    prediction: float


@dataclass(frozen=True, slots=True)
class EndpointScore:
    """Exact aggregate ingredients for one endpoint ST-RAE value."""

    endpoint: str
    eligible_rows: int
    numerator: float
    denominator: float
    value: float


@dataclass(frozen=True, slots=True)
class MacroScore:
    """Four endpoint scores and their plain arithmetic mean."""

    metric_id: str
    endpoint_scores: tuple[EndpointScore, ...]
    value: float


def tutorial_endpoint_st_rae(
    truth_rows: Sequence[TruthRow],
    prediction_rows: Sequence[PredictionRow],
    endpoint: str,
) -> EndpointScore:
    """Compute the pinned tutorial soft-threshold relative absolute error."""

    if endpoint not in ENDPOINTS:
        raise GlobalV2MetricError("endpoint differs from the frozen set")
    truth = _truth_index(truth_rows)
    predictions = _prediction_index(prediction_rows)
    selected = sorted((key, row) for key, row in truth.items() if key[1] == endpoint)
    if not selected:
        raise GlobalV2MetricError(f"endpoint has no eligible truth: {endpoint}")
    missing = [key for key, _ in selected if key not in predictions]
    if missing:
        raise GlobalV2MetricError(
            f"prediction is missing eligible endpoint keys: {endpoint}"
        )

    mean_true = math.fsum(row.point for _, row in selected) / len(selected)
    numerator = math.fsum(
        _distance_outside(predictions[key].prediction, row.low, row.high)
        for key, row in selected
    )
    denominator = math.fsum(
        _distance_outside(mean_true, row.low, row.high) for _, row in selected
    )
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise GlobalV2MetricError(
            f"endpoint tutorial denominator is nonpositive: {endpoint}"
        )
    value = numerator / denominator
    if not math.isfinite(value):
        raise GlobalV2MetricError(f"endpoint tutorial value is nonfinite: {endpoint}")
    return EndpointScore(endpoint, len(selected), numerator, denominator, value)


def tutorial_macro_st_rae(
    truth_rows: Sequence[TruthRow],
    prediction_rows: Sequence[PredictionRow],
) -> MacroScore:
    """Compute the plain arithmetic mean over all four endpoint ST-RAEs."""

    scores = tuple(
        tutorial_endpoint_st_rae(truth_rows, prediction_rows, endpoint)
        for endpoint in ENDPOINTS
    )
    value = math.fsum(score.value for score in scores) / len(scores)
    if not math.isfinite(value):
        raise GlobalV2MetricError("tutorial macro value is nonfinite")
    return MacroScore(METRIC_ID, scores, value)


def _truth_index(rows: Sequence[TruthRow]) -> dict[tuple[str, str], TruthRow]:
    result: dict[tuple[str, str], TruthRow] = {}
    for row in rows:
        _key(row.molecule_id, row.endpoint)
        if not all(math.isfinite(value) for value in (row.point, row.low, row.high)):
            raise GlobalV2MetricError("truth value is nonfinite")
        if row.low > row.point or row.point > row.high:
            raise GlobalV2MetricError("reported bounds do not contain central truth")
        key = (row.molecule_id, row.endpoint)
        if key in result:
            raise GlobalV2MetricError("truth key is duplicated")
        result[key] = row
    return result


def _prediction_index(
    rows: Sequence[PredictionRow],
) -> dict[tuple[str, str], PredictionRow]:
    result: dict[tuple[str, str], PredictionRow] = {}
    for row in rows:
        _key(row.molecule_id, row.endpoint)
        if not math.isfinite(row.prediction):
            raise GlobalV2MetricError("prediction is nonfinite")
        key = (row.molecule_id, row.endpoint)
        if key in result:
            raise GlobalV2MetricError("prediction key is duplicated")
        result[key] = row
    return result


def _key(molecule_id: str, endpoint: str) -> None:
    if not molecule_id or molecule_id.strip() != molecule_id:
        raise GlobalV2MetricError("molecule identifier differs")
    if endpoint not in ENDPOINTS:
        raise GlobalV2MetricError("endpoint differs from the frozen set")


def _distance_outside(value: float, low: float, high: float) -> float:
    return max(value - high, 0.0) + max(low - value, 0.0)


__all__ = [
    "ENDPOINTS",
    "METRIC_ID",
    "EndpointScore",
    "GlobalV2MetricError",
    "MacroScore",
    "PredictionRow",
    "TruthRow",
    "tutorial_endpoint_st_rae",
    "tutorial_macro_st_rae",
]
