from __future__ import annotations

from dataclasses import fields, replace

import pytest

from cypshift.openadmet_oracle_scoring import (
    PRIMARY_POPULATION,
    SAFETY_POPULATION,
    STRESS_POLICY,
    STRESS_POPULATION,
    InnerCandidate,
    OracleScoringError,
    PredictionRow,
    PublicQuery,
    SealedTruth,
    absolute_loss,
    aggregate_metrics,
    cell_contrasts,
    cell_metrics,
    contrast,
    score_predictions,
    score_stress_predictions,
    select_inner_candidates,
    stress_diagnostic,
)
from cypshift.openadmet_oracle_statistics import (
    CellContrast,
    ContrastSeries,
    InfluenceCheck,
    SafetySeries,
    SystemSeries,
    bootstrap_contrasts,
    comparison_series,
    fuse_safety_predictions,
    make_contrast_series,
    resolve_status,
    safety_bootstrap,
    top_influence,
    worst_component_decile,
)


def _public(
    episode: str,
    query: str,
    rank: int,
    component: str,
    *,
    repeat: int = 0,
    outer: int = 0,
    policy: str = "selected_anchor",
) -> PublicQuery:
    return PublicQuery(episode, query, rank, policy, repeat, outer, component)


def _truth(
    public: PublicQuery,
    value: float | None,
    *,
    available: bool = True,
    selector: str = "CYP3A4",
    valid: bool = True,
    anchor: bool = True,
) -> SealedTruth:
    return SealedTruth(public, selector, value, available, valid, anchor)


def _prediction(
    public: PublicQuery, value: float, system: str = "G0", *, local: bool = False
) -> PredictionRow:
    return PredictionRow(public, system, value, local, "LOCAL" if local else system)


def _fixture() -> tuple[tuple[SealedTruth, ...], tuple[PredictionRow, ...]]:
    public = (
        _public("e1", "q1", 0, "a"),
        _public("e1", "q2", 1, "a"),
        _public("e2", "q3", 0, "a", repeat=1),
        _public("e3", "q4", 0, "b", outer=1),
        _public("stress", "qs", 0, "s", policy=STRESS_POLICY),
    )
    truths = (
        _truth(public[0], 0.0),
        _truth(public[1], 0.0),
        _truth(public[2], 0.0),
        _truth(public[3], 0.0),
        _truth(public[4], 0.0),
    )
    predictions = tuple(
        _prediction(row.public, value)
        for row, value in zip(truths, (1.0, 3.0, 5.0, 1.0, 100.0), strict=True)
    )
    return truths, predictions


def test_absolute_loss_and_scored_rows_never_expose_targets() -> None:
    assert absolute_loss(1.25, 0.25) == 1.0
    truths, predictions = _fixture()
    scored = score_predictions(predictions, truths, system_id="G0")
    assert len(scored) == 4
    assert "query_point" not in {field.name for field in fields(scored[0])}
    assert all(row.episode_policy_id != STRESS_POLICY for row in scored)


def test_primary_filter_is_scorer_only_and_safety_keeps_nonlocal_selected_rows() -> (
    None
):
    truths, predictions = _fixture()
    truths = truths[:3] + (
        _truth(truths[3].public, 0.0, valid=False, anchor=False),
        truths[4],
    )
    scored_primary = score_predictions(predictions, truths, system_id="G0")
    scored_safety = score_predictions(
        predictions, truths, system_id="G0", population_id=SAFETY_POPULATION
    )
    assert len(scored_primary) == 3
    assert len(scored_safety) == 4
    assert all(row.population_id == PRIMARY_POPULATION for row in scored_primary)


