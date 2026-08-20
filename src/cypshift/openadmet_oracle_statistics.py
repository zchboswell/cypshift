"""Pure R5C comparison statistics; no I/O, models, or challenge access."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from cypshift.openadmet_oracle_scoring import (
    PRIMARY_POPULATION,
    REQUIRED_CONTRASTS,
    SAFETY_POPULATION,
    STRESS_POPULATION,
    OracleScoringError,
    PredictionRow,
    PublicQuery,
    ScoredRow,
    SealedTruth,
    _aggregate_metrics,
    _finite,
    _mean,
    _metadata_map,
    _validate_truth,
    aggregate_metrics,
)


@dataclass(frozen=True, slots=True)
class ContrastSeries:
    """One comparison's already-aligned component loss series."""

    comparison_id: str
    population_id: str
    control_system_id: str
    candidate_system_id: str
    component_ids: tuple[str, ...]
    control_losses: tuple[float | None, ...]
    candidate_losses: tuple[float | None, ...]


@dataclass(frozen=True, slots=True)
class CellContrast:
    repeat: int
    outer_fold: int
    point_delta: float


@dataclass(frozen=True, slots=True)
class SystemSeries:
    population_id: str
    system_id: str
    component_ids: tuple[str, ...]
    losses: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SafetySeries:
    population_id: str
    component_ids: tuple[str, ...]
    g0_losses: tuple[float, ...]
    fusion_losses: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class BootstrapSummary:
    comparison_id: str
    population_id: str
    control_system_id: str
    candidate_system_id: str
    point_delta: float
    lower_95: float
    upper_95: float
    accepted_replicates: int
    attempts: int
    lower_bound_positive: bool


@dataclass(frozen=True, slots=True)
class InfluenceCheck:
    comparison_id: str
    rank: int
    component_id: str
    absolute_contribution: float
    loo_point_delta: float
    direction_preserved: bool


@dataclass(frozen=True, slots=True)
class SafetySummary:
    population_id: str
    point_relative_degradation: float
    lower_95: float
    upper_95: float
    accepted_replicates: int
    attempts: int
    upper_bound_below_criterion: bool
    worst_decile_component_ids: tuple[str, ...]
    worst_decile_point_degradation: float
    worst_decile_criterion: bool


def comparison_series(
    rows: Sequence[ScoredRow],
    control_system_id: str,
    candidate_system_id: str,
    *,
    comparison_id: str | None = None,
    local_only: bool = False,
) -> ContrastSeries:
    """Build one aligned component series; local filtering is comparison-scoped."""

    if control_system_id == candidate_system_id:
        raise OracleScoringError("comparison systems must differ")
    controls = _metadata_map(
        tuple(row for row in rows if row.system_id == control_system_id)
    )
    candidates = _metadata_map(
        tuple(row for row in rows if row.system_id == candidate_system_id)
    )
    if not controls or not candidates:
        raise OracleScoringError("comparison system is missing")
    if set(controls) != set(candidates):
        raise OracleScoringError("comparison metadata is not aligned")
    control_all = tuple(controls[key] for key in sorted(controls))
    candidate_all = tuple(candidates[key] for key in sorted(candidates))
    control_metric = aggregate_metrics(control_all)
    candidate_metric = aggregate_metrics(candidate_all)
    if control_all[0].population_id != candidate_all[0].population_id:
        raise OracleScoringError("comparison populations differ")
    full_components = tuple(item[0] for item in control_metric.component_losses)
    if full_components != tuple(item[0] for item in candidate_metric.component_losses):
        raise OracleScoringError("comparison components differ")
    if local_only:
        controls = {key: row for key, row in controls.items() if row.local_available}
        candidates = {key: row for key, row in candidates.items() if key in controls}
    if set(controls) != set(candidates):
        raise OracleScoringError("comparison metadata is not aligned")
    if not controls:
        raise OracleScoringError("local comparison is empty")
    control_rows = tuple(controls[key] for key in sorted(controls))
    candidate_rows = tuple(candidates[key] for key in sorted(candidates))
    if local_only:
        control_metric = _aggregate_metrics(control_rows, validate_weights=False)
        candidate_metric = _aggregate_metrics(candidate_rows, validate_weights=False)
    control_map = dict(control_metric.component_losses)
    candidate_map = dict(candidate_metric.component_losses)
    return ContrastSeries(
        comparison_id or f"{control_system_id}-{candidate_system_id}",
        (f"local:{control_system_id}" if local_only else control_rows[0].population_id),
        control_system_id,
        candidate_system_id,
        full_components,
        tuple(control_map.get(item) for item in full_components),
        tuple(candidate_map.get(item) for item in full_components),
    )


