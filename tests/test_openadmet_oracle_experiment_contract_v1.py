from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "oracle_experiment_contract_v1.json"
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load() -> dict[str, Any]:
    return json.loads(
        CONTRACT_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_is_strict_json_and_binds_accepted_parents() -> None:
    contract = _load()
    assert contract["schema_version"].endswith("oracle_experiment_contract.v1")
    assert contract["contract_id"] == "R5-CYP3A4-ORACLE-V1"
    assert contract["status"] == "R5_ORACLE_CONTRACT_ONLY"

    parents = contract["parent_receipts"]
    for key in (
        "validation_contract",
        "global_contract_v5",
        "r4_contract_v5",
        "r4_contract_v6",
    ):
        path = ROOT / parents[key]["path"]
        assert _sha256(path) == parents[key]["sha256"]

    assert parents["r3c_manifest"]["required_status"] == "GLOBAL_EXPERT_FROZEN"
    assert (
        parents["r4_manifest"]["required_status"]
        == "R4_TRANSFORMATION_COVERAGE_SUPPORTED"
    )
    assert parents["r4_pairs"]["rows"] == 564
    assert parents["r4_episode_transformations"]["rows"] == 1818


def test_scope_is_the_smallest_honest_oracle_question() -> None:
    contract = _load()
    scope = contract["scope"]
    assert scope == {
        "endpoint": "CYP3A4",
        "protocol": "ANCHOR_EXPANSION_HOLDOUT",
        "primary_episode_policy": "selected_anchor",
        "diagnostic_episode_policy": "deterministic_random_anchor_stress",
        "internal_metric": "absolute_error_on_reported_central_pIC50",
        "official_st_rae": False,
        "inferred_anchor": False,
        "tdi": False,
        "test_access": False,
        "submission": False,
    }
    primary = contract["population"]["primary_local_eligible"]
    assert "selector_cyp_truth equals CYP3A4" in primary
    assert "episode_policy_id equals selected_anchor" in primary
    assert any("VALID_SINGLE or VALID_DOUBLE" in rule for rule in primary)
    assert contract["population"]["independence_unit"].startswith(
        "similarity_component_hash"
    )


def test_folds_and_support_fail_closed_without_repeat_inflation() -> None:
    contract = _load()
    folds = contract["folds"]
    assert (folds["repeats"], folds["outer_folds"], folds["inner_folds"]) == (
        3,
        5,
        4,
    )
    assert "one designated anchor" in folds["outer_rule"]
    assert "never regenerated" in folds["no_regeneration"]

    support = contract["support_gate"]
    assert support["unique_primary_components_min"] == 50
    assert support["unique_primary_episode_query_pairs_min"] == 100
    assert support["each_repeat_outer_fold_components_min"] == 5
    assert support["each_repeat_outer_fold_unique_rows_min"] == 10
    assert "before repeat expansion" in support["evaluation_counting"]
    assert support["outer_training_min"] == {
        "families": 50,
        "valid_unordered_pairs": 200,
    }
    assert support["inner_training_min"] == {
        "families": 40,
        "valid_unordered_pairs": 150,
    }
    assert support["label_safe_replay"]["inner_cell_min_families"] == 43
    assert support["label_safe_replay"]["inner_cell_min_pairs"] == 199
    assert "UNDERPOWERED" in support["clean_miss"]


def test_systems_include_every_required_control_without_model_bloat() -> None:
    contract = _load()
    systems = contract["systems"]
    assert systems["ordered"] == [
        "G0",
        "C0",
        "C1",
        "C2",
        "C3",
        "T0",
        "F0",
        "F1",
        "F2",
        "A0",
        "A1",
        "A2",
    ]
    assert set(systems["definitions"]) == set(systems["ordered"])
    definitions = " ".join(systems["definitions"].values())
    for required in (
        "MAPL-FIXED",
        "Copy",
        "Morgan",
        "signed-Morgan-difference ridge",
        "without measured anchor potency",
        "residual hierarchy",
        "shuffled",
        "most Morgan-similar",
        "permuting",
        "class-only",
        "without contextual ridge",
        "without hierarchy",
    ):
        assert required in definitions
    assert contract["context_model"]["alpha_grid"] == [1.0, 10.0]
    assert contract["hierarchy"]["lambda_grid"] == [2.0, 10.0]
    forbidden_models = " ".join(contract["context_model"]["forbidden"])
    assert "neural" in forbidden_models
    assert "MCS" in forbidden_models


def test_scoring_acceptance_and_safety_are_predeclared() -> None:
    contract = _load()
    scoring = contract["scoring"]
    assert scoring["required_contrasts"] == [
        "G0-T0",
        "C0-T0",
        "C1-T0",
        "C2-T0",
        "C3-T0",
        "F0-T0",
        "F1-T0",
        "F2-T0",
        "F0_LOCAL-T0",
        "F1_LOCAL-T0",
    ]
    assert "positive favors T0" in scoring["contrast"]

    bootstrap = contract["bootstrap"]
    assert bootstrap["accepted_replicates"] == 2000
    assert bootstrap["maximum_attempts"] == 20000
    assert bootstrap["unit"].startswith("unique primary component_id")

    acceptance = contract["acceptance"]
    assert acceptance["statuses_precedence"] == [
        "R5_ORACLE_FAILED",
        "R5_ORACLE_UNDERPOWERED",
        "R5_ORACLE_NO_SIGNAL",
        "R5_ORACLE_SIGNAL_PASS",
    ]
    signal = " ".join(acceptance["signal_pass"])
    assert "strictly positive 95% bootstrap lower bound" in signal
    assert "12 of 15" in signal
    assert "top-10" in signal
    assert "below 0.01" in signal
    assert "0.05 pIC50" in signal

    safety = contract["safety_fusion"]
    assert safety["prediction"].startswith("On primary_local_eligible rows use 0.5")
    assert "strictly below 0.01" in safety["criterion"]
    assert safety["bootstrap_seed"] != contract["bootstrap"]["seed"]
    assert "Never reuse primary multiplicities" in safety["bootstrap"]


def test_capability_firewall_and_authority_never_imply_submission() -> None:
    contract = _load()
    firewall = contract["capability_firewall"]
    assert "completion artifacts are forbidden" in firewall["projector"]
    assert "no query truth" in firewall["model"]
    assert "no ability to refit" in firewall["scorer"]
    assert "No non-anchor member" in firewall["episode_exclusion"]
    assert set(firewall["always_zero"]) == {
        "blinded_test_files_opened",
        "tdi_files_opened",
        "official_metric_calls",
        "submissions_created",
        "transductive_relationships",
        "inferred_anchor_candidate_pools",
    }

    authority = contract["authority"]
    for status, values in authority.items():
        assert values["model_fits"] is False, status
        assert values["predictions"] is False, status
        assert values["official_st_rae"] is False, status
        assert values["test_access"] is False, status
        assert values["tdi"] is False, status
        assert values["submission"] is False, status
        assert values["transduction"] is False, status
    assert authority["R5_ORACLE_SIGNAL_PASS"]["inferred_anchor_contract"] is True
    assert authority["R5_ORACLE_NO_SIGNAL"]["inferred_anchor_contract"] is False


def test_terminal_is_minimal_and_no_signal_cannot_be_rescued() -> None:
    contract = _load()
    outputs = contract["outputs"]
    full_files = [
        "manifest.json",
        "oracle_inner_selection.csv",
        "oracle_scored_rows.csv",
        "oracle_cell_metrics.csv",
        "oracle_bootstrap_summary.csv",
        "oracle_influence_checks.csv",
        "oracle_ablation_scorecard.csv",
        "oracle_result.json",
    ]
    assert outputs["status_files"] == {
        "R5_ORACLE_FAILED": ["failure.json"],
        "R5_ORACLE_UNDERPOWERED": ["manifest.json", "oracle_result.json"],
        "R5_ORACLE_NO_SIGNAL": full_files,
        "R5_ORACLE_SIGNAL_PASS": full_files,
    }
    assert "point_estimates" in outputs["underpowered_sentinels"]
    assert "never emit target values or anchor values" in outputs["scored_rows_policy"]
    assert "cannot rescue T0" in contract["acceptance"]["ablation_rule"]
    assert "stops inferred-anchor" in contract["acceptance"]["stop_rule"]


def test_cross_fit_control_and_membership_repairs_are_pinned() -> None:
    contract = _load()
    parents = contract["parent_receipts"]
    assert (
        parents["r3_global_oof_predictions"]["sha256"]
        == "1935b580ec779f2fc08d40e32e9669edae6e166ea70cd964e325df853527af80"
    )
    assert (
        parents["r3_global_inner_oof_predictions"]["sha256"]
        == "17cc5aadf6e109efe13893e9d9364371043f1fc7b1e4e2faa20dae5ab5c3c332"
    )
    assert "parent_completion" not in " ".join(parents)
    assert "Never use completion_state" in contract["features"]["C3_anchor_state"]
    assert (
        parents["r4_extractor"]["unified_source_sha256"]
        == "2ac5ea0004402df82bbb26024089a1b0b2fe258346a71c7b89bd1512672eaaed"
    )

    folds = contract["folds"]
    assert "outer fit" in folds["current_training_partition"]
    assert "inner fit" in folds["current_training_partition"]
    assert "Every label" in folds["current_training_authority"]
    assert "every selected_anchor public episode" in folds["prediction_superset"]
    assert "Only the sealed" in folds["sealed_filter"]

    randomization = contract["control_randomization"]
    assert "current_training_partition" in randomization["on_demand_geometry"]
    assert "min(64,N)" in randomization["on_demand_geometry"]
    assert "int.from_bytes" in randomization["scoped_seed"]
    assert "no held-out validation anchor" in randomization["F0"]
    assert "current-training" in randomization["F2"]
    assert contract["support_gate"]["control_local_availability_min"] == {
        "families": 30,
        "unique_episode_query_rows": 50,
    }


def test_trace_is_nested_over_generic_difference_and_selection_is_exact() -> None:
    contract = _load()
    features = contract["features"]
    assert "4096-bit" in features["generic_signed_morgan"]
    assert "strict structural extension" in features["nested_context_rule"]

    candidates = contract["selection_candidates"]
    assert candidates["T0"] == {
        "alpha": [1.0, 10.0],
        "lambda": [2.0, 10.0],
    }
    assert candidates["C3"] == candidates["T0"]
    assert candidates["C2"]["lambda"] == [None]
    assert candidates["A0"]["alpha"] == [None]
    assert candidates["F2"]["reuse"] == "T0 score-free token"
    assert "joint (alpha,lambda)" in contract["context_model"]["selection"]
    assert "C3" in contract["hierarchy"]["fit_target"]
    assert "A0 stops after" in contract["hierarchy"]["selection"]
    assert "1/(2*P)" in contract["targets"]["sample_weight"]

    global_model = contract["global_model"]
    assert (
        global_model["resolved_parameter_sha256"]
        == "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
    )
    assert "Every finite reported CYP3A4 point" in global_model["training"]
    assert "fit(X,y) with no sample_weight" in global_model["training"]
    assert contract["runtimes"]["root"]["python"] == "3.12.3"
    assert contract["runtimes"]["root"]["scikit_learn"] == "1.9.0"
    assert contract["runtimes"]["maplight"]["python"] == "3.10.13"
    assert contract["runtimes"]["maplight"]["catboost"] == "1.2.1"


def test_process_schemas_and_operation_accounting_are_mechanical() -> None:
    contract = _load()
    roots = contract["projection_roots"]
    assert set(roots) == {
        "model_public",
        "cell_target",
        "c3_target",
        "sealed_scorer",
        "receipt_rule",
    }
    assert "selector_cyp_truth" in roots["model_public"]["forbidden"]
    assert "current_training_partition" in roots["cell_target"]["rule"]
    anchor_columns = roots["cell_target"]["episode_anchor_contexts_columns"]
    assert "anchor_global_oof_prediction" in anchor_columns
    assert "anchor_global_oof_receipt_sha256" in anchor_columns
    assert roots["cell_target"]["training_pairs_columns"][-1] == "sample_weight"
    assert "training_points.csv" not in roots["c3_target"]["one_cell_files"]
    assert "anchor_point" not in roots["c3_target"]["global_anchor_contexts_columns"]
    assert "C3 process receives this root instead" in roots["c3_target"]["rule"]
    assert roots["sealed_scorer"]["consumer"] == "inner and outer scorer processes only"

    dag = contract["process_dag"]
    assert dag["stages"][0] == "pre_gate"
    assert dag["stages"][-1] == "terminal_publish"
    assert "score-free token" in dag["selection_token"]
    assert "fixed prediction_superset" in dag["inner_models"]

    schemas = contract["output_schemas"]
    assert set(schemas) == {
        "manifest.json",
        "oracle_inner_selection.csv",
        "oracle_scored_rows.csv",
        "oracle_cell_metrics.csv",
        "oracle_bootstrap_summary.csv",
        "oracle_influence_checks.csv",
        "oracle_ablation_scorecard.csv",
        "oracle_result.json",
        "failure.json",
    }
    assert "absolute_error" in schemas["oracle_scored_rows.csv"]
    assert "query_point" not in schemas["oracle_scored_rows.csv"]
    assert "anchor_point" not in schemas["oracle_scored_rows.csv"]

    accounting = contract["operation_accounting"]
    assert set(accounting["forbidden_zeros"]) == set(
        contract["capability_firewall"]["always_zero"]
    )
    assert "Nonzero historical fit" in accounting["authority_distinction"]
    assert contract["failure_precedence"]["terminal"].startswith(
        "Publish exactly the file set"
    )


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        json.loads('{"a": 1, "a": 2}', object_pairs_hook=_reject_duplicate_keys)