def test_public_superset_metadata_and_duplicate_rows_fail_closed() -> None:
    truths, predictions = _fixture()
    wrong_public = replace(predictions[0].public, component_id="wrong")
    with pytest.raises(OracleScoringError, match="public metadata"):
        score_predictions(
            (PredictionRow(wrong_public, "G0", 1.0), *predictions[1:]),
            truths,
            system_id="G0",
        )
    with pytest.raises(OracleScoringError, match="duplicate prediction"):
        score_predictions(predictions + (predictions[0],), truths, system_id="G0")
    with pytest.raises(OracleScoringError, match="duplicate sealed truth"):
        score_predictions(predictions, truths + (truths[0],), system_id="G0")


def test_aggregation_deinflates_repeats_and_uses_exact_hierarchy() -> None:
    truths, predictions = _fixture()
    rows = score_predictions(predictions, truths, system_id="G0")
    metrics = aggregate_metrics(rows)
    assert metrics.query_macro_mae == pytest.approx(2.5)
    assert metrics.episode_macro_mae == pytest.approx(8.0 / 3.0)
    assert metrics.component_macro_mae == pytest.approx(2.25)
    assert metrics.component_losses == (("a", 3.5), ("b", 1.0))
    cells = cell_metrics(rows)
    assert tuple(
        (item.repeat, item.outer_fold, item.component_macro_mae) for item in cells
    ) == (
        (0, 0, 2.0),
        (0, 1, 1.0),
        (1, 0, 5.0),
    )


def test_aggregation_weights_are_contract_validated() -> None:
    truths, predictions = _fixture()
    rows = score_predictions(predictions, truths, system_id="G0")
    with pytest.raises(OracleScoringError, match="aggregation weights"):
        aggregate_metrics((replace(rows[0], query_weight=0.25), *rows[1:]))


def test_cell_contrasts_preserve_full_hierarchy_weights_across_15_cells() -> None:
    public = tuple(
        _public(
            f"episode-{repeat}-{outer}",
            f"query-{repeat}-{outer}",
            0,
            f"component-{outer}",
            repeat=repeat,
            outer=outer,
        )
        for repeat in range(3)
        for outer in range(5)
    )
    truths = tuple(_truth(row, 0.0) for row in public)
    g0 = tuple(_prediction(row, 2.0, "G0") for row in public)
    t0 = tuple(_prediction(row, 1.0, "T0") for row in public)
    g0_rows = score_predictions(g0, truths, system_id="G0")
    t0_rows = score_predictions(t0, truths, system_id="T0")

    assert {row.component_weight for row in g0_rows} == {1.0 / 3.0}
    cells = cell_contrasts((*g0_rows, *t0_rows))
    assert tuple(
        (row.repeat, row.outer_fold, row.point_delta) for row in cells
    ) == tuple((repeat, outer, 1.0) for repeat in range(3) for outer in range(5))
    with pytest.raises(OracleScoringError, match="aggregation weights"):
        contrast(
            (replace(g0_rows[0], component_weight=1.0), *g0_rows[1:], *t0_rows),
            "G0",
            "T0",
        )


def test_contrast_uses_identical_rows_and_local_only_control_rows() -> None:
    truths, g0 = _fixture()
    t0 = tuple(
        _prediction(row.public, value, "T0", local=True)
        for row, value in zip(truths, (0.0, 0.0, 4.0, 0.0, 0.0), strict=True)
    )
    g0 = tuple(
        PredictionRow(
            row.public,
            row.system_id,
            row.prediction,
            local_available=(index < 3),
            prediction_source=row.prediction_source,
        )
        for index, row in enumerate(g0)
    )
    g0_rows = score_predictions(g0, truths, system_id="G0")
    t0_rows = score_predictions(t0, truths, system_id="T0")
    result = contrast(g0_rows + t0_rows, "G0", "T0")
    local = contrast(g0_rows + t0_rows, "G0", "T0", local_only=True)
    assert result.point_delta == pytest.approx(1.25)
    assert local.point_delta == pytest.approx(1.5)


