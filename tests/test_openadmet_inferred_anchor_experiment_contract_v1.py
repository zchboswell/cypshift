from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "benchmarks"
    / "openadmet_cyp_2026"
    / "inferred_anchor_experiment_contract_v1.json"
)

TOP_LEVEL_KEYS = {
    "schema_version",
    "contract_id",
    "status",
    "purpose",
    "parent_receipts",
    "activation",
    "permission_resolution",
    "system",
    "evidence_gate",
    "final_t0_coordinate",
    "full_train_inference",
    "operation_accounting",
    "acceptance",
    "authority",
    "hard_stop",
}


def _strict_object(data: bytes) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    loaded = json.loads(
        data,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )
    assert isinstance(loaded, dict)
    return loaded


def _load() -> dict[str, Any]:
    return _strict_object(CONTRACT_PATH.read_bytes())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_i0_contract_is_strict_dormant_and_binds_exact_r5_chain() -> None:
    contract = _load()
    assert set(contract) == TOP_LEVEL_KEYS
    assert contract["schema_version"] == (
        "cypshift.openadmet_cyp_2026.i0_preregistration.v1"
    )
    assert contract["contract_id"] == "R6-CYP3A4-I0-V1"
    assert contract["status"] == "I0_PREREG_ONLY"

    expected = {
        "validation_contract": (
            "validation_contract.json",
            "ada8beff0b6f42baeb61c91df1cbb75ef832ce2b1b87b0d0bcbf253c94326ab3",
        ),
        "r5_contract_v1": (
            "oracle_experiment_contract_v1.json",
            "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf",
        ),
        "r5_contract_v2": (
            "oracle_experiment_contract_v2.json",
            "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623",
        ),
        "r5_contract_v3": (
            "oracle_experiment_contract_v3.json",
            "275f1425d1a93805cb7d5b7dc1b63c67d6f02476eab9f77798cac6cc625a3d55",
        ),
    }
    parents = contract["parent_receipts"]
    for key, (filename, digest) in expected.items():
        path = ROOT / parents[key]["path"]
        assert path.name == filename
        assert parents[key]["sha256"] == digest
        assert _sha256(path) == digest
    assert parents["r5_resolved_contract"]["sha256"] == (
        "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
    )
    official = parents["r5d_official_execution_contract"]
    assert official["path"] == (
        "benchmarks/openadmet_cyp_2026/oracle_official_execution_contract_v1.json"
    )
    assert official["schema_version"] == (
        "cypshift.openadmet_cyp_2026.oracle_official_execution_contract.v1"
    )
    assert official["sha256"] == (
        "f8aadef95be8e0d719a14d08bc2a1164a03d2cf5079e9ed2dec749ee048bd700"
    )
    assert _sha256(ROOT / official["path"]) == official["sha256"]


def test_activation_is_exact_official_r5_signal_pass() -> None:
    contract = _load()
    activation = contract["activation"]
    assert activation["required_status"] == "R5_ORACLE_SIGNAL_PASS"
    assert (
        activation["required_contract_sha256"]
        == contract["parent_receipts"]["r5_resolved_contract"]["sha256"]
    )
    assert activation["required_result_authority"] == {
        "oracle_evidence": True,
        "inferred_anchor_contract": True,
        "internal_metrics": True,
    }
    envelope = activation["required_attempt_envelope"]
    assert envelope["schema_version"] == (
        "cypshift.openadmet_cyp_2026.r5d_official_attempt_receipt.v1"
    )
    assert envelope["source_revision"] == ("85f8b358d0a2056a98b990dd75d3b3ec9247862b")
    assert "R2B, R3A, R3C and R4" in envelope["official_source_parent_ancestry"]
    assert (
        "self-declared or synthetic ancestry is invalid"
        in envelope["official_source_parent_ancestry"]
    )
    assert "one authorized official attempt" in envelope["attempt_semantics"]
    assert "terminal manifest SHA-256" in envelope["terminal_cross_binding"]
    assert "separately authenticated" in activation["terminal"]
    assert "synthetic rehearsal terminal is ineligible" in activation["terminal"]
    assert activation["authentication_order"].startswith(
        "First verify the exact r5d_official_execution_contract receipt"
    )
    assert "I0_DEPLOYMENT_NO_SIGNAL" in activation["nonpass"]
    assert "before oracle_scored_rows.csv" in activation["nonpass"]


