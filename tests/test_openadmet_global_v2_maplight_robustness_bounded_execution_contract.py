from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = (
    BENCHMARK / "global_v2_maplight_robustness_bounded_execution_contract.json"
)
PARENT_PATH = BENCHMARK / "global_v2_maplight_robustness_contract.json"
REJECTION_PATH = (
    BENCHMARK / "global_v2_maplight_robustness_synthetic_rejection.json"
)
REPRODUCTION_PATH = BENCHMARK / "global_v2_maplight_official_reproduction.json"
EXPECTED_CONTRACT_SHA256 = (
    "55fafa1d9806ba3221c26b8cd71d077ad61a0f485e51defbae21cbd4b5806527"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_identity_and_base_are_frozen() -> None:
    contract = _load(CONTRACT_PATH)
    assert _sha256(CONTRACT_PATH) == EXPECTED_CONTRACT_SHA256
    assert contract["schema_version"].endswith(
        "global_v2_maplight_robustness_bounded_execution_contract.v1"
    )
    assert (
        contract["gate"]
        == "G2_7C_MAPLIGHT_ROBUSTNESS_BOUNDED_EXECUTION_CONTRACT_FROZEN"
    )
    assert contract["base_commit"] == (
        "2aa9eda2cb41a2ef1c22dbad3531b734724caa44"
    )
    assert contract["status"].startswith("contract_only")


def test_parents_and_accepted_primitives_are_exact() -> None:
    contract = _load(CONTRACT_PATH)
    parents = contract["parents"]
    paths = {
        "maplight_robustness_contract": PARENT_PATH,
        "maplight_robustness_synthetic_rejection": REJECTION_PATH,
        "maplight_official_reproduction": REPRODUCTION_PATH,
        "maplight_execution_contract": (
            BENCHMARK / "global_v2_maplight_execution_contract.json"
        ),
        "maplight_execution_synthetic_acceptance": (
            BENCHMARK / "global_v2_maplight_execution_synthetic_acceptance.json"
        ),
    }
    for key, path in paths.items():
        assert parents[key]["sha256"] == _sha256(path)

    primitives = contract["accepted_runtime_primitives"]
    for key in ("runner", "official_compiler", "official_wrapper", "research_uv_lock"):
        item = primitives[key]
        assert item["sha256"] == _sha256(ROOT / item["path"])
    assert primitives["runtime"] == {
        "platform": "Linux x86_64 CPU",
        "python": "3.10.13",
        "numpy": "1.25.2",
        "rdkit": "2023.3.3",
        "catboost": "1.2.1",
        "thread_count": 16,
        "maximum_concurrent_fits": 1,
        "gpu_hours": 0,
    }


def test_rejected_g2_7b_is_bound_only_as_non_reusable_history() -> None:
    contract = _load(CONTRACT_PATH)
    rejection = _load(REJECTION_PATH)
    boundary = contract["rejected_g2_7b_non_reuse"]
    assert rejection["status"] == "G2_7B_MAPLIGHT_ROBUSTNESS_SYNTHETIC_REJECTED"
    assert boundary["runner_sha256"] == rejection["implementation_receipts"][
        "runner_source_sha256"
    ]
    assert boundary["driver_sha256"] == rejection["implementation_receipts"][
        "driver_source_sha256"
    ]
    assert boundary["formal_attempts_remaining"] == 0
    assert not boundary["resource_acceptance_authority"]
    assert not boundary["mechanical_acceptance_authority"]
    assert all(
        word in boundary["rule"]
        for word in ("import", "copy", "execute", "patch", "claim")
    )


def test_scientific_workload_is_an_exact_d_122_inheritance() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)
    inherited = contract["exact_scientific_inheritance"]
    assert inherited["default_candidate"] == parent["fixed_maplight"]["candidate_id"]
    assert inherited["drop_one_candidates"] == [
        item["candidate_id"] for item in parent["drop_one_candidates"]
    ]
    assert inherited["seed_perturbation_values"] == parent["stage_a_selection"][
        "seed_perturbation_values"
    ]
    assert inherited["group_perturbations"] == [
        item["id"]
        for item in parent["stage_b_selected_robustness"]["group_perturbations"]
    ]
    workload = parent["workload"]
    assert inherited["fits"] == {
        "stage_a": workload["stage_a_fits"],
        "stage_b": workload["stage_b_fits"],
        "stage_c_if_deletion_selected": workload["stage_c_conditional_fits"],
        "minimum_total": workload["minimum_new_fits"],
        "maximum_total": workload["maximum_new_fits"],
        "baseline_refits": workload["baseline_refits"],
        "inner_fits": workload["inner_model_fits"],
    }
    assert inherited["predictions"]["minimum_total"] == workload[
        "minimum_new_prediction_rows"
    ]
    assert inherited["predictions"]["maximum_total"] == workload[
        "maximum_new_prediction_rows"
    ]
    assert inherited["selection_tokens"] == 1
    assert inherited["runner_ups"] == inherited["deployable_clips"] == 0


