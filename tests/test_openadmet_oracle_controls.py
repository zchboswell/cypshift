from __future__ import annotations

from dataclasses import replace

import pytest

from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_oracle_controls import (
    ControlMolecule,
    ControlQuery,
    OracleControlError,
    copy_anchor_prediction,
    external_anchor_prediction,
    morgan_tanimoto,
    nearest_training_anchor,
    select_f0_anchor,
    select_f1_anchor,
    valid_on_demand_anchors,
    wrong_anchor_prediction,
)
from cypshift.openadmet_oracle_models import PairExample, fit_t0
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput


def _record(molecule_id: str, smiles: str):
    return standardize_molecule(
        MoleculeInput(molecule_id, smiles, "smiles", "synthetic", "fixture")
    )


def _candidate(
    molecule_id: str,
    smiles: str,
    component: str,
    point: float,
    bits: tuple[int, ...],
) -> ControlMolecule:
    return ControlMolecule(_record(molecule_id, smiles), component, point, bits)


def test_morgan_and_c1_ranking_are_exact_and_family_safe() -> None:
    query = ControlQuery("episode", _record("q", "CCN"), "heldout", (1, 1, 0, 0))
    first = _candidate("a", "CCO", "train-a", 5.0, (1, 0, 0, 0))
    second = _candidate("b", "CCC", "train-b", 6.0, (1, 0, 0, 0))
    assert morgan_tanimoto(first.morgan_bits, query.morgan_bits) == 0.5
    assert nearest_training_anchor(query, (second, first)) == first
    with pytest.raises(OracleControlError, match="held-out"):
        nearest_training_anchor(query, (replace(first, component_id="heldout"),))


def test_on_demand_pool_extracts_top_ranked_once_and_preserves_direction() -> None:
    query = ControlQuery("episode", _record("q", "CCN"), "heldout", (1, 1, 0, 0))
    valid = _candidate("a", "CCO", "train-a", 5.0, (1, 0, 0, 0))
    invalid = _candidate("b", "c1ccccc1", "train-b", 6.0, (0, 0, 1, 0))
    calls: list[tuple[str, str]] = []

    def extractor(left, right):
        calls.append((left.molecule_id, right.molecule_id))
        return extract_transformation_pair(left, right)

    pool = valid_on_demand_anchors(query, (invalid, valid), extractor=extractor)
    assert calls == [("a", "q"), ("b", "q")]
    assert len(pool) == 1
    assert pool[0].anchor == valid
    assert pool[0].pair_features.signed_morgan == (0.0, 1.0, 0.0, 0.0)
    expected = extract_transformation_pair(valid.molecule, query.molecule)
    assert pool[0].pair_features.class_id == expected.a_to_b.transformation_class_id


def test_f0_and_f1_keep_anchor_identity_value_paired() -> None:
    query = ControlQuery("episode", _record("q", "CCN"), "heldout", (1, 1, 0, 0))
    anchors = (
        _candidate("a", "CCO", "train-a", 5.0, (1, 0, 0, 0)),
        _candidate("b", "CCCl", "train-b", 7.0, (1, 1, 1, 0)),
    )
    pool = valid_on_demand_anchors(
        query, anchors, extractor=extract_transformation_pair
    )
    assert select_f0_anchor(
        pool, repeat=1, outer_fold=2, inner_fold=None, query_id="q"
    ) == select_f0_anchor(
        tuple(reversed(pool)),
        repeat=1,
        outer_fold=2,
        inner_fold=None,
        query_id="q",
    )
    nearest = select_f1_anchor(pool)
    assert nearest is not None
    assert nearest.anchor.molecule.molecule_id == "b"
    assert nearest.anchor.point == 7.0


def test_predictions_use_explicit_control_or_g0_fallback() -> None:
    assert copy_anchor_prediction(5.0).value == 5.0
    fallback = external_anchor_prediction(None, g0_prediction=6.0)
    assert not fallback.local_available and fallback.prediction_source == "G0"

    query = ControlQuery("episode", _record("q", "CCN"), "heldout", (1, 1, 0, 0))
    anchor = _candidate("a", "CCO", "train-a", 5.0, (1, 0, 0, 0))
    chosen = valid_on_demand_anchors(
        query, (anchor,), extractor=extract_transformation_pair
    )[0]
    forward = PairExample(
        "pair",
        "forward",
        "a",
        "q",
        "train-a",
        1.0,
        0.5,
        chosen.pair_features,
        "a_to_b",
    )
    reverse = PairExample(
        "pair",
        "reverse",
        "q",
        "a",
        "train-a",
        -1.0,
        0.5,
        replace(
            chosen.pair_features,
            signed_morgan=tuple(-value for value in chosen.pair_features.signed_morgan),
        ),
        "b_to_a",
    )
    model = fit_t0((forward, reverse), {"a": 5.0, "q": 6.0}, alpha=1.0, lambda_=2.0)
    prediction = wrong_anchor_prediction(
        model, chosen, g0_prediction=8.0, system_id="F1"
    )
    assert prediction.local_available
    assert prediction.prediction_source == "F1"
    assert prediction.value != 8.0
    missing = wrong_anchor_prediction(model, None, g0_prediction=8.0, system_id="F0")
    assert not missing.local_available
    assert missing.fallback_reason == "no_valid_control_anchor"


def test_top64_limit_is_frozen_and_duplicates_fail() -> None:
    query = ControlQuery("episode", _record("q", "CCN"), "heldout", (1, 1, 0, 0))
    anchor = _candidate("a", "CCO", "train-a", 5.0, (1, 0, 0, 0))
    with pytest.raises(OracleControlError, match="remain 64"):
        valid_on_demand_anchors(
            query, (anchor,), extractor=extract_transformation_pair, limit=32
        )
    with pytest.raises(OracleControlError, match="duplicate"):
        valid_on_demand_anchors(
            query, (anchor, anchor), extractor=extract_transformation_pair
        )
