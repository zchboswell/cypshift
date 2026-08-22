"""Authenticated R5C outer scoring; no target, fit, or prediction authority."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, cast

from cypshift.openadmet_oracle_freezer_io import SYSTEMS
from cypshift.openadmet_oracle_pair_cell_io import ACCOUNTING_FIELDS
from cypshift.openadmet_oracle_private_io import (
    OraclePrivateIOError,
    publish_readonly_tree,
    validate_output_root,
)
from cypshift.openadmet_oracle_scoring import (
    PRIMARY_POPULATION,
    REQUIRED_CONTRASTS,
    SAFETY_POPULATION,
    STRESS_POPULATION,
    CellMetric,
    MetricResult,
    PredictionRow,
    PublicQuery,
    ScoredRow,
    SealedTruth,
    _aggregate_metrics,
    aggregate_metrics,
    cell_contrasts,
    cell_metrics,
    score_predictions,
    score_stress_predictions,
    stress_diagnostic,
)
from cypshift.openadmet_oracle_sealed import SealedScorerCapability
from cypshift.openadmet_oracle_statistics import (
    BootstrapSummary,
    InfluenceCheck,
    SafetySeries,
    SafetySummary,
    bootstrap_contrasts,
    comparison_series,
    fuse_safety_predictions,
    resolve_status,
    safety_bootstrap,
    top_influence,
)
from cypshift.openadmet_oracle_terminal import (
    ABLATION_COLUMNS,
    BOOTSTRAP_COLUMNS,
    CELL_COLUMNS,
    INFLUENCE_COLUMNS,
    RESULT_SCHEMA,
    SCORED_COLUMNS,
    _authority,
    _compact_json,
    _manifest,
    _receipt,
    _validate_terminal,
    cleanup_private_roots,
)
from cypshift.openadmet_oracle_terminal_cleanup import (
    CleanupCapability,
    CleanupInput,
    OracleTerminalCleanupError,
    load_cleanup,
)
from cypshift.openadmet_oracle_terminal_io import (
    AggregateAccountingInput,
    FreezeInput,
    InnerSelectionInput,
    LoadedAggregateAccounting,
    LoadedFreeze,
    LoadedInnerSelection,
    LoadedSupport,
    OracleTerminalIOError,
    SealedOuterInput,
    SupportInput,
    load_aggregate_accounting,
    load_freeze,
    load_inner_selection,
    load_sealed_outer,
    load_support,
    validate_execution,
)
from cypshift.openadmet_transformation_io import canonical_csv_bytes

SYSTEM_ORDER: Final = {system: index for index, system in enumerate(SYSTEMS)}
POPULATION_ORDER: Final = {
    PRIMARY_POPULATION: 0,
    SAFETY_POPULATION: 1,
    STRESS_POPULATION: 2,
}


class OracleOuterScorerError(ValueError):
    """An outer scorer input, join, statistic, or terminal invariant failed."""


@dataclass(frozen=True, slots=True)
class OuterScorerInputs:
    freeze: FreezeInput
    inner_selection: InnerSelectionInput
    sealed_outer: tuple[SealedOuterInput, ...]
    support: SupportInput
    aggregate_accounting: AggregateAccountingInput
    cleanup: CleanupInput


@dataclass(frozen=True, slots=True)
class OuterEvidence:
    status: str
    primary_rows: tuple[ScoredRow, ...]
    safety_rows: tuple[ScoredRow, ...]
    stress_rows: tuple[ScoredRow, ...]
    metrics: tuple[MetricResult, ...]
    cells: tuple[CellMetric, ...]
    bootstrap: tuple[BootstrapSummary, ...]
    influence: tuple[InfluenceCheck, ...]
    safety: SafetySummary
    stress: Mapping[str, Mapping[str, Any]]


def score_outer_terminal(
    inputs: OuterScorerInputs,
    output_root: Path,
    *,
    expected_source_sha256: str,
) -> Path:
    """Authenticate all scorer-only roots, score once, and publish one terminal."""

    try:
        source, runtime = validate_execution(expected_source_sha256)
        validate_output_root(output_root)
        freeze = load_freeze(inputs.freeze)
        inner = load_inner_selection(inputs.inner_selection)
        support = load_support(inputs.support)
        if support.status != "SUPPORTED":
            raise OracleOuterScorerError("supported scorer received underpowered input")
        sealed = load_sealed_outer(inputs.sealed_outer)
        accounting = load_aggregate_accounting(inputs.aggregate_accounting)
        cleanup = load_cleanup(inputs.cleanup)
        _validate_accounting_ancestry(freeze, inner, sealed, accounting)
        truths, predictions, truth_opens = _bind_inputs(freeze, inner, sealed)
        _validate_observed_support(truths, support)
        evidence = _score(truths, predictions)
        payloads = _serialize(
            freeze,
            inner,
            support,
            accounting,
            evidence,
            truth_opens,
            source,
            runtime,
            cleanup.sha256,
        )
        required_cleanup = _required_cleanup(inputs)
        if cleanup.capabilities != required_cleanup:
            raise OracleOuterScorerError("outer cleanup set differs")
        cleanup_roots = (*(item.root for item in required_cleanup), inputs.cleanup.root)
        _validate_cleanup_paths(output_root, cleanup_roots)
        _validate_terminal(payloads, evidence.status)
        cleanup_private_roots(cleanup_roots)
        publish_readonly_tree(output_root, payloads)
    except (
        OraclePrivateIOError,
        OracleTerminalCleanupError,
        OracleTerminalIOError,
        ValueError,
    ) as exc:
        if isinstance(exc, OracleOuterScorerError):
            raise
        raise OracleOuterScorerError(str(exc)) from exc
    return output_root


def _bind_inputs(
    freeze: LoadedFreeze,
    inner: LoadedInnerSelection,
    sealed: Sequence[SealedScorerCapability],
) -> tuple[
    tuple[SealedTruth, ...],
    dict[str, tuple[PredictionRow, ...]],
    int,
]:
    freeze_inputs = _object(freeze.manifest["input_receipts"], "freeze inputs")
    tokens = _object(freeze_inputs["selection_tokens"], "freeze tokens")
    inner_tokens = _object(inner.manifest["token_receipts"], "inner tokens")
    for system in ("C2", "C3", "T0", "A0", "A1", "A2"):
        for repeat in range(3):
            for outer in range(5):
                outer_key = f"repeat-{repeat}/outer-{outer}/{system}"
                inner_key = f"{system}/repeat-{repeat}/outer-{outer}"
                if tokens.get(outer_key) != inner_tokens.get(inner_key):
                    raise OracleOuterScorerError("selection token receipt differs")
    selected = {
        (row["system_id"], int(row["repeat"]), int(row["outer_fold"])): row[
            "candidate_id"
        ]
        for row in inner.rows
        if row["selected"] == "true"
    }
    for selection_key in selected:
        system_id, repeat, outer = selection_key
        candidates = {
            row["candidate_id"]
            for row in freeze.predictions[system_id]
            if int(row["repeat"]) == repeat and int(row["outer_fold"]) == outer
        }
        if candidates != {selected[selection_key]}:
            raise OracleOuterScorerError("selected outer candidate differs")

    eligibility_receipts = _object(
        freeze_inputs["eligibility_manifests"], "freeze eligibility receipts"
    )
    source_binding = _object(
        _object(freeze.manifest["parent_receipts"], "freeze parents")[
            "source_bundle_binding"
        ],
        "freeze source binding",
    )
    eligibility_index = {
        (row["episode_id"], row["query_molecule_id"], int(row["query_rank"])): row
        for row in freeze.eligibility
    }
    public_index = {
        (row["episode_id"], row["query_molecule_id"], int(row["query_rank"])): row
        for row in freeze.predictions["G0"]
    }
    if len(public_index) != len(freeze.predictions["G0"]):
        raise OracleOuterScorerError("frozen public key is duplicated")
    truths: list[SealedTruth] = []
    cliffs: dict[tuple[str, str, int], bool] = {}
    observed_keys: set[tuple[str, str, int]] = set()
    for capability in sealed:
        repeat, outer = capability.scope[1], capability.scope[2]
        scope = f"repeat-{repeat}/outer-{outer}"
        if (
            eligibility_receipts.get(scope) != capability.manifest_sha256
            or capability.manifest.get("source_bundle_binding") != source_binding
        ):
            raise OracleOuterScorerError("sealed scorer parent differs")
        truths_by_pair = {
            (row["episode_id"], row["query_molecule_id"]): row
            for row in capability.truth_rows
        }
        cliffs_by_pair = {
            (row["episode_id"], row["query_molecule_id"]): row
            for row in capability.cliff_rows
        }
        for eligibility in capability.eligibility_rows:
            rank = int(eligibility["query_rank"])
            key = (
                eligibility["episode_id"],
                eligibility["query_molecule_id"],
                rank,
            )
            public_row = public_index.get(key)
            frozen_eligibility = eligibility_index.get(key)
            pair = key[0], key[1]
            truth_row = truths_by_pair.get(pair)
            cliff_row = cliffs_by_pair.get(pair)
            if (
                public_row is None
                or frozen_eligibility != eligibility
                or truth_row is None
                or cliff_row is None
                or int(public_row["repeat"]) != repeat
                or int(public_row["outer_fold"]) != outer
                or key in observed_keys
            ):
                raise OracleOuterScorerError("sealed/frozen join differs")
            observed_keys.add(key)
            public = PublicQuery(
                key[0],
                key[1],
                rank,
                public_row["episode_policy_id"],
                repeat,
                outer,
                public_row["component_id"],
            )
            available = truth_row["query_point_available"] == "true"
            point = float(truth_row["query_point"]) if available else None
            truths.append(
                SealedTruth(
                    public,
                    truth_row["selector_cyp_truth"],
                    point,
                    available,
                    eligibility["valid_true_transformation"] == "true",
                    eligibility["complete_anchor"] == "true",
                )
            )
            cliffs[key] = cliff_row["activity_cliff"] == "true"
    if observed_keys != set(public_index) or observed_keys != set(eligibility_index):
        raise OracleOuterScorerError("sealed scorer population differs")
    ordered_truths = tuple(
        sorted(truths, key=lambda row: (row.public.episode_id, row.public.query_rank))
    )
    predictions = {
        system: tuple(
            _prediction(row, system, public_index, cliffs)
            for row in freeze.predictions[system]
        )
        for system in SYSTEMS
    }
    return ordered_truths, predictions, sum(row.query_point_available for row in truths)


def _prediction(
    row: Mapping[str, str],
    system: str,
    public_index: Mapping[tuple[str, str, int], Mapping[str, str]],
    cliffs: Mapping[tuple[str, str, int], bool],
) -> PredictionRow:
    key = row["episode_id"], row["query_molecule_id"], int(row["query_rank"])
    public_row = public_index[key]
    public = PublicQuery(
        key[0],
        key[1],
        key[2],
        public_row["episode_policy_id"],
        int(public_row["repeat"]),
        int(public_row["outer_fold"]),
        public_row["component_id"],
    )
    return PredictionRow(
        public,
        system,
        float(row["prediction"]),
        row["local_available"] == "true",
        row["prediction_source"],
        row["extraction_status"],
        float(row["similarity"]) if row["similarity"] else None,
        int(row["exact_support_components"]),
        int(row["class_support_components"]),
        cliffs[key],
    )


def _score(
    truths: Sequence[SealedTruth],
    predictions: Mapping[str, Sequence[PredictionRow]],
) -> OuterEvidence:
    primary = tuple(
        row
        for system in SYSTEMS
        for row in score_predictions(predictions[system], truths, system_id=system)
    )
    stress_eligible = any(
        row.public.episode_policy_id == "deterministic_random_anchor_stress"
        and row.selector_cyp_truth == "CYP3A4"
        and row.query_point_available
        and row.valid_true_transformation
        and row.complete_anchor
        for row in truths
    )
    stress = (
        tuple(
            row
            for system in SYSTEMS
            for row in score_stress_predictions(
                predictions[system], truths, system_id=system
            )
        )
        if stress_eligible
        else ()
    )
    fusion = fuse_safety_predictions(predictions["G0"], predictions["T0"], truths)
    safety = (
        *score_predictions(
            predictions["G0"], truths, system_id="G0", population_id=SAFETY_POPULATION
        ),
        *score_predictions(
            fusion,
            truths,
            system_id="SAFETY_FUSION",
            population_id=SAFETY_POPULATION,
        ),
    )
    metrics = tuple(
        aggregate_metrics(tuple(row for row in primary if row.system_id == system))
        for system in SYSTEMS
    )
    cells = tuple(
        cell
        for system in SYSTEMS
        for cell in cell_metrics(
            tuple(row for row in primary if row.system_id == system)
        )
    )
    series = tuple(
        comparison_series(
            primary,
            control,
            candidate,
            comparison_id=comparison_id,
            local_only=local,
        )
        for comparison_id, control, candidate, local in REQUIRED_CONTRASTS
    )
    bootstraps = bootstrap_contrasts(series)
    influence = top_influence(series[0])
    cell_evidence = cell_contrasts(primary)
    g0_safety = aggregate_metrics(tuple(row for row in safety if row.system_id == "G0"))
    fusion_safety = aggregate_metrics(
        tuple(row for row in safety if row.system_id == "SAFETY_FUSION")
    )
    safety_summary = safety_bootstrap(
        SafetySeries(
            SAFETY_POPULATION,
            tuple(item[0] for item in g0_safety.component_losses),
            tuple(item[1] for item in g0_safety.component_losses),
            tuple(item[1] for item in fusion_safety.component_losses),
        )
    )
    stress_summary = (
        {
            system: cast(
                Mapping[str, Any],
                asdict(
                    stress_diagnostic(
                        tuple(row for row in primary if row.system_id == system),
                        tuple(row for row in stress if row.system_id == system),
                    )
                ),
            )
            for system in SYSTEMS
        }
        if stress
        else {system: {"status": "EMPTY", "scored_rows": 0} for system in SYSTEMS}
    )
    status = resolve_status(
        integrity_status="PASS",
        support_status="SUPPORTED",
        predictions_status="COMPLETE",
        bootstrap_summaries=bootstraps,
        cell_contrasts=cell_evidence,
        influence_checks=influence,
        safety=safety_summary,
    )
    return OuterEvidence(
        status,
        primary,
        tuple(safety),
        stress,
        metrics,
        cells,
        bootstraps,
        influence,
        safety_summary,
        stress_summary,
    )


def _serialize(
    freeze: LoadedFreeze,
    inner: LoadedInnerSelection,
    support: LoadedSupport,
    aggregate: LoadedAggregateAccounting,
    evidence: OuterEvidence,
    truth_opens: int,
    source: str,
    runtime: Mapping[str, str],
    cleanup_sha256: str,
) -> dict[str, bytes]:
    scored_rows = _ordered_scored_rows(evidence)
    cell_rows = _cell_rows(evidence.cells)
    bootstrap_rows = [_bootstrap_row(item) for item in evidence.bootstrap]
    influence_rows = [_influence_row(item) for item in evidence.influence]
    ablation_rows, ablation_result = _ablation_rows(evidence)
    accounting = dict(aggregate.operation_accounting)
    accounting["query_truth_values_opened_by_scorers"] += truth_opens
    evaluations = {
        (row.system_id, row.episode_id, row.query_molecule_id, row.query_rank)
        for row in scored_rows
    }
    accounting["internal_absolute_error_evaluations"] += len(evaluations)
    _validate_final_accounting(accounting, freeze)
    parents = {
        "aggregate_accounting_sha256": aggregate.sha256,
        "cleanup_manifest_sha256": cleanup_sha256,
        "inner_selection_manifest_sha256": inner.manifest_sha256,
        "outer_freeze_manifest_sha256": freeze.manifest_sha256,
        "prefit_support_sha256": support.sha256,
    }
    # The freeze already binds the exact 15 scorer capabilities. They are
    # transport inputs, not operation-accounting children to sum a second time.
    freeze_inputs = _object(freeze.manifest["input_receipts"], "freeze inputs")
    sealed_receipts = _object(
        freeze_inputs["eligibility_manifests"], "freeze eligibility receipts"
    )
    sealed_material = "".join(
        f"{label}|{receipt}\n" for label, receipt in sorted(sealed_receipts.items())
    ).encode()
    from hashlib import sha256

    parents["outer_sealed_set_sha256"] = sha256(sealed_material).hexdigest()
    authority = _authority(evidence.status)
    positive_cells = cell_contrasts(evidence.primary_rows)
    repeat_positive = {
        str(repeat): sum(
            item.point_delta > 0.0 for item in positive_cells if item.repeat == repeat
        )
        for repeat in range(3)
    }
    criteria = {
        **dict(support.criteria),
        "all_required_bootstrap_lower_bounds_positive": all(
            item.lower_bound_positive for item in evidence.bootstrap
        ),
        "positive_G0_T0_cells_at_least_12": sum(
            item.point_delta > 0.0 for item in positive_cells
        )
        >= 12,
        "each_repeat_positive_G0_T0_cells_at_least_3": all(
            count >= 3 for count in repeat_positive.values()
        ),
        "all_top10_leave_one_out_directions_positive": all(
            item.direction_preserved for item in evidence.influence
        ),
        "safety_upper_95_below_0.01": evidence.safety.upper_bound_below_criterion,
        "safety_worst_decile_degradation_at_most_0.05": (
            evidence.safety.worst_decile_criterion
        ),
    }
    result = {
        "schema_version": RESULT_SCHEMA,
        "contract_sha256": cast(str, freeze.manifest["contract_sha256"]),
        "parent_receipts": dict(sorted(parents.items())),
        "status": evidence.status,
        "support": dict(support.support),
        "criteria": criteria,
        "point_estimates": {
            item.system_id: {
                "query_macro_mae": item.query_macro_mae,
                "episode_macro_mae": item.episode_macro_mae,
                "component_macro_mae": item.component_macro_mae,
            }
            for item in evidence.metrics
        },
        "bootstrap": {
            item.comparison_id: {
                "point_delta": item.point_delta,
                "lower_95": item.lower_95,
                "upper_95": item.upper_95,
                "accepted_replicates": item.accepted_replicates,
                "attempts": item.attempts,
            }
            for item in evidence.bootstrap
        },
        "safety": asdict(evidence.safety),
        "diagnostics": {
            "positive_G0_T0_cells": sum(
                item.point_delta > 0.0 for item in positive_cells
            ),
            "positive_G0_T0_cells_by_repeat": repeat_positive,
            "stress": dict(evidence.stress),
            "ablation_scorecard": ablation_result,
        },
        "operation_accounting": accounting,
        "authority": authority,
    }
    payloads = {
        "oracle_inner_selection.csv": inner.data,
        "oracle_scored_rows.csv": canonical_csv_bytes(
            SCORED_COLUMNS, [_scored_row(row) for row in scored_rows]
        ),
        "oracle_cell_metrics.csv": canonical_csv_bytes(CELL_COLUMNS, cell_rows),
        "oracle_bootstrap_summary.csv": canonical_csv_bytes(
            BOOTSTRAP_COLUMNS, bootstrap_rows
        ),
        "oracle_influence_checks.csv": canonical_csv_bytes(
            INFLUENCE_COLUMNS, influence_rows
        ),
        "oracle_ablation_scorecard.csv": canonical_csv_bytes(
            ABLATION_COLUMNS, ablation_rows
        ),
        "oracle_result.json": _compact_json(result),
    }
    outputs = {
        name: _receipt(
            name,
            data,
            {
                "oracle_inner_selection.csv": tuple(inner.rows[0])
                if inner.rows
                else (),
                "oracle_scored_rows.csv": SCORED_COLUMNS,
                "oracle_cell_metrics.csv": CELL_COLUMNS,
                "oracle_bootstrap_summary.csv": BOOTSTRAP_COLUMNS,
                "oracle_influence_checks.csv": INFLUENCE_COLUMNS,
                "oracle_ablation_scorecard.csv": ABLATION_COLUMNS,
            }.get(name),
        )
        for name, data in payloads.items()
    }
    manifest = _manifest(
        evidence.status,
        parents,
        parents,
        source,
        runtime,
        {
            "primary_bootstrap_seed": 20260821,
            "safety_bootstrap_seed": 20260822,
            "accepted_replicates": 2000,
            "maximum_attempts": 20000,
        },
        outputs,
        accounting,
        authority,
    )
    return {"manifest.json": _compact_json(manifest), **payloads}


def _required_cleanup(inputs: OuterScorerInputs) -> tuple[CleanupCapability, ...]:
    capabilities = [
        CleanupCapability(
            "aggregate-accounting",
            inputs.aggregate_accounting.root,
            "accounting.json",
            inputs.aggregate_accounting.expected_sha256,
        ),
        CleanupCapability(
            "inner-selection",
            inputs.inner_selection.root,
            "manifest.json",
            inputs.inner_selection.expected_manifest_sha256,
        ),
        CleanupCapability(
            "outer-freeze",
            inputs.freeze.root,
            "manifest.json",
            inputs.freeze.expected_manifest_sha256,
        ),
        CleanupCapability(
            "prefit-support",
            inputs.support.root,
            "support.json",
            inputs.support.expected_sha256,
        ),
    ]
    capabilities.extend(
        CleanupCapability(
            f"sealed-repeat-{item.repeat}-fold-{item.outer_fold}",
            item.root,
            "manifest.json",
            item.expected_manifest_sha256,
        )
        for item in inputs.sealed_outer
    )
    retained_roots = {item.root.absolute() for item in capabilities}
    for child in inputs.aggregate_accounting.child_manifests:
        child_root = child.root.absolute()
        if child_root in retained_roots:
            continue
        capabilities.append(
            CleanupCapability(
                f"accounting-child-{child.label}",
                child.root,
                "manifest.json",
                child.expected_manifest_sha256,
            )
        )
        retained_roots.add(child_root)
    return tuple(sorted(capabilities, key=lambda item: item.label))


def _validate_cleanup_paths(output_root: Path, roots: Sequence[Path]) -> None:
    output = output_root.absolute()
    for root in roots:
        candidate = root.absolute()
        if (
            output == candidate
            or output in candidate.parents
            or candidate in output.parents
        ):
            raise OracleOuterScorerError("cleanup/output path overlap")


def _ordered_scored_rows(evidence: OuterEvidence) -> tuple[ScoredRow, ...]:
    rows = (*evidence.primary_rows, *evidence.safety_rows, *evidence.stress_rows)

    def key(row: ScoredRow) -> tuple[Any, ...]:
        if row.population_id == SAFETY_POPULATION:
            system = 0 if row.system_id == "G0" else 1
        else:
            system = SYSTEM_ORDER[row.system_id]
        return (
            POPULATION_ORDER[row.population_id],
            system,
            row.repeat,
            row.outer_fold,
            row.episode_id,
            row.query_rank,
            row.query_molecule_id,
        )

    return tuple(sorted(rows, key=key))


def _scored_row(row: ScoredRow) -> dict[str, str]:
    return {
        "episode_id": row.episode_id,
        "query_molecule_id": row.query_molecule_id,
        "query_rank": str(row.query_rank),
        "episode_policy_id": row.episode_policy_id,
        "repeat": str(row.repeat),
        "outer_fold": str(row.outer_fold),
        "component_id": row.component_id,
        "population_id": row.population_id,
        "system_id": row.system_id,
        "local_eligible": _bool(row.local_eligible),
        "local_available": _bool(row.local_available),
        "prediction_source": row.prediction_source,
        "extraction_status": row.extraction_status,
        "similarity": "" if row.similarity is None else _float(row.similarity),
        "exact_support_components": str(row.exact_support_components),
        "class_support_components": str(row.class_support_components),
        "activity_cliff": _bool(row.activity_cliff),
        "similarity_bin": row.similarity_bin,
        "support_bin": row.support_bin,
        "absolute_error": _float(row.absolute_error),
        "query_weight": _float(row.query_weight),
        "episode_weight": _float(row.episode_weight),
        "component_weight": _float(row.component_weight),
    }


def _cell_rows(cells: Sequence[CellMetric]) -> list[dict[str, str]]:
    index = {(item.system_id, item.repeat, item.outer_fold): item for item in cells}
    rows: list[dict[str, str]] = []
    for system in SYSTEMS:
        for repeat in range(3):
            for outer in range(5):
                item = index[(system, repeat, outer)]
                t0 = index[("T0", repeat, outer)]
                rows.append(
                    {
                        "population_id": item.population_id,
                        "system_id": system,
                        "repeat": str(repeat),
                        "outer_fold": str(outer),
                        "scored_rows": str(item.scored_rows),
                        "scored_episodes": str(item.scored_episodes),
                        "scored_components": str(item.scored_components),
                        "query_macro_mae": _float(item.query_macro_mae),
                        "episode_macro_mae": _float(item.episode_macro_mae),
                        "component_macro_mae": _float(item.component_macro_mae),
                        "contrast_vs_T0": _float(
                            item.component_macro_mae - t0.component_macro_mae
                        ),
                    }
                )
    return rows


def _bootstrap_row(item: BootstrapSummary) -> dict[str, str]:
    return {
        "comparison_id": item.comparison_id,
        "population_id": item.population_id,
        "control_system_id": item.control_system_id,
        "candidate_system_id": item.candidate_system_id,
        "point_delta": _float(item.point_delta),
        "lower_95": _float(item.lower_95),
        "upper_95": _float(item.upper_95),
        "accepted_replicates": str(item.accepted_replicates),
        "attempts": str(item.attempts),
        "lower_bound_positive": _bool(item.lower_bound_positive),
    }


def _influence_row(item: InfluenceCheck) -> dict[str, str]:
    return {
        "comparison_id": item.comparison_id,
        "rank": str(item.rank),
        "component_id": item.component_id,
        "absolute_contribution": _float(item.absolute_contribution),
        "loo_point_delta": _float(item.loo_point_delta),
        "direction_preserved": _bool(item.direction_preserved),
    }


def _ablation_rows(
    evidence: OuterEvidence,
) -> tuple[list[dict[str, str]], dict[str, Mapping[str, Any]]]:
    by_system = {
        system: tuple(row for row in evidence.primary_rows if row.system_id == system)
        for system in SYSTEMS
    }
    g0_metric = aggregate_metrics(by_system["G0"])
    g0_losses = dict(g0_metric.component_losses)
    ranked = sorted(g0_losses, key=lambda item: (-g0_losses[item], item))
    worst = set(ranked[: max(1, math.ceil(len(ranked) * 0.10))])
    rows: list[dict[str, str]] = []
    result: dict[str, Mapping[str, Any]] = {}
    for system in SYSTEMS:
        selected = by_system[system]
        metric = aggregate_metrics(selected)
        worst_metric = _aggregate_metrics(
            tuple(row for row in selected if row.component_id in worst),
            validate_weights=False,
        )
        cliff_metric = _aggregate_metrics(
            tuple(row for row in selected if row.activity_cliff),
            validate_weights=False,
        )
        local_count = sum(row.local_available for row in selected)
        record = {
            "system_id": system,
            "population_id": PRIMARY_POPULATION,
            "scored_rows": str(metric.scored_rows),
            "scored_episodes": str(metric.scored_episodes),
            "scored_components": str(metric.scored_components),
            "query_macro_mae": _float(metric.query_macro_mae),
            "episode_macro_mae": _float(metric.episode_macro_mae),
            "component_macro_mae": _float(metric.component_macro_mae),
            "worst_global_decile_mae": _float(worst_metric.component_macro_mae),
            "activity_cliff_mae": _float(cliff_metric.component_macro_mae),
            "local_available_rows": str(local_count),
        }
        rows.append(record)
        result[system] = {
            "worst_global_decile_mae": worst_metric.component_macro_mae,
            "activity_cliff_mae": cliff_metric.component_macro_mae,
            "local_available_rows": local_count,
        }
    return rows, result


def _validate_final_accounting(
    accounting: Mapping[str, int], freeze: LoadedFreeze
) -> None:
    if (
        set(accounting) != set(ACCOUNTING_FIELDS)
        or any(type(value) is not int or value < 0 for value in accounting.values())
        or any(accounting[name] for name in ACCOUNTING_FIELDS[8:])
        or accounting["predictions_frozen"]
        != cast(Mapping[str, int], freeze.manifest["operation_accounting"])[
            "predictions_frozen"
        ]
    ):
        raise OracleOuterScorerError("final operation accounting differs")


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _float(value: float) -> str:
    if not math.isfinite(value):
        raise OracleOuterScorerError("terminal value is nonfinite")
    return format(value, ".17g")


def _validate_observed_support(
    truths: Sequence[SealedTruth], support: LoadedSupport
) -> None:
    observed: defaultdict[tuple[int, int], list[SealedTruth]] = defaultdict(list)
    for row in truths:
        if (
            row.public.episode_policy_id == "selected_anchor"
            and row.selector_cyp_truth == "CYP3A4"
            and row.query_point_available
            and row.complete_anchor
            and row.valid_true_transformation
        ):
            observed[(row.public.repeat, row.public.outer_fold)].append(row)
    expected = _object(support.support["outer_cell_support"], "support cells")
    for repeat in range(3):
        for outer in range(5):
            rows = observed[(repeat, outer)]
            actual = {
                "families": len({row.public.component_id for row in rows}),
                "rows_or_pairs": len({row.public.key for row in rows}),
            }
            if expected[f"repeat-{repeat}/outer-{outer}"] != actual:
                raise OracleOuterScorerError("observed primary cell support differs")


def _validate_accounting_ancestry(
    freeze: LoadedFreeze,
    inner: LoadedInnerSelection,
    sealed: Sequence[Any],
    accounting: LoadedAggregateAccounting,
) -> None:
    expected = _child_receipts(freeze, inner, sealed)
    if accounting.child_manifest_receipts != expected:
        raise OracleOuterScorerError("aggregate accounting ancestry differs")
    freeze_accounting = _object(
        freeze.manifest["operation_accounting"], "freeze accounting"
    )
    inner_accounting = _object(
        inner.manifest["operation_accounting"], "inner accounting"
    )
    if (
        accounting.operation_accounting["predictions_frozen"]
        != freeze_accounting["predictions_frozen"]
        or accounting.operation_accounting["query_truth_values_opened_by_scorers"]
        != inner_accounting["query_truth_values_opened_by_scorers"]
        or accounting.operation_accounting["internal_absolute_error_evaluations"]
        != inner_accounting["internal_absolute_error_evaluations"]
    ):
        raise OracleOuterScorerError("aggregate scorer/freezer ownership differs")


def _child_receipts(
    freeze: LoadedFreeze, inner: LoadedInnerSelection, sealed: Sequence[Any]
) -> tuple[tuple[str, str], ...]:
    result: dict[str, str] = {}

    def add(label: str, receipt: str) -> None:
        if label in result:
            raise OracleOuterScorerError("aggregate accounting label collision")
        result[label] = receipt

    add("inner-selection", inner.manifest_sha256)
    add("outer-freeze", freeze.manifest_sha256)
    # Sealed roots are authenticated scorer transport, not accounting owners.
    del sealed
    for prefix, manifest in (("inner", inner.manifest), ("freeze", freeze.manifest)):
        inputs = _object(manifest["input_receipts"], f"{prefix} inputs")
        for group, records in sorted(inputs.items()):
            if group not in {
                "candidate_manifests",
                "pair_fragments",
                "g0_fragments",
            }:
                continue
            if not isinstance(records, Mapping):
                continue
            for key, value in sorted(cast(Mapping[str, Any], records).items()):
                if isinstance(value, str) and len(value) == 64:
                    add(f"{prefix}-{group}-{key}".replace("/", "-"), value)
    return tuple(sorted(result.items()))


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleOuterScorerError(f"{label} differs")
    return dict(cast(Mapping[str, Any], value))


__all__ = [
    "OracleOuterScorerError",
    "OuterScorerInputs",
    "score_outer_terminal",
]
