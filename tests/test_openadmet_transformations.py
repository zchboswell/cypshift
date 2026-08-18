from __future__ import annotations

import hashlib
import json

from rdkit import Chem

from cypshift.chemistry import standardize_molecule
from cypshift.openadmet_transformation_types import (
    EXTRACTION_SPEC_RECEIPT,
    canonical_json,
)
from cypshift.openadmet_transformations import extract_transformation_pair
from cypshift.schema import MoleculeInput, MoleculeRecord


def record(molecule_id: str, smiles: str) -> MoleculeRecord:
    return standardize_molecule(
        MoleculeInput(molecule_id, smiles, "smiles", "synthetic", "fixture")
    )


def test_ordinary_pairs_delegate_without_stereo_override() -> None:
    result = extract_transformation_pair(record("left", "CCO"), record("right", "CCN"))
    assert result.extraction_status == "VALID_SINGLE"
    assert result.failure_code == ""
    assert result.a_to_b.extraction_status == "VALID_SINGLE"
    assert result.b_to_a.extraction_status == "VALID_SINGLE"


def test_unsupported_stereo_on_nonidentical_graph_uses_ordinary_mmp() -> None:
    result = extract_transformation_pair(
        record("left", "[C@SP1](F)(Cl)(Br)CCO"),
        record("right", "[C@SP1](F)(Cl)(Br)CCN"),
    )
    assert result.extraction_status == "VALID_SINGLE"
    assert result.failure_code == ""
    assert result.stereo_changed is False
    assert result.a_to_b.extraction_status == "VALID_SINGLE"
    assert result.b_to_a.extraction_status == "VALID_SINGLE"


def test_hazard_precedes_unsupported_stereo_and_standardization() -> None:
    left = record("left", "C[C@H](F)O.CN")
    right = record("right", "C[C@@H](F)O.CN")
    result = extract_transformation_pair(left, right)
    assert result.extraction_status == "STANDARDIZATION_HAZARD"
    assert result.failure_code == "C2"


def test_tetrahedral_and_double_bond_stereo_have_valid_pair_records() -> None:
    for left_smiles, right_smiles, kind in (
        ("C[C@H](O)Cl", "C[C@@H](O)Cl", "Atom_Tetrahedral"),
        ("F/C=C/F", "F/C=C\\F", "Bond_Double"),
    ):
        result = extract_transformation_pair(
            record("left", left_smiles), record("right", right_smiles)
        )
        assert result.extraction_status == "VALID_STEREO"
        assert result.failure_code == ""
        assert result.cut_count == 0
        assert result.stereo_changed is True
        assert len(result.stereo_elements) == 1
        assert result.stereo_elements[0].kind == kind
        assert result.tie_count == 1
        assert result.tie_material == (result.candidate_material,)
        assert result.left_attachment_environment_radius_1 == ()
        assert result.a_to_b.environment_level_1_id == ""
        assert (
            result.a_to_b.undirected_exchange_id == result.b_to_a.undirected_exchange_id
        )


def test_c3_stereo_has_exact_invalid_sentinels_and_no_ordinary_fallback() -> None:
    result = extract_transformation_pair(
        record("left", "FC=CC[C@H](O)Cl"),
        record("right", "FC=CC[C@@H](O)Cl"),
    )
    assert result.extraction_status == "AMBIGUOUS"
    assert result.failure_code == "C3"
    assert result.ambiguous is True
    assert result.cut_count is None
    assert result.candidate_material is None
    assert result.candidate_digest == ""
    assert result.tie_count == 0
    assert result.tie_material == ()
    assert result.tie_digest == hashlib.sha256(b"[]").hexdigest()
    assert result.warnings == ("stereo_not_confident",)
    assert result.a_to_b.direction_id
    assert result.a_to_b.exact_transformation_id == ""
    assert result.a_to_b.candidate_material is None
    assert result.a_to_b.warnings == ("stereo_not_confident",)


def test_pair_order_and_direction_are_invariant_to_input_reversal() -> None:
    left = record("left", "C[C@H](O)Cl")
    right = record("right", "C[C@@H](O)Cl")
    forward = extract_transformation_pair(left, right)
    reversed_inputs = extract_transformation_pair(right, left)
    assert forward == reversed_inputs
    assert forward.left_molecule_id == reversed_inputs.left_molecule_id
    assert forward.transformation_pair_id == reversed_inputs.transformation_pair_id


def test_v4_stereo_ids_material_and_tie_are_independently_recomputed() -> None:
    result = extract_transformation_pair(
        record("left", "F/C=C/F"), record("right", "F/C=C\\F")
    )
    assert result.extraction_status == "VALID_STEREO"
    element = result.stereo_elements[0].as_dict()
    expected_exact = hashlib.sha256(
        json.dumps(
            [EXTRACTION_SPEC_RECEIPT, "FC=CF", [element]],
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert result.a_to_b.exact_transformation_id == expected_exact
    assert (
        result.a_to_b.transformation_class_id
        == hashlib.sha256(
            json.dumps(
                [EXTRACTION_SPEC_RECEIPT, "stereochemical_change"],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert result.candidate_material is not None
    assert (
        result.candidate_digest
        == hashlib.sha256(canonical_json(result.candidate_material)).hexdigest()
    )
    assert (
        result.tie_digest
        == hashlib.sha256(canonical_json([result.candidate_material])).hexdigest()
    )
    assert (
        result.a_to_b.exact_transformation_id != result.b_to_a.exact_transformation_id
    )
    assert result.a_to_b.environment_level_1_id == ""
    assert result.a_to_b.environment_level_2_id == ""


def test_stereo_atom_order_invariance_and_isotope_noncollision() -> None:
    left = Chem.MolFromSmiles("C[C@H](O)Cl")
    right = Chem.MolFromSmiles("C[C@@H](O)Cl")
    assert left is not None and right is not None
    order = list(reversed(range(left.GetNumAtoms())))
    left_reordered = Chem.MolToSmiles(
        Chem.RenumberAtoms(left, order), canonical=False, isomericSmiles=True
    )
    right_reordered = Chem.MolToSmiles(
        Chem.RenumberAtoms(right, order), canonical=False, isomericSmiles=True
    )
    original = extract_transformation_pair(
        record("left", "C[C@H](O)Cl"), record("right", "C[C@@H](O)Cl")
    )
    reordered = extract_transformation_pair(
        record("left", left_reordered), record("right", right_reordered)
    )
    assert original == reordered
    isotopic = extract_transformation_pair(
        record("left", "[13CH3][C@H](O)Cl"),
        record("right", "[13CH3][C@@H](O)Cl"),
    )
    assert isotopic.extraction_status == "VALID_STEREO"
    assert isotopic.conserved_core_smiles != original.conserved_core_smiles
    assert (
        isotopic.a_to_b.exact_transformation_id
        != original.a_to_b.exact_transformation_id
    )
