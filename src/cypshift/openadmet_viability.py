"""Independent pair, fold-support, and cliff facts for OpenADMET R2B."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from cypshift.openadmet_validation import R2A_SCHEMA_VERSION
from cypshift.openadmet_validation_contract import (
    CONTRACT_SCHEMA_VERSION,
    ENDPOINTS,
    SEEDS,
)

TOPOLOGY_VIABILITY_SCHEMA_VERSION = "cypshift.openadmet_cyp_2026.topology_viability.v1"


class ViabilityError(ValueError):
    """Computed R2B viability facts disagree with the frozen contract."""


@dataclass(frozen=True, slots=True)
class DirectPair:
    """One exact Morgan edge inside a frozen component."""

    left: str
    right: str
    component: str
    similarity: float


def compute_viability(
    pairs: Sequence[DirectPair],
    observations: Mapping[str, Mapping[str, Mapping[str, str]]],
    outer_folds: Mapping[tuple[str, int], int],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    """Recompute every endpoint, fold-support, and strict cliff diagnostic."""

    fold_minimum = _mapping(_mapping(contract, "folds"), "fold_support_minimum")
    minimum_components = cast(
        int, fold_minimum["eligible_components_per_outer_validation_fold"]
    )
    minimum_pairs = cast(int, fold_minimum["eligible_pairs_per_outer_validation_fold"])
    endpoint_map: dict[str, Any] = {}
    cliffs: dict[str, dict[str, int]] = {}
    for endpoint in ENDPOINTS:
        eligible = [
            pair
            for pair in pairs
            if observations[pair.left][endpoint]["value_state"] == "complete"
            and observations[pair.right][endpoint]["value_state"] == "complete"
        ]
        components = {pair.component for pair in eligible}
        cells: list[dict[str, int | bool]] = []
        for repeat, seed in enumerate(SEEDS):
            for outer_fold in range(5):
                selected = [
                    pair
                    for pair in eligible
                    if outer_folds[(pair.component, repeat)] == outer_fold
                ]
                component_count = len({pair.component for pair in selected})
                pair_count = len(selected)
                cells.append(
                    {
                        "repeat": repeat,
                        "seed": seed,
                        "outer_fold": outer_fold,
                        "component_count": component_count,
                        "pair_count": pair_count,
                        "meets_minimum": component_count >= minimum_components
                        and pair_count >= minimum_pairs,
                    }
                )
        supported = (
            len(components) >= 50
            and len(eligible) >= 200
            and all(cast(bool, cell["meets_minimum"]) for cell in cells)
        )
        endpoint_map[endpoint] = {
            "eligible_components": len(components),
            "eligible_pairs": len(eligible),
            "fold_support_cells": cells,
            "status": "LOCAL_SUPPORTED" if supported else "LOCAL_UNDERPOWERED",
            "fusion_weight": None if supported else 0.0,
        }
        cliff_pairs = [
            pair for pair in eligible if _is_cliff(pair, endpoint, observations)
        ]
        cliffs[endpoint] = {
            "pairs": len(cliff_pairs),
            "components": len({pair.component for pair in cliff_pairs}),
        }
    return endpoint_map, cliffs


def verify_frozen_facts(
    contract: Mapping[str, Any],
    episode_diagnostics: Mapping[str, Any],
    selector_diagnostics: Mapping[str, Any],
    endpoint_map: Mapping[str, Any],
    cliffs: Mapping[str, Any],
    artifact_counts: Mapping[str, int],
) -> None:
    """Fail before output if any computed fact differs from v4."""

    viability = _mapping(contract, "topology_viability")
    if endpoint_map != _mapping(viability, "endpoint_map"):
        raise ViabilityError("topology endpoint diagnostics mismatch")
    if cliffs != _mapping(viability, "activity_cliff_counts"):
        raise ViabilityError("activity-cliff diagnostics mismatch")
    if episode_diagnostics != _mapping(viability, "episode_diagnostics"):
        raise ViabilityError("episode diagnostics mismatch")
    episodes = _mapping(contract, "campaign_episodes")
    preliminary = _mapping(episodes, "preliminary_diagnostics")
    if any(
        selector_diagnostics[key] != preliminary.get(key)
        for key in selector_diagnostics
    ):
        raise ViabilityError("selector episode diagnostics mismatch")
    official = _mapping(episodes, "official_diagnostics")
    repeat = _mapping(official, "repeat_expansion")
    inference = _mapping(official, "identity_inference_diagnostic")
    if (
        official.get("primary_base") != episode_diagnostics["primary_base"]
        or official.get("stress_base") != episode_diagnostics["stress_base"]
        or repeat
        != {
            "repeats": len(SEEDS),
            **{
                key: episode_diagnostics[key]
                for key in (
                    "expanded_artifact_rows_each",
                    "total_expanded_queries",
                    "anchor_observation_references",
                    "query_observation_references",
                )
            },
        }
        or inference.get("primary_selected_episodes_with_anchor_inference")
        != episode_diagnostics["primary_anchor_inference"]
        or inference.get("stress_selected_episodes_with_anchor_inference")
        != episode_diagnostics["stress_anchor_inference"]
    ):
        raise ViabilityError("official episode diagnostics mismatch")
    counts = _mapping(
        _mapping(_mapping(contract, "acceptance"), "r2b_success"),
        "exact_artifact_counts",
    )
    if artifact_counts != counts:
        raise ViabilityError("R2B exact artifact counts mismatch")


def build_topology_viability(
    contract: Mapping[str, Any],
    contract_hash: str,
    r2a_hashes: Mapping[str, str],
    endpoint_map: Mapping[str, Any],
    cliffs: Mapping[str, Any],
    episode_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    """Construct the exact v4 topology-viability schema from computed facts."""

    frozen = _mapping(contract, "topology_viability")
    receipts = _mapping(frozen, "input_receipts")
    r2a = _mapping(receipts, "r2a_validation_inputs")
    return {
        "schema_version": TOPOLOGY_VIABILITY_SCHEMA_VERSION,
        "source_revision": frozen["source_revision"],
        "validation_contract": {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "sha256": contract_hash,
        },
        "input_receipts": {
            "direct_source": _mapping(receipts, "direct_source"),
            "r1_source_row_adapter": _mapping(receipts, "r1_source_row_adapter"),
            "r1_topology": _mapping(receipts, "r1_topology"),
            "r2a_validation_inputs": {
                "schema_version": R2A_SCHEMA_VERSION,
                "manifest_sha256": r2a_hashes["manifest.json"],
                "direct_observations.csv": _mapping(r2a, "direct_observations.csv"),
                "group_folds.csv": _mapping(r2a, "group_folds.csv"),
            },
        },
        "chemistry_policy": _mapping(frozen, "chemistry_policy"),
        "fold_support_schema": _mapping(frozen, "fold_support_schema"),
        "endpoint_map": endpoint_map,
        "minimum_fold_counts": _mapping(frozen, "minimum_fold_counts"),
        "activity_cliff_counts": cliffs,
        "episode_diagnostics": episode_diagnostics,
        "artifact_authority": _mapping(frozen, "artifact_authority"),
        "serialization": _mapping(frozen, "serialization"),
        "forbidden": frozen["forbidden"],
        "failure_policy": frozen["failure_policy"],
        "interpretation": frozen["interpretation"],
    }


def _is_cliff(
    pair: DirectPair,
    endpoint: str,
    observations: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> bool:
    left = observations[pair.left][endpoint]
    right = observations[pair.right][endpoint]
    return abs(float(left["point"]) - float(right["point"])) >= 1.0 and (
        float(left["high"]) < float(right["low"])
        or float(right["high"]) < float(left["low"])
    )


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ViabilityError(f"{key} must be an object")
    return cast(dict[str, Any], item)


__all__ = [
    "DirectPair",
    "TOPOLOGY_VIABILITY_SCHEMA_VERSION",
    "ViabilityError",
    "build_topology_viability",
    "compute_viability",
    "verify_frozen_facts",
]
