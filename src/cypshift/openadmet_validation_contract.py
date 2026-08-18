"""Exact executable policy checks for OpenADMET validation-contract v4."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

CONTRACT_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.validation_contract.v4"
CONTRACT_GATE = "R2_VALIDATION_CONTRACT_V4_FROZEN"
DIRECT_SOURCE_FILE = "cyp-challenge-TRAIN_inhibition.csv"
ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
SEEDS = (20260810, 20260811, 20260812)
OUTER_SCOPE = "openadmet-direct-outer-v1"
INNER_SCOPE = "openadmet-direct-inner-v1|outer=<outer_fold>"
FOLD_POLICY_ID = "openadmet-balanced-component-folds-sha256-v1"
EPISODE_ID_POLICY_ID = "openadmet-campaign-episode-sha256-v1"
JSON_CELL_POLICY_ID = "openadmet-campaign-json-cell-v1"
PROTOCOL = "ANCHOR_EXPANSION_HOLDOUT"
CANDIDATE_POOL_ID = "DEFERRED_NO_INFERRED_POOL_V1"
SELECTED_ANCHOR_POLICY = "selected_anchor"
STRESS_ANCHOR_POLICY = "deterministic_random_anchor_stress"
SELECTOR_ENDPOINTS = ("CYP1A2", "CYP2C9", "CYP3A4")
PUBLIC_EPISODE_COLUMNS = (
    "episode_id",
    "protocol",
    "repeat",
    "outer_fold",
    "outer_group_id",
    "query_molecule_ids",
    "candidate_pool_id",
    "episode_policy_id",
)
TRUTH_COLUMNS = (
    "episode_id",
    "selector_cyp_truth",
    "anchor_molecule_id_truth",
    "query_truth_references",
    "query_truth_availability_masks",
)
MASK_COLUMNS = (
    "episode_id",
    "anchor_molecule_id_truth",
    "anchor_observation_references",
    "anchor_value_availability_mask",
)
VALUE_FIELDS = ("point", "low", "high", "std")

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
    """Verify every v4 declaration implemented by the R2A compiler."""

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


def verify_r2b_contract(contract: Mapping[str, Any], source_revision: str) -> None:
    """Verify the result-affecting v4 declarations implemented by R2B."""

    verify_r2a_contract(contract, source_revision)
    episodes = _mapping(contract, "campaign_episodes")
    if (
        episodes.get("protocol") != PROTOCOL
        or episodes.get("candidate_pool_policy") != CANDIDATE_POOL_ID
        or episodes.get("outer_group_id") != "frozen D-032 similarity component hash"
        or episodes.get("repeat_expansion")
        != "Expand exactly the three frozen repeats; do not represent the three repeats times five outer-validation folds as fifteen episode contexts."
        or episodes.get("selector_endpoints") != list(SELECTOR_ENDPOINTS)
        or episodes.get("excluded_selector_endpoints") != ["CYP2D6"]
        or episodes.get("anchor_rule")
        != "Within a selected component, choose the complete selector measurement with maximum point; tie-break by narrower reported span (high - low), then molecule_id."
        or episodes.get("absolute_potency_cutoff") is not None
        or episodes.get("episode_eligibility")
        != "The selected anchor must have at least one other direct-training identity with a non-empty finite point for any direct endpoint and exact anchor-query similarity >= 0.60."
        or episodes.get("anchor_policies")
        != [SELECTED_ANCHOR_POLICY, STRESS_ANCHOR_POLICY]
        or _mapping(episodes, "episode_policy_tokens")
        != {
            SELECTED_ANCHOR_POLICY: SELECTED_ANCHOR_POLICY,
            STRESS_ANCHOR_POLICY: STRESS_ANCHOR_POLICY,
        }
    ):
        raise ValidationContractError("contract episode policy drift")
    query = _mapping(episodes, "query_rule")
    if query != {
        "identity": "other direct-training identity",
        "measurement": "any direct point, regardless of completeness",
        "similarity": ">= 0.60 to the selected anchor",
        "ranking": ["similarity descending", "molecule_id ascending"],
        "cap": 10,
        "availability": (
            "After anchor selection, non-anchor measurement availability may "
            "determine query eligibility or score masks, but non-anchor measurement "
            "magnitudes cannot affect query eligibility or ranking."
        ),
    }:
        raise ValidationContractError("contract query policy drift")
    stress = _mapping(episodes, "random_anchor_stress")
    if stress != {
        "purpose": "stress control only; never candidate selection, tuning, or fusion evidence",
        "seed": 20260818,
        "eligible_set": "complete selector observations in a primary-eligible component-selector cell that each have at least one query under the frozen query rule",
        "choice": "choose the smallest tuple of SHA256('20260818|deterministic-random-anchor-stress-v1|' + component_hash + '|' + selector_cyp + '|' + molecule_id), then molecule_id",
        "episodes": "exactly one stress episode per primary-eligible component-selector cell, using the same query rule and cap",
    }:
        raise ValidationContractError("contract stress-anchor policy drift")
    episode_id = _mapping(episodes, "episode_id_policy")
    if episode_id != {
        "policy_id": EPISODE_ID_POLICY_ID,
        "material": (
            "source_revision|protocol|repeat|outer_group_id|selector_cyp_truth|"
            "episode_policy_id"
        ),
        "digest": "SHA256",
        "encoding": (
            "lowercase hexadecimal, exactly 64 characters, matching ^[0-9a-f]{64}$"
        ),
        "meaning": "deterministic join pseudonym, not secrecy",
        "token_distinction": (
            "The selected_anchor and deterministic_random_anchor_stress tokens "
            "are distinct, so their IDs are distinct even when stress and selected "
            "anchors are the same molecule."
        ),
    }:
        raise ValidationContractError("contract episode-ID policy drift")
    serialization = _mapping(episodes, "serialization")
    if serialization != {
        "policy_id": JSON_CELL_POLICY_ID,
        "json": "compact JSON with sort_keys=True and separators=(',', ':')",
        "arrays": "Preserve query rank and array order; do not sort arrays.",
        "csv_rows": "Sort campaign_episodes_public.csv, campaign_episodes_truth.csv, and episode_label_masks.csv by episode_id ascending; corresponding rows must form exact one-to-one joins.",
        "fold_indices": "Encode repeat as the zero-based integer 0 through 2 and outer_fold as the zero-based integer 0 through 4.",
        "json_artifacts": "Serialize JSON artifacts with indent=2, sort_keys=True, and one trailing newline.",
        "episode_id_uniqueness": "All 1,122 expanded rows across selected_anchor and deterministic_random_anchor_stress must have unique episode_id values; duplicate IDs abort before output.",
    }:
        raise ValidationContractError("contract episode serialization drift")

    compiler = _mapping(contract, "direct_compiler")
    if compiler.get("observation_cardinality") != (
        "Exactly one observation per molecule_id and endpoint is required after "
        "identity resolution; fail closed on zero or multiple observations."
    ):
        raise ValidationContractError("contract observation-cardinality drift")
    local = _mapping(contract, "local_pairs")
    if (
        local.get("relation")
        != "unordered pair of distinct direct-training identities in the same frozen D-032 similarity component and endpoint"
        or local.get("eligibility")
        != [
            "both observations complete",
            "inclusive Morgan/Tanimoto similarity >= 0.60",
            "same endpoint",
            "same frozen component",
        ]
        or local.get("remote_pair_policy")
        != "Do not use transitive remote pairs; an edge qualifies only from its exact pairwise similarity."
        or _mapping(local, "status_rules")
        != {
            "LOCAL_SUPPORTED": "at least 50 eligible components, at least 200 eligible pairs, and every frozen outer fold meets the declared fold minimum after implementation",
            "LOCAL_UNDERPOWERED": "clean contract, identity, and leakage audit, but any LOCAL_SUPPORTED evidence threshold is not met; low sample support is never LOCAL_FAILED",
            "LOCAL_FAILED": "a scientific or contract-integrity defect, including receipt, identity, state, chemistry, determinism, or leakage failure",
            "fusion_weight": "0 for LOCAL_UNDERPOWERED and LOCAL_FAILED",
        }
    ):
        raise ValidationContractError("contract local-pair policy drift")

    firewall = _mapping(contract, "public_truth_firewall")
    if (
        firewall.get("public_episode_fields") != list(PUBLIC_EPISODE_COLUMNS)
        or firewall.get("truth_fields") != list(TRUTH_COLUMNS)
        or _mapping(firewall, "campaign_episodes_truth").get("columns")
        != list(TRUTH_COLUMNS)
        or _mapping(firewall, "episode_label_masks").get("columns")
        != list(MASK_COLUMNS)
        or _mapping(firewall, "episode_label_masks").get("endpoint_keys")
        != list(ENDPOINTS)
        or _mapping(firewall, "episode_label_masks").get("value_fields")
        != list(VALUE_FIELDS)
    ):
        raise ValidationContractError("contract firewall schema drift")
    public_schema = _mapping(
        _mapping(firewall, "public_csv_semantic_schema"), "columns"
    )
    expected_public_schema = {
        "episode_id": {
            "type": "string",
            "format": "lowercase SHA256 hex, exactly 64 characters",
        },
        "protocol": {"type": "string", "const": PROTOCOL},
        "repeat": {"type": "integer", "minimum": 0, "maximum": 2},
        "outer_fold": {"type": "integer", "minimum": 0, "maximum": 4},
        "outer_group_id": {
            "type": "string",
            "format": "lowercase SHA256 hex, exactly 64 characters",
        },
        "query_molecule_ids": {
            "type": "compact JSON array",
            "items": "nonempty molecule-ID strings in query-rank order",
        },
        "candidate_pool_id": {"type": "string", "const": CANDIDATE_POOL_ID},
        "episode_policy_id": {
            "type": "string",
            "enum": [SELECTED_ANCHOR_POLICY, STRESS_ANCHOR_POLICY],
        },
    }
    if public_schema != expected_public_schema:
        raise ValidationContractError("contract public semantic-schema drift")

    viability = _mapping(contract, "topology_viability")
    chemistry = _mapping(viability, "chemistry_policy")
    fingerprint = _mapping(chemistry, "fingerprint")
    folds = _mapping(contract, "folds")
    minimum = _mapping(folds, "fold_support_minimum")
    if (
        viability.get("schema_version")
        != "cypshift.openadmet_cyp_2026.topology_viability.v1"
        or viability.get("source_revision") != source_revision
        or chemistry.get("assert_standardized_structure_hash") is not True
        or fingerprint
        != {
            "family": "Morgan/ECFP4",
            "radius": 2,
            "n_bits": 4096,
            "use_chirality": True,
            "similarity": "inclusive Tanimoto >= 0.60",
        }
        or _mapping(viability, "fold_support_schema").get("count") != 15
        or minimum.get("eligible_components_per_outer_validation_fold") != 5
        or minimum.get("eligible_pairs_per_outer_validation_fold") != 20
        or _mapping(viability, "minimum_fold_counts").get("eligible_components") != 5
        or _mapping(viability, "minimum_fold_counts").get("eligible_pairs") != 20
        or _mapping(contract, "activity_cliff").get("eligibility")
        != [
            "direct pair similarity >= 0.60",
            "absolute point delta >= 1.0",
            "a.high < b.low OR b.high < a.low",
        ]
    ):
        raise ValidationContractError("contract topology-viability policy drift")
    future_artifacts = _mapping(contract, "future_artifacts")
    required = future_artifacts.get("required")
    if required != [
        "direct_observations.csv",
        "group_folds.csv",
        "campaign_episodes_public.csv",
        "campaign_episodes_truth.csv",
        "episode_label_masks.csv",
        "topology_viability.json",
        "manifest.json",
    ]:
        raise ValidationContractError("contract future-artifact drift")
    if future_artifacts.get("manifest_requirements") != [
        "schemas",
        "policy IDs",
        "input hashes",
        "output hashes",
        "source revisions",
        "seeds",
        "scope and authority flags",
        "zero TDI access",
        "zero blinded-test access",
    ]:
        raise ValidationContractError("contract manifest-requirement drift")
    after = _mapping(contract, "authority_after_successful_r2b")
    expected_true = {
        "fold_assignments",
        "episodes",
        "episode_labels",
        "topology_viability",
    }
    if set(after) != _FALSE_AUTHORITIES | {"status_note"} or any(
        after.get(key) is not (key in expected_true) for key in _FALSE_AUTHORITIES
    ):
        raise ValidationContractError("contract post-R2B authority drift")
    artifact_authority = _mapping(viability, "artifact_authority")
    expected_artifact_authority = {
        key: value for key, value in after.items() if key != "status_note"
    }
    if artifact_authority != expected_artifact_authority:
        raise ValidationContractError("contract topology artifact authority drift")
    accounting = _mapping(
        _mapping(_mapping(contract, "acceptance"), "r2b_success"), "accounting"
    )
    if accounting != {
        "tdi_files_opened": 0,
        "blinded_test_files_opened": 0,
        "model_fits": 0,
        "predictions": 0,
        "metric_evaluations": 0,
        "submissions": 0,
    }:
        raise ValidationContractError("contract R2B accounting drift")


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
    "CANDIDATE_POOL_ID",
    "CONTRACT_GATE",
    "CONTRACT_SCHEMA_VERSION",
    "DIRECT_SOURCE_FILE",
    "ENDPOINTS",
    "EPISODE_ID_POLICY_ID",
    "FOLD_POLICY_ID",
    "INNER_SCOPE",
    "JSON_CELL_POLICY_ID",
    "MASK_COLUMNS",
    "OUTER_SCOPE",
    "PROTOCOL",
    "PUBLIC_EPISODE_COLUMNS",
    "SEEDS",
    "SELECTED_ANCHOR_POLICY",
    "SELECTOR_ENDPOINTS",
    "STRESS_ANCHOR_POLICY",
    "TRUTH_COLUMNS",
    "VALUE_FIELDS",
    "ValidationContractError",
    "verify_r2a_contract",
    "verify_r2b_contract",
]
