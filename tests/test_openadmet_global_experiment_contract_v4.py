from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
V3_PATH = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "global_experiment_contract.json"
)
V4_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "global_experiment_contract_v4.json"
)
V3_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
V4_SHA256 = "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254"


def _bytes(path: Path) -> bytes:
    return path.read_bytes()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        assert key not in value, f"duplicate JSON key: {key}"
        value[key] = item
    return value


def _load(path: Path) -> dict[str, object]:
    value = json.loads(_bytes(path), object_pairs_hook=_unique_object)
    assert isinstance(value, dict)
    return value


def _contract() -> dict[str, object]:
    return _load(V4_PATH)


def test_v4_bytes_identity_parent_and_r3a_receipts_are_exact() -> None:
    contract = _contract()
    assert hashlib.sha256(_bytes(V3_PATH)).hexdigest() == V3_SHA256
    assert hashlib.sha256(_bytes(V4_PATH)).hexdigest() == V4_SHA256
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v4"
    )
    assert contract["gate"] == "R3B_GLOBAL_RUNNER_CONTRACT_V4_FROZEN"
    assert contract["status"] == "contract_only_not_implemented"
    assert contract["base_commit"] == (
        "57ff5f08d190566305977f491a4d3d4933ea716c"
    )
    parent = contract["parent"]
    assert parent["path"] == (
        "benchmarks/openadmet_cyp_2026/global_experiment_contract.json"
    )
    assert parent["sha256"] == V3_SHA256
    assert parent["immutable"] is True

    r3a = contract["accepted_r3a_feature_root"]
    assert r3a["canonical_build"] == 1
    assert r3a["manifest_sha256"] == (
        "32a950959ceca0641b56518e2059069a275ced64cf399d095aa5bce522c8026b"
    )
    assert r3a["feature_rows"] == {
        "path": "feature_rows.csv",
        "rows": 4905,
        "sha256": (
            "14260507a8fc6740e94dab848dc7fc87f1d45a57c2a2c67cfb2142fbea36cb30"
        ),
    }
    assert r3a["arrays"] == {
        "morgan_binary.npy": (
            "7e10e94b9f89c71d0d76951ebc27f9e0a8fd28e6cb7bc499560e759b6fee52f3"
        ),
        "maplight_morgan_count.npy": (
            "24c805df9dc7da5ca7d43e86161aa2862995cd818415ee083b6f6ba5ac493c14"
        ),
        "maplight_avalon_count.npy": (
            "368cb438d02127324f3471d21bf29e75e108bc0021f5fc50bfffb6ab841eed95"
        ),
        "maplight_erg.npy": (
            "24e70fdf07d1d7bb8bbb3ed54acd95b9734e847908ab5e99d6a454360d5a3504"
        ),
        "maplight_rdkit_descriptors.npy": (
            "4a85afd7340121e175691775b944bcc0c2d4f7765ea729565d0f3c885e8c9905"
        ),
    }


def test_fixed_maplight_and_complete_only_eligibility_supersede_v3_narrowly() -> None:
    contract = _contract()
    v3 = _load(V3_PATH)
    scope = contract["scope"]
    v3_population = v3["scope"]["population"]
    assert scope["molecules"] == v3_population["molecules"] == 4905
    assert scope["molecule_endpoint_cells"] == (
        v3_population["molecule_endpoint_cells"]
    ) == 19620
    assert scope["target_eligible_cells"] == (
        v3_population["finite_point_targets"]
    ) == 6525
    assert scope["target_ineligible_cells"] == (
        v3_population["missing_targets"]
    ) == 13095
    assert scope["official_states"] == {
        "complete": 6525,
        "partial": 0,
        "missing": 13095,
        "orphan_auxiliary": 0,
    }
    assert scope["target_eligibility"] == (
        "Eligible if and only if point_eligible is lowercase true, value_state "
        "is exactly complete, and point parses as a finite float. Partial, "
        "missing, and orphan_auxiliary rows are ineligible even when a point "
        "string is present."
    )
    assert "dynamic candidate selection" in contract["forbidden"]
    assert "partial target eligibility" in contract["forbidden"]

    fixed = contract["fixed_system"]
    assert fixed["predesignated_before_target_access"] == (
        "TRACE-G0-MAPL-FIXED"
    )
    assert fixed["comparators"] == [
        "TRACE-C1-MORGAN-CATBOOST",
        "TRACE-C0-ENDPOINT-MEDIAN",
        "TRACE-C2-MORGAN-1NN",
    ]
    assert "cannot be selected" in fixed["comparator_rule"]
    assert contract["supersedes"]["v3_dynamic_candidate_selection"].endswith(
        "Morgan CatBoost remains a required nonselecting comparator."
    )


