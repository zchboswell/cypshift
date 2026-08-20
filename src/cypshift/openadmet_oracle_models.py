"""Pure deterministic model primitives for the R5 TRACE experiment.

The module has no filesystem or challenge-data access.  It owns only the
small algebra used by later model cells: signed Morgan/MMP features, weighted
ridge, component-macro hierarchy shrinkage, deterministic controls, and the
uniform local-to-G0 fallback record.  NumPy is imported inside ridge methods so
the base package remains usable without the benchmark dependency group.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from importlib import import_module
from typing import Any, Final, Literal

BASE_SEED: Final = 20260820
ALPHA_VALUES: Final = (1.0, 10.0)
LAMBDA_VALUES: Final = (2.0, 10.0)
OTHER_CLASS: Final = "OTHER"


class OracleModelError(ValueError):
    """Raised when a model primitive receives an invalid scientific input."""


def _finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise OracleModelError(f"{label} must be finite")
    return float(value)


def _numeric_rows(rows: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    result = tuple(
        tuple(_finite(float(value), "feature") for value in row) for row in rows
    )
    if not result or not result[0]:
        raise OracleModelError("feature matrix must be non-empty")
    width = len(result[0])
    if any(len(row) != width for row in result):
        raise OracleModelError("feature rows have different widths")
    return result


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise OracleModelError("cannot summarize an empty column")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


@dataclass(frozen=True, slots=True)
class RobustScaler:
    """Column-wise median/IQR scaler with the frozen zero-IQR rule."""

    medians: tuple[float, ...]
    scales: tuple[float, ...]

    @classmethod
    def fit(cls, rows: Sequence[Sequence[float]]) -> RobustScaler:
        matrix = _numeric_rows(rows)
        columns = tuple(zip(*matrix, strict=True))
        medians = tuple(_percentile(column, 0.5) for column in columns)
        scales = tuple(
            (iqr if iqr > 0.0 else 1.0)
            for iqr in (
                _percentile(column, 0.75) - _percentile(column, 0.25)
                for column in columns
            )
        )
        return cls(medians, scales)

    def transform_row(self, row: Sequence[float]) -> tuple[float, ...]:
        if len(row) != len(self.medians):
            raise OracleModelError("feature width differs from fitted scaler")
        return tuple(
            (_finite(float(value), "feature") - center) / scale
            for value, center, scale in zip(row, self.medians, self.scales, strict=True)
        )


@dataclass(frozen=True, slots=True)
class PairFeatures:
    """Structural and categorical information for one directed pair."""

    signed_morgan: tuple[float, ...]
    cut_count: int
    changed_heavy_atom_fraction: float
    class_id: str
    exact_transformation_id: str
    environment_level_1_id: str
    environment_level_2_id: str


@dataclass(frozen=True, slots=True)
class PairExample:
    """One directed, weighted training delta and its immutable pair metadata."""

    pair_id: str
    direction_id: str
    anchor_molecule_id: str
    analog_molecule_id: str
    component_id: str
    target: float
    sample_weight: float
    features: PairFeatures
    direction_role: str


@dataclass(frozen=True, slots=True)
class HierarchyObservation:
    """A residual/delta observation used by component-macro hierarchy fitting."""

    component_id: str
    class_id: str
    exact_transformation_id: str
    environment_level_1_id: str
    environment_level_2_id: str
    target: float
    sample_weight: float


@dataclass(frozen=True, slots=True)
class RidgeFit:
    """Deterministic weighted ridge state, including its fitted scaler."""

    scaler: RobustScaler
    coefficients: tuple[float, ...]
    intercept: float
    alpha: float

    def predict_row(self, row: Sequence[float]) -> float:
        scaled = self.scaler.transform_row(row)
        value = self.intercept + sum(
            coefficient * feature
            for coefficient, feature in zip(self.coefficients, scaled, strict=True)
        )
        return _finite(value, "ridge prediction")

    def predict(self, rows: Sequence[Sequence[float]]) -> tuple[float, ...]:
        return tuple(self.predict_row(row) for row in rows)


@dataclass(frozen=True, slots=True)
class HierarchyFit:
    """Component-macro estimates at class/exact/environment levels."""

    class_values: Mapping[str, float]
    exact_values: Mapping[str, float]
    environment_level_1_values: Mapping[str, float]
    environment_level_2_values: Mapping[str, float]
    class_support: Mapping[str, int]
    exact_support: Mapping[str, int]
    environment_level_1_support: Mapping[str, int]
    environment_level_2_support: Mapping[str, int]
    level_order: tuple[str, ...]

    def predict(
        self,
        class_id: str,
        exact_transformation_id: str,
        environment_level_1_id: str,
        environment_level_2_id: str,
    ) -> tuple[float, str, int]:
        candidates = (
            (
                "environment_level_2",
                environment_level_2_id,
                self.environment_level_2_values,
                self.environment_level_2_support,
            ),
            (
                "environment_level_1",
                environment_level_1_id,
                self.environment_level_1_values,
                self.environment_level_1_support,
            ),
            ("exact", exact_transformation_id, self.exact_values, self.exact_support),
            ("class", class_id, self.class_values, self.class_support),
        )
        for level, key, values, support in candidates:
            if key and key in values:
                return values[key], level, support[key]
        return 0.0, "endpoint_zero", 0


@dataclass(frozen=True, slots=True)
class Prediction:
    """A local prediction or the required episode-specific G0 fallback."""

    value: float
    local_available: bool
    prediction_source: str
    fallback_reason: str | None
    hierarchy_level: str | None = None
    hierarchy_support_components: int = 0


@dataclass(frozen=True, slots=True)
class PairAntisymmetryDiagnostics:
    """Read-only reversal diagnostic; it never alters fitting or selection."""

    pair_count: int
    complete_pair_count: int
    missing_reverse_pair_count: int
    violating_pair_count: int
    max_absolute_delta_sum: float


@dataclass(frozen=True, slots=True)
class PredictedDelta:
    """One pre-anchor directional prediction used only for reversal checks."""

    pair_id: str
    direction_role: str
    delta: float


def signed_morgan_difference(
    anchor_bits: Sequence[int], analog_bits: Sequence[int]
) -> tuple[float, ...]:
    """Return exact ``analog - anchor`` signed Morgan bits in column order."""

    if len(anchor_bits) != len(analog_bits) or not anchor_bits:
        raise OracleModelError("Morgan vectors must have equal non-zero widths")
    result: list[float] = []
    for anchor, analog in zip(anchor_bits, analog_bits, strict=True):
        if anchor not in (0, 1) or analog not in (0, 1):
            raise OracleModelError("Morgan vectors must contain only binary bits")
        result.append(float(int(analog) - int(anchor)))
    return tuple(result)


def pair_feature_vector(
    pair: PairFeatures,
    class_vocabulary: Sequence[str],
    *,
    anchor_context: float | None = None,
    include_context: bool = False,
) -> tuple[float, ...]:
    """Build frozen structural features and an optional anchor-state column.

    The class vocabulary is fit on current training rows.  A validation class
    absent from it is represented by one explicit ``OTHER`` column.
    """

    vocabulary = tuple(class_vocabulary)
    if (
        len(vocabulary) != len(set(vocabulary))
        or OTHER_CLASS in vocabulary
        or vocabulary != tuple(sorted(vocabulary))
    ):
        raise OracleModelError("class vocabulary must be unique and omit OTHER")
    if any(not item for item in vocabulary):
        raise OracleModelError("class vocabulary contains an empty class")
    if pair.cut_count < 0:
        raise OracleModelError("cut count must be nonnegative")
    fraction = _finite(pair.changed_heavy_atom_fraction, "changed fraction")
    if fraction < 0.0 or fraction > 1.0:
        raise OracleModelError("changed fraction must be in [0, 1]")
    if include_context and anchor_context is None:
        raise OracleModelError("contextual features require an anchor state")
    one_hot = [0.0] * (len(vocabulary) + 1)
    try:
        one_hot[vocabulary.index(pair.class_id)] = 1.0
    except ValueError:
        one_hot[-1] = 1.0
    result = tuple(float(value) for value in pair.signed_morgan)
    if include_context:
        if anchor_context is None:
            raise OracleModelError("contextual features require an anchor state")
        result += (_finite(float(anchor_context), "anchor context"),)
    return result + (float(pair.cut_count), fraction) + tuple(one_hot)


def generic_feature_vector(
    pair: PairFeatures, *, anchor_context: float | None = None
) -> tuple[float, ...]:
    """Build C2's signed-Morgan plus optional anchor-state representation."""

    result = tuple(float(value) for value in pair.signed_morgan)
    if anchor_context is not None:
        result += (_finite(float(anchor_context), "anchor context"),)
    return result


