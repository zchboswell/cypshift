"""Immutable result types and receipt-bound identifiers for R4 MMP extraction.

The chemistry implementation deliberately lives in :mod:`openadmet_transformation_mmp`.
Keeping the small result vocabulary here makes the pure extractor useful to the
later stereo and coverage slices without coupling it to CSV or episode I/O.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final

EXTRACTION_SPEC_RECEIPT: Final[str] = (
    "59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950"
)
HYDROGEN_SIDE_TOKEN: Final[str] = "[H][*:1]"
NO_TIE_DIGEST: Final[str] = hashlib.sha256(b"[]").hexdigest()


def canonical_json(value: Any) -> bytes:
    """Return the contract's compact, sorted UTF-8 JSON representation."""

    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json_array(value: list[Any]) -> str:
    """Hash one contract ID material array."""

    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class TransformationIntegrityError(ValueError):
    """Raised when a terminal integrity condition makes extraction unsafe."""

    def __init__(self, codes: str | tuple[str, ...] | list[str]) -> None:
        values = (codes,) if isinstance(codes, str) else tuple(codes)
        if not values:
            raise ValueError("at least one integrity code is required")
        self.codes = values
        super().__init__(", ".join(values))


@dataclass(frozen=True, slots=True)
class StereoElement:
    """A canonical changed stereo element (reserved for the stereo slice)."""

    kind: str
    atom_indices: tuple[int, ...]
    bond_indices: tuple[int, ...]
    left_value: str
    right_value: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "atom_indices": list(self.atom_indices),
            "bond_indices": list(self.bond_indices),
            "left_value": self.left_value,
            "right_value": self.right_value,
        }


@dataclass(frozen=True, slots=True)
class DirectionalTransformation:
    """One anchor-to-analog view of a selected structural candidate."""

    direction_id: str
    anchor_molecule_id: str
    analog_molecule_id: str
    anchor_standardized_structure_hash: str
    analog_standardized_structure_hash: str
    extraction_status: str
    failure_code: str
    cut_count: int | None
    conserved_core_smiles: str
    removed_labeled_fragment: str
    added_labeled_fragment: str
    attachment_labels: tuple[int, ...]
    anchor_attachment_environment_radius_1: tuple[str, ...]
    analog_attachment_environment_radius_1: tuple[str, ...]
    anchor_attachment_environment_radius_2: tuple[str, ...]
    analog_attachment_environment_radius_2: tuple[str, ...]
    anchor_virtual_h_eligible: bool
    analog_virtual_h_eligible: bool
    changed_anchor_atom_indices: tuple[int, ...]
    changed_analog_atom_indices: tuple[int, ...]
    conserved_heavy_atoms: int | None
    anchor_heavy_atoms: int | None
    analog_heavy_atoms: int | None
    changed_heavy_atom_fraction: str
    stereo_changed: bool
    stereo_elements: tuple[StereoElement, ...]
    exact_transformation_id: str
    transformation_class_id: str
    environment_level_1_id: str
    environment_level_2_id: str
    undirected_exchange_id: str
    candidate_material: dict[str, Any] | None
    candidate_digest: str
    ambiguous: bool
    warnings: tuple[str, ...]

    @property
    def anchor_env_radius_1(self) -> tuple[str, ...]:
        return self.anchor_attachment_environment_radius_1

    @property
    def analog_env_radius_1(self) -> tuple[str, ...]:
        return self.analog_attachment_environment_radius_1

    @property
    def anchor_env_radius_2(self) -> tuple[str, ...]:
        return self.anchor_attachment_environment_radius_2

    @property
    def analog_env_radius_2(self) -> tuple[str, ...]:
        return self.analog_attachment_environment_radius_2

    @property
    def attachment_labels_array(self) -> tuple[int, ...]:
        return self.attachment_labels

    @property
    def removed_fragment_smiles(self) -> str:
        return self.removed_labeled_fragment

    @property
    def added_fragment_smiles(self) -> str:
        return self.added_labeled_fragment


@dataclass(frozen=True, slots=True)
class TransformationPairResult:
    """One canonical unordered pair and its two provenance directions."""

    transformation_pair_id: str
    left_molecule_id: str
    right_molecule_id: str
    left_standardized_structure_hash: str
    right_standardized_structure_hash: str
    extraction_status: str
    failure_code: str
    similarity: float
    a_to_b: DirectionalTransformation
    b_to_a: DirectionalTransformation
    cut_count: int | None
    conserved_core_smiles: str
    left_removed_fragment: str
    right_removed_fragment: str
    left_attachment_environment_radius_1: tuple[str, ...]
    right_attachment_environment_radius_1: tuple[str, ...]
    left_attachment_environment_radius_2: tuple[str, ...]
    right_attachment_environment_radius_2: tuple[str, ...]
    left_virtual_h_eligible: bool | None
    right_virtual_h_eligible: bool | None
    changed_left_atom_indices: tuple[int, ...]
    changed_right_atom_indices: tuple[int, ...]
    conserved_heavy_atoms: int | None
    left_heavy_atoms: int | None
    right_heavy_atoms: int | None
    changed_heavy_atom_fraction: str
    stereo_changed: bool | None
    stereo_elements: tuple[StereoElement, ...]
    candidate_material: dict[str, Any] | None
    candidate_digest: str
    tie_count: int
    tie_material: tuple[dict[str, Any], ...]
    tie_digest: str
    ambiguous: bool
    warnings: tuple[str, ...]

    @property
    def left_to_right(self) -> DirectionalTransformation:
        return self.a_to_b

    @property
    def right_to_left(self) -> DirectionalTransformation:
        return self.b_to_a

    @property
    def pair_id(self) -> str:
        return self.transformation_pair_id

    @property
    def left_removed_fragment_smiles(self) -> str:
        return self.left_removed_fragment

    @property
    def right_removed_fragment_smiles(self) -> str:
        return self.right_removed_fragment


__all__ = [
    "DirectionalTransformation",
    "EXTRACTION_SPEC_RECEIPT",
    "HYDROGEN_SIDE_TOKEN",
    "NO_TIE_DIGEST",
    "StereoElement",
    "TransformationIntegrityError",
    "TransformationPairResult",
    "canonical_json",
    "sha256_json_array",
]
