from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
V3 = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract.json"
V4 = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json"
V5 = ROOT / "benchmarks/openadmet_cyp_2026/global_experiment_contract_v5.json"
V3_SHA256 = "d728684cc3794bbe01ea44342202944a378968f097cb8f5490852b63721a6285"
V4_SHA256 = "a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254"
V5_SHA256 = "596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2"


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_unique)
    assert isinstance(value, dict)
    return value


def _path(value: dict[str, Any], dotted: str) -> Any:
    for part in dotted.split("."):
        value = value[part]
    return value


def _keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [key for key, item in value.items() for _ in [None]] + [
            nested for item in value.values() for nested in _keys(item)
        ]
    if isinstance(value, list):
        return [nested for item in value for nested in _keys(item)]
    return []


def test_v5_is_strict_json_and_hash_bound_to_immutable_v4() -> None:
    v3 = _load(V3)
    v5 = _load(V5)
    assert hashlib.sha256(V3.read_bytes()).hexdigest() == V3_SHA256
    assert hashlib.sha256(V4.read_bytes()).hexdigest() == V4_SHA256
    assert hashlib.sha256(V5.read_bytes()).hexdigest() == V5_SHA256
    assert v5["schema_version"] == (
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v5"
    )
    assert v5["gate"] == "R3B_GLOBAL_RUNNER_CONTRACT_V5_REPAIR_FROZEN"
    assert v5["status"] == "contract_only_repair_not_implemented"
    assert v5["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/global_experiment_contract_v4.json",
        "schema_version": "cypshift.openadmet_cyp_2026.global_experiment_contract.v4",
        "sha256": V4_SHA256,
        "immutable": True,
    }
    binding = v5["artifact_binding"]
    assert binding["authority"] == "parent.authority.INHERITED_ONLY"
    assert binding["active_contract"]["schema_version"] == v5["schema_version"]
    assert binding["active_contract"]["sha256"].startswith("sha256 of these exact V5")
    assert binding["parent_contract"] == {
        "schema_version": "cypshift.openadmet_cyp_2026.global_experiment_contract.v4",
        "sha256": V4_SHA256,
    }
    assert binding["historical_r3a"] == {
        "schema_version": "cypshift.openadmet_cyp_2026.r3a_feature_manifest.v1",
        "manifest_sha256": "32a950959ceca0641b56518e2059069a275ced64cf399d095aa5bce522c8026b",
    }
    assert binding["model_public"]["schema_version"].endswith("model_public.v5")
    assert binding["cell_receipts"]["schema_version"].endswith("cell.v5")
    assert binding["split"]["group_folds_sha256"] == (
        "91678d68b2f9ac3913f6b679dd284f82ba2a040d803de83655bf89906f31f774"
    )
    assert binding["split"]["split_id_formula"] == (
        "Lowercase SHA256 of group_folds_sha256|repeat|outer_fold|"
        "inner_fold_or_none|scope."
    )
    assert binding["split"]["group_hash_formula"].startswith(
        "model_rows.similarity_component_hash equals"
    )
    assert binding["permitted_contract_versions"] == [
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v5",
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v4",
        "cypshift.openadmet_cyp_2026.global_experiment_contract.v3",
    ]
    assert v3["schema_version"].endswith(".v3")


