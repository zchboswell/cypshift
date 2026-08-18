"""Exact executable policy checks for OpenADMET validation-contract v3."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

CONTRACT_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.validation_contract.v3"
CONTRACT_GATE = "R2_VALIDATION_CONTRACT_V3_FROZEN"
DIRECT_SOURCE_FILE = "cyp-challenge-TRAIN_inhibition.csv"
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
SEEDS = (20260810, 20260811, 20260812)
OUTER_SCOPE = "openadmet-direct-outer-v1"
INNER_SCOPE = "openadmet-direct-inner-v1|outer=<outer_fold>"
FOLD_POLICY_ID = "openadmet-balanced-component-folds-sha256-v1"

_STATE_RULES = {
    "missing": "point, low, high, and std are all empty",
    "complete": (
        "point, low, high, and std are all present and finite, "
        "low <= point <= high, and std >= 0"
    ),
    "orphan_auxiliary": (
        "point is empty and at least one of low, high, or std is non-empty"
    ),
    "partial": (
        "point is finite, at least one auxiliary is empty, every present "
        "auxiliary is finite, any present std is nonnegative, any present "
        "low is <= point, and any present high is >= point"
    ),
}
_FIELDS = {
    "point": "reported point pIC50",
    "low": "reported low bound",
    "high": "reported high bound",
    "std": "reported standard deviation",
}
_ALGORITHM = {
    "policy_id": FOLD_POLICY_ID,
    "group_weight": (
        "number of unique direct-training molecule identities in the component, "
        "independent of endpoint labels and availability"
    ),
    "group_order": (
        "sort by descending group_weight, then SHA256(seed + '|' + scope + "
        "'|group-order-v1|' + component_hash), then component_hash"
    ),
    "fold_choice": (
        "assign to the fold with smallest current molecule weight, then smallest "
        "SHA256(seed + '|' + scope + '|fold-tie-v1|' + component_hash + '|' + "
        "fold_index), then smallest fold_index"
    ),
    "outer_scope": OUTER_SCOPE,
    "inner_scope": INNER_SCOPE,
    "inner_population": (
        "all components outside the selected outer fold; reuse the repeat seed "
        "with the scoped outer-fold identifier"
    ),
}
_FALSE_AUTHORITIES = {
    "validation",
    "models",
    "metrics",
    "submissions",
    "fold_assignments",
    "episodes",
    "episode_labels",
    "topology_viability",
    "tdi",
    "predictions",
    "transduction",
}


class ValidationContractError(ValueError):
    """The tracked validation policy is inconsistent or expanded."""


def verify_r2a_contract(contract: Mapping[str, Any], source_revision: str) -> None:
    """Verify every v3 declaration implemented by the R2A compiler."""

    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValidationContractError("unsupported validation contract schema")
    if contract.get("gate") != CONTRACT_GATE:
        raise ValidationContractError("validation contract gate mismatch")
    if contract.get("status") != "contract_only_not_validation_frozen":
        raise ValidationContractError("validation contract status drift")
    inputs = _mapping(contract, "input_chain")
    if inputs.get("dataset_revision") != source_revision:
        raise ValidationContractError("contract source revision mismatch")
    compiler = _mapping(contract, "direct_compiler")
    if compiler.get("endpoints") != list(ENDPOINTS):
        raise ValidationContractError("contract direct endpoint drift")
    if _mapping(compiler, "fields") != _FIELDS:
        raise ValidationContractError("contract direct field drift")
    if _mapping(compiler, "state_rules") != _STATE_RULES:
        raise ValidationContractError("contract direct state-rule drift")
    row_contract = _mapping(compiler, "row_contract")
    direct_receipt = _mapping(inputs, "direct_source")
    if direct_receipt.get("path") != DIRECT_SOURCE_FILE:
        raise ValidationContractError("contract direct source path drift")
    source_rows = _integer(direct_receipt, "rows")
    if (
        row_contract.get("source_identities") != source_rows
        or row_contract.get("rows_per_identity") != len(ENDPOINTS)
        or row_contract.get("expected_rows") != source_rows * len(ENDPOINTS)
    ):
        raise ValidationContractError("contract direct row-count drift")
    source_policy = _mapping(compiler, "source_policy")
    if source_policy.get("allowed_files") != [DIRECT_SOURCE_FILE]:
        raise ValidationContractError("contract direct source policy drift")
    forbidden = source_policy.get("forbidden_files")
    if not isinstance(forbidden, list) or set(forbidden) != {
        "cyp-challenge-TRAIN_TDI.csv",
        "cyp-challenge-TRAIN_Emax.csv",
        "cyp-challenge-single-concentration-TRAIN.csv",
        "cyp-challenge-TEST-BLINDED.csv",
    }:
        raise ValidationContractError("contract forbidden source policy drift")
    folds = _mapping(contract, "folds")
    if (
        folds.get("repeats") != len(SEEDS)
        or folds.get("seeds") != list(SEEDS)
        or folds.get("outer_folds") != 5
        or folds.get("inner_folds") != 4
        or _mapping(folds, "assignment_algorithm") != _ALGORITHM
    ):
        raise ValidationContractError("contract fold policy drift")
    authority = _mapping(contract, "authority")
    if set(authority) != _FALSE_AUTHORITIES | {"status_note"} or any(
        authority.get(key) is not False for key in _FALSE_AUTHORITIES
    ):
        raise ValidationContractError("contract authority expansion")


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValidationContractError(f"{key} must be an object")
    return cast(dict[str, Any], item)


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise ValidationContractError(f"{key} must be a nonnegative integer")
    return item


__all__ = [
    "CONTRACT_GATE",
    "CONTRACT_SCHEMA_VERSION",
    "DIRECT_SOURCE_FILE",
    "ENDPOINTS",
    "FOLD_POLICY_ID",
    "INNER_SCOPE",
    "OUTER_SCOPE",
    "SEEDS",
    "ValidationContractError",
    "verify_r2a_contract",
]