def _validate_comparison_series(series: Sequence[ContrastSeries]) -> None:
    ids: set[str] = set()
    for item in series:
        if item.comparison_id in ids or not item.component_ids:
            raise OracleScoringError("duplicate or empty comparison series")
        ids.add(item.comparison_id)
        if item.population_id == STRESS_POPULATION:
            raise OracleScoringError("stress series are diagnostic-only")
        if (
            item.population_id != PRIMARY_POPULATION
            and not item.population_id.startswith("local:")
        ):
            raise OracleScoringError("comparison population is invalid")
        if tuple(sorted(item.component_ids)) != item.component_ids or len(
            item.component_ids
        ) != len(set(item.component_ids)):
            raise OracleScoringError("duplicate component in comparison series")
        if len(item.control_losses) != len(item.component_ids) or len(
            item.candidate_losses
        ) != len(item.component_ids):
            raise OracleScoringError("comparison series lengths differ")
        local = item.population_id.startswith("local:")
        for control, candidate in zip(
            item.control_losses, item.candidate_losses, strict=True
        ):
            if (control is None) != (candidate is None):
                raise OracleScoringError("one-sided component missingness")
            if control is None:
                if not local:
                    raise OracleScoringError("primary component is missing")
                continue
            _finite(control, "control loss")
            assert candidate is not None
            _finite(candidate, "candidate loss")


def make_contrast_series(
    comparison_id: str,
    population_id: str,
    control_system_id: str,
    candidate_system_id: str,
    control_losses: Mapping[str, float | None],
    candidate_losses: Mapping[str, float | None],
) -> ContrastSeries:
    """Align one comparison; only paired missingness may be dropped."""

    component_ids = tuple(sorted(set(control_losses) | set(candidate_losses)))
    controls: list[float | None] = []
    candidates: list[float | None] = []
    for component in component_ids:
        control, candidate = (
            control_losses.get(component),
            candidate_losses.get(component),
        )
        if (control is None) != (candidate is None):
            raise OracleScoringError("one-sided component missingness")
        if control is None:
            if not population_id.startswith("local:"):
                raise OracleScoringError("primary component is missing")
            controls.append(None)
            candidates.append(None)
            continue
        if candidate is None:
            raise OracleScoringError("candidate loss missing")
        controls.append(_finite(control, "control loss"))
        candidates.append(_finite(candidate, "candidate loss"))
    series = ContrastSeries(
        comparison_id,
        population_id,
        control_system_id,
        candidate_system_id,
        component_ids,
        tuple(controls),
        tuple(candidates),
    )
    _validate_comparison_series((series,))
    return series


def _weighted_series_delta(series: ContrastSeries, counts: Sequence[int]) -> float:
    if len(counts) != len(series.component_ids):
        raise OracleScoringError("bootstrap multiplicity width differs")
    finite_indices = [
        index
        for index, (control, candidate) in enumerate(
            zip(series.control_losses, series.candidate_losses, strict=True)
        )
        if control is not None and candidate is not None
    ]
    denominator = sum(counts[index] for index in finite_indices)
    if denominator <= 0:
        raise OracleScoringError("bootstrap draw has no jointly finite component")
    control_values = [(index, series.control_losses[index]) for index in finite_indices]
    candidate_values = [
        (index, series.candidate_losses[index]) for index in finite_indices
    ]
    control = (
        math.fsum(
            counts[index] * value
            for index, value in control_values
            if value is not None
        )
        / denominator
    )
    candidate = (
        math.fsum(
            counts[index] * value
            for index, value in candidate_values
            if value is not None
        )
        / denominator
    )
    return _finite(control - candidate, "bootstrap contrast")


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise OracleScoringError("cannot percentile empty values")
    h = (len(ordered) - 1) * fraction
    low = math.floor(h)
    high = math.ceil(h)
    if low == high:
        return ordered[low]
    return _finite(
        ordered[low] + (h - low) * (ordered[high] - ordered[low]), "percentile"
    )


