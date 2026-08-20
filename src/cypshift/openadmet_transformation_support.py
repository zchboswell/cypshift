"""Pure, label-safe support arithmetic for the frozen R4 geometry.

This module consumes only the accepted projection bundle and structural geometry.
It never reads activity magnitudes, selector facts, test chemistry, or labels.
All support counts are structural and family-deduplicated; endpoint availability
is used only internally to form aggregate complete-state partitions.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final

from cypshift.openadmet_transformation_compiler import (
    CompiledEpisodeDirection,
    CompiledTransformationPair,
    TransformationGeometry,
)
from cypshift.openadmet_transformation_coverage import (
    OpenADMETTransformationCoverageError,
    ProjectionBundle,
    ProjectionFold,
)
from cypshift.openadmet_transformation_io import ENDPOINTS
from cypshift.openadmet_transformation_types import DirectionalTransformation

STATUS_VALUES: Final[tuple[str, ...]] = (
    "VALID_STEREO",
    "VALID_SINGLE",
    "VALID_DOUBLE",
    "AMBIGUOUS",
    "UNSUPPORTED",
    "STANDARDIZATION_HAZARD",
)
VALID_STATUSES: Final[frozenset[str]] = frozenset(STATUS_VALUES[:3])
FOLD_COUNT: Final[int] = 15
LOCAL_FAMILY_MIN: Final[int] = 5
LOCAL_PAIR_MIN: Final[int] = 20
LOCAL_FAMILY_OVERALL_MIN: Final[int] = 50
LOCAL_PAIR_OVERALL_MIN: Final[int] = 200
SELECTED_FAMILY_MIN: Final[int] = 5
SELECTED_FAMILY_OVERALL_MIN: Final[int] = 50


@dataclass(frozen=True, slots=True)
class StatusPartition:
    """Exhaustive structural-row status counts and exact fractions."""

    denominator_rows: int
    counts: tuple[tuple[str, int], ...]
    fractions: tuple[tuple[str, str], ...]

    def count(self, status: str) -> int:
        return dict(self.counts)[status]


@dataclass(frozen=True, slots=True)
class LocalSupportCell:
    """One repeat/outer-validation-fold endpoint support cell."""

    endpoint: str
    repeat: int
    outer_validation_fold: int
    pairs: int
    families: int
    meets_gate: bool


@dataclass(frozen=True, slots=True)
class SelectedSupportCell:
    """One repeat/fold selected-anchor structural coverage cell."""

    repeat: int
    outer_fold: int
    rows: int
    valid_rows: int
    distinct_families: int
    meets_gate: bool


@dataclass(frozen=True, slots=True)
class EndpointLocalSupport:
    """Aggregate and 15-cell complete-state local support for one endpoint."""

    endpoint: str
    pairs: int
    families: int
    cells: tuple[LocalSupportCell, ...]


@dataclass(frozen=True, slots=True)
class FrequencyRecord:
    """Frequency of a reusable directional ID in the union valid views."""

    rows: int
    denominator_rows: int


@dataclass(frozen=True, slots=True)
class IndependentGroupSupport:
    """Full-population component counts for reusable exact and class IDs."""

    exact: tuple[tuple[str, int], ...]
    transformation_class: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class RationalDistribution:
    """Exact changed-heavy-atom-fraction distribution."""

    count: int
    unique_rationals: int
    minimum: str | None
    median: str | None
    maximum: str | None
    histogram: tuple[tuple[str, int], ...]

    @property
    def min(self) -> str | None:
        return self.minimum

    @property
    def max(self) -> str | None:
        return self.maximum


@dataclass(frozen=True, slots=True)
class EpisodeTrainingSupport:
    """Family support for one episode direction after held-out exclusion."""

    episode_id: str
    query_rank: int
    exact: int
    transformation_class: int


@dataclass(frozen=True, slots=True)
class SelectedAnchorCoverage:
    """Endpoint-agnostic selected-anchor structural coverage gate."""

    status: str
    rows: int
    valid_rows: int
    distinct_families_overall: int
    cell_support: tuple[SelectedSupportCell, ...]
    meets_gate: bool


@dataclass(frozen=True, slots=True)
class LocalCYP3A4State:
    """State-only CYP3A4 local support gate."""

    status: str
    overall_families: int
    overall_pairs: int
    fold_cells: tuple[LocalSupportCell, ...]
    meets_gate: bool


@dataclass(frozen=True, slots=True)
class TransformationSupport:
    """All deterministic R4 arithmetic before episode/publication serialization."""

    status: str
    status_partition_union: StatusPartition
    status_partition_local_by_endpoint: tuple[tuple[str, StatusPartition], ...]
    status_partition_selected_primary: StatusPartition
    status_partition_stress: StatusPartition
    endpoint_local_support: tuple[EndpointLocalSupport, ...]
    exact_transformation_frequency: tuple[tuple[str, FrequencyRecord], ...]
    transformation_class_frequency: tuple[tuple[str, FrequencyRecord], ...]
    independent_group_support: IndependentGroupSupport
    valid_changed_heavy_atom_fraction_distribution: RationalDistribution
    cross_cyp_valid_transformation_sharing: tuple[tuple[str, tuple[str, ...]], ...]
    selected_anchor_structural_coverage: SelectedAnchorCoverage
    local_cyp3a4_state: LocalCYP3A4State
    episode_training_support: tuple[EpisodeTrainingSupport, ...]

    @property
    def status_partition(self) -> dict[str, object]:
        """Expose the contract partition names without serializing artifacts."""

        return {
            "union": self.status_partition_union,
            "local_by_endpoint": dict(self.status_partition_local_by_endpoint),
            "selected_primary": self.status_partition_selected_primary,
            "stress": self.status_partition_stress,
        }


def compile_transformation_support(
    bundle: ProjectionBundle, geometry: TransformationGeometry
) -> TransformationSupport:
    """Compute every R4 support summary over the accepted synthetic geometry."""

    pairs = _unique_pairs(geometry.pairs)
    episodes = _unique_episodes(geometry.episodes)
    expected_episodes = tuple(
        sorted(bundle.episodes, key=lambda row: (row.episode_id, row.query_rank))
    )
    if tuple(item.episode for item in episodes) != expected_episodes:
        raise OpenADMETTransformationCoverageError(
            "episode geometry differs from projection"
        )
    if any(
        item.episode.outer_group_id != item.pair.similarity_component_hash
        for item in episodes
    ):
        raise OpenADMETTransformationCoverageError("episode component differs")
    complete = _complete_molecules(bundle)
    fold_by_key, component_outer = _fold_maps(bundle.folds)

    union = _partition(pairs)
    local_by_endpoint = tuple(
        (
            endpoint,
            _partition(
                item
                for item in pairs
                if item.local_pair
                and _pair_molecules_complete(item, complete[endpoint])
            ),
        )
        for endpoint in ENDPOINTS
    )
    selected_rows = tuple(
        item for item in episodes if item.episode.episode_policy_id == "selected_anchor"
    )
    stress_rows = tuple(
        item
        for item in episodes
        if item.episode.episode_policy_id == "deterministic_random_anchor_stress"
    )
    selected_partition = _episode_partition(selected_rows)
    stress_partition = _episode_partition(stress_rows)
    endpoint_support = tuple(
        _local_support(endpoint, pairs, complete[endpoint], fold_by_key)
        for endpoint in ENDPOINTS
    )
    frequencies = _frequencies(pairs)
    independent = _independent_support(pairs, complete)
    distribution = _changed_fraction_distribution(pairs)
    if distribution.count != sum(
        union.count(status) for status in sorted(VALID_STATUSES)
    ):
        raise OpenADMETTransformationCoverageError(
            "changed-fraction distribution count differs from valid union rows"
        )
    sharing = _cross_cyp_sharing(pairs, complete)
    selected_coverage = _selected_coverage(selected_rows)
    cyp3a4 = next(item for item in endpoint_support if item.endpoint == "CYP3A4")
    local_state = _local_cyp3a4_state(cyp3a4)
    episode_support = _episode_training_support(
        episodes, pairs, complete["CYP3A4"], component_outer
    )
    return TransformationSupport(
        status=(
            "R4_TRANSFORMATION_COVERAGE_SUPPORTED"
            if local_state.meets_gate and selected_coverage.meets_gate
            else "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED"
        ),
        status_partition_union=union,
        status_partition_local_by_endpoint=local_by_endpoint,
        status_partition_selected_primary=selected_partition,
        status_partition_stress=stress_partition,
        endpoint_local_support=endpoint_support,
        exact_transformation_frequency=frequencies[0],
        transformation_class_frequency=frequencies[1],
        independent_group_support=independent,
        valid_changed_heavy_atom_fraction_distribution=distribution,
        cross_cyp_valid_transformation_sharing=sharing,
        selected_anchor_structural_coverage=selected_coverage,
        local_cyp3a4_state=local_state,
        episode_training_support=episode_support,
    )


def _unique_pairs(
    values: Iterable[CompiledTransformationPair],
) -> tuple[CompiledTransformationPair, ...]:
    by_identity: dict[tuple[str, str], CompiledTransformationPair] = {}
    for item in values:
        result = item.result
        key = _pair_identity(item)
        prior = by_identity.get(key)
        if prior is None:
            by_identity[key] = item
            continue
        if (
            prior.result != result
            or prior.similarity_component_hash != item.similarity_component_hash
        ):
            raise OpenADMETTransformationCoverageError(
                "conflicting duplicate structural pair"
            )
        by_identity[key] = replace(
            prior,
            local_pair=prior.local_pair or item.local_pair,
            episode_pair=prior.episode_pair or item.episode_pair,
        )
    return tuple(
        sorted(
            by_identity.values(), key=lambda item: item.result.transformation_pair_id
        )
    )


def _unique_episodes(
    values: Iterable[CompiledEpisodeDirection],
) -> tuple[CompiledEpisodeDirection, ...]:
    by_key: dict[tuple[str, int], CompiledEpisodeDirection] = {}
    for item in values:
        key = (item.episode.episode_id, item.episode.query_rank)
        prior = by_key.get(key)
        if prior is not None and prior != item:
            raise OpenADMETTransformationCoverageError("conflicting duplicate episode")
        by_key[key] = item
    return tuple(
        sorted(
            by_key.values(),
            key=lambda item: (item.episode.episode_id, item.episode.query_rank),
        )
    )


def _complete_molecules(bundle: ProjectionBundle) -> dict[str, frozenset[str]]:
    complete: dict[str, set[str]] = {endpoint: set() for endpoint in ENDPOINTS}
    for row in bundle.direct_availability:
        if row.endpoint not in complete:
            raise OpenADMETTransformationCoverageError("unknown direct endpoint")
        if row.value_state == "complete":
            complete[row.endpoint].add(row.molecule_id)
    return {endpoint: frozenset(ids) for endpoint, ids in complete.items()}


def _fold_maps(
    folds: Iterable[ProjectionFold],
) -> tuple[
    dict[tuple[str, int, int], ProjectionFold],
    dict[tuple[str, int], int],
]:
    by_key: dict[tuple[str, int, int], ProjectionFold] = {}
    component_outer: dict[tuple[str, int], int] = {}
    for row in folds:
        key = (row.molecule_id, row.repeat, row.outer_validation_fold)
        prior = by_key.get(key)
        if prior is not None and prior != row:
            raise OpenADMETTransformationCoverageError("conflicting duplicate fold")
        by_key[key] = row
        component_key = (row.similarity_component_hash, row.repeat)
        prior_outer = component_outer.get(component_key)
        if prior_outer is not None and prior_outer != row.outer_fold:
            raise OpenADMETTransformationCoverageError("component fold differs")
        component_outer[component_key] = row.outer_fold
    return by_key, component_outer


def _pair_molecules_complete(
    item: CompiledTransformationPair, complete: frozenset[str]
) -> bool:
    return (
        item.result.left_molecule_id in complete
        and item.result.right_molecule_id in complete
    )


def _partition(values: Iterable[CompiledTransformationPair]) -> StatusPartition:
    rows = tuple(values)
    counts = {status: 0 for status in STATUS_VALUES}
    for item in rows:
        status = item.result.extraction_status
        if status not in counts:
            raise OpenADMETTransformationCoverageError("unknown extraction status")
        counts[status] += 1
    return _status_partition(len(rows), counts)


def _episode_partition(values: Iterable[CompiledEpisodeDirection]) -> StatusPartition:
    rows = tuple(values)
    counts = {status: 0 for status in STATUS_VALUES}
    for item in rows:
        status = item.direction.extraction_status
        if status not in counts:
            raise OpenADMETTransformationCoverageError("unknown episode status")
        counts[status] += 1
    return _status_partition(len(rows), counts)


def _status_partition(rows: int, counts: Mapping[str, int]) -> StatusPartition:
    count_values = tuple((status, counts[status]) for status in STATUS_VALUES)
    fractions = tuple(
        (
            status,
            "0/1" if rows == 0 else _fraction_text(Fraction(counts[status], rows)),
        )
        for status in STATUS_VALUES
    )
    return StatusPartition(rows, count_values, fractions)


def _local_support(
    endpoint: str,
    pairs: tuple[CompiledTransformationPair, ...],
    complete: frozenset[str],
    folds: Mapping[tuple[str, int, int], ProjectionFold],
) -> EndpointLocalSupport:
    local = tuple(
        item
        for item in pairs
        if item.local_pair
        and item.result.extraction_status in VALID_STATUSES
        and _pair_molecules_complete(item, complete)
    )
    overall_pairs = {_pair_identity(item) for item in local}
    overall_families = {item.similarity_component_hash for item in local}
    cells: list[LocalSupportCell] = []
    for repeat in range(3):
        for validation in range(5):
            held_out = {
                molecule_id
                for (molecule_id, row_repeat, row_validation), row in folds.items()
                if row_repeat == repeat
                and row_validation == validation
                and row.outer_fold == validation
            }
            cell = tuple(
                item
                for item in local
                if item.result.left_molecule_id in held_out
                and item.result.right_molecule_id in held_out
            )
            pair_ids = {_pair_identity(item) for item in cell}
            families = {item.similarity_component_hash for item in cell}
            cells.append(
                LocalSupportCell(
                    endpoint,
                    repeat,
                    validation,
                    len(pair_ids),
                    len(families),
                    len(pair_ids) >= LOCAL_PAIR_MIN
                    and len(families) >= LOCAL_FAMILY_MIN,
                )
            )
    if len(cells) != FOLD_COUNT:
        raise OpenADMETTransformationCoverageError("local fold cell count differs")
    return EndpointLocalSupport(
        endpoint, len(overall_pairs), len(overall_families), tuple(cells)
    )


def _frequencies(
    pairs: tuple[CompiledTransformationPair, ...],
) -> tuple[
    tuple[tuple[str, FrequencyRecord], ...],
    tuple[tuple[str, FrequencyRecord], ...],
]:
    valid = tuple(
        item for item in pairs if item.result.extraction_status in VALID_STATUSES
    )
    denominator = 2 * len(valid)
    exact: defaultdict[str, int] = defaultdict(int)
    classes: defaultdict[str, int] = defaultdict(int)
    for item in valid:
        for direction in (item.result.a_to_b, item.result.b_to_a):
            exact[direction.exact_transformation_id] += 1
            classes[_class_token(direction)] += 1
    return (
        tuple((key, FrequencyRecord(exact[key], denominator)) for key in sorted(exact)),
        tuple(
            (key, FrequencyRecord(classes[key], denominator)) for key in sorted(classes)
        ),
    )


def _independent_support(
    pairs: tuple[CompiledTransformationPair, ...],
    complete: Mapping[str, frozenset[str]],
) -> IndependentGroupSupport:
    exact: defaultdict[str, set[str]] = defaultdict(set)
    classes: defaultdict[str, set[str]] = defaultdict(set)
    for item in pairs:
        if not item.local_pair or item.result.extraction_status not in VALID_STATUSES:
            continue
        if not any(
            _pair_molecules_complete(item, values) for values in complete.values()
        ):
            continue
        for direction in (item.result.a_to_b, item.result.b_to_a):
            exact[direction.exact_transformation_id].add(item.similarity_component_hash)
            classes[_class_token(direction)].add(item.similarity_component_hash)
    return IndependentGroupSupport(
        tuple((key, len(exact[key])) for key in sorted(exact)),
        tuple((key, len(classes[key])) for key in sorted(classes)),
    )


def _parse_fraction(value: str) -> Fraction:
    parts = value.split("/")
    if len(parts) != 2 or any(
        not part.isdigit() or (part != "0" and part.startswith("0")) for part in parts
    ):
        raise OpenADMETTransformationCoverageError("invalid changed fraction")
    try:
        numerator, denominator = (int(part) for part in parts)
        parsed = Fraction(numerator, denominator)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise OpenADMETTransformationCoverageError("invalid changed fraction") from exc
    if numerator < 0 or denominator <= 0 or parsed.denominator != denominator:
        raise OpenADMETTransformationCoverageError("changed fraction is not reduced")
    return parsed


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _changed_fraction_distribution(
    pairs: tuple[CompiledTransformationPair, ...],
) -> RationalDistribution:
    values = [
        _parse_fraction(item.result.changed_heavy_atom_fraction)
        for item in pairs
        if item.result.extraction_status in VALID_STATUSES
    ]
    if not values:
        return RationalDistribution(0, 0, None, None, None, ())
    ordered = sorted(values)
    histogram: defaultdict[str, int] = defaultdict(int)
    for value in values:
        histogram[_fraction_text(value)] += 1
    middle = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / 2
    lexical_histogram = tuple((key, histogram[key]) for key in sorted(histogram))
    return RationalDistribution(
        len(values),
        len(histogram),
        _fraction_text(ordered[0]),
        _fraction_text(median),
        _fraction_text(ordered[-1]),
        lexical_histogram,
    )


def _cross_cyp_sharing(
    pairs: tuple[CompiledTransformationPair, ...],
    complete: Mapping[str, frozenset[str]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    endpoints_by_id: defaultdict[str, set[str]] = defaultdict(set)
    for endpoint in ENDPOINTS:
        for item in pairs:
            if (
                item.local_pair
                and item.result.extraction_status in VALID_STATUSES
                and _pair_molecules_complete(item, complete[endpoint])
            ):
                for direction in (item.result.a_to_b, item.result.b_to_a):
                    endpoints_by_id[direction.exact_transformation_id].add(endpoint)
    return tuple(
        (key, tuple(sorted(endpoints_by_id[key])))
        for key in sorted(endpoints_by_id)
        if len(endpoints_by_id[key]) >= 2
    )


def _selected_coverage(
    rows: tuple[CompiledEpisodeDirection, ...],
) -> SelectedAnchorCoverage:
    valid = tuple(
        item for item in rows if item.direction.extraction_status in VALID_STATUSES
    )
    overall = {item.episode.outer_group_id for item in valid}
    cells: list[SelectedSupportCell] = []
    for repeat in range(3):
        for outer in range(5):
            all_rows = tuple(
                item
                for item in rows
                if item.episode.repeat == repeat and item.episode.outer_fold == outer
            )
            cell = tuple(
                item
                for item in all_rows
                if item.direction.extraction_status in VALID_STATUSES
            )
            families = {item.episode.outer_group_id for item in cell}
            cells.append(
                SelectedSupportCell(
                    repeat,
                    outer,
                    len(all_rows),
                    len(cell),
                    len(families),
                    len(families) >= SELECTED_FAMILY_MIN,
                )
            )
    meets = len(overall) >= SELECTED_FAMILY_OVERALL_MIN and all(
        cell.meets_gate for cell in cells
    )
    return SelectedAnchorCoverage(
        "SUPPORTED" if meets else "UNDERPOWERED",
        len(rows),
        len(valid),
        len(overall),
        tuple(cells),
        meets,
    )


def _local_cyp3a4_state(support: EndpointLocalSupport) -> LocalCYP3A4State:
    meets = (
        support.families >= LOCAL_FAMILY_OVERALL_MIN
        and support.pairs >= LOCAL_PAIR_OVERALL_MIN
        and all(cell.meets_gate for cell in support.cells)
    )
    return LocalCYP3A4State(
        "LOCAL_SUPPORTED" if meets else "LOCAL_UNDERPOWERED",
        support.families,
        support.pairs,
        support.cells,
        meets,
    )


def _episode_training_support(
    episodes: tuple[CompiledEpisodeDirection, ...],
    pairs: tuple[CompiledTransformationPair, ...],
    complete: frozenset[str],
    component_outer: Mapping[tuple[str, int], int],
) -> tuple[EpisodeTrainingSupport, ...]:
    candidates = tuple(
        item
        for item in pairs
        if item.local_pair
        and item.result.extraction_status in VALID_STATUSES
        and _pair_molecules_complete(item, complete)
    )
    output: list[EpisodeTrainingSupport] = []
    for episode in episodes:
        target = episode.direction
        exact_components: set[str] = set()
        class_components: set[str] = set()
        for item in candidates:
            component = item.similarity_component_hash
            if component == episode.episode.outer_group_id:
                continue
            outer = component_outer.get((component, episode.episode.repeat))
            if outer is None or outer == episode.episode.outer_fold:
                continue
            directions = (item.result.a_to_b, item.result.b_to_a)
            if any(
                direction.extraction_status in VALID_STATUSES
                and direction.exact_transformation_id == target.exact_transformation_id
                for direction in directions
            ):
                exact_components.add(component)
            if any(
                direction.extraction_status in VALID_STATUSES
                and direction.transformation_class_id == target.transformation_class_id
                for direction in directions
            ):
                class_components.add(component)
        output.append(
            EpisodeTrainingSupport(
                episode.episode.episode_id,
                episode.episode.query_rank,
                len(exact_components),
                len(class_components),
            )
        )
    return tuple(output)


def _pair_identity(item: CompiledTransformationPair) -> tuple[str, str]:
    left = item.result.left_standardized_structure_hash
    right = item.result.right_standardized_structure_hash
    return (left, right) if left <= right else (right, left)


def _class_token(direction: DirectionalTransformation) -> str:
    material = direction.candidate_material
    if not isinstance(material, dict) or "class" not in material:
        raise OpenADMETTransformationCoverageError("missing transformation class token")
    value = material["class"]
    if not isinstance(value, str) or not value:
        raise OpenADMETTransformationCoverageError("invalid transformation class token")
    return value


__all__ = [
    "EndpointLocalSupport",
    "EpisodeTrainingSupport",
    "FrequencyRecord",
    "IndependentGroupSupport",
    "LocalCYP3A4State",
    "LocalSupportCell",
    "RationalDistribution",
    "SelectedAnchorCoverage",
    "SelectedSupportCell",
    "STATUS_VALUES",
    "StatusPartition",
    "TransformationSupport",
    "VALID_STATUSES",
    "compile_transformation_support",
]
