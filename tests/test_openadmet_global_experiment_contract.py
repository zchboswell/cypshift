from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONTRACT_PATH = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "global_experiment_contract.json"
)


def load_contract() -> dict[str, object]:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_r3_contract_identity_and_receipts_are_frozen() -> None:
    contract = load_contract()
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v1"
    )
    assert contract["freeze_date"] == "2026-08-18"
    assert contract["gate"] == "R3_GLOBAL_EXPERIMENT_CONTRACT_FROZEN"
    assert contract["status"] == "contract_only_not_implemented"
    assert contract["base_commit"] == "291ad3274e0cb1188189d314f6063eac32429028"
    inputs = contract["inputs"]
    assert inputs["validation_contract"] == {
        "path": "benchmarks/openadmet_cyp_2026/validation_contract.json",
        "schema_version": "cypshift.openadmet_cyp_2026.validation_contract.v4",
        "sha256": "ada8beff0b6f42baeb61c91df1cbb75ef832ce2b1b87b0d0bcbf253c94326ab3",
    }
    assert inputs["r2b_manifest"] == {
        "schema_version": "cypshift.openadmet_cyp_2026.validation_artifacts.v1",
        "sha256": "08dcf61cded99fae046bff49b57b0c4a12082cd8714c779ac44a351bf1a0c8c8",
    }
    assert inputs["direct_observations"]["sha256"] == (
        "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7"
    )
    assert inputs["group_folds"]["sha256"] == (
        "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"
    )
    assert inputs["maplight_method"] == {
        "source_contract_sha256": "a2a608e327cd7adc5e54f24edbcb41007ef03313c26db582f37c9d85836b23a8",
        "stage_a_contract_sha256": "e20985ecabb1aa9ceaeddc3f81ad15dc60b194e250e28de934c12a6bfb10f710",
        "signed_int8_contract_sha256": "ace395a195016854f81c96777921a2fad4c2f638927d2ad15c452b5ecd915ea8",
        "nan_contract_sha256": "52f01f93470cfe461e7ee9fed0ff3a06d7362aceaef343da0c5840d2a74bea09",
        "uv_lock_sha256": "99e72821b69d9bb943a6e32adc7e0dec0e46c6d32df090241d4fb9296a4195d8",
    }


def test_r3_is_global_only_and_target_semantics_are_central_points() -> None:
    contract = load_contract()
    scope = contract["scope"]
    assert scope["protocol"] == "GLOBAL_FAMILY_HOLDOUT"
    assert scope["group_unit"].startswith("unchanged D-032")
    assert scope["endpoints"] == ["CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"]
    assert scope["target"] == "reported central direct pIC50 point"
    assert scope["population"] == {
        "molecules": 4905,
        "molecule_endpoint_cells": 19620,
        "finite_point_targets": 6525,
        "missing_targets": 13095,
        "partial_targets": 0,
        "orphan_auxiliary_targets": 0,
        "prediction_rule": "Predict all 19,620 molecule-endpoint cells in each repeat; score only the 6,525 finite point targets.",
    }
    assert "finite reported point only" in scope["target_eligibility"]
    assert "interval midpoints" in scope["measurement_policy"]
    assert scope["folds"] == {
        "repeats": 3,
        "repeat_seeds": [20260810, 20260811, 20260812],
        "outer_folds": 5,
        "inner_folds": 4,
        "outer_scope_pattern": "openadmet-direct-outer-v1",
        "inner_scope_pattern": "openadmet-direct-inner-v1|outer=<outer_fold>",
        "assignment": "Read the accepted R2B group_folds artifact; never regenerate topology, reassign a component, or use endpoint availability to choose a fold.",
        "holdout_rule": "Every molecule, exact duplicate, and D-032 component remains wholly outside its outer validation fold; no anchor is exposed.",
        "inner_rule": "Inner folds are created only inside each outer training population with the declared scoped seed and never read outer-validation labels.",
        "shared_assignments": "The same component assignment is used for all four endpoints and every system.",
    }
    deferred = scope["deferred_protocols"]
    assert "ANCHOR_EXPANSION_HOLDOUT" in deferred
    assert "all structural transformation and oracle experiments" in deferred
    assert "episode-specific anchor-inclusive global refits" in deferred
    assert "TDI and TDI-TRACE" in deferred