def fit_weighted_ridge(
    features: Sequence[Sequence[float]],
    targets: Sequence[float],
    sample_weights: Sequence[float],
    *,
    alpha: float,
) -> RidgeFit:
    """Fit intercept-unregularized weighted ridge after median/IQR scaling."""

    if len(features) != len(targets) or len(features) != len(sample_weights):
        raise OracleModelError("ridge inputs have different row counts")
    if alpha <= 0.0 or not math.isfinite(alpha):
        raise OracleModelError("ridge alpha must be positive and finite")
    matrix = _numeric_rows(features)
    values = tuple(_finite(float(target), "target") for target in targets)
    weights = tuple(
        _finite(float(weight), "sample weight") for weight in sample_weights
    )
    if any(weight <= 0.0 for weight in weights):
        raise OracleModelError("sample weights must be positive")
    scaler = RobustScaler.fit(matrix)
    scaled = tuple(scaler.transform_row(row) for row in matrix)
    np: Any = import_module("numpy")
    width = len(scaled[0])
    design = np.asarray(tuple((1.0, *row) for row in scaled), dtype=float)
    weight_array = np.asarray(weights, dtype=float)
    target_array = np.asarray(values, dtype=float)
    normal = design.T @ (weight_array[:, None] * design)
    normal[1:, 1:] += float(alpha) * np.eye(width)
    right = design.T @ (weight_array * target_array)
    try:
        solution = np.linalg.solve(normal, right)
    except np.linalg.LinAlgError:
        solution = np.linalg.lstsq(normal, right, rcond=None)[0]
    if not np.all(np.isfinite(solution)):
        raise OracleModelError("ridge fit is non-finite")
    return RidgeFit(
        scaler,
        tuple(float(value) for value in solution[1:]),
        float(solution[0]),
        float(alpha),
    )


