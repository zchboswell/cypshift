from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from rdkit import Chem
from rdkit.Chem import rdCIPLabeler

ROOT = Path(__file__).parents[1]
PATH = ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v3.json"
PARENT_PATH = (
    ROOT / "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v2.json"
)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AssertionError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load(path: Path = PATH) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_unique)
    assert isinstance(value, dict)
    return value


def _reference_smiles(smiles: str) -> str:
    molecule = Chem.MolFromSmiles(smiles)
    assert molecule is not None
    molecule = Chem.Mol(molecule)
    Chem.RemoveStereochemistry(molecule)
    return Chem.MolToSmiles(
        molecule,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )


def _cip_values(smiles: str) -> tuple[list[str], list[str]]:
    molecule = Chem.MolFromSmiles(smiles)
    assert molecule is not None
    for atom in molecule.GetAtoms():
        if atom.HasProp("_CIPCode"):
            atom.ClearProp("_CIPCode")
    for bond in molecule.GetBonds():
        if bond.HasProp("_CIPCode"):
            bond.ClearProp("_CIPCode")
    rdCIPLabeler.AssignCIPLabels(molecule)
    atoms = sorted(
        atom.GetProp("_CIPCode")
        for atom in molecule.GetAtoms()
        if atom.HasProp("_CIPCode")
    )
    bonds = sorted(
        bond.GetProp("_CIPCode")
        for bond in molecule.GetBonds()
        if bond.HasProp("_CIPCode")
    )
    return atoms, bonds


def _discover(smiles: str) -> tuple[Chem.Mol, tuple[Any, ...]]:
    molecule = Chem.MolFromSmiles(smiles)
    assert molecule is not None
    discovered = Chem.FindPotentialStereo(molecule, cleanIt=True, flagPossible=True)
    return molecule, tuple(discovered)


def _raw_stereo_is_unsupported(molecule: Chem.Mol) -> bool:
    allowed_atoms = {
        Chem.ChiralType.CHI_UNSPECIFIED,
        Chem.ChiralType.CHI_TETRAHEDRAL_CW,
        Chem.ChiralType.CHI_TETRAHEDRAL_CCW,
    }
    allowed_bonds = {
        Chem.BondStereo.STEREONONE,
        Chem.BondStereo.STEREOE,
        Chem.BondStereo.STEREOZ,
    }
    return (
        bool(molecule.GetStereoGroups())
        or any(atom.GetChiralTag() not in allowed_atoms for atom in molecule.GetAtoms())
        or any(bond.GetStereo() not in allowed_bonds for bond in molecule.GetBonds())
    )


def _atom_attributes(atom: Chem.Atom) -> tuple[Any, ...]:
    return (
        atom.GetAtomicNum(),
        atom.GetIsotope(),
        atom.GetFormalCharge(),
        atom.GetNumRadicalElectrons(),
        atom.GetIsAromatic(),
        atom.GetNumExplicitHs(),
        atom.GetNumImplicitHs(),
        atom.GetNoImplicit(),
        atom.GetAtomMapNum(),
    )


def _bond_attributes(bond: Chem.Bond) -> tuple[Any, ...]:
    return bond.GetBondType(), bond.GetIsAromatic(), bond.GetIsConjugated()


def _exact_graph_map(
    source: Chem.Mol, target: Chem.Mol, mapping: tuple[int, ...]
) -> bool:
    if (
        source.GetNumAtoms() != target.GetNumAtoms()
        or source.GetNumBonds() != target.GetNumBonds()
        or len(mapping) != source.GetNumAtoms()
        or set(mapping) != set(range(target.GetNumAtoms()))
    ):
        return False
    if any(
        _atom_attributes(source.GetAtomWithIdx(index))
        != _atom_attributes(target.GetAtomWithIdx(mapped))
        for index, mapped in enumerate(mapping)
    ):
        return False
    for bond in source.GetBonds():
        mapped = target.GetBondBetweenAtoms(
            mapping[bond.GetBeginAtomIdx()], mapping[bond.GetEndAtomIdx()]
        )
        if mapped is None or _bond_attributes(mapped) != _bond_attributes(bond):
            return False
        if bond.GetBondType() in {
            Chem.BondType.DATIVE,
            Chem.BondType.DATIVEL,
            Chem.BondType.DATIVER,
            Chem.BondType.DATIVEONE,
        } and (
            mapping[bond.GetBeginAtomIdx()] != mapped.GetBeginAtomIdx()
            or mapping[bond.GetEndAtomIdx()] != mapped.GetEndAtomIdx()
        ):
            return False
    return True