def test_model_public_and_scorer_sealed_projection_are_disjoint() -> None:
    projection = _contract()["target_projection"]
    assert projection["inputs"] == {
        "direct_observations_sha256": (
            "00b1ac95cc73dda2699f2f05bc33200d1119a197d7a92ae900cde78d722f00b7"
        ),
        "group_folds_sha256": (
            "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"
        ),
        "direct_rows": 19620,
        "fold_rows": 73575,
    }
    public = projection["model_public_root"]
    sealed = projection["scorer_sealed_root"]
    assert public["path"] == "model-public"
    assert sealed["path"] == "scorer-sealed"
    assert public["manifest"] != sealed["manifest"]
    public_fields = public["manifest_schema"]["fields"]
    sealed_fields = sealed["manifest_schema"]["fields"]
    assert not any("truth" in field for field in public_fields)
    assert {"outer_truth", "inner_truth"} <= set(sealed_fields)
    assert set(public["forbidden_metadata"]) == {
        "truth path",
        "truth SHA256",
        "truth row count",
        "private audit path",
        "private audit SHA256",
        "score",
        "metric",
    }
    assert projection["public_accounting"] == {
        "truth_paths": 0,
        "truth_hashes": 0,
        "scores": 0,
        "metrics": 0,
    }
    assert projection["private_audit_receipt"]["consumer"].startswith(
        "Private audit/final manifest only"
    )

    outer = public["outer_targets"]
    inner = public["inner_targets"]
    assert (outer["files"], outer["total_rows"]) == (60, 78300)
    assert (inner["files"], inner["total_rows"]) == (240, 234900)
    assert outer["columns"] == ["observation_id", "molecule_id", "point"]
    assert inner["columns"] == outer["columns"]
    assert sealed["outer_truth"]["rows"] == 58860
    assert sealed["outer_truth"]["eligible_rows"] == 19575
    assert sealed["inner_truth"]["rows"] == 235440
    assert sealed["inner_truth"]["eligible_rows"] == 78300
    receipt = public["cell_target_receipt"]
    assert receipt["fields"] == {
        "stage": "enum outer|inner",
        "cell_id": "sha256",
        "endpoint": "endpoint enum",
        "repeat": "integer 0..2",
        "outer_fold": "integer 0..4",
        "inner_fold": "empty for outer or integer 0..3",
        "relative_path": "safe relative path",
        "sha256": "sha256",
        "rows": "nonnegative integer",
        "identity_sha256": "sha256",
    }
    assert "header-only zero-row file" in receipt["identity_material"]
    assert "projector alone proves" in projection["eligibility_proof"]
    assert "does not reopen observations" in projection["eligibility_proof"]


def test_preflight_is_complete_and_runs_before_every_fit() -> None:
    contract = _contract()
    preflight = contract["preflight"]
    assert preflight["timing"] == (
        "After target projection and before any model fit or prediction."
    )
    assert preflight["checks"] == {
        "outer_score_support_cells": {
            "records": 60,
            "minimum_components": 10,
        },
        "outer_training_populations": {
            "records": 60,
            "minimum_eligible_targets": 1,
        },
        "inner_training_populations": {
            "records": 240,
            "minimum_eligible_targets": 1,
        },
        "q90_residual_eligibility_populations": {
            "records": 60,
            "minimum_eligible_targets": 1,
        },
    }
    assert preflight["failure_reason_enum"] == [
        "OUTER_COMPONENT_SUPPORT",
        "OUTER_TRAINING_EMPTY",
        "INNER_TRAINING_EMPTY",
        "Q90_RESIDUAL_ELIGIBILITY_EMPTY",
    ]
    assert "before every fit" in preflight["status_rule"]
    assert "GLOBAL_FAILED, never underpowered" in preflight["status_rule"]
    assert "scorer-sealed root" in preflight["forbidden_inputs"]
    fit_budget = contract["runtime_and_models"]["fit_budget"]
    assert fit_budget == {
        "outer_morgan": 60,
        "outer_maplight": 60,
        "inner_maplight_after_outer_pass": 240,
        "outer_no_advantage_total": 120,
        "maximum_total": 360,
    }
    assert 60 + 60 == fit_budget["outer_no_advantage_total"]
    assert 60 + 60 + 240 == fit_budget["maximum_total"]


