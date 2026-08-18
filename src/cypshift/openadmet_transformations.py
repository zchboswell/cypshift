"""Unified pure R4 pair extraction.

The ordinary MMP implementation owns record integrity, canonical pair order,
hazard precedence, and all non-stereo candidate mechanics.  This thin module
adds the cut-zero stereo decision at the correct precedence boundary and
returns the same immutable v4 pair schema for either branch.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from cypshift.openadmet_transformation_mmp import extract_ordinary_transformation_pair
from cypshift.openadmet_transformation_stereo import (
    StereoCandidate,
    StereoDecisionStatus,
    extract_stereo_decision,
)
from cypshift.openadmet_transformation_types import (
    EXTRACTION_SPEC_RECEIPT,
    NO_TIE_DIGEST,
    DirectionalTransformation,
    TransformationIntegrityError,
    TransformationPairResult,
    canonical_json,
    sha256_json_array,
)
from cypshift.schema import MoleculeRecord


def _warning(failure_code: str) -> tuple[str, ...]:
    return {
        "C3": ("stereo_not_confident",),
        "S3": ("inconsistent_direction",),
    }.get(failure_code, ())


def _invalid_direction(
    direction: DirectionalTransformation,
    status: str,
    failure_code: str,
) -> DirectionalTransformation:
    return replace(
        direction,
        extraction_status=status,
        failure_code=failure_code,
        cut_count=None,
        conserved_core_smiles="",
        removed_labeled_fragment="",
        added_labeled_fragment="",
        attachment_labels=(),
        anchor_attachment_environment_radius_1=(),
        analog_attachment_environment_radius_1=(),
        anchor_attachment_environment_radius_2=(),
        analog_attachment_environment_radius_2=(),
        anchor_virtual_h_eligible=False,
        analog_virtual_h_eligible=False,
        changed_anchor_atom_indices=(),
        changed_analog_atom_indices=(),
        conserved_heavy_atoms=None,
        anchor_heavy_atoms=None,
        analog_heavy_atoms=None,
        changed_heavy_atom_fraction="",
        stereo_changed=False,
        stereo_elements=(),
        exact_transformation_id="",
        transformation_class_id="",
        environment_level_1_id="",
        environment_level_2_id="",
        undirected_exchange_id="",
        candidate_material=None,
        candidate_digest="",
        ambiguous=status == "AMBIGUOUS",
        warnings=_warning(failure_code),
    )


def _invalid_result(
    base: TransformationPairResult,
    failure_code: str,
) -> TransformationPairResult:
    status = "AMBIGUOUS"
    return replace(
        base,
        extraction_status=status,
        failure_code=failure_code,
        a_to_b=_invalid_direction(base.a_to_b, status, failure_code),
        b_to_a=_invalid_direction(base.b_to_a, status, failure_code),
        cut_count=None,
        conserved_core_smiles="",
        left_removed_fragment="",
        right_removed_fragment="",
        left_attachment_environment_radius_1=(),
        right_attachment_environment_radius_1=(),
        left_attachment_environment_radius_2=(),
        right_attachment_environment_radius_2=(),
        left_virtual_h_eligible=None,
        right_virtual_h_eligible=None,
        changed_left_atom_indices=(),
        changed_right_atom_indices=(),
        conserved_heavy_atoms=None,
        left_heavy_atoms=None,
        right_heavy_atoms=None,
        changed_heavy_atom_fraction="",
        stereo_changed=None,
        stereo_elements=(),
        candidate_material=None,
        candidate_digest="",
        tie_count=0,
        tie_material=(),
        tie_digest=NO_TIE_DIGEST,
        ambiguous=True,
        warnings=_warning(failure_code),
    )


def _stereo_material(candidate: StereoCandidate) -> dict[str, Any]:
    value = json.loads(candidate.candidate_material)
    if not isinstance(value, dict):
        raise ValueError("stereo candidate material must be a JSON object")
    return value


def _undirected_stereo_id() -> str:
    return sha256_json_array([EXTRACTION_SPEC_RECEIPT, ["", ""], 0])


def _stereo_direction(
    pair_id: str,
    anchor: MoleculeRecord,
    analog: MoleculeRecord,
    candidate: StereoCandidate,
) -> DirectionalTransformation:
    if (
        anchor.standardized_structure_hash is None
        or analog.standardized_structure_hash is None
    ):
        raise ValueError("stereo direction requires standardized hashes")
    material = _stereo_material(candidate)
    direction_id = sha256_json_array(
        [
            EXTRACTION_SPEC_RECEIPT,
            pair_id,
            anchor.standardized_structure_hash,
            analog.standardized_structure_hash,
        ]
    )
    candidate_bytes = candidate.candidate_material.encode("utf-8")
    return DirectionalTransformation(
        direction_id=direction_id,
        anchor_molecule_id=anchor.molecule_id,
        analog_molecule_id=analog.molecule_id,
        anchor_standardized_structure_hash=anchor.standardized_structure_hash,
        analog_standardized_structure_hash=analog.standardized_structure_hash,
        extraction_status="VALID_STEREO",
        failure_code="",
        cut_count=0,
        conserved_core_smiles=candidate.canonical_nonstereo_full_graph,
        removed_labeled_fragment="",
        added_labeled_fragment="",
        attachment_labels=(),
        anchor_attachment_environment_radius_1=(),
        analog_attachment_environment_radius_1=(),
        anchor_attachment_environment_radius_2=(),
        analog_attachment_environment_radius_2=(),
        anchor_virtual_h_eligible=False,
        analog_virtual_h_eligible=False,
        changed_anchor_atom_indices=candidate.changed_left_atom_indices,
        changed_analog_atom_indices=candidate.changed_right_atom_indices,
        conserved_heavy_atoms=candidate.conserved_heavy_atoms,
        anchor_heavy_atoms=candidate.conserved_heavy_atoms,
        analog_heavy_atoms=candidate.conserved_heavy_atoms,
        changed_heavy_atom_fraction="0/1",
        stereo_changed=True,
        stereo_elements=candidate.stereo_elements,
        exact_transformation_id=candidate.exact_transformation_id,
        transformation_class_id=candidate.transformation_class_id,
        environment_level_1_id="",
        environment_level_2_id="",
        undirected_exchange_id=_undirected_stereo_id(),
        candidate_material=material,
        candidate_digest=hashlib.sha256(candidate_bytes).hexdigest(),
        ambiguous=False,
        warnings=(),
    )


def _stereo_reversal_is_consistent(
    forward: StereoCandidate, reverse: StereoCandidate
) -> bool:
    if forward.exact_transformation_id == reverse.exact_transformation_id:
        return False
    if forward.transformation_class_id != reverse.transformation_class_id:
        return False
    if forward.canonical_nonstereo_full_graph != reverse.canonical_nonstereo_full_graph:
        return False
    if forward.changed_left_atom_indices != reverse.changed_right_atom_indices:
        return False
    if forward.changed_right_atom_indices != reverse.changed_left_atom_indices:
        return False
    expected = tuple(
        sorted(
            (
                replace(
                    element,
                    left_value=element.right_value,
                    right_value=element.left_value,
                )
                for element in forward.stereo_elements
            ),
            key=lambda element: (
                element.atom_indices,
                element.bond_indices,
                element.kind,
                element.left_value,
                element.right_value,
            ),
        )
    )
    return reverse.stereo_elements == expected


def _stereo_result(
    base: TransformationPairResult,
    left: MoleculeRecord,
    right: MoleculeRecord,
    candidate: StereoCandidate,
) -> TransformationPairResult:
    reverse = candidate.reversed()
    if not _stereo_reversal_is_consistent(candidate, reverse):
        return _invalid_result(base, "S3")
    material = _stereo_material(candidate)
    candidate_bytes = canonical_json(material)
    a_to_b = _stereo_direction(base.transformation_pair_id, left, right, candidate)
    b_to_a = _stereo_direction(base.transformation_pair_id, right, left, reverse)
    if (
        a_to_b.removed_labeled_fragment != b_to_a.added_labeled_fragment
        or a_to_b.added_labeled_fragment != b_to_a.removed_labeled_fragment
        or a_to_b.undirected_exchange_id != b_to_a.undirected_exchange_id
    ):
        return _invalid_result(base, "S3")
    return replace(
        base,
        extraction_status="VALID_STEREO",
        failure_code="",
        a_to_b=a_to_b,
        b_to_a=b_to_a,
        cut_count=0,
        conserved_core_smiles=candidate.canonical_nonstereo_full_graph,
        left_removed_fragment="",
        right_removed_fragment="",
        left_attachment_environment_radius_1=(),
        right_attachment_environment_radius_1=(),
        left_attachment_environment_radius_2=(),
        right_attachment_environment_radius_2=(),
        left_virtual_h_eligible=False,
        right_virtual_h_eligible=False,
        changed_left_atom_indices=candidate.changed_left_atom_indices,
        changed_right_atom_indices=candidate.changed_right_atom_indices,
        conserved_heavy_atoms=candidate.conserved_heavy_atoms,
        left_heavy_atoms=candidate.conserved_heavy_atoms,
        right_heavy_atoms=candidate.conserved_heavy_atoms,
        changed_heavy_atom_fraction="0/1",
        stereo_changed=True,
        stereo_elements=candidate.stereo_elements,
        candidate_material=material,
        candidate_digest=hashlib.sha256(candidate_bytes).hexdigest(),
        tie_count=1,
        tie_material=(material,),
        tie_digest=hashlib.sha256(canonical_json([material])).hexdigest(),
        ambiguous=False,
        warnings=(),
    )


def extract_transformation_pair(
    left: MoleculeRecord, right: MoleculeRecord
) -> TransformationPairResult:
    """Return one canonical unordered pair with both directional records."""

    base = extract_ordinary_transformation_pair(left, right)
    if (
        base.left_molecule_id == base.right_molecule_id
        and base.left_standardized_structure_hash
        != base.right_standardized_structure_hash
    ):
        raise TransformationIntegrityError(("P6",))
    if base.extraction_status == "STANDARDIZATION_HAZARD":
        return base
    records = {left.molecule_id: left, right.molecule_id: right}
    if len(records) != 2:
        raise TransformationIntegrityError(("P6",))
    canonical_left = records[base.left_molecule_id]
    canonical_right = records[base.right_molecule_id]
    decision = extract_stereo_decision(canonical_left, canonical_right)
    if decision.status is StereoDecisionStatus.NOT_APPLICABLE:
        return base
    if decision.status is StereoDecisionStatus.AMBIGUOUS:
        return _invalid_result(base, decision.failure_code or "C3")
    if decision.candidate is None:
        return _invalid_result(base, "S3")
    return _stereo_result(base, canonical_left, canonical_right, decision.candidate)


__all__ = ["TransformationIntegrityError", "extract_transformation_pair"]
