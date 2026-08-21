"""Independent semantic revalidation of a staged full R5C terminal."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any, Final

from cypshift.openadmet_oracle_freezer_io import SYSTEMS
from cypshift.openadmet_oracle_scoring import (
    PRIMARY_POPULATION,
    REQUIRED_CONTRASTS,
    SAFETY_POPULATION,
    STRESS_POPULATION,
    OracleScoringError,
    ScoredRow,
    _aggregate_metrics,
    _similarity_bin,
    _support_bin,
    aggregate_metrics,
    cell_contrasts,
    cell_metrics,
    stress_diagnostic,
)
from cypshift.openadmet_oracle_statistics import (
    SafetySeries,
    bootstrap_contrasts,
    comparison_series,
    resolve_status,
    safety_bootstrap,
    top_influence,
)

SIGNAL_CRITERIA: Final = (
    "all_required_bootstrap_lower_bounds_positive",
    "positive_G0_T0_cells_at_least_12",
    "each_repeat_positive_G0_T0_cells_at_least_3",
    "all_top10_leave_one_out_directions_positive",
    "safety_upper_95_below_0.01",
    "safety_worst_decile_degradation_at_most_0.05",
)


class OracleTerminalValidationError(ValueError):
    """Published full evidence is not the deterministic scorer result."""


def validate_scientific_evidence(
    *,
    status: str,
    scored_rows: Sequence[Mapping[str, str]],
    cell_rows: Sequence[Mapping[str, str]],
    bootstrap_rows: Sequence[Mapping[str, str]],
    influence_rows: Sequence[Mapping[str, str]],
    ablation_rows: Sequence[Mapping[str, str]],
    result: Mapping[str, Any],
) -> None:
    try:
        scored = tuple(_scored(row) for row in scored_rows)
        primary = tuple(
            row for row in scored if row.population_id == PRIMARY_POPULATION
        )
        safety_rows = tuple(
            row for row in scored if row.population_id == SAFETY_POPULATION
        )
        stress = tuple(row for row in scored if row.population_id == STRESS_POPULATION)
        _aligned(primary, SYSTEMS)
        _aligned(safety_rows, ("G0", "SAFETY_FUSION"))
        if stress:
            _aligned(stress, SYSTEMS)
        metrics = {
            system: aggregate_metrics(
                tuple(row for row in primary if row.system_id == system)
            )
            for system in SYSTEMS
        }
        cells = {
            (system, item.repeat, item.outer_fold): item
            for system in SYSTEMS
            for item in cell_metrics(
                tuple(row for row in primary if row.system_id == system)
            )
        }
        comparisons = tuple(
            comparison_series(
                primary,
                control,
                candidate,
                comparison_id=comparison_id,
                local_only=local,
            )
            for comparison_id, control, candidate, local in REQUIRED_CONTRASTS
        )
        bootstraps = bootstrap_contrasts(comparisons)
        influence = top_influence(comparisons[0])
        cell_evidence = cell_contrasts(primary)
        g0_safety = aggregate_metrics(
            tuple(row for row in safety_rows if row.system_id == "G0")
        )
        fusion_safety = aggregate_metrics(
            tuple(row for row in safety_rows if row.system_id == "SAFETY_FUSION")
        )
        safety = safety_bootstrap(
            SafetySeries(
                SAFETY_POPULATION,
                tuple(item[0] for item in g0_safety.component_losses),
                tuple(item[1] for item in g0_safety.component_losses),
                tuple(item[1] for item in fusion_safety.component_losses),
            )
        )
        expected_status = resolve_status(
            integrity_status="PASS",
            support_status="SUPPORTED",
            predictions_status="COMPLETE",
            bootstrap_summaries=bootstraps,
            cell_contrasts=cell_evidence,
            influence_checks=influence,
            safety=safety,
        )
        if status != expected_status:
            raise OracleTerminalValidationError("terminal status evidence differs")
        _validate_cells(cell_rows, cells)
        _validate_bootstrap(bootstrap_rows, bootstraps)
        _validate_influence(influence_rows, influence)
        ablation = _expected_ablations(primary, metrics)
        if list(ablation_rows) != ablation:
            raise OracleTerminalValidationError("ablation scorecard differs")
        _validate_result(
            result,
            metrics,
            bootstraps,
            influence,
            safety,
            cell_evidence,
            primary,
            stress,
            ablation,
        )
    except OracleScoringError as exc:
        raise OracleTerminalValidationError(str(exc)) from exc


def _scored(row: Mapping[str, str]) -> ScoredRow:
    similarity = None if row["similarity"] == "" else _float(row["similarity"])
    exact = _int(row["exact_support_components"])
    class_support = _int(row["class_support_components"])
    result = ScoredRow(
        row["episode_id"],
        row["query_molecule_id"],
        _int(row["query_rank"], minimum=1),
        row["episode_policy_id"],
        _int(row["repeat"]),
        _int(row["outer_fold"]),
        row["component_id"],
        row["population_id"],
        row["system_id"],
        _bool(row["local_eligible"]),
        _bool(row["local_available"]),
        row["prediction_source"],
        row["extraction_status"],
        similarity,
        exact,
        class_support,
        _bool(row["activity_cliff"]),
        row["similarity_bin"],
        row["support_bin"],
        _float(row["absolute_error"]),
        _float(row["query_weight"]),
        _float(row["episode_weight"]),
        _float(row["component_weight"]),
    )
    if (
        result.similarity_bin != _similarity_bin(similarity)
        or result.support_bin != _support_bin(exact, class_support)
        or result.repeat not in range(3)
        or result.outer_fold not in range(5)
    ):
        raise OracleTerminalValidationError("scored row derived metadata differs")
    expected_policy = (
        "deterministic_random_anchor_stress"
        if result.population_id == STRESS_POPULATION
        else "selected_anchor"
    )
    if result.episode_policy_id != expected_policy:
        raise OracleTerminalValidationError("scored population policy differs")
    if result.population_id in {PRIMARY_POPULATION, STRESS_POPULATION} and not (
        result.local_eligible
    ):
        raise OracleTerminalValidationError("local-eligible row differs")
    if result.system_id == "SAFETY_FUSION":
        expected_source = "G0_T0_HALF" if result.local_eligible else "G0"
        if result.prediction_source != expected_source:
            raise OracleTerminalValidationError("safety source differs")
    return result


def _aligned(rows: Sequence[ScoredRow], systems: Sequence[str]) -> None:
    by_system = {
        system: {
            (
                row.episode_id,
                row.query_molecule_id,
                row.query_rank,
                row.episode_policy_id,
                row.repeat,
                row.outer_fold,
                row.component_id,
                row.activity_cliff,
            )
            for row in rows
            if row.system_id == system
        }
        for system in systems
    }
    if (
        not by_system
        or any(not value for value in by_system.values())
        or len({frozenset(value) for value in by_system.values()}) != 1
    ):
        raise OracleTerminalValidationError("scored system populations differ")
    for system in systems:
        aggregate_metrics(tuple(row for row in rows if row.system_id == system))


def _validate_cells(
    rows: Sequence[Mapping[str, str]], cells: Mapping[Any, Any]
) -> None:
    expected: list[dict[str, str]] = []
    for system in SYSTEMS:
        for repeat in range(3):
            for outer in range(5):
                item = cells[(system, repeat, outer)]
                t0 = cells[("T0", repeat, outer)]
                expected.append(
                    {
                        "population_id": item.population_id,
                        "system_id": system,
                        "repeat": str(repeat),
                        "outer_fold": str(outer),
                        "scored_rows": str(item.scored_rows),
                        "scored_episodes": str(item.scored_episodes),
                        "scored_components": str(item.scored_components),
                        "query_macro_mae": _number(item.query_macro_mae),
                        "episode_macro_mae": _number(item.episode_macro_mae),
                        "component_macro_mae": _number(item.component_macro_mae),
                        "contrast_vs_T0": _number(
                            item.component_macro_mae - t0.component_macro_mae
                        ),
                    }
                )
    if list(rows) != expected:
        raise OracleTerminalValidationError("cell metric evidence differs")


def _validate_bootstrap(
    rows: Sequence[Mapping[str, str]], expected: Sequence[Any]
) -> None:
    serialized = [
        {
            "comparison_id": item.comparison_id,
            "population_id": item.population_id,
            "control_system_id": item.control_system_id,
            "candidate_system_id": item.candidate_system_id,
            "point_delta": _number(item.point_delta),
            "lower_95": _number(item.lower_95),
            "upper_95": _number(item.upper_95),
            "accepted_replicates": str(item.accepted_replicates),
            "attempts": str(item.attempts),
            "lower_bound_positive": _text_bool(item.lower_bound_positive),
        }
        for item in expected
    ]
    if list(rows) != serialized:
        raise OracleTerminalValidationError("bootstrap evidence differs")


def _validate_influence(
    rows: Sequence[Mapping[str, str]], expected: Sequence[Any]
) -> None:
    serialized = [
        {
            "comparison_id": item.comparison_id,
            "rank": str(item.rank),
            "component_id": item.component_id,
            "absolute_contribution": _number(item.absolute_contribution),
            "loo_point_delta": _number(item.loo_point_delta),
            "direction_preserved": _text_bool(item.direction_preserved),
        }
        for item in expected
    ]
    if list(rows) != serialized:
        raise OracleTerminalValidationError("influence evidence differs")


def _expected_ablations(
    primary: Sequence[ScoredRow], metrics: Mapping[str, Any]
) -> list[dict[str, str]]:
    g0_losses = dict(metrics["G0"].component_losses)
    ranked = sorted(g0_losses, key=lambda item: (-g0_losses[item], item))
    worst = set(ranked[: max(1, math.ceil(len(ranked) * 0.10))])
    result: list[dict[str, str]] = []
    for system in SYSTEMS:
        selected = tuple(row for row in primary if row.system_id == system)
        worst_metric = _aggregate_metrics(
            tuple(row for row in selected if row.component_id in worst),
            validate_weights=False,
        )
        cliff_metric = _aggregate_metrics(
            tuple(row for row in selected if row.activity_cliff),
            validate_weights=False,
        )
        metric = metrics[system]
        result.append(
            {
                "system_id": system,
                "population_id": PRIMARY_POPULATION,
                "scored_rows": str(metric.scored_rows),
                "scored_episodes": str(metric.scored_episodes),
                "scored_components": str(metric.scored_components),
                "query_macro_mae": _number(metric.query_macro_mae),
                "episode_macro_mae": _number(metric.episode_macro_mae),
                "component_macro_mae": _number(metric.component_macro_mae),
                "worst_global_decile_mae": _number(worst_metric.component_macro_mae),
                "activity_cliff_mae": _number(cliff_metric.component_macro_mae),
                "local_available_rows": str(
                    sum(row.local_available for row in selected)
                ),
            }
        )
    return result


def _validate_result(
    result: Mapping[str, Any],
    metrics: Mapping[str, Any],
    bootstraps: Sequence[Any],
    influence: Sequence[Any],
    safety: Any,
    cells: Sequence[Any],
    primary: Sequence[ScoredRow],
    stress: Sequence[ScoredRow],
    ablations: Sequence[Mapping[str, str]],
) -> None:
    points = result.get("point_estimates")
    expected_points = {
        system: {
            "query_macro_mae": metric.query_macro_mae,
            "episode_macro_mae": metric.episode_macro_mae,
            "component_macro_mae": metric.component_macro_mae,
        }
        for system, metric in metrics.items()
    }
    expected_bootstrap = {
        item.comparison_id: {
            "point_delta": item.point_delta,
            "lower_95": item.lower_95,
            "upper_95": item.upper_95,
            "accepted_replicates": item.accepted_replicates,
            "attempts": item.attempts,
        }
        for item in bootstraps
    }
    expected_safety = asdict(safety)
    expected_safety["worst_decile_component_ids"] = list(
        expected_safety["worst_decile_component_ids"]
    )
    criteria = result.get("criteria")
    positive = sum(item.point_delta > 0 for item in cells)
    repeat_positive = {
        str(repeat): sum(
            item.point_delta > 0 for item in cells if item.repeat == repeat
        )
        for repeat in range(3)
    }
    expected_criteria = {
        "all_required_bootstrap_lower_bounds_positive": all(
            item.lower_bound_positive for item in bootstraps
        ),
        "positive_G0_T0_cells_at_least_12": positive >= 12,
        "each_repeat_positive_G0_T0_cells_at_least_3": all(
            count >= 3 for count in repeat_positive.values()
        ),
        "all_top10_leave_one_out_directions_positive": all(
            item.direction_preserved for item in influence
        ),
        "safety_upper_95_below_0.01": safety.upper_bound_below_criterion,
        "safety_worst_decile_degradation_at_most_0.05": safety.worst_decile_criterion,
    }
    # Support criteria share the object; compare only outcome-derived keys here.
    if (
        points != expected_points
        or result.get("bootstrap") != expected_bootstrap
        or result.get("safety") != expected_safety
        or not isinstance(criteria, Mapping)
        or any(criteria.get(key) != value for key, value in expected_criteria.items())
    ):
        raise OracleTerminalValidationError("result evidence differs")
    diagnostics = result.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise OracleTerminalValidationError("result diagnostics differ")
    expected_ablation_result = {
        row["system_id"]: {
            "worst_global_decile_mae": float(row["worst_global_decile_mae"]),
            "activity_cliff_mae": float(row["activity_cliff_mae"]),
            "local_available_rows": int(row["local_available_rows"]),
        }
        for row in ablations
    }
    if (
        diagnostics.get("positive_G0_T0_cells") != positive
        or diagnostics.get("positive_G0_T0_cells_by_repeat") != repeat_positive
        or diagnostics.get("ablation_scorecard") != expected_ablation_result
    ):
        raise OracleTerminalValidationError("result diagnostics differ")
    stress_record = diagnostics.get("stress")
    if not isinstance(stress_record, Mapping) or set(stress_record) != set(SYSTEMS):
        raise OracleTerminalValidationError("stress diagnostics differ")
    if not stress and any(
        value != {"status": "EMPTY", "scored_rows": 0}
        for value in stress_record.values()
    ):
        raise OracleTerminalValidationError("empty stress diagnostics differ")
    if stress:
        expected_stress = {
            system: asdict(
                stress_diagnostic(
                    tuple(row for row in primary if row.system_id == system),
                    tuple(row for row in stress if row.system_id == system),
                )
            )
            for system in SYSTEMS
        }
        if stress_record != expected_stress:
            raise OracleTerminalValidationError("stress diagnostics differ")


def _int(value: str, *, minimum: int = 0) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise OracleTerminalValidationError("integer serialization differs") from exc
    if str(result) != value or result < minimum:
        raise OracleTerminalValidationError("integer serialization differs")
    return result


def _float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleTerminalValidationError("float serialization differs") from exc
    if not math.isfinite(result) or _number(result) != value:
        raise OracleTerminalValidationError("float serialization differs")
    return result


def _bool(value: str) -> bool:
    if value not in {"true", "false"}:
        raise OracleTerminalValidationError("boolean serialization differs")
    return value == "true"


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise OracleTerminalValidationError("nonfinite terminal evidence")
    return format(value, ".17g")


def _text_bool(value: bool) -> str:
    return "true" if value else "false"


__all__ = ["OracleTerminalValidationError", "validate_scientific_evidence"]