def bootstrap_contrasts(
    comparisons: Sequence[ContrastSeries],
    *,
    seed: int = 20260821,
    accepted_replicates: int = 2000,
    maximum_attempts: int = 20000,
) -> tuple[BootstrapSummary, ...]:
    if accepted_replicates <= 0 or maximum_attempts < accepted_replicates:
        raise OracleScoringError("invalid bootstrap budget")
    if not comparisons:
        raise OracleScoringError("bootstrap comparisons are empty")
    _validate_comparison_series(comparisons)
    primary = tuple(
        series for series in comparisons if series.population_id == PRIMARY_POPULATION
    )
    if not primary:
        raise OracleScoringError("primary bootstrap universe is missing")
    component_ids = primary[0].component_ids
    if any(series.component_ids != component_ids for series in comparisons):
        raise OracleScoringError("bootstrap component universe differs")
    np = _numpy()
    rng = np.random.Generator(np.random.PCG64(seed))
    values: dict[str, list[float]] = {item.comparison_id: [] for item in comparisons}
    attempts = 0
    while attempts < maximum_attempts and any(
        len(values[item.comparison_id]) < accepted_replicates for item in comparisons
    ):
        attempts += 1
        draw = rng.integers(0, len(component_ids), size=len(component_ids))
        counts = [0] * len(component_ids)
        for index in draw:
            counts[int(index)] += 1
        if any(
            not any(
                counts[index] > 0
                for index, (control, candidate) in enumerate(
                    zip(series.control_losses, series.candidate_losses, strict=True)
                )
                if control is not None and candidate is not None
            )
            for series in comparisons
        ):
            continue
        deltas = {
            series.comparison_id: _weighted_series_delta(series, counts)
            for series in comparisons
        }
        for comparison_id, delta in deltas.items():
            values[comparison_id].append(delta)
    if any(
        len(values[item.comparison_id]) < accepted_replicates for item in comparisons
    ):
        raise OracleScoringError("bootstrap attempt exhaustion")
    summaries: list[BootstrapSummary] = []
    for series in comparisons:
        bootstrap_deltas = values[series.comparison_id]
        point_deltas = []
        for control, candidate in zip(
            series.control_losses, series.candidate_losses, strict=True
        ):
            if control is None:
                continue
            assert candidate is not None
            point_deltas.append(control - candidate)
        point_delta = _mean(
            point_deltas,
            "point contrast",
        )
        lower = _percentile(bootstrap_deltas, 0.025)
        summaries.append(
            BootstrapSummary(
                series.comparison_id,
                series.population_id,
                series.control_system_id,
                series.candidate_system_id,
                point_delta,
                lower,
                _percentile(bootstrap_deltas, 0.975),
                accepted_replicates,
                attempts,
                lower > 0.0,
            )
        )
    return tuple(summaries)


def top_influence(
    series: ContrastSeries,
    *,
    comparison_id: str = "G0-T0",
    limit: int = 10,
) -> tuple[InfluenceCheck, ...]:
    if limit <= 0:
        raise OracleScoringError("influence limit must be positive")
    if (series.control_system_id, series.candidate_system_id) != ("G0", "T0"):
        raise OracleScoringError("influence requires G0-T0 systems")
    _validate_comparison_series((series,))
    components = series.component_ids
    point_deltas: dict[str, float] = {}
    for component, control, candidate in zip(
        components, series.control_losses, series.candidate_losses, strict=True
    ):
        if control is None or candidate is None:
            raise OracleScoringError("influence requires complete component losses")
        point_deltas[component] = control - candidate
    ranking = sorted(
        components, key=lambda component: (-abs(point_deltas[component]), component)
    )[:limit]
    result: list[InfluenceCheck] = []
    for rank, component in enumerate(ranking, 1):
        remaining = [item for item in components if item != component]
        if not remaining:
            raise OracleScoringError("cannot leave out the only component")
        loo = _mean(
            (point_deltas[item] for item in remaining), "leave-one-out contrast"
        )
        result.append(
            InfluenceCheck(
                comparison_id,
                rank,
                component,
                abs(point_deltas[component]) / len(components),
                loo,
                loo > 0.0,
            )
        )
    return tuple(result)