def _changed_record(left_smiles: str, right_smiles: str) -> list[dict[str, Any]]:
    left, left_infos = _discover(left_smiles)
    right, right_infos = _discover(right_smiles)
    for molecule in (left, right):
        for atom in molecule.GetAtoms():
            if atom.HasProp("_CIPCode"):
                atom.ClearProp("_CIPCode")
        for bond in molecule.GetBonds():
            if bond.HasProp("_CIPCode"):
                bond.ClearProp("_CIPCode")
        rdCIPLabeler.AssignCIPLabels(molecule)
    left_by_key = {(str(info.type), info.centeredOn): info for info in left_infos}
    right_by_key = {(str(info.type), info.centeredOn): info for info in right_infos}
    assert left_by_key.keys() == right_by_key.keys()
    records: list[dict[str, Any]] = []
    for kind, centered_on in left_by_key:
        assert str(left_by_key[(kind, centered_on)].specified) == "Specified"
        assert str(right_by_key[(kind, centered_on)].specified) == "Specified"
        if kind == "Atom_Tetrahedral":
            left_value = left.GetAtomWithIdx(centered_on).GetProp("_CIPCode")
            right_value = right.GetAtomWithIdx(centered_on).GetProp("_CIPCode")
            atom_indices = [centered_on]
            bond_indices: list[int] = []
        else:
            assert kind == "Bond_Double"
            left_bond = left.GetBondWithIdx(centered_on)
            right_bond = right.GetBondWithIdx(centered_on)
            left_value = left_bond.GetProp("_CIPCode")
            right_value = right_bond.GetProp("_CIPCode")
            atom_indices = sorted(
                [left_bond.GetBeginAtomIdx(), left_bond.GetEndAtomIdx()]
            )
            bond_indices = [centered_on]
        if left_value != right_value:
            records.append(
                {
                    "kind": kind,
                    "atom_indices": atom_indices,
                    "bond_indices": bond_indices,
                    "left_value": left_value,
                    "right_value": right_value,
                }
            )
    return sorted(
        records,
        key=lambda item: (
            item["atom_indices"],
            item["bond_indices"],
            item["kind"],
            item["left_value"],
            item["right_value"],
        ),
    )


def test_v3_is_strict_self_contained_child_of_immutable_v2() -> None:
    contract = load()
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() == (
        "f5e1862682c1d2a3e34fcf530c9aad42cbd4e4538488eca1a4c5508443f61db5"
    )
    with pytest.raises(AssertionError, match="duplicate JSON key"):
        json.loads('{"duplicate":1,"duplicate":2}', object_pairs_hook=_unique)
    assert contract["schema_version"].endswith("transformation_coverage_contract.v3")
    assert contract["parent"] == {
        "path": "benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v2.json",
        "schema_version": (
            "cypshift.openadmet_cyp_2026.transformation_coverage_contract.v2"
        ),
        "sha256": "a13adee526575b4dc22c414c08cbcb9cf3ff8cc69c8eb10ad9c078e5eb4ae73e",
        "immutable": True,
    }
    assert (
        hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest()
        == (contract["parent"]["sha256"])
    )
    inheritance = contract["inheritance"]
    assert inheritance["mode"] == "full_self_contained_snapshot"
    assert inheritance["recursive_merge"] is False
    assert inheritance["parent_runtime_access_required"] is False
    assert inheritance["no_new_data_or_authority"] is True
    assert "file alone" in inheritance["implementation_source"]


