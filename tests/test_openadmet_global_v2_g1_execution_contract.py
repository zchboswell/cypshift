from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_g1_execution_contract.json"
CLAIM_PATH = BENCHMARK / "global_v2_g1_execution_claim.json"
CONTRACT_SHA256 = "c75cb01e3d4fec1595c17d5b0f0bd4369c8424ef7dbf4f8fd1fe2112fd20b869"
CLAIM_SHA256 = "1c9f34388290c3992ae9346fbb9b4a71602d3d12b44a619f425ac93dec946154"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g1_execution_contract_and_claim_have_exact_identity() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert _sha256(CLAIM_PATH) == CLAIM_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_g1_execution_contract.v1"
    )
    assert contract["gate"] == "G2_3C_EXP_G1_EXECUTION_CONTRACT_FROZEN"
    assert contract["status"] == (
        "contract_and_unconsumed_claim_only_no_official_execution_yet"
    )
    assert contract["base_commit"] == "80313c8c8c25c5ff95f0f33293d28cd0c3e70e05"
    assert claim["status"] == "G2_3C_CLAIM_UNCONSUMED"
    assert claim["contract_sha256"] == CONTRACT_SHA256
    assert claim["base_commit"] == contract["base_commit"]
    assert claim["claim_id"] == contract["claim_contract"]["claim_id"]
    assert contract["claim_contract"]["claim_path"] == CLAIM_PATH.name


def test_g1_execution_contract_binds_every_parent_and_accepted_source() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha256(path) == parent["sha256"]

    implementation = contract["accepted_implementation"]
    source_pairs = (
        ("g1_runner_path", "g1_runner_sha256"),
        ("g1_synthetic_driver_path", "g1_synthetic_driver_sha256"),
        ("g1_focused_tests_path", "g1_focused_tests_sha256"),
        ("accepted_maplight_runner_path", "accepted_maplight_runner_sha256"),
        ("tutorial_metric_source_path", "tutorial_metric_source_sha256"),
        ("research_lock_path", "research_lock_sha256"),
    )
    for path_key, sha_key in source_pairs:
        assert _sha256(ROOT / implementation[path_key]) == implementation[sha_key]
    assert claim["g1_runner_source_sha256"] == implementation["g1_runner_sha256"]
    assert claim["g1_synthetic_driver_source_sha256"] == implementation[
        "g1_synthetic_driver_sha256"
    ]
    assert claim["g1_focused_tests_sha256"] == implementation[
        "g1_focused_tests_sha256"
    ]


def test_g1_claim_is_single_use_and_cannot_yet_be_consumed() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    future_fields = contract["claim_contract"]["future_receipt_fields"]
    assert claim["maximum_consumptions"] == 1
    assert contract["claim_contract"]["maximum_consumptions"] == 1
    assert all(claim[name] is None for name in future_fields)
    assert "Atomic no-replace creation" in contract["claim_contract"]["consumption"]
    assert "remains consumed" in contract["claim_contract"]["consumption"]
    assert "two fresh roots byte-identical" in contract["claim_contract"][
        "precondition"
    ]


def test_g1_official_receipts_are_exact_without_source_access() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    inputs = contract["official_inputs"]
    receipts = claim["official_input_receipts"]
    expected = {
        "dataset_revision": inputs["dataset_revision"],
        **{
            name: value
            for name, value in inputs.items()
            if name.endswith("_sha256")
        },
    }
    assert receipts == expected
    assert len(receipts["dataset_revision"]) == 40
    assert set(receipts["dataset_revision"]) <= set("0123456789abcdef")
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for name, value in receipts.items()
        if name != "dataset_revision"
    )
    assert inputs["attempt_root"].endswith("g2-3c-g1-development-attempt-1")
    assert "does not parse" in inputs["read_boundary"]


def test_g1_execution_budget_and_selection_are_exact() -> None:
    contract = _load(CONTRACT_PATH)
    execution = contract["execution"]
    assert execution["attempts"] == 1
    assert execution["replays"] == 1
    assert execution["exact_configurations"] == 12
    assert execution["model_seeds"] == [20260824, 20260825, 20260826]
    assert execution["inner_contexts"] == 3 * 5 * 4 * 4
    assert execution["inner_configuration_seed_fits"] == 3 * 5 * 4 * 4 * 12 * 3
    assert execution["outer_endpoint_cells"] == 3 * 5 * 4
    assert execution["selected_outer_seed_fits"] == 3 * 5 * 4 * 3
    assert execution["exact_new_catboost_fits"] == 8820
    assert execution["baseline_refits"] == 0
    assert execution["expected_inner_raw_prediction_rows"] == 6_753_024
    assert execution["expected_inner_seed_averaged_rows"] == 2_251_008
    assert execution["expected_complete_selection_projection_rows"] == 562_752
    assert execution["expected_outer_raw_prediction_rows"] == 140_688
    assert execution["expected_outer_seed_averaged_rows"] == 46_896
    assert not any(execution[name] for name in ("retry", "resume", "move", "overwrite"))


def test_g1_acceptance_is_frozen_and_conjunctive() -> None:
    acceptance = _load(CONTRACT_PATH)["development_acceptance"]
    assert acceptance["minimum_relative_primary_improvement"] == 0.03
    assert acceptance["minimum_absolute_component_mae_improvement"] == 0.015
    assert acceptance["paired_component_mae_upper_95_below_zero"]
    assert acceptance["minimum_favorable_outer_cells"] == 8
    assert acceptance["total_outer_cells"] == 15
    assert acceptance["maximum_endpoint_mae_degradation"] == 0.015
    assert acceptance["bootstrap_seed"] == 20260827
    assert acceptance["accepted_bootstrap_replicates"] == 2000
    assert acceptance["maximum_bootstrap_attempts"] == 20000
    assert "All five gates are conjunctive" in acceptance["logic"]
    assert "permanently stop EXP-G1" in acceptance["clean_rejection"]


def test_g1_runtime_resources_and_terminals_fail_closed() -> None:
    contract = _load(CONTRACT_PATH)
    resources = contract["runtime_and_resources"]
    assert resources["python"] == "3.10.13"
    assert resources["catboost"] == "1.2.1"
    assert resources["thread_count_per_fit"] == 16
    assert resources["maximum_concurrent_catboost_fits"] == 1
    assert resources["maximum_cpu_core_hours"] == 1200
    assert resources["maximum_wall_hours"] == 120
    assert resources["maximum_restricted_storage_gb"] == 40
    terminal = contract["terminal_contract"]
    assert terminal["statuses"] == [
        "G2_3_G1_FAILED",
        "G2_3_G1_UNDERPOWERED",
        "G2_3_G1_REJECTED",
        "G2_3_G1_ACCEPTED",
    ]
    assert len(terminal["required_aggregate_outputs"]) == 6
    assert len(terminal["private_row_level_outputs"]) == 3
    assert "Cleanup failure" in terminal["cleanup"]
    assert "no retry, resume, move, overwrite" in terminal["failure"]


def test_g1_contract_freeze_has_zero_authority_and_operations() -> None:
    contract = _load(CONTRACT_PATH)
    assert all(value == 0 for value in contract["current_milestone_accounting"].values())
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert authority["tracked_unconsumed_claim"]
    assert not any(
        value
        for name, value in authority.items()
        if name not in {"contract_and_static_tests", "tracked_unconsumed_claim"}
    )
    assert contract["next_gate"].startswith(
        "Implement only the additive G2-3C official capability compiler"
    )
    assert "Do not consume the claim or open development inputs" in contract[
        "next_gate"
    ]