def _validate_system_series(series: SystemSeries) -> None:
    if not series.component_ids or len(series.component_ids) != len(
        set(series.component_ids)
    ):
        raise OracleScoringError("system series components are invalid")
    if len(series.losses) != len(series.component_ids):
        raise OracleScoringError("system series lengths differ")
    if series.population_id == STRESS_POPULATION:
        raise OracleScoringError("stress series are diagnostic-only")
    for value in series.losses:
        _finite(value, "system loss")


def worst_component_decile(series: SystemSeries) -> tuple[str, ...]:
    _validate_system_series(series)
    if series.system_id != "G0":
        raise OracleScoringError("worst decile requires G0")
    losses = dict(zip(series.component_ids, series.losses, strict=True))
    ranked = sorted(series.component_ids, key=lambda item: (-losses[item], item))
    return tuple(ranked[: max(1, math.ceil(len(ranked) * 0.10))])


def fuse_safety_predictions(
    g0_predictions: Sequence[PredictionRow],
    t0_predictions: Sequence[PredictionRow],
    truths: Sequence[SealedTruth],
) -> tuple[PredictionRow, ...]:
    g0 = _prediction_public_map(g0_predictions, "G0")
    t0 = _prediction_public_map(t0_predictions, "T0")
    if len(g0) != len(g0_predictions) or len(t0) != len(t0_predictions):
        raise OracleScoringError("safety systems differ")
    truth_map: dict[tuple[str, str, int], SealedTruth] = {}
    for row in truths:
        _validate_truth(row)
        if row.public.key in truth_map:
            raise OracleScoringError("duplicate safety truth key")
        truth_map[row.public.key] = row
    if set(g0) != set(t0) or set(g0) != set(truth_map):
        raise OracleScoringError("safety supersets differ")
    for key in g0:
        if g0[key].public != t0[key].public or g0[key].public != truth_map[key].public:
            raise OracleScoringError("safety public metadata differs")
    output: list[PredictionRow] = []
    for key in sorted(g0, key=lambda item: (item[0], item[2], item[1])):
        truth = truth_map[key]
        all_row = (
            truth.public.episode_policy_id == "selected_anchor"
            and truth.selector_cyp_truth == "CYP3A4"
            and truth.query_point_available
        )
        g0_row, t0_row = g0[key], t0[key]
        local = all_row and truth.valid_true_transformation and truth.complete_anchor
        value = (
            (g0_row.prediction + t0_row.prediction) / 2.0
            if local
            else g0_row.prediction
        )
        output.append(
            PredictionRow(
                truth.public,
                "SAFETY_FUSION",
                _finite(value, "fusion prediction"),
                local,
                "G0_T0_HALF" if local else "G0",
                t0_row.extraction_status if local else g0_row.extraction_status,
                t0_row.similarity if local else g0_row.similarity,
                t0_row.exact_support_components
                if local
                else g0_row.exact_support_components,
                t0_row.class_support_components
                if local
                else g0_row.class_support_components,
                t0_row.activity_cliff if local else g0_row.activity_cliff,
            )
        )
    if not output:
        raise OracleScoringError("safety population is empty")
    return tuple(output)


def _prediction_public_map(
    rows: Sequence[PredictionRow], system_id: str
) -> dict[tuple[str, str, int], PredictionRow]:
    result: dict[tuple[str, str, int], PredictionRow] = {}
    public: dict[tuple[str, str, int], PublicQuery] = {}
    for row in rows:
        if row.system_id != system_id or row.public.key in result:
            raise OracleScoringError("duplicate or wrong safety prediction")
        if row.public.key in public and public[row.public.key] != row.public:
            raise OracleScoringError("safety public metadata differs")
        _finite(row.prediction, "prediction")
        public[row.public.key] = row.public
        result[row.public.key] = row
    return result


