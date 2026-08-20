from __future__ import annotations

import inspect
from dataclasses import replace
from fractions import Fraction

import pytest

from cypshift.openadmet_oracle_models import (
    HierarchyObservation,
    OracleModelError,
    PairExample,
    PairFeatures,
    PredictedDelta,
    RobustScaler,
    deterministic_permutation,
    diagnose_pair_antisymmetry,
    diagnose_predicted_delta_antisymmetry,
    fit_a0,
    fit_a1,
    fit_a2,
    fit_c2,
    fit_c3,
    fit_f2,
    fit_hierarchy,
    fit_t0,
    fit_weighted_ridge,
    pair_feature_vector,
    permute_category_contexts,
    predict_local,
    scoped_seed,
    signed_morgan_difference,
)


def _features(
    class_id: str = "class-a",
    exact: str = "exact-a",
    env1: str = "env1-a",
    env2: str = "env2-a",
    bits: tuple[int, ...] = (1, 0, 1, 0),
) -> PairFeatures:
    return PairFeatures(bits, 1, 0.25, class_id, exact, env1, env2)


def _example(
    pair_id: str,
    direction: str,
    anchor: str,
    analog: str,
    target: float,
    *,
    component: str = "component-a",
    class_id: str = "class-a",
) -> PairExample:
    direction_role = "a_to_b" if anchor < analog else "b_to_a"
    return PairExample(
        pair_id,
        direction,
        anchor,
        analog,
        component,
        target,
        1.0,
        _features(class_id),
        direction_role,
    )


def test_robust_scaler_uses_linear_iqr_and_zero_scale_one() -> None:
    scaler = RobustScaler.fit(((1.0, 4.0), (3.0, 4.0), (9.0, 4.0)))
    assert scaler.medians == (3.0, 4.0)
    assert scaler.scales == (4.0, 1.0)
    assert scaler.transform_row((7.0, 8.0)) == (1.0, 4.0)


def test_signed_morgan_and_other_feature_are_exact() -> None:
    assert signed_morgan_difference((1, 0, 1), (0, 1, 1)) == (-1, 1, 0)
    pair = _features(class_id="unseen")
    vector = pair_feature_vector(pair, ("class-a", "class-b"))
    assert vector[:4] == (1.0, 0.0, 1.0, 0.0)
    assert vector[4:6] == (1.0, 0.25)
    assert vector[6:] == (0.0, 0.0, 1.0)


def test_pair_feature_validation_rejects_nonbinary_and_bad_fraction() -> None:
    with pytest.raises(OracleModelError):
        signed_morgan_difference((0, 2), (1, 0))
    with pytest.raises(OracleModelError):
        pair_feature_vector(_features(), ("class-a", "class-a"))
    with pytest.raises(OracleModelError):
        pair_feature_vector(PairFeatures((0,), 1, 1.1, "a", "e", "l1", "l2"), ())


def test_weighted_ridge_honors_explicit_pair_weights() -> None:
    fit = fit_weighted_ridge(
        ((0.0,), (1.0,), (1.0,)),
        (0.0, 10.0, 10.0),
        (Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)),
        alpha=1.0,
    )
    # The equal mass at x=1 must dominate the x=0 observation; this also
    # exercises Fraction-compatible frozen pair weights.
    assert fit.predict_row((1.0,)) > fit.predict_row((0.0,))
    assert fit.alpha == 1.0


def test_hierarchy_is_component_macro_recursive_and_most_specific() -> None:
    observations = (
        HierarchyObservation("c1", "class", "exact", "env1", "env2", 2.0, 1.0),
        HierarchyObservation("c2", "class", "exact", "env1", "env2", 4.0, 3.0),
        HierarchyObservation(
            "c3", "class", "other", "other-env1", "other-env2", 8.0, 1.0
        ),
    )
    hierarchy = fit_hierarchy(observations, lambda_=2.0, stop_after="full")
    value, level, support = hierarchy.predict("class", "exact", "env1", "env2")
    assert level == "environment_level_2"
    assert support == 2
    # Every level shrinks into the immediately broader posterior.
    assert value == pytest.approx(2.975)
    _, fallback_level, fallback_support = hierarchy.predict(
        "new-class", "missing-exact", "missing-env1", "missing-env2"
    )
    assert fallback_level == "endpoint_zero"
    assert fallback_support == 0


