"""Exact v5 preflight receipt validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from r3b_scoring_artifacts import _authority, _receipt, _require

_FAILURE_ORDER = (
    "OUTER_COMPONENT_SUPPORT",
    "OUTER_TRAINING_EMPTY",
    "INNER_TRAINING_EMPTY",
    "Q90_RESIDUAL_ELIGIBILITY_EMPTY",
)


def _ordered_contexts() -> list[tuple[str, int, int]]:
    return [
        (endpoint, repeat, outer_fold)
        for endpoint in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
        for repeat in range(3)
        for outer_fold in range(5)
    ]


def _integer(value: object, label: str) -> int:
    _require(type(value) is int and value >= 0, f"{label} differs")
    return cast(int, value)


def _validate_preflight(
    preflight: Mapping[str, Any],
    contract: Mapping[str, Any],
    contract_sha: str,
    synthetic: bool,
) -> None:
    fields = {
        "schema_version",
        "contract_sha256",
        "model_public_manifest_sha256",
        "private_projection_audit_sha256",
        "checks",
        "passed",
        "failure_reasons",
        "accounting",
        "authority",
    }
    _require(set(preflight) == fields, "preflight fields differ")
    _require(
        preflight["schema_version"] == "cypshift.openadmet_cyp_2026.r3b_preflight.v5"
        and preflight["contract_sha256"] == contract_sha
        and type(preflight["passed"]) is bool,
        "preflight receipt differs",
    )
    _receipt(preflight["model_public_manifest_sha256"], "preflight model", synthetic)
    _receipt(preflight["private_projection_audit_sha256"], "preflight audit", synthetic)
    checks = preflight["checks"]
    _require(isinstance(checks, Mapping), "preflight checks differ")
    check_map = cast(Mapping[str, Any], checks)
    _require(
        set(check_map)
        == {
            "outer_score_support_cells",
            "outer_training_populations",
            "inner_training_populations",
            "q90_residual_eligibility_populations",
        },
        "preflight check fields differ",
    )
    for key, count in (
        ("outer_score_support_cells", 60),
        ("outer_training_populations", 60),
        ("inner_training_populations", 240),
        ("q90_residual_eligibility_populations", 60),
    ):
        records = check_map[key]
        _require(
            isinstance(records, list) and len(records) == count,
            "preflight check cardinality differs",
        )
        expected_fields = (
            {
                "endpoint",
                "repeat",
                "outer_fold",
                "component_count",
                "minimum_components",
                "passes",
            }
            if key == "outer_score_support_cells"
            else {
                "endpoint",
                "repeat",
                "outer_fold",
                "eligible_residuals",
                "minimum_eligible_targets",
                "passes",
            }
            if key == "q90_residual_eligibility_populations"
            else {
                "stage",
                "endpoint",
                "repeat",
                "outer_fold",
                "inner_fold",
                "eligible_targets",
                "minimum_eligible_targets",
                "passes",
            }
        )
        for record in cast(list[object], records):
            _require(isinstance(record, Mapping), "preflight record differs")
            item = cast(Mapping[str, Any], record)
            _require(
                set(item) == expected_fields and type(item["passes"]) is bool,
                "preflight record fields differ",
            )
        expected_contexts = _ordered_contexts()
        expected_grid: list[tuple[str, int, int, int | str]]
        if key == "inner_training_populations":
            expected_grid = [
                (*context, inner) for context in expected_contexts for inner in range(4)
            ]
        else:
            expected_grid = [(*context, "") for context in expected_contexts]
        for record, expected in zip(
            cast(list[object], records), expected_grid, strict=True
        ):
            item = cast(Mapping[str, Any], record)
            endpoint, repeat, outer_fold, inner_fold = expected
            _require(
                item["endpoint"] == endpoint
                and item["repeat"] == repeat
                and item["outer_fold"] == outer_fold,
                "preflight context order differs",
            )
            if key == "inner_training_populations":
                _require(
                    item["stage"] == "inner" and item["inner_fold"] == inner_fold,
                    "preflight inner context differs",
                )
            elif key == "outer_training_populations":
                _require(
                    item["stage"] == "outer" and item["inner_fold"] == "",
                    "preflight outer context differs",
                )
            count_field = (
                "component_count"
                if key == "outer_score_support_cells"
                else "eligible_residuals"
                if key == "q90_residual_eligibility_populations"
                else "eligible_targets"
            )
            minimum_field = (
                "minimum_components"
                if key == "outer_score_support_cells"
                else "minimum_eligible_targets"
            )
            count_value = _integer(item[count_field], count_field)
            minimum = _integer(item[minimum_field], minimum_field)
            expected_minimum = 10 if key == "outer_score_support_cells" else 1
            _require(minimum == expected_minimum, f"{minimum_field} differs")
            _require(
                item["passes"] == (count_value >= minimum),
                "preflight pass arithmetic differs",
            )
    reasons = preflight["failure_reasons"]
    _require(isinstance(reasons, list), "preflight failures differ")
    pass_values: list[bool] = []
    for records in check_map.values():
        pass_values.extend(
            bool(cast(Mapping[str, Any], record)["passes"])
            for record in cast(list[object], records)
        )
    failed_categories = [
        reason
        for reason, records in zip(
            _FAILURE_ORDER,
            (
                check_map["outer_score_support_cells"],
                check_map["outer_training_populations"],
                check_map["inner_training_populations"],
                check_map["q90_residual_eligibility_populations"],
            ),
            strict=True,
        )
        if not all(
            cast(Mapping[str, Any], record)["passes"]
            for record in cast(list[object], records)
        )
    ]
    _require(reasons == failed_categories, "preflight failure reasons differ")
    _require(
        preflight["passed"] is (not failed_categories),
        "preflight pass arithmetic differs",
    )
    _require(
        preflight["passed"] == all(pass_values), "preflight pass arithmetic differs"
    )
    accounting = preflight["accounting"]
    _require(isinstance(accounting, Mapping), "preflight accounting differs")
    accounting_map = cast(Mapping[str, Any], accounting)
    accounting_fields = {
        "preflight_target_files_opened",
        "outer_model_target_files_opened",
        "inner_model_target_files_opened",
        "sealed_truth_files_opened",
        "outer_model_fits",
        "inner_model_fits",
        "prediction_rows",
        "provisional_metric_rows",
        "tdi_files_opened",
        "blinded_test_files_opened",
        "episode_or_anchor_files_opened",
        "official_metric_calls",
        "submission_rows_opened",
        "leaderboard_submissions",
        "transductive_operations",
        "gpu_fits",
    }
    _require(
        set(accounting_map) == accounting_fields, "preflight accounting fields differ"
    )
    _require(
        all(type(value) is int and value >= 0 for value in accounting_map.values()),
        "preflight accounting values differ",
    )
    _require(
        accounting_map["preflight_target_files_opened"] == 300
        and all(
            value == 0
            for key, value in accounting_map.items()
            if key != "preflight_target_files_opened"
        ),
        "preflight accounting values differ",
    )
    _require(
        preflight["authority"] == _authority(contract, "INHERITED_ONLY"),
        "preflight authority differs",
    )