def test_v5_declares_no_science_drift_against_parent() -> None:
    v3 = _load(V3)
    v4 = _load(V4)
    v5 = _load(V5)
    expected = [
        "scope",
        "fixed_system",
        "serialization",
        "runtime_and_models.model_and_scorer",
        "runtime_and_models.catboost_constructor_arguments",
        "runtime_and_models.fit_call",
        "runtime_and_models.fit_budget",
        "scoring",
        "completion",
        "forbidden",
    ]
    assert v5["preserves"]["paths"] == expected
    assert v4["scope"] == {
        "protocol": "GLOBAL_FAMILY_HOLDOUT",
        "endpoints": ["CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4"],
        "molecules": 4905,
        "molecule_endpoint_cells": 19620,
        "target_eligible_cells": 6525,
        "target_ineligible_cells": 13095,
        "official_states": {
            "complete": 6525,
            "partial": 0,
            "missing": 13095,
            "orphan_auxiliary": 0,
        },
        "target_eligibility": "Eligible if and only if point_eligible is lowercase true, value_state is exactly complete, and point parses as a finite float. Partial, missing, and orphan_auxiliary rows are ineligible even when a point string is present.",
        "repeats": 3,
        "outer_folds": 5,
        "inner_folds": 4,
        "outer_cells": 60,
        "inner_cells": 240,
    }
    assert v3["scope"]["population"]["molecules"] == 4905
    assert (
        v4["fixed_system"]["predesignated_before_target_access"]
        == "TRACE-G0-MAPL-FIXED"
    )
    assert v4["runtime_and_models"]["fit_budget"] == {
        "outer_morgan": 60,
        "outer_maplight": 60,
        "inner_maplight_after_outer_pass": 240,
        "outer_no_advantage_total": 120,
        "maximum_total": 360,
    }
    assert v4["scoring"]["q90"]["contexts"] == 60
    assert v4["completion"]["expert_counts"]["final"]["rows"] == 19620
    assert "Endpoints" in v5["preserves"]["science"]
    assert "metrics" in v5["preserves"]["science"]
    assert "official-data prohibition" in v5["preserves"]["science"]


