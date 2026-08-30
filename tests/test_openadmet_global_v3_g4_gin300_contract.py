from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "openadmet_cyp_2026"
CONTRACT = BENCHMARK / "global_v3_g4_gin300_contract.json"
CONTRACT_SHA256 = "b48dc0c39c12b06cdd99693539cca18b99c73d8b801e81a416e52a798df8fd4e"

TOP_LEVEL_KEYS = {
    "schema_version",
    "recorded_at_utc",
    "freeze_date",
    "gate",
    "status",
    "contract_id",
    "experiment_id",
    "base_commit",
    "purpose",
    "hypothesis",
    "targeted_failure",
    "occam_boundary",
    "distinctness_and_closed_lane_boundary",
    "parents",
    "accepted_receipt_strings",
    "challenge_rules_snapshot",
    "pretrained_eligibility_gate",
    "historical_support_only",
    "population_and_splits",
    "feature_contract",
    "control_contract",
    "runtime_contract",
    "model_contract",
    "fit_prediction_metric_budget",
    "capability_and_stage_contract",
    "development_evaluation",
    "resource_ceiling",
    "resource_feasibility_gate",
    "terminal_statuses",
    "milestone_sequence",
    "current_milestone_accounting",
    "current_authority",
    "next_gate",
}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_load(raw: bytes) -> dict[str, Any]:
    value = json.loads(
        raw,
        object_pairs_hook=_reject_duplicates,
        parse_constant=_reject_constant,
    )
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _load() -> dict[str, Any]:
    return _strict_load(CONTRACT.read_bytes())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_contract_is_strict_canonical_json_with_exact_schema_and_identity() -> None:
    raw = CONTRACT.read_bytes()
    contract = _strict_load(raw)

    assert hashlib.sha256(raw).hexdigest() == CONTRACT_SHA256
    assert raw == (
        json.dumps(contract, ensure_ascii=False, allow_nan=False, indent=2).encode()
        + b"\n"
    )
    assert set(contract) == TOP_LEVEL_KEYS
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_v3_g4_gin300_contract.v1"
    )
    assert contract["gate"] == "G3_1_EXP_G4_GIN300_CONTRACT_FROZEN"
    assert contract["status"] == contract["gate"]
    assert contract["contract_id"] == "GLOBAL_V3_G4_GIN300"
    assert contract["experiment_id"] == "EXP-G4-GIN300"
    assert contract["base_commit"] == ("d029bb3b154f1721d094dae76e5587c0c927da2e")

    with pytest.raises(ValueError, match="duplicate JSON key"):
        _strict_load(b'{"status":"a","status":"b"}')
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        _strict_load(b'{"value":NaN}')


def test_contract_binds_exact_live_public_parents_and_rules_snapshot() -> None:
    contract = _load()
    parents = contract["parents"]
    assert set(parents) == {
        "challenge_contract",
        "global_v2_contract",
        "fixed_maplight_reproduction",
        "g2_7g_underpowered",
        "maplight_source_contract",
        "maplight_gin_contract",
        "maplight_gin_stage_b_contract",
        "historical_gin_report",
    }
    for receipt in parents.values():
        assert set(receipt) == {"path", "sha256"}
        path = (BENCHMARK / receipt["path"]).resolve()
        path.relative_to(ROOT)
        assert path.is_file()
        assert _sha256(path) == receipt["sha256"]

    receipts = contract["accepted_receipt_strings"]
    assert set(receipts) == {
        "dataset_revision",
        "direct_observations_sha256",
        "group_folds_sha256",
        "r2b_manifest_sha256",
        "r3a_feature_manifest_sha256",
        "feature_rows_sha256",
        "maplight_rdkit_descriptors_sha256",
        "fixed_maplight_outer_oof_sha256",
        "read_boundary",
    }
    assert receipts["dataset_revision"] == ("85f8b358d0a2056a98b990dd75d3b3ec9247862b")
    assert receipts["group_folds_sha256"] == (
        "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"
    )
    assert "opens no official" in receipts["read_boundary"]

    rules = contract["challenge_rules_snapshot"]
    assert set(rules) == {
        "space_revision",
        "config_path",
        "config_git_blob",
        "config_sha256",
        "submission_path",
        "submission_git_blob",
        "permission",
        "method_report",
        "refresh_rule",
    }
    assert rules["space_revision"] == ("4a87b2dcc800036b745e4c7bbb0023be817b5408")
    assert rules["config_sha256"] == (
        "342cd287e63a79c61b8e18fa46e81950ebb7333b6e91ee427af18426e04ca52f"
    )
    assert "permit external data and pretrained models" in rules["permission"]
    assert "grants no portal or upload authority" in rules["refresh_rule"]