def test_v3_receipt_and_all_output_schema_ids_are_self_versioned() -> None:
    contract = load()
    extraction = contract["extraction"]
    receipt = extraction["extraction_spec_receipt"]
    material = {"extraction_spec_id": extraction["extraction_spec_id"]}
    material.update({name: extraction[name] for name in receipt["receipt_subtrees"]})
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert extraction["extraction_spec_id"] == "cypshift.trace.mmp.v3"
    assert receipt["sha256"] == hashlib.sha256(encoded).hexdigest()
    assert receipt["sha256"] == (
        "3d0b097602008457ffcefd4a0cf93673b5522112f91637634d162f5e619ff202"
    )
    ids = extraction["ids"]
    assert ids["v3_spec_hash"].startswith("The exact extraction")
    assert all(
        material[0] == "v3_spec_hash"
        for key, material in ids.items()
        if key.endswith("_material") and isinstance(material, list)
    )
    schemas = contract["outputs"]["schemas"]
    for name in (
        "transformation_pairs.csv",
        "episode_transformations.csv",
        "transformation_coverage.json",
        "manifest.json",
        "failure_receipt.json",
    ):
        assert schemas[name]["schema_version"].endswith(".v3")


def test_stereo_vocabulary_reference_maps_and_fallback_are_exact() -> None:
    stereo = load()["extraction"]["fragmentation"]["stereo_policy"]
    assert stereo["supported_kinds"] == ["Atom_Tetrahedral", "Bond_Double"]
    assert stereo["value_vocabulary"] == {
        "Atom_Tetrahedral": ["R", "S", "r", "s"],
        "Bond_Double": ["E", "Z"],
        "source": stereo["value_vocabulary"]["source"],
    }
    assert "rdCIPLabeler.AssignCIPLabels" in stereo["explicitness"]
    assert stereo["discovery"]["rdkit_call"] == (
        "Chem.FindPotentialStereo(mol, cleanIt=True, flagPossible=True)"
    )
    assert "Every returned StereoInfo" in stereo["discovery"]["completeness"]
    assert "Tet_CW/Tet_CCW" in stereo["value_vocabulary"]["source"]
    calls = stereo["map_calls"]
    assert calls["phi_call"].startswith("right_no_stereo.GetSubstructMatches")
    assert "phi[left_atom_index] = right_atom_index" in calls["phi_tuple"]
    assert calls["lambda_call"].startswith("left_no_stereo.GetSubstructMatches")
    assert "lambda[reference_atom_index] = left_atom_index" in calls["lambda_tuple"]
    assert (
        "rho[reference_atom_index] = phi[lambda[reference_atom_index]]"
        in calls["composition"]
    )
    assert "maxMatches=0" in calls["phi_call"]
    assert "maxMatches=0" in calls["lambda_call"]
    assert "lexicographically smallest" in stereo["mapping"]
    assert "isomericSmiles=True" in stereo["graph_test"]
    assert "isotope information must remain" in stereo["graph_test"]
    fallback = stereo["unsupported_kind_policy"]
    for token in ("atropisomeric", "cumulene", "square-planar", "octahedral"):
        assert token in fallback
    assert "AMBIGUOUS/C3" in fallback
    assert stereo["element_schema"]["Atom_Tetrahedral"] == {
        "kind": "Atom_Tetrahedral",
        "atom_indices": "[reference center atom index]",
        "bond_indices": "[]",
        "values": ["R", "S", "r", "s"],
    }
    assert stereo["element_schema"]["Bond_Double"]["values"] == ["E", "Z"]
    assert stereo["reversal"].startswith(
        "Keep kind, atom_indices, and bond_indices unchanged"
    )


