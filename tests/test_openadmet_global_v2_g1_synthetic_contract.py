from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_g1_synthetic_contract.json"
PARENT_PATH = BENCHMARK / "global_v2_g1_screen_contract.json"
ACCEPTANCE_PATH = BENCHMARK / "global_v2_g1_synthetic_acceptance.json"
CONTRACT_SHA256 = "c8c706a815c3fa44933021e1f44b33cb3372a9334c9bc34f01dd5c851bdba866"
ACCEPTANCE_SHA256 = "479ba13074908e1d092867a940a29fe42e30b7265d36bc81d614450380c7ff06"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g1_synthetic_contract_has_exact_identity_and_parent() -> None:
    contract = _load(CONTRACT_PATH)
    parent = contract["parent"]
    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v2_g1_synthetic_contract.v1"
    )
    assert contract["gate"] == (
        "G2_3B_EXP_G1_SYNTHETIC_IMPLEMENTATION_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "synthetic_implementation_only_no_official_execution_authority"
    )
    assert parent["path"] == PARENT_PATH.name
    assert _sha256(PARENT_PATH) == parent["sha256"]
    assert parent["sha256"] == (
        "ce39721f403686dbac67cf72ea3b5996212bb571b08cd1bb7f571d0c2e5d97c3"
    )


def test_fixture_is_family_bearing_and_order_adversarial() -> None:
    fixture = _load(CONTRACT_PATH)["synthetic_fixture"]
    assert fixture["roots"] == 2
    assert fixture["root_a_order"].startswith("canonical")
    assert fixture["root_b_order"].startswith("exact reverse")
    assert fixture["components"] == 40
    assert fixture["molecules_per_component"] == 2
    assert fixture["molecules"] == 80
    assert fixture["feature_columns"] == 2563
    assert fixture["repeats"] == 3
    assert fixture["outer_folds"] == 5
    assert fixture["inner_folds"] == 4
    assert len(fixture["endpoints"]) == 4
    assert "no component crosses" in fixture["family_rule"]
    assert "at least three different configuration IDs" in fixture["selection_oracles"]
    assert "exact metric tie" in fixture["selection_oracles"]


def test_full_model_double_topology_matches_g1_parent() -> None:
    contract = _load(CONTRACT_PATH)
    topology = contract["full_topology_model_double"]
    parent = _load(PARENT_PATH)
    configurations = len(parent["screen"]["configurations"])
    seeds = len(parent["screen"]["model_seeds"])
    population = parent["population_and_splits"]
    inner_contexts = (
        population["repeats"]
        * population["outer_folds"]
        * population["inner_folds"]
        * len(population["endpoints"])
    )
    outer_cells = (
        population["repeats"]
        * population["outer_folds"]
        * len(population["endpoints"])
    )
    assert topology["configurations"] == configurations == 12
    assert topology["model_seeds"] == seeds == 3
    assert topology["inner_contexts"] == inner_contexts == 240
    assert topology["inner_model_stage_invocations_per_root"] == (
        inner_contexts * configurations * seeds
    ) == 8640
    assert topology["outer_endpoint_cells"] == outer_cells == 60
    assert topology["outer_model_stage_invocations_per_root"] == (
        outer_cells * seeds
    ) == 180
    assert topology["total_model_stage_invocations_per_root"] == 8820
    assert topology["total_model_stage_invocations"] == 17640
    assert "never reported as CatBoost fits" in topology["catboost_fit_accounting"]


def test_real_catboost_probe_is_minimal_and_complete() -> None:
    contract = _load(CONTRACT_PATH)
    probe = contract["locked_runtime_catboost_probe"]
    acceptance = contract["acceptance"]
    resources = contract["resource_ceiling"]
    assert probe["fits_per_root"] == 12 + 2 == 14
    assert probe["roots"] == 2
    assert probe["exact_total_real_catboost_fits"] == 28
    assert acceptance["real_catboost_fits_total"] == 28
    assert resources["real_catboost_fits"] == 28
    assert acceptance["all_configuration_forms_probed_per_root"]
    assert acceptance["all_three_seeds_probed_per_root"]
    assert "no fast-mode parameter substitution" in probe["input"]
    assert "neither ranks configurations" in probe["scientific_boundary"]


def test_stage_graph_is_nested_and_truth_sealed() -> None:
    stages = _load(CONTRACT_PATH)["stage_graph"]
    assert "cannot resolve validation truth" in stages["inner_model"]
    assert "cannot resolve outer-validation truth" in stages["inner_selector"]
    assert "cannot resolve outer truth" in stages["outer_model"]
    assert "before any outer truth opens" in stages["outer_freezer"]
    assert "Only after all 60 candidate outer cell freezers" in stages["outer_scorer"]
    assert "cannot revise any outer prediction" in stages[
        "global_configuration_freezer"
    ]
    assert "no-replace semantics" in stages["terminal_publisher"]


