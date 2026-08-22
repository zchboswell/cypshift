"""Pure deterministic anchor controls for the frozen R5 TRACE experiment."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import cast

from cypshift.openadmet_oracle_models import (
    PairFeatures,
    Prediction,
    TraceModel,
    deterministic_permutation,
    predict_local,
    scoped_seed,
    signed_morgan_difference,
)
from cypshift.openadmet_transformation_types import TransformationPairResult
from cypshift.schema import MoleculeRecord

VALID_CONTROL_STATUSES = frozenset({"VALID_SINGLE", "VALID_DOUBLE"})


class OracleControlError(ValueError):
    """A control-pool or transformation invariant failed."""


@dataclass(frozen=True, slots=True)
class ControlMolecule:
    """One complete current-training anchor candidate."""

    molecule: MoleculeRecord
    component_id: str
    point: float
    morgan_bits: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ControlQuery:
    """One held-out query needing an external control anchor."""

    episode_id: str
    molecule: MoleculeRecord
    component_id: str
    morgan_bits: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LocalControlAnchor:
    """A valid on-demand anchor-to-query transformation."""

    anchor: ControlMolecule
    similarity: float
    pair_features: PairFeatures


Extractor = Callable[[MoleculeRecord, MoleculeRecord], TransformationPairResult]


def _bits(values: Sequence[int], label: str) -> tuple[int, ...]:
    result = tuple(values)
    if not result or any(value not in (0, 1) for value in result):
        raise OracleControlError(f"{label} must be a non-empty binary vector")
    return result


def morgan_tanimoto(left: Sequence[int], right: Sequence[int]) -> float:
    """Compute exact binary Tanimoto for frozen Morgan columns."""

    left_bits, right_bits = _bits(left, "left Morgan"), _bits(right, "right Morgan")
    if len(left_bits) != len(right_bits):
        raise OracleControlError("Morgan widths differ")
    intersection = sum(a & b for a, b in zip(left_bits, right_bits, strict=True))
    union = sum(a | b for a, b in zip(left_bits, right_bits, strict=True))
    return 1.0 if union == 0 else intersection / union


def _validate_candidate(candidate: ControlMolecule, query: ControlQuery) -> None:
    if not candidate.molecule.molecule_id or not candidate.component_id:
        raise OracleControlError("control anchor identity is empty")
    if not math.isfinite(candidate.point):
        raise OracleControlError("control anchor point is non-finite")
    if candidate.component_id == query.component_id:
        raise OracleControlError("held-out query family entered control pool")
    if candidate.molecule.molecule_id == query.molecule.molecule_id:
        raise OracleControlError("query identity entered control pool")
    if len(_bits(candidate.morgan_bits, "anchor Morgan")) != len(
        _bits(query.morgan_bits, "query Morgan")
    ):
        raise OracleControlError("Morgan widths differ")


def nearest_training_anchor(
    query: ControlQuery, candidates: Sequence[ControlMolecule]
) -> ControlMolecule | None:
    """Return C1's most Morgan-similar complete current-training molecule."""

    ranked: list[tuple[float, str, ControlMolecule]] = []
    for candidate in candidates:
        _validate_candidate(candidate, query)
        ranked.append(
            (
                morgan_tanimoto(candidate.morgan_bits, query.morgan_bits),
                candidate.molecule.molecule_id,
                candidate,
            )
        )
    if not ranked:
        return None
    return min(ranked, key=lambda item: (-item[0], item[1]))[2]


def _direction_features(
    result: TransformationPairResult,
    anchor: ControlMolecule,
    query: ControlQuery,
) -> PairFeatures:
    directions = (result.a_to_b, result.b_to_a)
    matches = tuple(
        direction
        for direction in directions
        if direction.anchor_molecule_id == anchor.molecule.molecule_id
        and direction.analog_molecule_id == query.molecule.molecule_id
    )
    if len(matches) != 1:
        raise OracleControlError("on-demand anchor direction differs")
    direction = matches[0]
    if direction.extraction_status not in VALID_CONTROL_STATUSES:
        raise OracleControlError("on-demand direction is not valid")
    if direction.cut_count is None or not direction.transformation_class_id:
        raise OracleControlError("valid direction metadata is incomplete")
    try:
        changed_fraction = float(Fraction(direction.changed_heavy_atom_fraction))
    except (ValueError, ZeroDivisionError) as exc:
        raise OracleControlError("changed fraction differs") from exc
    return PairFeatures(
        signed_morgan_difference(anchor.morgan_bits, query.morgan_bits),
        direction.cut_count,
        changed_fraction,
        direction.transformation_class_id,
        direction.exact_transformation_id,
        direction.environment_level_1_id,
        direction.environment_level_2_id,
    )


