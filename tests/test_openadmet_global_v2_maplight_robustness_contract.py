from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = BENCHMARK / "global_v2_maplight_robustness_contract.json"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_robustness_contract_binds_terminal_parents_and_green_main() -> None:
    contract = _read(CONTRACT)
    assert contract["gate"] == "G2_7_MAPLIGHT_ROBUSTNESS_CONTRACT_FROZEN"
    assert contract["status"] == "contract_only_no_scientific_execution_authority"
    assert contract["base_commit"] == "e7398a2c9a227bc4cdf4665499f635045aa731bb"

    parents = contract["parents"]
    for key in (
        "global_v2",
        "maplight_reproduction_contract",
        "maplight_execution_contract",
        "maplight_official_reproduction",
        "g3_terminal_failure",
        "direct_maplight_deployment",
    ):
        parent = parents[key]
        assert parent["sha256"] == _sha256(BENCHMARK / parent["path"])
    assert parents["post_main_ci"] == {
        "run_id": 32864287869,
        "head_sha": "e7398a2c9a227bc4cdf4665499f635045aa731bb",
        "conclusion": "success",
    }
    assert parents["maplight_official_reproduction"]["status"] == (
        "G2_2_MAPLIGHT_REPRODUCED"
    )
    assert parents["g3_terminal_failure"]["meaning"].startswith("EXP-G3 is closed")


def test_exact_full_maplight_and_drop_one_family_are_frozen() -> None:
    contract = _read(CONTRACT)
    assert contract["runtime"]["trusted_compiler"] == {
        "platform": "Linux x86_64 CPU",
        "python": "3.12.3",
        "rdkit": "2026.03.5",
        "root_uv_lock_sha256": _sha256(ROOT / "uv.lock"),
        "standardizer_source_sha256": _sha256(
            ROOT / "src" / "cypshift" / "chemistry.py"
        ),
    }
    assert contract["runtime"]["model"]["uv_lock_sha256"] == _sha256(
        ROOT / "research" / "maplight-fixed" / "uv.lock"
    )
    assert contract["runtime"]["model"]["catboost"] == "1.2.1"
    full = contract["fixed_maplight"]
    assert full["candidate_id"] == "G2-7-M0-FULL"
    assert full["system_id"] == "TRACE-G0-MAPL-FIXED"
    assert full["feature_columns"] == 2563
    assert [(block["id"], block["columns"]) for block in full["feature_blocks"]] == [
        ("MORGAN_COUNT", 1024),
        ("AVALON_COUNT", 1024),
        ("ERG", 315),
        ("RDKIT_DESCRIPTORS", 200),
    ]
    assert sum(block["columns"] for block in full["feature_blocks"]) == 2563
    assert full["constructor_arguments"] == {
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": 1,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
    }

    candidates = contract["drop_one_candidates"]
    assert [candidate["candidate_id"] for candidate in candidates] == [
        "G2-7-M1-DROP-MORGAN",
        "G2-7-M2-DROP-AVALON",
        "G2-7-M3-DROP-ERG",
        "G2-7-M4-DROP-DESCRIPTORS",
    ]
    block_columns = {block["id"]: block["columns"] for block in full["feature_blocks"]}
    assert all(
        candidate["feature_columns"]
        == full["feature_columns"] - block_columns[candidate["drop_block"]]
        for candidate in candidates
    )
    selection = contract["stage_a_selection"]["candidate_selection"]
    assert selection["full_is_default"] is True
    assert selection["one_selection_token"] is True
    assert selection["no_runner_up"] is True
    assert "fewer feature columns" in selection["ordering"]


def test_staged_workload_and_prediction_freezes_are_exact() -> None:
    contract = _read(CONTRACT)
    stage_a = contract["stage_a_selection"]
    stage_b = contract["stage_b_selected_robustness"]
    stage_c = contract["stage_c_conditional_selected_seed_check"]
    workload = contract["workload"]

    assert stage_a["drop_one_fits"] == 4 * 3 * 5 * 4 == 240
    assert len(stage_a["seed_perturbation_values"]) == 5
    assert stage_a["full_feature_seed_perturbation_fits"] == 5 * 3 * 5 * 4 == 300
    assert stage_a["stage_a_fits"] == 540
    assert stage_a["stage_a_prediction_rows"] == 9 * 46_896 == 422_064
    assert len(stage_b["group_perturbations"]) == 3
    assert stage_b["fits"] == 3 * 3 * 5 * 4 == 180
    assert stage_b["prediction_rows_upper_bound"] == 3 * 46_896 == 140_688
    assert stage_c["fits"] == 5 * 3 * 5 * 4 == 300
    assert stage_c["prediction_rows"] == 5 * 46_896 == 234_480

    assert workload["minimum_new_fits"] == stage_a["stage_a_fits"] + stage_b["fits"]
    assert workload["maximum_new_fits"] == (
        workload["minimum_new_fits"] + stage_c["fits"]
    )
    assert workload["minimum_new_prediction_rows"] == (
        stage_a["stage_a_prediction_rows"] + stage_b["prediction_rows_upper_bound"]
    )
    assert workload["maximum_new_prediction_rows"] == (
        workload["minimum_new_prediction_rows"] + stage_c["prediction_rows"]
    )
    assert workload["baseline_refits"] == 0
    assert workload["inner_model_fits"] == 0
    assert workload["model_binaries_retained"] == 0
    assert "before any outer validation truth" in stage_a["chronology"]
    assert "Freeze every perturbation prediction" in stage_b["chronology"]