def test_runner_firewall_token_and_stage_specific_freezers_are_exact() -> None:
    contract = _contract()
    runner = contract["model_cell_runner"]
    assert runner["fresh_process_per_cell"] is True
    assert "inner_selection_token.json" in runner["inner_permitted"]
    assert {"scorer-sealed root", "private projection audit"} <= set(
        runner["forbidden"]
    )
    assert "outer assessment or score artifacts" in runner["forbidden"]
    assert runner["inner_behavior"] == (
        "Verify the minimal token and emit only fixed MapLight; one fit."
    )
    assert "unique observation_id" in runner["target_validation"]
    assert "structural training membership" in runner["target_validation"]

    cell_rule = contract["cell_identity"]
    assert cell_rule["component_rule"] == (
        "Every artifact component_id is exactly the model_rows "
        "similarity_component_hash for that molecule; no alias, recomputation, "
        "or alternate component field is allowed."
    )
    assert cell_rule["inner_none_token"] == "none"

    token = contract["score_artifacts"]["inner_selection_token.json"]
    assert token["fields"] == {
        "schema_version": "const",
        "contract_sha256": "sha256",
        "token_writer_source_sha256": "sha256",
        "outer_assessment_sha256": "sha256",
        "selected_system_id": "const TRACE-G0-MAPL-FIXED",
        "outer_outcome": "const PASS",
        "authority": "exact INHERITED_ONLY authority",
    }
    assert token["rule"].endswith(
        "emits no metric, score, interval, comparison, influence, or target field."
    )

    freezers = contract["prediction_freezers"]
    outer = freezers["outer"]
    inner = freezers["inner"]
    assert (outer["cell_receipts"], outer["rows"], outer["systems"]) == (
        60,
        235440,
        4,
    )
    assert (inner["cell_receipts"], inner["rows"], inner["systems"]) == (
        240,
        235440,
        1,
    )
    outer_fields = outer["manifest_schema"]["fields"]
    inner_fields = inner["manifest_schema"]["fields"]
    assert "inner_selection_token_sha256" not in outer_fields
    assert "inner_selection_token_sha256" in inner_fields
    assert set(outer["forbidden_fields"]) == {
        "selection receipt",
        "selection token",
        "truth receipt",
        "score",
    }
    assert freezers["firewall"].endswith(
        "open no target, private audit, truth, or score artifact."
    )