def test_r3_systems_and_cpu_maplight_gate_are_exact() -> None:
    contract = load_contract()
    assert "sole eligible learned candidate" in contract["systems"]["selection_policy"]
    assert contract["systems"]["learned_runtime"] == (
        "Both learned candidates run in the same Linux x86_64 CPU "
        "environment pinned by research/maplight-fixed/uv.lock with "
        "CatBoost 1.2.1; record the resolved defaults and package versions "
        "in the manifest."
    )
    systems = contract["systems"]["systems"]
    assert [system["id"] for system in systems] == [
        "TRACE-C0-ENDPOINT-MEDIAN",
        "TRACE-C1-MORGAN-CATBOOST",
        "TRACE-G0-MAPL-FIXED",
        "TRACE-C2-MORGAN-1NN",
    ]
    morgan = systems[1]
    assert morgan["features"].startswith("D-032 chiral binary Morgan/ECFP4")
    assert morgan["estimator"] == "catboost.CatBoostRegressor"
    assert morgan["constructor_arguments"] == {
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": 1,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
    }
    assert "nan_mode" in morgan["omitted_arguments"]
    maplight = systems[2]
    assert maplight["features"].startswith("MapLight fixed 2563-column")
    assert maplight["constructor_arguments"] == morgan["constructor_arguments"]
    assert "Leave nan_mode unset" in maplight["nan_policy"]
    nn = systems[3]
    assert "exactly one" in nn["rule"]
    assert "maximum Morgan/Tanimoto" in nn["rule"]
    assert "molecule_id ascending" in nn["rule"]
    assert "top-k averaging" in nn["support"]
    assert contract["systems"]["forbidden_candidates"] == [
        "Ridge",
        "generic fingerprint-difference model",
        "GIN or pretrained molecular weights",
        "broad hyperparameter search",
        "auxiliary assay targets",
        "ensemble or stack",
    ]
    linux = contract["maplight_linux_gate"]
    assert linux["required_before_features_or_fits"] is True
    assert linux["platform"] == "Linux x86_64 CPU"
    assert "signed-int8" in linux["overlay"]
    assert "NaN" in linux["overlay"]
    assert "cross-platform byte identity" in linux["claim_boundary"]
    assert "old macOS/TDC" in linux["claim_boundary"]
    assert "continue with Morgan as the only eligible learned candidate" in linux[
        "failure"
    ]


def test_r3_firewall_oof_completion_uncertainty_and_budget_are_pinned() -> None:
    contract = load_contract()
    firewall = contract["process_firewall"]
    assert "accepted direct_observations.csv" in firewall["trusted_target_projector"]["may_resolve"]
    assert "accepted group_folds.csv" in firewall["trusted_target_projector"]["may_resolve"]
    assert "low/high/std fields" in firewall["trusted_target_projector"]["must_not_emit_to_feature_or_model_process"]
    assert "any target file" in firewall["feature_process"]["must_not_resolve"]
    assert "outer-validation targets" in firewall["model_process"]["must_not_resolve"]
    assert "outer OOF predictions before" in firewall["model_process"]["prediction_freeze"]
    assert "inner OOF predictions before" in firewall["model_process"]["prediction_freeze"]
    oof = contract["oof_artifacts"]
    expected_columns = [
        "molecule_id", "endpoint", "component_id", "repeat", "outer_fold",
        "inner_fold", "scope", "prediction", "applicability_score", "model_id",
        "feature_spec_id", "split_id",
    ]
    assert oof["outer"]["columns"] == expected_columns
    assert oof["inner"]["columns"] == expected_columns
    assert oof["outer"]["inner_fold_value"] is None
    assert oof["outer"]["scope"] == "openadmet-direct-outer-v1"
    assert oof["inner"]["scope"] == "openadmet-direct-inner-v1|outer=<outer_fold>"
    assert oof["outer"]["row_count"] == 235440
    assert oof["inner"]["row_count"] == 235440
    assert contract["required_outputs_after_implementation"] == [
        "linux_compatibility_receipt.json",
        "feature_rows.csv",
        "feature_manifest.json",
        "maplight feature arrays (only if TRACE-G0-MAPL-FIXED remains eligible)",
        "target_projection_manifest.json",
        "global_oof_predictions.csv",
        "global_inner_oof_predictions.csv",
        "parent_state_completion_outer_training.csv",
        "parent_state_completion_final.csv",
        "global_cell_metrics.csv",
        "global_bootstrap_summary.csv",
        "global_uncertainty_calibration.csv with one selected-winner q90 row per repeat, outer fold, and endpoint",
        "global_result.json",
        "manifest.json",
    ]
    completion = contract["completion_and_uncertainty"]
    assert completion["completion_states"] == [
        "measured_point", "global_oof_completed", "unavailable"
    ]
    assert completion["priority"] == [
        "finite measured central point",
        "matching frozen OOF global prediction",
        "unavailable",
    ]
    assert "matching inner-OOF prediction" in completion["outer_training_completion"]
    assert "arithmetic mean of the selected winner's three outer-OOF predictions" in (
        completion["final_completion"]
    )
    assert "interval midpoint" in completion["interval_policy"]
    assert completion["uncertainty"] == {
        "method": "q90 of absolute residuals from the selected winner's inner OOF predictions",
        "grouping": "Compute separately within each repeat, outer context, and endpoint from that context's inner-OOF residuals using component-equal weighting; each component contributes equal total mass before q90 is taken.",
        "conditioning": "No learned conditioning or deep ensemble. Applicability is reported separately.",
        "fallback": "Use the endpoint q90 from the available inner OOF residuals; fail closed if no finite residual exists.",
        "diagnostic_band": "prediction plus or minus q90 is a symmetric diagnostic band, never a confidence, credible, or official scoring interval.",
        "calibration_rule": "Report component-weighted coverage and width. Coverage outside [0.80,0.98] sets UNCERTAINTY_DIAGNOSTIC_ONLY and forbids later uncertainty-driven gating without invalidating the point predictor.",
    }
    budget = contract["budget"]
    assert budget["outer_learned_fits"] == 120
    assert budget["outer_fit_breakdown"] == {"Morgan": 60, "MapLight": 60}
    assert budget["inner_winner_fits"] == 240
    assert budget["maximum_total_model_fits"] == 360
    assert budget["gpu_fits"] == 0