def _component_macro(
    observations: Sequence[HierarchyObservation],
    key_name: str,
) -> tuple[dict[str, float], dict[str, int]]:
    by_key_component: dict[tuple[str, str], list[HierarchyObservation]] = defaultdict(
        list
    )
    for observation in observations:
        key = getattr(observation, key_name)
        if key:
            by_key_component[(key, observation.component_id)].append(observation)
    values: dict[str, float] = {}
    support: dict[str, int] = {}
    by_key: dict[str, list[float]] = defaultdict(list)
    for (key, _component), rows in by_key_component.items():
        total_weight = sum(row.sample_weight for row in rows)
        if total_weight <= 0.0:
            raise OracleModelError("hierarchy component has no positive weight")
        by_key[key].append(
            sum(row.target * row.sample_weight for row in rows) / total_weight
        )
    for key, component_means in by_key.items():
        values[key] = sum(component_means) / len(component_means)
        support[key] = len(component_means)
    return values, support


def _shrink(direct: float, support: int, broader: float, lambda_: float) -> float:
    return (support * direct + lambda_ * broader) / (support + lambda_)


def fit_hierarchy(
    observations: Sequence[HierarchyObservation], *, lambda_: float, stop_after: str
) -> HierarchyFit:
    """Fit class/exact/environment residual means with component-macro shrinkage."""

    if lambda_ <= 0.0 or not math.isfinite(lambda_):
        raise OracleModelError("hierarchy lambda must be positive and finite")
    if stop_after not in {"class", "full"}:
        raise OracleModelError("hierarchy stop level must be class or full")
    if not observations:
        raise OracleModelError("hierarchy needs at least one observation")
    for row in observations:
        _finite(row.target, "hierarchy target")
        if row.sample_weight <= 0.0 or not math.isfinite(row.sample_weight):
            raise OracleModelError("hierarchy weights must be positive")
    class_raw, class_support = _component_macro(observations, "class_id")
    class_values = {
        key: _shrink(value, class_support[key], 0.0, lambda_)
        for key, value in class_raw.items()
    }
    empty: dict[str, float] = {}
    empty_support: dict[str, int] = {}
    if stop_after == "class":
        return HierarchyFit(
            class_values,
            empty,
            empty,
            empty,
            class_support,
            empty_support,
            empty_support,
            empty_support,
            ("endpoint_zero", "class"),
        )
    exact_raw, exact_support = _component_macro(observations, "exact_transformation_id")
    exact_parent = {
        key: _parent_value(
            observations,
            "exact_transformation_id",
            key,
            "class_id",
            class_values,
        )
        for key in exact_raw
    }
    exact_values = {
        key: _shrink(value, exact_support[key], exact_parent[key], lambda_)
        for key, value in exact_raw.items()
    }
    env1_raw, env1_support = _component_macro(observations, "environment_level_1_id")
    env1_values = {
        key: _shrink(
            value,
            env1_support[key],
            _parent_value(
                observations,
                "environment_level_1_id",
                key,
                "exact_transformation_id",
                exact_values,
            ),
            lambda_,
        )
        for key, value in env1_raw.items()
    }
    env2_raw, env2_support = _component_macro(observations, "environment_level_2_id")
    env2_values = {
        key: _shrink(
            value,
            env2_support[key],
            _parent_value(
                observations,
                "environment_level_2_id",
                key,
                "environment_level_1_id",
                env1_values,
            ),
            lambda_,
        )
        for key, value in env2_raw.items()
    }
    return HierarchyFit(
        class_values,
        exact_values,
        env1_values,
        env2_values,
        class_support,
        exact_support,
        env1_support,
        env2_support,
        (
            "endpoint_zero",
            "class",
            "exact",
            "environment_level_1",
            "environment_level_2",
        ),
    )