def test_local_comparison_validates_full_weights_then_allows_partial_queries() -> None:
    truths, g0 = _fixture()
    t0 = tuple(
        _prediction(row.public, value, "T0", local=True)
        for row, value in zip(truths, (0.0, 0.0, 4.0, 0.0, 0.0), strict=True)
    )
    g0 = tuple(replace(row, local_available=index < 3) for index, row in enumerate(g0))
    rows = score_predictions(g0, truths, system_id="G0") + score_predictions(
        t0, truths, system_id="T0"
    )
    series = comparison_series(rows, "G0", "T0", local_only=True)
    assert series.population_id == "local:G0"
    assert series.component_ids == ("a", "b")
    assert series.control_losses == (3.5, None)
    assert series.candidate_losses == (2.0, None)


def test_inner_selection_tie_prefers_larger_alpha_then_lambda() -> None:
    candidates = (
        InnerCandidate("T0", 0, 0, "a1", 1.0, 2.0, 1.0, 10, 5),
        InnerCandidate("T0", 0, 0, "a2", 10.0, 2.0, 1.0, 10, 5),
        InnerCandidate("T0", 0, 0, "a3", 10.0, 10.0, 1.0, 10, 5),
        InnerCandidate("T0", 0, 0, "a4", 1.0, 10.0, 1.0, 10, 5),
    )
    assert select_inner_candidates(candidates)[0].candidate_id == "a3"
    with pytest.raises(OracleScoringError):
        select_inner_candidates(
            candidates
            + (
                InnerCandidate(
                    "T0", 0, 0, "stress", 1.0, 2.0, 0.5, population_id="stress"
                ),
            )
        )


def test_inner_support_counts_are_scope_local() -> None:
    grid = ((1.0, 2.0), (1.0, 10.0), (10.0, 2.0), (10.0, 10.0))
    candidates = tuple(
        InnerCandidate(
            "T0",
            repeat,
            0,
            f"{repeat}-{index}",
            alpha,
            lam,
            1.0,
            10 if repeat == 0 else 20,
            5 if repeat == 0 else 6,
        )
        for repeat in (0, 1)
        for index, (alpha, lam) in enumerate(grid)
    )
    assert len(select_inner_candidates(candidates)) == 2


def test_bootstrap_is_reproducible_shared_and_has_linear_percentiles() -> None:
    components = ("a", "b", "c")
    comparisons = (
        ContrastSeries(
            "G0-T0",
            PRIMARY_POPULATION,
            "G0",
            "T0",
            components,
            (2.0, 4.0, 6.0),
            (1.0, 2.0, 3.0),
        ),
        ContrastSeries(
            "C0-T0",
            PRIMARY_POPULATION,
            "C0",
            "T0",
            components,
            (1.5, 3.0, 4.5),
            (1.0, 2.0, 3.0),
        ),
    )
    first = bootstrap_contrasts(
        comparisons, accepted_replicates=50, maximum_attempts=100
    )
    second = bootstrap_contrasts(
        comparisons, accepted_replicates=50, maximum_attempts=100
    )
    assert first == second
    assert all(item.accepted_replicates == 50 and item.attempts == 50 for item in first)
    assert all(item.lower_bound_positive for item in first)


def test_bootstrap_attempt_exhaustion_is_explicit() -> None:
    with pytest.raises(OracleScoringError, match="invalid bootstrap budget"):
        bootstrap_contrasts(
            (
                ContrastSeries(
                    "G0-T0", PRIMARY_POPULATION, "G0", "T0", ("a",), (1.0,), (0.0,)
                ),
            ),
            accepted_replicates=2,
            maximum_attempts=1,
        )
    with pytest.raises(OracleScoringError, match="one-sided"):
        make_contrast_series(
            "G0-T0", PRIMARY_POPULATION, "G0", "T0", {"a": 1.0}, {"a": None}
        )
    with pytest.raises(OracleScoringError, match="primary component"):
        make_contrast_series(
            "G0-T0", PRIMARY_POPULATION, "G0", "T0", {"a": None}, {"a": None}
        )
    local = make_contrast_series(
        "F0_LOCAL-T0", "local:F0", "F0", "T0", {"a": None}, {"a": None}
    )
    assert local.control_losses == (None,)


