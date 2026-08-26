from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_maplight_robustness_execution_contract_v2.json"
CLAIM_PATH = BENCHMARK / "global_v2_maplight_robustness_execution_claim_v2.json"
D122_PATH = BENCHMARK / "global_v2_maplight_robustness_contract.json"
D125_PATH = BENCHMARK / "global_v2_maplight_robustness_bounded_execution_contract.json"
D127_CONTRACT_PATH = BENCHMARK / "global_v2_maplight_robustness_execution_contract.json"
D127_CLAIM_PATH = BENCHMARK / "global_v2_maplight_robustness_execution_claim.json"
CONTRACT_SHA256 = "9464b0947255298a8de8836af6178857841bb2a55bc5c0f4897be2ba91151bcf"
CLAIM_SHA256 = "d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_corrected_contract_and_claim_have_exact_identity() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert _sha(CONTRACT_PATH) == CONTRACT_SHA256
    assert _sha(CLAIM_PATH) == CLAIM_SHA256
    assert contract["schema_version"].endswith("execution_contract.v2")
    assert contract["gate"] == "G2_7G_MAPLIGHT_ROBUSTNESS_EXECUTION_CONTRACT_FROZEN"
    assert contract["base_commit"] == "fed05e694b7200f21332ed585bf40b31f7df238b"
    assert claim["status"] == "G2_7G_MAPLIGHT_ROBUSTNESS_CLAIM_UNCONSUMED"
    assert claim["contract_sha256"] == CONTRACT_SHA256
    assert claim["claim_id"] == contract["claim_contract"]["claim_id"]
    assert contract["claim_contract"]["claim_path"] == CLAIM_PATH.name


def test_all_accepted_parents_are_hash_bound() -> None:
    contract = _load(CONTRACT_PATH)
    for name, parent in contract["parents"].items():
        if name == "post_main_ci":
            assert parent == {
                "run_id": 32911452732,
                "head_sha": "fed05e694b7200f21332ed585bf40b31f7df238b",
                "conclusion": "success",
                "python_jobs_passed": ["3.11", "3.12.3", "3.14"],
            }
            continue
        path = BENCHMARK / parent["path"]
        assert path.is_file()
        assert _sha(path) == parent["sha256"]


def test_d127_and_d128_paths_are_permanently_barred() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    history = contract["barred_history"]
    assert history["d127_contract_sha256"] == _sha(D127_CONTRACT_PATH)
    assert history["d127_claim_sha256"] == _sha(D127_CLAIM_PATH)
    assert history["d127_claim_consumptions"] == 0
    assert history["d127_claim_usable"] is False
    assert history["d127_claim_and_root_permanently_barred"] is True
    assert history["d128_attempts_remaining"] == 0
    assert claim["barred_history"]["d127_claim_and_root_permanently_barred"] is True
    assert claim["barred_history"]["d128_attempts_remaining"] == 0


def test_accepted_implementation_and_scorer_sources_are_exact() -> None:
    implementation = _load(CONTRACT_PATH)["accepted_implementation"]
    pairs = (
        ("robustness_compiler_path", "robustness_compiler_sha256"),
        ("no_fit_wrapper_path", "no_fit_wrapper_sha256"),
        ("resource_supervisor_path", "resource_supervisor_sha256"),
        ("maplight_runner_path", "maplight_runner_sha256"),
        ("scoring_compiler_path", "scoring_compiler_sha256"),
        ("scoring_acceptance_driver_path", "scoring_acceptance_driver_sha256"),
        ("scoring_acceptance_tests_path", "scoring_acceptance_tests_sha256"),
        ("tutorial_metric_source_path", "tutorial_metric_source_sha256"),
        ("chemistry_source_path", "chemistry_source_sha256"),
        ("research_lock_path", "research_lock_sha256"),
        ("root_lock_path", "root_lock_sha256"),
    )
    for path_key, hash_key in pairs:
        assert _sha(ROOT / implementation[path_key]) == implementation[hash_key]