def test_pretrained_rights_lineage_and_unknown_overlap_are_fail_closed() -> None:
    gate = _load()["pretrained_eligibility_gate"]
    assert set(gate) == {
        "supported_claim",
        "forbidden_claims",
        "snap",
        "dgl_lifesci",
        "molfeat",
        "pretraining_lineage",
        "future_provenance_parity",
        "redistribution",
    }
    assert gate["supported_claim"] == "public pretrained-representation transfer"
    assert set(gate["forbidden_claims"]) == {
        "clean zero-shot transfer",
        "uncontaminated external validation",
        "strict family holdout from all pretraining",
        "known absence of challenge-structure overlap",
        "known absence of challenge-assay overlap",
    }

    snap = gate["snap"]
    assert snap == {
        "repository": "snap-stanford/pretrain-gnns",
        "commit": "8b20528a83b8869ce16451305b32c827258d19a3",
        "checkpoint_path": "chem/model_gin/supervised_masking.pth",
        "checkpoint_git_blob": "1f8de843feb5b51e73488a95096283028820583e",
        "checkpoint_sha256": (
            "375cd40af9f21d2a92ed1acbdea9efad14254c36703bb0e3a7e433e09e624ce1"
        ),
        "checkpoint_size_bytes": 7452448,
        "license": "MIT",
        "license_git_blob": "4ec60e59108c68fc9a8d507920c393d7a1cda23b",
    }
    assert gate["dgl_lifesci"]["license"] == "Apache-2.0"
    assert gate["dgl_lifesci"]["remote_checkpoint_sha256"] is None
    assert gate["molfeat"]["artifact_sha256"] == (
        "6d0f8febad73e437772ebffc2ac32253d79f86ee138cfc233590ae50fb1cfeb9"
    )
    assert gate["molfeat"]["artifact_license_field"] is None
    assert gate["molfeat"]["model_usage"] is None

    lineage = gate["pretraining_lineage"]
    assert lineage["openadmet_structure_overlap"] == "unknown"
    assert lineage["openadmet_assay_overlap"] == "unknown"
    assert "must be disclosed" in lineage["policy"]
    assert "prevents clean external-validation claims" in lineage["policy"]
    assert "No pretraining corpus may be downloaded" in lineage["policy"]

    redistribution = gate["redistribution"]
    for forbidden_destination in (
        "Git",
        "CI artifacts",
        "submission files",
        "public terminals",
        "documentation bundles",
        "publication bundles",
    ):
        assert forbidden_destination in redistribution
    assert "Local nonredistributed inference" in redistribution