def test_r3_metric_bootstrap_acceptance_and_authority_are_frozen() -> None:
    contract = load_contract()
    evaluation = contract["evaluation"]
    assert evaluation["primary_metric"] == "provisional_component_macro_MAE"
    assert evaluation["repeat_fold_cell_definition"] == (
        "For each repeat and outer fold, compute the unweighted mean of the "
        "per-endpoint component-macro MAEs over the endpoints with at least "
        "one scored component in that cell."
    )
    assert "official ST-RAE" in evaluation["blocked_names"]
    assert "interval-hit" in evaluation["blocked_names"]
    bootstrap = evaluation["bootstrap"]
    assert bootstrap["unit"] == "full D-032 component shared across endpoints and repeats"
    assert bootstrap["method"].startswith("paired synchronized component bootstrap")
    assert bootstrap["replicates"] == 2000
    assert bootstrap["seed"] == 20260819
    assert bootstrap["maximum_attempts"] == 20000
    assert "Morgan MAE minus MapLight MAE" in bootstrap["comparisons"]
    acceptance = contract["acceptance"]
    assert "Linux MapLight overlay passes" in acceptance["pre_fit"][1]
    assert "MapLight is ineligible" in acceptance["candidate_selection"]
    assert acceptance["winner"] == [
        "positive bootstrap lower bound for endpoint-median MAE minus selected-winner MAE",
        "positive bootstrap lower bound for one-nearest-neighbor MAE minus selected-winner MAE",
        "positive control-MAE-minus-winner-MAE delta in at least 12 of 15 repeat-fold macro cells for each control",
        "no endpoint exceeds the predeclared loss cap of 0.05 pIC50 MAE versus the endpoint median",
        "top-10 component contribution leave-one-out stability preserves the winner and every required comparison direction",
        "complete finite outer predictions, inner predictions, and parent completion states",
    ]
    assert set(acceptance["statuses"]) == {
        "GLOBAL_FAILED", "GLOBAL_UNDERPOWERED", "GLOBAL_NO_ADVANTAGE",
        "GLOBAL_EXPERT_FROZEN",
    }
    assert acceptance["next_gate"] == "R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN"
    assert contract["authority"] == {
        "global_surrogate_validation": False,
        "global_model": False,
        "internal_surrogate_metrics": False,
        "global_oof_predictions": False,
        "parent_state_completion": False,
        "official_st_rae": False,
        "submissions": False,
        "tdi": False,
        "transduction": False,
        "inherited_r2b_authority": {
            "fold_assignments": True,
            "episodes": True,
            "episode_labels": True,
            "topology_viability": True,
        },
        "status_note": "All R3-added authority remains denied until reviewed implementation and evidence pass. Accepted R2B artifact authority is inherited unchanged, not revoked or expanded.",
    }
    after = contract["authority_after_successful_r3"]
    assert after["global_surrogate_validation"] is True
    assert after["global_model"] is True
    assert after["internal_surrogate_metrics"] is True
    assert after["global_oof_predictions"] is True
    assert after["parent_state_completion"] is True
    assert after["official_st_rae"] is False
    assert after["validation_frozen"] is False
    assert after["submissions"] is False
    assert after["tdi"] is False
    assert after["transduction"] is False
    assert after["anchor_expansion"] is False
    assert after["transformations"] is False
    assert "episode-specific fits or predictions" in contract["forbidden"]
    assert "official ST-RAE or interval-hit implementation" in contract["forbidden"]
