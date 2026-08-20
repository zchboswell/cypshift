from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "oracle_experiment_contract_v1.json"
)
V2_PATH = (
    ROOT / "benchmarks" / "openadmet_cyp_2026" / "oracle_experiment_contract_v2.json"
)
V1_SHA256 = "c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf"
TARGET_POINTER = "/folds"


def _strict_object(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key: {key}")
            value[key] = item
        return value

    loaded = json.loads(path.read_bytes(), object_pairs_hook=reject_duplicates)
    assert isinstance(loaded, dict)
    return loaded


def _resolve_pointer(root: dict[str, Any], pointer: str) -> dict[str, Any]:
    assert pointer.startswith("/")
    value: Any = root
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        assert isinstance(value, dict)
        assert token in value
        value = value[token]
    assert isinstance(value, dict)
    return value


def _apply_operation(root: dict[str, Any], operation: dict[str, Any]) -> None:
    if operation.get("op") != "add_absent_object_member":
        raise ValueError("unknown operation")
    target = _resolve_pointer(root, operation["parent_object_pointer"])
    member = operation["member"]
    if member in target:
        raise ValueError("member already exists")
    target[member] = operation["value"]


def _effective_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    parent = _strict_object(V1_PATH)
    overlay = _strict_object(V2_PATH)
    effective = copy.deepcopy(parent)
    operations = overlay["resolution"]["operations"]
    assert isinstance(operations, list) and len(operations) == 1
    _apply_operation(effective, operations[0])
    return overlay, effective


def test_v2_binds_exact_parent_and_one_addition_only() -> None:
    overlay, effective = _effective_contract()
    assert hashlib.sha256(V1_PATH.read_bytes()).hexdigest() == V1_SHA256
    assert overlay["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/oracle_experiment_contract_v1.json",
        "schema_version": "cypshift.openadmet_cyp_2026.oracle_experiment_contract.v1",
        "contract_id": "R5-CYP3A4-ORACLE-V1",
        "sha256": V1_SHA256,
    }
    operation = overlay["resolution"]["operations"][0]
    assert operation["parent_object_pointer"] == TARGET_POINTER
    assert operation["member"] == "diagnostic_stress_scope"
    parent = _strict_object(V1_PATH)
    assert set(effective["folds"]) - set(parent["folds"]) == {"diagnostic_stress_scope"}
    for key in parent:
        if key != "folds":
            assert effective[key] == parent[key]


def test_v2_freezes_selected_only_inner_and_outer_only_stress() -> None:
    _, effective = _effective_contract()
    stress = effective["folds"]["diagnostic_stress_scope"]
    assert set(stress) == {
        "inner_membership",
        "outer_membership",
        "model_context",
        "hyperparameters",
        "sealed_scoring",
        "non_authority",
    }
    assert stress["inner_membership"].startswith(
        "No deterministic_random_anchor_stress"
    )
    assert "every query row" in stress["outer_membership"]
    assert "score-free hyperparameters" in stress["hyperparameters"]
    assert "diagnostic facts only" in stress["sealed_scoring"]
    for forbidden_use in (
        "primary support",
        "required contrasts",
        "safety fusion",
        "status resolution",
    ):
        assert forbidden_use in stress["non_authority"]


def test_v2_preserves_science_and_denies_execution_authority() -> None:
    overlay, effective = _effective_contract()
    assert overlay["unchanged"] == {
        "primary_selected_anchor_population": True,
        "systems_features_targets_and_hyperparameters": True,
        "inner_selection": True,
        "outer_primary_scoring": True,
        "support_thresholds": True,
        "bootstrap_influence_and_safety": True,
        "acceptance_and_statuses": True,
        "output_schemas_and_publication": True,
        "forbidden_operations": True,
        "authority": True,
    }
    assert effective["acceptance"] == _strict_object(V1_PATH)["acceptance"]
    assert overlay["authority"]["contract_only"] is True
    assert all(
        value is False
        for key, value in overlay["authority"].items()
        if key != "contract_only"
    )


def test_v2_resolution_rejects_unknown_or_preexisting_mutation() -> None:
    overlay = _strict_object(V2_PATH)
    operation = overlay["resolution"]["operations"][0]
    assert operation["op"] == "add_absent_object_member"
    parent = _strict_object(V1_PATH)
    target = _resolve_pointer(parent, operation["parent_object_pointer"])
    assert operation["member"] not in target
    poisoned = copy.deepcopy(parent)
    _resolve_pointer(poisoned, TARGET_POINTER)[operation["member"]] = "poison"
    try:
        _apply_operation(poisoned, operation)
    except ValueError as exc:
        assert str(exc) == "member already exists"
    else:
        raise AssertionError("preexisting member was accepted")
    unknown = copy.deepcopy(operation)
    unknown["op"] = "replace"
    try:
        _apply_operation(copy.deepcopy(parent), unknown)
    except ValueError as exc:
        assert str(exc) == "unknown operation"
    else:
        raise AssertionError("unknown operation was accepted")