def test_provenance_parity_gate_requires_all_objects_and_zero_fit_failure() -> None:
    parity = _load()["pretrained_eligibility_gate"]["future_provenance_parity"]
    assert set(parity) == {
        "required_before_any_official_row_or_target",
        "objects",
        "non_git_cache",
        "tensor_coverage",
        "fixture",
        "embedding_gate",
        "publication",
        "success_authority",
        "failure_status",
        "failure_effect",
    }
    assert parity["required_before_any_official_row_or_target"] is True
    assert parity["objects"] == [
        "exact SNAP checkpoint",
        "exact DGL-LifeSci remote checkpoint",
        "exact MolFeat artifact",
    ]
    assert "isolated non-Git storage" in parity["non_git_cache"]
    assert "no missing, extra" in parity["tensor_coverage"]
    assert "three fresh CPU processes" in parity["fixture"]
    assert "existing eight-row redistributable fixture" in parity["fixture"]
    assert "exact 300-column shape" in parity["embedding_gate"]
    assert "finite float64 output" in parity["embedding_gate"]
    assert "byte-identical pooled embeddings" in parity["embedding_gate"]
    assert "cannot be chosen from observed differences" in parity["embedding_gate"]
    assert parity["failure_status"] == (
        "G3_G4_GIN300_INELIGIBLE_PRETRAINED_PROVENANCE_OR_PARITY_FAILED"
    )
    assert (
        "Zero official rows, labels, fits, predictions, or metrics"
        in parity["failure_effect"]
    )
    assert "without in-place repair, fallback" in parity["failure_effect"]


def test_candidate_controls_splits_and_feature_topology_are_exact() -> None:
    contract = _load()
    population = contract["population_and_splits"]
    assert set(population) == {
        "label_free_assignment",
        "endpoints",
        "targeted_weak_endpoints",
        "repeats",
        "outer_folds",
        "repeat_seeds",
        "family_rule",
        "training_mask",
        "prediction_population",
        "preflight_minima",
        "underpowered",
        "integrity_failure",
    }
    assert population["label_free_assignment"] == {
        "all_molecules": 4905,
        "all_components": 4553,
        "development_molecules": 3908,
        "development_components": 3640,
        "confirmatory_molecules": 997,
        "confirmatory_components": 913,
    }
    assert population["endpoints"] == ["CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"]
    assert population["targeted_weak_endpoints"] == ["CYP1A2", "CYP2D6"]
    assert population["repeats"] == 3
    assert population["outer_folds"] == 5
    assert population["repeat_seeds"] == [20260810, 20260811, 20260812]
    assert "No molecule, exact duplicate" in population["family_rule"]
    assert population["preflight_minima"] == {
        "development_finite_targets_per_endpoint": 750,
        "outer_training_targets_per_endpoint_repeat_fold": 400,
        "outer_validation_targets_per_endpoint_repeat_fold": 75,
    }
    assert "authenticated numerical minimum" in population["underpowered"]
    assert "with zero fits" in population["underpowered"]
    assert "publishes G3_G4_GIN300_FAILED" in population["integrity_failure"]

    features = contract["feature_contract"]
    assert set(features) == {
        "exact_raw_identity",
        "raw_capability",
        "maplight",
        "gin",
        "candidate_matrix",
        "two_root_rule",
        "forbidden",
    }
    assert "raw_structure_sha256" in features["exact_raw_identity"]
    assert features["maplight"]["columns"] == 2563
    assert features["gin"] == {
        "alias": "gin_supervised_masking",
        "columns": 300,
        "pooling": "mean",
        "batch_size": 32,
        "add_self_loop": True,
        "atom_and_bond_features": (
            "pinned DGL-LifeSci pretrained categorical featurizers"
        ),
        "dtype": "float64",
        "layout": "finite C-contiguous dense matrix",
        "source": "Only the exact provenance-cleared checkpoint chain may construct this block.",
    }
    matrix = features["candidate_matrix"]
    assert matrix["system_id"] == "G4-MAPL2563-GIN300"
    assert matrix["total_columns"] == 2563 + 300 == 2863
    assert matrix["column_order"] == (
        "exact MapLight columns 0:2563 followed by exact GIN columns 2563:2863"
    )
    assert matrix["preprocessing"].startswith("None.")
    assert "two fresh opposite-order feature builds" in features["two_root_rule"]

    controls = contract["control_contract"]
    assert set(controls) == {"controls", "same_learner", "predeclared_only"}
    assert len(controls["controls"]) == 2
    shuffled, noise = controls["controls"]
    assert set(shuffled) == {"system_id", "seed", "rule"}
    assert shuffled["system_id"] == "G4-MAPL2563-SHUFFLED-GIN300"
    assert shuffled["seed"] == 20260816
    assert "repeat_index in 0..2" in shuffled["rule"]
    assert "outer_fold in 0..4" in shuffled["rule"]
    assert "partition_code 0=train or 1=validation" in shuffled["rule"]
    assert (
        "SeedSequence([20260816, repeat_index, outer_fold, partition_code])"
        in (shuffled["rule"])
    )
    assert ".permutation(n_unique_partition) exactly once" in shuffled["rule"]
    assert "only within that partition" in shuffled["rule"]
    assert "may cross the training-validation boundary" in shuffled["rule"]

    assert set(noise) == {"system_id", "seed", "rule"}
    assert noise["system_id"] == "G4-MAPL2563-NOISE300"
    assert noise["seed"] == 20260817
    assert "repeat_index in 0..2" in noise["rule"]
    assert "outer_fold in 0..4" in noise["rule"]
    assert "partition_code 0=train or 1=validation" in noise["rule"]
    assert (
        "SeedSequence([20260817, repeat_index, outer_fold, partition_code])"
        in (noise["rule"])
    )
    assert ".standard_normal((n_unique_partition, 300)) exactly once" in noise["rule"]
    assert (
        "Training noise assignments never depend on validation identities"
        in (noise["rule"])
    )
    assert "identical CatBoost constructor" in controls["same_learner"]
    assert "No alternative permutation" in controls["predeclared_only"]