def test_fixed_outer_assessment_bootstrap_and_q90_are_mechanical() -> None:
    contract = _contract()
    scoring = contract["scoring"]
    bootstrap = scoring["bootstrap"]
    assert bootstrap["rng"] == (
        "numpy.random.Generator(numpy.random.PCG64(20260819)) in NumPy 1.25.2"
    )
    assert bootstrap["accepted"] == 2000
    assert bootstrap["maximum_attempts"] == 20000
    assert bootstrap["accept_draw"] == (
        "Consume every draw. Accept it only when every system, endpoint, and "
        "repeat has positive sampled eligible-component multiplicity and a "
        "finite macro."
    )
    assert bootstrap["weighted_macro"] == (
        "For each system, endpoint, and repeat compute math.fsum(multiplicity*"
        "component_mean_error) divided by math.fsum(multiplicity) over eligible "
        "components, then equally average the twelve endpoint-repeat values "
        "with math.fsum divided by 12."
    )
    assert bootstrap["point_delta"] == (
        "For each fixed comparison, the unbootstrapped point_delta is the "
        "comparator's complete twelve-cell primary macro minus "
        "TRACE-G0-MAPL-FIXED's complete twelve-cell primary macro."
    )
    assert bootstrap["attempt_exhaustion"] == (
        "Fewer than 2,000 accepted replicates after exactly 20,000 attempts is "
        "GLOBAL_FAILED."
    )
    assert bootstrap["comparison_order"] == [
        "MORGAN_MINUS_MAPLIGHT",
        "MEDIAN_MINUS_MAPLIGHT",
        "ONE_NN_MINUS_MAPLIGHT",
    ]
    assert "no restart" in bootstrap["reuse"]
    assert scoring["outer_pass"] == [
        "lower_95 > 0 for MORGAN_MINUS_MAPLIGHT",
        "lower_95 > 0 for MEDIAN_MINUS_MAPLIGHT",
        "lower_95 > 0 for ONE_NN_MINUS_MAPLIGHT",
        "median-minus-MapLight repeat-fold delta > 0 in at least 12 of 15 cells",
        "1NN-minus-MapLight repeat-fold delta > 0 in at least 12 of 15 cells",
        "for every endpoint mean over repeats of MapLight MAE minus median MAE <= 0.05",
        "all three top-ten influence checks preserve strictly positive point direction",
        "outer predictions complete and finite",
    ]
    assert scoring["outer_outcome"].endswith(
        "stop before inner token, inner fits, inner predictions, q90, or completion."
    )
    assert "never rerun bootstrap" in scoring["influence"]

    q90 = scoring["q90"]
    assert q90["contexts"] == 60
    assert q90["fallback"] == "None; pooling is forbidden"
    assert q90["post_preflight_failure"] == (
        "Any missing, empty, nonfinite, or mismatched residual population is "
        "GLOBAL_FAILED"
    )
    assert "no interpolation" in q90["statistic"]
    bootstrap_output = contract["score_artifacts"][
        "global_bootstrap_summary.csv"
    ]
    assert bootstrap_output["rows"] == 3
    assert bootstrap_output["order"] == bootstrap["comparison_order"]
    assert bootstrap_output["candidate_system_id"] == "TRACE-G0-MAPL-FIXED"
    score_artifacts = contract["score_artifacts"]
    assert score_artifacts["global_endpoint_loss_checks.csv"] == {
        "columns": [
            "endpoint",
            "maplight_component_macro_mae",
            "median_component_macro_mae",
            "maplight_minus_median",
            "passes_loss_cap",
        ],
        "rows": 4,
        "order": "endpoint",
    }
    assert score_artifacts["global_influence_checks.csv"]["rows"] == 30
    assessment = score_artifacts["global_outer_assessment.json"]
    for receipt in (
        "cell_metrics_sha256",
        "bootstrap_summary_sha256",
        "endpoint_loss_checks_sha256",
        "influence_checks_sha256",
    ):
        assert assessment["fields"][receipt] == "sha256"
    assert assessment["outer_criteria"]["endpoint_loss_pass"] == (
        "boolean derived from four bound CSV rows"
    )
    assert assessment["outer_criteria"]["influence_pass"] == (
        "boolean derived from thirty bound CSV rows"
    )