def test_discovery_rejects_unspecified_supported_elements_before_cip() -> None:
    for smiles in ("FC=CC[C@H](O)Cl", "FC=CC[C@@H](O)Cl"):
        molecule, discovered = _discover(smiles)
        assert not _raw_stereo_is_unsupported(molecule)
        states = {(str(info.type), str(info.specified)) for info in discovered}
        assert ("Atom_Tetrahedral", "Specified") in states
        assert ("Bond_Double", "Unspecified") in states
        assert any(specified != "Specified" for _kind, specified in states)


def test_enhanced_and_raw_unsupported_stereo_are_c3_predicates() -> None:
    rr = Chem.MolFromSmiles("C[C@@H](F)[C@H](Cl)C |&1:1,3|")
    ss = Chem.MolFromSmiles("C[C@H](F)[C@@H](Cl)C |&1:1,3|")
    assert rr is not None and ss is not None
    assert rr.GetStereoGroups() and ss.GetStereoGroups()
    assert _cip_values("C[C@@H](F)[C@H](Cl)C |&1:1,3|") == (["R", "R"], [])
    assert _cip_values("C[C@H](F)[C@@H](Cl)C |&1:1,3|") == (["S", "S"], [])
    assert _raw_stereo_is_unsupported(rr)
    assert _raw_stereo_is_unsupported(ss)
    stereo = load()["extraction"]["fragmentation"]["stereo_policy"]
    assert (
        "len(mol.GetStereoGroups()) == 0"
        in stereo["raw_stereo_preflight"]["enhanced_stereo"]
    )
    assert "AMBIGUOUS/C3" in stereo["raw_stereo_preflight"]["enhanced_stereo"]

    tagged = Chem.MolFromSmiles("FC=CF")
    assert tagged is not None
    tagged.GetBondWithIdx(1).SetStereo(Chem.BondStereo.STEREOANY)
    assert _raw_stereo_is_unsupported(tagged)


def test_exact_map_orientation_attributes_and_atom_maps_execute() -> None:
    left = Chem.MolFromSmiles("[CH3:1][CH3:2]")
    right = Chem.MolFromSmiles("[CH3:2][CH3:1]")
    assert left is not None and right is not None
    Chem.RemoveStereochemistry(left)
    Chem.RemoveStereochemistry(right)
    assert _reference_smiles("[CH3:1][CH3:2]") == _reference_smiles("[CH3:2][CH3:1]")
    phi_values = right.GetSubstructMatches(
        left, uniquify=False, useChirality=False, maxMatches=0
    )
    assert phi_values == ((0, 1), (1, 0))
    exact_phi = [phi for phi in phi_values if _exact_graph_map(left, right, phi)]
    assert exact_phi == [(1, 0)]

    reference = Chem.MolFromSmiles(_reference_smiles("[CH3:1][CH3:2]"))
    assert reference is not None
    lambda_values = left.GetSubstructMatches(
        reference, uniquify=False, useChirality=False, maxMatches=0
    )
    exact_lambda = [
        value for value in lambda_values if _exact_graph_map(reference, left, value)
    ]
    assert exact_lambda == [(0, 1)]
    phi = exact_phi[0]
    lambda_value = exact_lambda[0]
    rho = tuple(phi[lambda_value[index]] for index in range(reference.GetNumAtoms()))
    assert rho == (1, 0)

    map_filter = load()["extraction"]["fragmentation"]["stereo_policy"][
        "exact_map_filter"
    ]
    assert map_filter["atom_attributes"] == [
        "atomic_number",
        "isotope",
        "formal_charge",
        "num_radical_electrons",
        "is_aromatic",
        "num_explicit_hs",
        "num_implicit_hs",
        "no_implicit",
        "atom_map_number",
    ]
    assert map_filter["bond_attributes"] == [
        "bond_type",
        "is_aromatic",
        "is_conjugated",
    ]
    assert "Never clear or ignore atom maps" in map_filter["atom_maps"]
    assert map_filter["directional_bond_types"] == [
        "DATIVE",
        "DATIVEL",
        "DATIVER",
        "DATIVEONE",
    ]
    assert (
        "map[source.GetBeginAtomIdx()] == target.GetBeginAtomIdx()"
        in map_filter["directional_bond_predicate"]
    )