def test_linux_runtime_model_and_exact_workload_are_frozen() -> None:
    contract = _load()
    runtime = contract["runtime_contract"]
    assert set(runtime) == {
        "future_platform",
        "historical_platform",
        "future_python",
        "historical_versions",
        "future_isolated_uv_lock_sha256",
        "boundary",
    }
    assert runtime["future_platform"] == "Linux x86_64 CPU"
    assert runtime["future_python"] == "3.10.13"
    assert runtime["historical_versions"] == {
        "numpy": "1.25.2",
        "torch": "2.0.1",
        "dgl": "1.1.2",
        "dgllife": "0.3.2",
        "molfeat": "0.9.2",
        "catboost": "1.2.1",
        "rdkit": "2023.3.3",
    }
    assert runtime["future_isolated_uv_lock_sha256"] is None
    assert "later contract must create" in runtime["boundary"]
    assert "changes no dependency or runtime" in runtime["boundary"]

    model = contract["model_contract"]
    assert model == {
        "api": "catboost.CatBoostRegressor",
        "loss_function": "MAE",
        "random_strength": 2,
        "random_seed": 1,
        "task_type": "CPU",
        "thread_count": 16,
        "verbose": 0,
        "allow_writing_files": False,
        "resolved_parameter_sha256": (
            "c56235a54a883a9a4488f1c8779f9013dae777af0f99cd92c9da1c4f51e61757"
        ),
        "fit_rule": (
            "Create one fresh model per system, endpoint, repeat, and outer fold. Fit "
            "once on the exact finite-central outer-training rows with no eval set or "
            "additional fit argument, then predict the complete matching "
            "outer-validation feature population."
        ),
        "prohibited": (
            "No parameter change, grid, inner tuning, early stopping, validation "
            "Dataset, callback, custom loss, custom metric, continuation, warm start, "
            "model reuse, GPU, changed thread count, ensemble, calibration, stack, "
            "blend, endpoint-specific recipe, or seed averaging."
        ),
    }

    budget = contract["fit_prediction_metric_budget"]
    assert set(budget) == {
        "systems",
        "outer_contexts_per_system",
        "endpoints_per_outer_context",
        "fits_per_endpoint_context",
        "exact_new_fits_per_system",
        "exact_new_fits_total",
        "baseline_refits",
        "inner_selection_fits",
        "expected_outer_prediction_rows_per_system",
        "expected_new_outer_prediction_rows_total",
        "fixed_maplight_prediction_rows_reopened_after_candidate_freeze",
        "tutorial_calls",
        "synchronized_component_bootstrap_streams",
        "bootstrap_contrasts",
        "bootstrap_contrast_count",
        "accepted_synchronized_replicates",
        "maximum_synchronized_draw_attempts_total",
        "bootstrap_system_metric_evaluations",
        "bootstrap_paired_differences",
        "budget_rule",
    }
    assert budget["systems"] == [
        "G4-MAPL2563-GIN300",
        "G4-MAPL2563-SHUFFLED-GIN300",
        "G4-MAPL2563-NOISE300",
    ]
    assert budget["outer_contexts_per_system"] == 3 * 5 == 15
    assert budget["endpoints_per_outer_context"] == 4
    assert budget["fits_per_endpoint_context"] == 1
    assert budget["exact_new_fits_per_system"] == 15 * 4 == 60
    assert budget["exact_new_fits_total"] == 3 * 60 == 180
    assert budget["baseline_refits"] == 0
    assert budget["inner_selection_fits"] == 0
    assert budget["expected_outer_prediction_rows_per_system"] == 46_896
    assert budget["expected_new_outer_prediction_rows_total"] == 3 * 46_896
    assert budget["tutorial_calls"] == 3 * 4 * 4 == 48
    expected_contrasts = [
        "candidate_minus_fixed_maplight",
        "candidate_minus_shuffled_gin",
        "candidate_minus_noise300",
        "shuffled_gin_minus_fixed_maplight",
        "noise300_minus_fixed_maplight",
    ]
    assert budget["synchronized_component_bootstrap_streams"] == 1
    assert budget["bootstrap_contrasts"] == expected_contrasts
    assert budget["bootstrap_contrast_count"] == len(expected_contrasts) == 5
    assert budget["accepted_synchronized_replicates"] == 2000
    assert budget["maximum_synchronized_draw_attempts_total"] == 20000
    assert budget["bootstrap_system_metric_evaluations"] == 4 * 2000 == 8000
    assert budget["bootstrap_paired_differences"] == 5 * 2000 == 10000


