"""Small benchmark metrics with explicit direction and input contracts."""

from __future__ import annotations

import math
from collections.abc import Sequence

AUPRC_DIRECTION = "higher_is_better"


class MetricError(ValueError):
    """Raised when metric inputs cannot support the requested statistic."""


def average_precision(labels: Sequence[int], scores: Sequence[float]) -> float:
    """Return binary average precision, matching TDC's sklearn evaluator."""

    if len(labels) != len(scores):
        raise MetricError("labels and scores must have the same length")
    if not labels:
        raise MetricError("average precision requires at least one row")
    if any(label not in {0, 1} for label in labels):
        raise MetricError("average precision labels must be binary 0 or 1")
    if any(not math.isfinite(score) for score in scores):
        raise MetricError("average precision scores must be finite")
    positive_count = sum(labels)
    if positive_count == 0:
        raise MetricError("average precision requires at least one positive label")

    ranked = sorted(
        zip(scores, labels, strict=True), key=lambda item: item[0], reverse=True
    )
    true_positives = 0
    false_positives = 0
    previous_recall = 0.0
    result = 0.0
    index = 0
    while index < len(ranked):
        score = ranked[index][0]
        tied_positives = 0
        tied_total = 0
        while index < len(ranked) and ranked[index][0] == score:
            tied_positives += ranked[index][1]
            tied_total += 1
            index += 1
        true_positives += tied_positives
        false_positives += tied_total - tied_positives
        recall = true_positives / positive_count
        precision = true_positives / (true_positives + false_positives)
        result += (recall - previous_recall) * precision
        previous_recall = recall
    return result


__all__ = ["AUPRC_DIRECTION", "MetricError", "average_precision"]
