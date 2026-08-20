"""Pure R5C scoring and resampling; no I/O, models, or challenge access."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypeAlias

if TYPE_CHECKING:
    from cypshift.openadmet_oracle_statistics import CellContrast

SELECTED_POLICY: Final = "selected_anchor"
STRESS_POLICY: Final = "deterministic_random_anchor_stress"
PRIMARY_POPULATION: Final = "primary_local_eligible"
SAFETY_POPULATION: Final = "all_row_safety"
STRESS_POPULATION: Final = "diagnostic_stress"
REQUIRED_CONTRASTS: Final = (
    ("G0-T0", "G0", "T0", False),
    ("C0-T0", "C0", "T0", False),
    ("C1-T0", "C1", "T0", False),
    ("C2-T0", "C2", "T0", False),
    ("C3-T0", "C3", "T0", False),
    ("F0-T0", "F0", "T0", False),
    ("F1-T0", "F1", "T0", False),
    ("F2-T0", "F2", "T0", False),
    ("F0_LOCAL-T0", "F0", "T0", True),
    ("F1_LOCAL-T0", "F1", "T0", True),
)
EXPECTED_GRIDS: Final = {
    "C2": frozenset({(1.0, None), (10.0, None)}),
    "A2": frozenset({(1.0, None), (10.0, None)}),
    "T0": frozenset({(1.0, 2.0), (1.0, 10.0), (10.0, 2.0), (10.0, 10.0)}),
    "C3": frozenset({(1.0, 2.0), (1.0, 10.0), (10.0, 2.0), (10.0, 10.0)}),
    "A0": frozenset({(None, 2.0), (None, 10.0)}),
    "A1": frozenset({(None, 2.0), (None, 10.0)}),
}
Key: TypeAlias = tuple[str, str, int]
MetadataKey: TypeAlias = tuple[str, str, int, str, int, int, str, str]


class OracleScoringError(ValueError):
    """Frozen scoring invariant failed."""


@dataclass(frozen=True, slots=True)
class PublicQuery:
    episode_id: str
    query_molecule_id: str
    query_rank: int
    episode_policy_id: str
    repeat: int
    outer_fold: int
    component_id: str

    @property
    def key(self) -> Key:
        return (self.episode_id, self.query_molecule_id, self.query_rank)


@dataclass(frozen=True, slots=True)
class SealedTruth:
    public: PublicQuery
    selector_cyp_truth: str
    query_point: float | None
    query_point_available: bool
    valid_true_transformation: bool
    complete_anchor: bool


@dataclass(frozen=True, slots=True)
class PredictionRow:
    public: PublicQuery
    system_id: str
    prediction: float
    local_available: bool = False
    prediction_source: str = "G0"
    extraction_status: str = ""
    similarity: float | None = None
    exact_support_components: int = 0
    class_support_components: int = 0
    activity_cliff: bool = False


@dataclass(frozen=True, slots=True)
class ScoredRow:
    episode_id: str
    query_molecule_id: str
    query_rank: int
    episode_policy_id: str
    repeat: int
    outer_fold: int
    component_id: str
    population_id: str
    system_id: str
    local_eligible: bool
    local_available: bool
    prediction_source: str
    extraction_status: str
    similarity: float | None
    exact_support_components: int
    class_support_components: int
    activity_cliff: bool
    similarity_bin: str
    support_bin: str
    absolute_error: float
    query_weight: float
    episode_weight: float
    component_weight: float

    @property
    def key(self) -> Key:
        return (self.episode_id, self.query_molecule_id, self.query_rank)

    @property
    def metadata_key(self) -> MetadataKey:
        return (
            *self.key,
            self.episode_policy_id,
            self.repeat,
            self.outer_fold,
            self.component_id,
            self.population_id,
        )


@dataclass(frozen=True, slots=True)
class MetricResult:
    population_id: str
    system_id: str
    scored_rows: int
    scored_episodes: int
    scored_components: int
    query_macro_mae: float
    episode_macro_mae: float
    component_macro_mae: float
    component_losses: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class CellMetric:
    population_id: str
    system_id: str
    repeat: int
    outer_fold: int
    scored_rows: int
    scored_episodes: int
    scored_components: int
    query_macro_mae: float
    episode_macro_mae: float
    component_macro_mae: float


@dataclass(frozen=True, slots=True)
class ContrastResult:
    comparison_id: str
    population_id: str
    control_system_id: str
    candidate_system_id: str
    point_delta: float


@dataclass(frozen=True, slots=True)
class StressDiagnostic:
    selected_component_macro_mae: float
    random_component_macro_mae: float
    selected_vs_random_delta: float
    scored_rows: int
    outer_only: bool = True
    population_id: str = STRESS_POPULATION


@dataclass(frozen=True, slots=True)
class InnerCandidate:
    system_id: str
    repeat: int
    outer_fold: int
    candidate_id: str
    alpha: float | None
    lambda_value: float | None
    inner_component_macro_mae: float
    inner_scored_rows: int = 0
    inner_scored_components: int = 0
    population_id: str = PRIMARY_POPULATION


@dataclass(frozen=True, slots=True)
class SelectedCandidate:
    system_id: str
    repeat: int
    outer_fold: int
    candidate_id: str
    alpha: float | None
    lambda_value: float | None
    inner_component_macro_mae: float


def _finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise OracleScoringError(f"{label} must be finite")
    return float(value)


def _mean(values: Iterable[float], label: str = "mean") -> float:
    values_tuple = tuple(values)
    if not values_tuple:
        raise OracleScoringError(f"cannot compute empty {label}")
    return _finite(math.fsum(values_tuple) / len(values_tuple), label)


def _validate_truth(row: SealedTruth) -> None:
    if row.public.episode_policy_id not in {SELECTED_POLICY, STRESS_POLICY}:
        raise OracleScoringError("unknown episode policy")
    if row.query_point_available:
        if row.query_point is None:
            raise OracleScoringError("available truth has no point")
        _finite(row.query_point, "query point")
    elif row.query_point is not None:
        raise OracleScoringError("unavailable truth exposes a point")
    if not isinstance(row.valid_true_transformation, bool) or not isinstance(
        row.complete_anchor, bool
    ):
        raise OracleScoringError("eligibility fields must be booleans")


def _join(
    predictions: Sequence[PredictionRow], truths: Sequence[SealedTruth], system_id: str
) -> tuple[tuple[PredictionRow, SealedTruth], ...]:
    if not predictions or not truths:
        raise OracleScoringError("prediction and truth supersets must be non-empty")
    truth_map: dict[Key, SealedTruth] = {}
    for truth in truths:
        _validate_truth(truth)
        if truth.public.key in truth_map:
            if truth_map[truth.public.key].public != truth.public:
                raise OracleScoringError("truth public metadata differs")
            raise OracleScoringError("duplicate sealed truth key")
        truth_map[truth.public.key] = truth
    prediction_map: dict[Key, PredictionRow] = {}
    for prediction in predictions:
        if prediction.system_id != system_id:
            raise OracleScoringError("prediction system differs")
        _finite(prediction.prediction, "prediction")
        if prediction.public.key in prediction_map:
            if prediction_map[prediction.public.key].public != prediction.public:
                raise OracleScoringError("prediction public metadata differs")
            raise OracleScoringError("duplicate prediction key")
        prediction_map[prediction.public.key] = prediction
    if set(prediction_map) != set(truth_map):
        raise OracleScoringError("prediction superset differs from sealed truth")
    joined: list[tuple[PredictionRow, SealedTruth]] = []
    for key in sorted(truth_map, key=lambda key: (key[0], key[2], key[1])):
        prediction, truth = prediction_map[key], truth_map[key]
        if prediction.public != truth.public:
            raise OracleScoringError("prediction/truth public metadata differs")
        joined.append((prediction, truth))
    return tuple(joined)


def _similarity_bin(similarity: float | None) -> str:
    if similarity is None:
        return "unknown"
    value = _finite(similarity, "similarity")
    if value < 0.60:
        return "lt_0.60"
    if value < 0.70:
        return "0.60_0.70"
    if value < 0.80:
        return "0.70_0.80"
    return "ge_0.80"


def _support_bin(exact: int, class_support: int) -> str:
    if exact < 0 or class_support < 0:
        raise OracleScoringError("support must be nonnegative")
    if exact > 0:
        return "exact"
    if class_support > 0:
        return "class_only"
    return "none"


def _score_population(
    predictions: Sequence[PredictionRow],
    truths: Sequence[SealedTruth],
    *,
    system_id: str,
    population_id: str,
    policy: str,
) -> tuple[ScoredRow, ...]:
    if population_id not in {
        PRIMARY_POPULATION,
        SAFETY_POPULATION,
        STRESS_POPULATION,
    }:
        raise OracleScoringError("stress or unknown population cannot be scored")
    joined = _join(predictions, truths, system_id)
    selected: list[tuple[PredictionRow, SealedTruth]] = []
    for prediction, truth in joined:
        public = truth.public
        if public.episode_policy_id != policy:
            continue
        if truth.selector_cyp_truth != "CYP3A4" or not truth.query_point_available:
            continue
        if population_id in {PRIMARY_POPULATION, STRESS_POPULATION} and not (
            truth.valid_true_transformation and truth.complete_anchor
        ):
            continue
        selected.append((prediction, truth))
    if not selected:
        raise OracleScoringError("scored population is empty")
    query_counts: defaultdict[str, int] = defaultdict(int)
    episode_keys: defaultdict[tuple[str, int], set[str]] = defaultdict(set)
    component_repeats: defaultdict[str, set[int]] = defaultdict(set)
    for _, truth in selected:
        public = truth.public
        query_counts[public.episode_id] += 1
        episode_keys[(public.component_id, public.repeat)].add(public.episode_id)
        component_repeats[public.component_id].add(public.repeat)
    episode_counts = {key: len(value) for key, value in episode_keys.items()}
    result: list[ScoredRow] = []
    for prediction, truth in selected:
        public = truth.public
        assert truth.query_point is not None
        local_eligible = bool(truth.valid_true_transformation and truth.complete_anchor)
        error = absolute_loss(prediction.prediction, truth.query_point)
        result.append(
            ScoredRow(
                public.episode_id,
                public.query_molecule_id,
                public.query_rank,
                public.episode_policy_id,
                public.repeat,
                public.outer_fold,
                public.component_id,
                population_id,
                system_id,
                local_eligible,
                prediction.local_available,
                prediction.prediction_source,
                prediction.extraction_status,
                prediction.similarity,
                prediction.exact_support_components,
                prediction.class_support_components,
                prediction.activity_cliff,
                _similarity_bin(prediction.similarity),
                _support_bin(
                    prediction.exact_support_components,
                    prediction.class_support_components,
                ),
                error,
                1.0 / query_counts[public.episode_id],
                1.0 / episode_counts[(public.component_id, public.repeat)],
                1.0 / len(component_repeats[public.component_id]),
            )
        )
    return tuple(result)


def score_predictions(
    predictions: Sequence[PredictionRow],
    truths: Sequence[SealedTruth],
    *,
    system_id: str,
    population_id: str = PRIMARY_POPULATION,
) -> tuple[ScoredRow, ...]:
    if population_id not in {PRIMARY_POPULATION, SAFETY_POPULATION}:
        raise OracleScoringError("stress uses the diagnostic scorer")
    return _score_population(
        predictions,
        truths,
        system_id=system_id,
        population_id=population_id,
        policy=SELECTED_POLICY,
    )


def score_stress_predictions(
    predictions: Sequence[PredictionRow],
    truths: Sequence[SealedTruth],
    *,
    system_id: str,
) -> tuple[ScoredRow, ...]:
    """Score selected-vs-random stress rows in the outer diagnostic path only."""

    return _score_population(
        predictions,
        truths,
        system_id=system_id,
        population_id=STRESS_POPULATION,
        policy=STRESS_POLICY,
    )


def absolute_loss(prediction: float, truth: float) -> float:
    return _finite(
        abs(_finite(prediction, "prediction") - _finite(truth, "truth")), "loss"
    )


def aggregate_metrics(rows: Sequence[ScoredRow]) -> MetricResult:
    return _aggregate_metrics(rows, validate_weights=True)


def _aggregate_metrics(
    rows: Sequence[ScoredRow], *, validate_weights: bool
) -> MetricResult:
    _validate_scored_rows(rows, validate_weights=validate_weights)
    first = rows[0]
    by_episode: defaultdict[tuple[str, int, str], list[float]] = defaultdict(list)
    for row in rows:
        by_episode[(row.component_id, row.repeat, row.episode_id)].append(
            row.absolute_error
        )
    episode_loss = {
        key: _mean(values, "episode loss") for key, values in by_episode.items()
    }
    by_repeat_component: defaultdict[tuple[int, str], list[float]] = defaultdict(list)
    for (component, repeat, _), value in episode_loss.items():
        by_repeat_component[(repeat, component)].append(value)
    repeat_component = {
        key: _mean(values, "repeat/component loss")
        for key, values in by_repeat_component.items()
    }
    by_component: defaultdict[str, list[float]] = defaultdict(list)
    for (_repeat, component), value in repeat_component.items():
        by_component[component].append(value)
    component_loss = {
        component: _mean(values, "component loss")
        for component, values in by_component.items()
    }
    return MetricResult(
        first.population_id,
        first.system_id,
        len(rows),
        len(episode_loss),
        len(component_loss),
        _mean((row.absolute_error for row in rows), "query MAE"),
        _mean(episode_loss.values(), "episode MAE"),
        _mean(component_loss.values(), "component MAE"),
        tuple(sorted(component_loss.items())),
    )


def cell_metrics(rows: Sequence[ScoredRow]) -> tuple[CellMetric, ...]:
    _validate_scored_rows(rows)
    groups: defaultdict[tuple[int, int], list[ScoredRow]] = defaultdict(list)
    for row in rows:
        groups[(row.repeat, row.outer_fold)].append(row)
    result: list[CellMetric] = []
    for (repeat, outer_fold), cell_rows in sorted(groups.items()):
        metrics = _aggregate_metrics(cell_rows, validate_weights=False)
        result.append(
            CellMetric(
                metrics.population_id,
                metrics.system_id,
                repeat,
                outer_fold,
                metrics.scored_rows,
                metrics.scored_episodes,
                metrics.scored_components,
                metrics.query_macro_mae,
                metrics.episode_macro_mae,
                metrics.component_macro_mae,
            )
        )
    return tuple(result)


def stress_diagnostic(
    selected_rows: Sequence[ScoredRow], random_rows: Sequence[ScoredRow]
) -> StressDiagnostic:
    """Compare selected and random-anchor outer stress slices without authority."""

    selected = tuple(selected_rows)
    random = tuple(random_rows)
    _validate_scored_rows(selected)
    _validate_scored_rows(random)
    if selected[0].population_id != PRIMARY_POPULATION:
        raise OracleScoringError("selected stress comparator population differs")
    if random[0].population_id != STRESS_POPULATION:
        raise OracleScoringError("random stress population differs")
    if selected[0].system_id != random[0].system_id:
        raise OracleScoringError("stress diagnostic systems differ")
    selected_metric = aggregate_metrics(selected)
    random_metric = aggregate_metrics(random)
    return StressDiagnostic(
        selected_metric.component_macro_mae,
        random_metric.component_macro_mae,
        _finite(
            selected_metric.component_macro_mae - random_metric.component_macro_mae,
            "selected/random diagnostic",
        ),
        len(random),
    )


def _validate_scored_rows(
    rows: Sequence[ScoredRow], *, validate_weights: bool = True
) -> None:
    if not rows:
        raise OracleScoringError("scored rows are empty")
    first = rows[0]
    valid_populations = {
        PRIMARY_POPULATION,
        SAFETY_POPULATION,
        STRESS_POPULATION,
    }
    if first.population_id not in valid_populations:
        raise OracleScoringError("stress rows cannot enter scoring")
    keys: set[MetadataKey] = set()
    query_counts: defaultdict[str, int] = defaultdict(int)
    episode_counts: defaultdict[tuple[str, int], set[str]] = defaultdict(set)
    repeat_counts: defaultdict[str, set[int]] = defaultdict(set)
    for row in rows:
        if (row.episode_policy_id == STRESS_POLICY) != (
            first.population_id == STRESS_POPULATION
        ) or row.population_id != first.population_id:
            raise OracleScoringError("mixed or stress scoring population")
        if row.system_id != first.system_id or row.metadata_key in keys:
            raise OracleScoringError("scored row identity differs")
        keys.add(row.metadata_key)
        _finite(row.absolute_error, "absolute error")
        query_counts[row.episode_id] += 1
        episode_counts[(row.component_id, row.repeat)].add(row.episode_id)
        repeat_counts[row.component_id].add(row.repeat)
    if validate_weights:
        for row in rows:
            expected = (
                1.0 / query_counts[row.episode_id],
                1.0 / len(episode_counts[(row.component_id, row.repeat)]),
                1.0 / len(repeat_counts[row.component_id]),
            )
            actual = (row.query_weight, row.episode_weight, row.component_weight)
            if actual != expected:
                raise OracleScoringError("aggregation weights differ")


def contrast(
    rows: Sequence[ScoredRow],
    control_system_id: str,
    candidate_system_id: str,
    *,
    comparison_id: str | None = None,
    local_only: bool = False,
) -> ContrastResult:
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
    aggregate_metrics(control_all)
    aggregate_metrics(candidate_all)
    if control_all[0].population_id != candidate_all[0].population_id:
        raise OracleScoringError("comparison populations differ")
    if local_only:
        controls = {key: row for key, row in controls.items() if row.local_available}
        candidates = {key: row for key, row in candidates.items() if key in controls}
    if set(controls) != set(candidates):
        raise OracleScoringError("comparison metadata is not aligned")
    if not controls:
        raise OracleScoringError("local comparison is empty")
    control_rows = tuple(controls[key] for key in sorted(controls))
    candidate_rows = tuple(candidates[key] for key in sorted(candidates))
    if {row.population_id for row in control_rows} != {
        control_rows[0].population_id
    } or {row.population_id for row in candidate_rows} != {
        candidate_rows[0].population_id
    }:
        raise OracleScoringError("comparison population is mixed")
    if control_rows[0].population_id != candidate_rows[0].population_id:
        raise OracleScoringError("comparison populations differ")
    if local_only:
        control_metric = _aggregate_metrics(control_rows, validate_weights=False)
        candidate_metric = _aggregate_metrics(candidate_rows, validate_weights=False)
    else:
        control_metric = aggregate_metrics(control_rows)
        candidate_metric = aggregate_metrics(candidate_rows)
    control_map = dict(control_metric.component_losses)
    candidate_map = dict(candidate_metric.component_losses)
    if set(control_map) != set(candidate_map):
        raise OracleScoringError("comparison components differ")
    return ContrastResult(
        comparison_id or f"{control_system_id}-{candidate_system_id}",
        f"local:{control_system_id}" if local_only else control_rows[0].population_id,
        control_system_id,
        candidate_system_id,
        _mean(
            (control_map[item] - candidate_map[item] for item in sorted(control_map)),
            "contrast",
        ),
    )


def _metadata_map(rows: Sequence[ScoredRow]) -> dict[MetadataKey, ScoredRow]:
    result: dict[MetadataKey, ScoredRow] = {}
    public_metadata: dict[Key, MetadataKey] = {}
    for row in rows:
        prior = public_metadata.get(row.key)
        if prior is not None and prior != row.metadata_key:
            raise OracleScoringError("public row metadata differs")
        if row.metadata_key in result:
            raise OracleScoringError("duplicate contrast row")
        public_metadata[row.key] = row.metadata_key
        result[row.metadata_key] = row
    return result


def cell_contrasts(
    rows: Sequence[ScoredRow],
    control_system_id: str = "G0",
    candidate_system_id: str = "T0",
) -> tuple[CellContrast, ...]:
    """Return the exact 15 primary repeat/outer-fold contrasts."""

    from cypshift.openadmet_oracle_statistics import CellContrast

    selected = tuple(row for row in rows if row.population_id == PRIMARY_POPULATION)
    cells: list[CellContrast] = []
    for repeat in range(3):
        for outer_fold in range(5):
            subset = tuple(
                row
                for row in selected
                if row.repeat == repeat and row.outer_fold == outer_fold
            )
            if not subset:
                raise OracleScoringError("primary cell is missing")
            result = contrast(
                subset, control_system_id, candidate_system_id, comparison_id="G0-T0"
            )
            cells.append(CellContrast(repeat, outer_fold, result.point_delta))
    return tuple(cells)


def select_inner_candidates(
    candidates: Sequence[InnerCandidate],
) -> tuple[SelectedCandidate, ...]:
    if not candidates:
        raise OracleScoringError("candidate list is empty")
    groups: defaultdict[tuple[str, int, int], list[InnerCandidate]] = defaultdict(list)
    configs_by_system: defaultdict[str, set[tuple[float | None, float | None]]] = (
        defaultdict(set)
    )
    for candidate in candidates:
        if candidate.population_id != PRIMARY_POPULATION:
            raise OracleScoringError("stress candidate cannot enter selection")
        if candidate.system_id not in EXPECTED_GRIDS:
            raise OracleScoringError("unknown selectable system")
        if candidate.inner_scored_rows <= 0 or candidate.inner_scored_components <= 0:
            raise OracleScoringError("candidate support counts must be positive")
        _finite(candidate.inner_component_macro_mae, "inner metric")
        for value, label in (
            (candidate.alpha, "alpha"),
            (candidate.lambda_value, "lambda"),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0.0):
                raise OracleScoringError(f"invalid {label}")
        config = (candidate.alpha, candidate.lambda_value)
        configs_by_system[candidate.system_id].add(config)
        groups[(candidate.system_id, candidate.repeat, candidate.outer_fold)].append(
            candidate
        )
    for system_id, configs in configs_by_system.items():
        if configs != EXPECTED_GRIDS[system_id]:
            raise OracleScoringError("candidate hyperparameter grid differs")
    for (system_id, _, _), group in groups.items():
        counts = {
            (item.inner_scored_rows, item.inner_scored_components) for item in group
        }
        configs = {(item.alpha, item.lambda_value) for item in group}
        if (
            len(counts) != 1
            or configs != EXPECTED_GRIDS[system_id]
            or len(group) != len(configs)
            or len({item.candidate_id for item in group}) != len(group)
        ):
            raise OracleScoringError("candidate support/grid differs by scope")
    selected: list[SelectedCandidate] = []
    for group_key in sorted(groups):
        best = min(
            groups[group_key],
            key=lambda item: (
                item.inner_component_macro_mae,
                -(item.alpha if item.alpha is not None else float("-inf")),
                -(
                    item.lambda_value
                    if item.lambda_value is not None
                    else float("-inf")
                ),
                item.candidate_id,
            ),
        )
        selected.append(
            SelectedCandidate(
                best.system_id,
                best.repeat,
                best.outer_fold,
                best.candidate_id,
                best.alpha,
                best.lambda_value,
                best.inner_component_macro_mae,
            )
        )
    return tuple(selected)


__all__ = [
    "EXPECTED_GRIDS",
    "PRIMARY_POPULATION",
    "REQUIRED_CONTRASTS",
    "SAFETY_POPULATION",
    "STRESS_POPULATION",
    "STRESS_POLICY",
    "CellMetric",
    "ContrastResult",
    "InnerCandidate",
    "MetricResult",
    "OracleScoringError",
    "PredictionRow",
    "PublicQuery",
    "ScoredRow",
    "SealedTruth",
    "SelectedCandidate",
    "StressDiagnostic",
    "absolute_loss",
    "aggregate_metrics",
    "cell_contrasts",
    "cell_metrics",
    "contrast",
    "score_predictions",
    "score_stress_predictions",
    "select_inner_candidates",
    "stress_diagnostic",
]
