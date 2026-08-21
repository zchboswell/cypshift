"""One isolated, receipt-authenticated R5C pair-model cell.

The cell is deliberately small: capability loading remains in
``openadmet_oracle_cell_io``; this module turns an already authenticated
capability into one private prediction fragment.  It never opens a scorer,
rebuilds a fold, or sees a challenge file.  The same functions are used by the
synthetic runner and by focused scientific tests.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Any, Final, Literal

from cypshift.chemistry import audit_molecules
from cypshift.openadmet_oracle_cell_validation import (
    OracleC3TargetCapability,
    OracleCellCapability,
    OracleCellTargetCapability,
    OracleModelPublicCapability,
)
from cypshift.openadmet_oracle_controls import (
    ControlMolecule,
    ControlQuery,
    LocalControlAnchor,
    external_anchor_prediction,
    nearest_training_anchor,
    select_f0_anchor,
    select_f1_anchor,
    valid_on_demand_anchors,
    wrong_anchor_prediction,
)
from cypshift.openadmet_oracle_models import (
    ALPHA_VALUES,
    BASE_SEED,
    LAMBDA_VALUES,
    PairExample,
    PairFeatures,
    Prediction,
    TraceModel,
    fit_a0,
    fit_a1,
    fit_a2,
    fit_c2,
    fit_c3,
    fit_f2,
    fit_t0,
    predict_local,
    scoped_seed,
    signed_morgan_difference,
)
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput, MoleculeRecord

SYSTEMS: Final = frozenset(
    {"C0", "C1", "C2", "C3", "T0", "F0", "F1", "F2", "A0", "A1", "A2"}
)
VALID_STATUSES: Final = frozenset({"VALID_SINGLE", "VALID_DOUBLE"})
FRAGMENT_COLUMNS: Final = (
    "episode_id",
    "query_molecule_id",
    "query_rank",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "inner_fold",
    "component_id",
    "system_id",
    "candidate_id",
    "prediction",
    "local_available",
    "prediction_source",
    "extraction_status",
    "similarity",
    "exact_support_components",
    "class_support_components",
)
CONTRACT_ID: Final = "R5-CYP3A4-ORACLE-V1"
G0_SYSTEM_ID: Final = "G0"


class OraclePairCellError(ValueError):
    """An isolated pair cell cannot satisfy its frozen contract."""


@dataclass(frozen=True, slots=True)
class G0Prediction:
    """One authenticated G0 fallback value for one public query row."""

    episode_id: str
    query_molecule_id: str
    query_rank: int
    prediction: float


@dataclass(frozen=True, slots=True)
class PairCellResult:
    """Private fragment bytes and operation counters from one cell."""

    fragment: bytes
    rows: tuple[Mapping[str, str], ...]
    accounting: Mapping[str, int]
    candidate_id: str
    fragment_id: str
    model: TraceModel | None = None


@dataclass(frozen=True, slots=True)
class _EpisodeQuery:
    row: Mapping[str, str]
    pair: PairFeatures | None
    similarity: str
    extraction_status: str
    exact_support: str
    class_support: str
    g0: float
    anchor_point: float | None
    global_anchor: float | None
    inner_fold: int | None


def candidate_id(
    system_id: str,
    alpha: float | None,
    lambda_: float | None,
    *,
    selection_token_sha256: str | None = None,
    upstream_candidate_receipt_sha256: str | None = None,
) -> str:
    """Return the frozen candidate identity (without fold or score material)."""

    if system_id not in SYSTEMS | {"G0"}:
        raise OraclePairCellError("candidate system differs")
    if system_id == "F2" and selection_token_sha256:
        material = [
            CONTRACT_ID,
            "F2",
            alpha,
            lambda_,
            selection_token_sha256,
        ]
    elif (
        system_id in {"F0", "F1"}
        and selection_token_sha256
        and upstream_candidate_receipt_sha256
    ):
        material = [
            CONTRACT_ID,
            system_id,
            None,
            None,
            selection_token_sha256,
            upstream_candidate_receipt_sha256,
        ]
    else:
        material = [CONTRACT_ID, system_id, alpha, lambda_]
    return sha256(_compact_json(material)).hexdigest()


def cell_id(
    stage: Literal["inner", "outer"],
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    system_id: str,
    candidate: str,
    episode_id: str,
    *,
    alpha: float | None = None,
    lambda_: float | None = None,
    selection_token_sha256: str | None = None,
    upstream_candidate_receipt_sha256: str | None = None,
) -> str:
    """Build the exact scoped identity used by private fragments."""

    if stage not in {"inner", "outer"} or repeat not in range(3):
        raise OraclePairCellError("cell scope differs")
    if outer_fold not in range(5) or (stage == "outer") != (inner_fold is None):
        raise OraclePairCellError("cell scope differs")
    if inner_fold is not None and inner_fold not in range(4):
        raise OraclePairCellError("cell scope differs")
    scope_material: list[Any] = [
        CONTRACT_ID,
        stage,
        repeat,
        outer_fold,
        -1 if inner_fold is None else inner_fold,
    ]
    if system_id == "F2":
        material = [
            *scope_material,
            "F2",
            alpha,
            lambda_,
            candidate,
            episode_id,
            selection_token_sha256,
        ]
    else:
        material = [*scope_material, system_id, candidate, episode_id]
        if system_id in {"F0", "F1"}:
            material.extend((selection_token_sha256, upstream_candidate_receipt_sha256))
    return sha256(_compact_json(material)).hexdigest()


def fragment_id(
    stage: Literal["inner", "outer"],
    repeat: int,
    outer_fold: int,
    inner_fold: int | None,
    system_id: str,
    candidate: str,
    episode_id: str,
    scoped_cell_id: str,
    *,
    selection_token_sha256: str | None = None,
    upstream_candidate_receipt_sha256: str | None = None,
) -> str:
    """Build the exact private fragment identity."""

    material: list[Any] = [
        CONTRACT_ID,
        stage,
        repeat,
        outer_fold,
        -1 if inner_fold is None else inner_fold,
        system_id,
        candidate,
        episode_id,
        scoped_cell_id,
    ]
    if system_id == "F2":
        material.append(selection_token_sha256)
    elif system_id in {"F0", "F1"}:
        material.extend((selection_token_sha256, upstream_candidate_receipt_sha256))
    return sha256(_compact_json(material)).hexdigest()


def build_pair_examples(
    capability: OracleCellCapability,
) -> tuple[PairExample, ...]:
    """Rebuild directed examples from verified pair rows and target deltas."""

    if not isinstance(
        capability.target, (OracleCellTargetCapability, OracleC3TargetCapability)
    ):
        raise OraclePairCellError("unsupported target capability")
    model = capability.model_public
    rows = capability.target.training_pairs
    molecule_by_id = {row["molecule_id"]: row for row in model.molecules}
    bits = _morgan_bits(model)
    pairs = model.pair_index
    examples: list[PairExample] = []
    for row in rows:
        pair = pairs.get(row["pair_id"])
        if pair is None:
            raise OraclePairCellError("training pair is not in authenticated geometry")
        direction = _direction(pair, row["direction_id"])
        if direction is None:
            raise OraclePairCellError("training pair direction is not in geometry")
        anchor = row["anchor_molecule_id"]
        analog = row["analog_molecule_id"]
        if (anchor, analog) != (direction["anchor"], direction["analog"]):
            raise OraclePairCellError("training pair direction members differ")
        if anchor not in molecule_by_id or analog not in molecule_by_id:
            raise OraclePairCellError("training pair molecule differs")
        feature = _pair_features(direction, bits[anchor], bits[analog])
        target = _finite(row["delta"], "training delta")
        try:
            weight = float(Fraction(row["sample_weight"]))
        except (ValueError, ZeroDivisionError) as exc:
            raise OraclePairCellError("training pair weight is not finite") from exc
        if not math.isfinite(weight):
            raise OraclePairCellError("training pair weight is not finite")
        if weight <= 0.0:
            raise OraclePairCellError("training pair weight is not positive")
        role = (
            "a_to_b" if row["direction_id"] == pair["a_to_b_direction_id"] else "b_to_a"
        )
        examples.append(
            PairExample(
                row["pair_id"],
                row["direction_id"],
                anchor,
                analog,
                row["component_id"],
                target,
                weight,
                feature,
                role,
            )
        )
    if not examples:
        raise OraclePairCellError("cell has no pair examples")
    return tuple(examples)


def run_pair_cell(
    capability: OracleCellCapability,
    *,
    system_id: str,
    alpha: float | None,
    lambda_: float | None,
    g0_predictions: Mapping[tuple[str, str, int], float],
    upstream_t0: TraceModel | None = None,
    extractor: Any = extract_transformation_pair,
    selection_token_sha256: str | None = None,
    upstream_candidate_receipt_sha256: str | None = None,
    control_cache: Mapping[tuple[str, str, int], tuple[LocalControlAnchor, ...]]
    | None = None,
    _shared_t0_capability: bool = False,
) -> PairCellResult:
    """Fit one system in one fresh cell and return its immutable CSV bytes.

    The caller has already authenticated one exact model-public/target root
    pair.  No hidden scorer fields are needed: only public episode rows and the
    single target-context row for each episode are used.
    """

    if system_id not in SYSTEMS:
        raise OraclePairCellError("unknown pair system")
    if capability.system_id != system_id and not (
        _shared_t0_capability
        and capability.system_id == "T0"
        and system_id in {"F0", "F1"}
    ):
        raise OraclePairCellError("capability system differs")
    stage, repeat, outer, inner = _scope(capability)
    if system_id == "C3" and not isinstance(
        capability.target, OracleC3TargetCapability
    ):
        raise OraclePairCellError("C3 requires c3-target capability")
    if system_id != "C3" and isinstance(capability.target, OracleC3TargetCapability):
        raise OraclePairCellError(
            "measured pair system requires cell-target capability"
        )
    candidate = candidate_id(
        system_id,
        alpha,
        lambda_,
        selection_token_sha256=selection_token_sha256,
        upstream_candidate_receipt_sha256=upstream_candidate_receipt_sha256,
    )
    if system_id == "F2" and not selection_token_sha256:
        raise OraclePairCellError("F2 requires the T0 selection token")
    if system_id in {"F0", "F1"} and (
        not selection_token_sha256 or not upstream_candidate_receipt_sha256
    ):
        raise OraclePairCellError("wrong-anchor control requires T0 receipts")
    if selection_token_sha256 is not None and not _is_digest(selection_token_sha256):
        raise OraclePairCellError("selection token receipt differs")
    if upstream_candidate_receipt_sha256 is not None and not _is_digest(
        upstream_candidate_receipt_sha256
    ):
        raise OraclePairCellError("upstream candidate receipt differs")
    if system_id in {"C0", "C1", "F0", "F1"} and (
        alpha is not None or lambda_ is not None
    ):
        raise OraclePairCellError("non-learned candidate hyperparameters differ")
    if system_id in {"C2", "A2"} and (alpha not in ALPHA_VALUES or lambda_ is not None):
        raise OraclePairCellError("candidate grid differs")
    if system_id in {"C3", "T0", "F2"} and (
        alpha not in ALPHA_VALUES or lambda_ not in LAMBDA_VALUES
    ):
        raise OraclePairCellError("candidate grid differs")
    if system_id in {"A0", "A1"} and (
        alpha is not None or lambda_ not in LAMBDA_VALUES
    ):
        raise OraclePairCellError("candidate grid differs")
    examples = (
        build_pair_examples(capability)
        if system_id in {"C2", "C3", "T0", "F2", "A0", "A1", "A2"}
        else ()
    )
    points = _training_points(capability)
    point_values = {key: value.point for key, value in points.items()}
    measured_contexts = _measured_contexts(capability)
    global_contexts = _global_contexts(capability)
    queries = _episode_queries(
        capability, g0_predictions, measured_contexts, global_contexts
    )
    if not queries:
        raise OraclePairCellError("cell has no public query rows")
    fit_context = point_values
    context_examples = tuple(
        example for example in examples if example.anchor_molecule_id in fit_context
    )
    if system_id in {"C2", "T0", "A2", "F2"} and not context_examples:
        raise OraclePairCellError("context model has no anchored training examples")
    model: TraceModel | None = None
    if system_id in {"C2", "T0", "A2", "F2", "C3"}:
        if alpha is None or (lambda_ is None and system_id in {"T0", "F2", "C3"}):
            raise OraclePairCellError("candidate hyperparameters are incomplete")
    if system_id == "C2":
        model = fit_c2(context_examples, fit_context, alpha=alpha or 0.0)
    elif system_id == "C3":
        model = fit_c3(examples, alpha=alpha or 0.0, lambda_=lambda_ or 0.0)
    elif system_id == "T0":
        model = fit_t0(
            context_examples,
            fit_context,
            alpha=alpha or 0.0,
            lambda_=lambda_ or 0.0,
        )
    elif system_id == "F2":
        model = fit_f2(
            context_examples,
            fit_context,
            alpha=alpha or 0.0,
            lambda_=lambda_ or 0.0,
            seed=scoped_seed(BASE_SEED, "F2", repeat, outer, inner, "fit"),
        )
    elif system_id == "A0":
        model = fit_a0(examples, lambda_=lambda_ or 0.0)
    elif system_id == "A1":
        model = fit_a1(examples, lambda_=lambda_ or 0.0)
    elif system_id == "A2":
        model = fit_a2(context_examples, fit_context, alpha=alpha or 0.0)
    elif system_id in {"F0", "F1"}:
        if stage != "outer" or upstream_t0 is None or upstream_t0.system_id != "T0":
            raise OraclePairCellError("F0/F1 require one shared outer T0 model")
        model = upstream_t0
    rows: list[dict[str, str]] = []
    for item in queries:
        prediction = _predict(
            system_id,
            model,
            item,
            points,
            capability.model_public,
            repeat,
            outer,
            inner,
            extractor,
            control_cache,
        )
        rows.append(_fragment_row(item, system_id, candidate, prediction))
    rows.sort(key=lambda row: (row["episode_id"], int(row["query_rank"])))
    fragment = _csv_bytes(rows)
    episode_id = "all"
    scoped_cell = cell_id(
        stage,
        repeat,
        outer,
        inner,
        system_id,
        candidate,
        episode_id,
        alpha=alpha,
        lambda_=lambda_,
        selection_token_sha256=selection_token_sha256,
        upstream_candidate_receipt_sha256=upstream_candidate_receipt_sha256,
    )
    return PairCellResult(
        fragment,
        tuple(rows),
        _accounting(
            system_id,
            len(examples),
            len(points),
            measured_contexts,
        ),
        candidate,
        fragment_id(
            stage,
            repeat,
            outer,
            inner,
            system_id,
            candidate,
            episode_id,
            scoped_cell,
            selection_token_sha256=selection_token_sha256,
            upstream_candidate_receipt_sha256=upstream_candidate_receipt_sha256,
        ),
        model,
    )


def run_shared_outer_t0(
    capability: OracleCellCapability,
    *,
    alpha: float,
    lambda_: float,
    selection_token_sha256: str,
    g0_predictions: Mapping[tuple[str, str, int], float],
    extractor: Any = extract_transformation_pair,
) -> tuple[PairCellResult, PairCellResult, PairCellResult]:
    """Fit one outer T0 model and emit T0, F0, and F1 results from it.

    The two controls receive the already-fitted model and the same capability;
    they perform no target parse, fit, selection, or calibration of their own.
    """

    if capability.system_id != "T0":
        raise OraclePairCellError("shared T0 capability differs")
    if capability.target.scope[0] != "outer":
        raise OraclePairCellError("shared T0 process requires outer scope")
    if not _is_digest(selection_token_sha256):
        raise OraclePairCellError("selection token receipt differs")
    t0 = run_pair_cell(
        capability,
        system_id="T0",
        alpha=alpha,
        lambda_=lambda_,
        g0_predictions=g0_predictions,
        extractor=extractor,
    )
    if t0.model is None:
        raise OraclePairCellError("shared T0 model was not retained")
    upstream_receipt = sha256(t0.fragment).hexdigest()
    control_cache = _build_control_cache(capability, g0_predictions, extractor)
    f0 = run_pair_cell(
        capability,
        system_id="F0",
        alpha=None,
        lambda_=None,
        g0_predictions=g0_predictions,
        upstream_t0=t0.model,
        extractor=extractor,
        selection_token_sha256=selection_token_sha256,
        upstream_candidate_receipt_sha256=upstream_receipt,
        control_cache=control_cache,
        _shared_t0_capability=True,
    )
    f1 = run_pair_cell(
        capability,
        system_id="F1",
        alpha=None,
        lambda_=None,
        g0_predictions=g0_predictions,
        upstream_t0=t0.model,
        extractor=extractor,
        selection_token_sha256=selection_token_sha256,
        upstream_candidate_receipt_sha256=upstream_receipt,
        control_cache=control_cache,
        _shared_t0_capability=True,
    )
    return t0, f0, f1


def _predict(
    system_id: str,
    model: TraceModel | None,
    item: _EpisodeQuery,
    points: Mapping[str, ControlMolecule],
    public: OracleModelPublicCapability,
    repeat: int,
    outer: int,
    inner: int | None,
    extractor: Any,
    control_cache: Mapping[tuple[str, str, int], tuple[LocalControlAnchor, ...]] | None,
) -> Prediction:
    if system_id == "C0":
        if item.anchor_point is None:
            return Prediction(item.g0, False, "G0", "missing_anchor_context")
        return Prediction(item.anchor_point, True, "C0", None)
    if system_id == "C1":
        query = _control_query(item, public)
        anchor = nearest_training_anchor(query, tuple(points.values()))
        return external_anchor_prediction(anchor, g0_prediction=item.g0)
    if system_id in {"F0", "F1"}:
        if model is None:
            raise OraclePairCellError("control model missing")
        key = (
            item.row["episode_id"],
            item.row["query_molecule_id"],
            int(item.row["query_rank"]),
        )
        if control_cache is None:
            query = _control_query(item, public)
            valid = valid_on_demand_anchors(
                query, tuple(points.values()), extractor=extractor
            )
        else:
            if key not in control_cache:
                raise OraclePairCellError("control geometry cache is incomplete")
            valid = control_cache[key]
        selected: LocalControlAnchor | None
        if system_id == "F0":
            selected = select_f0_anchor(
                valid,
                repeat=repeat,
                outer_fold=outer,
                inner_fold=inner,
                query_id=_f0_query_id(item.row),
            )
        else:
            selected = select_f1_anchor(valid)
        return wrong_anchor_prediction(
            model, selected, g0_prediction=item.g0, system_id=system_id
        )
    if model is None:
        raise OraclePairCellError("local model missing")
    context = item.anchor_point if system_id != "C3" else _global_anchor(item)
    if item.pair is None:
        return Prediction(item.g0, False, "G0", "invalid_transformation")
    return predict_local(
        model, item.pair, anchor_context=context, g0_prediction=item.g0
    )


def _episode_queries(
    capability: OracleCellCapability,
    g0: Mapping[tuple[str, str, int], float],
    measured: Mapping[str, float | None],
    global_context: Mapping[str, float],
) -> tuple[_EpisodeQuery, ...]:
    model = capability.model_public
    target = capability.target
    scopes = {
        row["episode_id"]
        for row in (
            target.episode_anchor_contexts
            if isinstance(target, OracleCellTargetCapability)
            else target.global_anchor_contexts
        )
    }
    pair_rows = model.pair_index
    bits = _morgan_bits(model)
    _stage, _repeat, _outer, inner = _scope(capability)
    output: list[_EpisodeQuery] = []
    for row in model.public_queries:
        if row["episode_id"] not in scopes:
            continue
        key = (row["episode_id"], row["query_molecule_id"], int(row["query_rank"]))
        if key not in g0:
            raise OraclePairCellError("G0 fragment is missing a public query")
        episode = model.episode_index.get((row["episode_id"], int(row["query_rank"])))
        if episode is None:
            raise OraclePairCellError("episode transformation is missing")
        pair = pair_rows.get(episode["transformation_pair_id"])
        if pair is None:
            raise OraclePairCellError("episode pair is missing")
        direction = _direction(pair, episode["direction_id"])
        features = (
            None
            if episode["extraction_status"] not in VALID_STATUSES
            else _pair_features(
                direction,
                bits[row["anchor_molecule_id"]],
                bits[row["query_molecule_id"]],
            )
            if direction is not None
            else None
        )
        sim = pair["similarity"]
        output.append(
            _EpisodeQuery(
                row,
                features,
                sim,
                episode["extraction_status"],
                episode["cyp3a4_training_family_exact_support_count"],
                episode["cyp3a4_training_family_class_support_count"],
                _finite(str(g0[key]), "G0 prediction"),
                measured.get(row["episode_id"]),
                global_context.get(row["episode_id"]),
                inner,
            )
        )
    return tuple(output)


def _training_points(capability: OracleCellCapability) -> dict[str, ControlMolecule]:
    if not isinstance(capability.target, OracleCellTargetCapability):
        return {}
    bits = _morgan_bits(capability.model_public)
    molecules = {row["molecule_id"]: row for row in capability.model_public.molecules}
    records = _records(capability.model_public)
    output: dict[str, ControlMolecule] = {}
    for row in capability.target.training_points:
        value = _finite(row["point"], "training point")
        molecule = molecules.get(row["molecule_id"])
        if molecule is None:
            raise OraclePairCellError("training point molecule missing")
        output[row["molecule_id"]] = ControlMolecule(
            records[row["molecule_id"]],
            row["component_id"],
            value,
            bits[row["molecule_id"]],
        )
    return output


def _records(model: OracleModelPublicCapability) -> dict[str, MoleculeRecord]:
    inputs = [
        MoleculeInput(row["molecule_id"], row["raw_smiles"], "smiles", "r5c", "r5c")
        for row in model.molecules
    ]
    records = audit_molecules(inputs)
    by_id = {record.molecule_id: record for record in records}
    if set(by_id) != {row["molecule_id"] for row in model.molecules}:
        raise OraclePairCellError("audited molecule identity differs")
    for row in model.molecules:
        record = by_id[row["molecule_id"]]
        if (
            record.standardized_structure_hash != row["standardized_structure_hash"]
            or record.standardized_structure != row["standardized_smiles"]
        ):
            raise OraclePairCellError("audited chemistry differs")
    return by_id


def _control_query(
    item: _EpisodeQuery, model: OracleModelPublicCapability
) -> ControlQuery:
    row = item.row
    records = _records(model)
    molecule = records[row["query_molecule_id"]]
    return ControlQuery(
        row["episode_id"],
        molecule,
        row["outer_group_id"],
        _morgan_bits(model)[molecule.molecule_id],
    )


def _build_control_cache(
    capability: OracleCellCapability,
    g0: Mapping[tuple[str, str, int], float],
    extractor: Any,
) -> dict[tuple[str, str, int], tuple[LocalControlAnchor, ...]]:
    """Compute F0/F1 control geometry once for one shared outer process."""

    points = _training_points(capability)
    measured = _measured_contexts(capability)
    global_context = _global_contexts(capability)
    queries = _episode_queries(capability, g0, measured, global_context)
    records = _records(capability.model_public)
    bits = _morgan_bits(capability.model_public)
    training = tuple(points.values())
    cache: dict[tuple[str, str, int], tuple[LocalControlAnchor, ...]] = {}
    for item in queries:
        row = item.row
        molecule = records.get(row["query_molecule_id"])
        if molecule is None:
            raise OraclePairCellError("control query molecule is missing")
        query = ControlQuery(
            row["episode_id"],
            molecule,
            row["outer_group_id"],
            bits[molecule.molecule_id],
        )
        key = (row["episode_id"], row["query_molecule_id"], int(row["query_rank"]))
        cache[key] = valid_on_demand_anchors(query, training, extractor=extractor)
    return cache


def _measured_contexts(capability: OracleCellCapability) -> dict[str, float | None]:
    if not isinstance(capability.target, OracleCellTargetCapability):
        return {}
    result: dict[str, float | None] = {}
    for row in capability.target.episode_anchor_contexts:
        if row["anchor_point_available"] == "true":
            result[row["episode_id"]] = _finite(row["anchor_point"], "anchor point")
        else:
            result[row["episode_id"]] = None
    return result


def _global_contexts(capability: OracleCellCapability) -> dict[str, float]:
    if not isinstance(capability.target, OracleC3TargetCapability):
        return {}
    return {
        row["episode_id"]: _finite(row["anchor_global_oof_prediction"], "OOF anchor")
        for row in capability.target.global_anchor_contexts
    }


def _global_anchor(item: _EpisodeQuery) -> float | None:
    # C3 has a distinct pure OOF context; it is never derived from measured
    # anchor state or from the G0 fallback value.
    return item.global_anchor


def _scope(
    capability: OracleCellCapability,
) -> tuple[Literal["inner", "outer"], int, int, int | None]:
    stage, repeat, outer, inner = capability.target.scope
    if stage not in {"inner", "outer"}:
        raise OraclePairCellError("cell stage differs")
    return stage, repeat, outer, inner


def _direction(pair: Mapping[str, str], direction_id: str) -> dict[str, str] | None:
    if direction_id == pair["a_to_b_direction_id"]:
        return {
            "anchor": pair["left_molecule_id"],
            "analog": pair["right_molecule_id"],
            "class": pair["a_to_b_transformation_class_id"],
            "exact": pair["a_to_b_exact_transformation_id"],
            "env1": pair["a_to_b_environment_level_1_id"],
            "env2": pair["a_to_b_environment_level_2_id"],
            "cut": pair["cut_count"],
            "fraction": pair["changed_heavy_atom_fraction"],
        }
    if direction_id == pair["b_to_a_direction_id"]:
        return {
            "anchor": pair["right_molecule_id"],
            "analog": pair["left_molecule_id"],
            "class": pair["b_to_a_transformation_class_id"],
            "exact": pair["b_to_a_exact_transformation_id"],
            "env1": pair["b_to_a_environment_level_1_id"],
            "env2": pair["b_to_a_environment_level_2_id"],
            "cut": pair["cut_count"],
            "fraction": pair["changed_heavy_atom_fraction"],
        }
    return None


def _pair_features(
    direction: Mapping[str, str] | None,
    anchor_bits: Sequence[int],
    analog_bits: Sequence[int],
) -> PairFeatures:
    if direction is None or direction["cut"] == "" or not direction["class"]:
        raise OraclePairCellError("valid direction metadata is incomplete")
    try:
        cut = int(direction["cut"])
        fraction = float(Fraction(direction["fraction"]))
    except (ValueError, ZeroDivisionError) as exc:
        raise OraclePairCellError("direction fraction differs") from exc
    return PairFeatures(
        signed_morgan_difference(anchor_bits, analog_bits),
        cut,
        fraction,
        direction["class"],
        direction["exact"],
        direction["env1"],
        direction["env2"],
    )


def _morgan_bits(model: OracleModelPublicCapability) -> dict[str, tuple[int, ...]]:
    array = model.features["morgan_binary.npy"]
    return {
        row["molecule_id"]: tuple(int(value) for value in array[index])
        for index, row in enumerate(model.molecules)
    }


def _f0_query_id(row: Mapping[str, str]) -> str:
    return sha256(
        _compact_json(
            [row["episode_id"], row["query_molecule_id"], int(row["query_rank"])]
        )
    ).hexdigest()


def _fragment_row(
    item: _EpisodeQuery, system_id: str, candidate: str, prediction: Prediction
) -> dict[str, str]:
    row = item.row
    return {
        "episode_id": row["episode_id"],
        "query_molecule_id": row["query_molecule_id"],
        "query_rank": row["query_rank"],
        "episode_policy_id": row["episode_policy_id"],
        "repeat": row["repeat"],
        "outer_fold": row["outer_fold"],
        "inner_fold": "" if item.inner_fold is None else str(item.inner_fold),
        "component_id": row["outer_group_id"],
        "system_id": system_id,
        "candidate_id": candidate,
        "prediction": format(_finite(str(prediction.value), "prediction"), ".17g"),
        "local_available": "true" if prediction.local_available else "false",
        "prediction_source": prediction.prediction_source,
        "extraction_status": item.extraction_status,
        "similarity": item.similarity,
        "exact_support_components": item.exact_support,
        "class_support_components": item.class_support,
    }


def _csv_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(FRAGMENT_COLUMNS),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _accounting(
    system: str,
    pair_rows: int,
    point_rows: int,
    contexts: Mapping[str, float | None],
) -> dict[str, int]:
    result = {
        name: 0
        for name in (
            "direct_target_values_parsed",
            "anchor_labels_exposed_to_models",
            "query_truth_values_opened_by_scorers",
            "maplight_model_fits",
            "ridge_model_fits",
            "hierarchy_fits",
            "predictions_frozen",
            "internal_absolute_error_evaluations",
            "blinded_test_files_opened",
            "tdi_files_opened",
            "official_metric_calls",
            "submissions_created",
            "transductive_relationships",
            "inferred_anchor_candidate_pools",
        )
    }
    available = sum(value is not None for value in contexts.values())
    if system == "C0":
        result["direct_target_values_parsed"] = available
    elif system == "C3":
        result["direct_target_values_parsed"] = pair_rows
    elif system in {"F0", "F1"}:
        result["direct_target_values_parsed"] = 0
    elif system == "C1":
        result["direct_target_values_parsed"] = point_rows + available
    else:
        result["direct_target_values_parsed"] = point_rows + pair_rows + available
    if system in {"F0", "F1", "C3"}:
        result["anchor_labels_exposed_to_models"] = 0
    else:
        result["anchor_labels_exposed_to_models"] = available
    if system in {"C2", "A2", "C3", "T0", "F2"}:
        result["ridge_model_fits"] = 1
    if system in {"A0", "A1", "C3", "T0", "F2"}:
        result["hierarchy_fits"] = 1
    return result


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OraclePairCellError(f"{label} is not finite") from exc
    if not math.isfinite(result):
        raise OraclePairCellError(f"{label} is not finite")
    return result


def _compact_json(value: Any) -> bytes:
    import json

    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()


def _is_digest(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


__all__ = [
    "CONTRACT_ID",
    "FRAGMENT_COLUMNS",
    "G0Prediction",
    "OraclePairCellError",
    "PairCellResult",
    "build_pair_examples",
    "candidate_id",
    "cell_id",
    "fragment_id",
    "run_pair_cell",
    "run_shared_outer_t0",
]