def safety_bootstrap(
    series: SafetySeries,
    *,
    seed: int = 20260822,
    accepted_replicates: int = 2000,
    maximum_attempts: int = 20000,
) -> SafetySummary:
    if series.population_id != SAFETY_POPULATION:
        raise OracleScoringError("safety population differs")
    if not series.component_ids or len(series.component_ids) != len(
        set(series.component_ids)
    ):
        raise OracleScoringError("safety components are invalid")
    if len(series.g0_losses) != len(series.component_ids) or len(
        series.fusion_losses
    ) != len(series.component_ids):
        raise OracleScoringError("safety systems are missing or misaligned")
    for value in (*series.g0_losses, *series.fusion_losses):
        _finite(value, "safety loss")
    components = series.component_ids
    worst = worst_component_decile(
        SystemSeries(SAFETY_POPULATION, "G0", components, series.g0_losses)
    )
    g0 = dict(zip(components, series.g0_losses, strict=True))
    fusion = dict(zip(components, series.fusion_losses, strict=True))
    g0_point = _mean((g0[item] for item in components), "G0 point")
    fusion_point = _mean((fusion[item] for item in components), "fusion point")
    point = _finite((fusion_point - g0_point) / g0_point, "relative degradation")
    worst_point = _finite(
        _mean((fusion[item] - g0[item] for item in worst), "worst degradation"),
        "worst degradation",
    )
    np = _numpy()
    rng = np.random.Generator(np.random.PCG64(seed))
    values: list[float] = []
    attempts = 0
    while attempts < maximum_attempts and len(values) < accepted_replicates:
        attempts += 1
        draw = rng.integers(0, len(components), size=len(components))
        counts = [0] * len(components)
        for index in draw:
            counts[int(index)] += 1
        denominator = math.fsum(
            count * g0[item] for count, item in zip(counts, components, strict=True)
        )
        numerator = math.fsum(
            count * fusion[item] for count, item in zip(counts, components, strict=True)
        )
        if (
            denominator == 0.0
            or not math.isfinite(denominator)
            or not math.isfinite(numerator)
        ):
            continue
        values.append(
            (numerator / len(components) - denominator / len(components))
            / (denominator / len(components))
        )
    if len(values) < accepted_replicates:
        raise OracleScoringError("safety bootstrap attempt exhaustion")
    lower, upper = _percentile(values, 0.025), _percentile(values, 0.975)
    return SafetySummary(
        SAFETY_POPULATION,
        point,
        lower,
        upper,
        len(values),
        attempts,
        upper < 0.01,
        worst,
        worst_point,
        worst_point <= 0.05,
    )


def resolve_status(
    *,
    integrity_status: str,
    support_status: str,
    predictions_status: str,
    bootstrap_summaries: Sequence[BootstrapSummary] | None = None,
    cell_contrasts: Sequence[CellContrast] | None = None,
    influence_checks: Sequence[InfluenceCheck] | None = None,
    safety: SafetySummary | None = None,
) -> str:
    if integrity_status not in {"PASS", "FAIL"}:
        raise OracleScoringError("integrity status differs")
    if support_status not in {"SUPPORTED", "UNDERPOWERED"}:
        raise OracleScoringError("support status differs")
    if predictions_status not in {"COMPLETE", "INCOMPLETE"}:
        raise OracleScoringError("prediction status differs")
    if integrity_status == "FAIL":
        return "R5_ORACLE_FAILED"
    if support_status == "UNDERPOWERED":
        return "R5_ORACLE_UNDERPOWERED"
    if predictions_status == "INCOMPLETE":
        return "R5_ORACLE_FAILED"
    if (
        bootstrap_summaries is None
        or cell_contrasts is None
        or influence_checks is None
        or safety is None
    ):
        raise OracleScoringError("complete status evidence is required")
    _validate_bootstrap_evidence(bootstrap_summaries)
    if len(cell_contrasts) != 15 or {
        (item.repeat, item.outer_fold) for item in cell_contrasts
    } != {(repeat, fold) for repeat in range(3) for fold in range(5)}:
        raise OracleScoringError("cell evidence must contain exactly 15 cells")
    if any(not math.isfinite(item.point_delta) for item in cell_contrasts):
        raise OracleScoringError("cell evidence is nonfinite")
    positive_cells = sum(item.point_delta > 0.0 for item in cell_contrasts)
    repeat_positive = [
        sum(item.point_delta > 0.0 for item in cell_contrasts if item.repeat == repeat)
        for repeat in range(3)
    ]
    if len(influence_checks) != 10 or {item.rank for item in influence_checks} != set(
        range(1, 11)
    ):
        raise OracleScoringError("influence evidence must contain exactly 10 ranks")
    if len({item.component_id for item in influence_checks}) != 10:
        raise OracleScoringError("influence component identities differ")
    if any(
        item.comparison_id != "G0-T0"
        or not math.isfinite(item.absolute_contribution)
        or not math.isfinite(item.loo_point_delta)
        or item.direction_preserved != (item.loo_point_delta > 0.0)
        for item in influence_checks
    ):
        raise OracleScoringError("influence evidence differs")
    _validate_safety_evidence(safety)
    signal_pass = (
        all(item.lower_bound_positive for item in bootstrap_summaries)
        and positive_cells >= 12
        and all(count >= 3 for count in repeat_positive)
        and all(item.direction_preserved for item in influence_checks)
        and safety.upper_bound_below_criterion
        and safety.worst_decile_criterion
    )
    return "R5_ORACLE_SIGNAL_PASS" if signal_pass else "R5_ORACLE_NO_SIGNAL"


