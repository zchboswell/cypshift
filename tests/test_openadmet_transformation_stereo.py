from __future__ import annotations

import hashlib
import json

from rdkit import Chem

import cypshift.openadmet_transformation_stereo as stereo_module
from cypshift.openadmet_transformation_stereo import (
    EXTRACTION_SPEC_SHA256,
    StereoDecisionStatus,
    extract_stereo_decision,
)
from cypshift.schema import (
    MoleculeRecord,
    MoleculeStatus,
    StereochemistryStatus,
)


def _record(
    molecule_id: str,
    raw_structure: str,
    standardized_structure: str | None = None,
) -> MoleculeRecord:
    standardized = standardized_structure or raw_structure
    return MoleculeRecord(
        molecule_id=molecule_id,
        raw_structure=raw_structure,
        structure_format="smiles",
        standardized_structure=standardized,
        standardized_structure_hash=hashlib.sha256(
            standardized.encode("utf-8")
        ).hexdigest(),
        status=MoleculeStatus.ACCEPTED,
        stereochemistry_status=StereochemistryStatus.SPECIFIED,
        input_fragments=(raw_structure,),
        standardization_changed=standardized != raw_structure,
        duplicate_of=None,
        warnings=(),
        standardization_version="synthetic-test-v1",
        source="synthetic",
        provenance="synthetic",
    )


def _decision(left: str, right: str):  # type: ignore[no-untyped-def]
    return extract_stereo_decision(_record("left", left), _record("right", right))


def _candidate(left: str, right: str):  # type: ignore[no-untyped-def]
    decision = _decision(left, right)
    assert decision.status is StereoDecisionStatus.VALID_STEREO
    assert decision.failure_code is None
    assert decision.warnings == ()
    assert decision.candidate is not None
    return decision.candidate