def test_permission_exception_is_only_published_r5_derived_evidence() -> None:
    contract = _load()
    resolution = contract["permission_resolution"]
    assert "must not be reused" in resolution["superseded_rule"]
    assert set(resolution["authentication_only"]) == {"manifest.json"}
    assert set(resolution["evidence_inputs"]) == {
        "oracle_scored_rows.csv",
        "oracle_inner_selection.csv",
        "oracle_result.json",
    }
    assert "G0 and F1" in resolution["evidence_inputs"]["oracle_scored_rows.csv"]
    assert (
        "never reconstruct a target or prediction"
        in resolution["evidence_inputs"]["oracle_scored_rows.csv"]
    )
    assert resolution["raw_r2_forbidden"] == [
        "campaign_episodes_public.csv",
        "campaign_episodes_truth.csv",
        "episode_label_masks.csv",
        "direct_observations.csv",
        "group_folds.csv",
    ]
    candidate = resolution["candidate_pool_resolution"]
    assert candidate["candidate_pool_id"] == ("I0_TOP64_COMPLETE_CYP3A4_TRAIN_ONLY_V1")
    assert "never candidates for one another" in candidate["scope"]
    assert "not materialized" in candidate["milestone_state"]


def test_i0_is_exact_f1_and_loss_rows_are_aligned_fail_closed() -> None:
    contract = _load()
    system = contract["system"]
    assert system["system_id"] == "I0"
    assert "exact frozen R5 F1" in system["alias_of"]
    assert set(system["no_new_components"]) == {
        "no new model",
        "no new ranker",
        "no new metric",
        "no competence gate",
        "no ensemble or fusion",
        "no framework",
    }
    assert "only when no valid candidate anchor exists" in system["fallback"]
    assert "must not be converted to G0 fallback" in system["integrity_rule"]

    population = contract["evidence_gate"]["population"]
    assert population["filters"] == {
        "population_id": "primary_local_eligible",
        "episode_policy_id": "selected_anchor",
        "system_id": ["G0", "F1"],
    }
    assert population["alignment_key"] == [
        "episode_id",
        "query_molecule_id",
        "query_rank",
        "episode_policy_id",
        "repeat",
        "outer_fold",
        "component_id",
        "population_id",
    ]
    assert "exactly one G0 and one F1" in population["alignment"]
    assert "local_available=true" in population["f1_local"]
    assert "prediction_source=F1" in population["f1_local"]
    assert "prediction_source=G0" in population["f1_fallback"]
    assert "equals the aligned G0 absolute_error exactly" in population["f1_fallback"]


def test_evidence_gate_freezes_shared_bootstrap_cells_influence_and_support() -> None:
    gate = _load()["evidence_gate"]
    assert set(gate["contrasts"]) == {"G0-I0", "G0-I0_LOCAL"}
    assert "including exact F1 fallback rows" in gate["contrasts"]["G0-I0"]
    assert "f1_local mask" in gate["contrasts"]["G0-I0_LOCAL"]

    bootstrap = gate["bootstrap"]
    assert bootstrap["seed"] == 20260821
    assert bootstrap["accepted_replicates"] == 2000
    assert bootstrap["maximum_attempts"] == 20000
    assert "sorted ascending" in bootstrap["universe"]
    assert "reuse that one multiplicity vector" in bootstrap["draw"]
    assert "local mask never receives an independent draw" in bootstrap["draw"]
    assert "both G0-I0 and G0-I0_LOCAL" in bootstrap["criterion"]
    assert "linear interpolation" in bootstrap["percentile"]

    cells = gate["cells"]
    assert cells["grid"] == {"repeats": 3, "outer_folds": 5, "required_cells": 15}
    assert "at least 12 of 15" in cells["criterion"]
    assert "at least 3 of 5" in cells["criterion"]
    influence = gate["influence"]
    assert influence["checks"] == 10
    assert "absolute contribution descending" in influence["ranking"]
    assert "every leave-one-component-out contrast" in influence["criterion"]

    availability = gate["availability"]
    assert availability["minimum_primary_components_with_local_f1"] == 30
    assert (
        availability["minimum_unique_base_episode_query_rows_before_repeat_expansion"]
        == 50
    )
    assert availability["support_paths"] == {
        "components": "support.control_local_support.F1.families",
        "base_rows": "support.control_local_support.F1.rows_or_pairs",
        "criterion": "criteria.F1_min_30_families_50_rows",
    }
    assert "exactly true" in availability["criterion"]