def test_grouping_perturbations_are_conservative_and_nonselecting() -> None:
    contract = _read(CONTRACT)
    population = contract["population"]
    perturbations = contract["stage_b_selected_robustness"]["group_perturbations"]
    by_id = {item["id"]: item["rule"] for item in perturbations}

    assert "threshold 0.60" in population["primary_group_rule"]
    assert (
        "only candidate-selection and confirmatory group unit"
        in population["primary_group_rule"]
    )
    assert set(by_id) == {"THRESHOLD_0_55", "THRESHOLD_0_50", "TAUTOMER_MERGED"}
    assert "touching any confirmatory identity" in by_id["THRESHOLD_0_55"]
    assert "can never replace the primary D-032 groups" in by_id["THRESHOLD_0_50"]
    assert "changes grouping only" in by_id["TAUTOMER_MERGED"]
    assert (
        "No perturbation may move, parse, or score a confirmatory target"
        in population["confirmatory_rule"]
    )
    assert (
        "No molecule, exact duplicate"
        in contract["stage_b_selected_robustness"]["family_invariant"]
    )


def test_all_eight_robustness_families_have_fail_closed_gates() -> None:
    contract = _read(CONTRACT)
    gates = contract["robustness_acceptance"]
    assert set(gates) == {
        "seed",
        "grouping",
        "duplicate",
        "influence",
        "source",
        "endpoint",
        "clipping",
        "constituent",
        "all_required",
    }
    assert gates["all_required"] is True
    diagnostics = contract["diagnostics_without_additional_fits"]
    assert "standardized_structure_hash" in diagnostics["duplicate_policy"]
    assert "exactly the top ten" in diagnostics["influential_families"]
    assert "SINGLE_SOURCE_NOT_APPLICABLE" in diagnostics["assay_source"]
    assert [item["id"] for item in diagnostics["clipping"]] == [
        "NO_CLIP_PRIMARY",
        "OUTER_TRAIN_MINMAX_DIAGNOSTIC",
        "OUTER_TRAIN_Q005_Q995_DIAGNOSTIC",
    ]
    assert "cannot select or modify" in diagnostics["clipping_boundary"]
    assert (
        contract["metrics"]["paired_bootstrap"][
            "accepted_replicates_per_drop_one_comparison"
        ]
        == 2000
    )
    assert contract["workload"]["drop_one_bootstrap_replicates"] == 4 * 2000


def test_contract_opens_no_scientific_or_private_capability() -> None:
    contract = _read(CONTRACT)
    assert all(
        value == 0 for value in contract["current_milestone_accounting"].values()
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key != "contract_and_static_tests"
    )
    assert contract["confirmatory_boundary"]["maximum_confirmatory_scores"] == 0
    assert (
        "does not resolve or authorize G2-8"
        in contract["confirmatory_boundary"]["meaning"]
    )
    assert (
        "two-root synthetic implementation/resource contract" in contract["next_gate"]
    )
    text = CONTRACT.read_text(encoding="utf-8").lower()
    assert "submission_name" not in text
    assert "leaderboard_score" not in text
    assert "leaderboard_rank" not in text
    assert "/home/zbos/cypshift-private" not in text


def test_public_handoffs_make_no_stale_portal_status_claim() -> None:
    paths = (
        ROOT / "docs" / "strategy" / "PROJECT_STATE.md",
        BENCHMARK / "DIRECT_BASELINE_HANDOFF.md",
        BENCHMARK / "TRACE_OFFICIAL_OUTCOME.md",
    )
    stale = (
        "has not been uploaded or scored",
        "has not yet been uploaded",
        "neither has occurred",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert "private portal activity" in text
        assert all(value not in text for value in stale)