def _parent_value(
    observations: Sequence[HierarchyObservation],
    child_level: str,
    child_key: str,
    parent_level: str,
    parent_values: Mapping[str, float],
) -> float:
    parents = sorted(
        {
            getattr(row, parent_level)
            for row in observations
            if getattr(row, child_level) == child_key
        }
    )
    if not parents:
        return 0.0
    if len(parents) != 1:
        raise OracleModelError("hierarchy child maps to conflicting parents")
    return parent_values.get(parents[0], 0.0)


@dataclass(frozen=True, slots=True)
class TraceModel:
    """Reusable delta model for C2/T0/C3/A0/A1/A2/F2."""

    system_id: str
    ridge: RidgeFit | None
    hierarchy: HierarchyFit | None
    class_vocabulary: tuple[str, ...]
    feature_spec: Literal["none", "generic_context", "structural_context", "structural"]

    def predict_delta(
        self,
        pair: PairFeatures,
        *,
        anchor_context: float | None = None,
    ) -> tuple[float, str | None, int]:
        if self.ridge is None:
            base = 0.0
        else:
            if self.feature_spec == "generic_context":
                if anchor_context is None:
                    raise OracleModelError("generic context model needs anchor context")
                features = generic_feature_vector(pair, anchor_context=anchor_context)
            elif self.feature_spec == "structural_context":
                features = pair_feature_vector(
                    pair,
                    self.class_vocabulary,
                    anchor_context=anchor_context,
                    include_context=True,
                )
            elif self.feature_spec == "structural":
                features = pair_feature_vector(pair, self.class_vocabulary)
            else:
                raise OracleModelError("ridge model has no feature specification")
            base = self.ridge.predict_row(features)
        if self.hierarchy is None:
            return _finite(base, "delta prediction"), None, 0
        correction, level, support = self.hierarchy.predict(
            pair.class_id,
            pair.exact_transformation_id,
            pair.environment_level_1_id,
            pair.environment_level_2_id,
        )
        return _finite(base + correction, "delta prediction"), level, support


