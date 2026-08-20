"""Exact in-memory R4 episode and coverage serialization.

This slice converts accepted structural geometry and support arithmetic into the
two remaining scientific payloads.  Filesystem publication, official receipt
authentication, and manifests deliberately remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from cypshift.openadmet_transformation_compiler import TransformationGeometry
from cypshift.openadmet_transformation_coverage import (
    OpenADMETTransformationCoverageError,
)
from cypshift.openadmet_transformation_io import (
    canonical_csv_bytes,
    canonical_json_bytes,
)
from cypshift.openadmet_transformation_support import (
    STATUS_VALUES,
    VALID_STATUSES,
    FrequencyRecord,
    StatusPartition,
    TransformationSupport,
)
from cypshift.openadmet_transformation_types import canonical_json

CONTRACT_SHA256: Final[str] = (
    "63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954"
)

EPISODE_COLUMNS: Final[tuple[str, ...]] = (
    "episode_id",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "outer_group_id",
    "query_molecule_id",
    "query_rank",
    "anchor_molecule_id",
    "transformation_pair_id",
    "direction_id",
    "extraction_status",
    "failure_code",
    "cut_count",
    "exact_transformation_id",
    "transformation_class_id",
    "environment_level_1_id",
    "environment_level_2_id",
    "changed_heavy_atom_fraction",
    "cyp3a4_training_family_exact_support_count",
    "cyp3a4_training_family_class_support_count",
    "tie_count",
    "tie_material",
    "tie_digest",
    "ambiguous",
    "warnings",
)

_FRACTION_NAMES: Final[dict[str, str]] = {
    "VALID_STEREO": "valid_stereo_fraction",
    "VALID_SINGLE": "single_cut_fraction",
    "VALID_DOUBLE": "double_cut_fraction",
    "AMBIGUOUS": "ambiguous_fraction",
    "UNSUPPORTED": "unsupported_fraction",
    "STANDARDIZATION_HAZARD": "standardization_hazard_fraction",
}

_ACCOUNTING: Final[dict[str, int]] = {
    "numeric_target_magnitudes_parsed": 0,
    "numeric_target_magnitudes_retained": 0,
    "tdi_rows_opened": 0,
    "blinded_test_rows_opened": 0,
    "model_fits": 0,
    "predictions_generated": 0,
    "metric_evaluations": 0,
    "official_scorer_calls": 0,
    "leaderboard_submissions": 0,
    "transductive_operations": 0,
}


@dataclass(frozen=True, slots=True)
class TransformationSerialization:
    """The two deterministic R4 payloads before publication."""

    episode_transformations_csv: bytes
    transformation_coverage_json: bytes


def serialize_transformation_results(
    geometry: TransformationGeometry, support: TransformationSupport
) -> TransformationSerialization:
    """Serialize exact episode and aggregate coverage artifacts."""

    episode_csv = _episode_csv(geometry, support)
    coverage_json = canonical_json_bytes(_coverage_value(support))
    return TransformationSerialization(episode_csv, coverage_json)


def _episode_csv(
    geometry: TransformationGeometry, support: TransformationSupport
) -> bytes:
    support_by_key = {
        (row.episode_id, row.query_rank): row
        for row in support.episode_training_support
    }
    if len(support_by_key) != len(support.episode_training_support):
        raise OpenADMETTransformationCoverageError("duplicate episode support")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, int]] = set()
    for item in sorted(
        geometry.episodes,
        key=lambda row: (row.episode.episode_id, row.episode.query_rank),
    ):
        episode = item.episode
        key = (episode.episode_id, episode.query_rank)
        if key in seen:
            raise OpenADMETTransformationCoverageError("duplicate episode geometry")
        seen.add(key)
        training = support_by_key.get(key)
        if training is None:
            raise OpenADMETTransformationCoverageError("missing episode support")
        direction = item.direction
        pair = item.pair.result
        valid = direction.extraction_status in VALID_STATUSES
        rows.append(
            {
                "episode_id": episode.episode_id,
                "episode_policy_id": episode.episode_policy_id,
                "repeat": str(episode.repeat),
                "outer_fold": str(episode.outer_fold),
                "outer_group_id": episode.outer_group_id,
                "query_molecule_id": episode.query_molecule_id,
                "query_rank": str(episode.query_rank),
                "anchor_molecule_id": episode.anchor_molecule_id,
                "transformation_pair_id": pair.transformation_pair_id,
                "direction_id": direction.direction_id,
                "extraction_status": direction.extraction_status,
                "failure_code": direction.failure_code,
                "cut_count": "" if not valid else str(direction.cut_count),
                "exact_transformation_id": (
                    direction.exact_transformation_id if valid else ""
                ),
                "transformation_class_id": (
                    direction.transformation_class_id if valid else ""
                ),
                "environment_level_1_id": (
                    direction.environment_level_1_id if valid else ""
                ),
                "environment_level_2_id": (
                    direction.environment_level_2_id if valid else ""
                ),
                "changed_heavy_atom_fraction": (
                    direction.changed_heavy_atom_fraction if valid else ""
                ),
                "cyp3a4_training_family_exact_support_count": str(
                    training.exact if valid else 0
                ),
                "cyp3a4_training_family_class_support_count": str(
                    training.transformation_class if valid else 0
                ),
                "tie_count": str(pair.tie_count),
                "tie_material": _compact_json(pair.tie_material),
                "tie_digest": pair.tie_digest,
                "ambiguous": _boolean(direction.ambiguous),
                "warnings": _compact_json(direction.warnings),
            }
        )
    if seen != set(support_by_key):
        raise OpenADMETTransformationCoverageError("unused episode support")
    return canonical_csv_bytes(EPISODE_COLUMNS, rows)


def _coverage_value(support: TransformationSupport) -> dict[str, Any]:
    simple_partitions = {
        "union": support.status_partition_union,
        "selected_primary": support.status_partition_selected_primary,
        "stress": support.status_partition_stress,
    }
    local_partitions = dict(support.status_partition_local_by_endpoint)
    counts: dict[str, Any] = {
        name: _count_record(partition) for name, partition in simple_partitions.items()
    }
    counts["local_by_endpoint"] = {
        endpoint: _count_record(partition)
        for endpoint, partition in sorted(local_partitions.items())
    }
    status_partition: dict[str, Any] = {
        name: dict(partition.counts) for name, partition in simple_partitions.items()
    }
    status_partition["local_by_endpoint"] = {
        endpoint: dict(partition.counts)
        for endpoint, partition in sorted(local_partitions.items())
    }
    fractions: dict[str, Any] = {
        name: _fraction_record(partition)
        for name, partition in simple_partitions.items()
    }
    fractions["local_by_endpoint"] = {
        endpoint: _fraction_record(partition)
        for endpoint, partition in sorted(local_partitions.items())
    }
    return {
        "contract_sha256": CONTRACT_SHA256,
        "status": support.status,
        "counts": counts,
        "status_partition": status_partition,
        "fractions": fractions,
        "frequency_units": {
            "scope": "union of directional valid views",
            "exact_transformation_frequency": (
                "count of distinct valid directional views per reusable "
                "exact_transformation_id; denominator is the union of valid "
                "directional views"
            ),
            "transformation_class_frequency": (
                "count of distinct valid directional views per reusable class "
                "token; denominator is the union of valid directional views"
            ),
            "two_direction_denominator": (
                "Each valid structural pair contributes exactly two directional "
                "views, so the denominator is 2 * valid structural pair rows in "
                "the partition; invalid rows contribute zero views."
            ),
            "independent_group_support": (
                "exact and class maps each contain only full-population "
                "families_overall, counting each frozen D-032 component once "
                "across endpoint and direction duplication with no held-out "
                "exclusion; episode-specific held-out support remains in CSV columns"
            ),
            "cross_cyp_valid_transformation_sharing": (
                "distinct reusable exact_transformation_id present with valid "
                "status in at least two endpoint aggregate partitions"
            ),
        },
        "exact_transformation_frequency": _frequency_map(
            support.exact_transformation_frequency
        ),
        "transformation_class_frequency": _frequency_map(
            support.transformation_class_frequency
        ),
        "independent_group_support": {
            "exact": {
                key: {"families_overall": value}
                for key, value in support.independent_group_support.exact
            },
            "class": {
                key: {"families_overall": value}
                for key, value in support.independent_group_support.transformation_class
            },
        },
        "valid_changed_heavy_atom_fraction_distribution": _distribution(support),
        "cross_cyp_valid_transformation_sharing": {
            key: {
                "endpoints": list(endpoints),
                "endpoint_count": len(endpoints),
                "unit": "one reusable exact ID",
            }
            for key, endpoints in support.cross_cyp_valid_transformation_sharing
        },
        "test_query_coverage": {
            "status": "NOT_COMPUTED_TEST_ACCESS_FORBIDDEN",
            "values": None,
        },
        "selected_anchor_structural_coverage": _selected_coverage(support),
        "local_cyp3a4_state": _local_state(support),
        "accounting": dict(_ACCOUNTING),
        "authority": _authority(support.status),
    }


def _count_record(partition: StatusPartition) -> dict[str, int]:
    return {
        "denominator_rows": partition.denominator_rows,
        "valid_rows": sum(partition.count(status) for status in VALID_STATUSES),
        "single_cut_rows": partition.count("VALID_SINGLE"),
        "double_cut_rows": partition.count("VALID_DOUBLE"),
    }


def _fraction_record(partition: StatusPartition) -> dict[str, str]:
    by_status = dict(partition.fractions)
    return {_FRACTION_NAMES[status]: by_status[status] for status in STATUS_VALUES}


def _frequency_map(
    values: tuple[tuple[str, FrequencyRecord], ...],
) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "rows": record.rows,
            "denominator_rows": record.denominator_rows,
            "unit": "distinct valid directional views",
            "scope": "union of directional valid views",
        }
        for key, record in values
    }


def _distribution(support: TransformationSupport) -> dict[str, Any]:
    value = support.valid_changed_heavy_atom_fraction_distribution
    return {
        "count": value.count,
        "unique_rationals": value.unique_rationals,
        "min": value.min,
        "median": value.median,
        "max": value.max,
        "histogram": dict(value.histogram),
    }


def _selected_coverage(support: TransformationSupport) -> dict[str, Any]:
    value = support.selected_anchor_structural_coverage
    return {
        "status": value.status,
        "rows": value.rows,
        "valid_rows": value.valid_rows,
        "distinct_families_overall": value.distinct_families_overall,
        "cell_support": [
            {
                "repeat": cell.repeat,
                "outer_fold": cell.outer_fold,
                "rows": cell.rows,
                "valid_rows": cell.valid_rows,
                "distinct_families": cell.distinct_families,
                "meets_gate": cell.meets_gate,
            }
            for cell in value.cell_support
        ],
        "meets_gate": value.meets_gate,
    }


def _local_state(support: TransformationSupport) -> dict[str, Any]:
    value = support.local_cyp3a4_state
    return {
        "status": value.status,
        "overall": {
            "families": value.overall_families,
            "pairs": value.overall_pairs,
        },
        "fold_cells": [
            {
                "repeat": cell.repeat,
                "outer_validation_fold": cell.outer_validation_fold,
                "families": cell.families,
                "pairs": cell.pairs,
                "meets_gate": cell.meets_gate,
            }
            for cell in value.fold_cells
        ],
        "meets_gate": value.meets_gate,
    }


def _authority(status: str) -> dict[str, Any]:
    underpowered = status == "R4_TRANSFORMATION_COVERAGE_UNDERPOWERED"
    supported = status == "R4_TRANSFORMATION_COVERAGE_SUPPORTED"
    if not (underpowered or supported):
        raise OpenADMETTransformationCoverageError("invalid coverage status")
    return {
        "status": status,
        "geometry_coverage": underpowered or supported,
        "oracle_contract_freeze": supported,
        "model_fits": False,
        "predictions": False,
        "metrics": False,
        "official_st_rae": False,
        "test_access": False,
        "tdi": False,
        "submissions": False,
        "transduction": False,
    }


def _compact_json(value: Any) -> str:
    return canonical_json(value).decode("utf-8")


def _boolean(value: bool) -> str:
    return "true" if value else "false"


__all__ = [
    "CONTRACT_SHA256",
    "EPISODE_COLUMNS",
    "TransformationSerialization",
    "serialize_transformation_results",
]