def test_named_nested_schemas_close_all_result_objects() -> None:
    contract = _contract()
    schemas = contract["nested_object_schemas"]
    assert set(schemas) == {
        "projection_input_receipts",
        "eligibility_counts",
        "preflight_checks",
        "catboost_resolved_parameter",
        "cell_counts",
        "outer_freeze_counts",
        "inner_freeze_counts",
        "outer_assessment_counts",
        "terminal_runtime",
        "terminal_accepted_r3a_receipts",
        "output_receipt",
        "terminal_output_receipts",
        "terminal_resolved_catboost_parameters",
        "terminal_seeds",
    }
    eligibility = schemas["eligibility_counts"]
    assert eligibility["official"] == {
        "direct_rows": 19620, "eligible": 6525, "ineligible": 13095,
        "complete": 6525, "partial": 0, "missing": 13095,
        "orphan_auxiliary": 0, "outer_target_files": 60,
        "inner_target_files": 240, "outer_target_rows": 78300,
        "inner_target_rows": 234900, "outer_truth_rows": 58860,
        "inner_truth_rows": 235440, "outer_truth_eligible": 19575,
        "inner_truth_eligible": 78300,
    }
    checks = schemas["preflight_checks"]
    assert set(checks["fields"]) == {
        "outer_score_support_cells", "outer_training_populations",
        "inner_training_populations", "q90_residual_eligibility_populations",
    }
    assert contract["preflight"]["receipt_schema"]["fields"]["checks"] == (
        "exact preflight_checks"
    )
    assert set(schemas["catboost_resolved_parameter"]["fields"]) == {
        "system_id", "canonical_get_all_params_json",
        "canonical_get_all_params_sha256",
    }
    projection = contract["target_projection"]["private_audit_receipt"]["fields"]
    assert projection["input_receipts"] == "exact projection_input_receipts"
    assert projection["eligibility_counts"] == "exact eligibility_counts"
    assert contract["model_cell_runner"]["cell_receipt_schema"]["fields"][
        "resolved_catboost_parameters"
    ] == "ordered catboost_resolved_parameter records"
    freezers = contract["prediction_freezers"]
    assert freezers["outer"]["manifest_schema"]["fields"]["counts"] == (
        "exact outer_freeze_counts"
    )
    assert freezers["inner"]["manifest_schema"]["fields"]["counts"] == (
        "exact inner_freeze_counts"
    )
    assert schemas["outer_assessment_counts"]["fields"]["attempts"] == (
        "integer 2000..20000"
    )
    fields = contract["terminal_schemas"]["manifest.json"]["fields"]
    for field, name in {
        "runtime": "terminal_runtime",
        "accepted_r3a_receipts": "terminal_accepted_r3a_receipts",
        "output_receipts": "terminal_output_receipts",
        "resolved_catboost_parameters": "terminal_resolved_catboost_parameters",
        "seeds": "terminal_seeds",
    }.items():
        assert fields[field] == f"exact {name}"
    assert schemas["terminal_output_receipts"]["status_counts"] == {
        "GLOBAL_UNDERPOWERED": 1,
        "GLOBAL_NO_ADVANTAGE": 8,
        "GLOBAL_EXPERT_FROZEN": 14,
    }
    assert schemas["terminal_seeds"]["fields"] == {
        "fold_seeds": "const [20260810,20260811,20260812]",
        "catboost_random_seed": "const 1",
        "bootstrap_seed": "const 20260819",
    }