def test_development_gates_are_conjunctive_and_attribution_is_mandatory() -> None:
    evaluation = _load()["development_evaluation"]
    assert set(evaluation) == {
        "paired_identity",
        "primary_metric",
        "component_macro_mae",
        "favorable_cells",
        "paired_component_bootstrap",
        "baseline_promotion",
        "attribution_gate",
        "logic",
        "decision",
    }
    primary = evaluation["primary_metric"]
    assert primary["relative_improvement"] == (
        "relative_improvement(first, comparator) = (comparator_primary - "
        "first_primary) / comparator_primary; a nonpositive or nonfinite comparator "
        "fails closed."
    )
    component = evaluation["component_macro_mae"]
    assert component["absolute_improvement"] == (
        "absolute_component_improvement(first, comparator) = "
        "comparator_component_macro_mae minus first_component_macro_mae on "
        "identical rows."
    )
    assert component["endpoint_improvement"].startswith(
        "endpoint_improvement(first, comparator) = comparator endpoint component-MAE"
    )
    bootstrap = evaluation["paired_component_bootstrap"]
    assert bootstrap["unit"] == (
        "D-032 component shared across endpoints, repeats, and every system"
    )
    assert bootstrap["seed"] == 20260830
    assert bootstrap["accepted_replicates"] == 2000
    assert bootstrap["maximum_attempts_total"] == 20000
    expected_contrasts = [
        "candidate_minus_fixed_maplight",
        "candidate_minus_shuffled_gin",
        "candidate_minus_noise300",
        "shuffled_gin_minus_fixed_maplight",
        "noise300_minus_fixed_maplight",
    ]
    assert bootstrap["contrasts"] == expected_contrasts
    assert "Reuse one multiplicity vector across all four systems" in bootstrap["draw"]
    assert "all five contrasts" in bootstrap["draw"]
    assert "never restart or use a contrast-specific stream" in bootstrap["draw"]

    baseline = evaluation["baseline_promotion"]
    assert baseline == {
        "candidate": "G4-MAPL2563-GIN300",
        "comparator": "fixed MapLight",
        "minimum_relative_primary_improvement": 0.03,
        "minimum_absolute_component_macro_mae_improvement": 0.015,
        "paired_component_mae_upper_95_below_zero": True,
        "minimum_favorable_outer_cells": 8,
        "total_outer_cells": 15,
        "maximum_endpoint_component_mae_degradation": 0.015,
        "minimum_improved_targeted_endpoints": 1,
        "targeted_endpoints": ["CYP1A2", "CYP2D6"],
        "minimum_targeted_endpoint_component_mae_improvement": 0.01,
    }
    attribution = evaluation["attribution_gate"]
    assert attribution == {
        "comparators": [
            "G4-MAPL2563-SHUFFLED-GIN300",
            "G4-MAPL2563-NOISE300",
        ],
        "minimum_relative_primary_improvement_vs_each": 0.01,
        "minimum_absolute_component_macro_mae_improvement_vs_each": 0.005,
        "paired_component_mae_upper_95_below_zero_vs_each": True,
        "minimum_favorable_outer_cells_vs_each": 8,
        "total_outer_cells": 15,
        "control_may_pass_baseline_promotion": False,
        "interpretation": (
            "True GIN must beat each control conjunctively, and neither control may "
            "independently satisfy every fixed-MapLight promotion member. This "
            "attributes any promotion to learned representation content rather than "
            "width, scale, learner capacity, or arbitrary vector assignment."
        ),
    }
    assert evaluation["logic"].startswith(
        "Every baseline-promotion and attribution member is conjunctive."
    )
    assert "separate preregistered robustness" in evaluation["decision"]
    assert "Any clean miss permanently rejects" in evaluation["decision"]


