"""Exact, synthetic-only R4 v4 stereochemical transformation decisions.

This module deliberately implements only the cut-zero stereo branch.  A
non-identical non-stereo graph is returned to the ordinary MMP extractor as
``not_applicable``; this module does not attempt fragmentation or I/O.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from rdkit import Chem, rdBase
from rdkit.Chem import rdCIPLabeler

from cypshift.openadmet_transformation_types import StereoElement
from cypshift.schema import MoleculeRecord, MoleculeStatus

EXTRACTION_SPEC_SHA256 = (
    "59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950"
)
STEREOCHEMICAL_CHANGE = "stereochemical_change"

_ALLOWED_ATOM_TAGS = {
    Chem.ChiralType.CHI_UNSPECIFIED,
    Chem.ChiralType.CHI_TETRAHEDRAL_CW,
    Chem.ChiralType.CHI_TETRAHEDRAL_CCW,
}
_ALLOWED_BOND_STEREO = {
    Chem.BondStereo.STEREONONE,
    Chem.BondStereo.STEREOE,
    Chem.BondStereo.STEREOZ,
}
_DIRECTIONAL_BOND_TYPES = {
    Chem.BondType.DATIVE,
    Chem.BondType.DATIVEL,
    Chem.BondType.DATIVER,
    Chem.BondType.DATIVEONE,
}
_SUPPORTED_TYPES = {
    Chem.StereoType.Atom_Tetrahedral,
    Chem.StereoType.Bond_Double,
}
_CIP_VALUES = {
    "Atom_Tetrahedral": frozenset({"R", "S", "r", "s"}),
    "Bond_Double": frozenset({"E", "Z"}),
}


class StereoDecisionStatus(StrEnum):
    """The exhaustive outcomes of the pure stereo-only decision."""

    NOT_APPLICABLE = "not_applicable"
    VALID_STEREO = "VALID_STEREO"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class StereoCandidate:
    """The one valid cut-zero candidate in the supplied left-to-right direction."""

    canonical_nonstereo_full_graph: str
    stereo_elements: tuple[StereoElement, ...]
    changed_left_atom_indices: tuple[int, ...]
    changed_right_atom_indices: tuple[int, ...]
    conserved_heavy_atoms: int
    exact_transformation_id: str
    transformation_class_id: str
    candidate_material: str
    status: str = "VALID_STEREO"
    cut_count: int = 0
    transformation_class: str = STEREOCHEMICAL_CHANGE
    conserved_core_smiles: str = ""
    removed_labeled_fragment: str = ""
    added_labeled_fragment: str = ""
    attachment_labels_array: tuple[int, ...] = ()
    left_attachment_environment_radius_1: tuple[str, ...] = ()
    left_attachment_environment_radius_2: tuple[str, ...] = ()
    right_attachment_environment_radius_1: tuple[str, ...] = ()
    right_attachment_environment_radius_2: tuple[str, ...] = ()
    left_virtual_h_eligible: bool = False
    right_virtual_h_eligible: bool = False
    changed_heavy_atom_fraction: str = "0/1"

    def reversed(self) -> StereoCandidate:
        """Return the exact direction reversal on the common reference graph."""

        elements = tuple(
            sorted(
                (
                    StereoElement(
                        kind=element.kind,
                        atom_indices=element.atom_indices,
                        bond_indices=element.bond_indices,
                        left_value=element.right_value,
                        right_value=element.left_value,
                    )
                    for element in self.stereo_elements
                ),
                key=_element_sort_key,
            )
        )
        return _candidate(self.canonical_nonstereo_full_graph, elements)


@dataclass(frozen=True, slots=True)
class StereoDecision:
    """A valid candidate, a C3 rejection, or delegation to ordinary MMP."""

    status: StereoDecisionStatus
    candidate: StereoCandidate | None
    failure_code: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _LocatedStereo:
    kind: str
    centered_on: int
    value: str


def extract_stereo_decision(
    left: MoleculeRecord, right: MoleculeRecord
) -> StereoDecision:
    """Apply the receipt-bound R4 v4 stereo-only decision to two records."""

    if (
        left.status is not MoleculeStatus.ACCEPTED
        or right.status is not MoleculeStatus.ACCEPTED
        or left.standardized_structure is None
        or right.standardized_structure is None
    ):
        return _not_applicable()

    raw_left = _parse(left.raw_structure)
    raw_right = _parse(right.raw_structure)
    if raw_left is None or raw_right is None:
        return _ambiguous()
    raw_stereo_unsupported = _unsupported_raw_stereo(
        raw_left
    ) or _unsupported_raw_stereo(raw_right)

    standardized_left = _parse(left.standardized_structure)
    standardized_right = _parse(right.standardized_structure)
    if standardized_left is None or standardized_right is None:
        return _ambiguous()
    standardized_stereo_unsupported = _unsupported_raw_stereo(
        standardized_left
    ) or _unsupported_raw_stereo(standardized_right)
    canonical_left = _canonical_reparse(standardized_left)
    canonical_right = _canonical_reparse(standardized_right)
    if canonical_left is None or canonical_right is None:
        return _ambiguous()
    canonical_stereo_unsupported = _unsupported_raw_stereo(
        canonical_left
    ) or _unsupported_raw_stereo(canonical_right)

    left_no_stereo, left_graph = _without_stereo(canonical_left)
    right_no_stereo, right_graph = _without_stereo(canonical_right)
    if left_graph != right_graph:
        return _not_applicable()
    if (
        raw_stereo_unsupported
        or standardized_stereo_unsupported
        or canonical_stereo_unsupported
    ):
        return _ambiguous()

    # Discovery is deliberately before stale-CIP cleanup and labeling.
    left_infos = tuple(
        Chem.FindPotentialStereo(canonical_left, cleanIt=True, flagPossible=True)
    )
    right_infos = tuple(
        Chem.FindPotentialStereo(canonical_right, cleanIt=True, flagPossible=True)
    )
    if not _complete_supported_discovery(
        left_infos
    ) or not _complete_supported_discovery(right_infos):
        return _ambiguous()

    _assign_fresh_cip(canonical_left)
    _assign_fresh_cip(canonical_right)
    left_stereo = _located_stereo(canonical_left, left_infos)
    right_stereo = _located_stereo(canonical_right, right_infos)
    if left_stereo is None or right_stereo is None:
        return _ambiguous()
    left_tetra_centers = _tetrahedral_centers(left_stereo)
    right_tetra_centers = _tetrahedral_centers(right_stereo)

    reference = _parse(left_graph)
    if reference is None:
        return _ambiguous()
    phi_maps = tuple(
        mapping
        for mapping in right_no_stereo.GetSubstructMatches(
            left_no_stereo,
            uniquify=False,
            useChirality=False,
            maxMatches=0,
        )
        if _is_exact_graph_map(left_no_stereo, right_no_stereo, mapping)
    )
    lambda_maps = tuple(
        mapping
        for mapping in left_no_stereo.GetSubstructMatches(
            reference,
            uniquify=False,
            useChirality=False,
            maxMatches=0,
        )
        if _is_reference_graph_map(
            reference,
            left_no_stereo,
            mapping,
            target_tetrahedral_centers=left_tetra_centers,
        )
    )
    if not phi_maps or not lambda_maps:
        return _ambiguous()

    retained_by_phi: list[bytes] = []
    records_by_bytes: dict[bytes, tuple[StereoElement, ...]] = {}
    for phi in phi_maps:
        lambda_materials: list[bytes] = []
        for lambda_map in lambda_maps:
            rho = tuple(phi[lambda_map[index]] for index in range(len(lambda_map)))
            if not _is_reference_graph_map(
                reference,
                right_no_stereo,
                rho,
                target_tetrahedral_centers=right_tetra_centers,
            ):
                continue
            elements = _mapped_changes(
                reference,
                canonical_left,
                canonical_right,
                left_stereo,
                right_stereo,
                lambda_map,
                rho,
            )
            if elements is None:
                continue
            material = _canonical_json_bytes(
                [_element_dict(element) for element in elements]
            )
            records_by_bytes[material] = elements
            lambda_materials.append(material)
        if not lambda_materials:
            return _ambiguous()
        retained_by_phi.append(min(lambda_materials))

    if len(set(retained_by_phi)) != 1:
        return _ambiguous()
    retained = retained_by_phi[0]
    elements = records_by_bytes[retained]
    if not elements:
        return _ambiguous()
    return StereoDecision(
        status=StereoDecisionStatus.VALID_STEREO,
        candidate=_candidate(left_graph, elements),
        failure_code=None,
        warnings=(),
    )


def _parse(smiles: str) -> Chem.Mol | None:
    with rdBase.BlockLogs():
        return Chem.MolFromSmiles(smiles)


def _canonical_reparse(molecule: Chem.Mol) -> Chem.Mol | None:
    canonical = Chem.MolToSmiles(
        molecule,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )
    return _parse(canonical)


def _unsupported_raw_stereo(molecule: Chem.Mol) -> bool:
    return (
        len(molecule.GetStereoGroups()) != 0
        or any(
            atom.GetChiralTag() not in _ALLOWED_ATOM_TAGS
            for atom in molecule.GetAtoms()
        )
        or any(
            bond.GetStereo() not in _ALLOWED_BOND_STEREO for bond in molecule.GetBonds()
        )
    )


def _without_stereo(molecule: Chem.Mol) -> tuple[Chem.Mol, str]:
    clone = Chem.Mol(molecule)
    Chem.RemoveStereochemistry(clone)
    graph = Chem.MolToSmiles(
        clone,
        canonical=True,
        isomericSmiles=True,
        kekuleSmiles=False,
        allBondsExplicit=False,
        allHsExplicit=False,
    )
    return clone, graph


def _complete_supported_discovery(infos: tuple[Any, ...]) -> bool:
    return all(
        info.type in _SUPPORTED_TYPES
        and info.specified == Chem.StereoSpecified.Specified
        for info in infos
    )


def _assign_fresh_cip(molecule: Chem.Mol) -> None:
    for atom in molecule.GetAtoms():
        if atom.HasProp("_CIPCode"):
            atom.ClearProp("_CIPCode")
    for bond in molecule.GetBonds():
        if bond.HasProp("_CIPCode"):
            bond.ClearProp("_CIPCode")
    rdCIPLabeler.AssignCIPLabels(molecule)


def _located_stereo(
    molecule: Chem.Mol, infos: tuple[Any, ...]
) -> tuple[_LocatedStereo, ...] | None:
    located: list[_LocatedStereo] = []
    for info in infos:
        kind = str(info.type)
        centered_on = int(info.centeredOn)
        item = (
            molecule.GetAtomWithIdx(centered_on)
            if kind == "Atom_Tetrahedral"
            else molecule.GetBondWithIdx(centered_on)
        )
        if not item.HasProp("_CIPCode"):
            return None
        value = item.GetProp("_CIPCode")
        if value not in _CIP_VALUES[kind]:
            return None
        located.append(_LocatedStereo(kind, centered_on, value))
    return tuple(located)


def _tetrahedral_centers(
    located: tuple[_LocatedStereo, ...],
) -> frozenset[int]:
    return frozenset(
        stereo.centered_on for stereo in located if stereo.kind == "Atom_Tetrahedral"
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


def _atom_nonhydrogen_attributes(atom: Chem.Atom) -> tuple[Any, ...]:
    return (
        atom.GetAtomicNum(),
        atom.GetIsotope(),
        atom.GetFormalCharge(),
        atom.GetNumRadicalElectrons(),
        atom.GetIsAromatic(),
        atom.GetAtomMapNum(),
    )


def _atom_hydrogen_partition(atom: Chem.Atom) -> tuple[int, int, bool]:
    return atom.GetNumExplicitHs(), atom.GetNumImplicitHs(), atom.GetNoImplicit()


def _bond_attributes(bond: Chem.Bond) -> tuple[Any, ...]:
    return bond.GetBondType(), bond.GetIsAromatic(), bond.GetIsConjugated()


def _is_exact_graph_map(
    source: Chem.Mol, target: Chem.Mol, mapping: tuple[int, ...]
) -> bool:
    if not _is_full_bijection(source, target, mapping):
        return False
    if any(
        _atom_attributes(source.GetAtomWithIdx(index))
        != _atom_attributes(target.GetAtomWithIdx(mapped))
        for index, mapped in enumerate(mapping)
    ):
        return False
    return _bonds_are_exact(source, target, mapping)


def _is_reference_graph_map(
    source: Chem.Mol,
    target: Chem.Mol,
    mapping: tuple[int, ...],
    *,
    target_tetrahedral_centers: frozenset[int],
) -> bool:
    """Apply the v4 tetra-only H partition exception to a lambda or rho."""

    if not _is_full_bijection(source, target, mapping):
        return False
    for source_index, target_index in enumerate(mapping):
        source_atom = source.GetAtomWithIdx(source_index)
        target_atom = target.GetAtomWithIdx(target_index)
        if _atom_nonhydrogen_attributes(source_atom) != (
            _atom_nonhydrogen_attributes(target_atom)
        ):
            return False
        source_h = _atom_hydrogen_partition(source_atom)
        target_h = _atom_hydrogen_partition(target_atom)
        if source_h == target_h:
            continue
        if not (
            target_index in target_tetrahedral_centers
            and source_h == (0, 1, False)
            and target_h == (1, 0, True)
            and source_atom.GetTotalNumHs() == target_atom.GetTotalNumHs() == 1
        ):
            return False
    return _bonds_are_exact(source, target, mapping)


def _is_full_bijection(
    source: Chem.Mol, target: Chem.Mol, mapping: tuple[int, ...]
) -> bool:
    return (
        source.GetNumAtoms() == target.GetNumAtoms()
        and source.GetNumBonds() == target.GetNumBonds()
        and len(mapping) == source.GetNumAtoms()
        and set(mapping) == set(range(target.GetNumAtoms()))
    )


def _bonds_are_exact(
    source: Chem.Mol, target: Chem.Mol, mapping: tuple[int, ...]
) -> bool:
    for source_bond in source.GetBonds():
        mapped_bond = target.GetBondBetweenAtoms(
            mapping[source_bond.GetBeginAtomIdx()],
            mapping[source_bond.GetEndAtomIdx()],
        )
        if mapped_bond is None or _bond_attributes(source_bond) != _bond_attributes(
            mapped_bond
        ):
            return False
        if source_bond.GetBondType() in _DIRECTIONAL_BOND_TYPES and (
            mapping[source_bond.GetBeginAtomIdx()] != mapped_bond.GetBeginAtomIdx()
            or mapping[source_bond.GetEndAtomIdx()] != mapped_bond.GetEndAtomIdx()
        ):
            return False
    return True


def _mapped_changes(
    reference: Chem.Mol,
    left: Chem.Mol,
    right: Chem.Mol,
    left_stereo: tuple[_LocatedStereo, ...],
    right_stereo: tuple[_LocatedStereo, ...],
    lambda_map: tuple[int, ...],
    rho: tuple[int, ...],
) -> tuple[StereoElement, ...] | None:
    left_inverse = _inverse_map(lambda_map)
    right_inverse = _inverse_map(rho)
    left_values = _reference_stereo_values(reference, left, left_stereo, left_inverse)
    right_values = _reference_stereo_values(
        reference, right, right_stereo, right_inverse
    )
    if left_values is None or right_values is None:
        return None
    if left_values.keys() != right_values.keys():
        return None
    elements = [
        StereoElement(
            kind=key[0],
            atom_indices=key[1],
            bond_indices=key[2],
            left_value=left_values[key],
            right_value=right_values[key],
        )
        for key in left_values
        if left_values[key] != right_values[key]
    ]
    return tuple(sorted(elements, key=_element_sort_key))


def _inverse_map(mapping: tuple[int, ...]) -> dict[int, int]:
    return {target: source for source, target in enumerate(mapping)}


def _reference_stereo_values(
    reference: Chem.Mol,
    molecule: Chem.Mol,
    located: tuple[_LocatedStereo, ...],
    inverse: dict[int, int],
) -> dict[tuple[str, tuple[int, ...], tuple[int, ...]], str] | None:
    values: dict[tuple[str, tuple[int, ...], tuple[int, ...]], str] = {}
    for stereo in located:
        key: tuple[str, tuple[int, ...], tuple[int, ...]]
        if stereo.kind == "Atom_Tetrahedral":
            key = (stereo.kind, (inverse[stereo.centered_on],), ())
        else:
            bond = molecule.GetBondWithIdx(stereo.centered_on)
            atom_indices = tuple(
                sorted(
                    (
                        inverse[bond.GetBeginAtomIdx()],
                        inverse[bond.GetEndAtomIdx()],
                    )
                )
            )
            reference_bond = reference.GetBondBetweenAtoms(*atom_indices)
            key = (stereo.kind, atom_indices, (reference_bond.GetIdx(),))
        if key in values:
            return None
        values[key] = stereo.value
    return values


def _element_sort_key(
    element: StereoElement,
) -> tuple[tuple[int, ...], tuple[int, ...], str, str, str]:
    return (
        element.atom_indices,
        element.bond_indices,
        element.kind,
        element.left_value,
        element.right_value,
    )


def _element_dict(element: StereoElement) -> dict[str, Any]:
    return {
        "atom_indices": list(element.atom_indices),
        "bond_indices": list(element.bond_indices),
        "kind": element.kind,
        "left_value": element.left_value,
        "right_value": element.right_value,
    }


def _candidate(
    reference_graph: str, elements: tuple[StereoElement, ...]
) -> StereoCandidate:
    changed_indices = tuple(
        sorted({index for element in elements for index in element.atom_indices})
    )
    element_json = [_element_dict(element) for element in elements]
    material_object: dict[str, Any] = {
        "added_labeled_fragment": "",
        "attachment_labels_array": [],
        "changed_heavy_atom_fraction": "0/1",
        "changed_left_atom_indices": list(changed_indices),
        "changed_right_atom_indices": list(changed_indices),
        "class": STEREOCHEMICAL_CHANGE,
        "conserved_core_smiles": reference_graph,
        "cut_count": 0,
        "left_attachment_environment_radius_1": [],
        "left_attachment_environment_radius_2": [],
        "left_virtual_h_eligible": False,
        "removed_labeled_fragment": "",
        "right_attachment_environment_radius_1": [],
        "right_attachment_environment_radius_2": [],
        "right_virtual_h_eligible": False,
        "stereo": {"changed": True, "elements": element_json},
    }
    reference = _parse(reference_graph)
    assert reference is not None
    exact_id = _sha256_json([EXTRACTION_SPEC_SHA256, reference_graph, element_json])
    class_id = _sha256_json([EXTRACTION_SPEC_SHA256, STEREOCHEMICAL_CHANGE])
    return StereoCandidate(
        canonical_nonstereo_full_graph=reference_graph,
        stereo_elements=elements,
        changed_left_atom_indices=changed_indices,
        changed_right_atom_indices=changed_indices,
        conserved_heavy_atoms=sum(
            atom.GetAtomicNum() > 1 for atom in reference.GetAtoms()
        ),
        exact_transformation_id=exact_id,
        transformation_class_id=class_id,
        candidate_material=_canonical_json_bytes(material_object).decode("utf-8"),
        conserved_core_smiles=reference_graph,
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _not_applicable() -> StereoDecision:
    return StereoDecision(StereoDecisionStatus.NOT_APPLICABLE, None, None, ())


def _ambiguous() -> StereoDecision:
    return StereoDecision(
        StereoDecisionStatus.AMBIGUOUS,
        None,
        "C3",
        ("stereo_not_confident",),
    )


__all__ = [
    "EXTRACTION_SPEC_SHA256",
    "StereoCandidate",
    "StereoDecision",
    "StereoDecisionStatus",
    "StereoElement",
    "extract_stereo_decision",
]