def test_new_claim_is_single_use_and_deliberately_unusable() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    assert contract["claim_contract"]["maximum_consumptions"] == 1
    assert claim["maximum_consumptions"] == 1
    assert claim["consumptions"] == 0
    assert claim["usable"] is False
    for field in contract["claim_contract"]["future_receipt_fields"]:
        assert claim[field] is None
    assert all(value is False for value in claim["authority"].values())
    assert (
        "starts before atomic no-replace creation"
        in contract["claim_contract"]["consumption"]
    )
    assert "permits no retry" in contract["claim_contract"]["consumption"]


def test_new_attempt_root_is_distinct_and_absent_at_freeze() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(CLAIM_PATH)
    official = contract["official_inputs"]
    old_root = _load(D127_CLAIM_PATH)["fixed_roots"]["attempt_root"]
    assert official["attempt_root_absent_at_freeze"] is True
    assert official["attempt_root"].endswith(
        "g2-7g-maplight-robustness-development-attempt-1"
    )
    assert official["attempt_root"] != old_root
    assert claim["fixed_roots"] == {
        key: official[key]
        for key in (
            "development_source_root",
            "fixed_baseline_terminal_root",
            "attempt_root",
        )
    }
    assert not Path(official["attempt_root"]).exists()
    assert "does not list, parse, copy, link, hash" in official["read_boundary"]


def test_official_receipts_and_allowlists_are_unchanged() -> None:
    corrected = _load(CONTRACT_PATH)["official_inputs"]
    prior = _load(D127_CONTRACT_PATH)["official_inputs"]
    for name in (
        "development_source_root",
        "fixed_baseline_terminal_root",
        "dataset_revision",
        "r2b_manifest_sha256",
        "r3a_feature_manifest_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "feature_rows_sha256",
        "maplight_morgan_count_sha256",
        "maplight_avalon_count_sha256",
        "maplight_erg_sha256",
        "maplight_rdkit_descriptors_sha256",
        "baseline_manifest_sha256",
        "baseline_outer_oof_sha256",
        "baseline_component_metrics_sha256",
        "source_file_allowlist",
        "baseline_file_allowlist",
        "denied_baseline_files",
    ):
        assert corrected[name] == prior[name]
    claim_receipts = _load(CLAIM_PATH)["official_input_receipts"]
    expected = {
        "dataset_revision": corrected["dataset_revision"],
        **{
            name: value for name, value in corrected.items() if name.endswith("_sha256")
        },
    }
    assert claim_receipts == expected


def test_scientific_identity_exactly_inherits_d122() -> None:
    science = _load(CONTRACT_PATH)["scientific_invariants"]
    parent = _load(D122_PATH)
    assert science["default_candidate"] == parent["fixed_maplight"]["candidate_id"]
    assert science["drop_one_candidates"] == [
        item["candidate_id"] for item in parent["drop_one_candidates"]
    ]
    assert (
        science["seed_perturbation_values"]
        == parent["stage_a_selection"]["seed_perturbation_values"]
    )
    assert science["group_perturbations"] == [
        item["id"]
        for item in parent["stage_b_selected_robustness"]["group_perturbations"]
    ]
    assert science["selection_tokens"] == 1
    assert science["runner_ups"] == 0
    assert science["full_is_default"] is True
    assert all(
        science[name] is False
        for name in ("retry", "resume", "move", "overwrite", "replacement")
    )


def test_fit_and_prediction_accounting_are_unchanged() -> None:
    science = _load(CONTRACT_PATH)["scientific_invariants"]
    assert science["fit_counts"] == {
        "stage_a_total": 540,
        "stage_b_total": 180,
        "stage_c_if_deletion_selected": 300,
        "minimum_total": 720,
        "maximum_total": 1020,
        "baseline_refits": 0,
        "inner_fits": 0,
    }
    assert science["prediction_counts"] == {
        "stage_a": 422_064,
        "stage_b_upper_bound": 140_688,
        "stage_c_if_deletion_selected": 234_480,
        "minimum_total": 562_752,
        "maximum_total": 797_232,
    }
    assert "runs only when" in science["conditional_stage_c"]
    assert "conjunctively" in science["selection_and_robustness"]