def test_comparison_bootstrap_keeps_local_population_scoped() -> None:
    primary = ContrastSeries(
        "G0-T0", PRIMARY_POPULATION, "G0", "T0", ("a", "b"), (2.0, 4.0), (1.0, 2.0)
    )
    local = ContrastSeries(
        "F0_LOCAL-T0",
        "local:F0",
        "F0",
        "T0",
        ("a", "b"),
        (2.0, None),
        (1.0, None),
    )
    result = bootstrap_contrasts(
        (primary, local), accepted_replicates=20, maximum_attempts=100
    )
    assert {item.population_id for item in result} == {PRIMARY_POPULATION, "local:F0"}
    assert result[0].attempts == result[1].attempts
    assert result[1].point_delta == pytest.approx(1.0)


def test_influence_and_worst_decile_are_deterministic() -> None:
    series = ContrastSeries(
        "G0-T0",
        PRIMARY_POPULATION,
        "G0",
        "T0",
        ("a", "b", "c", "d"),
        (5.0, 5.0, 1.0, 0.0),
        (1.0, 2.0, 0.0, 0.0),
    )
    influence = top_influence(series, limit=2)
    assert tuple(item.component_id for item in influence) == ("a", "b")
    assert all(item.direction_preserved for item in influence)
    assert worst_component_decile(
        SystemSeries(
            PRIMARY_POPULATION, "G0", series.component_ids, series.control_losses
        )
    ) == ("a",)


def test_influence_worst_and_safety_require_their_systems() -> None:
    with pytest.raises(OracleScoringError, match="G0-T0"):
        top_influence(
            ContrastSeries(
                "bad", PRIMARY_POPULATION, "C0", "T0", ("a",), (1.0,), (0.0,)
            )
        )
    with pytest.raises(OracleScoringError, match="worst decile"):
        worst_component_decile(SystemSeries(PRIMARY_POPULATION, "T0", ("a",), (1.0,)))
    with pytest.raises(OracleScoringError, match="misaligned"):
        safety_bootstrap(
            SafetySeries(SAFETY_POPULATION, ("a",), (1.0,), (1.0, 2.0)),
            accepted_replicates=2,
            maximum_attempts=2,
        )


def test_safety_fusion_uses_half_local_and_g0_for_safety_only_rows() -> None:
    truths, g0 = _fixture()
    truths = truths[:3] + (
        _truth(truths[3].public, 0.0, valid=False, anchor=False),
        truths[4],
    )
    t0 = tuple(_prediction(row.public, 20.0, "T0", local=True) for row in truths)
    fused = fuse_safety_predictions(g0, t0, truths)
    assert len(fused) == 5
    assert fused[0].prediction == 10.5
    assert fused[3].prediction == 1.0
    assert fused[4].public.episode_policy_id == STRESS_POLICY
    fused_rows = score_predictions(
        fused, truths, system_id="SAFETY_FUSION", population_id=SAFETY_POPULATION
    )
    assert len(fused_rows) == 4
    summary = safety_bootstrap(
        SafetySeries(SAFETY_POPULATION, ("a", "safety-only"), (1.0, 2.0), (1.0, 2.0)),
        accepted_replicates=20,
        maximum_attempts=20,
    )
    assert summary.accepted_replicates == 20
    assert summary.upper_bound_below_criterion
    assert summary.worst_decile_component_ids == ("safety-only",)


def test_safety_fusion_requires_exact_public_metadata_across_systems() -> None:
    truths, g0 = _fixture()
    t0 = tuple(_prediction(row.public, 1.0, "T0") for row in truths)
    mismatched = replace(
        t0[0], public=replace(t0[0].public, episode_policy_id="wrong-policy")
    )
    with pytest.raises(OracleScoringError, match="public metadata"):
        fuse_safety_predictions(g0, (mismatched, *t0[1:]), truths)