def test_receipt_bound_ez_candidate_material_and_ids_are_exact() -> None:
    candidate = _candidate("F/C=C/F", "F/C=C\\F")
    assert EXTRACTION_SPEC_SHA256 == (
        "59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950"
    )
    assert candidate.canonical_nonstereo_full_graph == "FC=CF"
    assert [element.as_dict() for element in candidate.stereo_elements] == [
        {
            "kind": "Bond_Double",
            "atom_indices": [1, 2],
            "bond_indices": [1],
            "left_value": "E",
            "right_value": "Z",
        }
    ]
    expected_record = [
        {
            "atom_indices": [1, 2],
            "bond_indices": [1],
            "kind": "Bond_Double",
            "left_value": "E",
            "right_value": "Z",
        }
    ]
    exact_material = [
        EXTRACTION_SPEC_SHA256,
        "FC=CF",
        expected_record,
    ]
    assert (
        candidate.exact_transformation_id
        == hashlib.sha256(
            json.dumps(
                exact_material,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert candidate.exact_transformation_id == (
        "827786e2fc909251ade6b5cf1489f7a2677dcec6058e5df1712563c7b1eba17e"
    )
    assert (
        candidate.transformation_class_id
        == hashlib.sha256(
            json.dumps(
                [EXTRACTION_SPEC_SHA256, "stereochemical_change"],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    material = json.loads(candidate.candidate_material)
    assert material == {
        "added_labeled_fragment": "",
        "attachment_labels_array": [],
        "changed_heavy_atom_fraction": "0/1",
        "changed_left_atom_indices": [1, 2],
        "changed_right_atom_indices": [1, 2],
        "class": "stereochemical_change",
        "conserved_core_smiles": "FC=CF",
        "cut_count": 0,
        "left_attachment_environment_radius_1": [],
        "left_attachment_environment_radius_2": [],
        "left_virtual_h_eligible": False,
        "removed_labeled_fragment": "",
        "right_attachment_environment_radius_1": [],
        "right_attachment_environment_radius_2": [],
        "right_virtual_h_eligible": False,
        "stereo": {"changed": True, "elements": expected_record},
    }
    assert candidate.conserved_heavy_atoms == 4
    assert candidate.changed_left_atom_indices == (1, 2)
    assert candidate.changed_right_atom_indices == (1, 2)


def test_nonidentical_graph_is_not_applicable() -> None:
    decision = _decision("CCO", "CCN")
    assert decision.status is StereoDecisionStatus.NOT_APPLICABLE
    assert decision.candidate is None
    assert decision.failure_code is None
    assert decision.warnings == ()


def test_unspecified_supported_stereo_is_c3() -> None:
    decision = _decision("FC=CC[C@H](O)Cl", "FC=CC[C@@H](O)Cl")
    assert decision.status is StereoDecisionStatus.AMBIGUOUS
    assert decision.candidate is None
    assert decision.failure_code == "C3"
    assert decision.warnings == ("stereo_not_confident",)


def test_enhanced_stereo_is_rejected_from_exact_raw_input() -> None:
    left_raw = "C[C@@H](F)[C@H](Cl)C |&1:1,3|"
    right_raw = "C[C@H](F)[C@@H](Cl)C |&1:1,3|"
    left_standard = "C[C@@H](F)[C@H](Cl)C"
    right_standard = "C[C@H](F)[C@@H](Cl)C"
    decision = extract_stereo_decision(
        _record("left", left_raw, left_standard),
        _record("right", right_raw, right_standard),
    )
    assert decision.status is StereoDecisionStatus.AMBIGUOUS
    assert decision.failure_code == "C3"
    assert decision.candidate is None


def test_unsupported_stereo_on_nonidentical_graph_delegates_to_ordinary_mmp() -> None:
    decision = _decision(
        "[C@SP1](F)(Cl)(Br)CCO",
        "[C@SP1](F)(Cl)(Br)CCN",
    )
    assert decision.status is StereoDecisionStatus.NOT_APPLICABLE
    assert decision.failure_code is None
    assert decision.candidate is None


def test_unsupported_raw_non_tetrahedral_tag_is_c3() -> None:
    raw = "[Pt@SP1](Cl)(Br)(I)F"
    standardized = "F[Pt](Cl)(Br)I"
    decision = extract_stereo_decision(
        _record("left", raw, standardized),
        _record("right", raw, standardized),
    )
    assert decision.status is StereoDecisionStatus.AMBIGUOUS
    assert decision.failure_code == "C3"
    assert decision.candidate is None


def test_isotope_is_retained_and_domains_the_exact_id() -> None:
    ordinary = _candidate("C[C@H](O)Cl", "C[C@@H](O)Cl")
    isotopic = _candidate("[13CH3][C@H](O)Cl", "[13CH3][C@@H](O)Cl")
    assert "13C" in isotopic.canonical_nonstereo_full_graph
    assert ordinary.canonical_nonstereo_full_graph != (
        isotopic.canonical_nonstereo_full_graph
    )
    assert ordinary.exact_transformation_id != isotopic.exact_transformation_id


def test_atom_maps_are_retained_and_exactly_mapped() -> None:
    candidate = _candidate(
        "[CH3:1][C@H:2](O)Cl",
        "[CH3:1][C@@H:2](O)Cl",
    )
    assert ":1" in candidate.canonical_nonstereo_full_graph
    assert ":2" in candidate.canonical_nonstereo_full_graph
    assert candidate.stereo_elements[0].kind == "Atom_Tetrahedral"
    assert candidate.stereo_elements[0].left_value == "R"
    assert candidate.stereo_elements[0].right_value == "S"


def test_exact_map_rejects_implicit_h_and_dative_false_automorphism() -> None:
    molecule = Chem.MolFromSmiles("C[C@H](F)N->N[C@@H](F)C")
    assert molecule is not None
    Chem.RemoveStereochemistry(molecule)
    mappings = molecule.GetSubstructMatches(
        molecule,
        uniquify=False,
        useChirality=False,
        maxMatches=0,
    )
    assert len(mappings) == 2
    identity, false_automorphism = mappings
    assert stereo_module._is_exact_graph_map(molecule, molecule, identity)
    assert not stereo_module._is_exact_graph_map(molecule, molecule, false_automorphism)
    assert molecule.GetAtomWithIdx(3).GetNumImplicitHs() == 2
    assert molecule.GetAtomWithIdx(false_automorphism[3]).GetNumImplicitHs() == 1
    dative = molecule.GetBondWithIdx(3)
    assert dative.GetBondType() == Chem.BondType.DATIVE


def test_atom_order_and_direction_reversal_are_invariant() -> None:
    left = Chem.MolFromSmiles("F/C=C/F")
    right = Chem.MolFromSmiles("F/C=C\\F")
    assert left is not None and right is not None
    order = list(reversed(range(left.GetNumAtoms())))
    left_reordered = Chem.MolToSmiles(
        Chem.RenumberAtoms(left, order), canonical=False, isomericSmiles=True
    )
    right_reordered = Chem.MolToSmiles(
        Chem.RenumberAtoms(right, order), canonical=False, isomericSmiles=True
    )
    forward = _candidate("F/C=C/F", "F/C=C\\F")
    reordered = _candidate(left_reordered, right_reordered)
    reverse = _candidate("F/C=C\\F", "F/C=C/F")
    assert reordered == forward
    assert reverse == forward.reversed()
    assert reverse.transformation_class_id == forward.transformation_class_id
    assert reverse.exact_transformation_id != forward.exact_transformation_id


def test_unrelated_graphs_with_same_reference_indices_do_not_collide() -> None:
    fluorine = _candidate("F/C=C/F", "F/C=C\\F")
    chlorine = _candidate("Cl/C=C/Cl", "Cl/C=C\\Cl")
    assert fluorine.stereo_elements[0].atom_indices == (
        chlorine.stereo_elements[0].atom_indices
    )
    assert fluorine.stereo_elements[0].bond_indices == (
        chlorine.stereo_elements[0].bond_indices
    )
    assert fluorine.exact_transformation_id != chlorine.exact_transformation_id


def test_v4_lambda_partition_accepts_ordinary_tetrahedral_inversion() -> None:
    left_stereo = Chem.MolFromSmiles("C[C@H](O)Cl")
    right_stereo = Chem.MolFromSmiles("C[C@@H](O)Cl")
    assert left_stereo is not None and right_stereo is not None
    left_centers = frozenset(
        int(info.centeredOn)
        for info in Chem.FindPotentialStereo(
            left_stereo, cleanIt=True, flagPossible=True
        )
        if info.type == Chem.StereoType.Atom_Tetrahedral
        and info.specified == Chem.StereoSpecified.Specified
    )
    left = Chem.Mol(left_stereo)
    Chem.RemoveStereochemistry(left)
    reference_smiles = Chem.MolToSmiles(
        left,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )
    reference = Chem.MolFromSmiles(reference_smiles)
    assert reference is not None
    mappings = left.GetSubstructMatches(
        reference,
        uniquify=False,
        useChirality=False,
        maxMatches=0,
    )
    assert mappings == ((0, 1, 2, 3),)
    center_from_stereo = left.GetAtomWithIdx(1)
    center_from_reference = reference.GetAtomWithIdx(1)
    assert (
        center_from_stereo.GetNumExplicitHs(),
        center_from_stereo.GetNumImplicitHs(),
        center_from_stereo.GetNoImplicit(),
    ) == (1, 0, True)
    assert (
        center_from_reference.GetNumExplicitHs(),
        center_from_reference.GetNumImplicitHs(),
        center_from_reference.GetNoImplicit(),
    ) == (0, 1, False)
    assert not stereo_module._is_exact_graph_map(reference, left, mappings[0])
    assert stereo_module._is_reference_graph_map(
        reference,
        left,
        mappings[0],
        target_tetrahedral_centers=left_centers,
    )

    candidate = _candidate("C[C@H](O)Cl", "C[C@@H](O)Cl")
    assert candidate.canonical_nonstereo_full_graph == "CC(O)Cl"
    assert [element.as_dict() for element in candidate.stereo_elements] == [
        {
            "kind": "Atom_Tetrahedral",
            "atom_indices": [1],
            "bond_indices": [],
            "left_value": "R",
            "right_value": "S",
        }
    ]
    assert candidate.exact_transformation_id == (
        "e706c9a5f62b23e724582dc9dc4e288ae2205910e8b95946bcec458db47d127d"
    )


def test_v4_tetra_only_lambda_and_rho_partition_is_narrow() -> None:
    left_stereo = Chem.MolFromSmiles("C[C@H](O)Cl")
    right_stereo = Chem.MolFromSmiles("C[C@@H](O)Cl")
    assert left_stereo is not None and right_stereo is not None
    left_centers = frozenset(
        int(info.centeredOn)
        for info in Chem.FindPotentialStereo(
            left_stereo, cleanIt=True, flagPossible=True
        )
        if info.type == Chem.StereoType.Atom_Tetrahedral
        and info.specified == Chem.StereoSpecified.Specified
    )
    right_centers = frozenset(
        int(info.centeredOn)
        for info in Chem.FindPotentialStereo(
            right_stereo, cleanIt=True, flagPossible=True
        )
        if info.type == Chem.StereoType.Atom_Tetrahedral
        and info.specified == Chem.StereoSpecified.Specified
    )
    left_no_stereo = Chem.Mol(left_stereo)
    right_no_stereo = Chem.Mol(right_stereo)
    Chem.RemoveStereochemistry(left_no_stereo)
    Chem.RemoveStereochemistry(right_no_stereo)
    reference_smiles = Chem.MolToSmiles(
        left_no_stereo,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )
    reference = Chem.MolFromSmiles(reference_smiles)
    assert reference is not None
    lambda_map = left_no_stereo.GetSubstructMatches(
        reference, uniquify=False, useChirality=False, maxMatches=0
    )[0]
    rho = right_no_stereo.GetSubstructMatches(
        reference, uniquify=False, useChirality=False, maxMatches=0
    )[0]
    phi = right_no_stereo.GetSubstructMatches(
        left_no_stereo, uniquify=False, useChirality=False, maxMatches=0
    )[0]
    assert stereo_module._is_exact_graph_map(left_no_stereo, right_no_stereo, phi)
    assert not stereo_module._is_exact_graph_map(reference, left_no_stereo, lambda_map)
    assert not stereo_module._is_exact_graph_map(reference, right_no_stereo, rho)
    assert stereo_module._is_reference_graph_map(
        reference,
        left_no_stereo,
        lambda_map,
        target_tetrahedral_centers=left_centers,
    )
    assert not stereo_module._is_reference_graph_map(
        reference,
        left_no_stereo,
        lambda_map,
        target_tetrahedral_centers=frozenset(),
    )
    inverse_lambda = tuple(lambda_map.index(index) for index in range(len(lambda_map)))
    assert not stereo_module._is_reference_graph_map(
        left_no_stereo,
        reference,
        inverse_lambda,
        target_tetrahedral_centers=left_centers,
    )
    assert stereo_module._is_reference_graph_map(
        reference,
        right_no_stereo,
        rho,
        target_tetrahedral_centers=right_centers,
    )

    mapped_left = Chem.MolFromSmiles("[CH3:1][CH3:2]")
    mapped_right = Chem.MolFromSmiles("[CH3:2][CH3:1]")
    assert mapped_left is not None and mapped_right is not None
    assert not stereo_module._is_reference_graph_map(
        mapped_left,
        mapped_right,
        (0, 1),
        target_tetrahedral_centers=frozenset(),
    )

    dative = Chem.MolFromSmiles("C[C@H](F)N->N[C@@H](F)C")
    assert dative is not None
    dative_centers = frozenset(
        int(info.centeredOn)
        for info in Chem.FindPotentialStereo(dative, cleanIt=True, flagPossible=True)
        if info.type == Chem.StereoType.Atom_Tetrahedral
        and info.specified == Chem.StereoSpecified.Specified
    )
    Chem.RemoveStereochemistry(dative)
    false_automorphism = dative.GetSubstructMatches(
        dative, uniquify=False, useChirality=False, maxMatches=0
    )[1]
    assert not stereo_module._is_reference_graph_map(
        dative,
        dative,
        false_automorphism,
        target_tetrahedral_centers=dative_centers,
    )