def _examples_and_context(
    examples: Sequence[PairExample],
    contexts: Mapping[str, float] | None,
    class_vocabulary: tuple[str, ...],
    *,
    generic: bool = False,
    include_anchor_context: bool = False,
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...], tuple[float, ...]]:
    if not examples:
        raise OracleModelError("model needs at least one pair")
    rows: list[tuple[float, ...]] = []
    targets: list[float] = []
    weights: list[float] = []
    for example in examples:
        anchor: float | None = None
        if include_anchor_context:
            if contexts is None or example.anchor_molecule_id not in contexts:
                raise OracleModelError("anchor context is missing")
            anchor = contexts[example.anchor_molecule_id]
        row = (
            generic_feature_vector(
                example.features,
                anchor_context=anchor,
            )
            if generic
            else pair_feature_vector(
                example.features,
                class_vocabulary,
                anchor_context=anchor,
                include_context=include_anchor_context,
            )
        )
        rows.append(row)
        targets.append(example.target)
        weights.append(example.sample_weight)
    return tuple(rows), tuple(targets), tuple(weights)


def _hierarchy_observations(
    examples: Sequence[PairExample], residuals: Sequence[float]
) -> tuple[HierarchyObservation, ...]:
    if len(examples) != len(residuals):
        raise OracleModelError("residual row count differs")
    return tuple(
        HierarchyObservation(
            example.component_id,
            example.features.class_id,
            example.features.exact_transformation_id,
            example.features.environment_level_1_id,
            example.features.environment_level_2_id,
            residual,
            example.sample_weight,
        )
        for example, residual in zip(examples, residuals, strict=True)
    )


def fit_c2(
    examples: Sequence[PairExample],
    measured_anchor_points: Mapping[str, float],
    *,
    alpha: float,
) -> TraceModel:
    """Fit generic signed-Morgan delta ridge; add measured anchor at output."""

    rows, targets, weights = _examples_and_context(
        examples,
        measured_anchor_points,
        (),
        generic=True,
        include_anchor_context=True,
    )
    return TraceModel(
        "C2",
        fit_weighted_ridge(rows, targets, weights, alpha=alpha),
        None,
        (),
        "generic_context",
    )


def fit_t0(
    examples: Sequence[PairExample],
    measured_anchor_points: Mapping[str, float],
    *,
    alpha: float,
    lambda_: float,
) -> TraceModel:
    """Fit structural ridge plus residual hierarchy; add anchor at output."""

    vocabulary = tuple(sorted({row.features.class_id for row in examples}))
    rows, targets, weights = _examples_and_context(
        examples,
        measured_anchor_points,
        vocabulary,
        include_anchor_context=True,
    )
    ridge = fit_weighted_ridge(rows, targets, weights, alpha=alpha)
    residuals = tuple(
        target - ridge.predict_row(row)
        for target, row in zip(targets, rows, strict=True)
    )
    hierarchy = fit_hierarchy(
        _hierarchy_observations(examples, residuals), lambda_=lambda_, stop_after="full"
    )
    return TraceModel("T0", ridge, hierarchy, vocabulary, "structural_context")


def fit_c3(
    examples: Sequence[PairExample],
    *,
    alpha: float,
    lambda_: float,
) -> TraceModel:
    """Fit C3 deltas from structure alone.

    The pure G0 OOF anchor prediction is episode-specific and is supplied only
    when producing an absolute prediction.  It is never needed for fitting.
    """

    vocabulary = tuple(sorted({row.features.class_id for row in examples}))
    rows, targets, weights = _examples_and_context(examples, None, vocabulary)
    ridge = fit_weighted_ridge(rows, targets, weights, alpha=alpha)
    residuals = tuple(
        target - ridge.predict_row(row)
        for target, row in zip(targets, rows, strict=True)
    )
    hierarchy = fit_hierarchy(
        _hierarchy_observations(examples, residuals), lambda_=lambda_, stop_after="full"
    )
    return TraceModel("C3", ridge, hierarchy, vocabulary, "structural")


def fit_a0(examples: Sequence[PairExample], *, lambda_: float) -> TraceModel:
    """Fit transformation-class-only raw delta hierarchy."""

    hierarchy = fit_hierarchy(
        _hierarchy_observations(examples, [row.target for row in examples]),
        lambda_=lambda_,
        stop_after="class",
    )
    return TraceModel("A0", None, hierarchy, (), "none")