def test_a0_a1_and_context_models_are_reusable() -> None:
    examples = (
        _example("p1", "a->b", "a", "b", 1.0),
        _example("p1", "b->a", "b", "a", -1.0),
        _example("p2", "c->d", "c", "d", 2.0, component="component-b"),
        _example("p2", "d->c", "d", "c", -2.0, component="component-b"),
    )
    points = {"a": 5.0, "b": 5.0, "c": 6.0, "d": 6.0}
    assert fit_a0(examples, lambda_=2.0).system_id == "A0"
    assert fit_a1(examples, lambda_=2.0).system_id == "A1"
    assert fit_c2(examples, points, alpha=1.0).system_id == "C2"
    assert fit_t0(examples, points, alpha=1.0, lambda_=2.0).system_id == "T0"
    assert fit_a2(examples, points, alpha=1.0).system_id == "A2"
    assert fit_f2(examples, points, alpha=1.0, lambda_=2.0, seed=3).system_id == "F2"


def test_c2_t0_and_a2_include_measured_anchor_as_a_fitted_feature() -> None:
    examples = (
        _example("p1", "z", "a", "b", -2.0),
        _example("p1", "a", "b", "a", 2.0),
        _example("p2", "z2", "c", "d", 2.0, component="component-b"),
        _example("p2", "a2", "d", "c", -2.0, component="component-b"),
    )
    points = {"a": 4.0, "b": 6.0, "c": 6.0, "d": 4.0}
    c2 = fit_c2(examples, points, alpha=1.0)
    t0 = fit_t0(examples, points, alpha=1.0, lambda_=2.0)
    a2 = fit_a2(examples, points, alpha=1.0)
    assert c2.ridge is not None and len(c2.ridge.scaler.medians) == 5
    assert t0.ridge is not None and len(t0.ridge.scaler.medians) == 9
    assert a2.ridge is not None and len(a2.ridge.scaler.medians) == 9
    low, _, _ = c2.predict_delta(_features(), anchor_context=4.0)
    high, _, _ = c2.predict_delta(_features(), anchor_context=6.0)
    assert low != high


def test_c3_api_exposes_only_oof_anchor_context() -> None:
    assert "measured_anchor" not in inspect.signature(fit_c3).parameters
    assert "anchor_global_oof_predictions" not in inspect.signature(fit_c3).parameters
    examples = (
        _example("p1", "a->b", "a", "b", 1.0),
        _example("p1", "b->a", "b", "a", -1.0),
    )
    model = fit_c3(examples, alpha=1.0, lambda_=2.0)
    assert model.system_id == "C3"
    assert model.ridge is not None
    assert len(model.ridge.scaler.medians) == 4 + 2 + 2


def test_prediction_fallback_is_explicit_and_local_context_is_used() -> None:
    examples = (
        _example("p1", "a->b", "a", "b", 1.0),
        _example("p1", "b->a", "b", "a", -1.0),
    )
    model = fit_a0(examples, lambda_=2.0)
    missing = predict_local(model, _features(), anchor_context=None, g0_prediction=7.0)
    assert missing.value == 7.0
    assert not missing.local_available
    assert missing.prediction_source == "G0"
    local = predict_local(model, _features(), anchor_context=5.0, g0_prediction=7.0)
    assert local.local_available
    assert local.prediction_source == "LOCAL"
    assert local.value != 7.0


