from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v1.json"
V2_PATH = ROOT / "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v2.json"
V3_PATH = ROOT / "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v3.json"
V1_SHA256 = "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
V2_SHA256 = "bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623"
V3_SHA256 = "275f1425d1a93805cb7d5b7dc1b63c67d6f02476eab9f77798cac6cc625a3d55"
RESOLVED_SHA256 = "9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50"
TOP_LEVEL_KEYS = {
    "schema_version",
    "contract_id",
    "gate",
    "status",
    "purpose",
    "parent",
    "resolution",
    "unchanged",
    "authority",
    "reversal_condition",
}
RESOLUTION_KEYS = {"algorithm", "operations", "effective_contract", "failure"}
OPERATION_KEYS = {"op", "parent_object_pointer", "member", "value"}
UNCHANGED = {
    "science_and_populations": True,
    "systems_features_targets_and_hyperparameters": True,
    "support_thresholds_and_gates": True,
    "inner_selection_and_outer_primary_scoring": True,
    "bootstrap_influence_and_safety": True,
    "output_authority_and_publication": True,
    "forbidden_operations": True,
}
AUTHORITY = {
    "contract_only": True,
    "oracle_evidence": False,
    "inferred_anchor_contract": False,
    "model_fits": False,
    "predictions": False,
    "internal_metrics": False,
    "official_st_rae": False,
    "test_access": False,
    "tdi": False,
    "submission": False,
    "transduction": False,
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


def _load_verified(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"{label} raw receipt differs before parse")
    return _strict_object(raw)


def _validate_overlay_shape(overlay: dict[str, Any]) -> None:
    if set(overlay) != TOP_LEVEL_KEYS:
        raise ValueError("top-level keyset differs")
    if overlay["schema_version"] != (
        "cypshift.openadmet_cyp_2026.oracle_experiment_contract.v3"
    ):
        raise ValueError("schema version differs")
    if overlay["gate"] != "R5_ORACLE_CONTRACT_V3_FROZEN":
        raise ValueError("gate differs")
    if overlay["status"] != "R5_ORACLE_CONTRACT_ONLY":
        raise ValueError("status differs")
    if overlay["unchanged"] != UNCHANGED:
        raise ValueError("unchanged flags differ")
    if overlay["authority"] != AUTHORITY:
        raise ValueError("authority differs")
    if set(overlay["resolution"]) != RESOLUTION_KEYS:
        raise ValueError("resolution keyset differs")
    operations = overlay["resolution"]["operations"]
    if not isinstance(operations, list) or len(operations) != 1:
        raise ValueError("operation set differs")
    if set(operations[0]) != OPERATION_KEYS:
        raise ValueError("operation keyset differs")
    if operations[0]["op"] != "add_absent_object_member":
        raise ValueError("operation differs")
    if operations[0]["parent_object_pointer"] != "":
        raise ValueError("operation path differs")
    if operations[0]["member"] != "execution_overlay":
        raise ValueError("operation member differs")
    if operations[0]["value"] != _EXPECTED_EXECUTION:
        raise ValueError("overlay value differs")


_EXPECTED_EXECUTION = copy.deepcopy(
    _load_verified(V3_PATH, V3_SHA256, "v3")["resolution"]["operations"][0]["value"]
)


def _resolve_pointer(root: Any, pointer: str) -> Any:
    if pointer == "":
        return root
    assert pointer.startswith("/")
    value = root
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        assert isinstance(value, dict)
        assert token in value
        value = value[token]
    return value


def _apply_operation(root: dict[str, Any], operation: dict[str, Any]) -> None:
    if operation.get("op") != "add_absent_object_member":
        raise ValueError("unknown operation")
    pointer = operation.get("parent_object_pointer")
    if not isinstance(pointer, str):
        raise ValueError("pointer differs")
    target = _resolve_pointer(root, pointer)
    if not isinstance(target, dict):
        raise ValueError("pointer target is not an object")
    member = operation.get("member")
    if not isinstance(member, str) or not member:
        raise ValueError("member differs")
    if member in target:
        raise ValueError("member already exists")
    target[member] = copy.deepcopy(operation["value"])


def _apply_overlay(
    parent: dict[str, Any], overlay: dict[str, Any], *, parent_path: Path
) -> dict[str, Any]:
    _validate_overlay_shape(overlay)
    binding = overlay["parent"]
    if binding != {
        "path": "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v2.json",
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_experiment_contract.v2",
        "contract_id": "R5-CYP3A4-ORACLE-V2",
        "sha256": V2_SHA256,
    }:
        raise ValueError("parent binding differs")
    if hashlib.sha256(parent_path.read_bytes()).hexdigest() != binding["sha256"]:
        raise ValueError("parent receipt differs")
    operations = overlay["resolution"]["operations"]
    effective = copy.deepcopy(parent)
    _apply_operation(effective, operations[0])
    _audit_resolved(effective)
    return effective


def _effective_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    v1 = _load_verified(V1_PATH, V1_SHA256, "v1")
    v2 = _load_verified(V2_PATH, V2_SHA256, "v2")
    v3 = _load_verified(V3_PATH, V3_SHA256, "v3")
    v2_effective = copy.deepcopy(v1)
    v2_ops = v2["resolution"]["operations"]
    assert isinstance(v2_ops, list) and len(v2_ops) == 1
    _apply_operation(v2_effective, v2_ops[0])
    return v3, _apply_overlay(v2_effective, v3, parent_path=V2_PATH)


def _deep_diff(before: Any, after: Any, path: str = "") -> set[str]:
    if isinstance(before, dict) and isinstance(after, dict):
        differences: set[str] = set()
        for key in before.keys() | after.keys():
            child = f"{path}/{key}"
            if key not in before or key not in after:
                differences.add(child)
            else:
                differences |= _deep_diff(before[key], after[key], child)
        return differences
    if before != after:
        return {path or "/"}
    return set()


def _identity_bytes(value: list[Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_resolved_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _audit_resolved(effective: dict[str, Any]) -> None:
    execution = effective.get("execution_overlay")
    if not isinstance(execution, dict):
        raise AssertionError("execution overlay missing")
    expected = {
        "g0",
        "identity",
        "private_prediction_fragment",
        "sealed_scorer_capability",
        "population_scope",
        "parameter_sentinels",
        "hash_domains",
        "canonical_serialization",
        "outer_t0",
        "selection_token",
        "g0_freeze",
        "operation_accounting",
        "operation_accounting_table",
        "scorer_transport",
    }
    if set(execution) != expected:
        raise AssertionError("execution overlay keyset differs")
    fragment = execution["private_prediction_fragment"]
    if (
        "complete_anchor" in fragment["columns"]
        or "complete_anchor" in fragment["types"]
    ):
        raise AssertionError("raw model fragment carries complete_anchor")
    if fragment["columns"] != [
        "episode_id",
        "query_molecule_id",
        "query_rank",
        "episode_policy_id",
        "repeat",
        "outer_fold",
        "inner_fold",
        "component_id",
        "system_id",
        "candidate_id",
        "prediction",
        "local_available",
        "prediction_source",
        "extraction_status",
        "similarity",
        "exact_support_components",
        "class_support_components",
    ]:
        raise AssertionError("private fragment columns differ")
    if execution["sealed_scorer_capability"]["columns"] != [
        "episode_id",
        "query_molecule_id",
        "query_rank",
        "complete_anchor",
        "valid_true_transformation",
        "true_extraction_status",
    ]:
        raise AssertionError("sealed completion field differs")
    if set(execution["identity"]) != {
        "canonical_json",
        "contract_id",
        "candidate_id",
        "cell_id",
        "fragment_id",
        "f0_query_identity",
        "stage_mapping",
    }:
        raise AssertionError("identity keyset differs")
    if execution["identity"]["stage_mapping"]["values"] != {
        "inner": "inner",
        "outer": "outer",
    }:
        raise AssertionError("stage mapping differs")
    if execution["identity"]["f0_query_identity"]["material"] != [
        "episode_id",
        "query_molecule_id",
        "query_rank",
    ]:
        raise AssertionError("F0 identity material differs")
    if set(execution["hash_domains"]) != {
        "overlay_contract",
        "resolved_contract",
        "candidate_receipt",
        "pre_token_selection_artifact",
        "g0_binding",
    }:
        raise AssertionError("hash-domain keyset differs")
    if set(execution["selection_token"]) != {
        "schema_version",
        "fields",
        "serialization",
        "cardinality",
        "forbidden_fields",
        "forbidden_values",
    }:
        raise AssertionError("selection-token keyset differs")
    if execution["population_scope"] != {
        "inner": ["selected_anchor"],
        "outer": ["selected_anchor", "deterministic_random_anchor_stress"],
        "rule": "Inner model cells and inner selection contain selected_anchor only; outer model cells and private freezes contain selected_anchor plus deterministic_random_anchor_stress. Stress remains diagnostic-only under the accepted v2 clarification.",
    }:
        raise AssertionError("population scope differs")


def test_v3_binds_exact_v2_and_adds_one_root_member_only() -> None:
    overlay, effective = _effective_contract()
    assert hashlib.sha256(V2_PATH.read_bytes()).hexdigest() == V2_SHA256
    assert hashlib.sha256(V3_PATH.read_bytes()).hexdigest() == V3_SHA256
    _audit_resolved(effective)
    assert set(overlay) == TOP_LEVEL_KEYS
    assert overlay["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v2.json",
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_experiment_contract.v2",
        "contract_id": "R5-CYP3A4-ORACLE-V2",
        "sha256": V2_SHA256,
    }

    v1 = _load_verified(V1_PATH, V1_SHA256, "v1")
    v2 = _load_verified(V2_PATH, V2_SHA256, "v2")
    v2_effective = copy.deepcopy(v1)
    _apply_operation(v2_effective, v2["resolution"]["operations"][0])
    assert _deep_diff(v2_effective, effective) == {"/execution_overlay"}
    assert hashlib.sha256(_canonical_resolved_bytes(effective)).hexdigest() == (
        RESOLVED_SHA256
    )
    assert overlay["resolution"]["operations"] == [
        {
            "op": "add_absent_object_member",
            "parent_object_pointer": "",
            "member": "execution_overlay",
            "value": effective["execution_overlay"],
        }
    ]


def test_v3_freezes_g0_identity_and_private_fragment_mechanics() -> None:
    _, effective = _effective_contract()
    execution = effective["execution_overlay"]
    assert "every public query row" in execution["g0"]["prediction_superset"]
    assert "only when anchor_point_available=true" in execution["g0"]["anchor_fit_rule"]
    assert "current-training points only" in execution["g0"]["anchor_fit_rule"]

    identity = execution["identity"]
    assert identity["contract_id"].endswith(
        "effective resolved parent contract_id R5-CYP3A4-ORACLE-V1 in identity arrays; the v3 overlay metadata contract_id is not silently substituted."
    )
    assert identity["candidate_id"]["material"] == [
        "contract_id",
        "system_id",
        "alpha",
        "lambda",
    ]
    assert identity["candidate_id"]["reuse_material"]["F2"] == [
        "contract_id",
        "F2",
        "selected_t0_alpha",
        "selected_t0_lambda",
        "t0_selection_token_sha256",
    ]
    assert identity["cell_id"]["reuse_material"]["F2"] == [
        "contract_id",
        "stage",
        "repeat",
        "outer_fold",
        "inner_fold_or_minus_one",
        "F2",
        "selected_t0_alpha",
        "selected_t0_lambda",
        "candidate_id",
        "episode_id_or_all",
        "t0_selection_token_sha256",
    ]
    assert identity["candidate_id"]["reuse_material"]["F0"][2:4] == [
        None,
        None,
    ]
    assert (
        "upstream_t0_candidate_receipt_sha256"
        in identity["cell_id"]["reuse_material"]["F0"]
    )
    assert (
        "upstream_t0_candidate_receipt_sha256"
        in identity["fragment_id"]["control_reuse"]["F1"]
    )
    assert identity["cell_id"]["material"] == [
        "contract_id",
        "stage",
        "repeat",
        "outer_fold",
        "inner_fold_or_minus_one",
        "system_id",
        "candidate_id",
        "episode_id_or_all",
    ]
    assert identity["f0_query_identity"]["material"] == [
        "episode_id",
        "query_molecule_id",
        "query_rank",
    ]
    assert "Repeat is not appended" in identity["f0_query_identity"]["episode_id"]

    fragment = execution["private_prediction_fragment"]
    assert fragment["columns"] == [
        "episode_id",
        "query_molecule_id",
        "query_rank",
        "episode_policy_id",
        "repeat",
        "outer_fold",
        "inner_fold",
        "component_id",
        "system_id",
        "candidate_id",
        "prediction",
        "local_available",
        "prediction_source",
        "extraction_status",
        "similarity",
        "exact_support_components",
        "class_support_components",
    ]
    assert fragment["row_order"].startswith("episode_id ascending")
    assert "complete_anchor" not in fragment["columns"]
    assert "complete_anchor" not in fragment["types"]
    assert "no complete_anchor" in fragment["raw_model_only"]
    assert fragment["system_id"]["vocabulary"] == [
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
    assert fragment["system_id"]["g0_normalization"].startswith(
        "Every locked TRACE-G0-MAPL-FIXED"
    )
    assert fragment["prediction_source"]["vocabulary"] == [
        "G0",
        "LOCAL",
        "C0",
        "C1",
        "F0",
        "F1",
    ]
    assert fragment["prediction_source"]["fallback"] == "G0"
    sealed = execution["sealed_scorer_capability"]
    assert sealed["added_file"] == "sealed_episode_eligibility.csv"
    assert sealed["root_file_set"] == [
        "manifest.json",
        "episode_truth.csv",
        "activity_cliffs.csv",
        "sealed_episode_eligibility.csv",
    ]
    assert sealed["columns"] == [
        "episode_id",
        "query_molecule_id",
        "query_rank",
        "complete_anchor",
        "valid_true_transformation",
        "true_extraction_status",
    ]
    assert sealed["key"] == ["episode_id", "query_molecule_id", "query_rank"]
    assert "accepted R4 true episode transformation" in sealed["trusted_source"]
    assert "Exactly one row for every public query row" in sealed["cardinality"]
    assert (
        sealed["row_order"]
        == "episode_id ascending, then query_rank ascending; query_molecule_id must match the public key at that rank."
    )
    assert "exact stage, repeat, outer_fold, and inner_fold scope" in sealed["scope"]
    assert "manifest output_receipts" in sealed["manifest_receipt"]
    assert "query_truth_values_opened_by_scorers" in sealed["accounting"]
    assert "After immutable model-fragment freeze" in sealed["join"]
    assert "never receives" in sealed["c3_firewall"]
    assert (
        "do run frozen on-demand R4 control geometry" in fragment["metadata_provenance"]
    )
    assert (
        "never replaces these true anchor-to-query metadata fields"
        in fragment["metadata_provenance"]
    )


def test_v3_freezes_outer_t0_reuse_and_accounting_without_new_gates() -> None:
    overlay, effective = _effective_contract()
    execution = effective["execution_overlay"]
    assert execution["outer_t0"]["emission"] == (
        "That one exact fitted model and token may emit T0, F0, and F1 fragments together."
    )
    assert "never fit, tune, select, calibrate" in execution["outer_t0"]["controls"]
    token = execution["selection_token"]
    assert token["fields"] == [
        "schema_version",
        "contract_sha256",
        "system_id",
        "repeat",
        "outer_fold",
        "candidate_id",
        "alpha",
        "lambda",
        "candidate_receipt_sha256",
        "scorer_receipt_sha256",
    ]
    assert set(token["forbidden_fields"]) >= {"score", "loss", "rank"}
    assert "one token per learned system" in token["cardinality"]
    assert execution["population_scope"]["inner"] == ["selected_anchor"]
    assert execution["population_scope"]["outer"] == [
        "selected_anchor",
        "deterministic_random_anchor_stress",
    ]
    assert execution["identity"]["stage_mapping"] == {
        "v1_scope_field": "stage",
        "values": {"inner": "inner", "outer": "outer"},
        "replacement": "Use these exact V1 scope tokens in every scope, cell, receipt, and fragment; no stage alias or replacement token is permitted.",
    }
    assert execution["identity"]["fragment_id"]["material"][-1] == "cell_id"
    assert "T0, F0, and F1" in execution["identity"]["fragment_id"]["serialization"]
    sentinels = execution["parameter_sentinels"]["systems"]
    assert set(sentinels) == set(
        execution["private_prediction_fragment"]["system_id"]["vocabulary"]
    )
    assert sentinels["G0"] == {"alpha": None, "lambda": None}
    assert sentinels["F0"] == {"alpha": None, "lambda": None}
    assert sentinels["F1"] == {"alpha": None, "lambda": None}
    assert sentinels["F2"] == {
        "alpha": "selected_t0_alpha",
        "lambda": "selected_t0_lambda",
        "token_receipt": "t0_selection_token_sha256",
    }
    assert (
        "candidate prediction-fragment bytes"
        in execution["hash_domains"]["candidate_receipt"]
    )
    assert "pre-token" in execution["hash_domains"]["pre_token_selection_artifact"]
    assert execution["hash_domains"]["g0_binding"]["material"] == [
        "contract_sha256",
        "model_public_manifest_sha256",
        "episode_target_manifest_sha256",
        "stage",
        "repeat",
        "outer_fold",
        "inner_fold_or_minus_one",
        "episode_id_or_all",
        "cell_id",
        "r3c_parameter_record_sha256",
        "g0_source_bundle_sha256",
    ]
    assert execution["canonical_serialization"]["field_domains"] == {
        "contract_sha256": "cypshift.openadmet_cyp_2026.oracle.resolved.v3",
        "candidate_receipt_sha256": "cypshift.openadmet_cyp_2026.oracle.candidate-fragment.v1",
        "scorer_receipt_sha256": "cypshift.openadmet_cyp_2026.oracle.pre-token-selection.v1",
    }
    assert "sort_keys=true" in execution["canonical_serialization"]["resolved_json"]
    assert "ensure_ascii=false" in execution["canonical_serialization"]["resolved_json"]
    assert (
        execution["canonical_serialization"]["fixed_witnesses"]["candidate_receipt"][
            "sha256"
        ]
        == "2622fe89c9e886e0a4e08a5fda43b1ea0bee1015d5b15379ca288c74ae7949e3"
    )
    assert (
        execution["canonical_serialization"]["fixed_witnesses"]["resolved_json"][
            "sha256"
        ]
        == "767e0c5e9367724c031c31765db1363df75e6a8ea2885876e3789547a7355377"
    )
    assert (
        execution["canonical_serialization"]["fixed_witnesses"]["scorer_receipt"][
            "sha256"
        ]
        == "a03d729c9b447fc5befc6a77ba271924bc80e09298e113741e72ce0256f0924e"
    )
    assert (
        "distinct system_id, candidate_id, cell_id"
        in execution["outer_t0"]["distinct_ids"]
    )
    accounting = execution["operation_accounting"]
    assert (
        accounting["fields"]
        == _load_verified(V1_PATH, V1_SHA256, "v1")["operation_accounting"]["fields"]
    )
    assert "anchor_point_available=true" in accounting["g0_rule"]
    assert "exactly zero" in accounting["forbidden_operations"]
    assert overlay["unchanged"] == UNCHANGED
    assert overlay["authority"] == AUTHORITY
    assert execution["operation_accounting_table"]["fit_deltas"] == {
        "C2": {"ridge_model_fits": 1, "hierarchy_fits": 0},
        "C3": {"ridge_model_fits": 1, "hierarchy_fits": 1},
        "T0": {"ridge_model_fits": 1, "hierarchy_fits": 1},
        "F2": {"ridge_model_fits": 1, "hierarchy_fits": 1},
        "A0": {"ridge_model_fits": 0, "hierarchy_fits": 1},
        "A1": {"ridge_model_fits": 0, "hierarchy_fits": 1},
        "A2": {"ridge_model_fits": 1, "hierarchy_fits": 0},
    }
    assert (
        "unique [episode_id, query_molecule_id"
        in execution["operation_accounting_table"]["prediction_freeze"]
    )
    assert (
        "Eligibility-only sealed_episode_eligibility.csv opens add zero"
        in execution["operation_accounting_table"]["scorer"]
    )
    assert (
        "finite numeric query_point values"
        in execution["operation_accounting_table"]["scorer"]
    )
    target_accounting = execution["operation_accounting_table"][
        "target_capability_accounting"
    ]
    assert set(target_accounting["processes"]) == set(
        execution["private_prediction_fragment"]["system_id"]["vocabulary"]
    )
    assert "training_points.point" in target_accounting["source_rows"]["cell_target"]
    assert target_accounting["processes"]["C3"]["anchor_labels_exposed"].startswith(
        "0;"
    )
    assert target_accounting["processes"]["F0"][
        "direct_target_values_parsed"
    ].startswith("0;")
    for process in ("C2", "T0", "F2", "A0", "A1", "A2"):
        assert (
            "plus finite episode_anchor_contexts.anchor_point rows iff "
            "anchor_point_available=true"
            in target_accounting["processes"][process]["direct_target_values_parsed"]
        )
        assert target_accounting["processes"][process]["anchor_labels_exposed"] == (
            "one per episode_anchor_contexts row iff anchor_point_available=true"
        )
    ownership = execution["operation_accounting_table"]["counter_ownership"]
    assert (
        "Only the final prediction freezer owns predictions_frozen"
        in ownership["prediction_freezer"]
    )
    assert "Eligibility-only opens add zero" in ownership["scorer"]
    assert execution["scorer_transport"]["public_terminal_forbidden"] == [
        "complete_anchor",
        "anchor_point",
        "anchor_point_available",
        "query_truth",
        "score",
        "loss",
    ]


def test_v3_identity_serialization_is_exact_and_repeat_free() -> None:
    _, effective = _effective_contract()
    identity = effective["execution_overlay"]["identity"]
    candidate_material = ["R5-CYP3A4-ORACLE-V1", "T0", 1.0, 2.0]
    candidate = hashlib.sha256(_identity_bytes(candidate_material)).hexdigest()
    assert (
        candidate == "2cde50d6e3bc25d579ee3746771758e7e3f3de4d65950e6cf989756210050b40"
    )
    assert json.dumps(candidate_material, separators=(",", ":")) == (
        '["R5-CYP3A4-ORACLE-V1","T0",1.0,2.0]'
    )
    cell_material = [
        "R5-CYP3A4-ORACLE-V1",
        "outer",
        0,
        2,
        -1,
        "T0",
        candidate,
        "all",
    ]
    cell = hashlib.sha256(_identity_bytes(cell_material)).hexdigest()
    assert cell == "521751c5069314d09b14b272c99a9c3b2671c2c9bea2ce221ddaddeed6521152"
    query_material = ["episode-id", "query-molecule", 3]
    query = hashlib.sha256(_identity_bytes(query_material)).hexdigest()
    assert query == "e6163c1045dd2c3e82d33eb55858714c323430e68388ab5b9ffca9f2da53cf0c"
    assert "query_rank" in identity["f0_query_identity"]["serialization"]
    assert "repeat" not in identity["f0_query_identity"]["serialization"]


def test_v3_rejects_parent_drift_duplicate_keys_and_any_patch_mutation(
    tmp_path: Path,
) -> None:
    overlay = _load_verified(V3_PATH, V3_SHA256, "v3")
    parent = _load_verified(V2_PATH, V2_SHA256, "v2")
    with pytest.raises(ValueError, match="parent receipt differs"):
        mutated = tmp_path / "oracle_experiment_contract_v2.json"
        mutated.write_bytes(
            V2_PATH.read_bytes().replace(
                b"R5-CYP3A4-ORACLE-V2", b"R5-CYP3A4-ORACLE-X2", 1
            )
        )
        _apply_overlay(parent, overlay, parent_path=mutated)

    with pytest.raises(ValueError, match="v3 raw receipt differs before parse"):
        mutated = tmp_path / "oracle_experiment_contract_v3.json"
        mutated.write_bytes(
            V3_PATH.read_bytes().replace(
                b"R5-CYP3A4-ORACLE-V3", b"R5-CYP3A4-ORACLE-X3", 1
            )
        )
        _load_verified(mutated, V3_SHA256, "v3")

    for source, expected, label, old, new in (
        (
            V1_PATH,
            V1_SHA256,
            "v1",
            b"R5-CYP3A4-ORACLE-V1",
            b"R5-CYP3A4-ORACLE-X1",
        ),
        (
            V2_PATH,
            V2_SHA256,
            "v2",
            b"R5-CYP3A4-ORACLE-V2",
            b"R5-CYP3A4-ORACLE-X2",
        ),
    ):
        with pytest.raises(
            ValueError, match=f"{label} raw receipt differs before parse"
        ):
            mutated = tmp_path / f"{label}-raw-mutated.json"
            mutated.write_bytes(source.read_bytes().replace(old, new, 1))
            _load_verified(mutated, expected, label)

    with pytest.raises(ValueError, match="duplicate JSON key"):
        _strict_object(b'{"a":1,"a":2}')

    operation = overlay["resolution"]["operations"][0]
    with pytest.raises(ValueError, match="unknown operation"):
        unknown = copy.deepcopy(operation)
        unknown["op"] = "replace"
        _apply_operation(copy.deepcopy(parent), unknown)

    with pytest.raises(ValueError, match="member already exists"):
        preexisting = copy.deepcopy(operation)
        preexisting["member"] = "schema_version"
        _apply_operation(copy.deepcopy(parent), preexisting)

    with pytest.raises(ValueError, match="operation set differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["resolution"]["operations"].append(copy.deepcopy(operation))
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="top-level keyset differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["unexpected"] = True
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="operation keyset differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["resolution"]["operations"][0]["unexpected"] = True
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="operation path differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["resolution"]["operations"][0]["parent_object_pointer"] = (
            "/missing"
        )
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="operation member differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["resolution"]["operations"][0]["member"] = "other"
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="overlay value differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["resolution"]["operations"][0]["value"][
            "private_prediction_fragment"
        ]["columns"][0] = "molecule_id"
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    for section, field in (
        ("g0", "prediction_superset"),
        ("hash_domains", "resolved_contract"),
        ("operation_accounting", "g0_rule"),
    ):
        with pytest.raises(ValueError, match="overlay value differs"):
            mutated_overlay = copy.deepcopy(overlay)
            mutated_overlay["resolution"]["operations"][0]["value"][section][field] += (
                " mutation"
            )
            _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="unchanged flags differ"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["unchanged"]["science_and_populations"] = False
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(ValueError, match="authority differs"):
        mutated_overlay = copy.deepcopy(overlay)
        mutated_overlay["authority"]["predictions"] = True
        _apply_overlay(copy.deepcopy(parent), mutated_overlay, parent_path=V2_PATH)

    with pytest.raises(AssertionError, match="private fragment columns differ"):
        _, mutated_effective = _effective_contract()
        mutated_effective["execution_overlay"]["private_prediction_fragment"][
            "columns"
        ][0] = "molecule_id"
        _audit_resolved(mutated_effective)

    with pytest.raises(AssertionError, match="sealed completion field differs"):
        _, mutated_effective = _effective_contract()
        mutated_effective["execution_overlay"]["sealed_scorer_capability"]["columns"][
            3
        ] = "anchor_point"
        _audit_resolved(mutated_effective)

    with pytest.raises(AssertionError, match="stage mapping differs"):
        _, mutated_effective = _effective_contract()
        mutated_effective["execution_overlay"]["identity"]["stage_mapping"]["values"][
            "inner"
        ] = "INNER"
        _audit_resolved(mutated_effective)