def fit_a1(examples: Sequence[PairExample], *, lambda_: float) -> TraceModel:
    """Fit full raw delta hierarchy without contextual ridge."""

    hierarchy = fit_hierarchy(
        _hierarchy_observations(examples, [row.target for row in examples]),
        lambda_=lambda_,
        stop_after="full",
    )
    return TraceModel("A1", None, hierarchy, (), "none")


def fit_a2(
    examples: Sequence[PairExample],
    measured_anchor_points: Mapping[str, float],
    *,
    alpha: float,
) -> TraceModel:
    """Fit contextual signed-Morgan/MMP/class ridge without hierarchy."""

    vocabulary = tuple(sorted({row.features.class_id for row in examples}))
    rows, targets, weights = _examples_and_context(
        examples,
        measured_anchor_points,
        vocabulary,
        include_anchor_context=True,
    )
    ridge = fit_weighted_ridge(rows, targets, weights, alpha=alpha)
    return TraceModel("A2", ridge, None, vocabulary, "structural_context")


def fit_f2(
    examples: Sequence[PairExample],
    measured_anchor_points: Mapping[str, float],
    *,
    alpha: float,
    lambda_: float,
    seed: int,
) -> TraceModel:
    """Fit T0 after one deterministic complete categorical-tuple permutation."""

    permuted = permute_category_contexts(examples, seed=seed)
    fitted = fit_t0(
        permuted,
        measured_anchor_points,
        alpha=alpha,
        lambda_=lambda_,
    )
    return replace(fitted, system_id="F2")


def predict_local(
    model: TraceModel,
    pair: PairFeatures,
    *,
    anchor_context: float | None,
    g0_prediction: float,
) -> Prediction:
    """Predict locally, falling back to finite G0 with explicit metadata."""

    fallback = _finite(float(g0_prediction), "G0 prediction")
    if anchor_context is None:
        return Prediction(fallback, False, "G0", "missing_anchor_context")
    delta, level, support = model.predict_delta(pair, anchor_context=anchor_context)
    value = _finite(float(anchor_context) + delta, "local prediction")
    return Prediction(value, True, "LOCAL", None, level, support)


def scoped_seed(
    base_seed: int,
    system_id: str,
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    query_id_or_fit: str,
) -> int:
    """Derive the exact unsigned 64-bit PCG64 scope seed from frozen material."""

    if repeat < 0 or outer_fold < 0 or (inner_fold is not None and inner_fold < 0):
        raise OracleModelError("fold indices must be nonnegative")
    material = "|".join(
        (
            str(base_seed),
            system_id,
            str(repeat),
            str(outer_fold),
            str(-1 if inner_fold is None else inner_fold),
            query_id_or_fit,
        )
    ).encode("utf-8")
    return int.from_bytes(sha256(material).digest()[:8], "big", signed=False)


def deterministic_permutation(values: Sequence[Any], *, seed: int) -> tuple[Any, ...]:
    """Return a deterministic PCG64 permutation without mutating the input."""

    np: Any = import_module("numpy")
    if seed < 0 or seed >= 1 << 64:
        raise OracleModelError("PCG64 seed must be an unsigned 64-bit integer")
    order = np.random.Generator(np.random.PCG64(seed)).permutation(len(values))
    return tuple(values[int(index)] for index in order)