def test_exact_map_rejects_implicit_h_and_dative_direction_reversal() -> None:
    molecule = Chem.MolFromSmiles("C[C@H](F)N->N[C@@H](F)C")
    assert molecule is not None
    Chem.RemoveStereochemistry(molecule)
    mappings = molecule.GetSubstructMatches(
        molecule, uniquify=False, useChirality=False, maxMatches=0
    )
    assert mappings == (
        (0, 1, 2, 3, 4, 5, 6, 7),
        (7, 5, 6, 4, 3, 1, 2, 0),
    )
    identity, reversed_mapping = mappings
    assert _exact_graph_map(molecule, molecule, identity)
    assert not _exact_graph_map(molecule, molecule, reversed_mapping)
    assert molecule.GetAtomWithIdx(3).GetNumImplicitHs() == 2
    assert molecule.GetAtomWithIdx(reversed_mapping[3]).GetNumImplicitHs() == 1
    dative = molecule.GetBondWithIdx(3)
    assert dative.GetBondType() == Chem.BondType.DATIVE
    assert reversed_mapping[dative.GetBeginAtomIdx()] != dative.GetBeginAtomIdx()
    assert reversed_mapping[dative.GetEndAtomIdx()] != dative.GetEndAtomIdx()


def test_stereo_records_and_reversal_use_cip_not_raw_orientation() -> None:
    tetra = _changed_record("C[C@H](O)Cl", "C[C@@H](O)Cl")
    assert tetra == [
        {
            "kind": "Atom_Tetrahedral",
            "atom_indices": [1],
            "bond_indices": [],
            "left_value": "R",
            "right_value": "S",
        }
    ]
    double = _changed_record("F/C=C/F", "F/C=C\\F")
    assert double == [
        {
            "kind": "Bond_Double",
            "atom_indices": [1, 2],
            "bond_indices": [1],
            "left_value": "E",
            "right_value": "Z",
        }
    ]
    reversed_tetra = [
        {
            **element,
            "left_value": element["right_value"],
            "right_value": element["left_value"],
        }
        for element in tetra
    ]
    assert reversed_tetra[0]["left_value"] == "S"
    assert reversed_tetra[0]["right_value"] == "R"


def test_rdkit_tetra_double_isotope_and_atom_order_witnesses() -> None:
    assert _cip_values("C[C@H](O)Cl") == (["R"], [])
    assert _cip_values("C[C@@H](O)Cl") == (["S"], [])
    assert _cip_values("F/C=C/F") == ([], ["E"])
    assert _cip_values("F/C=C\\F") == ([], ["Z"])
    assert _reference_smiles("C[C@H](O)Cl") == _reference_smiles("C[C@@H](O)Cl")
    isotope_reference = _reference_smiles("[13CH3][C@H](O)Cl")
    assert "13C" in isotope_reference
    assert isotope_reference != _reference_smiles("C[C@H](O)Cl")

    molecule = Chem.MolFromSmiles("[13CH3][C@H](O)Cl")
    assert molecule is not None
    renumbered = Chem.RenumberAtoms(
        molecule, list(reversed(range(molecule.GetNumAtoms())))
    )
    renumbered_smiles = Chem.MolToSmiles(
        renumbered, canonical=False, isomericSmiles=True
    )
    assert _reference_smiles(renumbered_smiles) == isotope_reference
    assert _cip_values(renumbered_smiles) == (["R"], [])