def test_status_boundaries_are_strict_and_stress_is_rejected() -> None:
    safety = safety_bootstrap(
        SafetySeries(SAFETY_POPULATION, ("a", "b"), (1.0, 2.0), (1.0, 2.0))
    )
    series = tuple(
        ContrastSeries(
            comparison_id,
            f"local:{control}" if local else PRIMARY_POPULATION,
            control,
            candidate,
            ("a",),
            (2.0,),
            (1.0,),
        )
        for comparison_id, control, candidate, local in (
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
    )
    bootstrap = bootstrap_contrasts(series)
    cells = tuple(
        CellContrast(repeat, fold, 1.0) for repeat in range(3) for fold in range(5)
    )
    influence = tuple(
        InfluenceCheck("G0-T0", rank, f"c{rank}", 1.0, 1.0, True)
        for rank in range(1, 11)
    )
    kwargs = dict(
        integrity_status="PASS",
        support_status="SUPPORTED",
        predictions_status="COMPLETE",
        bootstrap_summaries=bootstrap,
        cell_contrasts=cells,
        influence_checks=influence,
        safety=safety,
    )
    assert resolve_status(**kwargs) == "R5_ORACLE_SIGNAL_PASS"
    negative_cells = cells[:12] + (
        CellContrast(2, 2, -1.0),
        CellContrast(2, 3, -1.0),
        CellContrast(2, 4, -1.0),
    )
    assert (
        resolve_status(**{**kwargs, "cell_contrasts": negative_cells})
        == "R5_ORACLE_NO_SIGNAL"
    )
    assert (
        resolve_status(
            integrity_status="FAIL",
            support_status="SUPPORTED",
            predictions_status="COMPLETE",
            bootstrap_summaries=(),
            cell_contrasts=(),
            influence_checks=(),
            safety=safety,
        )
        == "R5_ORACLE_FAILED"
    )
    assert (
        resolve_status(
            integrity_status="PASS",
            support_status="UNDERPOWERED",
            predictions_status="INCOMPLETE",
            bootstrap_summaries=(),
            cell_contrasts=(),
            influence_checks=(),
            safety=safety,
        )
        == "R5_ORACLE_UNDERPOWERED"
    )
    with pytest.raises(OracleScoringError, match="local bootstrap population"):
        resolve_status(
            **{
                **kwargs,
                "bootstrap_summaries": bootstrap[:8]
                + (replace(bootstrap[8], population_id="local:F2"),)
                + bootstrap[9:],
            }
        )


def test_stress_cannot_be_scored_as_primary_or_safety() -> None:
    public = _public("stress", "q", 0, "s", policy=STRESS_POLICY)
    truth = _truth(public, 1.0)
    prediction = _prediction(public, 1.0)
    with pytest.raises(OracleScoringError, match="empty"):
        score_predictions((prediction,), (truth,), system_id="G0")
    with pytest.raises(OracleScoringError, match="empty"):
        score_predictions(
            (prediction,), (truth,), system_id="G0", population_id=SAFETY_POPULATION
        )
    stress_rows = score_stress_predictions((prediction,), (truth,), system_id="G0")
    assert stress_rows[0].population_id == STRESS_POPULATION
    invalid_truth = _truth(public, 1.0, valid=False)
    with pytest.raises(OracleScoringError, match="empty"):
        score_stress_predictions((prediction,), (invalid_truth,), system_id="G0")
    diagnostic = stress_diagnostic(
        score_predictions(
            (_prediction(_public("selected", "q", 0, "a"), 1.0),),
            (_truth(_public("selected", "q", 0, "a"), 0.0),),
            system_id="G0",
        ),
        stress_rows,
    )
    assert diagnostic.population_id == STRESS_POPULATION