def permute_category_contexts(
    examples: Sequence[PairExample], *, seed: int
) -> tuple[PairExample, ...]:
    """F2 control: permute complete directional category tuples by pair."""

    by_pair: dict[str, list[PairExample]] = defaultdict(list)
    for example in examples:
        by_pair[example.pair_id].append(example)
    pair_ids = tuple(sorted(by_pair))
    if any(len(by_pair[pair_id]) != 2 for pair_id in pair_ids):
        raise OracleModelError("F2 requires exactly two directions per pair")
    by_pair_role: dict[str, dict[str, PairExample]] = {}
    for pair_id in pair_ids:
        roles = {row.direction_role: row for row in by_pair[pair_id]}
        if set(roles) != {"a_to_b", "b_to_a"} or len(roles) != 2:
            raise OracleModelError("F2 requires exact a_to_b and b_to_a roles")
        by_pair_role[pair_id] = roles
    source_ids = deterministic_permutation(pair_ids, seed=seed)
    result: list[PairExample] = []
    for destination, source in zip(pair_ids, source_ids, strict=True):
        for role in ("a_to_b", "b_to_a"):
            example = by_pair_role[destination][role]
            category = by_pair_role[source][role].features
            features = replace(
                example.features,
                class_id=category.class_id,
                exact_transformation_id=category.exact_transformation_id,
                environment_level_1_id=category.environment_level_1_id,
                environment_level_2_id=category.environment_level_2_id,
            )
            result.append(replace(example, features=features))
    return tuple(result)


def diagnose_pair_antisymmetry(
    examples: Sequence[PairExample], *, tolerance: float = 1e-12
) -> PairAntisymmetryDiagnostics:
    """Check directional reversals and signed target cancellation."""

    if tolerance < 0.0 or not math.isfinite(tolerance):
        raise OracleModelError("antisymmetry tolerance must be nonnegative")
    groups: dict[str, list[PairExample]] = defaultdict(list)
    for example in examples:
        groups[example.pair_id].append(example)
    complete = 0
    missing = 0
    violating = 0
    maximum = 0.0
    for rows in groups.values():
        if len(rows) != 2:
            missing += 1
            continue
        first, second = rows
        complete += 1
        reverse = (
            first.anchor_molecule_id == second.analog_molecule_id
            and first.analog_molecule_id == second.anchor_molecule_id
        )
        difference = abs(first.target + second.target)
        maximum = max(maximum, difference)
        if not reverse or difference > tolerance:
            violating += 1
    return PairAntisymmetryDiagnostics(
        len(groups), complete, missing, violating, maximum
    )


def diagnose_predicted_delta_antisymmetry(
    predictions: Sequence[PredictedDelta], *, tolerance: float = 1e-12
) -> PairAntisymmetryDiagnostics:
    """Check the required pre-anchor model delta reversal diagnostic."""

    if tolerance < 0.0 or not math.isfinite(tolerance):
        raise OracleModelError("antisymmetry tolerance must be nonnegative")
    groups: dict[str, list[PredictedDelta]] = defaultdict(list)
    for prediction in predictions:
        _finite(prediction.delta, "predicted delta")
        if prediction.direction_role not in {"a_to_b", "b_to_a"}:
            raise OracleModelError("predicted delta has an invalid direction role")
        groups[prediction.pair_id].append(prediction)
    complete = 0
    missing = 0
    violating = 0
    maximum = 0.0
    for rows in groups.values():
        roles = {row.direction_role: row for row in rows}
        if len(rows) != 2 or set(roles) != {"a_to_b", "b_to_a"}:
            missing += 1
            continue
        complete += 1
        difference = abs(roles["a_to_b"].delta + roles["b_to_a"].delta)
        maximum = max(maximum, difference)
        if difference > tolerance:
            violating += 1
    return PairAntisymmetryDiagnostics(
        len(groups), complete, missing, violating, maximum
    )


__all__ = [
    "ALPHA_VALUES",
    "BASE_SEED",
    "HierarchyFit",
    "HierarchyObservation",
    "LAMBDA_VALUES",
    "OTHER_CLASS",
    "OracleModelError",
    "PairAntisymmetryDiagnostics",
    "PairExample",
    "PairFeatures",
    "Prediction",
    "PredictedDelta",
    "RidgeFit",
    "RobustScaler",
    "TraceModel",
    "deterministic_permutation",
    "diagnose_pair_antisymmetry",
    "diagnose_predicted_delta_antisymmetry",
    "fit_a0",
    "fit_a1",
    "fit_a2",
    "fit_c2",
    "fit_c3",
    "fit_f2",
    "fit_hierarchy",
    "fit_t0",
    "fit_weighted_ridge",
    "generic_feature_vector",
    "pair_feature_vector",
    "permute_category_contexts",
    "predict_local",
    "scoped_seed",
    "signed_morgan_difference",
]