def test_eight_field_scorer_is_additive_and_confirmatory_opaque() -> None:
    scoring = _load(CONTRACT_PATH)["scoring_capability"]
    claim = _load(CLAIM_PATH)
    assert scoring["required_fields"] == [
        "molecule_id",
        "endpoint",
        "standardized_structure_hash",
        "primary_component_hash",
        "source_file",
        "point",
        "low",
        "high",
    ]
    compiler_path = (
        ROOT / _load(CONTRACT_PATH)["accepted_implementation"]["scoring_compiler_path"]
    )
    compiler_tree = ast.parse(compiler_path.read_text(encoding="utf-8"))
    output_columns = None
    for node in compiler_tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "OUTPUT_COLUMNS"
        ):
            output_columns = ast.literal_eval(node.value)
            break
    assert tuple(scoring["required_fields"]) == output_columns
    assert (
        scoring["accepted_compiler_sha256"] == claim["scoring_compiler_source_sha256"]
    )
    assert (
        scoring["accepted_capability_sha256"]
        == claim["scoring_capability_acceptance_sha256"]
    )
    assert scoring["confirmatory_value_fields_decoded_in_acceptance"] == 0
    assert "until every required prediction" in scoring["chronology"]
    assert "tutorial eligibility is derived" in scoring["repair_boundary"]
    assert "does not change any D-122 model" in scoring["repair_boundary"]


def test_resources_exactly_inherit_d125_and_start_before_consumption() -> None:
    resources = _load(CONTRACT_PATH)["runtime_and_resources"]
    limits = _load(D125_PATH)["cumulative_resource_envelope"]["hard_limits"]
    assert resources["hard_maxima"] == {
        "cpu_core_hours": limits["cpu_core_hours"],
        "wall_hours": limits["wall_hours"],
        "restricted_storage_gb": limits["restricted_storage_gb"],
        "peak_simultaneous_rss_gib": limits["peak_rss_gib"],
        "gpu_hours": limits["gpu_hours"],
    }
    assert "starts before claim consumption" in resources["measurement"]
    assert resources["model"]["thread_count_per_fit"] == 16
    assert resources["model"]["maximum_concurrent_fits"] == 1
    assert "Unused capacity cannot fund a retry" in resources["budget_rule"]


def test_contract_freeze_opens_zero_scientific_or_external_authority() -> None:
    contract = _load(CONTRACT_PATH)
    accounting = contract["current_milestone_accounting"]
    assert accounting["contracts_created"] == 1
    assert accounting["tracked_unconsumed_claims_created"] == 1
    assert all(
        value == 0
        for name, value in accounting.items()
        if name not in {"contracts_created", "tracked_unconsumed_claims_created"}
    )
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"] is True
    assert authority["tracked_unconsumed_claim"] is True
    assert all(
        value is False
        for name, value in authority.items()
        if name not in {"contract_and_static_tests", "tracked_unconsumed_claim"}
    )
    text = (CONTRACT_PATH.read_text() + CLAIM_PATH.read_text()).lower()
    for private_result_field in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
    ):
        assert private_result_field not in text


def test_terminal_privacy_and_next_gate_fail_closed() -> None:
    contract = _load(CONTRACT_PATH)
    terminal = contract["terminal_and_privacy"]
    assert len(terminal["statuses"]) == 5
    assert len(terminal["must_remain_zero"]) == 9
    assert "remain private" in terminal["publication"]
    assert "Cleanup failure changes" in terminal["cleanup"]
    assert "no retry, resume, move, overwrite" in terminal["failure"]
    assert contract["next_gate"].startswith("Implement only the additive")
    assert "Do not consume the claim" in contract["next_gate"]