def test_receipts_eligibility_and_file_cardinality_are_exact() -> None:
    amendments = _load(V5)["amendments"]
    receipt = amendments["projection_input_receipts"]
    assert receipt["production"] == {
        "parent_contract_sha256": V4_SHA256,
        "direct_rows": 19620,
        "fold_rows": 73575,
    }
    assert amendments["eligibility_counts"]["production"] == {
        "direct_rows": 19620,
        "eligible": 6525,
        "ineligible": 13095,
        "complete": 6525,
        "partial": 0,
        "missing": 13095,
        "orphan_auxiliary": 0,
        "outer_target_files": 60,
        "inner_target_files": 240,
        "outer_target_rows": 78300,
        "inner_target_rows": 234900,
        "outer_truth_rows": 58860,
        "inner_truth_rows": 235440,
        "outer_truth_eligible": 19575,
        "inner_truth_eligible": 78300,
    }
    files = amendments["target_file_set"]
    assert files["outer"]["files"] == 60
    assert files["inner"]["files"] == 240
    assert files["total_files"] == 300
    assert files["header_only_zero_row_allowed"] is True
    assert files["every_declared_path_requires_receipt"] is True
    assert files["receipt_schema"]["fields"] == [
        "stage",
        "cell_id",
        "endpoint",
        "repeat",
        "outer_fold",
        "inner_fold",
        "relative_path",
        "sha256",
        "rows",
        "identity_sha256",
    ]
    assert files["outer_receipts"]["count"] == 60
    assert files["inner_receipts"]["count"] == 240
    assert files["hash_before_parse"] == {
        "receipt_count": 300,
        "order": "hash every declared receipt and verify every path before parsing any target payload",
    }
    assert set(_keys(_load(V5))) & {"fold_rows"} == {"fold_rows"}
    locations: list[str] = []

    def find(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "fold_rows":
                    locations.append(path + "." + key)
                find(item, path + "." + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                find(item, f"{path}[{index}]")

    find(_load(V5))
    assert locations
    assert all(
        location.startswith(".amendments.projection_input_receipts.")
        for location in locations
    )


def test_named_accounting_schemas_and_terminal_preflight_constant() -> None:
    amendments = _load(V5)["amendments"]
    accountings = amendments["accounting_schemas"]
    required = {
        "projector_accounting",
        "sealed_accounting",
        "preflight_accounting",
        "cell_accounting",
        "outer_freezer_accounting",
        "inner_freezer_accounting",
        "scorer_accounting",
        "public_accounting",
    }
    assert set(accountings) == required
    for schema in accountings.values():
        assert schema["authority"] == "exact INHERITED_ONLY authority"
        fields = schema["fields"]
        if isinstance(fields, list):
            assert len(fields) == len(set(fields))
            assert set(fields) == set(schema["production"])
        else:
            assert len(fields) == len(set(fields))
            assert set(fields) == set(schema["production_constants"]) | {
                "direct_observation_rows_parsed",
                "target_rows_written",
                "truth_rows_written",
            }
    preflight = accountings["preflight_accounting"]["production"]
    assert preflight["preflight_target_files_opened"] == 300
    assert all(
        preflight[key] == 0
        for key in preflight
        if key != "preflight_target_files_opened"
    )
    projector = accountings["projector_accounting"]["production_constants"]
    assert projector["outer_target_files_written"] == 60
    assert projector["inner_target_files_written"] == 240
    assert projector["sealed_truth_files_written"] == 2
    assert accountings["cell_accounting"]["production"]["feature_arrays_opened"] == 5
    assert accountings["projector_accounting"]["official_reference_counts"] == {
        "direct_observation_rows_parsed": 19620,
        "target_rows_written": 313200,
        "truth_rows_written": 294300,
    }
    assert amendments["accounting_schemas"]["projector_accounting"][
        "production_equations"
    ] == [
        "target_rows_written = sum(rows in all 60 outer and 240 inner target receipts)",
        "truth_rows_written = outer_truth_rows + inner_truth_rows",
        "direct_observation_rows_parsed = len(receipt-verified direct observations)",
    ]
    terminal = amendments["terminal_accounting"]["preflight_target_files_opened"]
    assert terminal == {
        "GLOBAL_UNDERPOWERED": 300,
        "GLOBAL_NO_ADVANTAGE": 300,
        "GLOBAL_EXPERT_FROZEN": 300,
    }
    assert amendments["terminal_accounting"][
        "GLOBAL_FAILED_preflight_target_files_opened"
    ] == {
        "minimum": 0,
        "maximum": 300,
        "rule": "Count is the validated number opened before the failure; no target payload is opened after failure.",
    }
    bindings = amendments["vague_reference_bindings"]
    assert all(value.startswith("exact ") for value in bindings.values())


def test_runtime_fold_index_membership_and_preflight_arrays_are_mechanical() -> None:
    amendments = _load(V5)["amendments"]
    runtime = amendments["runtime_receipt_gate"]
    assert runtime["python_version"] == "3.12.3"
    assert runtime["uv_lock_path"] == "uv.lock"
    assert runtime["receipt_before_parse"] is True
    assert runtime["load_once"] is True
    assert runtime["order"][-1].startswith("only then open or parse")
    assert "mandatory" in runtime["source_receipt"]
    index = amendments["fold_lookup_index"]
    assert index["key"] == ["molecule_id", "repeat", "outer_validation_fold"]
    assert "repeated linear scans are forbidden" in index["use"]
    assert any("one immutable component hash" in item for item in index["validation"])
    split = amendments["split_semantics"]
    assert "row.outer_fold != context" in split["outer_training"]
    assert "outer-training rows" in split["inner_truth"]
    assert split["outer_scope"] == "openadmet-direct-outer-v1"
    assert split["inner_scope"] == "openadmet-direct-inner-v1|outer=<context>"
    arrays = amendments["preflight"]["arrays"]
    assert arrays["outer_score_support_cells"]["records"] == 60
    assert arrays["inner_training_populations"]["records"] == 240
    assert arrays["q90_residual_eligibility_populations"]["records"] == 60
    assert amendments["preflight"]["underpowered_before_fit"] is True


def test_source_bundles_and_inner_applicability_are_explicit() -> None:
    amendments = _load(V5)["amendments"]
    provenance = amendments["source_provenance"]
    assert provenance["composite_material"].startswith("Sorted UTF-8 lines")
    assert provenance["cell_runner_bundle"] == [
        "research/maplight-fixed/run_r3b_cells.py",
        "research/maplight-fixed/r3b_cell_io.py",
        "research/maplight-fixed/r3b_cell_freezer.py",
    ]
    assert provenance["freezer_bundle"] == [
        "research/maplight-fixed/r3b_cell_freezer.py",
        "research/maplight-fixed/r3b_cell_io.py",
    ]
    assert (
        "cell_runner_bundle composite_sha256"
        in provenance["terminal_source_receipts"]["cell_runner"]
    )
    features = amendments["feature_access"]
    assert len(features["outer_arrays"]) == 5
    assert features["inner_arrays_opened"] == features["outer_arrays"]
    assert features["inner_applicability_only"] == ["morgan_binary.npy"]
    assert features["inner_forbidden_model_features"] == ["morgan_binary.npy"]


def test_public_sealed_authority_and_freezer_parameter_propagation_are_exact() -> None:
    v4 = _load(V4)
    v5 = _load(V5)
    inherited = v4["authority"]["INHERITED_ONLY"]
    authority = v5["authority"]
    assert authority["source"] == "parent.authority"
    assert authority["object"] == "INHERITED_ONLY"
    assert authority["required_exact"] is True
    assert authority["amendment_allowlist"]
    assert "INHERITED_ONLY" not in authority
    assert set(inherited) == {
        "global_surrogate_validation",
        "global_model",
        "internal_surrogate_metrics",
        "global_oof_predictions",
        "inner_oof_predictions",
        "parent_state_completion",
        "official_st_rae",
        "validation_frozen",
        "fold_assignments",
        "episodes",
        "episode_labels",
        "topology_viability",
        "submissions",
        "tdi",
        "transduction",
        "anchor_expansion",
        "transformations",
    }
    schemas = v5["amendments"]["target_and_truth_schemas"]
    assert schemas["model_rows"] == [
        "molecule_id",
        "similarity_component_hash",
        "repeat",
        "seed",
        "outer_fold",
        "outer_validation_fold",
        "inner_fold",
    ]
    assert schemas["target_rows"] == ["observation_id", "molecule_id", "point"]
    assert len(schemas["truth_rows"]) == 14
    assert schemas["public_authority"] == "exact INHERITED_ONLY authority"
    freezer = v5["amendments"]["freezer_binding"]
    assert freezer["outer_manifest_schema_version"].endswith("outer_freeze.v2")
    assert freezer["inner_manifest_schema_version"].endswith("inner_freeze.v2")
    assert "resolved_catboost_parameters" in freezer["outer_manifest_fields"]
    assert "resolved_catboost_parameters" in freezer["inner_manifest_fields"]
    params = freezer["resolved_catboost_parameters"]
    assert params["record_schema"] == {
        "fields": [
            "system_id",
            "canonical_get_all_params_json",
            "canonical_get_all_params_sha256",
        ],
        "name": "catboost_resolved_parameter",
    }
    assert params["outer"] == {
        "records": 2,
        "order": ["TRACE-C1-MORGAN-CATBOOST", "TRACE-G0-MAPL-FIXED"],
    }
    assert params["inner"] == {
        "records": 1,
        "order": ["TRACE-G0-MAPL-FIXED"],
    }
    assert freezer["terminal_recovery"].startswith("Terminal manifest recovery")
    assert (
        "canonical parameters and SHA256 are identical" in freezer["parameter_equality"]
    )
    assert (
        v5["amendments"]["post_projection_verification"]["exact_totals"]["target_files"]
        == 300
    )


def test_duplicate_json_keys_fail_closed() -> None:
    try:
        json.loads(
            '{"schema_version": 1, "schema_version": 2}', object_pairs_hook=_unique
        )
    except AssertionError as error:
        assert "duplicate JSON key" in str(error)
    else:
        raise AssertionError("duplicate JSON key was accepted")


def test_declared_field_arrays_have_no_duplicates() -> None:
    duplicates: list[str] = []

    def visit(value: Any, path: str = "") -> None:
        if isinstance(value, dict):
            if isinstance(value.get("fields"), list):
                fields = value["fields"]
                if len(fields) != len(set(fields)):
                    duplicates.append(path + ".fields")
            for key, item in value.items():
                visit(item, path + "." + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(_load(V5))
    assert duplicates == []