def test_terminal_schemas_output_sets_and_source_digest_are_exact() -> None:
    contract = _contract()
    outputs = contract["publication"]["terminal_output_sets"]
    assert outputs["GLOBAL_FAILED"] == ["failure_receipt.json"]
    assert outputs["GLOBAL_UNDERPOWERED"] == [
        "global_result.json",
        "manifest.json",
    ]
    assert "global_inner_oof_predictions.csv" not in outputs[
        "GLOBAL_NO_ADVANTAGE"
    ]
    assert "inner_selection_token.json" not in outputs["GLOBAL_NO_ADVANTAGE"]
    assert "global_endpoint_loss_checks.csv" in outputs["GLOBAL_NO_ADVANTAGE"]
    assert "global_influence_checks.csv" in outputs["GLOBAL_NO_ADVANTAGE"]
    assert outputs["GLOBAL_EXPERT_FROZEN"] == [
        "global_oof_predictions.csv",
        "global_oof_freeze_manifest.json",
        "global_cell_metrics.csv",
        "global_bootstrap_summary.csv",
        "global_endpoint_loss_checks.csv",
        "global_influence_checks.csv",
        "global_outer_assessment.json",
        "inner_selection_token.json",
        "global_inner_oof_predictions.csv",
        "global_inner_oof_freeze_manifest.json",
        "global_uncertainty_calibration.csv",
        "parent_state_completion_outer_training.csv",
        "parent_state_completion_final.csv",
        "global_result.json",
        "manifest.json",
    ]

    schemas = contract["terminal_schemas"]
    result = schemas["global_result.json"]
    assert result["schema_version"] == (
        "cypshift.openadmet_cyp_2026.r3b_global_result.v1"
    )
    assert result["terminal_receipts"] == {
        "outer_freeze_manifest_sha256": "sha256 or empty sentinel",
        "outer_assessment_sha256": "sha256 or empty sentinel",
        "inner_selection_token_sha256": "sha256 or empty sentinel",
        "inner_freeze_manifest_sha256": "sha256 or empty sentinel",
    }
    assert result["sentinels"] == (
        "Unavailable receipt strings are empty and unavailable booleans/counts "
        "are false/0."
    )
    assert schemas["failure_receipt.json"]["fields"][
        "partial_outputs_published"
    ] == "const false"
    assert schemas["failure_receipt.json"]["fields"][
        "verified_input_receipts"
    ] == "exact verified_input_receipts with unverified empty"
    assert set(schemas["failure_receipt.json"]["stage_enum"]) == {
        "projection",
        "preflight",
        "outer_model",
        "outer_freeze",
        "outer_score",
        "inner_token",
        "inner_model",
        "inner_freeze",
        "final_score",
        "terminal_publish",
    }

    completion = contract["completion"]
    assert completion["source_prediction_sha256_material"] == (
        "Exact UTF-8 bytes global_oof_predictions_sha256|molecule_id|endpoint, "
        "where the first token is the lowercase SHA256 of the frozen outer CSV "
        "and endpoint is one fixed endpoint token."
    )
    assert completion["expert_counts"] == {
        "outer": {
            "rows": 235440,
            "measured_point": 78300,
            "global_oof_completed": 157140,
            "unavailable": 0,
        },
        "final": {
            "rows": 19620,
            "measured_point": 6525,
            "global_oof_completed": 13095,
            "unavailable": 0,
        },
        "combined": {
            "rows": 255060,
            "measured_point": 84825,
            "global_oof_completed": 170235,
            "unavailable": 0,
        },
    }

    terminal = contract["terminal_objects"]
    assert list(terminal["verified_input_receipts"]) == [
        "parent_contract_sha256",
        "direct_observations_sha256",
        "group_folds_sha256",
        "r3a_feature_manifest_sha256",
        "model_public_manifest_sha256",
        "sealed_truth_manifest_sha256",
        "private_projection_audit_sha256",
        "preflight_receipt_sha256",
    ]
    assert set(terminal["implementation_source_receipts"]) == {
        "projector",
        "preflight",
        "cell_runner",
        "freezer",
        "outer_scorer",
        "token_writer",
        "final_scorer",
        "terminal_writer",
    }
    status_counts = terminal["status_counts"]
    assert status_counts["GLOBAL_UNDERPOWERED"] == {
        key: 0 for key in terminal["count_fields"]
    }
    assert status_counts["GLOBAL_NO_ADVANTAGE"] == {
        "outer_morgan_fits": 60,
        "outer_maplight_fits": 60,
        "inner_maplight_fits": 0,
        "outer_prediction_rows": 235440,
        "inner_prediction_rows": 0,
        "bootstrap_replicates": 2000,
        "q90_contexts": 0,
        "outer_completion_rows": 0,
        "final_completion_rows": 0,
    }
    assert status_counts["GLOBAL_EXPERT_FROZEN"]["inner_maplight_fits"] == 240
    assert status_counts["GLOBAL_EXPERT_FROZEN"]["q90_contexts"] == 60
    status_accounting = terminal["status_accounting"]
    assert set(status_accounting) == {
        "GLOBAL_UNDERPOWERED",
        "GLOBAL_NO_ADVANTAGE",
        "GLOBAL_EXPERT_FROZEN",
    }
    assert all(
        set(accounting) == set(terminal["accounting_fields"])
        for accounting in status_accounting.values()
    )
    assert status_accounting["GLOBAL_NO_ADVANTAGE"]["sealed_truth_files_opened"] == 1
    assert status_accounting["GLOBAL_EXPERT_FROZEN"]["sealed_truth_files_opened"] == 3
    assert status_accounting["GLOBAL_EXPERT_FROZEN"]["provisional_metric_rows"] == 337
    assert terminal["completion_counts"]["expert"] == {
        "outer_rows": 235440,
        "final_rows": 19620,
        "measured_point": 84825,
        "global_oof_completed": 170235,
        "unavailable": 0,
    }
    assert terminal["uncertainty_counts"]["expert_constraints"] == [
        "contexts=60",
        "within_frozen_range+diagnostic_only=60",
    ]
    manifest_fields = schemas["manifest.json"]["fields"]
    assert manifest_fields["verified_input_receipts"] == (
        "exact verified_input_receipts"
    )
    assert manifest_fields["implementation_source_receipts"] == (
        "exact implementation_source_receipts"
    )
    assert manifest_fields["accounting"] == "exact accounting_fields object"