def _validate_bootstrap_evidence(summaries: Sequence[BootstrapSummary]) -> None:
    expected = {
        comparison_id: (control, candidate, local)
        for comparison_id, control, candidate, local in REQUIRED_CONTRASTS
    }
    if len(summaries) != len(expected) or {
        item.comparison_id for item in summaries
    } != set(expected):
        raise OracleScoringError("bootstrap evidence must contain 10 comparisons")
    if len({item.attempts for item in summaries}) != 1:
        raise OracleScoringError("bootstrap attempts are not shared")
    for item in summaries:
        control, candidate, local = expected[item.comparison_id]
        if (item.control_system_id, item.candidate_system_id) != (control, candidate):
            raise OracleScoringError("bootstrap comparison systems differ")
        expected_population = f"local:{control}" if local else PRIMARY_POPULATION
        if item.population_id != expected_population:
            raise OracleScoringError("local bootstrap population differs")
        if item.accepted_replicates != 2000 or not (0 < item.attempts <= 20000):
            raise OracleScoringError("bootstrap counts differ")
        if not all(
            math.isfinite(value)
            for value in (item.point_delta, item.lower_95, item.upper_95)
        ):
            raise OracleScoringError("bootstrap interval is nonfinite")
        if item.lower_95 > item.upper_95:
            raise OracleScoringError("bootstrap interval is reversed")
        if item.lower_bound_positive != (item.lower_95 > 0.0):
            raise OracleScoringError("bootstrap criterion differs")


def _validate_safety_evidence(safety: SafetySummary) -> None:
    if safety.population_id != SAFETY_POPULATION:
        raise OracleScoringError("safety evidence population differs")
    if safety.accepted_replicates != 2000 or not (0 < safety.attempts <= 20000):
        raise OracleScoringError("safety bootstrap counts differ")
    if not all(
        math.isfinite(value)
        for value in (
            safety.point_relative_degradation,
            safety.lower_95,
            safety.upper_95,
            safety.worst_decile_point_degradation,
        )
    ):
        raise OracleScoringError("safety evidence is nonfinite")
    if safety.upper_bound_below_criterion != (safety.upper_95 < 0.01):
        raise OracleScoringError("safety upper criterion differs")
    if safety.worst_decile_criterion != (safety.worst_decile_point_degradation <= 0.05):
        raise OracleScoringError("safety worst-decile criterion differs")


def _numpy() -> Any:
    try:
        return import_module("numpy")
    except ImportError as exc:  # pragma: no cover - benchmark extra is installed in CI
        raise OracleScoringError("numpy is required for bootstrap") from exc


__all__ = [
    "BootstrapSummary",
    "CellContrast",
    "ContrastSeries",
    "InfluenceCheck",
    "SafetySeries",
    "SafetySummary",
    "SystemSeries",
    "bootstrap_contrasts",
    "comparison_series",
    "fuse_safety_predictions",
    "make_contrast_series",
    "resolve_status",
    "safety_bootstrap",
    "top_influence",
    "worst_component_decile",
]
