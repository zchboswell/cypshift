from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
from rdkit import Chem

from cypshift.chemistry import STANDARDIZATION_VERSION, standardize_molecule
from cypshift.openadmet_transformation_mmp import (
    MMP_PATTERN,
    _environment,
    extract_ordinary_transformation_pair,
)
from cypshift.openadmet_transformation_types import (
    EXTRACTION_SPEC_RECEIPT,
    HYDROGEN_SIDE_TOKEN,
    TransformationIntegrityError,
    canonical_json,
)
from cypshift.schema import MoleculeInput


def record(molecule_id: str, smiles: str):
    return standardize_molecule(
        MoleculeInput(molecule_id, smiles, "smiles", "synthetic", "fixture")
    )


def test_single_exchange_and_independently_recomputed_ids() -> None:
    result = extract_ordinary_transformation_pair(
        record("left", "CCO"), record("right", "CCN")
    )
    assert result.extraction_status == "VALID_SINGLE"
    assert result.failure_code == ""
    assert result.cut_count == 1
    assert result.left_removed_fragment == "O[*:1]"
    assert result.right_removed_fragment == "N[*:1]"
    assert result.candidate_material is not None
    material_bytes = canonical_json(result.candidate_material)
    assert result.candidate_digest == hashlib.sha256(material_bytes).hexdigest()
    assert result.tie_count == 1
    assert result.tie_material == (result.candidate_material,)
    assert (
        result.tie_digest
        == hashlib.sha256(canonical_json([result.candidate_material])).hexdigest()
    )
    expected_pair = hashlib.sha256(
        json.dumps(
            [
                EXTRACTION_SPEC_RECEIPT,
                result.left_standardized_structure_hash,
                result.right_standardized_structure_hash,
            ],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert result.transformation_pair_id == expected_pair
    assert (
        result.a_to_b.exact_transformation_id
        == hashlib.sha256(
            json.dumps(
                [EXTRACTION_SPEC_RECEIPT, "O[*:1]", "N[*:1]", [1]],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert (
        result.a_to_b.exact_transformation_id != result.b_to_a.exact_transformation_id
    )
    assert (
        result.a_to_b.removed_labeled_fragment == result.b_to_a.added_labeled_fragment
    )
    assert (
        result.a_to_b.added_labeled_fragment == result.b_to_a.removed_labeled_fragment
    )
    assert (
        result.a_to_b.anchor_attachment_environment_radius_1
        == result.b_to_a.analog_attachment_environment_radius_1
    )
    assert (
        result.a_to_b.changed_anchor_atom_indices
        == result.b_to_a.changed_analog_atom_indices
    )
    assert result.a_to_b.undirected_exchange_id == result.b_to_a.undirected_exchange_id


def test_virtual_h_growth_and_contraction_reverse() -> None:
    result = extract_ordinary_transformation_pair(
        record("benzene", "c1ccccc1"), record("toluene", "Cc1ccccc1")
    )
    assert result.extraction_status == "VALID_SINGLE"
    assert HYDROGEN_SIDE_TOKEN in {
        result.left_removed_fragment,
        result.right_removed_fragment,
    }
    assert result.left_virtual_h_eligible is True
    assert result.right_virtual_h_eligible is False
    assert result.changed_left_atom_indices == ()
    assert (
        result.a_to_b.transformation_class_id != result.b_to_a.transformation_class_id
    )
    assert result.a_to_b.undirected_exchange_id == result.b_to_a.undirected_exchange_id


def test_unique_double_exchange_is_selected() -> None:
    left = "COc1cc(C)cc(COCc2cc(Cl)cc(F)c2)c1"
    right = "COc1cc(C)cc(CSCc2cc(Cl)cc(F)c2)c1"
    result = extract_ordinary_transformation_pair(
        record("left", left), record("right", right)
    )
    assert result.extraction_status == "VALID_DOUBLE"
    assert result.tie_count == 1
    assert result.left_removed_fragment == "O([*:1])[*:2]"
    assert result.right_removed_fragment == "S([*:1])[*:2]"


def test_double_exchange_preserves_stereo_and_is_order_invariant() -> None:
    left = "c1ccccc1/C=C/c2ccccc2"
    right = "c1ccccc1COc2ccccc2"
    forward = extract_ordinary_transformation_pair(
        record("left", left), record("right", right)
    )
    reverse = extract_ordinary_transformation_pair(
        record("right", right), record("left", left)
    )
    reordered = extract_ordinary_transformation_pair(
        record("left", "C(=C\\c1ccccc1)/c1ccccc1"),
        record("right", "c1ccc(COc2ccccc2)cc1"),
    )
    assert forward == reverse == reordered
    assert forward.extraction_status == "VALID_DOUBLE"
    assert forward.cut_count == 2
    assert forward.tie_count == 1
    assert {
        forward.left_removed_fragment,
        forward.right_removed_fragment,
    } == {
        "C(=C\\[*:2])/[*:1]",
        "C(O[*:2])[*:1]",
    }


def test_joint_double_enumeration_reaches_double_candidate() -> None:
    left = "Cc1ccc(CCc2ccc(C)cc2)cc1"
    right = "Cc1ccc(COCc2ccc(C)cc2)cc1"
    result = extract_ordinary_transformation_pair(
        record("left", left), record("right", right)
    )
    # The witness is intentionally symmetric; exact embedding recovery keeps
    # its distinct changed-index maps and therefore fail-closes as S2.
    assert result.extraction_status == "AMBIGUOUS"
    assert result.failure_code == "S2"
    assert result.tie_count >= 2
    assert all(item["cut_count"] == 2 for item in result.tie_material)


def test_symmetry_tie_and_pair_reversal_are_deterministic() -> None:
    left = record("difluoro", "Fc1ccc(F)cc1")
    right = record("fluorochloro", "Clc1ccc(F)cc1")
    first = extract_ordinary_transformation_pair(left, right)
    second = extract_ordinary_transformation_pair(right, left)
    assert first == second
    assert first.extraction_status == "AMBIGUOUS"
    assert first.failure_code == "S2"
    assert first.tie_count >= 2
    assert first.pair_id == second.pair_id
    assert first.a_to_b.direction_id == second.a_to_b.direction_id
    assert first.tie_material


def test_hazard_precedence_and_terminal_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    salt = record("salt", "CCO.CN")
    valid = record("valid", "CCN")
    result = extract_ordinary_transformation_pair(salt, valid)
    assert result.extraction_status == "STANDARDIZATION_HAZARD"
    assert result.failure_code == "C2"
    import cypshift.openadmet_transformation_mmp as mmp

    changed = replace(valid, standardization_changed=True)
    real_standardize = mmp.standardize_molecule

    def replay(input_row):
        if input_row.molecule_id == "valid":
            return changed
        return real_standardize(input_row)

    monkeypatch.setattr(mmp, "standardize_molecule", replay)
    result = mmp.extract_ordinary_transformation_pair(record("left", "CCO"), changed)
    assert result.failure_code == "C6"
    forged = replace(valid, standardized_structure_hash="0" * 64)
    with pytest.raises(TransformationIntegrityError) as error:
        extract_ordinary_transformation_pair(record("left", "CCO"), forged)
    assert error.value.codes == ("P6",)


def test_terminal_c1_c5_and_replayed_hazard_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid = record("valid", "CCN")
    invalid = replace(valid, raw_structure="not a SMILES")
    with pytest.raises(TransformationIntegrityError) as error:
        extract_ordinary_transformation_pair(record("left", "CCO"), invalid)
    assert error.value.codes == ("C1",)
    with pytest.raises(TransformationIntegrityError) as error:
        extract_ordinary_transformation_pair(record("a", "CCO"), record("b", "OCC"))
    assert error.value.codes == ("C5",)
    forged_flag = replace(valid, standardization_changed=True)
    with pytest.raises(TransformationIntegrityError) as error:
        extract_ordinary_transformation_pair(record("left", "CCO"), forged_flag)
    assert error.value.codes == ("P6",)
    forged_fragments = replace(valid, input_fragments=("CCN", "extra"))
    with pytest.raises(TransformationIntegrityError) as error:
        extract_ordinary_transformation_pair(record("left", "CCO"), forged_fragments)
    assert error.value.codes == ("P6",)


def test_raw_atom_order_replay_and_reusable_ids() -> None:
    first = extract_ordinary_transformation_pair(
        record("left", "CCO"), record("right", "CCN")
    )
    reordered = extract_ordinary_transformation_pair(
        record("left", "OCC"), record("right", "NCC")
    )
    assert first == reordered
    second = extract_ordinary_transformation_pair(
        record("left2", "CCCO"), record("right2", "CCCN")
    )
    second_direction = second.b_to_a
    assert (
        first.a_to_b.exact_transformation_id == second_direction.exact_transformation_id
    )
    assert (
        first.a_to_b.transformation_class_id == second_direction.transformation_class_id
    )
    assert (
        first.a_to_b.environment_level_2_id != second_direction.environment_level_2_id
    )
    assert (
        first.a_to_b.removed_labeled_fragment
        == second_direction.removed_labeled_fragment
    )
    assert (
        first.a_to_b.added_labeled_fragment == second_direction.added_labeled_fragment
    )
    assert first.a_to_b.anchor_attachment_environment_radius_1 != (
        first.b_to_a.anchor_attachment_environment_radius_1
    )


def test_embedding_cap_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import cypshift.openadmet_transformation_mmp as mmp

    monkeypatch.setattr(mmp, "MAX_EMBEDDING_MATCHES", 1)
    result = mmp.extract_ordinary_transformation_pair(
        record("left", "CCO"), record("right", "CCN")
    )
    assert result.extraction_status == "AMBIGUOUS"
    assert result.failure_code == "S2"
    assert result.tie_count == 0
    assert result.tie_material == ()
    assert result.tie_digest == hashlib.sha256(b"[]").hexdigest()


def test_mmp_constants_are_exact_and_rooted_zero_bond_is_retained() -> None:
    assert MMP_PATTERN == "[#6+0;!$(*=,#[!#6])]!@!=!#[*]"
    assert STANDARDIZATION_VERSION == "rdkit-cleanup-fragment-parent-v1"
    molecule = Chem.MolFromSmiles("C")
    assert molecule is not None
    assert _environment(molecule, 0, 1) == "[CH4:1]"
    assert _environment(molecule, 0, 2) == "[CH4:1]"
