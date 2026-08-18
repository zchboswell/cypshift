"""R3B component-macro scoring, bootstrap, q90, and completion math."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from r3b_scoring_artifacts import (
    BOOT_COLS,
    CELL_COLS,
    COMPARISONS,
    ENDPOINTS,
    FINAL_COMPLETE_COLS,
    MAPLIGHT,
    OUTER_COMPLETE_COLS,
    Q90_COLS,
    SYSTEMS,
    _csv_bytes,
    _eligible,
    _require,
    _sha,
    _uint,
)


def _component_means(values: Sequence[tuple[str, str, float]]) -> dict[str, float]:
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for component, _molecule, error in sorted(
        values, key=lambda item: (item[0], item[1])
    ):
        _require(math.isfinite(error), "nonfinite component error")
        grouped[component].append((_molecule, error))
    return {
        component: math.fsum(error for _molecule, error in errors) / len(errors)
        for component, errors in grouped.items()
    }


@dataclass(frozen=True)
class BootstrapResult:
    comparison_id: str
    control_system_id: str
    point_delta: float
    sign: str
    lower_95: float
    upper_95: float
    accepted_replicates: int
    attempts: int
    status: str


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    _require(
        bool(ordered and all(math.isfinite(value) for value in ordered)),
        "invalid percentile population",
    )
    h = (len(ordered) - 1) * percentile
    lower = math.floor(h)
    return ordered[lower] + (h - lower) * (
        ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]
    )


def _bootstrap(
    aggregate: Mapping[str, Mapping[tuple[str, int], Mapping[str, float]]],
    *,
    accepted_target: int = 2000,
    maximum_attempts: int = 20000,
) -> tuple[list[BootstrapResult], int]:
    contexts = sorted(next(iter(aggregate.values())))
    frame = sorted(
        {
            component
            for system in aggregate.values()
            for cell in system.values()
            for component in cell
        }
    )
    _require(bool(contexts and frame), "bootstrap frame is empty")
    index = {component: position for position, component in enumerate(frame)}
    rng = np.random.Generator(np.random.PCG64(20260819))
    draws: dict[str, list[float]] = {name: [] for name, _control in COMPARISONS}
    attempts = 0
    while (
        attempts < maximum_attempts and len(draws[COMPARISONS[0][0]]) < accepted_target
    ):
        attempts += 1
        sampled = rng.integers(
            0, len(frame), size=len(frame), endpoint=False, dtype=np.int64
        )
        multiplicity = np.bincount(sampled, minlength=len(frame))
        macros: dict[tuple[str, tuple[str, int]], float] = {}
        accepted = True
        for system in SYSTEMS:
            for context in contexts:
                cell = aggregate[system][context]
                denominator = math.fsum(multiplicity[index[name]] for name in cell)
                numerator = math.fsum(
                    multiplicity[index[name]] * value for name, value in cell.items()
                )
                if denominator <= 0 or not math.isfinite(numerator):
                    accepted = False
                    break
                macros[(system, context)] = numerator / denominator
            if not accepted:
                break
        if not accepted:
            continue
        for comparison, control in COMPARISONS:
            control_macro = math.fsum(
                macros[(control, context)] for context in contexts
            ) / len(contexts)
            maplight_macro = math.fsum(
                macros[(MAPLIGHT, context)] for context in contexts
            ) / len(contexts)
            draws[comparison].append(control_macro - maplight_macro)
    _require(
        len(draws[COMPARISONS[0][0]]) == accepted_target, "bootstrap attempt exhaustion"
    )
    results: list[BootstrapResult] = []
    for comparison, control in COMPARISONS:
        point = math.fsum(
            math.fsum(aggregate[control][context].values())
            / len(aggregate[control][context])
            - math.fsum(aggregate[MAPLIGHT][context].values())
            / len(aggregate[MAPLIGHT][context])
            for context in contexts
        ) / len(contexts)
        lower, upper = (
            _percentile(draws[comparison], 0.025),
            _percentile(draws[comparison], 0.975),
        )
        results.append(
            BootstrapResult(
                comparison,
                control,
                point,
                "positive" if point > 0 else "nonpositive",
                lower,
                upper,
                accepted_target,
                attempts,
                "PASS" if lower > 0 else "FAIL",
            )
        )
    return results, attempts


def _outer_metrics(
    rows: Sequence[Mapping[str, str]],
    truth: Mapping[tuple[str, ...], Mapping[str, str]],
    synthetic: bool,
) -> tuple[dict[str, Any], dict[str, bytes], str]:
    detailed: dict[tuple[str, str, int, int], list[tuple[str, str, float]]] = (
        defaultdict(list)
    )
    seen: set[tuple[str, ...]] = set()
    contexts: set[tuple[str, int, int]] = set()
    for row in rows:
        repeat, outer = (
            _uint(row["repeat"], "repeat", 2),
            _uint(row["outer_fold"], "outer fold", 4),
        )
        key = (row["molecule_id"], row["endpoint"], str(repeat), str(outer))
        _require(key in truth, "prediction identity missing from truth")
        identity = key + (row["system_id"],)
        _require(identity not in seen, "duplicate prediction identity")
        seen.add(identity)
        truth_row = truth[key]
        _require(
            row["component_id"] == truth_row["component_id"],
            "prediction component differs",
        )
        context = (row["endpoint"], repeat, outer)
        contexts.add(context)
        if _eligible(truth_row):
            detailed[(row["system_id"], row["endpoint"], repeat, outer)].append(
                (
                    truth_row["component_id"],
                    row["molecule_id"],
                    abs(float(row["prediction"]) - float(truth_row["point"])),
                )
            )
    _require(
        bool(contexts) and (synthetic or len(contexts) == 60),
        "outer context cardinality differs",
    )
    cell_rows: list[dict[str, object]] = []
    aggregate_values: dict[
        str, dict[tuple[str, int], dict[str, list[tuple[str, float]]]]
    ] = {system: {} for system in SYSTEMS}
    fold_macros: dict[str, dict[tuple[int, int, str], float]] = {
        system: {} for system in SYSTEMS
    }
    for endpoint, repeat, outer in sorted(contexts):
        for system in SYSTEMS:
            values = detailed[(system, endpoint, repeat, outer)]
            means = _component_means(values)
            _require(bool(means), "empty outer eligible cell")
            aggregate_values[system].setdefault((endpoint, repeat), {})
            all_errors = [
                error
                for _component, _molecule, error in sorted(
                    values, key=lambda item: (item[0], item[1])
                )
            ]
            for component in sorted(means):
                aggregate_values[system][(endpoint, repeat)].setdefault(
                    component, []
                ).extend(
                    (_molecule, error)
                    for name, _molecule, error in sorted(
                        values, key=lambda item: (item[0], item[1])
                    )
                    if name == component
                )
            cell_macro = math.fsum(means.values()) / len(means)
            fold_macros[system][(repeat, outer, endpoint)] = cell_macro
            cell_rows.append(
                {
                    "system_id": system,
                    "endpoint": endpoint,
                    "repeat": repeat,
                    "outer_fold": outer,
                    "scored_molecules": len(all_errors),
                    "scored_components": len(means),
                    "component_macro_mae": format(cell_macro, ".17g"),
                    "molecule_macro_mae": format(
                        math.fsum(all_errors) / len(all_errors), ".17g"
                    ),
                }
            )
    rank = {system: index for index, system in enumerate(SYSTEMS)}
    cell_rows.sort(
        key=lambda row: (
            rank[str(row["system_id"])],
            str(row["endpoint"]),
            int(cast(str, row["repeat"])),
            int(cast(str, row["outer_fold"])),
        )
    )
    aggregate = {
        system: {
            context: {
                component: math.fsum(error for _molecule, error in sorted(values))
                / len(values)
                for component, values in sorted(cells.items())
            }
            for context, cells in sorted(contexts.items())
        }
        for system, contexts in sorted(aggregate_values.items())
    }
    bootstrap, attempts = _bootstrap(aggregate)
    boot_rows = [
        {
            "comparison_id": result.comparison_id,
            "control_system_id": result.control_system_id,
            "candidate_system_id": MAPLIGHT,
            "point_delta": format(result.point_delta, ".17g"),
            "lower_95": format(result.lower_95, ".17g"),
            "upper_95": format(result.upper_95, ".17g"),
            "accepted_replicates": result.accepted_replicates,
            "attempts": attempts,
            "lower_bound_positive": "true" if result.lower_95 > 0 else "false",
        }
        for result in bootstrap
    ]
    endpoint_rows: list[dict[str, object]] = []
    endpoint_contexts = sorted({endpoint for endpoint, _repeat in aggregate[MAPLIGHT]})
    for endpoint in endpoint_contexts:
        map_values = [
            math.fsum(aggregate[MAPLIGHT][(endpoint, repeat)].values())
            / len(aggregate[MAPLIGHT][(endpoint, repeat)])
            for repeat in range(3)
            if (endpoint, repeat) in aggregate[MAPLIGHT]
        ]
        median_values = [
            math.fsum(aggregate[SYSTEMS[0]][(endpoint, repeat)].values())
            / len(aggregate[SYSTEMS[0]][(endpoint, repeat)])
            for repeat in range(3)
            if (endpoint, repeat) in aggregate[SYSTEMS[0]]
        ]
        map_mae, median_mae = (
            math.fsum(map_values) / len(map_values),
            math.fsum(median_values) / len(median_values),
        )
        endpoint_rows.append(
            {
                "endpoint": endpoint,
                "maplight_component_macro_mae": format(map_mae, ".17g"),
                "median_component_macro_mae": format(median_mae, ".17g"),
                "maplight_minus_median": format(map_mae - median_mae, ".17g"),
                "passes_loss_cap": "true" if map_mae - median_mae <= 0.05 else "false",
            }
        )
    influence_rows: list[dict[str, object]] = []
    for comparison, control in COMPARISONS:
        components = sorted(
            {component for cell in aggregate[control].values() for component in cell}
        )

        def normalized(component: str, bound_control: str = control) -> float:
            return (
                math.fsum(
                    (
                        aggregate[bound_control][context].get(component, 0)
                        - aggregate[MAPLIGHT][context].get(component, 0)
                    )
                    / len(aggregate[MAPLIGHT][context])
                    for context in sorted(aggregate[MAPLIGHT])
                )
                / 12
            )

        ranked = sorted(
            components, key=lambda component: (-abs(normalized(component)), component)
        )[:10]
        _require(len(ranked) == 10 or synthetic, "top-ten influence support differs")
        for rank_index, component in enumerate(ranked, 1):
            contribution = (
                math.fsum(
                    (
                        aggregate[control][context].get(component, 0)
                        - aggregate[MAPLIGHT][context].get(component, 0)
                    )
                    / len(aggregate[MAPLIGHT][context])
                    for context in sorted(aggregate[MAPLIGHT])
                )
                / 12
            )
            loo = []
            for aggregate_context in sorted(aggregate[MAPLIGHT]):
                control_values = [
                    value
                    for name, value in aggregate[control][aggregate_context].items()
                    if name != component
                ]
                map_values = [
                    value
                    for name, value in aggregate[MAPLIGHT][aggregate_context].items()
                    if name != component
                ]
                _require(
                    bool(control_values and map_values),
                    "influence LOO support differs",
                )
                loo.append(
                    math.fsum(control_values) / len(control_values)
                    - math.fsum(map_values) / len(map_values)
                )
            loo_delta = math.fsum(loo) / 12
            influence_rows.append(
                {
                    "comparison_id": comparison,
                    "rank": rank_index,
                    "component_id": component,
                    "absolute_contribution": format(abs(contribution), ".17g"),
                    "loo_point_delta": format(loo_delta, ".17g"),
                    "direction_preserved": "true" if loo_delta > 0 else "false",
                }
            )
    median_fold = int(
        math.fsum(
            math.fsum(
                fold_macros[SYSTEMS[0]].get((repeat, outer, endpoint), 0)
                - fold_macros[MAPLIGHT].get((repeat, outer, endpoint), 0)
                for endpoint in sorted(ENDPOINTS)
            )
            / len(ENDPOINTS)
            > 0
            for repeat in range(3)
            for outer in range(5)
        )
    )
    one_nn_fold = int(
        math.fsum(
            math.fsum(
                fold_macros[SYSTEMS[3]].get((repeat, outer, endpoint), 0)
                - fold_macros[MAPLIGHT].get((repeat, outer, endpoint), 0)
                for endpoint in sorted(ENDPOINTS)
            )
            / len(ENDPOINTS)
            > 0
            for repeat in range(3)
            for outer in range(5)
        )
    )
    criteria = {
        "morgan_lower_positive": bootstrap[0].lower_95 > 0,
        "median_lower_positive": bootstrap[1].lower_95 > 0,
        "one_nn_lower_positive": bootstrap[2].lower_95 > 0,
        "median_positive_fold_cells": median_fold,
        "one_nn_positive_fold_cells": one_nn_fold,
        "endpoint_loss_pass": all(
            row["passes_loss_cap"] == "true" for row in endpoint_rows
        ),
        "influence_pass": all(
            row["direction_preserved"] == "true" for row in influence_rows
        ),
        "outer_predictions_complete": True,
    }
    passed = all(
        (
            criteria["morgan_lower_positive"],
            criteria["median_lower_positive"],
            criteria["one_nn_lower_positive"],
            median_fold >= 12,
            one_nn_fold >= 12,
            criteria["endpoint_loss_pass"],
            criteria["influence_pass"],
        )
    )
    assessment = {
        "schema_version": "cypshift.openadmet_cyp_2026.r3b_outer_assessment.v1",
        "contract_sha256": "",
        "outer_freeze_manifest_sha256": "",
        "sealed_outer_truth_manifest_sha256": "",
        "cell_metrics_sha256": "",
        "bootstrap_summary_sha256": "",
        "endpoint_loss_checks_sha256": "",
        "influence_checks_sha256": "",
        "predesignated_system_id": MAPLIGHT,
        "support_pass": True,
        "criteria": criteria,
        "counts": {
            "cell_metric_rows": len(cell_rows),
            "bootstrap_summary_rows": len(boot_rows),
            "endpoint_loss_rows": len(endpoint_rows),
            "influence_rows": len(influence_rows),
            "accepted_replicates": 2000,
            "attempts": attempts,
            "positive_median_fold_cells": median_fold,
            "positive_one_nn_fold_cells": one_nn_fold,
        },
        "outcome": "PASS" if passed else "NO_ADVANTAGE",
        "accounting": {},
        "authority": {},
    }
    artifacts = {
        "global_cell_metrics.csv": _csv_bytes(CELL_COLS, cell_rows),
        "global_bootstrap_summary.csv": _csv_bytes(BOOT_COLS, boot_rows),
        "global_endpoint_loss_checks.csv": _csv_bytes(
            (
                "endpoint",
                "maplight_component_macro_mae",
                "median_component_macro_mae",
                "maplight_minus_median",
                "passes_loss_cap",
            ),
            endpoint_rows,
        ),
        "global_influence_checks.csv": _csv_bytes(
            (
                "comparison_id",
                "rank",
                "component_id",
                "absolute_contribution",
                "loo_point_delta",
                "direction_preserved",
            ),
            influence_rows,
        ),
    }
    return assessment, artifacts, ("PASS" if passed else "NO_ADVANTAGE")


def _q90_completion(
    outer: Sequence[Mapping[str, str]],
    inner: Sequence[Mapping[str, str]],
    outer_truth: Mapping[tuple[str, ...], Mapping[str, str]],
    inner_truth: Mapping[tuple[str, ...], Mapping[str, str]],
    outer_csv_sha: str,
) -> tuple[dict[str, bytes], dict[str, int]]:
    residuals: dict[tuple[str, int, int], list[tuple[str, str, float]]] = defaultdict(
        list
    )
    seen: set[tuple[str, ...]] = set()
    for row in inner:
        _require(row["system_id"] == MAPLIGHT, "inner system differs")
        key = (
            row["molecule_id"],
            row["endpoint"],
            row["repeat"],
            row["outer_fold"],
            row["inner_fold"],
        )
        _require(
            key not in seen and key in inner_truth, "inner residual identity differs"
        )
        seen.add(key)
        truth = inner_truth[key]
        _require(
            row["component_id"] == truth["component_id"], "inner component differs"
        )
        if _eligible(truth):
            residual = abs(float(row["prediction"]) - float(truth["point"]))
            _require(math.isfinite(residual), "inner residual is nonfinite")
            residuals[
                (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
            ].append((truth["component_id"], row["molecule_id"], residual))
    expected_eligible = {key for key, truth in inner_truth.items() if _eligible(truth)}
    observed_eligible = {key for key in seen if _eligible(inner_truth[key])}
    _require(
        seen == set(inner_truth),
        "inner residual population identities are not exhaustive",
    )
    inner_partitions: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for molecule, endpoint, repeat, outer_fold, inner_fold in seen:
        inner_partitions[(molecule, endpoint, repeat, outer_fold)].add(inner_fold)
    _require(
        set(inner_partitions)
        == {
            (truth_key[0], truth_key[1], truth_key[2], truth_key[3])
            for truth_key in inner_truth
        },
        "inner completion keys differ",
    )
    _require(
        all(len(partition) == 1 for partition in inner_partitions.values()),
        "inner-fold partition differs",
    )
    for endpoint in ENDPOINTS:
        for context_repeat in range(3):
            for context_outer in range(5):
                context_folds = {
                    next(iter(partition))
                    for base, partition in inner_partitions.items()
                    if base[1:] == (endpoint, str(context_repeat), str(context_outer))
                }
                _require(
                    context_folds == {"0", "1", "2", "3"},
                    "inner-fold context partition differs",
                )
    inner_components: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for truth_key, truth in inner_truth.items():
        inner_components[truth_key[:4]].add(truth["component_id"])
    _require(
        all(len(components) == 1 for components in inner_components.values()),
        "inner component identities differ",
    )
    _require(
        observed_eligible == expected_eligible, "inner residual population differs"
    )
    expected_contexts = {
        (endpoint, repeat, outer_fold)
        for endpoint in ENDPOINTS
        for repeat in range(3)
        for outer_fold in range(5)
    }
    _require(set(residuals) == expected_contexts, "q90 context set differs")
    q90: dict[tuple[str, int, int], float] = {}
    q_rows: list[dict[str, object]] = []
    outer_map: dict[tuple[str, int, int], list[Mapping[str, str]]] = defaultdict(list)
    for row in outer:
        if row["system_id"] == MAPLIGHT:
            outer_map[
                (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
            ].append(row)
    outer_base_keys = {
        (row["molecule_id"], row["endpoint"], row["repeat"], row["outer_fold"])
        for row in outer
        if row["system_id"] == MAPLIGHT
    }
    _require(outer_base_keys == set(outer_truth), "outer completion identities differ")
    for context in sorted(expected_contexts):
        values = residuals[context]
        grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for component, molecule, residual in values:
            grouped[component].append((molecule, residual))
        _require(bool(grouped), "empty q90 component population")
        ordered = sorted(
            (residual, component, molecule)
            for component, entries in grouped.items()
            for molecule, residual in entries
        )
        cumulative_terms: list[float] = []
        chosen = ordered[-1][0]
        for residual, component, _molecule in ordered:
            cumulative_terms.append(1.0 / len(grouped) / len(grouped[component]))
            cumulative = math.fsum(cumulative_terms)
            if cumulative >= 0.90:
                chosen = residual
                break
        q90[context] = chosen
        eligible = [
            row
            for row in outer_map[context]
            if _eligible(
                outer_truth[
                    (
                        row["molecule_id"],
                        row["endpoint"],
                        row["repeat"],
                        row["outer_fold"],
                    )
                ]
            )
        ]
        by_component: dict[str, list[tuple[str, bool]]] = defaultdict(list)
        for row in eligible:
            truth = outer_truth[
                (row["molecule_id"], row["endpoint"], row["repeat"], row["outer_fold"])
            ]
            by_component[truth["component_id"]].append(
                (
                    row["molecule_id"],
                    abs(float(row["prediction"]) - float(truth["point"])) <= chosen,
                )
            )
        coverage = (
            math.fsum(
                math.fsum(flag for _molecule, flag in sorted(by_component[component]))
                / len(by_component[component])
                for component in sorted(by_component)
            )
            / len(by_component)
            if by_component
            else 0.0
        )
        q_rows.append(
            {
                "endpoint": context[0],
                "repeat": context[1],
                "outer_fold": context[2],
                "system_id": MAPLIGHT,
                "q90": format(chosen, ".17g"),
                "residual_molecules": len(values),
                "residual_components": len(grouped),
                "outer_molecules": len(eligible),
                "outer_components": len(by_component),
                "inclusive_coverage": format(coverage, ".17g"),
                "status": "UNCERTAINTY_WITHIN_FROZEN_RANGE"
                if 0.80 <= coverage <= 0.98
                else "UNCERTAINTY_DIAGNOSTIC_ONLY",
            }
        )
    outer_complete: list[dict[str, object]] = []
    for row in sorted(
        inner,
        key=lambda item: (
            item["endpoint"],
            int(item["repeat"]),
            int(item["outer_fold"]),
            item["molecule_id"],
            item["component_id"],
            int(item["inner_fold"]),
        ),
    ):
        truth = inner_truth[
            (
                row["molecule_id"],
                row["endpoint"],
                row["repeat"],
                row["outer_fold"],
                row["inner_fold"],
            )
        ]
        context = (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
        if _eligible(truth):
            state, value, diagnostic, source = "measured_point", truth["point"], "", ""
        else:
            state, value, diagnostic, source = (
                "global_oof_completed",
                row["prediction"],
                format(q90[context], ".17g"),
                row["model_id"],
            )
        outer_complete.append(
            {
                "molecule_id": row["molecule_id"],
                "endpoint": row["endpoint"],
                "component_id": truth["component_id"],
                "repeat": row["repeat"],
                "outer_fold": row["outer_fold"],
                "completion_state": state,
                "value": value,
                "diagnostic_q90": diagnostic,
                "source_model_id": source,
            }
        )
    grouped_outer: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in outer:
        if row["system_id"] == MAPLIGHT:
            grouped_outer[(row["molecule_id"], row["endpoint"])].append(row)
    final: list[dict[str, object]] = []
    for (molecule, endpoint), predictions in sorted(
        grouped_outer.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        _require(len(predictions) == 3, "final repeat population differs")
        _require(
            {int(row["repeat"]) for row in predictions} == {0, 1, 2},
            "final context population differs",
        )
        ordered_predictions = sorted(predictions, key=lambda item: int(item["repeat"]))
        truths = [
            outer_truth[
                (row["molecule_id"], row["endpoint"], row["repeat"], row["outer_fold"])
            ]
            for row in ordered_predictions
        ]
        _require(
            len({truth["component_id"] for truth in truths}) == 1,
            "final component population differs",
        )
        contexts = [
            (row["endpoint"], int(row["repeat"]), int(row["outer_fold"]))
            for row in ordered_predictions
        ]
        _require(
            all(context in q90 for context in contexts), "final q90 context differs"
        )
        measured = next((truth for truth in truths if _eligible(truth)), None)
        if measured is not None:
            state, value, diagnostic, source = (
                "measured_point",
                measured["point"],
                "",
                "",
            )
        else:
            state, value, diagnostic = (
                "global_oof_completed",
                format(
                    math.fsum(float(row["prediction"]) for row in ordered_predictions)
                    / 3,
                    ".17g",
                ),
                format(max(q90[context] for context in contexts), ".17g"),
            )
            source = _sha(f"{outer_csv_sha}|{molecule}|{endpoint}".encode())
        final.append(
            {
                "molecule_id": molecule,
                "endpoint": endpoint,
                "component_id": truths[0]["component_id"],
                "completion_state": state,
                "value": value,
                "diagnostic_q90": diagnostic,
                "source_prediction_sha256": source,
            }
        )
    counts = {
        "outer_rows": len(outer_complete),
        "final_rows": len(final),
        "measured_point": int(
            math.fsum(
                row["completion_state"] == "measured_point"
                for row in outer_complete + final
            )
        ),
        "global_oof_completed": int(
            math.fsum(
                row["completion_state"] == "global_oof_completed"
                for row in outer_complete + final
            )
        ),
        "unavailable": 0,
    }
    return {
        "global_uncertainty_calibration.csv": _csv_bytes(Q90_COLS, q_rows),
        "parent_state_completion_outer_training.csv": _csv_bytes(
            OUTER_COMPLETE_COLS, outer_complete
        ),
        "parent_state_completion_final.csv": _csv_bytes(FINAL_COMPLETE_COLS, final),
    }, counts