def test_historical_full_feature_resource_context_is_recomputed_exactly() -> None:
    contract = _load(CONTRACT_PATH)
    reproduction = _load(REPRODUCTION_PATH)
    context = contract["historical_feasibility_context"]
    resource = reproduction["resource"]
    fits = (
        reproduction["accounting"]["official_model_fits_per_replay"]
        * reproduction["determinism"]["replays_completed"]
    )
    ratio = contract["exact_scientific_inheritance"]["fits"]["maximum_total"] / fits
    assert context["feature_columns"] == 2563
    assert context["fits_observed"] == fits == 600
    assert context["wall_seconds_observed"] == resource["wall_seconds"]
    assert (
        context["cpu_core_hours_upper_bound_observed"]
        == resource["cpu_core_hours_upper_bound"]
    )
    projected = context["maximum_branch_context"]
    assert projected["fit_ratio"] == pytest.approx(ratio)
    assert projected["wall_hours_linear_context"] == pytest.approx(
        resource["wall_seconds"] / 3600 * ratio
    )
    assert projected["cpu_core_hours_linear_upper_context"] == pytest.approx(
        resource["cpu_core_hours_upper_bound"] * ratio
    )
    assert projected["restricted_storage_gb_linear_context"] == pytest.approx(
        resource["peak_restricted_storage_bytes"] / 1e9 * ratio
    )


def test_historical_context_cannot_be_an_acceptance_gate() -> None:
    contract = _load(CONTRACT_PATH)
    context = contract["historical_feasibility_context"]
    interpretation = context["interpretation"].lower()
    for forbidden_meaning in (
        "not a per-fit maximum",
        "guarantee",
        "projection gate",
        "acceptance statistic",
        "optimization target",
    ):
        assert forbidden_meaning in interpretation
    assert "synthetic" not in context["source"].split("not ", maxsplit=1)[0].lower()


def test_hard_limits_preserve_the_frozen_twenty_percent_margin() -> None:
    contract = _load(CONTRACT_PATH)
    parent = _load(PARENT_PATH)
    limits = contract["cumulative_resource_envelope"]["hard_limits"]
    ceiling = parent["resource_ceiling"]
    assert limits == {
        "cpu_core_hours": ceiling["cpu_core_hours"] * 0.8,
        "wall_hours": ceiling["maximum_wall_hours"] * 0.8,
        "restricted_storage_gb": ceiling["restricted_storage_gb"] * 0.8,
        "peak_rss_gib": ceiling["peak_rss_gib"] * 0.8,
        "gpu_hours": 0,
    }
    context = contract["historical_feasibility_context"]["maximum_branch_context"]
    assert context["wall_headroom_factor_to_hard_limit"] == pytest.approx(
        limits["wall_hours"] / context["wall_hours_linear_context"]
    )
    assert context["cpu_headroom_factor_to_hard_limit"] == pytest.approx(
        limits["cpu_core_hours"] / context["cpu_core_hours_linear_upper_context"]
    )


