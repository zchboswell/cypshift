from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_g3_execution_contract.json"
CLAIM_PATH = BENCHMARK / "global_v2_g3_execution_claim.json"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_execution_contract_binds_every_accepted_parent_and_source() -> None:
    contract = _read(CONTRACT_PATH)
    assert contract["status"] == (
        "contract_and_unconsumed_claim_only_no_official_execution_yet"
    )
    assert contract["base_commit"] == "b68340c4a9b6495f79af0dc27db37f024a4db925"
    for parent in contract["parents"].values():
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert parent["sha256"] == _sha256(path)

    accepted = contract["accepted_implementation"]
    for path_key, hash_key in (
        ("g3_runner_path", "g3_runner_sha256"),
        ("g3_synthetic_driver_path", "g3_synthetic_driver_sha256"),
        ("g3_implementation_tests_path", "g3_implementation_tests_sha256"),
        ("g3_acceptance_tests_path", "g3_acceptance_tests_sha256"),
        ("research_pyproject_path", "research_pyproject_sha256"),
        ("research_lock_path", "research_lock_sha256"),
        ("chemistry_source_path", "chemistry_source_sha256"),
        ("schema_source_path", "schema_source_sha256"),
        ("tutorial_metric_source_path", "tutorial_metric_source_sha256"),
    ):
        assert accepted[hash_key] == _sha256(ROOT / accepted[path_key])


def test_unconsumed_claim_is_bound_but_deliberately_unusable() -> None:
    contract = _read(CONTRACT_PATH)
    claim = _read(CLAIM_PATH)
    assert claim["status"] == "G2_6T_G3_CLAIM_UNCONSUMED"
    assert claim["contract_sha256"] == _sha256(CONTRACT_PATH)
    assert claim["maximum_consumptions"] == 1
    assert claim["consumptions"] == 0
    assert claim["usable"] is False
    for field in contract["claim_contract"]["future_receipt_fields"]:
        assert claim[field] is None
    assert all(value is False for value in claim["authority"].values())


def test_official_receipts_and_file_boundaries_are_exact() -> None:
    official = _read(CONTRACT_PATH)["official_inputs"]
    assert official["attempt_root_absent_at_freeze"] is True
    assert official["dataset_revision"] == "85f8b358d0a2056a98b990dd75d3b3ec9247862b"
    assert official["source_file_allowlist"] == [
        "manifest.json",
        "direct_observations.csv",
        "group_folds.csv",
        "feature_rows.csv",
        "maplight_rdkit_descriptors.npy",
    ]
    assert official["baseline_file_allowlist"] == [
        "manifest.json",
        "development_outer_oof.csv",
    ]
    assert official["denied_source_files"] == [
        "maplight_morgan_count.npy",
        "maplight_avalon_count.npy",
        "maplight_erg.npy",
    ]
    assert "does not list, parse, copy, link, hash" in official["read_boundary"]


def test_population_and_structure_compilation_are_frozen() -> None:
    source = _read(CONTRACT_PATH)["source_compilation"]
    assert source["population"] == {
        "all_molecules": 4905,
        "all_components": 4553,
        "development_molecules": 3908,
        "development_components": 3640,
        "confirmatory_molecules_excluded": 997,
        "confirmatory_components_excluded": 913,
        "finite_development_truth_rows": 5197,
    }
    assert "before decoding any numeric target field" in source["identity_rule"]
    assert "every distinct raw string" in source["structure_rule"]
    assert "exact equality" in source["structure_rule"]
    assert "Parse zero confirmatory values" in source["truth_rule"]


def test_feature_matrix_is_exact_and_has_no_preprocessing() -> None:
    source = _read(CONTRACT_PATH)["source_compilation"]
    assert "2,048-column" in source["morgan_rule"]
    assert "includeChirality=true" in source["morgan_rule"]
    assert "countSimulation=false" in source["morgan_rule"]
    assert "4,905x200 float64" in source["descriptor_rule"]
    assert "Preserve column order and NaN" in source["descriptor_rule"]
    assert "3,908x2,248 C-contiguous float64" in source["matrix_rule"]
    for forbidden_transform in ("imputation", "scaling", "selection", "compression"):
        assert forbidden_transform in source["matrix_rule"]