def test_resource_gate_and_terminal_statuses_are_exact_and_single_use() -> None:
    contract = _load()
    ceiling = contract["resource_ceiling"]
    assert ceiling == {
        "cpu_core_hours": 96,
        "gpu_hours": 0,
        "restricted_storage_gb": 32,
        "maximum_wall_hours": 12,
        "maximum_peak_simultaneous_rss_gib": 16,
        "concurrency": (
            "Exactly one 16-thread CatBoost fit or one CPU GIN worker at a time. No "
            "model fit, feature worker, GPU operation, or unrelated memory-heavy job "
            "may overlap."
        ),
    }
    feasibility = contract["resource_feasibility_gate"]
    assert feasibility["required_before_claim"] is True
    assert feasibility["maximum_projected_cpu_core_hours"] == pytest.approx(
        0.8 * ceiling["cpu_core_hours"]
    )
    assert feasibility["maximum_projected_gpu_hours"] == 0
    assert feasibility["maximum_projected_restricted_storage_gb"] == pytest.approx(
        0.8 * ceiling["restricted_storage_gb"]
    )
    assert feasibility["maximum_projected_wall_hours"] == pytest.approx(
        0.8 * ceiling["maximum_wall_hours"]
    )
    assert feasibility["maximum_peak_simultaneous_rss_gib"] == pytest.approx(
        0.8 * ceiling["maximum_peak_simultaneous_rss_gib"]
    )
    assert "20% margin" in feasibility["margin"]
    assert "contract-frozen redistributable synthetic labels" in feasibility["method"]
    assert "no official target" in feasibility["method"]
    assert feasibility["failure_status"] == ("G3_G4_GIN300_RESOURCE_INFEASIBLE_PREFIT")
    assert "No optimization pass" in feasibility["failure"]

    terminal = contract["terminal_statuses"]
    assert set(terminal) == {
        "G3_G4_GIN300_INELIGIBLE_PRETRAINED_PROVENANCE_OR_PARITY_FAILED",
        "G3_G4_GIN300_RESOURCE_INFEASIBLE_PREFIT",
        "G3_G4_GIN300_UNDERPOWERED",
        "G3_G4_GIN300_RESOURCE_ABORTED",
        "G3_G4_GIN300_FAILED",
        "G3_G4_GIN300_REJECTED",
        "G3_G4_GIN300_ACCEPTED",
        "precedence",
        "common_effect",
    }
    assert terminal["precedence"] == [
        "INELIGIBLE before any official row or target",
        "RESOURCE_INFEASIBLE_PREFIT before any official feature or development claim",
        "UNDERPOWERED for clean prefit support failure",
        "RESOURCE_ABORTED for a hard claim-bound feature or development resource breach",
        "FAILED for any integrity or authority defect",
        "REJECTED for a clean scientific miss",
        "ACCEPTED only when every prior gate and scientific criterion passes",
    ]
    assert "single-use and immutable" in terminal["common_effect"]
    assert "No retry, resume" in terminal["common_effect"]