def test_supervisor_covers_complete_descendant_work_and_every_limit() -> None:
    contract = _load(CONTRACT_PATH)
    envelope = contract["cumulative_resource_envelope"]
    supervisor = envelope["supervisor"]
    assert "before any future claim consumption" in envelope["measurement_scope"]
    assert all(
        item in envelope["measurement_scope"]
        for item in ("compiler", "model", "scorer", "bootstrap", "publisher", "cleanup")
    )
    assert supervisor["poll_interval_seconds_maximum"] == 1.0
    assert all(
        supervisor[key]
        for key in (
            "wall_deadline_enforced_during_child_fit",
            "cpu_limit_enforced_during_child_fit",
            "storage_limit_enforced_during_child_fit",
            "simultaneous_rss_limit_enforced_during_child_fit",
            "storage_and_rss_checked_before_and_after_every_stage_and_fit",
            "network_disabled",
        )
    )
    assert "every descendant" in supervisor["cpu"]
    assert "simultaneous" in supervisor["rss"]
    assert "process group" in supervisor["child_signal_policy"]
    assert "partial scientific terminal" in supervisor["child_signal_policy"]


def test_acceptance_is_conjunctive_and_unused_budget_is_inert() -> None:
    envelope = _load(CONTRACT_PATH)["cumulative_resource_envelope"]
    assert "every hard limit passes conjunctively" in envelope["acceptance_rule"]
    assert "No mean, projection, extrapolation, partial completion" in envelope[
        "acceptance_rule"
    ]
    for forbidden_use in (
        "retry",
        "resume",
        "smaller battery",
        "extra candidate",
        "optimization",
        "concurrency",
    ):
        assert forbidden_use in envelope["budget_rule"]


def test_future_implementation_is_no_fit_and_receipt_gated() -> None:
    gate = _load(CONTRACT_PATH)["future_implementation_gate"]
    assert len(gate["required_new_components"]) == 5
    assert "two opposite-order official-shaped roots" in gate["no_fit_acceptance"]
    assert "Run no real CatBoost fit" in gate["no_fit_acceptance"]
    assert "resource projection" in gate["no_fit_acceptance"]
    assert "development metric" in gate["no_fit_acceptance"]
    assert all(value is None for value in gate["current_implementation_receipts"].values())
    assert gate["bounded_api_smokes"].startswith("At most two optional")
    assert "zero resource or model-quality authority" in gate["bounded_api_smokes"]


def test_future_claim_is_separate_single_use_and_currently_forbidden() -> None:
    claim = _load(CONTRACT_PATH)["future_claim_boundary"]
    assert claim["claims_created_now"] == 0
    assert claim["maximum_future_claims"] == claim["maximum_consumptions"] == 1
    assert claim["attempts"] == 1
    assert not any(
        claim[key]
        for key in (
            "retry",
            "resume",
            "move",
            "overwrite",
            "replacement",
            "claim_creation_authorized_by_this_contract",
            "claim_consumption_authorized_by_this_contract",
        )
    )
    assert "every future implementation receipt is non-null" in claim["claim_rule"]
    assert "private-portal boundary" in claim["claim_rule"]


def test_terminal_paths_never_promote_partial_or_failed_work() -> None:
    terminal = _load(CONTRACT_PATH)["terminal_contract"]
    assert terminal["accepted"] == "G2_7_PRIMARY_CONTENDER_FROZEN"
    assert terminal["resource_aborted"] == (
        "G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED"
    )
    assert "Exactly one aggregate-only" in terminal["publication"]
    assert "no partial terminal" in terminal["publication"]
    assert "without confirmatory access" in terminal["failure_effect"]
    assert "not automatically promoted" in terminal["failure_effect"]


def test_current_milestone_has_zero_execution_and_forbidden_authority() -> None:
    contract = _load(CONTRACT_PATH)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert all(value == 0 for key, value in accounting.items() if key != "contracts_created")
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert not any(value for key, value in authority.items() if key != "contract_and_static_tests")
    text = CONTRACT_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text
    assert "do not create a claim" in contract["next_gate"].lower()
    assert "fit a scientific model" in contract["next_gate"].lower()