def test_modal_t0_coordinate_and_full_train_i0_are_exact() -> None:
    contract = _load()
    coordinate = contract["final_t0_coordinate"]
    assert coordinate["filter"] == "system_id=T0 and selected=true."
    assert "Exactly one selected T0 row" in coordinate["required_rows"]
    assert coordinate["allowed_coordinates"] == {
        "alpha": [1.0, 10.0],
        "lambda": [2.0, 10.0],
    }
    assert "modal exact (alpha,lambda)" in coordinate["selection"]
    assert "larger alpha, then larger lambda" in coordinate["selection"]

    inference = contract["full_train_inference"]
    assert inference["endpoint"] == "CYP3A4 direct inhibition only."
    assert "TRACE-G0-MAPL-FIXED" in inference["G0"]
    assert "all official training observations" in inference["G0"]
    assert "both directions" in inference["T0"]
    assert "1/(2*P)" in inference["pair_weight"]
    candidate = inference["candidate_ranking"]
    assert candidate["pool_id"] == "I0_TOP64_COMPLETE_CYP3A4_TRAIN_ONLY_V1"
    assert (
        "Similarity descending, then molecule_id ascending"
        in candidate["pre_extraction_order"]
    )
    assert "min(64,N)" in candidate["pre_extraction_order"]
    assert "VALID_SINGLE or VALID_DOUBLE" in candidate["geometry"]
    assert "never an anchor candidate" in candidate["test_isolation"]
    assert "prediction_source=F1" in inference["prediction"]
    assert "honestly empty valid-anchor set" in inference["failure"]


def test_acceptance_authority_and_accounting_cannot_jump_to_test() -> None:
    contract = _load()
    accounting = contract["operation_accounting"]["preregistration_milestone"]
    assert accounting
    assert all(type(value) is int and value == 0 for value in accounting.values())
    assert (
        "zero targets or predictions"
        in contract["operation_accounting"]["future_evidence_reducer"]
    )

    acceptance = contract["acceptance"]
    assert acceptance["statuses"] == [
        "I0_PREREG_ONLY",
        "I0_FAILED",
        "I0_DEPLOYMENT_NO_SIGNAL",
        "I0_DEPLOYMENT_PASS",
    ]
    assert len(acceptance["deployment_pass"]) == 6
    assert "separate minimal I0 implementation gate only" in acceptance["pass_scope"]

    authority = contract["authority"]
    assert set(authority) == set(acceptance["statuses"])
    for status, values in authority.items():
        assert values["model_fits"] is False, status
        assert values["predictions"] is False, status
        assert values["test_access"] is False, status
        assert values["official_metric"] is False, status
        assert values["tdi"] is False, status
        assert values["submission"] is False, status
        assert values["transduction"] is False, status
    assert authority["I0_DEPLOYMENT_PASS"]["i0_implementation_contract"] is True
    assert authority["I0_DEPLOYMENT_NO_SIGNAL"]["i0_implementation_contract"] is False

    hard_stop = contract["hard_stop"]
    assert "stop before parsing detailed R5 losses" in hard_stop["r5_nonpass"]
    assert "permanently remove I0 from the critical path" in hard_stop["i0_gate_miss"]
    assert "do not tune" in hard_stop["i0_gate_miss"]
    assert "cannot activate or rescue I0" in hard_stop["leaderboard"]