def test_execution_is_one_fixed_sixty_fit_topology() -> None:
    execution = _read(CONTRACT_PATH)["execution"]
    assert execution["attempts"] == execution["replays"] == 1
    assert all(execution[field] is False for field in ("retry", "resume", "move", "overwrite"))
    assert execution["repeat_seeds"] == [20260810, 20260811, 20260812]
    assert execution["outer_folds"] == 5
    assert execution["outer_endpoint_contexts"] == 3 * 5 * 4
    assert execution["exact_new_lightgbm_fits"] == 60
    assert execution["baseline_refits"] == execution["inner_selection_fits"] == 0
    assert execution["expected_candidate_outer_prediction_rows"] == 46896
    assert execution["expected_baseline_outer_prediction_rows"] == 46896
    assert execution["model_seed"] == 20260825
    assert execution["num_boost_round"] == 1500
    assert "one fit process at a time" in execution["fit_order"]


def test_capabilities_freeze_predictions_before_scoring() -> None:
    contract = _read(CONTRACT_PATH)
    source = contract["source_compilation"]
    execution = contract["execution"]
    assert "model and scorer capabilities" in source["truth_rule"]
    assert "cannot resolve" in source["baseline_rule"]
    assert "scorer truth remains unreadable" in source["truth_rule"]
    assert "all candidate predictions freeze" in source["truth_rule"]
    assert "exactly 46,896 finite float64 candidate predictions" in execution[
        "prediction_freeze"
    ]


def test_all_six_promotion_gate_families_are_conjunctive() -> None:
    evaluation = _read(CONTRACT_PATH)["development_evaluation"]
    assert evaluation["primary_metric"]["exact_local_calls"] == 24
    bootstrap = evaluation["paired_component_bootstrap"]
    assert bootstrap["seed"] == 20260827
    assert bootstrap["accepted_replicates"] == 2000
    assert bootstrap["maximum_attempts"] == 20000
    gates = evaluation["promotion_gates"]
    assert gates["minimum_relative_primary_improvement"] == 0.03
    assert gates["minimum_absolute_component_mae_improvement"] == 0.015
    assert gates["paired_component_mae_upper_95_below_zero"] is True
    assert gates["minimum_favorable_outer_cells"] == 8
    assert gates["maximum_endpoint_mae_degradation"] == 0.015
    assert gates["targeted_endpoints"] == ["CYP1A2", "CYP2D6"]
    assert gates["minimum_targeted_endpoint_component_mae_improvement"] == 0.01
    assert "All six gate families are conjunctive" in gates["logic"]


def test_resources_terminals_and_cleanup_are_hard_bounded() -> None:
    contract = _read(CONTRACT_PATH)
    resources = contract["runtime_and_resources"]
    assert resources["thread_count_per_fit"] == 16
    assert resources["maximum_concurrent_fits"] == 1
    assert resources["hard_maxima"] == {
        "cpu_core_hours": 160,
        "wall_hours": 24,
        "restricted_storage_gb": 32,
        "peak_rss_gib": 24,
        "gpu_hours": 0,
    }
    terminal = contract["terminal_contract"]
    assert len(terminal["required_aggregate_outputs"]) == 6
    assert terminal["attempt_root_file_set"] == ["attempt_claim.json", "receipt", "terminal"]
    assert "remain private" in terminal["publication"]
    assert "Cleanup failure" in terminal["cleanup"]


def test_contract_opens_zero_scientific_or_submission_authority() -> None:
    contract = _read(CONTRACT_PATH)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert accounting["tracked_unconsumed_claims_created"] == 1
    assert all(
        value == 0
        for key, value in accounting.items()
        if key not in {"contracts_created", "tracked_unconsumed_claims_created"}
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert authority["tracked_unconsumed_claim"] is True
    assert all(
        value is False
        for key, value in authority.items()
        if key not in {"contract_and_static_tests", "tracked_unconsumed_claim"}
    )
    text = (CONTRACT_PATH.read_text() + CLAIM_PATH.read_text()).lower()
    assert all(
        forbidden not in text
        for forbidden in ("submission_name", "leaderboard_score", "leaderboard_rank")
    )