def test_single_publication_status_and_boolean_authority_are_exact() -> None:
    contract = _contract()
    publication = contract["publication"]
    assert publication["run_staging"].startswith(
        "Create one unpublished top-level run staging root."
    )
    assert "publish once with Linux renameat2(RENAME_NOREPLACE)" in publication[
        "terminal_promotion"
    ]
    assert "No rename/copy/replace/check-then-move fallback" in publication[
        "terminal_promotion"
    ]
    assert "on every non-success clean them before" in publication[
        "private_cleanup"
    ]
    statuses = contract["status_arithmetic"]
    assert statuses["precedence"] == [
        "GLOBAL_FAILED",
        "GLOBAL_UNDERPOWERED",
        "GLOBAL_NO_ADVANTAGE",
        "GLOBAL_EXPERT_FROZEN",
    ]
    assert "preflight failure only" in statuses["GLOBAL_UNDERPOWERED"]
    assert "stop before inner token or fit" in statuses["GLOBAL_NO_ADVANTAGE"]

    authority = contract["authority"]
    keys = authority["keys"]
    inherited = authority["INHERITED_ONLY"]
    no_advantage = authority["GLOBAL_NO_ADVANTAGE"]
    expert = authority["GLOBAL_EXPERT_FROZEN"]
    assert list(inherited) == list(no_advantage) == list(expert) == keys
    assert all(type(value) is bool for state in (inherited, no_advantage, expert) for value in state.values())
    inherited_true = {
        "fold_assignments",
        "episodes",
        "episode_labels",
        "topology_viability",
    }
    outer_true = inherited_true | {
        "global_surrogate_validation",
        "internal_surrogate_metrics",
        "global_oof_predictions",
    }
    expert_true = outer_true | {
        "inner_oof_predictions",
        "parent_state_completion",
    }
    assert {key for key, value in inherited.items() if value} == inherited_true
    assert {key for key, value in no_advantage.items() if value} == outer_true
    assert {key for key, value in expert.items() if value} == expert_true
    assert inherited["global_model"] is False
    assert no_advantage["global_model"] is False
    assert expert["global_model"] is False
    assert "fits no deployable or full-training model" in authority["rules"]


def test_synthetic_boundary_grants_no_r3_authority_or_official_access() -> None:
    contract = _contract()
    synthetic = contract["synthetic_boundary"]
    assert synthetic["authority"] == "INHERITED_ONLY"
    assert "Production CLI exposes no relaxation" in synthetic["private_api"]
    for key in (
        "official_files_opened",
        "official_feature_roots_opened",
        "official_target_projections",
        "scientific_fits",
        "scientific_metrics",
    ):
        assert synthetic[key] == 0
    assert all(value == 0 for value in contract["final_accounting_zeros"].values())
    acceptance = contract["r3b_acceptance"]
    assert acceptance["gate_after_review"] == (
        "R3B_GLOBAL_RUNNER_SYNTHETIC_ACCEPTED"
    )
    assert acceptance["official_execution_authorized"] is False
    assert "model access to truth metadata" in contract["forbidden"]
    assert "inner access to outer scores" in contract["forbidden"]
    assert "post-preflight underpowered classification" in contract["forbidden"]
    assert "multiple public promotions" in contract["forbidden"]
