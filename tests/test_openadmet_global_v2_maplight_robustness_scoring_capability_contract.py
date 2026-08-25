from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT_PATH = BENCHMARK / "global_v2_maplight_robustness_scoring_capability_contract.json"
D122_CONTRACT = BENCHMARK / "global_v2_maplight_robustness_contract.json"
D127_CONTRACT = BENCHMARK / "global_v2_maplight_robustness_execution_contract.json"
D127_CLAIM = BENCHMARK / "global_v2_maplight_robustness_execution_claim.json"
COMPILER = ROOT / "research" / "maplight-fixed" / "global_v2_maplight_robustness_execution_compiler.py"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assignment(name: str) -> tuple[str, ...]:
    tree = ast.parse(COMPILER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and isinstance(node.value, ast.Tuple):
                values: list[str] = []
                for value in node.value.elts:
                    assert isinstance(value, ast.Constant) and isinstance(value.value, str)
                    values.append(value.value)
                return tuple(values)
    raise AssertionError(f"{name} assignment not found")


def test_contract_is_contract_only_and_revokes_d127_progression() -> None:
    contract = _load(CONTRACT_PATH)
    assert contract["gate"] == (
        "G2_7E_MAPLIGHT_ROBUSTNESS_SCORING_CAPABILITY_CONTRACT_FROZEN"
    )
    assert contract["status"] == (
        "contract_only_d127_progression_revoked_no_implementation_or_official_operation"
    )
    superseded = contract["parents"]["superseded_execution_contract"]
    assert superseded["sha256"] == _sha(D127_CONTRACT)
    assert superseded["progression_authority"] is False


def test_d127_claim_remains_exactly_unconsumed_and_unusable() -> None:
    contract = _load(CONTRACT_PATH)
    claim = _load(D127_CLAIM)
    disposition = contract["parents"]["permanently_unusable_d127_claim"]
    assert disposition["sha256"] == _sha(D127_CLAIM)
    assert claim["status"] == disposition["required_status"]
    assert claim["consumptions"] == disposition["consumptions"] == 0
    assert claim["usable"] is disposition["usable"] is False
    assert all(
        claim[name] is None
        for name in (
            "future_scientific_runner_source_sha256",
            "future_official_attempt_driver_source_sha256",
            "future_official_shaped_acceptance_driver_source_sha256",
            "future_official_shaped_execution_acceptance_sha256",
            "future_focused_tests_sha256",
        )
    )


def test_defect_is_bound_to_the_actual_accepted_compiler_shape() -> None:
    contract = _load(CONTRACT_PATH)
    d122 = _load(D122_CONTRACT)
    evidence = contract["defect_evidence"]
    assert contract["parents"]["maplight_robustness_contract"]["sha256"] == _sha(
        D122_CONTRACT
    )
    assert d122["metrics"]["primary"]["eligibility"] == (
        "Finite central point and both finite reported bounds; no imputation or "
        "midpoint."
    )
    diagnostics = d122["diagnostics_without_additional_fits"]
    assert "standardized_structure_hash" in diagnostics["duplicate_policy"]
    assert "one source_file field" in diagnostics["assay_source"]
    accepted = evidence["accepted_compiler_source"]
    assert accepted["sha256"] == _sha(COMPILER)
    assert tuple(accepted["truth_columns_value"]) == _assignment("TARGET_COLUMNS")
    assert evidence["d126_emitted_stage_truth_columns"] == [
        "molecule_id",
        "endpoint",
        "point",
    ]
    assert set(evidence["missing_from_d126_scorer"]) == {
        "low",
        "high",
        "standardized_structure_hash",
        "source_file",
    }


def test_repair_emits_only_the_frozen_scoring_fields() -> None:
    contract = _load(CONTRACT_PATH)
    scoring = contract["scorer_enrichment_capability"]
    assert scoring["output_columns"] == [
        "molecule_id",
        "endpoint",
        "standardized_structure_hash",
        "primary_component_hash",
        "source_file",
        "point",
        "low",
        "high",
    ]
    assert scoring["source_policy"].startswith(
        "Every decoded development row must have source_file exactly "
        "cyp-challenge-TRAIN_inhibition.csv"
    )
    policy = scoring["row_policy"].lower()
    assert "do not decode" in policy
    assert "never impute" in policy
    assert "exact point equality" in policy
    assert scoring["official_population_accounting"] == {
        "all_molecules": 4905,
        "all_endpoint_rows": 19620,
        "development_molecules": 3908,
        "development_rows_decoded": 15632,
        "finite_development_point_rows_emitted": 5197,
        "confirmatory_molecules": 997,
        "confirmatory_rows_prefix_checked_suffix_opaque": 3988,
        "confirmatory_value_fields_decoded": 0,
    }


def test_repair_preserves_the_exact_scientific_and_resource_workload() -> None:
    contract = _load(CONTRACT_PATH)
    science = contract["corrected_execution_boundary"]["unchanged_science"]
    assert science == {
        "stage_a_fits": 540,
        "stage_b_fits": 180,
        "stage_c_conditional_fits": 300,
        "minimum_total_fits": 720,
        "maximum_total_fits": 1020,
        "minimum_prediction_identities": 562752,
        "maximum_prediction_identities": 797232,
        "baseline_refits": 0,
        "inner_fits": 0,
        "selection_tokens": 1,
        "runner_ups": 0,
        "deployable_clips": 0,
    }
    assert contract["corrected_execution_boundary"]["unchanged_resource_maxima"] == {
        "wall_hours": 7.68,
        "cpu_core_hours": 128.0,
        "restricted_storage_gb": 51.2,
        "peak_simultaneous_rss_gib": 15.36,
        "gpu_hours": 0,
    }


def test_synthetic_acceptance_is_opposite_order_and_zero_fit() -> None:
    acceptance = _load(CONTRACT_PATH)["future_official_shaped_acceptance"]
    assert acceptance["attempts"] == 1
    assert acceptance["roots"] == 2
    assert "canonical physical" in acceptance["root_a"]
    assert "reversed physical" in acceptance["root_b"]
    assert "invalid UTF-8 poison sentinel" in acceptance["fixture"]
    assert acceptance["real_catboost_fits"] == 0
    assert acceptance["development_metric_evaluations"] == 0
    assert acceptance["model_quality_authority"] is False
    assert acceptance["claim_authority"] is False


def test_current_milestone_has_zero_operations_and_no_authority() -> None:
    contract = _load(CONTRACT_PATH)
    assert set(contract["current_milestone_accounting"].values()) == {0}
    assert set(contract["current_authority"].values()) == {False}
    discovered = contract["defect_evidence"]["discovered_before"]
    assert "claim consumption" in discovered
    assert "official source access" in discovered
    assert "real CatBoost fit" in discovered


def test_next_gate_cannot_skip_the_repaired_capability() -> None:
    next_gate = _load(CONTRACT_PATH)["next_gate"].lower()
    for required in (
        "reviewed signed integration",
        "green post-main ci",
        "exactly one two-root synthetic acceptance",
        "zero real fit",
        "zero development metric",
        "do not implement the scientific runner",
        "create or consume a claim",
        "open an official byte",
        "access confirmatory truth",
        "use leaderboard evidence for selection",
    ):
        assert required in next_gate


def test_contract_contains_no_private_portal_result_fields() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
    ):
        assert forbidden not in text