def valid_on_demand_anchors(
    query: ControlQuery,
    candidates: Sequence[ControlMolecule],
    *,
    extractor: Extractor,
    limit: int = 64,
) -> tuple[LocalControlAnchor, ...]:
    """Extract valid transformations from the exact top-64 Morgan candidates."""

    if limit != 64:
        raise OracleControlError("on-demand candidate limit must remain 64")
    ranked: list[tuple[float, str, ControlMolecule]] = []
    seen: set[str] = set()
    for candidate in candidates:
        _validate_candidate(candidate, query)
        molecule_id = candidate.molecule.molecule_id
        if molecule_id in seen:
            raise OracleControlError("duplicate control anchor identity")
        seen.add(molecule_id)
        ranked.append(
            (
                morgan_tanimoto(candidate.morgan_bits, query.morgan_bits),
                molecule_id,
                candidate,
            )
        )
    selected = sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit]
    valid: list[LocalControlAnchor] = []
    for similarity, _molecule_id, candidate in selected:
        result = extractor(candidate.molecule, query.molecule)
        if result.extraction_status not in VALID_CONTROL_STATUSES:
            continue
        valid.append(
            LocalControlAnchor(
                candidate,
                similarity,
                _direction_features(result, candidate, query),
            )
        )
    return tuple(valid)


def select_f0_anchor(
    valid: Sequence[LocalControlAnchor],
    *,
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    query_id: str,
) -> LocalControlAnchor | None:
    """Choose F0's deterministic shuffled anchor identity/value tuple."""

    if not valid:
        return None
    ordered = tuple(sorted(valid, key=lambda item: item.anchor.molecule.molecule_id))
    seed = scoped_seed(20260820, "F0", repeat, outer_fold, inner_fold, query_id)
    return cast(LocalControlAnchor, deterministic_permutation(ordered, seed=seed)[0])


def select_f1_anchor(
    valid: Sequence[LocalControlAnchor],
) -> LocalControlAnchor | None:
    """Choose F1's nearest valid transformed anchor."""

    if not valid:
        return None
    return min(
        valid,
        key=lambda item: (-item.similarity, item.anchor.molecule.molecule_id),
    )


def copy_anchor_prediction(anchor_point: float, *, system_id: str = "C0") -> Prediction:
    """Return the measured-anchor copy control."""

    if not math.isfinite(anchor_point):
        raise OracleControlError("anchor point is non-finite")
    return Prediction(float(anchor_point), True, system_id, None)


def external_anchor_prediction(
    anchor: ControlMolecule | None,
    *,
    g0_prediction: float,
) -> Prediction:
    """Return C1 or its explicit G0 fallback."""

    if anchor is None:
        if not math.isfinite(g0_prediction):
            raise OracleControlError("G0 prediction is non-finite")
        return Prediction(float(g0_prediction), False, "G0", "empty_neighbor_pool")
    return copy_anchor_prediction(anchor.point, system_id="C1")


def wrong_anchor_prediction(
    model: TraceModel,
    anchor: LocalControlAnchor | None,
    *,
    g0_prediction: float,
    system_id: str,
) -> Prediction:
    """Apply frozen T0 to F0/F1's selected external anchor or fall back to G0."""

    if system_id not in {"F0", "F1"}:
        raise OracleControlError("wrong-anchor system must be F0 or F1")
    if model.system_id != "T0":
        raise OracleControlError("wrong-anchor controls must reuse frozen T0")
    if anchor is None:
        if not math.isfinite(g0_prediction):
            raise OracleControlError("G0 prediction is non-finite")
        return Prediction(float(g0_prediction), False, "G0", "no_valid_control_anchor")
    prediction = predict_local(
        model,
        anchor.pair_features,
        anchor_context=anchor.anchor.point,
        g0_prediction=g0_prediction,
    )
    return Prediction(
        prediction.value,
        prediction.local_available,
        system_id if prediction.local_available else prediction.prediction_source,
        prediction.fallback_reason,
        prediction.hierarchy_level,
        prediction.hierarchy_support_components,
    )


__all__ = [
    "ControlMolecule",
    "ControlQuery",
    "LocalControlAnchor",
    "OracleControlError",
    "copy_anchor_prediction",
    "external_anchor_prediction",
    "morgan_tanimoto",
    "nearest_training_anchor",
    "select_f0_anchor",
    "select_f1_anchor",
    "valid_on_demand_anchors",
    "wrong_anchor_prediction",
]
