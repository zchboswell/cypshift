"""Strict R4 geometry checks for the synthetic TRACE capability splitter."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from hashlib import sha256

from cypshift.openadmet_transformation_support import STATUS_VALUES, VALID_STATUSES
from cypshift.openadmet_transformation_types import (
    EXTRACTION_SPEC_RECEIPT,
    sha256_json_array,
)

PUBLIC_METADATA = (
    "episode_id",
    "episode_policy_id",
    "repeat",
    "outer_fold",
    "outer_group_id",
    "anchor_molecule_id",
    "query_molecule_id",
    "query_rank",
)


class OracleGeometryValidationError(ValueError):
    """Synthetic R4 geometry is not exact or internally linked."""


def validate_geometry(
    rows: Mapping[str, Sequence[Mapping[str, str]]],
    molecules: Mapping[str, Mapping[str, str]],
    public: Mapping[tuple[str, str], Mapping[str, str]],
) -> dict[str, Mapping[str, str]]:
    """Validate pair identities, grammar, and every episode join."""

    pairs: dict[str, Mapping[str, str]] = {}
    expected_cut = {"VALID_STEREO": 0, "VALID_SINGLE": 1, "VALID_DOUBLE": 2}
    for row in rows["transformation_pairs.csv"]:
        pair_id = row["transformation_pair_id"]
        _digest(pair_id, "transformation pair ID")
        left = row["left_molecule_id"]
        right = row["right_molecule_id"]
        if pair_id in pairs or left not in molecules or right not in molecules:
            raise OracleGeometryValidationError("transformation pair identity differs")
        ordered = sorted(
            (left, right),
            key=lambda molecule: (
                molecules[molecule]["standardized_structure_hash"],
                molecule,
            ),
        )
        if [left, right] != ordered:
            raise OracleGeometryValidationError("transformation pair order differs")
        if (
            row["left_standardized_structure_hash"]
            != molecules[left]["standardized_structure_hash"]
            or row["right_standardized_structure_hash"]
            != molecules[right]["standardized_structure_hash"]
        ):
            raise OracleGeometryValidationError("pair structure receipt differs")
        expected_pair_id = sha256_json_array(
            [
                EXTRACTION_SPEC_RECEIPT,
                row["left_standardized_structure_hash"],
                row["right_standardized_structure_hash"],
            ]
        )
        if pair_id != expected_pair_id:
            raise OracleGeometryValidationError("transformation pair ID differs")
        component = molecules[left]["similarity_component_hash"]
        if (
            component != molecules[right]["similarity_component_hash"]
            or row["similarity_component_hash"] != component
        ):
            raise OracleGeometryValidationError("pair component differs")
        similarity = _finite(row["similarity"], "pair similarity")
        if not 0.0 <= similarity <= 1.0:
            raise OracleGeometryValidationError("pair similarity differs")
        if row["local_pair"] not in {"true", "false"} or row["episode_pair"] not in {
            "true",
            "false",
        }:
            raise OracleGeometryValidationError("pair membership differs")
        if row["local_pair"] == row["episode_pair"] == "false":
            raise OracleGeometryValidationError("pair is outside the R4 union")
        status = row["extraction_status"]
        if status not in STATUS_VALUES:
            raise OracleGeometryValidationError("pair status differs")
        if status in VALID_STATUSES:
            _validate_valid_pair(row, pair_id, expected_cut[status])
        elif not row["failure_code"]:
            raise OracleGeometryValidationError("invalid pair lacks failure code")
        pairs[pair_id] = row
    _validate_episode_rows(rows["episode_transformations.csv"], public, pairs)
    return pairs


def _validate_valid_pair(
    row: Mapping[str, str], pair_id: str, expected_cut: int
) -> None:
    if (
        row["failure_code"]
        or _canonical_int(row["cut_count"], "cut count") != expected_cut
    ):
        raise OracleGeometryValidationError("valid pair status metadata differs")
    changed = _fraction(row["changed_heavy_atom_fraction"], "changed fraction")
    if not 0 <= changed <= 1:
        raise OracleGeometryValidationError("changed fraction differs")
    required = (
        "a_to_b_direction_id",
        "b_to_a_direction_id",
        "a_to_b_exact_transformation_id",
        "b_to_a_exact_transformation_id",
        "a_to_b_transformation_class_id",
        "b_to_a_transformation_class_id",
        "a_to_b_environment_level_1_id",
        "b_to_a_environment_level_1_id",
        "a_to_b_environment_level_2_id",
        "b_to_a_environment_level_2_id",
        "undirected_exchange_id",
    )
    if any(not row[item] for item in required):
        raise OracleGeometryValidationError("valid pair grammar is blank")
    if row["a_to_b_direction_id"] == row["b_to_a_direction_id"]:
        raise OracleGeometryValidationError("pair directions are identical")
    expected_directions = (
        sha256_json_array(
            [
                EXTRACTION_SPEC_RECEIPT,
                pair_id,
                row["left_standardized_structure_hash"],
                row["right_standardized_structure_hash"],
            ]
        ),
        sha256_json_array(
            [
                EXTRACTION_SPEC_RECEIPT,
                pair_id,
                row["right_standardized_structure_hash"],
                row["left_standardized_structure_hash"],
            ]
        ),
    )
    if expected_directions != (
        row["a_to_b_direction_id"],
        row["b_to_a_direction_id"],
    ):
        raise OracleGeometryValidationError("pair direction ID differs")
    for name in required:
        _digest(row[name], f"pair {name}")
    candidate = row["candidate_material"]
    tie_material = row["tie_material"]
    if (
        not candidate
        or _sha(candidate.encode()) != row["candidate_digest"]
        or _canonical_int(row["tie_count"], "tie count") != 1
        or tie_material != f"[{candidate}]"
        or _sha(tie_material.encode()) != row["tie_digest"]
        or row["ambiguous"] != "false"
        or not row["warnings"].startswith("[")
    ):
        raise OracleGeometryValidationError("valid pair tie metadata differs")


def _validate_episode_rows(
    rows: Sequence[Mapping[str, str]],
    public: Mapping[tuple[str, str], Mapping[str, str]],
    pairs: Mapping[str, Mapping[str, str]],
) -> None:
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        public_row = public.get((row["episode_id"], row["query_molecule_id"]))
        key = row["episode_id"], row["query_molecule_id"], row["query_rank"]
        if public_row is None or key in seen:
            raise OracleGeometryValidationError(
                "episode transformation identity differs"
            )
        seen.add(key)
        if any(row[name] != public_row[name] for name in PUBLIC_METADATA):
            raise OracleGeometryValidationError("episode metadata differs")
        pair = pairs.get(row["transformation_pair_id"])
        if pair is None or pair["episode_pair"] != "true":
            raise OracleGeometryValidationError("episode pair linkage differs")
        anchor = row["anchor_molecule_id"]
        query = row["query_molecule_id"]
        if {anchor, query} != {
            pair["left_molecule_id"],
            pair["right_molecule_id"],
        }:
            raise OracleGeometryValidationError("episode pair members differ")
        forward = anchor == pair["left_molecule_id"]
        prefix = "a_to_b" if forward else "b_to_a"
        if row["direction_id"] != pair[f"{prefix}_direction_id"]:
            raise OracleGeometryValidationError("episode direction differs")
        if row["extraction_status"] != pair["extraction_status"]:
            raise OracleGeometryValidationError("episode extraction status differs")
        if row["failure_code"] != pair["failure_code"]:
            raise OracleGeometryValidationError("episode failure code differs")
        valid = row["extraction_status"] in VALID_STATUSES
        if valid:
            exact_fields = {
                "cut_count": pair["cut_count"],
                "exact_transformation_id": pair[f"{prefix}_exact_transformation_id"],
                "transformation_class_id": pair[f"{prefix}_transformation_class_id"],
                "environment_level_1_id": pair[f"{prefix}_environment_level_1_id"],
                "environment_level_2_id": pair[f"{prefix}_environment_level_2_id"],
                "changed_heavy_atom_fraction": pair["changed_heavy_atom_fraction"],
            }
            if any(row[name] != value for name, value in exact_fields.items()):
                raise OracleGeometryValidationError("episode grammar differs")
        elif any(
            row[name]
            for name in (
                "cut_count",
                "exact_transformation_id",
                "transformation_class_id",
                "environment_level_1_id",
                "environment_level_2_id",
                "changed_heavy_atom_fraction",
            )
        ):
            raise OracleGeometryValidationError("invalid episode has grammar")
        for support_name in (
            "cyp3a4_training_family_exact_support_count",
            "cyp3a4_training_family_class_support_count",
        ):
            _canonical_int(row[support_name], support_name)
        for name in (
            "tie_count",
            "tie_material",
            "tie_digest",
            "ambiguous",
            "warnings",
        ):
            if row[name] != pair[name]:
                raise OracleGeometryValidationError("episode tie metadata differs")
    if {(episode, query) for episode, query, _ in seen} != set(public):
        raise OracleGeometryValidationError("episode transformation coverage differs")


def _canonical_int(value: str, label: str) -> int:
    try:
        if not value or str(int(value)) != value or int(value) < 0:
            raise ValueError
        return int(value)
    except ValueError as exc:
        raise OracleGeometryValidationError(
            f"{label} is not canonical integer"
        ) from exc


def _finite(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise OracleGeometryValidationError(f"{label} is not finite") from exc
    if value == "" or not math.isfinite(result):
        raise OracleGeometryValidationError(f"{label} is not finite")
    return result


def _fraction(value: str, label: str) -> Fraction:
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise OracleGeometryValidationError(f"{label} differs") from exc


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise OracleGeometryValidationError(f"{label} is not SHA-256")


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


__all__ = ["OracleGeometryValidationError", "validate_geometry"]