def test_model_schema_errors_fail_closed_instead_of_becoming_g0() -> None:
    examples = (
        _example("p1", "a->b", "a", "b", 1.0),
        _example("p1", "b->a", "b", "a", -1.0),
    )
    model = fit_c2(examples, {"a": 5.0, "b": 5.0}, alpha=1.0)
    malformed = replace(_features(), signed_morgan=(1.0, 0.0))
    with pytest.raises(OracleModelError, match="feature width"):
        predict_local(model, malformed, anchor_context=5.0, g0_prediction=7.0)


def test_scoped_seed_matches_sha256_material_and_permutation_is_repeatable() -> None:
    seed = scoped_seed(20260820, "F0", 1, 2, None, "query")
    import hashlib

    expected = int.from_bytes(
        hashlib.sha256(b"20260820|F0|1|2|-1|query").digest()[:8],
        "big",
        signed=False,
    )
    assert seed == expected
    assert deterministic_permutation(
        ("a", "b", "c"), seed=seed
    ) == deterministic_permutation(("a", "b", "c"), seed=seed)


def test_f2_permutation_preserves_pair_rows_and_is_deterministic() -> None:
    examples = (
        _example("p1", "a->b", "a", "b", 1.0, class_id="class-a"),
        _example("p1", "b->a", "b", "a", -1.0, class_id="class-b"),
        _example("p2", "c->d", "c", "d", 2.0, class_id="class-c"),
        _example("p2", "d->c", "d", "c", -2.0, class_id="class-d"),
    )
    shuffled = permute_category_contexts(examples, seed=11)
    assert tuple(row.pair_id for row in shuffled) == ("p1", "p1", "p2", "p2")
    assert tuple(row.target for row in shuffled) == (1.0, -1.0, 2.0, -2.0)
    assert shuffled == permute_category_contexts(examples, seed=11)
    originals = {(row.pair_id, row.direction_role): row for row in examples}
    for row in shuffled:
        original = originals[(row.pair_id, row.direction_role)]
        assert row.features.signed_morgan == original.features.signed_morgan
        assert row.features.cut_count == original.features.cut_count
        assert (
            row.features.changed_heavy_atom_fraction
            == original.features.changed_heavy_atom_fraction
        )
        assert row.direction_id == original.direction_id


def test_pair_antisymmetry_diagnostic_reports_reversal_and_missing_rows() -> None:
    rows = (
        _example("p1", "a->b", "a", "b", 1.0),
        _example("p1", "b->a", "b", "a", -1.0),
        _example("p2", "c->d", "c", "d", 2.0),
    )
    diagnostic = diagnose_pair_antisymmetry(rows)
    assert diagnostic.pair_count == 2
    assert diagnostic.complete_pair_count == 1
    assert diagnostic.missing_reverse_pair_count == 1
    assert diagnostic.violating_pair_count == 0
    assert diagnostic.max_absolute_delta_sum == 0.0


def test_predicted_delta_antisymmetry_checks_model_output_not_targets() -> None:
    diagnostic = diagnose_predicted_delta_antisymmetry(
        (
            PredictedDelta("p1", "a_to_b", 0.75),
            PredictedDelta("p1", "b_to_a", -0.5),
            PredictedDelta("p2", "a_to_b", 1.0),
        )
    )
    assert diagnostic.complete_pair_count == 1
    assert diagnostic.missing_reverse_pair_count == 1
    assert diagnostic.violating_pair_count == 1
    assert diagnostic.max_absolute_delta_sum == 0.25


def test_hierarchy_rejects_conflicting_parent_mappings() -> None:
    observations = (
        HierarchyObservation("c1", "a", "e1", "shared", "z1", 1.0, 1.0),
        HierarchyObservation("c2", "a", "e2", "shared", "z2", 2.0, 1.0),
    )
    with pytest.raises(OracleModelError, match="conflicting parents"):
        fit_hierarchy(observations, lambda_=2.0, stop_after="full")