def test_numeric_policy_binds_canonical_reductions() -> None:
    numeric = _load(CONTRACT_PATH)["deterministic_numeric_policy"]
    assert "complete contracted identity tuple" in numeric["canonical_order"]
    assert numeric["seed_mean"] == (
        "math.fsum in ascending seed order divided by exactly three"
    )
    assert numeric["outer_context_mean"] == (
        "math.fsum in ascending outer-fold order divided by exactly four"
    )
    assert "canonical endpoint order" in numeric["endpoint_macro"]
    assert "ascending repeat order" in numeric["repeat_mean"]
    assert "exact G2-3A unit" in numeric["bootstrap"]
    assert "fails the whole replay" in numeric["failure"]


def test_adversaries_cover_family_identity_runtime_and_cleanup() -> None:
    tests = _load(CONTRACT_PATH)["required_adversarial_tests"]
    joined = "\n".join(tests)
    assert len(tests) == 14
    for required in (
        "component crossing an outer boundary",
        "component crossing a scoped inner boundary",
        "selection from outer diagnostics",
        "configuration-seed identity forgery",
        "cross-root mix",
        "resolved parameter",
        "process completion order",
        "retry, resume",
        "injected stage failure",
        "forbidden-operation counters",
    ):
        assert required in joined


def test_contract_freeze_opens_no_synthetic_or_official_operation() -> None:
    contract = _load(CONTRACT_PATH)
    assert all(value == 0 for value in contract["current_milestone_accounting"].values())
    authority = contract["current_authority"]
    assert authority["contract_and_static_tests"]
    assert not any(
        value
        for name, value in authority.items()
        if name != "contract_and_static_tests"
    )
    boundary = "\n".join(contract["future_execution_boundary"]["must_never_open_under_g2_3b"])
    for forbidden in (
        "official development targets",
        "G2-2 row-level baseline predictions",
        "confirmatory truth",
        "blinded-test",
        "leaderboard",
    ):
        assert forbidden in boundary


def test_acceptance_is_conjunctive_mechanics_only_and_precedes_g2_3c() -> None:
    contract = _load(CONTRACT_PATH)
    acceptance = contract["acceptance"]
    assert acceptance["fresh_roots_required"] == 2
    assert acceptance["relative_terminal_maps_byte_identical"]
    assert acceptance["expected_inner_selections_match"]
    assert acceptance["expected_future_endpoint_tokens_match"]
    assert acceptance["family_and_capability_adversaries_pass"]
    assert acceptance["identity_and_numeric_adversaries_pass"]
    assert acceptance["accounting_cleanup_and_no_replace_adversaries_pass"]
    assert "mechanics" in acceptance["scientific_interpretation"]
    assert "No synthetic score" in acceptance["scientific_interpretation"]
    terminal = contract["terminal_contract"]
    assert terminal["success_status"] == "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED"
    assert terminal["failure_status"] == "G2_3B_EXP_G1_SYNTHETIC_FAILED"
    assert "cannot be resumed" in terminal["immutability"]
    assert "drafting G2-3C" in contract["next_gate"]
    assert "Do not open an official input" in contract["next_gate"]


def test_tracked_g1_synthetic_acceptance_binds_exact_implementation() -> None:
    acceptance = _load(ACCEPTANCE_PATH)
    assert _sha256(ACCEPTANCE_PATH) == ACCEPTANCE_SHA256
    assert acceptance["status"] == "G2_3B_EXP_G1_SYNTHETIC_ACCEPTED"
    assert acceptance["contract_sha256"] == CONTRACT_SHA256
    assert acceptance["roots"] == 2
    assert acceptance["relative_terminal_maps_identical"]
    assert acceptance["model_double_invocations_total"] == 17640
    assert acceptance["real_catboost_fits_total"] == 28
    assert acceptance["focused_tests_passed"] == 23
    receipts = acceptance["implementation_receipts"]
    assert receipts["g1_runner_source_sha256"] == _sha256(
        ROOT / "research" / "maplight-fixed" / "global_v2_g1_runner.py"
    )
    assert receipts["synthetic_driver_source_sha256"] == _sha256(
        ROOT / "research" / "maplight-fixed" / "run_global_v2_g1_synthetic.py"
    )
    assert receipts["focused_test_source_sha256"] == _sha256(
        ROOT / "tests" / "test_openadmet_global_v2_g1_synthetic.py"
    )
    forbidden = {
        "official_target_values_opened",
        "official_features_opened",
        "official_model_fits",
        "official_predictions_generated",
        "development_metric_evaluations",
        "official_metric_evaluations",
        "confirmatory_truth_values_opened",
        "historical_r3c_row_level_artifacts_opened",
        "blinded_test_files_opened",
        "tdi_files_opened",
        "external_records_acquired",
        "submissions_created",
        "leaderboard_observations",
        "live_uploads",
    }
    assert all(
        value == 0
        for name, value in acceptance["accounting_per_replay"].items()
        if name in forbidden
    )