def test_d147_has_zero_execution_private_claim_or_submission_authority() -> None:
    contract = _load()
    closed = contract["distinctness_and_closed_lane_boundary"]
    assert set(closed) == {
        "new_lane",
        "not_a_retry",
        "g2_7g_terminal",
        "maplight_boundary",
        "old_claims_and_roots",
    }
    assert "not a retry, repair, resume" in closed["not_a_retry"]
    assert (
        "UNDERPOWERED with zero fits, predictions, metrics" in closed["g2_7g_terminal"]
    )
    assert "No prior claim, attempt root" in closed["old_claims_and_roots"]

    sequence = contract["milestone_sequence"]
    assert set(sequence) == {
        "D147",
        "D148_contract",
        "D149_implementation",
        "future_feature_claim",
        "future_development_claim",
        "future_robustness",
        "future_confirmatory",
        "future_submission",
    }
    assert "Contract, public static test" in sequence["D147"]
    assert "bounded public source-rights/hash audit only" in sequence["D147"]
    assert "opened one SNAP checkpoint only for hashing" in sequence["D147"]
    assert "deserialized or executed no tensor" in sequence["D147"]
    assert (
        "no dependency, runtime, implementation, retained checkpoint"
        in sequence["D147"]
    )
    assert "freeze only a separate" in sequence["D148_contract"]
    assert "D148 may add its public static tests" in sequence["D148_contract"]
    assert "may not fetch or load a checkpoint" in sequence["D148_contract"]
    assert (
        "Only after D148 is independently reviewed" in sequence["D149_implementation"]
    )
    assert (
        "may D149 create the isolated Linux runtime" in sequence["D149_implementation"]
    )
    assert "one frozen formal-attempt boundary" in sequence["D149_implementation"]
    assert "exactly two opposite-order" in sequence["future_feature_claim"]
    assert "same 3,908 development molecules" in sequence["future_feature_claim"]
    assert (
        "Portal credential access and upload remain separately human-armed"
        in (sequence["future_submission"])
    )

    accounting = contract["current_milestone_accounting"]
    assert set(accounting) == {
        "contracts_created",
        "public_static_tests_created",
        "dependency_or_runtime_changes",
        "implementation_files_created",
        "public_snap_source_archives_downloaded_to_temporary_non_git_storage",
        "public_checkpoint_files_temporarily_persisted_outside_git",
        "public_checkpoint_bytes_temporarily_persisted_outside_git",
        "public_checkpoint_files_opened_only_for_hashing",
        "public_checkpoint_bytes_read_only_for_hashing",
        "dgl_checkpoint_bytes_downloaded",
        "molfeat_checkpoint_bytes_downloaded",
        "checkpoint_tensors_deserialized_or_executed",
        "checkpoint_files_added_to_git_or_workspace",
        "pretraining_rows_opened",
        "official_inputs_opened",
        "official_structure_rows_opened",
        "official_target_values_opened",
        "baseline_prediction_rows_opened",
        "gin_feature_rows_built",
        "model_fits",
        "predictions",
        "development_metrics",
        "selection_tokens",
        "contenders_locked",
        "claims_created_or_consumed",
        "confirmatory_truth_values_opened",
        "blinded_test_rows_opened",
        "tdi_rows_opened",
        "submission_rows_generated",
        "validator_calls",
        "leaderboard_observations_used_for_selection",
        "portal_credentials_opened",
        "live_uploads",
        "gpu_hours",
    }
    assert accounting["contracts_created"] == 1
    assert accounting["public_static_tests_created"] == 1
    assert (
        accounting[
            "public_snap_source_archives_downloaded_to_temporary_non_git_storage"
        ]
        == 1
    )
    assert accounting["public_checkpoint_files_temporarily_persisted_outside_git"] == 33
    assert (
        accounting["public_checkpoint_bytes_temporarily_persisted_outside_git"]
        == 204_567_885
    )
    assert accounting["public_checkpoint_files_opened_only_for_hashing"] == 1
    assert accounting["public_checkpoint_bytes_read_only_for_hashing"] == 7_452_448
    assert all(
        value == 0
        for name, value in accounting.items()
        if name
        not in {
            "contracts_created",
            "public_static_tests_created",
            "public_snap_source_archives_downloaded_to_temporary_non_git_storage",
            "public_checkpoint_files_temporarily_persisted_outside_git",
            "public_checkpoint_bytes_temporarily_persisted_outside_git",
            "public_checkpoint_files_opened_only_for_hashing",
            "public_checkpoint_bytes_read_only_for_hashing",
        }
    )
    assert accounting["checkpoint_tensors_deserialized_or_executed"] == 0
    assert accounting["gin_feature_rows_built"] == 0
    assert accounting["model_fits"] == 0

    authority = contract["current_authority"]
    assert set(authority) == {
        "contract_and_public_static_test",
        "dependency_or_runtime_change",
        "checkpoint_fetch_or_load",
        "provenance_parity_execution",
        "implementation",
        "synthetic_feature_or_model_execution",
        "official_structure_access",
        "official_target_access",
        "baseline_prediction_access",
        "gin_feature_build",
        "model_fit",
        "prediction",
        "development_metric",
        "claim_creation_or_consumption",
        "robustness",
        "contender_lock",
        "confirmatory",
        "blinded_test",
        "tdi",
        "submission_artifact",
        "validator",
        "leaderboard_selection",
        "portal_credentials",
        "upload",
    }
    assert authority["contract_and_public_static_test"] is True
    assert all(
        value is False
        for name, value in authority.items()
        if name != "contract_and_public_static_test"
    )

    next_gate = contract["next_gate"].lower()
    for prohibited in (
        "d148 may not fetch or load a checkpoint",
        "open an official row or target",
        "build an official feature",
        "create or consume a claim",
        "fit a model",
        "compute a metric",
        "access confirmatory or blinded-test data",
        "generate a submission",
        "run a validator",
        "observe a leaderboard for selection",
        "access portal credentials",
        "or upload",
    ):
        assert prohibited in next_gate

    lower = CONTRACT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "/home/zbos/cypshift-private",
        "submission_name",
        "leaderboard_score",
        "leaderboard_rank",
        "remote_submission_id",
        "official_attempt_driver",
        "private_driver",
    ):
        assert forbidden not in lower