def test_embedding_environment_and_warning_repairs_are_closed() -> None:
    extraction = load()["extraction"]
    candidate = extraction["candidate_generation"]
    assert candidate["maximum_constant_embedding_matches"] == 1000000
    assert "AMBIGUOUS/S2" in candidate["constant_embedding_cap_policy"]
    recovery = extraction["canonicalization"]["constant_embedding_recovery"]
    assert "uniquify=False" in recovery["rdkit_call"]
    assert "useChirality=True" in recovery["rdkit_call"]
    assert "maxMatches=1000000" in recovery["rdkit_call"]
    assert "every returned match" in recovery["all_maps"]
    assert "exact string equals" in recovery["variable_reconstruction"]
    assert "different changed-index arrays" in recovery["symmetry"]
    environment = extraction["canonicalization"]["attachment_environment_rule"]
    assert "sorted union of atom_idx" in environment["construction"]
    assert "always included" in environment["root"]
    warnings = extraction["serialization"]["warning_vocabulary"]
    assert warnings == {
        "valid": [],
        "C2": ["multiple_fragments_input"],
        "C3": ["stereo_not_confident"],
        "C6": ["standardization_changed"],
        "S2": ["ambiguous_decomposition"],
        "S3": ["inconsistent_direction"],
        "S6": ["unsupported_decomposition"],
    }


def _replace_v3_spec(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("v3_spec_hash", "v2_spec_hash").replace(
            "every v3 ID", "every v2 ID"
        )
    if isinstance(value, list):
        return [_replace_v3_spec(item) for item in value]
    if isinstance(value, dict):
        return {
            _replace_v3_spec(key): _replace_v3_spec(item) for key, item in value.items()
        }
    return value


def test_every_nonrepaired_semantic_equals_v2() -> None:
    parent = load(PARENT_PATH)
    child = copy.deepcopy(load())
    for key in (
        "schema_version",
        "purpose",
        "parent",
        "inheritance",
    ):
        child[key] = copy.deepcopy(parent[key])

    child_extraction = child["extraction"]
    parent_extraction = parent["extraction"]
    child_extraction["extraction_spec_id"] = parent_extraction["extraction_spec_id"]
    child_extraction["extraction_spec_receipt"] = copy.deepcopy(
        parent_extraction["extraction_spec_receipt"]
    )
    for key in (
        "maximum_constant_embedding_matches",
        "constant_embedding_cap_policy",
    ):
        child_extraction["candidate_generation"].pop(key)
    child_extraction["fragmentation"]["stereo_policy"] = copy.deepcopy(
        parent_extraction["fragmentation"]["stereo_policy"]
    )
    child_canonical = child_extraction["canonicalization"]
    parent_canonical = parent_extraction["canonicalization"]
    child_canonical.pop("constant_embedding_recovery")
    child_canonical["attachment_environment_rule"] = copy.deepcopy(
        parent_canonical["attachment_environment_rule"]
    )
    child_canonical["candidate_material_schema"]["sort_rule"] = parent_canonical[
        "candidate_material_schema"
    ]["sort_rule"]
    child_extraction["ids"] = _replace_v3_spec(child_extraction["ids"])
    child_extraction["ids"]["stereo_exact_transformation_id"] = parent_extraction[
        "ids"
    ]["stereo_exact_transformation_id"]
    child_extraction["class_rules"] = _replace_v3_spec(child_extraction["class_rules"])
    child_serial = child_extraction["serialization"]
    parent_serial = parent_extraction["serialization"]
    child_serial["warnings"] = parent_serial["warnings"]
    child_serial.pop("warning_vocabulary")
    child_serial["field_rules"]["warnings"] = parent_serial["field_rules"]["warnings"]

    schemas = child["outputs"]["schemas"]
    parent_schemas = parent["outputs"]["schemas"]
    for name in (
        "transformation_pairs.csv",
        "episode_transformations.csv",
        "transformation_coverage.json",
        "manifest.json",
        "failure_receipt.json",
    ):
        schemas[name]["schema_version"] = parent_schemas[name]["schema_version"]
    for name in ("transformation_pairs.csv", "episode_transformations.csv"):
        schemas[name]["invalid_sentinels"]["warnings"] = parent_schemas[name][
            "invalid_sentinels"
        ]["warnings"]

    assert child == parent
